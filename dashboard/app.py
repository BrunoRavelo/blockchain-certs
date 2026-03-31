"""
Dashboard Flask para cada nodo P2P — Demo Títulos Universitarios

Cambios respecto al original (Sprint 2A):
- Eliminado: import de tx_orchestrator (borrado del proyecto)
- Eliminado: endpoints /api/tx/auto, /api/tx/manual, /api/tx/status
- Eliminado: parámetro orchestrator (ya no existe)
- Actualizado: api_status — target_info ahora muestra info PoA
- Actualizado: api_chain — sin nonce real, sin target PoW
- Actualizado: api_block_verify — reemplaza validate_pow() por firmas PoA
- Agregado: endpoints de títulos universitarios (Sprint 2A)
"""

import asyncio
from flask import Flask, render_template, jsonify, request, redirect
from network.p2p_node import MINING_AUTO, MINING_MANUAL
from core.titulo import (
    build_titulo_tx,
    validate_titulo_tx,
    get_titulos_by_wallet,
    get_all_titulos,
    get_titulos_pendientes,
    verify_document,
)
import config


class NodeDashboard:
    def __init__(self, node, dashboard_port, dashboard_mode='manual'):
        self.node           = node
        self.dashboard_port = dashboard_port
        self.dashboard_mode = dashboard_mode
        self.app            = Flask(__name__)
        self._setup_routes()

    def _setup_routes(self):

        # ──────────────────────────────────────────────────────
        # Dashboard principal
        # ──────────────────────────────────────────────────────

        @self.app.route('/')
        def index():
            return render_template(
                'dashboard.html',
                node_id        = self.node.id,
                p2p_port       = self.node.port,
                dashboard_port = self.dashboard_port,
                dashboard_mode = self.dashboard_mode,
                node_role      = config.NODE_ROLE,
                institucion    = config.NOMBRE_INSTITUCION,
            )

        # ──────────────────────────────────────────────────────
        # Estado del nodo
        # ──────────────────────────────────────────────────────

        @self.app.route('/api/status')
        def api_status():
            is_validator = self.node.wallet.address in config.AUTHORIZED_VALIDATORS
            is_issuer    = self.node.wallet.address in config.AUTHORIZED_ISSUERS
            return jsonify({
                'node_id':        self.node.id,
                'address':        self.node.wallet.address,
                'balance':        self.node.get_balance(),
                'chain_height':   self.node.blockchain.get_height(),
                'mempool_count':  len(self.node.blockchain.mempool),
                'peers_count':    len(self.node.peers_connected),
                'mining_mode':    self.node.mining_mode,
                'blocks_mined':   self.node.blocks_mined,
                'mining_rewards': self.node.mining_rewards,
                'dashboard_mode': self.dashboard_mode,
                'node_role':      config.NODE_ROLE,
                'is_validator':   is_validator,
                'is_issuer':      is_issuer,
                'mining_progress': self.node.mining_progress,
                'latest_hash':    (
                    self.node.blockchain.get_latest_block().hash[:16]
                    if self.node.blockchain.chain else None
                ),
                # Compatibilidad con app.js (reemplaza target_info PoW)
                'target_info': {
                    'display':    'PoA',
                    'estimated': f'~{config.BLOCK_TIME}s',
                    'adjustment': None,
                },
            })

        @self.app.route('/api/wallet')
        def api_wallet():
            return jsonify({
                'address': self.node.wallet.address,
                'balance': self.node.get_balance(),
            })

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
                    'mined_by':  None,
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
                    'txid':   tx.short_hash(),
                    'from':   tx.from_address[:16] + '...',
                    'to':     tx.to_address[:16]   + '...',
                    'amount': tx.amount,
                    'tipo':   tx.data.get('tipo', 'normal') if tx.data else 'normal',
                    'type':   'coinbase' if tx.is_coinbase() else 'normal',
                } for tx in block.transactions],
                'tx_count': len(block.transactions),
            })

        @self.app.route('/api/block/<block_hash>/verify')
        def api_block_verify(block_hash):
            block = self.node.blockchain.get_block_by_hash(block_hash)
            if not block:
                return jsonify({'error': 'Bloque no encontrado'}), 404

            chain   = self.node.blockchain.chain
            idx     = next((i for i, b in enumerate(chain) if b.hash == block_hash), None)

            # PoA: verificar firmas en lugar de PoW
            from core.wallet import Wallet
            msg        = block.header.hash_without_sigs().encode()
            valid_sigs = 0
            for addr, sig_hex in block.header.signatures.items():
                if addr not in config.AUTHORIZED_VALIDATORS:
                    continue
                pubkey_hex = config.VALIDATOR_PUBKEYS.get(addr)
                if not pubkey_hex:
                    continue
                try:
                    if Wallet.verify_from_pubkey_hex(pubkey_hex, msg, bytes.fromhex(sig_hex)):
                        valid_sigs += 1
                except Exception:
                    continue

            poa_ok    = valid_sigs >= config.QUORUM_REQUIRED
            merkle_ok = block.validate_merkle_root()
            txs_ok    = block.validate_transactions()

            if idx == 0:
                prev_ok = True
            elif idx is not None:
                prev_ok = block.header.prev_hash == chain[idx - 1].hash
            else:
                prev_ok = False

            return jsonify({
                'hash':      block_hash,
                'height':    idx,
                'all_valid': poa_ok and merkle_ok and prev_ok and txs_ok,
                'checks': {
                    'poa':    {
                        'ok':     poa_ok,
                        'label':  'Firmas PoA',
                        'detail': f'{valid_sigs}/{config.QUORUM_REQUIRED} firmas de validadores autorizados',
                    },
                    'merkle': {
                        'ok':     merkle_ok,
                        'label':  'Merkle Root',
                        'detail': 'Raíz del árbol de TXs correcta',
                    },
                    'prev':   {
                        'ok':     prev_ok,
                        'label':  'Enlace prev_hash',
                        'detail': 'Conecta con el bloque anterior',
                    },
                    'txs':    {
                        'ok':     txs_ok,
                        'label':  'Firmas de TXs',
                        'detail': f'{len(block.transactions)} transacciones verificadas',
                    },
                },
            })

        # ──────────────────────────────────────────────────────
        # Transacciones manuales (sin cambios funcionales)
        # ──────────────────────────────────────────────────────

        @self.app.route('/api/tx/preview', methods=['POST'])
        def api_tx_preview():
            try:
                data = request.get_json(silent=True)
                if not data:
                    return jsonify({'error': 'Body JSON requerido'}), 400
                to_address = data.get('to_address')
                amount     = data.get('amount')
                if not to_address or amount is None:
                    return jsonify({'error': 'to_address y amount requeridos'}), 400
                tx      = self.node.create_transaction(to_address, float(amount))
                sig_hex = tx.signature if tx.signature else 'N/A'
                return jsonify({
                    'txid':      tx.hash(),
                    'from':      tx.from_address,
                    'to':        tx.to_address,
                    'amount':    tx.amount,
                    'signature': sig_hex[:48] + '...' if len(sig_hex) > 48 else sig_hex,
                    'valid':     tx.is_valid(),
                })
            except ValueError as e:
                return jsonify({'error': str(e)}), 400
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/all_nodes')
        def api_all_nodes():
            try:
                peers = self.node.seed_client.get_peers()
                nodes = [
                    {'name': p.get('node_id', f"node_{p['port']}"),
                     'host': p['host'], 'p2p_port': p['port']}
                    for p in peers
                ]
                nodes.insert(0, {
                    'name': self.node.id + ' (este nodo)',
                    'host': self.node.host,
                    'p2p_port': self.node.port,
                })
                return jsonify(nodes)
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/addresses')
        def api_addresses():
            try:
                return jsonify(self.node.seed_client.get_addresses(
                    exclude_host=self.node.host,
                    exclude_port=self.node.port,
                ))
            except Exception:
                return jsonify([])

        @self.app.route('/api/mine/auto', methods=['POST'])
        def api_mine_auto():
            try:
                self.node.set_mining_mode(MINING_AUTO)
                return jsonify({'status': 'ok', 'mode': MINING_AUTO})
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/mine/manual', methods=['POST'])
        def api_mine_manual():
            try:
                self.node.set_mining_mode(MINING_MANUAL)
                return jsonify({'status': 'ok', 'mode': MINING_MANUAL})
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/mine/once', methods=['POST'])
        def api_mine_once():
            try:
                if self.node.loop is None:
                    return jsonify({'error': 'Nodo no iniciado aún'}), 503
                asyncio.run_coroutine_threadsafe(self.node.mine_once(), self.node.loop)
                return jsonify({'status': 'ok'})
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/send_tx', methods=['POST'])
        def send_tx():
            try:
                to_address = request.form['to_address']
                amount     = float(request.form['amount'])
                tx         = self.node.create_transaction(to_address, amount)
                asyncio.run_coroutine_threadsafe(
                    self.node.broadcast_transaction(tx), self.node.loop
                )
                return redirect('/')
            except ValueError as e:
                return f"Error: {e}", 400
            except Exception as e:
                return f"Error inesperado: {e}", 500

        @self.app.route('/api/tx/create', methods=['POST'])
        def api_tx_create():
            try:
                data = request.get_json(silent=True)
                if not data:
                    return jsonify({'error': 'Body JSON requerido'}), 400
                to_address = data.get('to_address')
                amount     = data.get('amount')
                if not to_address or amount is None:
                    return jsonify({'error': 'to_address y amount requeridos'}), 400
                tx = self.node.create_transaction(to_address, float(amount))
                asyncio.run_coroutine_threadsafe(
                    self.node.broadcast_transaction(tx), self.node.loop
                )
                return jsonify({
                    'status': 'ok',
                    'txid':   tx.hash(),
                    'from':   tx.from_address,
                    'to':     tx.to_address,
                    'amount': tx.amount,
                })
            except ValueError as e:
                return jsonify({'error': str(e)}), 400
            except Exception as e:
                return jsonify({'error': f'Error inesperado: {e}'}), 500

        # ──────────────────────────────────────────────────────
        # NUEVOS — Títulos universitarios
        # ──────────────────────────────────────────────────────

        @self.app.route('/api/title/issue', methods=['POST'])
        def api_title_issue():
            """
            Emite un título universitario.
            Solo funciona en nodos con rol 'issuer'.

            Body (multipart/form-data):
                nombre, matricula, carrera, rvoe, fecha,
                egresado_address, archivo_pdf (file, opcional)
            """
            if self.node.wallet.address not in config.AUTHORIZED_ISSUERS:
                return jsonify({
                    'error': 'Este nodo no tiene permisos de emisor de títulos'
                }), 403

            try:
                # Leer PDF si fue subido, si no usar bytes vacíos (para pruebas)
                pdf_file  = request.files.get('archivo_pdf')
                pdf_bytes = pdf_file.read() if pdf_file else b''

                tx = build_titulo_tx(
                    secretaria_wallet = self.node.wallet,
                    egresado_address  = request.form['egresado_address'],
                    nombre            = request.form['nombre'],
                    matricula         = request.form['matricula'],
                    carrera           = request.form['carrera'],
                    fecha             = request.form['fecha'],
                    rvoe              = request.form['rvoe'],
                    pdf_bytes         = pdf_bytes,
                    institucion       = request.form.get('institucion', config.NOMBRE_INSTITUCION),
                )

                valido, err = validate_titulo_tx(tx, self.node.blockchain)
                if not valido:
                    return jsonify({'error': err}), 400

                aceptada = self.node.blockchain.add_transaction_to_mempool(tx)
                if not aceptada:
                    return jsonify({'error': 'TX rechazada por el mempool'}), 400

                # Propagar a la red
                if self.node.loop:
                    asyncio.run_coroutine_threadsafe(
                        self.node.broadcast_transaction(tx), self.node.loop
                    )

                return jsonify({
                    'status':   'ok',
                    'tx_hash':  tx.hash(),
                    'hash_doc': tx.data['hash_doc'],
                    'mensaje':  'Título enviado al mempool. Se confirmará en el próximo bloque.',
                })

            except KeyError as e:
                return jsonify({'error': f'Campo requerido faltante: {e}'}), 400
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/title/lookup/<tx_hash>', methods=['GET'])
        def api_title_lookup(tx_hash):
            """
            Busca un título por el hash de su TX.
            Endpoint público — lo usa el explorador del empleador.
            """
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
            """
            Todos los títulos emitidos a una wallet.
            El egresado llama este endpoint con su propia address.
            """
            titulos = get_titulos_by_wallet(self.node.blockchain, address)
            return jsonify(titulos)

        @self.app.route('/api/title/all', methods=['GET'])
        def api_title_all():
            """
            Todos los títulos confirmados en la cadena.
            Para el panel de administración de la secretaría.
            """
            return jsonify(get_all_titulos(self.node.blockchain))

        @self.app.route('/api/title/pending', methods=['GET'])
        def api_title_pending():
            """
            Títulos en el mempool pendientes de confirmación.
            """
            return jsonify(get_titulos_pendientes(self.node.blockchain))

        @self.app.route('/api/title/verify_doc', methods=['POST'])
        def api_title_verify_doc():
            """
            Verifica que un PDF corresponde al hash registrado en la cadena.

            Body (multipart/form-data):
                tx_hash     (string)
                archivo_pdf (file)
            """
            try:
                tx_hash   = request.form.get('tx_hash', '').strip()
                pdf_file  = request.files.get('archivo_pdf')

                if not tx_hash:
                    return jsonify({'error': 'tx_hash requerido'}), 400
                if not pdf_file:
                    return jsonify({'error': 'archivo_pdf requerido'}), 400

                pdf_bytes = pdf_file.read()
                result    = verify_document(self.node.blockchain, tx_hash, pdf_bytes)
                return jsonify(result)

            except Exception as e:
                return jsonify({'error': str(e)}), 500

        # ──────────────────────────────────────────────────────
        # Compatibilidad con endpoints de tx del orquestador
        # (devuelven 404 limpio en lugar de error de import)
        # ──────────────────────────────────────────────────────

        @self.app.route('/api/tx/status', methods=['GET'])
        def api_tx_status():
            return jsonify({'available': False, 'tx_mode': 'manual'})

        @self.app.route('/api/tx/auto', methods=['POST'])
        def api_tx_auto():
            return jsonify({'error': 'Orquestador no disponible en este demo'}), 404

        @self.app.route('/api/tx/manual', methods=['POST'])
        def api_tx_manual():
            return jsonify({'error': 'Orquestador no disponible en este demo'}), 404

    def run(self):
        self.app.run(
            host='0.0.0.0',
            port=self.dashboard_port,
            debug=False,
            use_reloader=False,
        )
