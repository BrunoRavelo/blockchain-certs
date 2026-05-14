"""
launcher_titulos.py — Demo Títulos Universitarios en Blockchain

Roles y responsabilidades:
    issuer    → Anáhuac: emite títulos + produce bloques (MANUAL)
    validator → Verificador: verifica bloques recibidos, NO produce bloques
    graduate  → 3 egresados: reciben y muestran sus credenciales

Nodos:
    :8888  Seed node
    :8002  Anáhuac     (issuer)    → :9002
    :8003  Verificador (validator) → :9003
    :8004  Bruno Rosas (graduate)  → :9004
    :8005  Ana López   (graduate)  → :9005
    :8006  Carlos Méndez(graduate) → :9006
    :9000  Explorador público
"""

import asyncio
import threading
import time
import sys

from core.wallet import Wallet
from core.blockchain import Blockchain
from network.p2p_node import P2PNode
from network.seed_node import SeedNode
import config

SEED_PORT = 8888

NODES = [
    {
        'role':       'issuer',
        'p2p':        8002,
        'dashboard':  9002,
        'name':       'Anahuac',
        'institucion': 'Universidad Anáhuac México',
    },
    {
        'role':       'validator',
        'p2p':        8003,
        'dashboard':  9003,
        'name':       'Verificador',
        'institucion': 'Consejo para la Acreditación de la Educación Superior',
    },
    {
        'role':       'graduate',
        'p2p':        8004,
        'dashboard':  9004,
        'name':       'Bruno Rosas',
        'institucion': '',
    },
    {
        'role':       'graduate',
        'p2p':        8005,
        'dashboard':  9005,
        'name':       'Ana Lopez',
        'institucion': '',
    },
    {
        'role':       'graduate',
        'p2p':        8006,
        'dashboard':  9006,
        'name':       'Carlos Mendez',
        'institucion': '',
    },
]


def setup_wallets_and_config():
    """
    Una wallet por nodo — clave = name (soporta múltiples issuers).
    Solo los issuers pueden firmar bloques Y emitir títulos.
    Los validators solo propagan y verifican bloques entrantes.
    """
    wallets = {n['name']: Wallet() for n in NODES}

    # Solo issuers son validadores PoA (pueden firmar bloques)
    issuer_wallets    = [wallets[n['name']] for n in NODES if n['role'] == 'issuer']
    validator_wallets = [wallets[n['name']] for n in NODES if n['role'] == 'issuer']
    # Nota: los nodos 'validator' (COPAES) NO firman bloques en este demo

    config.AUTHORIZED_VALIDATORS = [w.address for w in validator_wallets]
    config.VALIDATOR_PUBKEYS     = {w.address: w.get_public_key_hex() for w in validator_wallets}
    config.AUTHORIZED_ISSUERS    = [w.address for w in issuer_wallets]
    config.QUORUM_REQUIRED       = 1
    config.TITULO_MODE           = True
    config.NOMBRE_INSTITUCION    = 'Blockchain Certs Demo'

    return wallets


def print_demo_info(wallets):
    sep = '═' * 70
    print(f'\n{sep}')
    print('  DEMO — TÍTULOS UNIVERSITARIOS EN BLOCKCHAIN')
    print(sep)

    for n in NODES:
        w = wallets[n['name']]
        inst = f"  ({n['institucion']})" if n['institucion'] else ''
        print(f"\n  [{n['name']}]{inst}")
        print(f"    Rol:       {n['role']}")
        print(f"    Dashboard: http://localhost:{n['dashboard']}")
        print(f"    Address:   {w.address}")

    print(f'\n  [Explorador Público / Verificador]')
    print(f'    URL: http://localhost:9000')

    print(f'\n{sep}')
    print('  FLUJO DEL DEMO:')
    print('  1. Anáhuac (:9002) → llenar formulario de título')
    print('  2. Seleccionar egresado del dropdown de conocidos')
    print('  3. Click "Emitir" → TX en mempool')
    print('  4. Click "Sellar bloque" → bloque confirmado y propagado')
    print('  5. Egresado ve su credencial en su dashboard')
    print('  6. :9000 → pegar TX hash → verificar título')
    print(f'\n  Addresses de egresados:')
    for n in NODES:
        if n['role'] == 'graduate':
            print(f'    {n["name"]:15} → {wallets[n["name"]].address}')
    print(f'\n  Mapeo P2P → Dashboard:')
    for n in NODES:
        print(f'    :{n["p2p"]}  →  :{n["dashboard"]}  ({n["name"]})')
    print(f'\n{sep}\n')


def start_seed_node():
    seed = SeedNode(host='localhost', port=SEED_PORT)
    threading.Thread(target=seed.run, daemon=True).start()
    time.sleep(1)
    print(f'[SEED] :{SEED_PORT}')
    return seed


def start_node(node_cfg: dict, wallet: Wallet):
    role      = node_cfg['role']
    p2p_port  = node_cfg['p2p']
    dash_port = node_cfg['dashboard']
    name      = node_cfg['name']
    institucion = node_cfg.get('institucion', '')

    blockchain = Blockchain()
    node = P2PNode(
        host            = 'localhost',
        port            = p2p_port,
        bootstrap_peers = [],
        blockchain      = blockchain,
        seed_host       = 'localhost',
        wallet          = wallet,
        role            = role,
        dashboard_port  = dash_port,
    )
    node.id           = f"{name.lower().replace(' ', '_')}_{p2p_port}"
    node.display_name = name
    node.institucion  = institucion

    from dashboard.app import NodeDashboard
    dashboard = NodeDashboard(node, dash_port)

    threading.Thread(target=dashboard.run, daemon=True).start()

    def run_node():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(node.start())
        except Exception as e:
            print(f'[{name}] Error: {e}')

    threading.Thread(target=run_node, daemon=True).start()
    print(f'[{role.upper():10}] {name:15} → P2P :{p2p_port} | Dashboard :{dash_port}')
    return node


def main():
    print('\nIniciando Blockchain Certs Demo...\n')

    wallets = setup_wallets_and_config()
    start_seed_node()

    nodes = []
    for node_cfg in NODES:
        node = start_node(node_cfg, wallets[node_cfg['name']])
        nodes.append(node)
        time.sleep(1.5)

    from dashboard_global.app import GlobalDashboard
    threading.Thread(
        target=lambda: GlobalDashboard(
            seed_host='localhost', seed_port=SEED_PORT, port=9000
        ).run(),
        daemon=True
    ).start()

    print('\nConectando nodos', end='', flush=True)
    for _ in range(7):
        time.sleep(1)
        print('.', end='', flush=True)
    print(' listo.\n')

    print_demo_info(wallets)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print('\nDeteniendo demo...')
        sys.exit(0)


if __name__ == '__main__':
    main()
