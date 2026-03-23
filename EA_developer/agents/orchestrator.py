"""
agents/orchestrator.py
======================
Orchestrator Agent — coordina el pipeline y lo ejecuta continuamente.
Soporta rotación automática entre perfiles (símbolo/timeframe).
"""

import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval   import IntervalTrigger

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database      import get_database
from core.memory        import get_memory
from core.pipeline      import TradingPipeline
from core.config_loader import get_active_profile, list_profiles, load_config

log = logging.getLogger(__name__)

ROOT_DIR    = Path(__file__).parent.parent
CONFIG_PATH = ROOT_DIR / "config.yaml"


class OrchestratorAgent:
    """
    Orquesta el pipeline con soporte multi-símbolo/timeframe.
    Rota automáticamente entre perfiles según rotation_schedule.
    """

    def __init__(self, force_profile: str = None):
        self.db            = get_database()
        self.memory        = get_memory()
        self.pipeline      = TradingPipeline()
        self.config        = load_config()
        self.force_profile = force_profile
        self.scheduler     = BlockingScheduler(timezone="UTC")
        log.info("OrchestratorAgent inicializado")

    # ── Ciclo principal ───────────────────────────────────────────────

    def run_cycle(self):
        """Ejecuta un ciclo completo del pipeline con el perfil activo."""
        log.info(f"\n{'#'*55}")
        log.info(f"ORCHESTRATOR — Nuevo ciclo: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        log.info(f"{'#'*55}")

        # Verificar límite diario de API
        from core.llm_client import get_llm_client
        llm       = get_llm_client()
        pro_today = llm.count_pro_calls_today()
        if pro_today >= 18:
            log.warning(f"Cerca del límite diario ({pro_today} calls). Saltando ciclo.")
            return

        # Cargar perfil activo (rotación automática o forzado)
        try:
            profile = get_active_profile(force_profile=self.force_profile)
        except Exception as e:
            log.error(f"Error cargando perfil: {e}")
            return

        log.info(
            f"Perfil: {profile['profile_name']} | "
            f"{profile['symbol']} {profile['timeframe']} | "
            f"{profile.get('description', '')}"
        )

        # Ejecutar pipeline con el perfil
        state = self.pipeline.run(profile=profile)

        # Log estadísticas
        self.db.print_stats()

    # ── Arrancar el sistema ───────────────────────────────────────────

    def start(self):
        """Arranca el sistema continuo con scheduler."""
        interval_hours = self.config.get("scheduler", {}).get("strategy_interval_hours", 12)

        log.info(f"\n{'='*55}")
        log.info("SISTEMA DE TRADING ALGORÍTMICO AUTÓNOMO")
        log.info(f"{'='*55}")
        log.info(f"Intervalo: cada {interval_hours} horas")
        log.info(f"Rotación de perfiles:")
        list_profiles()
        log.info(f"{'='*55}\n")

        # Primer ciclo inmediato
        self.run_cycle()

        # Ciclos periódicos
        self.scheduler.add_job(
            func    = self.run_cycle,
            trigger = IntervalTrigger(hours=interval_hours),
            id      = "trading_cycle",
        )

        log.info(f"\nSistema corriendo. Próximo ciclo en {interval_hours} horas.")
        log.info("Presionar Ctrl+C para detener.\n")

        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            log.info("\nSistema detenido.")

    def run_once(self):
        """Ejecuta exactamente un ciclo."""
        self.run_cycle()


if __name__ == "__main__":
    logging.basicConfig(
        level   = logging.INFO,
        format  = "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers = [
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(
                ROOT_DIR / "output" / "logs" / "sistema.log",
                encoding = "utf-8"
            ),
        ]
    )

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--once",    action="store_true")
    parser.add_argument("--stats",   action="store_true")
    parser.add_argument("--profile", type=str, default=None)
    args = parser.parse_args()

    orchestrator = OrchestratorAgent(force_profile=args.profile)

    if args.stats:
        orchestrator.db.print_stats()
    elif args.once:
        orchestrator.run_once()
    else:
        orchestrator.start()
