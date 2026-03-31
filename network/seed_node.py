"""
Seed Node — Servidor HTTP de descubrimiento de peers
Sprint 5.1: agrega endpoints de wallet addresses para el orquestador

Endpoints:
    GET  /health              — verificar estado
    POST /register            — registrar nodo (IP + puerto)
    GET  /peers               — obtener lista de peers activos
    GET  /peers/all           — todos los peers (incluye inactivos)
    POST /announce_address    — anunciar wallet address (para orquestador)
    GET  /addresses           — obtener todas las wallet addresses activas

Separación de responsabilidades:
    /register + /peers  → lógica P2P (descubrimiento de nodos)
    /announce_address + /addresses → lógica de orquestador (TXs automáticas)

Si el orquestador se elimina en el futuro, los endpoints /announce_address
y /addresses se pueden quitar sin afectar el resto del sistema.
"""

import time
import threading
from flask import Flask, jsonify, request
from utils.logger import setup_logger
from config import SEED_PORT, CLEANUP_INTERVAL


class SeedNode:
    """
    Servidor HTTP de descubrimiento de peers y wallet addresses.

    Mantiene dos registros independientes:
    - peers:     {addr: {host, port, node_id, last_seen}} — para P2P
    - addresses: {addr: {wallet_address, node_id}}        — para orquestador
    """

    PEER_TIMEOUT = 300  # 5 minutos sin ping = inactivo

    def __init__(self, host: str = '0.0.0.0', port: int = SEED_PORT):
        self.host = host
        self.port = port

        # Registro P2P
        self.peers: dict = {}

        # Registro de wallet addresses (separado e independiente)
        self.addresses: dict = {}  # {f"{host}:{port}": {wallet_address, node_id}}

        self.lock    = threading.Lock()
        self.logger  = setup_logger('seed_node')
        self.app     = Flask(__name__)
        self._setup_routes()

    # ──────────────────────────────────────────────────────────
    # Rutas HTTP
    # ──────────────────────────────────────────────────────────

    def _setup_routes(self):

        # ── Health ─────────────────────────────────────────────

        @self.app.route('/health', methods=['GET'])
        def health():
            with self.lock:
                peers_count     = len(self.peers)
                addresses_count = len(self.addresses)

            return jsonify({
                'status':          'ok',
                'peers_count':     peers_count,
                'addresses_count': addresses_count,
                'timestamp':       time.time(),
            })

        # ── Registro P2P ───────────────────────────────────────

        @self.app.route('/register', methods=['POST'])
        def register():
            """
            Nodo anuncia su presencia (IP + puerto).
            Responsabilidad: descubrimiento P2P.
            No incluye wallet_address — eso va en /announce_address.
            """
            data = request.get_json(silent=True)

            if not data:
                return jsonify({'error': 'Body JSON requerido'}), 400

            host    = data.get('host')
            port    = data.get('port')
            node_id = data.get('node_id', f'node_{port}')

            if not host or not port:
                return jsonify({'error': 'host y port son requeridos'}), 400

            try:
                port = int(port)
            except (ValueError, TypeError):
                return jsonify({'error': 'port debe ser un número'}), 400

            addr = f"{host}:{port}"

            with self.lock:
                is_new = addr not in self.peers
                self.peers[addr] = {
                    'host':       host,
                    'port':       port,
                    'node_id':    node_id,
                    'last_seen':  time.time(),
                    'first_seen': self.peers[addr]['first_seen'] if not is_new
                                  else time.time(),
                }

            if is_new:
                self.logger.info(f"[REGISTER] Nuevo nodo: {addr} ({node_id})")
            else:
                self.logger.debug(f"[PING] Actualizado: {addr}")

            return jsonify({'status': 'ok', 'addr': addr})

        # ── Peers ──────────────────────────────────────────────

        @self.app.route('/peers', methods=['GET'])
        def get_peers():
            exclude_host = request.args.get('exclude_host')
            exclude_port = request.args.get('exclude_port')

            try:
                exclude_port = int(exclude_port) if exclude_port else None
            except ValueError:
                exclude_port = None

            with self.lock:
                now          = time.time()
                active_peers = []

                for addr, info in self.peers.items():
                    if now - info['last_seen'] > self.PEER_TIMEOUT:
                        continue
                    if (exclude_host and exclude_port and
                            info['host'] == exclude_host and
                            info['port'] == exclude_port):
                        continue
                    active_peers.append({
                        'host':    info['host'],
                        'port':    info['port'],
                        'node_id': info['node_id'],
                    })

            return jsonify({'peers': active_peers, 'count': len(active_peers)})

        @self.app.route('/peers/all', methods=['GET'])
        def get_all_peers():
            with self.lock:
                all_peers = [
                    {
                        'host':       info['host'],
                        'port':       info['port'],
                        'node_id':    info['node_id'],
                        'last_seen':  info['last_seen'],
                        'first_seen': info['first_seen'],
                        'active':     (time.time() - info['last_seen']) < self.PEER_TIMEOUT,
                    }
                    for info in self.peers.values()
                ]
            return jsonify({'peers': all_peers, 'count': len(all_peers)})

        # ── Wallet addresses (para orquestador) ───────────────

        @self.app.route('/announce_address', methods=['POST'])
        def announce_address():
            """
            Nodo anuncia su wallet address al orquestador.

            Completamente independiente de /register.
            Si el orquestador se elimina, este endpoint se puede quitar
            sin afectar el descubrimiento P2P.

            Body JSON:
                {
                    "host":           "192.168.1.X",
                    "port":           5000,
                    "node_id":        "node_5000",
                    "wallet_address": "1A2B3C..."
                }
            """
            data = request.get_json(silent=True)

            if not data:
                return jsonify({'error': 'Body JSON requerido'}), 400

            host           = data.get('host')
            port           = data.get('port')
            node_id        = data.get('node_id', f'node_{port}')
            wallet_address = data.get('wallet_address')
            dashboard_port = data.get('dashboard_port', 8000)


            if not all([host, port, wallet_address]):
                return jsonify({'error': 'host, port y wallet_address son requeridos'}), 400

            try:
                port = int(port)
            except (ValueError, TypeError):
                return jsonify({'error': 'port debe ser un número'}), 400

            addr = f"{host}:{port}"
            
            with self.lock:
                self.addresses[addr] = {
                    'host':           host,
                    'port':           port,
                    'node_id':        node_id,
                    'wallet_address': wallet_address,
                    'registered_at':  time.time(),
                    'dashboard_port': int(dashboard_port),
                }

            self.logger.info(
                f"[ADDRESS] Registrada: {addr} ({node_id}) "
                f"→ {wallet_address[:16]}..."
            )

            return jsonify({'status': 'ok', 'addr': addr})

        @self.app.route('/addresses', methods=['GET'])
        def get_addresses():
            """
            Retorna todas las wallet addresses registradas.
            Usado por el orquestador para saber a quién enviar TXs.

            Query params opcionales:
                exclude_host: IP a excluir
                exclude_port: Puerto a excluir

            Respuesta:
                {
                    "addresses": [
                        {
                            "host":           "192.168.1.X",
                            "port":           5000,
                            "node_id":        "node_5000",
                            "wallet_address": "1A2B3C..."
                        },
                        ...
                    ],
                    "count": N
                }
            """
            exclude_host = request.args.get('exclude_host')
            exclude_port = request.args.get('exclude_port')

            try:
                exclude_port = int(exclude_port) if exclude_port else None
            except ValueError:
                exclude_port = None

            with self.lock:
                result = []
                for addr, info in self.addresses.items():
                    if (exclude_host and exclude_port and
                            info['host'] == exclude_host and
                            info['port'] == exclude_port):
                        continue
                    result.append({
                        'host':           info['host'],
                        'port':           info['port'],
                        'node_id':        info['node_id'],
                        'wallet_address': info['wallet_address'],
                        'dashboard_port': info.get('dashboard_port', 8000),
                    })

            return jsonify({'addresses': result, 'count': len(result)})

    # ──────────────────────────────────────────────────────────
    # Limpieza automática
    # ──────────────────────────────────────────────────────────

    def _cleanup_loop(self):
        while True:
            time.sleep(CLEANUP_INTERVAL)
            self._cleanup_inactive()

    def _cleanup_inactive(self):
        """
        Elimina peers inactivos del registro P2P.
        Las wallet addresses NO se limpian automáticamente —
        permanecen hasta que el seed se reinicia.
        """
        now       = time.time()
        to_remove = []

        with self.lock:
            for addr, info in self.peers.items():
                if now - info['last_seen'] > self.PEER_TIMEOUT:
                    to_remove.append(addr)
            for addr in to_remove:
                del self.peers[addr]
                self.logger.info(f"[CLEANUP] Peer inactivo eliminado: {addr}")

        if to_remove:
            self.logger.info(
                f"[CLEANUP] {len(to_remove)} peers eliminados. "
                f"Activos: {len(self.peers)}"
            )

    # ──────────────────────────────────────────────────────────
    # Arranque
    # ──────────────────────────────────────────────────────────

    def run(self):
        self.logger.info(
            f"[SEED] Iniciando en http://{self.host}:{self.port}"
        )
        self.logger.info("[SEED] Endpoints:")
        self.logger.info("         GET  /health")
        self.logger.info("         POST /register")
        self.logger.info("         GET  /peers")
        self.logger.info("         GET  /peers/all")
        self.logger.info("         POST /announce_address")
        self.logger.info("         GET  /addresses")

        cleanup_thread = threading.Thread(
            target=self._cleanup_loop, daemon=True
        )
        cleanup_thread.start()

        self.app.run(
            host=self.host,
            port=self.port,
            debug=False,
            use_reloader=False,
        )
