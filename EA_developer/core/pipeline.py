"""
core/pipeline.py
================
Pipeline principal que conecta todos los agentes.
Recibe un perfil (símbolo/timeframe/filtros) y lo propaga a cada agente.
"""

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "mql5_mcp_server"))

from core.database      import get_database
from core.memory        import get_memory
from core.config_loader import get_active_profile

log = logging.getLogger(__name__)


@dataclass
class PipelineState:
    """Estado compartido entre todos los agentes del pipeline."""
    cycle_id:       Optional[int]  = None
    profile:        dict           = field(default_factory=dict)
    strategy_type:  str            = "tendencia"
    research_idea:  Optional[dict] = None
    design:         Optional[dict] = None
    mq5_path:       Optional[Path] = None
    compile_ok:     bool           = False
    backtest_metrics: object       = None
    opt_result:     object         = None
    validation:     object         = None
    failed:         bool           = False
    fail_reason:    str            = ""
    phase:          str            = "start"


class TradingPipeline:
    def __init__(self):
        self.db     = get_database()
        self.memory = get_memory()
        self._agents_loaded = False

    def _load_agents(self, profile: dict):
        """Carga los agentes pasándoles el perfil activo."""
        from agents.researcher import ResearcherAgent
        from agents.designer   import DesignerAgent
        from agents.coder      import CoderAgent
        from agents.compiler   import get_compiler
        from agents.backtester import get_backtester
        from agents.optimizer  import OptimizerAgent
        from agents.validator  import ValidatorAgent

        self.researcher = ResearcherAgent()
        self.designer   = DesignerAgent()
        self.coder      = CoderAgent()
        self.compiler   = get_compiler()
        self.backtester = get_backtester()
        self.optimizer  = OptimizerAgent()
        self.validator  = ValidatorAgent(profile=profile)

        self._agents_loaded = True
        log.info("Todos los agentes cargados")

    # ── Método principal ──────────────────────────────────────────────

    def run(
        self,
        profile:        Optional[dict] = None,
        strategy_type:  Optional[str]  = None,
    ) -> PipelineState:
        """
        Ejecuta el pipeline completo.

        Args:
            profile:       Perfil de símbolo/timeframe/filtros.
                          Si None, carga el perfil activo del config.
            strategy_type: Tipo de estrategia. Si None, el Researcher elige.
        """
        # Cargar perfil si no se pasó
        if profile is None:
            profile = get_active_profile()

        # Recargar agentes con el perfil actual
        self._load_agents(profile)

        symbol     = profile.get("symbol", "EURUSD")
        timeframe  = profile.get("timeframe", "H4")
        chosen_type = strategy_type or "tendencia"

        # Crear ciclo en DB
        cycle_id = self.db.create_cycle(chosen_type, symbol)
        # Guardar también el timeframe
        self.db.update_cycle(cycle_id, timeframe=timeframe)

        state = PipelineState(
            cycle_id      = cycle_id,
            profile       = profile,
            strategy_type = chosen_type,
        )

        log.info(f"\n{'='*55}")
        log.info(f"CICLO #{cycle_id} — {symbol} {timeframe} — Tipo: {chosen_type}")
        log.info(f"{'='*55}")

        phases = [
            ("research",  self._run_research),
            ("design",    self._run_design),
            ("code",      self._run_code),
            ("compile",   self._run_compile),
            ("backtest",  self._run_backtest),
            ("optimize",  self._run_optimize),
            ("validate",  self._run_validate),
        ]

        for phase_name, phase_fn in phases:
            if state.failed:
                break
            state.phase = phase_name
            log.info(f"\n── Fase: {phase_name.upper()} ──")
            try:
                state = phase_fn(state)
            except Exception as e:
                log.error(f"Error en {phase_name}: {e}", exc_info=True)
                state.failed      = True
                state.fail_reason = f"Error en {phase_name}: {e}"
                self.db.update_cycle(cycle_id,
                    status        = "error",
                    current_phase = phase_name,
                    discard_reason = state.fail_reason,
                )

        if state.failed:
            log.info(f"\n❌ Ciclo #{cycle_id} falló: {state.fail_reason}")
        elif state.validation and state.validation.approved:
            log.info(f"\n🎉 Ciclo #{cycle_id} — APROBADA | Score: {state.validation.score:.0%}")
        else:
            reason = state.validation.fail_reason if state.validation else "desconocido"
            log.info(f"\n📊 Ciclo #{cycle_id} — Descartada: {reason}")

        return state

    # ── Fases ─────────────────────────────────────────────────────────

    def _run_research(self, state: PipelineState) -> PipelineState:
        idea = self.researcher.research(
            strategy_type = state.strategy_type,
            cycle_id      = state.cycle_id,
        )
        if not idea:
            state.failed     = True
            state.fail_reason = "Research no encontró ideas"
            return state
        state.research_idea = idea
        log.info(f"Idea: '{idea.get('titulo')}'")
        return state

    def _run_design(self, state: PipelineState) -> PipelineState:
        profile   = state.profile
        idea_text = (
            f"{state.research_idea.get('titulo', '')} — "
            f"{state.research_idea.get('descripcion', '')}"
        )
        # Enriquecer el prompt con el símbolo/timeframe del perfil
        idea_enriched = (
            f"{idea_text} "
            f"[Símbolo: {profile.get('symbol','EURUSD')}, "
            f"Timeframe: {profile.get('timeframe','H4')}]"
        )
        design = self.designer.design(
            idea          = idea_enriched,
            strategy_type = state.strategy_type,
            cycle_id      = state.cycle_id,
        )
        if not design:
            state.failed     = True
            state.fail_reason = "Designer no pudo generar el diseño"
            return state
        # Inyectar símbolo y timeframe del perfil en el diseño
        design["symbol"]    = profile.get("symbol", "EURUSD")
        design["timeframe"] = profile.get("timeframe", "H4")
        state.design = design
        log.info(f"Diseño: {design.get('nombre')} [{design['symbol']} {design['timeframe']}]")
        return state

    def _run_code(self, state: PipelineState) -> PipelineState:
        mq5_path = self.coder.generate(
            design   = state.design,
            cycle_id = state.cycle_id,
        )
        if not mq5_path or not mq5_path.exists():
            state.failed     = True
            state.fail_reason = "Coder no pudo generar código MQL5"
            return state
        state.mq5_path = mq5_path
        log.info(f"Código: {mq5_path.name} ({mq5_path.stat().st_size} bytes)")
        return state

    def _run_compile(self, state: PipelineState) -> PipelineState:
        result = self.compiler.compile(
            mq5_path = state.mq5_path,
            cycle_id = state.cycle_id,
        )
        if not result.success:
            state.failed     = True
            state.fail_reason = f"Compilación fallida tras {result.attempts} intentos"
            return state
        state.compile_ok = True
        log.info(f"Compilado en {result.attempts} intento(s)")
        return state

    def _run_backtest(self, state: PipelineState) -> PipelineState:
        profile = state.profile
        metrics = self.backtester.run(
            mq5_path  = state.mq5_path,
            profile   = profile,
            cycle_id  = state.cycle_id,
        )
        if not metrics.success:
            state.failed     = True
            state.fail_reason = f"Backtest falló: {metrics.error_message}"
            return state
        state.backtest_metrics = metrics
        log.info(f"Backtest: {metrics.summary()}")
        return state

    def _run_optimize(self, state: PipelineState) -> PipelineState:
        opt_result = self.optimizer.optimize(
            mq5_path = state.mq5_path,
            design   = state.design,
            profile  = state.profile,
            cycle_id = state.cycle_id,
        )
        if not opt_result.success:
            state.failed     = True
            state.fail_reason = f"Optimización falló: {opt_result.error_message}"
            return state
        state.opt_result = opt_result
        log.info(f"Optimización: {opt_result.summary()}")
        return state

    def _run_validate(self, state: PipelineState) -> PipelineState:
        validation = self.validator.validate(
            mq5_path   = state.mq5_path,
            design     = state.design,
            opt_result = state.opt_result,
            profile    = state.profile,
            cycle_id   = state.cycle_id,
        )
        state.validation = validation
        if validation.approved:
            log.info(f"✅ APROBADA — Score: {validation.score:.0%}")
        else:
            log.info(f"❌ Descartada — {validation.fail_reason}")
        return state
