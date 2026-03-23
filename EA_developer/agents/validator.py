"""
agents/validator.py
===================
Validator Agent — aplica filtros de calidad y genera el reporte final.

Flujo:
1. Recibe métricas del Optimizer
2. Aplica filtros de calidad del config.yaml
3. Si pasa → pide al LLM una evaluación cualitativa
4. Genera reporte de texto (.txt) con métricas completas
5. Mueve el .mq5 a output/strategies/aprobadas/
6. Actualiza la DB como aprobada
"""

import json
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.llm_client import get_llm_client
from core.database   import get_database
from agents.backtester  import BacktestMetrics
from agents.optimizer   import OptimizationResult

log = logging.getLogger(__name__)

ROOT_DIR    = Path(__file__).parent.parent
CONFIG_PATH = ROOT_DIR / "config.yaml"
PROMPTS_DIR = ROOT_DIR / "prompts"
OUTPUT_DIR  = ROOT_DIR / "output" / "strategies"


# ─────────────────────────────────────────────
# RESULTADO DE VALIDACIÓN
# ─────────────────────────────────────────────

class ValidationResult:
    def __init__(
        self,
        approved:       bool,
        strategy_name:  str          = "",
        score:          float        = 0.0,
        report_path:    Optional[Path] = None,
        mq5_final_path: Optional[Path] = None,
        llm_analysis:   dict         = None,
        fail_reason:    str          = "",
    ):
        self.approved       = approved
        self.strategy_name  = strategy_name
        self.score          = score
        self.report_path    = report_path
        self.mq5_final_path = mq5_final_path
        self.llm_analysis   = llm_analysis or {}
        self.fail_reason    = fail_reason


# ─────────────────────────────────────────────
# VALIDATOR AGENT
# ─────────────────────────────────────────────

class ValidatorAgent:
    """
    Valida estrategias y genera reportes para las aprobadas.
    """

    def __init__(self, profile: Optional[dict] = None):
        self.llm     = get_llm_client()
        self.db      = get_database()
        self.config  = self._load_config()
        self.profile = profile or self._load_active_profile()
        self._system_prompt = self._build_system_prompt()
        log.info("ValidatorAgent inicializado")

    def _load_config(self) -> dict:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {}

    def _load_active_profile(self) -> dict:
        """Carga el perfil activo desde el config_loader."""
        try:
            from core.config_loader import get_active_profile
            return get_active_profile()
        except Exception:
            # Fallback al primer perfil disponible
            profiles = self.config.get("profiles", {})
            if profiles:
                name = list(profiles.keys())[0]
                p = profiles[name].copy()
                p["profile_name"] = name
                return p
            return {"symbol": "EURUSD", "timeframe": "H4", "quality_filters": {}}

    def _build_system_prompt(self) -> str:
        """Genera el system prompt dinámico según el perfil activo."""
        try:
            from core.config_loader import get_validator_system_prompt
            return get_validator_system_prompt(self.profile)
        except Exception:
            # Fallback al archivo estático
            path = PROMPTS_DIR / "validator_system.txt"
            if path.exists():
                return path.read_text(encoding="utf-8")
            raise FileNotFoundError(f"No se encontró validator_system.txt")

    # ── Método principal ──────────────────────────────────────────────

    def validate(
        self,
        mq5_path:    Path,
        design:      dict,
        opt_result:  OptimizationResult,
        profile:     Optional[dict] = None,
        cycle_id:    Optional[int] = None,
    ) -> ValidationResult:
        """
        Valida una estrategia y genera el reporte si es aprobada.

        Args:
            mq5_path:   Path al archivo .mq5
            design:     Diseño de la estrategia
            opt_result: Resultado de la optimización
            cycle_id:   ID del ciclo para logging

        Returns:
            ValidationResult con el veredicto y paths de los archivos finales
        """
        strategy_name = design.get("nombre", mq5_path.stem)
        log.info(f"[Validator] Validando: {strategy_name}")

        metrics  = opt_result.best_metrics
        active_profile = profile or self.profile
        filters  = active_profile.get("quality_filters", self.config.get("quality_filters", {}))

        # ── PASO 1: Filtros cuantitativos duros ──
        if not metrics or not metrics.success:
            return self._reject(cycle_id, strategy_name, "Métricas de backtest no disponibles")

        passed, fail_reason = metrics.passes_filters(filters)
        if not passed:
            log.info(f"[Validator] ❌ Rechazada: {fail_reason}")
            return self._reject(cycle_id, strategy_name, fail_reason)

        # ── PASO 2: Filtro walk-forward ──
        wf_passed = sum(1 for w in opt_result.walk_forward_windows if w.is_valid())
        wf_total  = len(opt_result.walk_forward_windows)
        wf_min    = self.config.get("optimizer", {}).get("walk_forward_windows", 5)
        wf_required = max(1, wf_min - 1)   # al menos N-1 ventanas deben pasar

        if wf_passed < wf_required:
            reason = f"Walk-forward insuficiente: {wf_passed}/{wf_total} ventanas (mínimo {wf_required})"
            log.info(f"[Validator] ❌ Rechazada: {reason}")
            return self._reject(cycle_id, strategy_name, reason)

        # ── PASO 3: Filtro overfitting ──
        if opt_result.overfitting_score > 0.5:
            reason = f"Riesgo de overfitting alto: {opt_result.overfitting_score:.0%}"
            log.info(f"[Validator] ❌ Rechazada: {reason}")
            return self._reject(cycle_id, strategy_name, reason)

        # ── PASO 4: Análisis cualitativo con LLM ──
        log.info("[Validator] Solicitando análisis cualitativo al LLM...")
        llm_analysis = self._get_llm_analysis(design, metrics, opt_result)

        # Si el LLM también rechaza, considerar su opinión
        if llm_analysis and not llm_analysis.get("aprobada", True):
            score = llm_analysis.get("score_general", 0)
            if score < 0.5:
                reason = f"Rechazada por análisis LLM: {llm_analysis.get('recomendacion', '')[:100]}"
                log.info(f"[Validator] ❌ {reason}")
                return self._reject(cycle_id, strategy_name, reason)

        # ── PASO 5: Generar reporte ──
        log.info("[Validator] ✅ Estrategia aprobada — generando reporte...")

        report_path    = self._generate_report(strategy_name, design, metrics, opt_result, llm_analysis)
        mq5_final_path = self._move_to_approved(mq5_path, strategy_name)

        # Calcular score final
        score = self._calculate_score(metrics, opt_result, llm_analysis)

        # Actualizar DB
        if cycle_id:
            self.db.update_cycle(cycle_id,
                status        = "completado",
                approved      = 1,
                current_phase = "completado",
                output_path   = str(mq5_final_path),
                notes         = llm_analysis.get("recomendacion", "")[:500],
            )

        log.info(f"[Validator] 🎉 Aprobada: {strategy_name} (score: {score:.0%})")
        log.info(f"[Validator] Reporte: {report_path}")
        log.info(f"[Validator] EA:      {mq5_final_path}")

        return ValidationResult(
            approved       = True,
            strategy_name  = strategy_name,
            score          = score,
            report_path    = report_path,
            mq5_final_path = mq5_final_path,
            llm_analysis   = llm_analysis,
        )

    # ── Análisis LLM ──────────────────────────────────────────────────

    def _get_llm_analysis(
        self,
        design:     dict,
        metrics:    BacktestMetrics,
        opt_result: OptimizationResult,
    ) -> dict:
        """Pide al LLM una evaluación cualitativa de la estrategia."""

        wf_summary = []
        for w in opt_result.walk_forward_windows:
            if w.test_metrics:
                wf_summary.append({
                    "ventana":  f"{w.train_from}→{w.test_to}",
                    "pf":       w.test_metrics.profit_factor,
                    "valida":   w.is_valid(),
                })

        prompt = f"""Analiza esta estrategia de trading algorítmico y dame tu evaluación.

DISEÑO DE LA ESTRATEGIA:
{json.dumps(design, ensure_ascii=False, indent=2)}

MÉTRICAS DEL BACKTEST (2013-2024):
- Profit Factor:    {metrics.profit_factor:.2f}
- Sharpe Ratio:     {metrics.sharpe_ratio:.2f}
- Max DrawDown:     {metrics.max_drawdown_pct:.1f}%
- Win Rate:         {metrics.win_rate:.1f}%
- Total Trades:     {metrics.total_trades}
- Trades/mes:       {metrics.trades_per_month:.1f}
- Net Profit:       ${metrics.net_profit:,.2f} ({metrics.net_profit_pct:.1f}%)

WALK-FORWARD:
{json.dumps(wf_summary, ensure_ascii=False, indent=2)}

OVERFITTING SCORE: {opt_result.overfitting_score:.0%}

MEJORES PARÁMETROS:
{json.dumps(opt_result.best_params, ensure_ascii=False, indent=2)}

Evalúa la estrategia y responde con el JSON de evaluación.
"""
        try:
            raw = self.llm.flash(prompt=prompt, system=self._system_prompt)

            import re
            for pattern in [r"```json\s*\n(.*?)```", r"```\s*\n(.*?)```"]:
                match = re.search(pattern, raw, re.DOTALL)
                if match:
                    raw = match.group(1)
                    break

            start = raw.find("{")
            end   = raw.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(raw[start:end])

        except Exception as e:
            log.warning(f"[Validator] LLM analysis falló: {e}")

        return {"aprobada": True, "score_general": 0.7, "recomendacion": "Aprobada por métricas cuantitativas"}

    # ── Generar reporte ───────────────────────────────────────────────

    def _generate_report(
        self,
        name:        str,
        design:      dict,
        metrics:     BacktestMetrics,
        opt_result:  OptimizationResult,
        llm_analysis: dict,
    ) -> Path:
        """Genera un reporte de texto con todas las métricas y el análisis."""

        report_dir = OUTPUT_DIR / "aprobadas" / name
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"{name}_reporte.txt"

        wf_lines = []
        for w in opt_result.walk_forward_windows:
            pf     = w.test_metrics.profit_factor if w.test_metrics else 0
            status = "✅" if w.is_valid() else "❌"
            wf_lines.append(f"  Ventana {w.index}: {w.train_from} → {w.test_to} | PF={pf:.2f} {status}")

        params_lines = "\n".join(
            f"  {k}: {v}"
            for k, v in opt_result.best_params.items()
        )

        fortalezas = "\n".join(
            f"  + {f}" for f in llm_analysis.get("fortalezas", [])
        )
        debilidades = "\n".join(
            f"  - {d}" for d in llm_analysis.get("debilidades", [])
        )
        alertas = "\n".join(
            f"  ⚠ {a}" for a in llm_analysis.get("alertas", [])
        )

        report = f"""
{'='*60}
ESTRATEGIA APROBADA: {name}
Generada el: {datetime.now().strftime('%Y-%m-%d %H:%M')}
{'='*60}

DESCRIPCIÓN
-----------
{design.get('descripcion', '')}
Tipo: {design.get('tipo', '')}

EXPLICACIÓN DE LA LÓGICA
------------------------
{llm_analysis.get('explicacion_estrategia', '')}

MÉTRICAS (EURUSD H4 | 2013-2024)
---------------------------------
  Profit Factor:   {metrics.profit_factor:.2f}
  Sharpe Ratio:    {metrics.sharpe_ratio:.2f}
  Max DrawDown:    {metrics.max_drawdown_pct:.1f}%
  Win Rate:        {metrics.win_rate:.1f}%
  Total Trades:    {metrics.total_trades}
  Trades/mes:      {metrics.trades_per_month:.1f}
  Net Profit:      ${metrics.net_profit:,.2f} ({metrics.net_profit_pct:.1f}%)

WALK-FORWARD VALIDATION
-----------------------
{chr(10).join(wf_lines)}

  Overfitting score: {opt_result.overfitting_score:.0%}

PARÁMETROS ÓPTIMOS
------------------
{params_lines}

ANÁLISIS CUALITATIVO
--------------------
Score general: {llm_analysis.get('score_general', 0):.0%}

Fortalezas:
{fortalezas or '  (ninguna especificada)'}

Debilidades:
{debilidades or '  (ninguna especificada)'}

Alertas:
{alertas or '  (ninguna)'}

RECOMENDACIÓN
-------------
{llm_analysis.get('recomendacion', '')}

NOTAS PARA TRADING REAL
-----------------------
{llm_analysis.get('notas_para_trading', '')}

{'='*60}
INSTRUCCIONES DE USO
{'='*60}
1. Copiar {name}.mq5 a: MetaTrader 5/MQL5/Experts/
2. Abrir MetaEditor (F4) y compilar el archivo
3. En MT5: arrastrar el EA a un gráfico EURUSD H4
4. Verificar que AutoTrading está activado
5. Usar los parámetros óptimos indicados arriba
6. Comenzar con cuenta demo antes de cuenta real
{'='*60}
"""

        report_path.write_text(report.strip(), encoding="utf-8")
        log.info(f"[Validator] Reporte guardado: {report_path}")
        return report_path

    # ── Mover EA a aprobadas ──────────────────────────────────────────

    def _move_to_approved(self, mq5_path: Path, name: str) -> Path:
        """Mueve el .mq5 al directorio de estrategias aprobadas."""
        dest_dir = OUTPUT_DIR / "aprobadas" / name
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / mq5_path.name

        shutil.copy2(mq5_path, dest)
        log.info(f"[Validator] EA copiado a: {dest}")
        return dest

    # ── Score final ───────────────────────────────────────────────────

    def _calculate_score(
        self,
        metrics:     BacktestMetrics,
        opt_result:  OptimizationResult,
        llm_analysis: dict,
    ) -> float:
        """Calcula un score final de 0 a 1 para la estrategia."""
        scores = []

        # Profit Factor (máx 2.5 esperado)
        scores.append(min(1.0, (metrics.profit_factor - 1.0) / 1.5))

        # Sharpe Ratio (máx 2.5 esperado)
        scores.append(min(1.0, metrics.sharpe_ratio / 2.5))

        # DrawDown inverso
        scores.append(max(0.0, 1.0 - metrics.max_drawdown_pct / 25.0))

        # Walk-forward ratio
        wf_passed = sum(1 for w in opt_result.walk_forward_windows if w.is_valid())
        wf_total  = max(1, len(opt_result.walk_forward_windows))
        scores.append(wf_passed / wf_total)

        # Anti-overfitting
        scores.append(1.0 - opt_result.overfitting_score)

        # LLM score
        scores.append(llm_analysis.get("score_general", 0.7))

        return sum(scores) / len(scores)

    # ── Rechazar ──────────────────────────────────────────────────────

    def _reject(
        self,
        cycle_id: Optional[int],
        name:     str,
        reason:   str,
    ) -> ValidationResult:
        """Registra el rechazo en la DB y retorna resultado negativo."""
        if cycle_id:
            self.db.update_cycle(cycle_id,
                status        = "descartado",
                approved      = 0,
                current_phase = "descartado",
                discard_reason = reason,
            )
        return ValidationResult(
            approved    = False,
            strategy_name = name,
            fail_reason = reason,
        )


# ─────────────────────────────────────────────
# TEST RÁPIDO
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\nProbando ValidatorAgent...\n")

    mq5_path = Path("output/strategies/descartadas/EMA50_200_RSI_Test.mq5")
    if not mq5_path.exists():
        print("❌ No se encontró EMA50_200_RSI_Test.mq5 — ejecutar agents/coder.py primero")
        sys.exit(1)

    # Crear métricas y resultado de optimización simulados que pasan los filtros
    from agents.backtester import BacktestMetrics
    from agents.optimizer  import OptimizationResult, WalkForwardWindow

    metrics = BacktestMetrics(
        profit_factor    = 1.87,
        sharpe_ratio     = 1.64,
        sortino_ratio    = 2.10,
        max_drawdown_pct = 14.3,
        win_rate         = 54.2,
        total_trades     = 412,
        trades_per_month = 3.1,
        net_profit       = 9850.0,
        net_profit_pct   = 98.5,
        symbol           = "EURUSD",
        timeframe        = "H4",
        date_from        = "2013.01.01",
        date_to          = "2024.12.31",
        initial_deposit  = 10000.0,
        success          = True,
    )

    # Ventanas walk-forward que pasan
    wf_windows = []
    for i in range(1, 6):
        w = WalkForwardWindow(
            index      = i,
            train_from = f"201{i}.01.01",
            train_to   = f"201{i}.12.31",
            test_from  = f"201{i+1}.01.01",
            test_to    = f"201{i+1}.12.31",
        )
        w.train_metrics = BacktestMetrics(profit_factor=1.9, net_profit=1000, success=True)
        w.test_metrics  = BacktestMetrics(profit_factor=1.6, net_profit=500,  success=True)
        wf_windows.append(w)

    opt_result = OptimizationResult(
        best_params          = {"EMA_Rapida": 50, "EMA_Lenta": 200, "RSI_Periodo": 14},
        best_metrics         = metrics,
        walk_forward_windows = wf_windows,
        n_trials             = 200,
        optimization_time    = 215.0,
        passed_walkforward   = True,
        passed_oos           = True,
        overfitting_score    = 0.15,
        success              = True,
    )

    design = {
        "nombre":      "EMA50_200_RSI_Test",
        "tipo":        "tendencia",
        "descripcion": "Cruce EMA 50/200 con filtro RSI en H4",
        "indicadores": [{"tipo": "EMA"}, {"tipo": "RSI"}],
    }

    validator = ValidatorAgent()
    result    = validator.validate(mq5_path, design, opt_result)

    print(f"\n{'='*50}")
    print("RESULTADO DE VALIDACIÓN")
    print(f"{'='*50}")
    print(f"  Aprobada:   {result.approved}")
    print(f"  Score:      {result.score:.0%}")

    if result.approved:
        print(f"  EA:         {result.mq5_final_path}")
        print(f"  Reporte:    {result.report_path}")
        if result.llm_analysis:
            print(f"\n  Análisis LLM:")
            print(f"    Score:   {result.llm_analysis.get('score_general', 0):.0%}")
            print(f"    Veredicto: {result.llm_analysis.get('recomendacion', '')[:80]}...")
        print("\n✅ ValidatorAgent funcionando correctamente")
    else:
        print(f"  Motivo rechazo: {result.fail_reason}")
