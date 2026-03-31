"""
Arranque del Seed Node
Ejecutar en la máquina del instructor (IP fija de la red)

Uso:
    python main_seed.py

Variables de entorno opcionales:
    SEED_PORT=8888   (default en config.py)

En laboratorio:
    - Ejecutar PRIMERO, antes que cualquier nodo
    - La IP de esta máquina es la que va en config.py → SEED_HOST
    - Todos los nodos deben poder alcanzar esta IP y puerto
"""

import argparse
from network.seed_node import SeedNode
from config import SEED_PORT


def main():
    parser = argparse.ArgumentParser(
        description='Seed Node — Servidor de descubrimiento de peers'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=SEED_PORT,
        help=f'Puerto HTTP del seed (default: {SEED_PORT})'
    )
    parser.add_argument(
        '--host',
        type=str,
        default='0.0.0.0',
        help='Host donde escuchar (default: 0.0.0.0 = todas las interfaces)'
    )
    args = parser.parse_args()

    print(f"""
╔══════════════════════════════════════════════╗
║         SEED NODE — BLOCKCHAIN DEMO          ║
╚══════════════════════════════════════════════╝

  Escuchando en: http://{args.host}:{args.port}

  Endpoints:
    GET  /health      — verificar estado
    POST /register    — registrar nodo
    GET  /peers       — obtener lista de peers
    GET  /peers/all   — todos (incluye inactivos)

  Arranca este nodo PRIMERO.
  Configura SEED_HOST={args.host} en config.py
  de todas las máquinas del laboratorio.

  Presiona Ctrl+C para detener.
""")

    seed = SeedNode(host=args.host, port=args.port)

    try:
        seed.run()
    except KeyboardInterrupt:
        print("\n\nSeed node detenido.\n")


if __name__ == '__main__':
    main()
