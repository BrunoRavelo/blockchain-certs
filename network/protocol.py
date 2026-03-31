"""
Protocolo de mensajes P2P
Define formato estándar + constantes de tipos de mensaje

Equivalencia con Bitcoin:
- version/verack  → handshake inicial
- ping/pong       → keep-alive
- addr/getaddr    → gossip de peers
- inv             → anunciar bloque o TX por hash
- getblocks       → solicitar lista de bloques
- block           → enviar bloque completo
- tx              → propagar transacción

Diferencias con Bitcoin:
- Bitcoin usa TCP binario con magic bytes; nosotros usamos WebSocket + JSON
- Bitcoin tiene ~30 tipos de mensaje; nosotros implementamos los esenciales
"""

import json
import hashlib
import uuid
from datetime import datetime


# ──────────────────────────────────────────────────────────
# Constantes de tipos de mensaje
# ──────────────────────────────────────────────────────────

# Handshake
MSG_VERSION  = 'version'   # Presentación inicial al conectar
MSG_VERACK   = 'verack'    # Confirmación del handshake

# Keep-alive
MSG_PING     = 'ping'      # Verificar que el peer sigue activo
MSG_PONG     = 'pong'      # Respuesta al ping

# Gossip de peers
MSG_GETADDR  = 'getaddr'   # Pedir lista de peers conocidos
MSG_ADDR     = 'addr'      # Responder con lista de peers

# Transacciones
MSG_TX       = 'tx'        # Propagar una transacción firmada

# Bloques — Sprint 4
MSG_INV      = 'inv'       # Anunciar que tenemos un bloque/TX nuevo (por hash)
MSG_GETBLOCKS = 'getblocks' # Solicitar bloques desde cierta altura
MSG_BLOCK    = 'block'     # Enviar un bloque completo


# ──────────────────────────────────────────────────────────
# Funciones de creación y validación
# ──────────────────────────────────────────────────────────

def create_message(msg_type: str, payload: dict) -> dict:
    """
    Crea un mensaje P2P con formato estándar.

    Formato:
        {
            'type':      str,    # Tipo de mensaje (constantes MSG_*)
            'id':        str,    # UUID único — usado para anti-loop
            'timestamp': float,  # Unix timestamp
            'payload':   dict,   # Datos del mensaje
            'checksum':  str,    # SHA256 del payload (detecta corrupción)
        }

    El checksum equivale funcionalmente a los magic bytes de Bitcoin:
    permite detectar mensajes corruptos o malformados antes de procesarlos.

    Args:
        msg_type: Tipo de mensaje (usar constantes MSG_*)
        payload:  Datos del mensaje

    Returns:
        Diccionario con el mensaje completo.
    """
    payload_str = json.dumps(payload, sort_keys=True)
    checksum    = hashlib.sha256(payload_str.encode()).hexdigest()

    return {
        'type':      msg_type,
        'id':        str(uuid.uuid4()),
        'timestamp': datetime.now().timestamp(),
        'payload':   payload,
        'checksum':  checksum,
    }


def validate_message(msg: dict) -> bool:
    """
    Valida que un mensaje tenga formato correcto y checksum válido.

    Args:
        msg: Diccionario con el mensaje recibido.

    Returns:
        True si el mensaje es válido.
    """
    required = ['type', 'id', 'timestamp', 'payload', 'checksum']
    if not all(field in msg for field in required):
        return False

    payload_str          = json.dumps(msg['payload'], sort_keys=True)
    calculated_checksum  = hashlib.sha256(payload_str.encode()).hexdigest()

    return calculated_checksum == msg['checksum']
