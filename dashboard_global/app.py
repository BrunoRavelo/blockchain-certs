"""
GlobalDashboard — Explorador público / Dashboard del evaluador

Observer de toda la red. Obtiene info de cada nodo via HTTP.
No comparte memoria con los nodos.

Sprint 3B: actualizado para PoA y títulos universitarios.
- Eliminado: orquestador de TXs
- Eliminado: control de minado de toda la red
- Agregado:  /api/title/lookup/<tx_hash> — busca título en cualquier nodo
- Actualizado: summary sin campos de minado PoW
"""

import requests
import threading
from flask import Flask, render_template, jsonify, request
from network.seed_client import SeedClient
from utils.logger import setup_logger
from config import SEED_HOST, SEED_PORT


class GlobalDashboard:

    def __init__(
        self,
        seed_host: str = SEED_HOST,
        seed_port: int = SEED_PORT,
        port:      int = 9000,
    ):
        self.port   = port
        self.logger = setup_logger('global_dashboard')

        self.seed_client = SeedClient(
            node_id='global_dashboard',
            host='global_dashboard',
            port=0,
            seed_host=seed_host,
            seed_port=seed_port,
        )

        self.app = Flask(__name__)
        self._setup_routes()

    def _setup_routes(self):

        # ── Página principal ───────────────────────────────────

        @self.app.route('/')
        def index():
            return render_template('global.html')

        # ── Estado de la red ───────────────────────────────────

        @self.app.route('/api/network')
        def api_network():
            addresses = self.seed_client.get_addresses()

            if not addresses:
                return jsonify({
                    'nodes':       [],
                    'summary':     self._empty_summary(),
                    'seed_online': False,
                })

            results = [None] * len(addresses)
            threads = []

            def fetch_node(idx, node_info):
                results[idx] = self._fetch_node_status(node_info)

            for i, node_info in enumerate(addresses):
                t = threading.Thread(target=fetch_node, args=(i, node_info))
                threads.append(t)
                t.start()
            for t in threads:
                t.join(timeout=3)

            nodes_status = [r for r in results if r is not None]
            max_height   = max(
                (n['chain_height'] for n in nodes_status), default=1
            )

            for node in nodes_status:
                lag             = max_height - node['chain_height']
                node['lag']     = lag
                node['in_sync'] = lag <= 2

            summary = self._build_summary(nodes_status, max_height)

            return jsonify({
                'nodes':       nodes_status,
                'summary':     summary,
                'seed_online': True,
            })

        # ── Cadena de bloques ──────────────────────────────────

        @self.app.route('/api/chain')
        def api_chain():
            count     = int(request.args.get('count', 10))
            node_info = self._get_best_node()
            if not node_info:
                return jsonify({'blocks': [], 'height': 0,
                                'error': 'Sin nodos disponibles'})

            host = node_info['host']
            port = node_info.get('dashboard_port', 8000)

            try:
                r = requests.get(
                    f"http://{host}:{port}/api/chain",
                    params={'count': count}, timeout=3
                )
                if r.status_code != 200:
                    return jsonify({'blocks': [], 'height': 0,
                                    'error': 'Error al obtener cadena'})
                data         = r.json()
                data['node'] = node_info.get('node_id', '-')
                return jsonify(data)
            except Exception as e:
                return jsonify({'blocks': [], 'height': 0, 'error': str(e)})

        # ── Detalle de un bloque ───────────────────────────────

        @self.app.route('/api/block/<block_hash>')
        def api_block(block_hash):
            node_info = self._get_best_node()
            if not node_info:
                return jsonify({'error': 'Sin nodos disponibles'}), 503

            host = node_info['host']
            port = node_info.get('dashboard_port', 8000)

            try:
                r = requests.get(
                    f"http://{host}:{port}/api/block/{block_hash}",
                    timeout=3
                )
                if r.status_code == 200:
                    return jsonify(r.json())
                return jsonify({'error': 'Bloque no encontrado'}), 404
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        # ── NUEVO: Buscar título por TX hash ───────────────────

        @self.app.route('/api/title/lookup/<tx_hash>')
        def api_title_lookup(tx_hash):
            """
            Busca un título en cualquier nodo de la red.
            El empleador usa este endpoint desde el explorador público.
            """
            addresses = self.seed_client.get_addresses()
            if not addresses:
                return jsonify({'encontrado': False,
                                'error': 'Sin nodos disponibles'}), 503

            for node_info in addresses:
                host = node_info['host']
                port = node_info.get('dashboard_port', 8000)
                try:
                    r = requests.get(
                        f"http://{host}:{port}/api/title/lookup/{tx_hash}",
                        timeout=3
                    )
                    if r.status_code == 200:
                        data = r.json()
                        if data.get('encontrado'):
                            return jsonify(data)
                except Exception:
                    continue

            return jsonify({'encontrado': False,
                            'error': 'TX no encontrada en ningún nodo'}), 404



    # ──────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────

    def _fetch_node_status(self, node_info: dict) -> dict:
        host    = node_info['host']
        port    = node_info.get('dashboard_port', 8000)
        node_id = node_info.get('node_id', f"node_{node_info['port']}")
        url     = f"http://{host}:{port}/api/status"

        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                data = r.json()
                data['online']         = True
                data['dashboard_port'] = port
                data['p2p_port']       = node_info['port']
                data['wallet_address'] = node_info.get('wallet_address', '-')
                return data
        except Exception:
            pass

        return {
            'node_id':        node_id,
            'online':         False,
            'chain_height':   0,
            'peers_count':    0,
            'mempool_count':  0,
            'node_role':      '-',
            'is_issuer':      False,
            'blocks_mined':   0,
            'dashboard_port': port,
            'p2p_port':       node_info['port'],
            'wallet_address': node_info.get('wallet_address', '-'),
        }

    def _get_best_node(self) -> dict:
        addresses = self.seed_client.get_addresses()
        if not addresses:
            return None

        best        = None
        best_height = -1

        for node_info in addresses:
            host = node_info['host']
            port = node_info.get('dashboard_port', 8000)
            try:
                r = requests.get(
                    f"http://{host}:{port}/api/status", timeout=3
                )
                if r.status_code == 200:
                    height = r.json().get('chain_height', 0)
                    if height > best_height:
                        best_height = height
                        best        = node_info
            except Exception:
                continue

        return best

    def _build_summary(self, nodes: list, max_height: int) -> dict:
        online   = [n for n in nodes if n['online']]
        in_sync  = [n for n in online if n.get('in_sync', True)]

        return {
            'total_nodes':   len(nodes),
            'online_nodes':  len(online),
            'offline_nodes': len(nodes) - len(online),
            'in_sync':       len(in_sync),
            'out_of_sync':   len(online) - len(in_sync),
            'max_height':    max_height,
            'total_mempool': max(
                (n.get('mempool_count', 0) for n in online), default=0
            ),
            'issuers_active': sum(
                1 for n in online if n.get('is_issuer')
            ),
        }

    def _empty_summary(self) -> dict:
        return {
            'total_nodes': 0, 'online_nodes': 0, 'offline_nodes': 0,
            'in_sync': 0, 'out_of_sync': 0, 'max_height': 1,
            'total_mempool': 0, 'issuers_active': 0,
        }

    def run(self):
        self.logger.info(
            f"[GLOBAL] Explorador público en http://0.0.0.0:{self.port}"
        )
        self.app.run(
            host='0.0.0.0', port=self.port,
            debug=False, use_reloader=False,
        )
