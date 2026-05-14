"""
Nodo P2P — Blockchain Certs (PoA)

Producción de bloques: MANUAL, solo issuers, via mine_once().
Validadores y egresados: solo propagan y verifican bloques entrantes.
No hay loop automático.
"""

import asyncio
import json
from typing import Dict, Set, Optional
from datetime import datetime
import websockets

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
import config
from config import (
    MAX_OUTBOUND_CONNECTIONS, MAX_INBOUND_CONNECTIONS, MAX_PEERS_TO_SHARE,
    GOSSIP_INTERVAL, PING_INTERVAL, CLEANUP_INTERVAL, CONNECT_TIMEOUT,
    SEED_HOST, SEED_PORT,
)

class P2PNode:

    def __init__(
        self,
        host:            str,
        port:            int,
        bootstrap_peers: list,
        blockchain:      Blockchain,
        seed_host:       str = SEED_HOST,
        wallet:          Optional[Wallet] = None,
        role:            str = 'full',
        dashboard_port:  int = 8000,
    ):
        self.id             = f"node_{port}"
        self.host           = host
        self.port           = port
        self.blockchain     = blockchain
        self.wallet         = wallet if wallet is not None else Wallet()
        self.node_role      = role
        self.dashboard_port = dashboard_port
        self.display_name   = self.id
        self.institucion    = ''

        self.peers_connected: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.peers_known:     Dict[str, PeerInfo] = {}

        for b_host, b_port in bootstrap_peers:
            self.peers_known[f"{b_host}:{b_port}"] = PeerInfo(b_host, b_port)

        self.messages_seen: Set[str] = set()
        self.MAX_MESSAGES_SEEN       = 1000
        self.MAX_OUTBOUND_CONNECTIONS = MAX_OUTBOUND_CONNECTIONS
        self.MAX_INBOUND_CONNECTIONS  = MAX_INBOUND_CONNECTIONS
        self.MAX_PEERS_TO_SHARE       = MAX_PEERS_TO_SHARE
        self.GOSSIP_INTERVAL  = GOSSIP_INTERVAL
        self.PING_INTERVAL    = PING_INTERVAL
        self.CLEANUP_INTERVAL = CLEANUP_INTERVAL

        self.seed_client = SeedClient(
            node_id=self.id, host=self.host, port=self.port,
            seed_host=seed_host, seed_port=SEED_PORT,
        )

        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.blocks_mined: int = 0

        self.logger = setup_logger(self.id)

    # ── Arranque ───────────────────────────────────────────

    async def start(self):
        self.loop = asyncio.get_running_loop()
        can_produce = self.wallet.address in config.AUTHORIZED_VALIDATORS
        self.logger.info(
            f"[INIT] {self.id} | rol={self.node_role} | "
            f"{'PUEDE SELLAR BLOQUES' if can_produce else 'solo propaga'}"
        )
        await self._bootstrap_from_seed()
        await websockets.serve(self.handle_incoming_connection, self.host, self.port)
        self.logger.info(f"[OK] ws://{self.host}:{self.port}")
        asyncio.create_task(self.connect_to_bootstrap())
        asyncio.create_task(self.gossip_loop())
        asyncio.create_task(self.ping_loop())
        asyncio.create_task(self.cleanup_loop())
        asyncio.create_task(self.seed_register_loop())
        await asyncio.Future()

    async def _bootstrap_from_seed(self):
        loop = asyncio.get_running_loop()
        registered = await loop.run_in_executor(None, self.seed_client.register)
        if not registered:
            self.logger.warning("[SEED] No disponible")
            return
        await loop.run_in_executor(
            None,
            lambda: self.seed_client.announce_address(self.wallet.address, self.dashboard_port)
        )
        peers = await loop.run_in_executor(None, self.seed_client.get_peers)
        for p in peers:
            addr = f"{p['host']}:{p['port']}"
            if addr not in self.peers_known:
                self.peers_known[addr] = PeerInfo(p['host'], p['port'], p.get('node_id'))
        self.logger.info(f"[SEED] {len(peers)} peers")

    async def seed_register_loop(self):
        await asyncio.sleep(30)
        while True:
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self.seed_client.register)
            except Exception:
                pass
            await asyncio.sleep(self.CLEANUP_INTERVAL)

    # ── Producción de bloques — MANUAL, solo issuers ───────

    async def mine_once(self):
        """
        Sella un bloque PoA con las TXs actuales del mempool.
        Solo funciona para issuers autorizados (config.AUTHORIZED_VALIDATORS).
        """
        if self.wallet.address not in config.AUTHORIZED_VALIDATORS:
            self.logger.warning(f"[SEAL] {self.node_role} no puede sellar bloques")
            return None

        if not self.blockchain.mempool:
            self.logger.info("[SEAL] Mempool vacío")
            return None

        try:
            loop  = asyncio.get_running_loop()
            block = await loop.run_in_executor(
                None, lambda: self.blockchain.produce_block_poa(self.wallet)
            )
            if block:
                self.blocks_mined += 1
                self.logger.info(
                    f"[SEAL] Bloque #{self.blockchain.get_height()-1} "
                    f"({len(block.transactions)} TXs)"
                )
                await self.broadcast_block(block)
            return block
        except Exception as e:
            self.logger.error(f"[SEAL] Error: {e}")
            return None
    # ── Conexiones entrantes ───────────────────────────────

    async def handle_incoming_connection(self, websocket, path="/"):
        if len(self.peers_connected) >= self.MAX_INBOUND_CONNECTIONS:
            await websocket.close()
            return
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

    async def _route_message(self, msg: dict, sender_ws):
        msg_id = msg.get('id', '')
        if msg_id in self.messages_seen:
            return
        self.messages_seen.add(msg_id)
        if len(self.messages_seen) > self.MAX_MESSAGES_SEEN:
            self.messages_seen = set(list(self.messages_seen)[-500:])

        t = msg.get('type')
        handlers = {
            MSG_VERSION:   lambda: self.handle_version(msg, sender_ws),
            MSG_PING:      lambda: self.handle_ping(msg, sender_ws),
            MSG_GETADDR:   lambda: self.handle_getaddr(sender_ws),
            MSG_ADDR:      lambda: self.handle_addr(msg),
            MSG_TX:        lambda: self.handle_tx(msg, sender_ws),
            MSG_BLOCK:     lambda: self.handle_block(msg, sender_ws),
            MSG_INV:       lambda: self.handle_inv(msg, sender_ws),
            MSG_GETBLOCKS: lambda: self.handle_getblocks(sender_ws),
        }
        handler = handlers.get(t)
        if handler:
            await handler()

    def _cleanup_peer(self, websocket):
        for addr, ws in list(self.peers_connected.items()):
            if ws == websocket:
                del self.peers_connected[addr]
                if addr in self.peers_known:
                    self.peers_known[addr].mark_disconnected()
                break

    # ── Conexiones salientes ───────────────────────────────

    async def connect_to_bootstrap(self):
        await asyncio.sleep(2)
        for addr, peer in list(self.peers_known.items()):
            if addr not in self.peers_connected:
                await self._connect_to_peer(peer.host, peer.port)

    async def _connect_to_peer(self, host: str, port: int):
        addr = f"{host}:{port}"
        if addr == f"{self.host}:{self.port}": return
        if addr in self.peers_connected: return
        if len(self.peers_connected) >= self.MAX_OUTBOUND_CONNECTIONS: return
        try:
            ws = await asyncio.wait_for(
                websockets.connect(f"ws://{host}:{port}"), timeout=CONNECT_TIMEOUT
            )
            self.peers_connected[addr] = ws
            if addr in self.peers_known:
                self.peers_known[addr].mark_connected()
            await self._send_version(ws)
            asyncio.create_task(self._listen_to_peer(ws, addr))
            self.logger.info(f"[CONN] → {addr}")
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

    # ── Handshake ──────────────────────────────────────────

    async def _send_version(self, websocket):
        await websocket.send(json.dumps(create_message(MSG_VERSION, {
            'node_id': self.id, 'host': self.host,
            'port': self.port, 'height': self.blockchain.get_height(),
        })))

    async def handle_version(self, msg: dict, sender_ws):
        try:
            p = msg['payload']
            peer_host = p.get('host', sender_ws.remote_address[0])
            peer_port = p.get('port')
            if peer_port:
                addr = f"{peer_host}:{peer_port}"
                if addr not in self.peers_connected:
                    self.peers_connected[addr] = sender_ws
                if addr not in self.peers_known:
                    self.peers_known[addr] = PeerInfo(peer_host, peer_port, p.get('node_id'))
                self.peers_known[addr].mark_connected()
            await sender_ws.send(json.dumps(create_message(MSG_VERACK, {'node_id': self.id})))
            if p.get('height', 0) > self.blockchain.get_height():
                await self._request_chain_sync(sender_ws)
        except Exception as e:
            self.logger.error(f"[VERSION] {e}")

    async def handle_ping(self, msg: dict, sender_ws):
        await sender_ws.send(json.dumps(
            create_message(MSG_PONG, {'nonce': msg['payload'].get('nonce')})
        ))

    # ── Gossip ─────────────────────────────────────────────

    async def handle_getaddr(self, sender_ws):
        peers_list = [
            info.to_dict()
            for _, info in list(self.peers_known.items())[:self.MAX_PEERS_TO_SHARE]
        ]
        await sender_ws.send(json.dumps(create_message(MSG_ADDR, {'peers': peers_list})))

    async def handle_addr(self, msg: dict):
        for p in msg['payload'].get('peers', []):
            addr = f"{p['host']}:{p['port']}"
            if addr not in self.peers_known and addr != f"{self.host}:{self.port}":
                self.peers_known[addr] = PeerInfo.from_dict(p)
                asyncio.create_task(self._connect_to_peer(p['host'], p['port']))

    async def request_peers(self, websocket):
        await websocket.send(json.dumps(create_message(MSG_GETADDR, {})))

    # ── Bloques ────────────────────────────────────────────

    async def handle_block(self, msg: dict, sender_ws):
        try:
            payload = msg['payload']
            if payload.get('type') == 'full_chain':
                new_chain = Blockchain.chain_from_dicts(payload.get('chain', []))
                if self.blockchain.replace_chain(new_chain):
                    self.logger.info(f"[SYNC] → #{self.blockchain.get_height()}")
                return

            block   = Block.from_dict(payload)
            is_next = block.header.prev_hash == self.blockchain.get_latest_block().hash

            if is_next:
                if self.blockchain.add_block(block):
                    self.logger.info(f"[BLOCK] ✓ #{self.blockchain.get_height()-1}")
                    await self.broadcast_block(block, exclude_ws=sender_ws)
            else:
                await self._request_chain_sync(sender_ws)
        except Exception as e:
            self.logger.error(f"[BLOCK] {e}")

    async def handle_inv(self, msg: dict, sender_ws):
        try:
            if msg['payload'].get('height', 0) > self.blockchain.get_height():
                await self._request_chain_sync(sender_ws)
        except Exception:
            pass

    async def handle_getblocks(self, sender_ws):
        try:
            await sender_ws.send(json.dumps(create_message(MSG_BLOCK, {
                'chain': self.blockchain.get_chain_as_dicts(),
                'height': self.blockchain.get_height(),
                'type': 'full_chain',
            })))
        except Exception as e:
            self.logger.error(f"[GETBLOCKS] {e}")

    async def _request_chain_sync(self, websocket):
        try:
            await websocket.send(json.dumps(
                create_message(MSG_GETBLOCKS, {'height': self.blockchain.get_height()})
            ))
        except Exception:
            pass

    async def broadcast_block(self, block: Block, exclude_ws=None):
        await self.broadcast_message(
            create_message(MSG_INV, {'hash': block.hash, 'height': self.blockchain.get_height()}),
            exclude_ws=exclude_ws
        )
        await self.broadcast_message(create_message(MSG_BLOCK, block.to_dict()), exclude_ws=exclude_ws)

    # ── Transacciones ──────────────────────────────────────

    async def handle_tx(self, msg: dict, sender_ws):
        try:
            tx = Transaction.from_dict(msg['payload'])
            if self.blockchain.add_transaction_to_mempool(tx):
                await self.broadcast_transaction(tx, exclude_ws=sender_ws)
        except Exception as e:
            self.logger.error(f"[TX] {e}")

    async def broadcast_transaction(self, tx: Transaction, exclude_ws=None):
        await self.broadcast_message(create_message(MSG_TX, tx.to_dict()), exclude_ws=exclude_ws)

    def create_transaction(self, to_address: str, amount: float) -> Transaction:
        tx = Transaction(from_address=self.wallet.address, to_address=to_address, amount=amount)
        tx.sign(self.wallet)
        self.blockchain.add_transaction_to_mempool(tx)
        return tx

    # ── Broadcast genérico ─────────────────────────────────

    async def broadcast_message(self, msg: dict, exclude_ws=None):
        for _, ws in list(self.peers_connected.items()):
            if ws == exclude_ws:
                continue
            try:
                await ws.send(json.dumps(msg))
            except Exception:
                pass

    # ── Loops periódicos ───────────────────────────────────

    async def gossip_loop(self):
        await asyncio.sleep(10)
        while True:
            for _, ws in list(self.peers_connected.items()):
                try:
                    await self.request_peers(ws)
                except Exception:
                    pass
            await asyncio.sleep(self.GOSSIP_INTERVAL)

    async def ping_loop(self):
        await asyncio.sleep(15)
        while True:
            for _, ws in list(self.peers_connected.items()):
                try:
                    await ws.send(json.dumps(
                        create_message(MSG_PING, {'nonce': int(datetime.now().timestamp())})
                    ))
                except Exception:
                    pass
            await asyncio.sleep(self.PING_INTERVAL)

    async def cleanup_loop(self):
        while True:
            await asyncio.sleep(self.CLEANUP_INTERVAL)
            self.messages_seen = set(list(self.messages_seen)[-500:])
            now   = datetime.now().timestamp()
            stale = [
                addr for addr, peer in self.peers_known.items()
                if not peer.is_connected and (now - peer.last_seen) > 86400
            ]
            for addr in stale:
                del self.peers_known[addr]

    def __repr__(self):
        return f"P2PNode(id={self.id}, role={self.node_role}, peers={len(self.peers_connected)})"
