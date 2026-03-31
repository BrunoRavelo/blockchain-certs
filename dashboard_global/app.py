"""
GlobalDashboard — Dashboard del instructor

Observer de toda la red. Obtiene info de cada nodo via HTTP
consultando sus dashboards individuales (/api/status).
No comparte memoria con los nodos — funciona igual en local y LAN.

Endpoints:
    GET  /                        — página principal
    GET  /api/network             — estado de toda la red
    GET  /api/chain               — cadena completa desde un nodo sincronizado
    GET  /api/block/<hash>        — detalle de un bloque
    GET  /api/orchestrator        — estado del orquestador
    POST /api/orchestrator/auto   — activar TXs automáticas
    POST /api/orchestrator/manual — pausar TXs automáticas
"""

import requests
import threading
from flask import Flask, render_template, jsonify, request
from network.seed_client import SeedClient
from utils.logger import setup_logger
from config import SEED_HOST, SEED_PORT


class GlobalDashboard:
    """
    Dashboard global del instructor.

    Consulta el seed para obtener la lista de nodos,
    luego hace GET /api/status a cada uno para obtener
    su estado en tiempo real.
    """

    def __init__(
        self,
        seed_host:    str = SEED_HOST,
        seed_port:    int = SEED_PORT,
        port:         int = 9000,
        orchestrator  = None,
    ):
        self.port         = port
        self.orchestrator = orchestrator
        self.logger       = setup_logger('global_dashboard')

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
            has_orchestrator = self.orchestrator is not None
            return render_template(
                'global.html',
                has_orchestrator=has_orchestrator,
            )

        # ── API: estado de toda la red ─────────────────────────

        @self.app.route('/api/network')
        def api_network():
            """
            Consulta el seed para obtener todos los nodos,
            luego hace GET /api/status a cada uno en paralelo.
            """
            addresses = self.seed_client.get_addresses()

            if not addresses:
                return jsonify({
                    'nodes':        [],
                    'summary':      self._empty_summary(),
                    'seed_online':  False,
                })

            nodes_status = []
            threads      = []
            results      = [None] * len(addresses)

            def fetch_node(idx, node_info):
                results[idx] = self._fetch_node_status(node_info)

            for i, node_info in enumerate(addresses):
                t = threading.Thread(
                    target=fetch_node, args=(i, node_info)
                )
                threads.append(t)
                t.start()

            for t in threads:
                t.join(timeout=3)

            nodes_status = [r for r in results if r is not None]

            max_height = max(
                (n['chain_height'] for n in nodes_status), default=1
            )

            for node in nodes_status:
                lag = max_height - node['chain_height']
                node['lag']      = lag
                node['in_sync']  = lag <= 2
                node['is_ahead'] = node['chain_height'] > max_height

            summary = self._build_summary(nodes_status, max_height)

            return jsonify({
                'nodes':       nodes_status,
                'summary':     summary,
                'seed_online': True,
            })

        # ── API: cadena de bloques ─────────────────────────────

        @self.app.route('/api/chain')
        def api_chain():
            """
            Obtiene la cadena de bloques desde el nodo más avanzado
            y sincronizado de la red.

            Query params opcionales:
                count: número de bloques a retornar (default: 10)
            """
            count = int(request.args.get('count', 10))

            # Obtener nodo más avanzado y online
            node_info = self._get_best_node()
            if not node_info:
                return jsonify({'blocks': [], 'height': 0, 'error': 'Sin nodos disponibles'})

            host           = node_info['host']
            dashboard_port = node_info.get('dashboard_port', 8000)

            try:
                # Pedir cadena al dashboard del nodo
                url      = f"http://{host}:{dashboard_port}/api/chain"
                response = requests.get(url, params={'count': count}, timeout=3)

                if response.status_code != 200:
                    return jsonify({'blocks': [], 'height': 0, 'error': 'Error al obtener cadena'})

                data         = response.json()
                data['node'] = node_info.get('node_id', '-')
                return jsonify(data)

            except Exception as e:
                return jsonify({'blocks': [], 'height': 0, 'error': str(e)})

        # ── API: detalle de un bloque ──────────────────────────

        @self.app.route('/api/block/<block_hash>')
        def api_block(block_hash):
            """
            Obtiene el detalle de un bloque específico desde
            cualquier nodo que lo tenga.
            """
            node_info = self._get_best_node()
            if not node_info:
                return jsonify({'error': 'Sin nodos disponibles'}), 503

            host           = node_info['host']
            dashboard_port = node_info.get('dashboard_port', 8000)

            try:
                url      = f"http://{host}:{dashboard_port}/api/block/{block_hash}"
                response = requests.get(url, timeout=3)

                if response.status_code == 200:
                    return jsonify(response.json())
                return jsonify({'error': 'Bloque no encontrado'}), 404

            except Exception as e:
                return jsonify({'error': str(e)}), 500

        # ── API: estado del orquestador ────────────────────────

        @self.app.route('/api/orchestrator')
        def api_orchestrator():
            if self.orchestrator is None:
                return jsonify({'available': False})
            stats = self.orchestrator.get_stats()
            stats['available'] = True
            return jsonify(stats)

        @self.app.route('/api/orchestrator/auto', methods=['POST'])
        def api_orchestrator_auto():
            if self.orchestrator is None:
                return jsonify({'error': 'Orquestador no disponible'}), 404
            from core.tx_orchestrator import ORCH_AUTO
            self.orchestrator.set_mode(ORCH_AUTO)
            return jsonify({'status': 'ok', 'mode': ORCH_AUTO})

        @self.app.route('/api/orchestrator/manual', methods=['POST'])
        def api_orchestrator_manual():
            if self.orchestrator is None:
                return jsonify({'error': 'Orquestador no disponible'}), 404
            from core.tx_orchestrator import ORCH_MANUAL
            self.orchestrator.set_mode(ORCH_MANUAL)
            return jsonify({'status': 'ok', 'mode': ORCH_MANUAL})

        # ── API: control de minado de toda la red ─────────────

        @self.app.route('/api/mining/all/auto', methods=['POST'])
        def api_mining_all_auto():
            return jsonify(self._set_all_mining('auto'))

        @self.app.route('/api/mining/all/manual', methods=['POST'])
        def api_mining_all_manual():
            return jsonify(self._set_all_mining('manual'))

    # ──────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────

    def _fetch_node_status(self, node_info: dict) -> dict:
        """
        Consulta /api/status del dashboard de un nodo.
        Retorna dict con status o datos de error si no responde.
        """
        host           = node_info['host']
        dashboard_port = node_info.get('dashboard_port', 8000)
        node_id        = node_info.get('node_id', f"node_{node_info['port']}")
        url            = f"http://{host}:{dashboard_port}/api/status"

        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                data['online']         = True
                data['dashboard_port'] = dashboard_port
                data['p2p_port']       = node_info['port']
                data['wallet_address'] = node_info.get('wallet_address', '-')
                return data
        except Exception:
            pass

        return {
            'node_id':        node_id,
            'online':         False,
            'chain_height':   0,
            'balance':        0.0,
            'peers_count':    0,
            'mempool_count':  0,
            'mining_mode':    '-',
            'blocks_mined':   0,
            'mining_rewards': 0.0,
            'dashboard_port': dashboard_port,
            'p2p_port':       node_info['port'],
            'wallet_address': node_info.get('wallet_address', '-'),
        }

    def _get_best_node(self) -> dict:
        """
        Retorna el nodo online con mayor altura de cadena.
        Usado para consultar la cadena y bloques individuales.
        """
        addresses = self.seed_client.get_addresses()
        if not addresses:
            return None

        best      = None
        best_height = -1

        for node_info in addresses:
            host           = node_info['host']
            dashboard_port = node_info.get('dashboard_port', 8000)
            try:
                r = requests.get(
                    f"http://{host}:{dashboard_port}/api/status",
                    timeout=5
                )
                if r.status_code == 200:
                    height = r.json().get('chain_height', 0)
                    if height > best_height:
                        best_height = height
                        best        = node_info
            except Exception:
                continue

        return best

    def _set_all_mining(self, mode: str) -> dict:
        """Envía POST /api/mine/<mode> a todos los nodos en paralelo."""
        addresses = self.seed_client.get_addresses()
        ok = 0
        failed = 0
        threads = []
        lock = __import__('threading').Lock()

        def call_node(node_info):
            nonlocal ok, failed
            host  = node_info['host']
            port  = node_info.get('dashboard_port', 8000)
            try:
                r = requests.post(f"http://{host}:{port}/api/mine/{mode}", timeout=3)
                with lock:
                    if r.status_code == 200:
                        ok += 1
                    else:
                        failed += 1
            except Exception:
                with lock:
                    failed += 1

        for node_info in addresses:
            t = __import__('threading').Thread(target=call_node, args=(node_info,))
            threads.append(t)
            t.start()
        for t in threads:
            t.join(timeout=4)

        return {'status': 'ok', 'mode': mode, 'nodes_ok': ok, 'nodes_failed': failed}

    def _build_summary(self, nodes: list, max_height: int) -> dict:
        online   = [n for n in nodes if n['online']]
        in_sync  = [n for n in online if n.get('in_sync', True)]
        out_sync = [n for n in online if not n.get('in_sync', True)]

        return {
            'total_nodes':   len(nodes),
            'online_nodes':  len(online),
            'offline_nodes': len(nodes) - len(online),
            'in_sync':       len(in_sync),
            'out_of_sync':   len(out_sync),
            'max_height':    max_height,
            'total_mempool': max((n.get('mempool_count', 0) for n in online), default=0),
            'total_mined':   sum(n.get('blocks_mined', 0) for n in online),
            'total_rewards': sum(n.get('mining_rewards', 0.0) for n in online),
            'mining_auto':   sum(1 for n in online if n.get('mining_mode') == 'auto'),
        }

    def _empty_summary(self) -> dict:
        return {
            'total_nodes': 0, 'online_nodes': 0, 'offline_nodes': 0,
            'in_sync': 0, 'out_of_sync': 0, 'max_height': 1,
            'total_mempool': 0, 'total_mined': 0, 'total_rewards': 0.0,
            'mining_auto': 0,
        }

    def run(self):
        self.logger.info(
            f"[GLOBAL] Dashboard global en http://0.0.0.0:{self.port}"
        )
        self.app.run(
            host='0.0.0.0',
            port=self.port,
            debug=False,
            use_reloader=False,
        )
