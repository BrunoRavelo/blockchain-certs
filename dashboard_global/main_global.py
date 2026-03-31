"""
Dashboard Global — Máquina del Instructor

Corre como proceso independiente, apunta a nodos remotos via HTTP.
Funciona tanto en demo local como en LAN de 30 máquinas.

Componentes:
    - TxOrchestrator: controla TXs automáticas de toda la red
    - GlobalDashboard: Flask en puerto 9000, observer de toda la red

Uso:
    # Demo local (segunda terminal, después de launcher_manual.py):
    python main_global.py

    # LAN (máquina del instructor):
    python main_global.py --seed-host 192.168.1.1

    # Sin orquestador (si launcher_auto.py ya tiene el suyo):
    python main_global.py --no-orchestrator
"""

import asyncio
import argparse
import threading
from core.tx_orchestrator import TxOrchestrator, ORCH_AUTO
from dashboard_global.app import GlobalDashboard
from config import SEED_HOST, SEED_PORT

GLOBAL_DASHBOARD_PORT = 9001


async def main(
    seed_host:       str  = SEED_HOST,
    seed_port:       int  = SEED_PORT,
    no_orchestrator: bool = False,
):
    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║           BLOCKCHAIN DEMO — Dashboard Global (Instructor)            ║
╚══════════════════════════════════════════════════════════════════════╝

  Seed:        http://{seed_host}:{seed_port}
  Dashboard:   http://localhost:{GLOBAL_DASHBOARD_PORT}
  Orquestador: {'desactivado' if no_orchestrator else 'activo (delay 30s)'}
""")

    # ── Orquestador ────────────────────────────────────────────
    orchestrator = None
    if not no_orchestrator:
        print("  [1/2] Creando orquestador de TXs...")
        orchestrator = TxOrchestrator(
            seed_host=seed_host,
            seed_port=seed_port,
        )
        asyncio.create_task(_start_orchestrator_delayed(orchestrator))
    else:
        print("  [1/2] Orquestador desactivado")

    # ── Dashboard Global ───────────────────────────────────────
    print("  [2/2] Iniciando dashboard global...")
    dashboard = GlobalDashboard(
        seed_host=seed_host,
        seed_port=seed_port,
        port=GLOBAL_DASHBOARD_PORT,
        orchestrator=orchestrator,
    )
    t = threading.Thread(target=dashboard.run, daemon=True)
    t.start()

    print(f"""
══════════════════════════════════════════════════════════════════════
  Dashboard activo en: http://localhost:{GLOBAL_DASHBOARD_PORT}
  Presiona Ctrl+C para detener.
══════════════════════════════════════════════════════════════════════
""")

    try:
        await asyncio.Future()
    except (KeyboardInterrupt, asyncio.CancelledError):
        if orchestrator:
            orchestrator.stop()
        print("\n  Dashboard global detenido.\n")


async def _start_orchestrator_delayed(orchestrator: TxOrchestrator):
    print("  [ORCH] Esperando 30s para que los nodos tengan balance...")
    await asyncio.sleep(30)
    orchestrator.set_mode(ORCH_AUTO)
    print("  [ORCH] TXs automáticas activas")
    await orchestrator.start()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Dashboard Global del instructor'
    )
    parser.add_argument('--seed-host', default=SEED_HOST)
    parser.add_argument('--seed-port', type=int, default=SEED_PORT)
    parser.add_argument('--no-orchestrator', action='store_true')
    args = parser.parse_args()

    try:
        asyncio.run(main(
            seed_host=args.seed_host,
            seed_port=args.seed_port,
            no_orchestrator=args.no_orchestrator,
        ))
    except KeyboardInterrupt:
        print("\n  Dashboard global detenido.\n")
