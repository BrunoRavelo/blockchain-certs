"""
Transacción con firma digital EdDSA (Ed25519)

Cambios respecto al original (Sprint 1A — demo títulos):
- Campo `data: dict` agregado para metadatos de título universitario
- `data` incluido en hash() — el contenido queda sellado criptográficamente
- `data` siempre presente en to_dict() (no es un campo de firma, es contenido)
- from_dict() reconstruye `data` con default {}
- Eliminada la TX coinbase — en PoA no hay recompensa de bloque
"""

import hashlib
import json
import time
from typing import Optional


class Transaction:
    """
    Transacción del sistema de títulos universitarios.

    Tipos:
    - Normal:   from_address → to_address  (requiere firma Ed25519)
    - Título:   secretaria  → egresado     (con data = metadatos del diploma)

    El campo `data` se incluye en el hash (txid) para que el contenido
    del título sea inmutable una vez confirmado en la cadena.
    """

    def __init__(self, from_address: str, to_address: str, amount: float, data: dict = None):
        """
        Args:
            from_address: Dirección del remitente (o "COINBASE" para génesis)
            to_address:   Dirección del destinatario
            amount:       Cantidad a transferir (>= 0)
            data:         Metadatos opcionales (para TXs de título universitario)
        """
        self.from_address = from_address
        self.to_address   = to_address
        self.amount       = amount
        self.timestamp    = time.time()
        self.data: dict   = data if data is not None else {}

        self.public_key: Optional[str] = None
        self.signature:  Optional[str] = None

    # ──────────────────────────────────────────────────────────
    # Serialización
    # ──────────────────────────────────────────────────────────

    def to_dict(self, include_signature: bool = True) -> dict:
        """
        Serializa la transacción a diccionario.

        `data` siempre se incluye — no es un campo de firma sino contenido
        de la transacción. `include_signature=False` solo omite signature
        y public_key (para calcular el hash y para la raíz Merkle).

        Args:
            include_signature: Si False, omite signature y public_key.

        Returns:
            Diccionario con los campos de la transacción.
        """
        d = {
            'from':       self.from_address,
            'to':         self.to_address,
            'amount':     self.amount,
            'timestamp':  self.timestamp,
            'data':       self.data,
            'public_key': self.public_key,
        }
        if include_signature and self.signature:
            d['signature'] = self.signature
        return d

    @staticmethod
    def from_dict(d: dict) -> 'Transaction':
        """
        Deserializa una transacción desde diccionario (red o bloque).
        """
        tx = Transaction(
            from_address=d['from'],
            to_address=d['to'],
            amount=d['amount'],
            data=d.get('data', {}),
        )
        tx.timestamp  = d.get('timestamp', time.time())
        tx.public_key = d.get('public_key')
        tx.signature  = d.get('signature')
        return tx

    # ──────────────────────────────────────────────────────────
    # Hash (txid)
    # ──────────────────────────────────────────────────────────

    def hash(self) -> str:
        """
        Calcula el txid con double SHA256.

        Incluye `data` para que el contenido del título sea parte
        del hash — cualquier modificación al diploma invalida el txid.

        Returns:
            txid en hexadecimal (64 caracteres).
        """
        payload = {
            'from':      self.from_address,
            'to':        self.to_address,
            'amount':    self.amount,
            'timestamp': self.timestamp,
            'data':      self.data,
        }
        raw     = json.dumps(payload, sort_keys=True).encode()
        digest1 = hashlib.sha256(raw).digest()
        return hashlib.sha256(digest1).hexdigest()

    # ──────────────────────────────────────────────────────────
    # Firma
    # ──────────────────────────────────────────────────────────

    def sign(self, wallet) -> None:
        """
        Firma la transacción con la wallet del remitente.

        Args:
            wallet: Instancia de Wallet con la clave privada del remitente.
        """
        if self.from_address == "COINBASE":
            raise ValueError("Las transacciones coinbase no se firman.")

        assert wallet.address == self.from_address, (
            f"La wallet ({wallet.address[:12]}...) no corresponde "
            f"al remitente ({self.from_address[:12]}...)"
        )

        self.public_key = wallet.get_public_key_hex()
        tx_data         = self.to_dict(include_signature=False)
        self.signature  = wallet.sign_transaction(tx_data)

    # ──────────────────────────────────────────────────────────
    # Validación
    # ──────────────────────────────────────────────────────────

    def is_valid(self) -> bool:
        """
        Valida la transacción.

        Reglas:
        1. COINBASE (génesis) siempre válida.
        2. Campos obligatorios presentes y amount >= 0.
        3. Firma Ed25519 correcta.

        Returns:
            True si la transacción es válida.
        """
        # Regla 1 — coinbase (solo existe en el bloque génesis)
        if self.from_address == "COINBASE":
            return True

        # Regla 2 — campos básicos
        # amount >= 0 permite TXs de registro (amount=0, data con metadatos)
        if not all([
            self.from_address,
            self.to_address,
            self.amount >= 0,
            self.public_key,
            self.signature,
        ]):
            return False

        # Regla 3 — verificar firma Ed25519
        from core.wallet import Wallet
        tx_data = self.to_dict(include_signature=False)
        return Wallet.verify_signature(tx_data, self.public_key, self.signature)

    # ──────────────────────────────────────────────────────────
    # Utilidades
    # ──────────────────────────────────────────────────────────

    def is_coinbase(self) -> bool:
        return self.from_address == "COINBASE"

    def is_titulo(self) -> bool:
        """Retorna True si es una transacción de título universitario."""
        return self.data.get("tipo") == "titulo_universitario"

    def short_hash(self, n: int = 16) -> str:
        return self.hash()[:n] + "..."

    def __repr__(self):
        src = self.from_address[:10]
        dst = self.to_address[:10]
        tipo = f" [{self.data.get('tipo', '')}]" if self.data else ""
        return f"Transaction({src}...→{dst}..., amount={self.amount}{tipo})"
