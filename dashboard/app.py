"""
Dashboard Flask — Blockchain Certs
Cada nodo tiene su propio rol y su propio dashboard.
"""

import asyncio
from flask import Flask, render_template, jsonify, request, redirect, send_file
from io import BytesIO
from core.titulo import (
    build_titulo_tx, validate_titulo_tx,
    get_titulos_by_wallet, get_all_titulos,
    get_titulos_pendientes,
)
import config


CARRERAS_ANAHUAC = [
    'Administración y Estrategia de Negocios',
    'Derecho',
    'Psicología',
    'Ingeniería en Tecnologías de la Información y Ciberseguridad',
    'Nutrición y Ciencia de los Alimentos',
]



class NodeDashboard:
    def __init__(self, node, dashboard_port, dashboard_mode='manual'):
        self.node           = node
        self.dashboard_port = dashboard_port
        self.dashboard_mode = dashboard_mode
        self.app            = Flask(__name__)
        self._setup_routes()

    def _setup_routes(self):

        # ── Página principal ───────────────────────────────────

        @self.app.route('/')
        def index():
            institucion  = getattr(self.node, 'institucion', '') or config.NOMBRE_INSTITUCION
            display_name = getattr(self.node, 'display_name', self.node.id)

            carreras = CARRERAS_ANAHUAC

            return render_template(
                'dashboard.html',
                node_id        = self.node.id,
                display_name   = display_name,
                p2p_port       = self.node.port,
                dashboard_port = self.dashboard_port,
                node_role      = self.node.node_role,
                institucion    = institucion,
                carreras       = carreras,
                quorum         = config.QUORUM_REQUIRED,
            )

        # ── Estado del nodo ────────────────────────────────────

        @self.app.route('/api/status')
        def api_status():
            is_issuer    = self.node.wallet.address in config.AUTHORIZED_ISSUERS
            display_name = getattr(self.node, 'display_name', self.node.id)
            institucion  = getattr(self.node, 'institucion', '') or config.NOMBRE_INSTITUCION

            credential_count = 0
            if self.node.node_role == 'graduate':
                credential_count = len(
                    get_titulos_by_wallet(self.node.blockchain, self.node.wallet.address)
                )

            return jsonify({
                'node_id':          self.node.id,
                'display_name':     display_name,
                'address':          self.node.wallet.address,
                'chain_height':     self.node.blockchain.get_height(),
                'mempool_count':    len(self.node.blockchain.mempool),
                'peers_count':      len(self.node.peers_connected),
                'blocks_mined':     self.node.blocks_mined,
                'node_role':        self.node.node_role,
                'is_issuer':        is_issuer,
                'institucion':      institucion,
                'credential_count': credential_count,
                'latest_hash': (
                    self.node.blockchain.get_latest_block().hash[:16]
                    if self.node.blockchain.chain else None
                ),
            })

        # ── Peers, cadena, mempool ─────────────────────────────

        @self.app.route('/api/peers')
        def api_peers():
            return jsonify([
                {'address': addr, 'status': 'connected'}
                for addr in self.node.peers_connected.keys()
            ])

        @self.app.route('/api/mempool')
        def api_mempool():
            return jsonify([{
                'txid':      tx.short_hash(),
                'from':      tx.from_address[:16] + '...',
                'to':        tx.to_address[:16]   + '...',
                'amount':    tx.amount,
                'timestamp': tx.timestamp,
                'tipo':      tx.data.get('tipo', ''),
                'tipo_cert': tx.data.get('tipo_certificado', ''),
                'nombre':    tx.data.get('nombre', ''),
            } for tx in self.node.blockchain.mempool])

        @self.app.route('/api/chain')
        def api_chain():
            chain  = self.node.blockchain.chain
            recent = []
            for block in reversed(chain[-5:]):
                recent.append({
                    'hash':      block.hash[:16] + '...',
                    'full_hash': block.hash,
                    'height':    chain.index(block),
                    'txs':       len(block.transactions),
                    'timestamp': block.header.timestamp,
                    'nonce':     0,
                    'target':    block.header.difficulty_display,
                    'firmas':    len(block.header.signatures),
                })
            return jsonify({
                'height':      len(chain),
                'latest_hash': chain[-1].hash[:16] + '...' if chain else None,
                'blocks':      recent,
            })

        @self.app.route('/api/block/<block_hash>')
        def api_block(block_hash):
            block = self.node.blockchain.get_block_by_hash(block_hash)
            if not block:
                return jsonify({'error': 'Bloque no encontrado'}), 404
            return jsonify({
                'hash':        block.hash,
                'prev_hash':   block.header.prev_hash[:16] + '...',
                'merkle_root': block.header.merkle_root[:16] + '...',
                'timestamp':   block.header.timestamp,
                'nonce':       0,
                'target':      block.header.difficulty_display,
                'firmas':      list(block.header.signatures.keys()),
                'txs': [{
                    'txid':      tx.short_hash(),
                    'from':      tx.from_address[:16] + '...',
                    'to':        tx.to_address[:16]   + '...',
                    'amount':    tx.amount,
                    'tipo':      tx.data.get('tipo', 'normal') if tx.data else 'normal',
                    'tipo_cert': tx.data.get('tipo_certificado', ''),
                    'nombre':    tx.data.get('nombre', ''),
                    'type':      'coinbase' if tx.is_coinbase() else 'normal',
                } for tx in block.transactions],
                'tx_count': len(block.transactions),
            })

        @self.app.route('/api/block/<block_hash>/verify')
        def api_block_verify(block_hash):
            block = self.node.blockchain.get_block_by_hash(block_hash)
            if not block:
                return jsonify({'error': 'Bloque no encontrado'}), 404

            chain = self.node.blockchain.chain
            idx   = next((i for i, b in enumerate(chain) if b.hash == block_hash), None)

            from core.wallet import Wallet as W
            msg        = block.header.hash_without_sigs().encode()
            valid_sigs = 0
            for addr, sig_hex in block.header.signatures.items():
                if addr not in config.AUTHORIZED_VALIDATORS:
                    continue
                pubkey_hex = config.VALIDATOR_PUBKEYS.get(addr)
                if not pubkey_hex:
                    continue
                try:
                    if W.verify_from_pubkey_hex(pubkey_hex, msg, bytes.fromhex(sig_hex)):
                        valid_sigs += 1
                except Exception:
                    continue

            poa_ok    = valid_sigs >= config.QUORUM_REQUIRED
            merkle_ok = block.validate_merkle_root()
            txs_ok    = block.validate_transactions()
            prev_ok   = (idx == 0) or (
                idx is not None and block.header.prev_hash == chain[idx - 1].hash
            )

            return jsonify({
                'hash':      block_hash,
                'height':    idx,
                'all_valid': poa_ok and merkle_ok and prev_ok and txs_ok,
                'checks': {
                    'poa':    {'ok': poa_ok,    'label': 'Firmas PoA',       'detail': f'{valid_sigs}/{config.QUORUM_REQUIRED} firmas válidas'},
                    'merkle': {'ok': merkle_ok, 'label': 'Merkle Root',      'detail': 'Integridad del árbol de TXs'},
                    'prev':   {'ok': prev_ok,   'label': 'Enlace prev_hash', 'detail': 'Conecta con bloque anterior'},
                    'txs':    {'ok': txs_ok,    'label': 'Firmas de TXs',    'detail': f'{len(block.transactions)} transacciones verificadas'},
                },
            })

        # ── Addresses conocidas ────────────────────────────────

        @self.app.route('/api/addresses')
        def api_addresses():
            try:
                all_addrs = self.node.seed_client.get_addresses(
                    exclude_host=self.node.host,
                    exclude_port=self.node.port,
                )
                graduates = [
                    a for a in all_addrs
                    if a.get('wallet_address') not in config.AUTHORIZED_VALIDATORS
                ]
                return jsonify(graduates)
            except Exception:
                return jsonify([])

        # ── Sellar bloque (solo issuers) ───────────────────────

        @self.app.route('/api/mine/once', methods=['POST'])
        def api_mine_once():
            """Produce un bloque PoA con las TXs del mempool."""
            if self.node.wallet.address not in config.AUTHORIZED_VALIDATORS:
                return jsonify({'error': 'Este nodo no está autorizado para sellar bloques'}), 403
            try:
                if self.node.loop is None:
                    return jsonify({'error': 'Nodo no iniciado'}), 503
                future = asyncio.run_coroutine_threadsafe(self.node.mine_once(), self.node.loop)
                block  = future.result(timeout=10)
                if block is None:
                    return jsonify({'error': 'Mempool vacío o no se pudo sellar el bloque'}), 400
                bloque_num = self.node.blockchain.get_height() - 1
                firma_hex  = list(block.header.signatures.values())[0] if block.header.signatures else ''
                return jsonify({
                    'status':            'ok',
                    'bloque_num':        bloque_num,
                    'validator_name':    getattr(self.node, 'display_name', ''),
                    'validator_address': self.node.wallet.address,
                    'firma_hex':         firma_hex[:64],
                    'firmas_count':      len(block.header.signatures),
                    'tx_count':          len(block.transactions),
                })
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        # ── TÍTULOS UNIVERSITARIOS ─────────────────────────────

        @self.app.route('/api/title/issue', methods=['POST'])
        def api_title_issue():
            """Emite un certificado digital universitario."""
            if self.node.wallet.address not in config.AUTHORIZED_ISSUERS:
                return jsonify({'error': 'Este nodo no tiene permisos de emisor'}), 403

            try:
                institucion_nodo = getattr(self.node, 'institucion', '') or config.NOMBRE_INSTITUCION

                tx = build_titulo_tx(
                    secretaria_wallet = self.node.wallet,
                    egresado_address  = request.form['egresado_address'],
                    nombre            = request.form['nombre'],
                    matricula         = request.form['matricula'],
                    carrera           = request.form['carrera'],
                    fecha             = request.form['fecha'],
                    institucion       = institucion_nodo,
                    tipo_certificado  = 'Certificado Total de Estudios',
                )

                valido, err = validate_titulo_tx(tx, self.node.blockchain)
                if not valido:
                    return jsonify({'error': err}), 400

                if not self.node.blockchain.add_transaction_to_mempool(tx):
                    return jsonify({'error': 'TX rechazada por el mempool'}), 400

                if self.node.loop:
                    asyncio.run_coroutine_threadsafe(
                        self.node.broadcast_transaction(tx), self.node.loop
                    )

                return jsonify({
                    'status':   'ok',
                    'tx_hash':  tx.hash(),
                    'hash_doc': tx.data['hash_doc'],
                    'mensaje':  'Certificado en mempool. Sella el bloque para confirmarlo.',
                })

            except KeyError as e:
                return jsonify({'error': f'Campo requerido: {e}'}), 400
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/title/lookup/<tx_hash>', methods=['GET'])
        def api_title_lookup(tx_hash):
            for block in self.node.blockchain.chain:
                for tx in block.transactions:
                    if (tx.hash() == tx_hash and
                            tx.data.get('tipo') == 'titulo_universitario'):
                        return jsonify({
                            'encontrado':         True,
                            'datos':              tx.data,
                            'bloque':             self.node.blockchain.chain.index(block),
                            'timestamp':          block.header.timestamp,
                            'firmas_validadores': list(block.header.signatures.keys()),
                        })
            return jsonify({'encontrado': False}), 404

        @self.app.route('/api/title/by_wallet/<address>', methods=['GET'])
        def api_title_by_wallet(address):
            return jsonify(get_titulos_by_wallet(self.node.blockchain, address))

        @self.app.route('/api/title/all', methods=['GET'])
        def api_title_all():
            return jsonify(get_all_titulos(self.node.blockchain))

        @self.app.route('/api/title/pending', methods=['GET'])
        def api_title_pending():
            return jsonify(get_titulos_pendientes(self.node.blockchain))

        @self.app.route('/api/title/<tx_hash>/pdf', methods=['GET'])
        def api_title_pdf(tx_hash):
            """Genera y devuelve el PDF del certificado para un TX hash dado."""
            from core.pdf_cert import generar_pdf_certificado
            for block in self.node.blockchain.chain:
                for tx in block.transactions:
                    if (tx.hash() == tx_hash and
                            tx.data.get('tipo') == 'titulo_universitario'):
                        datos = {
                            **tx.data,
                            'tx_hash':            tx_hash,
                            'bloque':             self.node.blockchain.chain.index(block),
                            'firmas_validadores': list(block.header.signatures.keys()),
                        }
                        pdf_bytes = generar_pdf_certificado(datos)
                        nombre_archivo = (
                            tx.data.get('nombre', 'certificado')
                            .replace(' ', '_').lower()
                        )
                        return send_file(
                            BytesIO(pdf_bytes),
                            mimetype='application/pdf',
                            as_attachment=True,
                            download_name=f'certificado_{nombre_archivo}.pdf',
                        )
            return jsonify({'error': 'Certificado no encontrado'}), 404

        # Tipos de certificado disponibles
        @self.app.route('/api/title/tipos', methods=['GET'])
        def api_title_tipos():
            return jsonify(TIPOS_CERTIFICADO)

    def run(self):
        self.app.run(
            host='0.0.0.0', port=self.dashboard_port,
            debug=False, use_reloader=False,
        )
