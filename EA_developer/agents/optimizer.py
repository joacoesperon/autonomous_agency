"""
agents/optimizer.py
===================
Optimizer Agent — optimiza parámetros con Optuna y valida con walk-forward.

DISEÑO CORRECTO DE PERÍODOS:
─────────────────────────────────────────────────────────────
  Período total del perfil: ej. 2013-2024 (11 años)
  │
  ├── Training set:   2013 → (end - 2 años) = 2013-2022  [9 años]
  │   │
  │   ├── Optuna optimiza aquí (200 trials × backtest real de 9 años)
  │   │   Los mismos parámetros siempre dan el mismo resultado
  │   │   Optuna encuentra genuinamente los mejores parámetros
  │   │
  │   └── Walk-forward: 5 ventanas dentro de 2013-2022
  │       Cada ventana: 70% train / 30% test
  │       Verifica robustez temporal dentro del training set
  │
  └── Out-of-sample: (end - 2 años) → end = 2023-2024  [2 años]
      NUNCA se toca durante la optimización
      Prueba final con los parámetros óptimos
      Si falla aquí, la estrategia se descarta aunque sea buena en training

  Backtest final de validación: 2013-2024 completo
  (con los parámetros óptimos, para las métricas del reporte)
─────────────────────────────────────────────────────────────
"""

import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_database
from agents.backtester import BacktesterAgent, BacktestMetrics, get_backtester

log = logging.getLogger(__name__)

ROOT_DIR    = Path(__file__).parent.parent
CONFIG_PATH = ROOT_DIR / "config.yaml"

# Años reservados para out-of-sample (nunca tocar durante optimización)
OOS_YEARS = 2


# ─────────────────────────────────────────────
# ESTRUCTURAS
# ─────────────────────────────────────────────

@dataclass
class WalkForwardWindow:
    index:         int
    train_from:    str
    train_to:      str
    test_from:     str
    test_to:       str
    train_metrics: Optional[BacktestMetrics] = None
    test_metrics:  Optional[BacktestMetrics] = None

    def is_valid(self) -> bool:
        if not self.train_metrics or not self.test_metrics:
            return False
        return (
            self.train_metrics.success and
            self.test_metrics.success and
            self.test_metrics.profit_factor >= 1.0 and
            self.test_metrics.net_profit > 0
        )


@dataclass
class OptimizationResult:
    best_params:           dict                    = field(default_factory=dict)
    best_metrics:          Optional[BacktestMetrics] = None
    walk_forward_windows:  list[WalkForwardWindow] = field(default_factory=list)
    oos_metrics:           Optional[BacktestMetrics] = None
    full_period_metrics:   Optional[BacktestMetrics] = None  # 2013-2024 completo
    n_trials:              int   = 0
    optimization_time:     float = 0.0
    training_period:       str   = ""   # ej. "2013.01.01 → 2022.12.31"
    oos_period:            str   = ""   # ej. "2023.01.01 → 2024.12.31"
    passed_walkforward:    bool  = False
    passed_oos:            bool  = False
    overfitting_score:     float = 0.0
    success:               bool  = False
    error_message:         str   = ""

    def summary(self) -> str:
        if not self.success:
            return f"❌ Falló: {self.error_message}"
        wf_passed = sum(1 for w in self.walk_forward_windows if w.is_valid())
        wf_total  = len(self.walk_forward_windows)
        return (
            f"Trials: {self.n_trials} | "
            f"WF: {wf_passed}/{wf_total} ventanas | "
            f"OOS: {'✅' if self.passed_oos else '❌'} | "
            f"Overfitting: {self.overfitting_score:.0%}"
        )


# ─────────────────────────────────────────────
# OPTIMIZER AGENT
# ─────────────────────────────────────────────

class OptimizerAgent:

    def __init__(self):
        self.db         = get_database()
        self.backtester = get_backtester()
        self.config     = self._load_config()
        log.info("OptimizerAgent inicializado")

    def _load_config(self) -> dict:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {}

    # ── Método principal ──────────────────────────────────────────────

    def optimize(
        self,
        mq5_path:  Path,
        design:    dict,
        profile:   Optional[dict] = None,
        cycle_id:  Optional[int]  = None,
    ) -> OptimizationResult:
        """
        Optimiza parámetros y valida con walk-forward + out-of-sample.

        Separación de períodos:
        - Training (Optuna + walk-forward): desde backtest_start hasta (end - OOS_YEARS)
        - Out-of-sample: últimos OOS_YEARS años, nunca tocados durante optimización
        - Backtest final: período completo (para métricas del reporte)
        """
        import optuna
        optuna.logging.set_verbosity(optuna.logging.WARNING)

        ea_name  = mq5_path.stem
        opt_cfg  = self.config.get("optimizer", {})
        n_trials = opt_cfg.get("n_trials", 200)
        timeout  = opt_cfg.get("timeout_minutes", 30) * 60

        # ── Calcular períodos ──────────────────────────────────────────
        if profile:
            full_start = profile.get("backtest_start", "2013.01.01")
            full_end   = profile.get("backtest_end",   "2024.12.31")
        else:
            cfg        = self.config.get("trading", {})
            full_start = cfg.get("backtest_start", "2013.01.01")
            full_end   = cfg.get("backtest_end",   "2024.12.31")

        train_start, train_end, oos_start, oos_end = self._split_periods(full_start, full_end)

        log.info(f"\n[Optimizer] {ea_name}")
        log.info(f"  Período completo:  {full_start} → {full_end}")
        log.info(f"  Training:          {train_start} → {train_end}")
        log.info(f"  Out-of-sample:     {oos_start} → {oos_end}")
        log.info(f"  Trials Optuna:     {n_trials}")

        # Construir espacio de búsqueda
        param_space = self._build_param_space(design)
        if not param_space:
            return OptimizationResult(success=False, error_message="No hay parámetros para optimizar")

        start_time = time.time()

        # ── FASE 1: Optimización bayesiana sobre TRAINING SET ──────────
        log.info(f"[Optimizer] Fase 1: Optimización bayesiana ({n_trials} trials sobre {train_start}→{train_end})...")

        study = optuna.create_study(
            direction  = "maximize",
            sampler    = optuna.samplers.TPESampler(seed=42),
            study_name = ea_name,
        )

        def objective(trial: optuna.Trial) -> float:
            params = self._sample_params(trial, param_space)
            # CRUCIAL: solo usa el training set, nunca el OOS
            metrics = self.backtester.run(
                mq5_path,
                params    = params,
                profile   = profile,
                date_from = train_start,
                date_to   = train_end,
            )
            if not metrics.success or metrics.total_trades < 30:
                return 0.0
            # Score: Sharpe penalizado por drawdown alto
            return max(0.0, metrics.sharpe_ratio - (metrics.max_drawdown_pct / 100))

        study.optimize(objective, n_trials=n_trials, timeout=timeout, show_progress_bar=False)

        best_params   = study.best_params
        actual_trials = len(study.trials)
        best_score    = study.best_value

        log.info(f"[Optimizer] Optimización completada: {actual_trials} trials, mejor score: {best_score:.3f}")
        log.info(f"[Optimizer] Mejores params: {best_params}")

        # ── FASE 2: Backtest completo con mejores parámetros ──────────
        log.info(f"[Optimizer] Fase 2: Backtest período completo ({full_start}→{full_end})...")
        full_metrics = self.backtester.run(
            mq5_path,
            params    = best_params,
            profile   = profile,
            date_from = full_start,
            date_to   = full_end,
        )
        log.info(f"[Optimizer] Completo: {full_metrics.summary()}")

        # ── FASE 3: Walk-forward dentro del training set ───────────────
        log.info(f"[Optimizer] Fase 3: Walk-forward dentro de {train_start}→{train_end}...")
        wf_windows = self._run_walk_forward(
            mq5_path, best_params, profile, train_start, train_end
        )
        wf_passed = all(w.is_valid() for w in wf_windows)
        wf_count  = sum(1 for w in wf_windows if w.is_valid())
        log.info(f"[Optimizer] Walk-forward: {wf_count}/{len(wf_windows)} ventanas válidas")

        # ── FASE 4: Out-of-sample (nunca visto durante optimización) ───
        log.info(f"[Optimizer] Fase 4: Out-of-sample ({oos_start}→{oos_end})...")
        oos_metrics = self.backtester.run(
            mq5_path,
            params    = best_params,
            profile   = profile,
            date_from = oos_start,
            date_to   = oos_end,
        )
        oos_passed = (
            oos_metrics.success and
            oos_metrics.profit_factor >= 1.0 and
            oos_metrics.net_profit > 0
        )
        log.info(
            f"[Optimizer] OOS: {oos_metrics.summary()} | "
            f"{'✅ Pasó' if oos_passed else '❌ Falló'}"
        )

        # ── FASE 5: Score de overfitting ────────────────────────────────
        overfitting_score = self._calculate_overfitting_score(study, full_metrics, wf_windows)

        optimization_time = time.time() - start_time

        result = OptimizationResult(
            best_params          = best_params,
            best_metrics         = full_metrics,     # métricas del período completo
            walk_forward_windows = wf_windows,
            oos_metrics          = oos_metrics,
            full_period_metrics  = full_metrics,
            n_trials             = actual_trials,
            optimization_time    = optimization_time,
            training_period      = f"{train_start} → {train_end}",
            oos_period           = f"{oos_start} → {oos_end}",
            passed_walkforward   = wf_passed,
            passed_oos           = oos_passed,
            overfitting_score    = overfitting_score,
            success              = True,
        )

        log.info(f"[Optimizer] ✅ Completado en {optimization_time:.0f}s: {result.summary()}")

        if cycle_id and full_metrics.success:
            self.db.update_cycle(cycle_id,
                profit_factor    = full_metrics.profit_factor,
                sharpe_ratio     = full_metrics.sharpe_ratio,
                max_drawdown_pct = full_metrics.max_drawdown_pct,
                win_rate         = full_metrics.win_rate,
                total_trades     = full_metrics.total_trades,
                current_phase    = "validate",
            )

        return result

    # ── Separación de períodos ────────────────────────────────────────

    def _split_periods(
        self, full_start: str, full_end: str
    ) -> tuple[str, str, str, str]:
        """
        Divide el período completo en training y out-of-sample.

        Returns:
            (train_start, train_end, oos_start, oos_end)
        """
        try:
            dt_end = datetime.strptime(full_end, "%Y.%m.%d")
            # OOS = últimos OOS_YEARS años
            oos_start_dt  = dt_end.replace(year=dt_end.year - OOS_YEARS, month=1, day=1)
            train_end_dt  = oos_start_dt - timedelta(days=1)

            return (
                full_start,
                train_end_dt.strftime("%Y.%m.%d"),
                oos_start_dt.strftime("%Y.%m.%d"),
                full_end,
            )
        except Exception:
            # Fallback hardcoded si falla el parsing
            return ("2013.01.01", "2022.12.31", "2023.01.01", "2024.12.31")

    # ── Espacio de parámetros ─────────────────────────────────────────

    def _build_param_space(self, design: dict) -> dict:
        space = {}
        for param in design.get("parametros_externos", []):
            nombre  = param.get("nombre", "")
            tipo    = param.get("tipo", "int")
            default = param.get("default", 0)

            if not nombre:
                continue

            if tipo == "int":
                low  = max(1, int(default * 0.5))
                high = int(default * 2.0)
                if low >= high:
                    high = low + 10
                space[nombre] = {"tipo": "int", "low": low, "high": high}
            elif tipo in ("double", "float"):
                low  = max(0.1, float(default) * 0.5)
                high = float(default) * 2.0
                if low >= high:
                    high = low + 1.0
                space[nombre] = {"tipo": "float", "low": low, "high": high}

        log.info(f"[Optimizer] Espacio de búsqueda: {len(space)} parámetros")
        return space

    def _sample_params(self, trial, param_space: dict) -> dict:
        params = {}
        for nombre, spec in param_space.items():
            if spec["tipo"] == "int":
                params[nombre] = trial.suggest_int(nombre, spec["low"], spec["high"])
            else:
                params[nombre] = trial.suggest_float(nombre, spec["low"], spec["high"], step=0.5)
        return params

    # ── Walk-forward ──────────────────────────────────────────────────

    def _run_walk_forward(
        self,
        mq5_path:     Path,
        best_params:  dict,
        profile:      Optional[dict],
        period_start: str,
        period_end:   str,
        n_windows:    int = 5,
    ) -> list[WalkForwardWindow]:
        """
        Walk-forward dentro del training set (nunca toca el OOS).
        Divide period_start→period_end en n_windows ventanas.
        Cada ventana: 70% train / 30% test.
        """
        try:
            dt_start = datetime.strptime(period_start, "%Y.%m.%d")
            dt_end   = datetime.strptime(period_end,   "%Y.%m.%d")
        except Exception:
            dt_start = datetime(2013, 1, 1)
            dt_end   = datetime(2022, 12, 31)

        total_days  = (dt_end - dt_start).days
        window_days = total_days // n_windows
        train_pct   = 0.70
        windows     = []

        for i in range(n_windows):
            w_start = dt_start + timedelta(days=i * window_days)
            w_end   = w_start + timedelta(days=window_days - 1)
            if i == n_windows - 1:
                w_end = dt_end  # última ventana llega hasta el final

            train_end_dt = w_start + timedelta(days=int(window_days * train_pct))
            test_start_dt = train_end_dt + timedelta(days=1)

            wf_train_from = w_start.strftime("%Y.%m.%d")
            wf_train_to   = train_end_dt.strftime("%Y.%m.%d")
            wf_test_from  = test_start_dt.strftime("%Y.%m.%d")
            wf_test_to    = w_end.strftime("%Y.%m.%d")

            window = WalkForwardWindow(
                index      = i + 1,
                train_from = wf_train_from,
                train_to   = wf_train_to,
                test_from  = wf_test_from,
                test_to    = wf_test_to,
            )

            window.train_metrics = self.backtester.run(
                mq5_path, params=best_params, profile=profile,
                date_from=wf_train_from, date_to=wf_train_to,
            )
            window.test_metrics = self.backtester.run(
                mq5_path, params=best_params, profile=profile,
                date_from=wf_test_from, date_to=wf_test_to,
            )

            status = "✅" if window.is_valid() else "❌"
            pf_test = window.test_metrics.profit_factor if window.test_metrics else 0
            log.info(
                f"[Optimizer] WF ventana {i+1}/{n_windows}: "
                f"Train {wf_train_from}→{wf_train_to} | "
                f"Test {wf_test_from}→{wf_test_to} | "
                f"PF_test={pf_test:.2f} {status}"
            )
            windows.append(window)

        return windows

    # ── Anti-overfitting ──────────────────────────────────────────────

    def _calculate_overfitting_score(self, study, best_metrics, wf_windows) -> float:
        if not best_metrics or not best_metrics.success:
            return 1.0

        scores = []

        # Varianza entre ventanas WF
        test_pfs = [
            w.test_metrics.profit_factor
            for w in wf_windows
            if w.test_metrics and w.test_metrics.success
        ]
        if len(test_pfs) >= 2:
            import statistics
            mean = sum(test_pfs) / len(test_pfs)
            if mean > 0:
                variance = statistics.stdev(test_pfs) / mean
                scores.append(min(1.0, variance))

        # Degradación train→test
        degradations = []
        for w in wf_windows:
            if (w.train_metrics and w.test_metrics and
                    w.train_metrics.success and w.test_metrics.success and
                    w.train_metrics.profit_factor > 0):
                deg = (w.train_metrics.profit_factor - w.test_metrics.profit_factor) / w.train_metrics.profit_factor
                degradations.append(max(0, deg))

        if degradations:
            scores.append(min(1.0, sum(degradations) / len(degradations)))

        # Trades insuficientes
        if best_metrics.total_trades < 100:
            scores.append(0.8)
        elif best_metrics.total_trades < 200:
            scores.append(0.3)
        else:
            scores.append(0.0)

        return sum(scores) / len(scores) if scores else 0.0


# ─────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    mq5_path = Path("output/strategies/descartadas/EMA50_200_RSI_Test.mq5")
    if not mq5_path.exists():
        print("❌ Ejecutar agents/coder.py primero")
        import sys; sys.exit(1)

    design = {
        "nombre": "EMA50_200_RSI_Test",
        "parametros_externos": [
            {"nombre": "EMA_Rapida",  "tipo": "int",    "default": 50},
            {"nombre": "EMA_Lenta",   "tipo": "int",    "default": 200},
            {"nombre": "RSI_Periodo", "tipo": "int",    "default": 14},
            {"nombre": "RSI_Nivel",   "tipo": "double", "default": 50.0},
            {"nombre": "SL_Pips",     "tipo": "double", "default": 50.0},
            {"nombre": "TP_Pips",     "tipo": "double", "default": 150.0},
        ]
    }

    optimizer = OptimizerAgent()
    result    = optimizer.optimize(mq5_path, design)

    print(f"\n{'='*55}")
    print("RESULTADO")
    print(f"{'='*55}")
    print(f"  Training:       {result.training_period}")
    print(f"  Out-of-sample:  {result.oos_period}")
    print(f"  Trials:         {result.n_trials}")
    print(f"  Walk-forward:   {'✅' if result.passed_walkforward else '❌'}")
    print(f"  OOS:            {'✅' if result.passed_oos else '❌'}")
    print(f"  Overfitting:    {result.overfitting_score:.0%}")
    if result.best_metrics:
        print(f"\n  Métricas completas (2013-2024):")
        print(f"    {result.best_metrics.summary()}")
    if result.best_params:
        print(f"\n  Mejores parámetros:")
        for k, v in result.best_params.items():
            print(f"    {k}: {v}")
    print(f"{'='*55}")
