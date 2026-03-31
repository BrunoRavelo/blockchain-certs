"""
Nodo P2P con consenso Proof of Authority.

Sprint 1B: mining_loop → validator_loop

Eliminado:
- start_mining_loop() (puzzle PoW)
- mine_once() (PoW manual)
- _cancel_current_mining()
- set_mining_mode() para AUTO/MANUAL/PAUSED → VALIDATOR_AUTO / NODE_PAUSED
- _stop_mining_event (threading.Event para cancelar PoW)
- mining_progress con hashrate

Conservado sin cambios:
- Todo el stack P2P: handshake, gossip, ping, cleanup
- handle_block(), handle_tx(), handle_inv(), handle_getblocks()
- broadcast_block(), broadcast_transaction()
- create_transaction()
- seed_client

Cambios:
- Modos: VALIDATOR_AUTO, NODE_PAUSED
- start_validator_loop(): produce bloques PoA cada BLOCK_TIME segundos
- set_node_mode(): reemplaza set_mining_mode()
- mining_progress: mantiene la estructura por compatibilidad con app.py,
  pero solo muestra si el validador está activo
"""

import asyncio
import threading
import websockets
import json
from typing import Dict, Set, Optional
from datetime import datetime

from utils.logger import setup_logger
from network.protocol import (
    create_message, validate_message,
    MSG_VERSION, MSG_VERACK, MSG_PING, MSG_PONG,
    MSG_GETADDR, MSG_ADDR, MSG_TX,
    MSG_INV, MSG_GETBLOCKS, MSG_BLOCK,
)
from network.peer_info import PeerInfo
from network.seed_client import SeedClient
from core.transaction import Transaction
from core.block import Block
from core.blockchain import Blockchain
from core.wallet import Wallet
from config import (
    MAX_OUTBOUND_CONNECTIONS, MAX_INBOUND_CONNECTIONS, MAX_PEERS_TO_SHARE,
    GOSSIP_INTERVAL, PING_INTERVAL, CLEANUP_INTERVAL, CONNECT_TIMEOUT,
    SEED_HOST, SEED_PORT, BLOCK_TIME, AUTHORIZED_VALIDATORS, NODE_ROLE,
)

# Modos del nodo
VALIDATOR_AUTO = 'validator_auto'   # Produce bloques PoA automáticamente
NODE_PAUSED    = 'paused'           # Solo escucha, no produce bloques

# Alias para compatibilidad con app.py (lee mining_mode)
MINING_AUTO   = VALIDATOR_AUTO
MINING_MANUAL = NODE_PAUSED


class P2PNode:
    """
    Nodo P2P con consenso PoA.

    Los nodos validadores producen bloques firmados cada BLOCK_TIME segundos.
    Los nodos no-validadores solo propagan bloques y transacciones.
    """

    def __init__(
        self,
        host:            str,
        port:            int,
        bootstrap_peers: list,
        blockchain:      Blockchain,
        seed_host:       str = SEED_HOST,
    ):
        self.id   = f"node_{port}"
        self.host = host
        self.port = port

        self.blockchain = blockchain
        self.wallet     = Wallet()

        self.peers_connected: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.peers_known:     Dict[str, PeerInfo] = {}

        for b_host, b_port in bootstrap_peers:
            addr = f"{b_host}:{b_port}"
            self.peers_known[addr] = PeerInfo(b_host, b_port)

        self.messages_seen:    Set[str] = set()
        self.MAX_MESSAGES_SEEN = 1000

        self.MAX_OUTBOUND_CONNECTIONS = MAX_OUTBOUND_CONNECTIONS
        self.MAX_INBOUND_CONNECTIONS  = MAX_INBOUND_CONNECTIONS
        self.MAX_PEERS_TO_SHARE       = MAX_PEERS_TO_SHARE

        self.GOSSIP_INTERVAL  = GOSSIP_INTERVAL
        self.PING_INTERVAL    = PING_INTERVAL
        self.CLEANUP_INTERVAL = CLEANUP_INTERVAL

        self.seed_client = SeedClient(
            node_id=self.id,
            host=self.host,
            port=self.port,
            seed_host=seed_host,
            seed_port=SEED_PORT,
        )

        self.loop: Optional[asyncio.AbstractEventLoop] = None

        # ── Modo del nodo ──────────────────────────────────────
        # Un nodo es validador si su wallet está en AUTHORIZED_VALIDATORS.
        # Esto se evalúa DESPUÉS de que el launcher configura config en runtime.
        # Por eso arrancamos en paused y el validator_loop arranca en start().
        self.mining_mode: str = NODE_PAUSED

        # Stats (compatibilidad con app.py)
        self.blocks_mined:   int   = 0
        self.mining_rewards: float = 0.0

        # Estado del validador (reemplaza mining_progress de PoW)
        self.mining_progress: dict = {
            'active':   False,
            'attempts': 0,
            'hashrate': 0.0,
        }

        self.node_role = NODE_ROLE
        self.logger = setup_logger(self.id)
        self.dashboard_port = 8000

    # ──────────────────────────────────────────────────────────
    # Arranque
    # ──────────────────────────────────────────────────────────

    async def start(self):
        self.loop = asyncio.get_running_loop()

        is_validator = self.wallet.address in AUTHORIZED_VALIDATORS
        self.logger.info(f"[INIT] {self.id} en {self.host}:{self.port}")
        self.logger.info(f"[WALLET] {self.wallet.address}")
        self.logger.info(f"[ROL] {'VALIDADOR' if is_validator else 'NODO COMPLETO'}")

        await self._bootstrap_from_seed()

        server = await websockets.serve(
            self.handle_incoming_connection,
            self.host,
            self.port,
        )
        self.logger.info(f"[OK] Servidor en ws://{self.host}:{self.port}")

        asyncio.create_task(self.connect_to_bootstrap())
        asyncio.create_task(self.gossip_loop())
        asyncio.create_task(self.ping_loop())
        asyncio.create_task(self.cleanup_loop())
        asyncio.create_task(self.seed_register_loop())

        # Solo los validadores autorizados producen bloques
        if is_validator:
            self.mining_mode = VALIDATOR_AUTO
            asyncio.create_task(self.start_validator_loop())
            self.logger.info(f"[POA] Validator loop iniciado (cada {BLOCK_TIME}s)")

        await asyncio.Future()

    async def _bootstrap_from_seed(self):
        loop = asyncio.get_running_loop()

        registered = await loop.run_in_executor(None, self.seed_client.register)
        if not registered:
            self.logger.warning("[SEED] No disponible — usando solo bootstrap peers")
            return

        await loop.run_in_executor(
            None,
            lambda: self.seed_client.announce_address(self.wallet.address, self.dashboard_port)
        )

        peers_from_seed = await loop.run_in_executor(None, self.seed_client.get_peers)
        for peer_data in peers_from_seed:
            addr = f"{peer_data['host']}:{peer_data['port']}"
            if addr not in self.peers_known:
                self.peers_known[addr] = PeerInfo(
                    peer_data['host'],
                    peer_data['port'],
                    peer_data.get('node_id'),
                )
                self.logger.info(f"[SEED] Peer: {addr}")

        self.logger.info(f"[SEED] {len(peers_from_seed)} peers. Total: {len(self.peers_known)}")

    async def seed_register_loop(self):
        await asyncio.sleep(30)
        while True:
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self.seed_client.register)
            except Exception as e:
                self.logger.warning(f"[SEED] Re-registro: {e}")
            await asyncio.sleep(self.CLEANUP_INTERVAL)

    # ──────────────────────────────────────────────────────────
    # Validator loop (reemplaza mining_loop)
    # ──────────────────────────────────────────────────────────

    async def start_validator_loop(self):
        """
        Produce bloques PoA automáticamente cada BLOCK_TIME segundos.

        A diferencia del mining_loop de PoW, esto es casi instantáneo —
        firmar un hash con Ed25519 toma microsegundos.
        El delay es artificial para que el demo sea legible.
        """
        self.logger.info(f"[VALIDATOR] Loop iniciado")
        self.mining_mode = VALIDATOR_AUTO

        while self.mining_mode == VALIDATOR_AUTO:
            await asyncio.sleep(BLOCK_TIME)

            if not self.blockchain.mempool:
                self.logger.debug("[VALIDATOR] Mempool vacío, esperando...")
                continue

            self.mining_progress = {'active': True, 'attempts': 0, 'hashrate': 0.0}

            try:
                loop  = asyncio.get_running_loop()
                # Ejecutar en executor para no bloquear el event loop
                # (aunque en PoA es casi instantáneo, mantenemos el patrón)
                block = await loop.run_in_executor(
                    None,
                    lambda: self.blockchain.produce_block_poa(self.wallet)
                )

                if block:
                    self.blocks_mined   += 1
                    self.mining_rewards += 0  # sin recompensa en PoA
                    self.logger.info(
                        f"[VALIDATOR] Bloque #{self.blockchain.get_height() - 1} "
                        f"→ {len(self.peers_connected)} peers"
                    )
                    await self.broadcast_block(block)

            except Exception as e:
                self.logger.error(f"[VALIDATOR] Error produciendo bloque: {e}")
            finally:
                self.mining_progress = {'active': False, 'attempts': 0, 'hashrate': 0.0}

    def set_node_mode(self, mode: str):
        """
        Cambia el modo del nodo.
        Llamado desde app.py (endpoints /api/mine/auto y /api/mine/manual).
        """
        self.mining_mode = mode
        self.logger.info(f"[MODE] Modo cambiado a: {mode}")

    # Alias para compatibilidad con app.py que llama set_mining_mode()
    def set_mining_mode(self, mode: str):
        self.set_node_mode(mode)

    async def mine_once(self):
        """
        Produce un bloque PoA manualmente (endpoint /api/mine/once).
        En PoA esto es simplemente produce_block_poa().
        """
        if self.wallet.address not in AUTHORIZED_VALIDATORS:
            self.logger.warning("[MINE_ONCE] Este nodo no es validador autorizado")
            return

        block = self.blockchain.produce_block_poa(self.wallet)
        if block:
            self.blocks_mined += 1
            await self.broadcast_block(block)
            self.logger.info(f"[MINE_ONCE] Bloque #{self.blockchain.get_height() - 1} producido")

    # ──────────────────────────────────────────────────────────
    # Conexiones entrantes
    # ──────────────────────────────────────────────────────────

    async def handle_incoming_connection(self, websocket, path="/"):
        peer_addr = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        self.logger.info(f"[CONN] Conexión entrante: {peer_addr}")

        if len(self.peers_connected) >= self.MAX_INBOUND_CONNECTIONS:
            self.logger.warning(f"[CONN] Rechazada: máximo de conexiones entrantes")
            await websocket.close()
            return

        try:
            async for raw in websocket:
                try:
                    msg = json.loads(raw)
                    if not validate_message(msg):
                        continue
                    await self._route_message(msg, websocket)
                except json.JSONDecodeError:
                    self.logger.warning(f"[CONN] JSON inválido de {peer_addr}")
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._cleanup_peer(websocket)

    async def _route_message(self, msg: dict, sender_ws):
        msg_type = msg.get('type')
        msg_id   = msg.get('id', '')

        if msg_id in self.messages_seen:
            return
        self.messages_seen.add(msg_id)
        if len(self.messages_seen) > self.MAX_MESSAGES_SEEN:
            self.messages_seen = set(list(self.messages_seen)[-500:])

        if msg_type == MSG_VERSION:
            await self.handle_version(msg, sender_ws)
        elif msg_type == MSG_VERACK:
            await self.handle_verack(msg, sender_ws)
        elif msg_type == MSG_PING:
            await self.handle_ping(msg, sender_ws)
        elif msg_type == MSG_PONG:
            pass
        elif msg_type == MSG_GETADDR:
            await self.handle_getaddr(sender_ws)
        elif msg_type == MSG_ADDR:
            await self.handle_addr(msg)
        elif msg_type == MSG_TX:
            await self.handle_tx(msg, sender_ws)
        elif msg_type == MSG_BLOCK:
            await self.handle_block(msg, sender_ws)
        elif msg_type == MSG_INV:
            await self.handle_inv(msg, sender_ws)
        elif msg_type == MSG_GETBLOCKS:
            await self.handle_getblocks(sender_ws)

    def _cleanup_peer(self, websocket):
        for addr, ws in list(self.peers_connected.items()):
            if ws == websocket:
                del self.peers_connected[addr]
                if addr in self.peers_known:
                    self.peers_known[addr].mark_disconnected()
                self.logger.info(f"[CONN] Desconectado: {addr}")
                break

    # ──────────────────────────────────────────────────────────
    # Conexiones salientes
    # ──────────────────────────────────────────────────────────

    async def connect_to_bootstrap(self):
        await asyncio.sleep(2)
        for addr, peer in list(self.peers_known.items()):
            if addr not in self.peers_connected:
                await self._connect_to_peer(peer.host, peer.port)

    async def _connect_to_peer(self, host: str, port: int):
        addr = f"{host}:{port}"
        if addr == f"{self.host}:{self.port}":
            return
        if addr in self.peers_connected:
            return
        if len(self.peers_connected) >= self.MAX_OUTBOUND_CONNECTIONS:
            return

        try:
            ws = await asyncio.wait_for(
                websockets.connect(f"ws://{host}:{port}"),
                timeout=CONNECT_TIMEOUT
            )
            self.peers_connected[addr] = ws
            if addr in self.peers_known:
                self.peers_known[addr].mark_connected()
            self.logger.info(f"[CONN] Conectado a {addr}")

            await self._send_version(ws)
            asyncio.create_task(self._listen_to_peer(ws, addr))

        except Exception as e:
            self.logger.debug(f"[CONN] Falló {addr}: {e}")
            if addr in self.peers_known:
                self.peers_known[addr].mark_failure()

    async def _listen_to_peer(self, websocket, addr: str):
        try:
            async for raw in websocket:
                try:
                    msg = json.loads(raw)
                    if validate_message(msg):
                        await self._route_message(msg, websocket)
                except json.JSONDecodeError:
                    pass
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._cleanup_peer(websocket)

    # ──────────────────────────────────────────────────────────
    # Handshake
    # ──────────────────────────────────────────────────────────

    async def _send_version(self, websocket):
        msg = create_message(MSG_VERSION, {
            'node_id':    self.id,
            'host':       self.host,
            'port':       self.port,
            'height':     self.blockchain.get_height(),
            'user_agent': 'blockchain-certs/1.0',
        })
        await websocket.send(json.dumps(msg))

    async def handle_version(self, msg: dict, sender_ws):
        try:
            payload  = msg['payload']
            peer_host = payload.get('host', sender_ws.remote_address[0])
            peer_port = payload.get('port')

            if peer_port:
                addr = f"{peer_host}:{peer_port}"
                if addr not in self.peers_connected:
                    self.peers_connected[addr] = sender_ws
                if addr not in self.peers_known:
                    self.peers_known[addr] = PeerInfo(peer_host, peer_port, payload.get('node_id'))
                self.peers_known[addr].mark_connected()

            verack = create_message(MSG_VERACK, {'node_id': self.id})
            await sender_ws.send(json.dumps(verack))

            # Solicitar sincronización si el peer tiene más bloques
            if payload.get('height', 0) > self.blockchain.get_height():
                await self._request_chain_sync(sender_ws)

        except Exception as e:
            self.logger.error(f"[VERSION] Error: {e}")

    async def handle_verack(self, msg: dict, sender_ws):
        pass

    # ──────────────────────────────────────────────────────────
    # Ping / Pong
    # ──────────────────────────────────────────────────────────

    async def handle_ping(self, msg: dict, sender_ws):
        pong = create_message(MSG_PONG, {'nonce': msg['payload'].get('nonce')})
        await sender_ws.send(json.dumps(pong))

    # ──────────────────────────────────────────────────────────
    # Gossip de peers
    # ──────────────────────────────────────────────────────────

    async def handle_getaddr(self, sender_ws):
        peers_list = [
            info.to_dict()
            for addr, info in list(self.peers_known.items())[:self.MAX_PEERS_TO_SHARE]
        ]
        msg = create_message(MSG_ADDR, {'peers': peers_list})
        await sender_ws.send(json.dumps(msg))

    async def handle_addr(self, msg: dict):
        for peer_data in msg['payload'].get('peers', []):
            addr = f"{peer_data['host']}:{peer_data['port']}"
            if addr not in self.peers_known and addr != f"{self.host}:{self.port}":
                self.peers_known[addr] = PeerInfo.from_dict(peer_data)
                asyncio.create_task(
                    self._connect_to_peer(peer_data['host'], peer_data['port'])
                )

    async def request_peers(self, websocket):
        getaddr = create_message(MSG_GETADDR, {})
        await websocket.send(json.dumps(getaddr))

    # ──────────────────────────────────────────────────────────
    # Handlers — bloques
    # ──────────────────────────────────────────────────────────

    async def handle_block(self, msg: dict, sender_ws):
        try:
            payload = msg['payload']

            # Cadena completa (sincronización)
            if payload.get('type') == 'full_chain':
                self._process_full_chain(payload.get('chain', []))
                return

            # Bloque individual
            block    = Block.from_dict(payload)
            prev     = self.blockchain.get_latest_block()
            is_next  = block.header.prev_hash == prev.hash

            if is_next:
                if self.blockchain.add_block(block):
                    self.logger.info(
                        f"[BLOCK] Aceptado #{self.blockchain.get_height() - 1}: "
                        f"{block.hash[:16]}..."
                    )
                    await self.broadcast_block(block, exclude_ws=sender_ws)
            else:
                self.logger.info("[BLOCK] No conecta — solicitando sincronización")
                await self._request_chain_sync(sender_ws)

        except Exception as e:
            self.logger.error(f"[BLOCK] Error: {e}")

    async def handle_inv(self, msg: dict, sender_ws):
        try:
            inv_hash   = msg['payload'].get('hash')
            inv_height = msg['payload'].get('height', 0)

            if not inv_hash:
                return
            if self.blockchain.get_block_by_hash(inv_hash):
                return

            if inv_height > self.blockchain.get_height():
                await self._request_chain_sync(sender_ws)

        except Exception as e:
            self.logger.error(f"[INV] Error: {e}")

    async def handle_getblocks(self, sender_ws):
        try:
            chain_data = self.blockchain.get_chain_as_dicts()
            msg = create_message(MSG_BLOCK, {
                'chain':  chain_data,
                'height': self.blockchain.get_height(),
                'type':   'full_chain',
            })
            await sender_ws.send(json.dumps(msg))
        except Exception as e:
            self.logger.error(f"[GETBLOCKS] Error: {e}")

    async def _request_chain_sync(self, websocket):
        try:
            msg = create_message(MSG_GETBLOCKS, {'height': self.blockchain.get_height()})
            await websocket.send(json.dumps(msg))
        except Exception as e:
            self.logger.error(f"[SYNC] Error: {e}")

    def _process_full_chain(self, chain_data: list) -> bool:
        try:
            new_chain = Blockchain.chain_from_dicts(chain_data)
            replaced  = self.blockchain.replace_chain(new_chain)
            if replaced:
                self.logger.info(f"[SYNC] Cadena reemplazada. Altura: {self.blockchain.get_height()}")
            return replaced
        except Exception as e:
            self.logger.error(f"[SYNC] Error: {e}")
            return False

    # ──────────────────────────────────────────────────────────
    # Broadcast
    # ──────────────────────────────────────────────────────────

    async def broadcast_block(self, block: Block, exclude_ws=None):
        inv_msg = create_message(MSG_INV, {
            'hash':   block.hash,
            'height': self.blockchain.get_height(),
        })
        await self.broadcast_message(inv_msg, exclude_ws=exclude_ws)

        block_msg = create_message(MSG_BLOCK, block.to_dict())
        await self.broadcast_message(block_msg, exclude_ws=exclude_ws)

        self.logger.info(
            f"[BROADCAST] Bloque {block.hash[:16]}... → {len(self.peers_connected)} peers"
        )

    # ──────────────────────────────────────────────────────────
    # Handlers — transacciones
    # ──────────────────────────────────────────────────────────

    async def handle_tx(self, msg: dict, sender_ws):
        try:
            tx       = Transaction.from_dict(msg['payload'])
            accepted = self.blockchain.add_transaction_to_mempool(tx)
            if accepted:
                self.logger.info(f"[TX] Aceptada: {tx.short_hash()}")
                await self.broadcast_transaction(tx, exclude_ws=sender_ws)
        except Exception as e:
            self.logger.error(f"[TX] Error: {e}")

    async def broadcast_transaction(self, tx: Transaction, exclude_ws=None):
        msg = create_message(MSG_TX, tx.to_dict())
        await self.broadcast_message(msg, exclude_ws=exclude_ws)

    def create_transaction(self, to_address: str, amount: float) -> Transaction:
        if not self.blockchain.has_sufficient_balance(self.wallet.address, amount):
            raise ValueError(
                f"Balance insuficiente: "
                f"tienes {self.get_balance():.2f}, intentas enviar {amount}"
            )
        tx = Transaction(
            from_address=self.wallet.address,
            to_address=to_address,
            amount=amount,
        )
        tx.sign(self.wallet)
        self.blockchain.add_transaction_to_mempool(tx)
        return tx

    def get_balance(self) -> float:
        return self.blockchain.get_balance(self.wallet.address)

    # ──────────────────────────────────────────────────────────
    # Broadcast genérico
    # ──────────────────────────────────────────────────────────

    async def broadcast_message(self, msg: dict, exclude_ws=None):
        for addr, ws in list(self.peers_connected.items()):
            if ws == exclude_ws:
                continue
            try:
                await ws.send(json.dumps(msg))
            except Exception as e:
                self.logger.error(f"[BROADCAST] Error a {addr}: {e}")

    # ──────────────────────────────────────────────────────────
    # Loops periódicos (sin cambios)
    # ──────────────────────────────────────────────────────────

    async def gossip_loop(self):
        await asyncio.sleep(10)
        while True:
            try:
                for addr, ws in list(self.peers_connected.items()):
                    try:
                        await self.request_peers(ws)
                    except Exception:
                        pass
                self.logger.info(
                    f"[GOSSIP] Conocidos: {len(self.peers_known)}, "
                    f"Conectados: {len(self.peers_connected)}"
                )
            except Exception as e:
                self.logger.error(f"[GOSSIP] Error: {e}")
            await asyncio.sleep(self.GOSSIP_INTERVAL)

    async def ping_loop(self):
        await asyncio.sleep(15)
        while True:
            try:
                for addr, ws in list(self.peers_connected.items()):
                    try:
                        ping = create_message(MSG_PING, {
                            'nonce': int(datetime.now().timestamp())
                        })
                        await ws.send(json.dumps(ping))
                    except Exception:
                        pass
            except Exception as e:
                self.logger.error(f"[PING] Error: {e}")
            await asyncio.sleep(self.PING_INTERVAL)

    async def cleanup_loop(self):
        while True:
            await asyncio.sleep(self.CLEANUP_INTERVAL)
            try:
                self.messages_seen = set(list(self.messages_seen)[-500:])
                now = datetime.now().timestamp()
                to_remove = [
                    addr for addr, peer in self.peers_known.items()
                    if not peer.is_connected and (now - peer.last_seen) > 86400
                ]
                for addr in to_remove:
                    del self.peers_known[addr]
            except Exception as e:
                self.logger.error(f"[CLEANUP] Error: {e}")

    def __repr__(self):
        return (
            f"P2PNode(id={self.id}, "
            f"peers={len(self.peers_connected)}, "
            f"height={self.blockchain.get_height()}, "
            f"mode={self.mining_mode})"
        )
