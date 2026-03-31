"""
Wallet con criptografía EdDSA (Ed25519)

Cambios respecto al original (Sprint 1B — demo títulos):
- Agregado: sign(message: bytes) -> str
  Firma bytes directos (para firmar el hash de un bloque en PoA)
- Agregado: verify_from_pubkey_hex() estático
  Verifica una firma PoA dado pubkey como hex string
- Todo lo demás sin cambios
"""

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from Crypto.Hash import RIPEMD160
import hashlib


class Wallet:
    """
    Wallet con Ed25519.
    Compatible con el sistema original + nuevos métodos para PoA.
    """

    def __init__(self):
        self.private_key = ed25519.Ed25519PrivateKey.generate()
        self.public_key  = self.private_key.public_key()
        self.address     = self._generate_address()

    # ──────────────────────────────────────────────────────────
    # Generación de dirección (sin cambios)
    # ──────────────────────────────────────────────────────────

    def _hash160(self, pub_bytes: bytes) -> bytes:
        sha256 = hashlib.sha256(pub_bytes).digest()
        h = RIPEMD160.new(sha256)
        return h.digest()

    def _checksum(self, payload: bytes) -> bytes:
        return hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]

    def _base58check_encode(self, payload: bytes) -> str:
        alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
        count = 0
        for byte in payload:
            if byte == 0:
                count += 1
            else:
                break
        num = int.from_bytes(payload, 'big')
        result = ''
        while num > 0:
            num, remainder = divmod(num, 58)
            result = alphabet[remainder] + result
        return '1' * count + result

    def _generate_address(self) -> str:
        pub_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        hash160  = self._hash160(pub_bytes)
        versioned = b'\x00' + hash160
        checksum  = self._checksum(versioned)
        payload   = versioned + checksum
        return self._base58check_encode(payload)

    # ──────────────────────────────────────────────────────────
    # Firma de transacciones (sin cambios)
    # ──────────────────────────────────────────────────────────

    def sign_transaction(self, tx_data: dict) -> str:
        """
        Firma un diccionario de transacción.
        Usado por Transaction.sign().
        """
        import json
        tx_string = json.dumps(tx_data, sort_keys=True)
        signature = self.private_key.sign(tx_string.encode('utf-8'))
        return signature.hex()

    def get_public_key_hex(self) -> str:
        pub_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        return pub_bytes.hex()

    @staticmethod
    def verify_signature(tx_data: dict, public_key_hex: str, signature_hex: str) -> bool:
        """
        Verifica firma de transacción (dict → JSON → verify).
        Usado por Transaction.is_valid().
        Sin cambios respecto al original.
        """
        import json
        try:
            pub_bytes  = bytes.fromhex(public_key_hex)
            public_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
            tx_string  = json.dumps(tx_data, sort_keys=True)
            signature  = bytes.fromhex(signature_hex)
            public_key.verify(signature, tx_string.encode('utf-8'))
            return True
        except Exception:
            return False

    # ──────────────────────────────────────────────────────────
    # NUEVO — Firma de bytes directos (para bloques PoA)
    # ──────────────────────────────────────────────────────────

    def sign(self, message: bytes) -> bytes:
        """
        Firma bytes directos con la llave privada Ed25519.

        Usado por blockchain.produce_block_poa() para firmar
        el hash del bloque candidato.

        Args:
            message: Bytes a firmar (tipicamente block_hash.encode())

        Returns:
            Firma en bytes (64 bytes Ed25519)
        """
        return self.private_key.sign(message)

    @staticmethod
    def verify_from_pubkey_hex(pubkey_hex: str, message: bytes, signature: bytes) -> bool:
        """
        Verifica una firma Ed25519 sobre bytes directos.

        Usado por blockchain._is_valid_block_poa() para verificar
        las firmas de los validadores en el header del bloque.

        Args:
            pubkey_hex: Llave pública del validador en hex (64 chars)
            message:    Bytes que fueron firmados (block_hash.encode())
            signature:  Firma en bytes (64 bytes)

        Returns:
            True si la firma es válida para esa pubkey y mensaje.
        """
        try:
            pub_bytes  = bytes.fromhex(pubkey_hex)
            public_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
            public_key.verify(signature, message)
            return True
        except Exception:
            return False

    def __repr__(self):
        return f"Wallet(address={self.address[:16]}...)"
