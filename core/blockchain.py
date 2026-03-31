"""
Blockchain — Demo Títulos Universitarios

Sprint 1B: migración completa de PoW a PoA.

Eliminado:
- import ProofOfWork (pow.py borrado)
- mine_block() / mine_block_cancellable()
- _maybe_adjust_target() / _recompute_target_from_chain()
- get_target_hex() / get_estimated_block_time()
- CURRENT_TARGET / MAX_TARGET / INITIAL_TARGET
- Validación de coinbase como primera TX

Agregado:
- produce_block_poa(validator_wallet) → Block | None
- _is_valid_block_poa(block, prev_block) → bool
- Validación de TXs de título: solo AUTHORIZED_ISSUERS pueden emitirlas

Conservado sin cambios:
- Estructura de cadena (chain, mempool, get_balance, etc.)
- replace_chain() / validate_chain() (adaptados a PoA)
- add_transaction_to_mempool()
- Serialización (get_chain_as_dicts, chain_from_dicts)
"""

import time
import threading
from typing import List, Optional

from core.block import Block, BlockHeader
from core.transaction import Transaction
from core.merkle import MerkleTree
from core.wallet import Wallet
from config import (
    BLOCK_REWARD,
    MAX_MEMPOOL_SIZE,
    MAX_TXS_PER_BLOCK,
    AUTHORIZED_VALIDATORS,
    VALIDATOR_PUBKEYS,
    QUORUM_REQUIRED,
    AUTHORIZED_ISSUERS,
    TITULO_MODE,
)


class Blockchain:
    """
    Cadena de bloques con consenso Proof of Authority.

    Los bloques son producidos por validadores autorizados que firman
    el hash del bloque con su llave privada Ed25519. No hay puzzle
    computacional — la autoridad reemplaza al trabajo.
    """

    def __init__(self):
        self.chain:   List[Block]       = []
        self.mempool: List[Transaction] = []
        self._lock = threading.Lock()

        self.MAX_MEMPOOL_SIZE  = MAX_MEMPOOL_SIZE
        self.MAX_TXS_PER_BLOCK = MAX_TXS_PER_BLOCK

        # Para compatibilidad con app.py (dashboard lee este campo)
        self._last_adjustment = None

        self._create_genesis_block()

    # ──────────────────────────────────────────────────────────
    # Genesis
    # ──────────────────────────────────────────────────────────

    def _create_genesis_block(self):
        """
        Bloque génesis. No requiere firma de validador —
        es el punto de partida acordado por todos los nodos.
        """
        genesis_tx           = Transaction("COINBASE", "genesis_address", 0)
        genesis_tx.timestamp = 0

        merkle = MerkleTree([genesis_tx])
        header = BlockHeader(
            prev_hash   = '0' * 64,
            merkle_root = merkle.get_root(),
            timestamp   = 0.0,
            signatures  = {},      # génesis no tiene firma de validador
        )
        genesis = Block(header, [genesis_tx])
        self.chain.append(genesis)
        print(f"[GENESIS] Bloque génesis: {genesis.hash[:16]}...")

    # ──────────────────────────────────────────────────────────
    # Consultas (sin cambios respecto al original)
    # ──────────────────────────────────────────────────────────

    def get_latest_block(self) -> Block:
        return self.chain[-1]

    def get_height(self) -> int:
        return len(self.chain)

    def get_block_by_hash(self, block_hash: str) -> Optional[Block]:
        for block in self.chain:
            if block.hash == block_hash:
                return block
        return None

    def get_balance(self, address: str) -> float:
        balance = 0.0
        for block in self.chain:
            for tx in block.transactions:
                if tx.to_address == address:
                    balance += tx.amount
                if tx.from_address == address and tx.from_address != "COINBASE":
                    balance -= tx.amount
        return balance

    def has_sufficient_balance(self, address: str, amount: float) -> bool:
        return self.get_balance(address) >= amount

    # Compatibilidad con app.py (dashboard llama a estos métodos)
    def get_target_hex(self) -> str:
        return "PoA"

    def get_estimated_block_time(self) -> str:
        from config import BLOCK_TIME
        return f"~{BLOCK_TIME}s"

    # ──────────────────────────────────────────────────────────
    # Mempool
    # ──────────────────────────────────────────────────────────

    def add_transaction_to_mempool(self, tx: Transaction) -> bool:
        with self._lock:
            if len(self.mempool) >= self.MAX_MEMPOOL_SIZE:
                print("[MEMPOOL] Rechazada: mempool lleno")
                return False

            if not tx.is_valid():
                print("[MEMPOOL] Rechazada: firma inválida")
                return False

            tx_hash = tx.hash()
            if any(t.hash() == tx_hash for t in self.mempool):
                print("[MEMPOOL] Rechazada: duplicada")
                return False

            # Verificar balance solo para TXs con amount > 0
            if tx.from_address != "COINBASE" and tx.amount > 0:
                if not self.has_sufficient_balance(tx.from_address, tx.amount):
                    print("[MEMPOOL] Rechazada: fondos insuficientes")
                    return False

            # Si TITULO_MODE, verificar que TXs de título vienen de issuers autorizados
            if TITULO_MODE and tx.data.get("tipo") == "titulo_universitario":
                if tx.from_address not in AUTHORIZED_ISSUERS:
                    print(f"[MEMPOOL] Rechazada: {tx.from_address[:12]}... no es issuer autorizado")
                    return False

            self.mempool.append(tx)
            tipo = f" [{tx.data.get('tipo')}]" if tx.data else ""
            print(
                f"[MEMPOOL] TX agregada: {tx_hash[:16]}..."
                f" ({tx.from_address[:8]}→{tx.to_address[:8]}{tipo})"
            )
            return True

    def get_transactions_for_block(self, max_count: int = None) -> List[Transaction]:
        if max_count is None:
            max_count = self.MAX_TXS_PER_BLOCK
        return self.mempool[:max_count]

    def remove_transactions(self, tx_hashes: List[str]):
        self.mempool = [
            tx for tx in self.mempool
            if tx.hash() not in tx_hashes
        ]

    # ──────────────────────────────────────────────────────────
    # Producción de bloques PoA
    # ──────────────────────────────────────────────────────────

    def produce_block_poa(self, validator_wallet) -> Optional[Block]:
        """
        Produce y firma un bloque PoA.

        En PoA no hay puzzle computacional. El validador:
        1. Toma las TXs del mempool
        2. Construye el bloque candidato
        3. Calcula el hash del bloque (hash_without_sigs)
        4. Lo firma con su llave privada Ed25519
        5. Agrega el bloque a la cadena si es válido

        Con QUORUM_REQUIRED = 1 (demo), el bloque se confirma
        inmediatamente con la firma de un solo validador.

        Args:
            validator_wallet: Wallet del validador (debe estar en AUTHORIZED_VALIDATORS)

        Returns:
            El bloque confirmado, o None si el mempool está vacío
            o este nodo no es un validador autorizado.
        """
        if validator_wallet.address not in AUTHORIZED_VALIDATORS:
            print(f"[POA] {validator_wallet.address[:12]}... no es validador autorizado")
            return None

        with self._lock:
            if not self.mempool:
                return None

            pending = self.get_transactions_for_block()

            merkle = MerkleTree(pending)
            header = BlockHeader(
                prev_hash   = self.get_latest_block().hash,
                merkle_root = merkle.get_root(),
                timestamp   = time.time(),
                signatures  = {},
            )
            candidate = Block(header, pending)

            # Firmar el hash del bloque con la llave privada del validador
            msg = candidate.header.hash_without_sigs().encode()
            sig = validator_wallet.sign(msg)   # retorna bytes
            candidate.header.signatures[validator_wallet.address] = sig.hex()

            if self._is_valid_block_poa(candidate, self.chain[-1]):
                self.chain.append(candidate)
                confirmed = [tx.hash() for tx in pending]
                self.remove_transactions(confirmed)
                print(
                    f"[POA] Bloque #{self.get_height() - 1} producido. "
                    f"TXs: {len(pending)}, Firmas: {len(candidate.header.signatures)}"
                )
                return candidate

            print("[POA] Error: bloque candidato inválido")
            return None

    # ──────────────────────────────────────────────────────────
    # Validación PoA
    # ──────────────────────────────────────────────────────────

    def _is_valid_block_poa(self, block: Block, prev_block: Block) -> bool:
        """
        Valida un bloque según las reglas PoA.

        Checks:
        1. Encadenamiento: prev_hash conecta con el bloque anterior
        2. Timestamp razonable (no más de 2h en el futuro)
        3. Merkle root correcto
        4. Firmas válidas con quórum suficiente
        5. TXs de título solo de issuers autorizados (si TITULO_MODE)
        6. Todas las TXs tienen firma Ed25519 válida
        """
        # 1. Encadenamiento
        if block.header.prev_hash != prev_block.hash:
            print(f"[VALIDATION] prev_hash no conecta")
            return False

        # 2. Timestamp
        if block.header.timestamp > time.time() + 7200:
            print(f"[VALIDATION] Timestamp futuro")
            return False

        # 3. Merkle root
        if not block.validate_merkle_root():
            print(f"[VALIDATION] Merkle root incorrecto")
            return False

        # 4. Quórum de firmas
        msg         = block.header.hash_without_sigs().encode()
        valid_sigs  = 0

        for addr, sig_hex in block.header.signatures.items():
            if addr not in AUTHORIZED_VALIDATORS:
                continue
            pubkey_hex = VALIDATOR_PUBKEYS.get(addr)
            if not pubkey_hex:
                continue
            try:
                sig = bytes.fromhex(sig_hex)
                if Wallet.verify_from_pubkey_hex(pubkey_hex, msg, sig):
                    valid_sigs += 1
            except Exception:
                continue

        if valid_sigs < QUORUM_REQUIRED:
            print(
                f"[VALIDATION] Quórum insuficiente: "
                f"{valid_sigs}/{QUORUM_REQUIRED} firmas válidas"
            )
            return False

        # 5. TXs de título solo de issuers autorizados
        if TITULO_MODE:
            for tx in block.transactions:
                if tx.data.get("tipo") == "titulo_universitario":
                    if tx.from_address not in AUTHORIZED_ISSUERS:
                        print(f"[VALIDATION] TX de título de issuer no autorizado")
                        return False

        # 6. Firmas de TXs
        if not block.validate_transactions():
            print(f"[VALIDATION] TX con firma inválida")
            return False

        return True

    # ──────────────────────────────────────────────────────────
    # Agregar bloque (recibido de la red o producido localmente)
    # ──────────────────────────────────────────────────────────

    def add_block(self, block: Block) -> bool:
        """
        Agrega un bloque a la cadena tras validarlo.
        Llamado tanto al producir localmente como al recibir de la red.
        """
        if not self._is_valid_block_poa(block, self.get_latest_block()):
            return False
        with self._lock:
            self.chain.append(block)
            confirmed = [tx.hash() for tx in block.transactions]
            self.remove_transactions(confirmed)
        return True

    # ──────────────────────────────────────────────────────────
    # Validación de cadena completa
    # ──────────────────────────────────────────────────────────

    def validate_chain(self, chain: List[Block]) -> bool:
        """
        Valida una cadena completa bloque a bloque.
        Usado por replace_chain() al recibir una cadena externa.
        """
        if not chain:
            return False

        # El génesis debe coincidir
        if chain[0].hash != self.chain[0].hash:
            print("[VALIDATION] Génesis diferente")
            return False

        for i in range(1, len(chain)):
            if not self._is_valid_block_poa(chain[i], chain[i - 1]):
                print(f"[VALIDATION] Bloque {i} inválido")
                return False

        return True

    # ──────────────────────────────────────────────────────────
    # Longest chain rule
    # ──────────────────────────────────────────────────────────

    def replace_chain(self, new_chain: List[Block]) -> bool:
        """
        Reemplaza la cadena local si la nueva es más larga y válida.
        Regla simple: cadena más larga gana (equivalente a PoW cuando
        la dificultad es uniforme para todos los validadores).
        """
        if len(new_chain) <= len(self.chain):
            print(
                f"[CHAIN] Rechazada: nueva ({len(new_chain)}) "
                f"<= actual ({len(self.chain)})"
            )
            return False

        if not self.validate_chain(new_chain):
            print("[CHAIN] Rechazada: inválida")
            return False

        fork_point   = self._find_fork_point(new_chain)
        orphaned_txs = []

        for block in self.chain[fork_point:]:
            for tx in block.transactions:
                if not tx.is_coinbase():
                    orphaned_txs.append(tx)

        confirmed_in_new = {
            tx.hash()
            for block in new_chain[fork_point:]
            for tx in block.transactions
        }

        old_height  = len(self.chain)
        with self._lock:
            self.chain = new_chain

        recovered = 0
        for tx in orphaned_txs:
            if tx.hash() not in confirmed_in_new:
                if self.add_transaction_to_mempool(tx):
                    recovered += 1

        self.remove_transactions(list(confirmed_in_new))

        print(
            f"[CHAIN] Reemplazada: {old_height}→{len(self.chain)} bloques "
            f"(fork en {fork_point}, {recovered} TXs recuperadas)"
        )
        return True

    def _find_fork_point(self, other_chain: List[Block]) -> int:
        min_len = min(len(self.chain), len(other_chain))
        for i in range(min_len):
            if self.chain[i].hash != other_chain[i].hash:
                return i
        return min_len

    # ──────────────────────────────────────────────────────────
    # Serialización (sin cambios)
    # ──────────────────────────────────────────────────────────

    def get_chain_as_dicts(self) -> List[dict]:
        return [block.to_dict() for block in self.chain]

    @staticmethod
    def chain_from_dicts(data: List[dict]) -> List[Block]:
        return [Block.from_dict(d) for d in data]

    def __repr__(self):
        return (
            f"Blockchain(height={self.get_height()}, "
            f"mempool={len(self.mempool)})"
        )
