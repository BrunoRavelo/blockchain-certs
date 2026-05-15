"""
Configuración central — Demo Títulos Universitarios en Blockchain
PoA (Proof of Authority) reemplaza completamente el PoW anterior.
"""

import os

# ──────────────────────────────────────────────────────────
# Red (sin cambios respecto al original)
# ──────────────────────────────────────────────────────────

SEED_HOST = os.environ.get('SEED_HOST', 'localhost')
SEED_PORT = int(os.environ.get('SEED_PORT', 8888))

P2P_PORT       = int(os.environ.get('P2P_PORT', 5000))
DASHBOARD_PORT = int(os.environ.get('DASHBOARD_PORT', 8000))

MAX_OUTBOUND_CONNECTIONS = 8
MAX_INBOUND_CONNECTIONS  = 8
MAX_PEERS_TO_SHARE       = 10

CONNECT_TIMEOUT  = 5
GOSSIP_INTERVAL  = 30
PING_INTERVAL    = 30
CLEANUP_INTERVAL = 60

# ──────────────────────────────────────────────────────────
# PoA — reemplaza toda la sección PoW/mining
# ──────────────────────────────────────────────────────────

# Wallets autorizadas para firmar bloques.
# Se pueblan en runtime por launcher_titulos.py — no hardcodear aquí.
AUTHORIZED_VALIDATORS: list = []

# Mapa address → public_key_hex para verificar firmas de bloque.
# Se puebla en runtime junto con AUTHORIZED_VALIDATORS.
VALIDATOR_PUBKEYS: dict = {}

# Cuántas firmas de validadores autorizados necesita un bloque para ser válido.
# 1 = un solo validador firma (suficiente para el demo).
# 2 = quórum real (secretaría + organismo acreditador).
QUORUM_REQUIRED = 1

# Wallets autorizadas para emitir TXs de tipo titulo_universitario.
# Subconjunto de AUTHORIZED_VALIDATORS — normalmente solo la secretaría.
AUTHORIZED_ISSUERS: list = []

# ──────────────────────────────────────────────────────────
# Blockchain
# ──────────────────────────────────────────────────────────

MAX_MEMPOOL_SIZE  = 100
MAX_TXS_PER_BLOCK = 10

# ──────────────────────────────────────────────────────────
# Demo de títulos universitarios
# ──────────────────────────────────────────────────────────

TITULO_MODE      = True
NOMBRE_INSTITUCION = os.environ.get('NOMBRE_INSTITUCION', 'Universidad Demo')
