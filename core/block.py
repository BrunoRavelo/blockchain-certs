"""
Bloque de la blockchain — Demo Títulos Universitarios

Sprint 1A: migración completa de PoW a PoA.

Cambios respecto al original:
- BlockHeader: eliminados `target` y `nonce` (PoW)
- BlockHeader: agregado `signatures: dict` (PoA)
  Estructura: { "address_validador": "firma_hex_ed25519" }
- hash() no incluye signatures (evita dependencia circular)
- hash_without_sigs() = alias explícito de hash() — es lo que firman los validadores
- Eliminado validate_pow()
- difficulty_display ahora muestra info de firmas PoA
"""

import hashlib
import json
import time
from typing import List, Optional
from core.merkle import MerkleTree


class BlockHeader:
    """
    Header del bloque (metadatos) — Proof of Authority.

    Un bloque es válido si tiene firmas Ed25519 de al menos
    QUORUM_REQUIRED validadores autorizados (config.AUTHORIZED_VALIDATORS).

    Por qué hash() no incluye signatures:
        Las firmas se calculan SOBRE el hash del bloque.
        Si el hash incluyera las firmas, habría una dependencia
        circular imposible de resolver. Por eso:
        1. Se calcula hash_without_sigs() del contenido
        2. Los validadores firman ese hash
        3. Las firmas se almacenan en signatures
        4. El bloque es válido si las firmas son correctas sobre ese hash
    """

    def __init__(
        self,
        prev_hash:   str,
        merkle_root: str,
        timestamp:   float,
        signatures:  dict = None,
    ):
        self.prev_hash   = prev_hash
        self.merkle_root = merkle_root
        self.timestamp   = timestamp
        self.signatures  = signatures if signatures is not None else {}

    # ──────────────────────────────────────────────────────────
    # Hash
    # ──────────────────────────────────────────────────────────

    def hash_without_sigs(self) -> str:
        """
        Hash del contenido del bloque SIN incluir las firmas.

        Este es el mensaje que los validadores firman con Ed25519.
        Es también el hash que se usa como prev_hash del siguiente bloque.

        Returns:
            Double SHA256 en hexadecimal (64 caracteres).
        """
        payload = {
            'prev_hash':   self.prev_hash,
            'merkle_root': self.merkle_root,
            'timestamp':   self.timestamp,
        }
        raw    = json.dumps(payload, sort_keys=True).encode()
        hash1  = hashlib.sha256(raw).digest()
        return hashlib.sha256(hash1).hexdigest()

    def hash(self) -> str:
        """
        Hash del bloque. Equivalente a hash_without_sigs().

        Alias que mantiene la misma interfaz que el código original
        (block.hash, block.header.hash()) sin cambiar el resto del sistema.
        """
        return self.hash_without_sigs()

    # ──────────────────────────────────────────────────────────
    # Serialización
    # ──────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            'prev_hash':   self.prev_hash,
            'merkle_root': self.merkle_root,
            'timestamp':   self.timestamp,
            'signatures':  self.signatures,
        }

    @staticmethod
    def from_dict(data: dict) -> 'BlockHeader':
        return BlockHeader(
            prev_hash   = data['prev_hash'],
            merkle_root = data['merkle_root'],
            timestamp   = data['timestamp'],
            signatures  = data.get('signatures', {}),
        )

    # ──────────────────────────────────────────────────────────
    # Propiedades de compatibilidad con el dashboard
    # ──────────────────────────────────────────────────────────

    @property
    def difficulty_display(self) -> str:
        """
        Compatibilidad con app.py y global.py que leen este campo.
        En lugar de mostrar el target PoW, muestra el estado de firmas PoA.
        """
        n = len(self.signatures)
        if n == 0:
            return "PoA (sin firmas)"
        firmas = "firma" if n == 1 else "firmas"
        return f"PoA ({n} {firmas})"

    @property
    def nonce(self) -> int:
        """
        Compatibilidad temporal con app.js que accede a block.nonce.
        Retorna 0 — en PoA no existe nonce.
        Se eliminará cuando actualicemos app.js en Sprint 2B.
        """
        return 0

    def __repr__(self):
        return (
            f"BlockHeader("
            f"hash={self.hash()[:16]}..., "
            f"sigs={len(self.signatures)})"
        )


class Block:
    """
    Bloque completo: header + transacciones.

    Un bloque PoA es válido si:
    1. Las firmas en header.signatures son Ed25519 válidas de validadores autorizados
    2. La cantidad de firmas válidas >= QUORUM_REQUIRED
    3. Merkle root correcto
    4. Todas las transacciones tienen firma válida
    5. prev_hash conecta con el bloque anterior

    La validación completa ocurre en blockchain._is_valid_block_poa().
    Este archivo solo define la estructura del bloque.
    """

    def __init__(self, header: BlockHeader, transactions: List):
        self.header       = header
        self.transactions = transactions

    @property
    def hash(self) -> str:
        """Hash del bloque (property, sin paréntesis — misma interfaz que el original)."""
        return self.header.hash()

    # ──────────────────────────────────────────────────────────
    # Validaciones de contenido (independientes de PoA)
    # ──────────────────────────────────────────────────────────

    def validate_merkle_root(self) -> bool:
        """Verifica que la raíz Merkle corresponde a las transacciones del bloque."""
        merkle = MerkleTree(self.transactions)
        return merkle.get_root() == self.header.merkle_root

    def validate_transactions(self) -> bool:
        """Verifica que todas las transacciones tienen firma Ed25519 válida."""
        for tx in self.transactions:
            if not tx.is_valid():
                return False
        return True

    # ──────────────────────────────────────────────────────────
    # Serialización
    # ──────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            'header':       self.header.to_dict(),
            'transactions': [tx.to_dict() for tx in self.transactions],
        }

    @staticmethod
    def from_dict(data: dict) -> 'Block':
        from core.transaction import Transaction
        header       = BlockHeader.from_dict(data['header'])
        transactions = [
            Transaction.from_dict(tx_data)
            for tx_data in data['transactions']
        ]
        return Block(header, transactions)

    def __repr__(self):
        return (
            f"Block("
            f"hash={self.hash[:16]}..., "
            f"txs={len(self.transactions)}, "
            f"sigs={len(self.header.signatures)})"
        )
