"""
main.py — Punto de entrada del sistema de trading algorítmico autónomo.

Uso:
    python main.py                          # sistema continuo, rotación automática
    python main.py --once                   # un solo ciclo
    python main.py --once --profile xauusd_h1  # un ciclo con perfil específico
    python main.py --stats                  # estadísticas
    python main.py --profiles              # listar perfiles disponibles
    python main.py --check                  # verificar setup
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
Path("output/logs").mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("output/logs/sistema.log", encoding="utf-8"),
    ]
)


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description = "Sistema de Trading Algorítmico Autónomo — MT5/MQL5"
    )
    parser.add_argument("--once",     action="store_true", help="Un solo ciclo")
    parser.add_argument("--stats",    action="store_true", help="Estadísticas")
    parser.add_argument("--check",    action="store_true", help="Verificar setup")
    parser.add_argument("--profiles", action="store_true", help="Listar perfiles")
    parser.add_argument(
        "--profile", type=str, default=None,
        help="Forzar un perfil específico (ej: eurusd_h4, xauusd_h1, gbpusd_h4)"
    )
    args = parser.parse_args()

    if args.check:
        import subprocess
        subprocess.run([sys.executable, "check_setup.py"])
        return

    if args.stats:
        from core.database import get_database
        get_database().print_stats()
        return

    if args.profiles:
        from core.config_loader import list_profiles
        list_profiles()
        return

    from agents.orchestrator import OrchestratorAgent
    orchestrator = OrchestratorAgent(force_profile=args.profile)

    if args.once:
        orchestrator.run_once()
    else:
        orchestrator.start()


if __name__ == "__main__":
    main()
