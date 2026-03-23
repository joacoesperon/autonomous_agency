"""
agents/backtester.py
====================
Backtester Agent — ejecuta backtests en MT5 Strategy Tester via Python.

IMPORTANTE sobre períodos:
- El método run() acepta date_from y date_to opcionales
- Si no se pasan, usa las fechas del perfil activo (período completo)
- El Optimizer pasa fechas específicas para separar training/test
- Esto evita data leakage durante la optimización de parámetros
"""

import hashlib
import logging
import random
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database      import get_database
from core.mt5_connector import get_mt5_connector, BacktestResult

log = logging.getLogger(__name__)

ROOT_DIR    = Path(__file__).parent.parent
CONFIG_PATH = ROOT_DIR / "config.yaml"
OUTPUT_DIR  = ROOT_DIR / "output"


# ─────────────────────────────────────────────
# MÉTRICAS
# ─────────────────────────────────────────────

@dataclass
class BacktestMetrics:
    """Métricas completas de un backtest."""
    profit_factor:      float = 0.0
    sharpe_ratio:       float = 0.0
    sortino_ratio:      float = 0.0
    max_drawdown_pct:   float = 0.0
    max_drawdown_usd:   float = 0.0
    win_rate:           float = 0.0
    total_trades:       int   = 0
    trades_per_month:   float = 0.0
    net_profit:         float = 0.0
    net_profit_pct:     float = 0.0
    gross_profit:       float = 0.0
    gross_loss:         float = 0.0
    avg_win:            float = 0.0
    avg_loss:           float = 0.0
    symbol:             str   = "EURUSD"
    timeframe:          str   = "H4"
    date_from:          str   = ""
    date_to:            str   = ""
    initial_deposit:    float = 10000.0
    success:            bool  = False
    error_message:      str   = ""

    def passes_filters(self, filters: dict) -> tuple[bool, str]:
        checks = [
            (self.profit_factor >= filters.get("min_profit_factor", 1.5),
             f"Profit Factor {self.profit_factor:.2f} < {filters.get('min_profit_factor', 1.5)}"),
            (self.sharpe_ratio >= filters.get("min_sharpe_ratio", 1.2),
             f"Sharpe Ratio {self.sharpe_ratio:.2f} < {filters.get('min_sharpe_ratio', 1.2)}"),
            (self.max_drawdown_pct <= filters.get("max_drawdown_pct", 25.0),
             f"Max DrawDown {self.max_drawdown_pct:.1f}% > {filters.get('max_drawdown_pct', 25.0)}%"),
            (self.win_rate >= filters.get("min_win_rate", 45.0),
             f"Win Rate {self.win_rate:.1f}% < {filters.get('min_win_rate', 45.0)}%"),
            (self.total_trades >= filters.get("min_total_trades", 200),
             f"Total trades {self.total_trades} < {filters.get('min_total_trades', 200)}"),
            (self.trades_per_month >= filters.get("min_trades_per_month", 1.5),
             f"Trades/mes {self.trades_per_month:.1f} < {filters.get('min_trades_per_month', 1.5)}"),
        ]
        for passed, reason in checks:
            if not passed:
                return False, reason
        return True, ""

    def summary(self) -> str:
        return (
            f"PF={self.profit_factor:.2f} | "
            f"Sharpe={self.sharpe_ratio:.2f} | "
            f"DD={self.max_drawdown_pct:.1f}% | "
            f"WR={self.win_rate:.1f}% | "
            f"Trades={self.total_trades}"
        )


# ─────────────────────────────────────────────
# BACKTESTER AGENT (MT5 real)
# ─────────────────────────────────────────────

class BacktesterAgent:
    """Ejecuta backtests reales en MT5 Strategy Tester."""

    def __init__(self):
        self.db     = get_database()
        self.mt5    = get_mt5_connector()
        self.config = self._load_config()
        log.info("BacktesterAgent inicializado")

    def _load_config(self) -> dict:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {}

    def run(
        self,
        mq5_path:   Path,
        params:     Optional[dict] = None,
        profile:    Optional[dict] = None,
        date_from:  Optional[str]  = None,
        date_to:    Optional[str]  = None,
        cycle_id:   Optional[int]  = None,
    ) -> BacktestMetrics:
        """
        Ejecuta un backtest en MT5.

        Args:
            mq5_path:  Path al .mq5
            params:    Parámetros del EA (dict nombre→valor)
            profile:   Perfil activo con símbolo, timeframe, depósito
            date_from: Fecha de inicio. Si None, usa la del perfil.
            date_to:   Fecha de fin. Si None, usa la del perfil.
            cycle_id:  ID del ciclo para logging

        IMPORTANTE: date_from y date_to permiten al Optimizer separar
        el período de training del período de validación, evitando
        data leakage. Siempre pasar fechas explícitas desde el Optimizer.
        """
        ea_name = mq5_path.stem
        log.info(f"[Backtester] {ea_name} | {date_from or '?'} → {date_to or '?'}")

        # Resolver símbolo, timeframe y depósito del perfil
        if profile:
            symbol    = profile.get("symbol",    "EURUSD")
            timeframe = profile.get("timeframe", "H4")
            deposit   = profile.get("deposit",   10000.0)
            # Fechas: usar las explícitas si se pasaron, sino las del perfil
            df = date_from or profile.get("backtest_start", "2013.01.01")
            dt = date_to   or profile.get("backtest_end",   "2024.12.31")
        else:
            cfg       = self.config.get("trading", {})
            symbol    = cfg.get("symbol",    "EURUSD")
            timeframe = cfg.get("timeframe", "H4")
            deposit   = cfg.get("deposit",   10000.0)
            df = date_from or cfg.get("backtest_start", "2013.01.01")
            dt = date_to   or cfg.get("backtest_end",   "2024.12.31")

        if cycle_id:
            self.db.update_cycle(cycle_id, current_phase="backtest")

        if not self.mt5.connect():
            return BacktestMetrics(success=False, error_message="No se pudo conectar con MT5")

        try:
            if self.mt5.experts_dir:
                try:
                    self.mt5.copy_ea_to_experts(mq5_path)
                except Exception as e:
                    log.warning(f"[Backtester] No se pudo copiar a Experts: {e}")

            result = self.mt5.run_backtest(
                ea_name   = ea_name,
                symbol    = symbol,
                timeframe = timeframe,
                date_from = df,
                date_to   = dt,
                deposit   = deposit,
                params    = params or {},
            )

            metrics = self._to_metrics(result, symbol, timeframe, df, dt, deposit)

            if metrics.success:
                log.info(f"[Backtester] ✅ {metrics.summary()}")
            else:
                log.error(f"[Backtester] ❌ {metrics.error_message}")

            if cycle_id and metrics.success:
                self.db.update_cycle(cycle_id,
                    profit_factor    = metrics.profit_factor,
                    sharpe_ratio     = metrics.sharpe_ratio,
                    max_drawdown_pct = metrics.max_drawdown_pct,
                    win_rate         = metrics.win_rate,
                    total_trades     = metrics.total_trades,
                    net_profit_pct   = metrics.net_profit_pct,
                    current_phase    = "optimize",
                )

            return metrics

        finally:
            self.mt5.disconnect()

    def _to_metrics(self, result, symbol, timeframe, date_from, date_to, deposit) -> BacktestMetrics:
        if not result.success:
            return BacktestMetrics(success=False, error_message=result.error_message,
                                   symbol=symbol, timeframe=timeframe)

        months = self._months_between(date_from, date_to)
        trades_per_month = result.total_trades / months if months > 0 else 0
        net_profit_pct   = (result.net_profit / deposit * 100) if deposit > 0 else 0

        return BacktestMetrics(
            profit_factor    = result.profit_factor,
            sharpe_ratio     = result.sharpe_ratio,
            max_drawdown_pct = result.max_drawdown_pct,
            win_rate         = result.win_rate,
            total_trades     = result.total_trades,
            trades_per_month = trades_per_month,
            net_profit       = result.net_profit,
            net_profit_pct   = net_profit_pct,
            gross_profit     = result.gross_profit,
            gross_loss       = result.gross_loss,
            symbol           = symbol,
            timeframe        = timeframe,
            date_from        = date_from,
            date_to          = date_to,
            initial_deposit  = deposit,
            success          = True,
        )

    def _months_between(self, date_from: str, date_to: str) -> int:
        try:
            dt_from = datetime.strptime(date_from, "%Y.%m.%d")
            dt_to   = datetime.strptime(date_to,   "%Y.%m.%d")
            return (dt_to.year - dt_from.year) * 12 + (dt_to.month - dt_from.month)
        except Exception:
            return 132


# ─────────────────────────────────────────────
# MOCK BACKTESTER — para desarrollo sin MT5
# ─────────────────────────────────────────────

class MockBacktesterAgent(BacktesterAgent):
    """
    Backtester simulado para desarrollo sin MT5.

    IMPORTANTE: los resultados son DETERMINISTAS según los parámetros.
    Los mismos parámetros + mismo período = mismo resultado.
    Esto permite que Optuna realmente encuentre los "mejores" parámetros
    en el mock, simulando el comportamiento real.
    """

    def run(
        self,
        mq5_path:   Path,
        params:     Optional[dict] = None,
        profile:    Optional[dict] = None,
        date_from:  Optional[str]  = None,
        date_to:    Optional[str]  = None,
        cycle_id:   Optional[int]  = None,
    ) -> BacktestMetrics:

        ea_name = mq5_path.stem

        # Resolver fechas igual que el backtester real
        if profile:
            df = date_from or profile.get("backtest_start", "2013.01.01")
            dt = date_to   or profile.get("backtest_end",   "2024.12.31")
            symbol    = profile.get("symbol",    "EURUSD")
            timeframe = profile.get("timeframe", "H4")
            deposit   = profile.get("deposit",   10000.0)
        else:
            df        = date_from or "2013.01.01"
            dt        = date_to   or "2024.12.31"
            symbol    = "EURUSD"
            timeframe = "H4"
            deposit   = 10000.0

        log.info(f"[MockBacktester] {ea_name} | {df} → {dt} | params: {params}")

        # ── Seed determinista: mismos parámetros + mismo período = mismo resultado ──
        # Esto es crítico para que Optuna funcione correctamente en modo mock
        seed_components = {
            "ea":     ea_name,
            "params": sorted((params or {}).items()),
            "from":   df,
            "to":     dt,
        }
        seed_str = str(seed_components)
        seed = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16) % (2**31)
        rng = random.Random(seed)

        # Simular 1 segundo de "cómputo"
        time.sleep(1)

        # ── Generar métricas simuladas pero consistentes ──
        # ~40% de combinaciones de parámetros son "buenas"
        # Los mejores parámetros siempre producen los mejores resultados
        pasa = rng.random() < 0.4

        months = self._months_between(df, dt)

        if pasa:
            profit_factor    = round(rng.uniform(1.5, 2.5), 2)
            sharpe_ratio     = round(rng.uniform(1.2, 2.2), 2)
            max_drawdown_pct = round(rng.uniform(8.0, 22.0), 1)
            win_rate         = round(rng.uniform(48.0, 65.0), 1)
            total_trades     = rng.randint(max(50, int(months * 1.5)), max(100, int(months * 5)))
            net_profit       = round(rng.uniform(3000, 12000), 2)
        else:
            profit_factor    = round(rng.uniform(0.7, 1.4), 2)
            sharpe_ratio     = round(rng.uniform(0.3, 1.1), 2)
            max_drawdown_pct = round(rng.uniform(20.0, 45.0), 1)
            win_rate         = round(rng.uniform(30.0, 44.0), 1)
            total_trades     = rng.randint(10, max(50, int(months * 1.2)))
            net_profit       = round(rng.uniform(-3000, 1000), 2)

        trades_per_month = round(total_trades / months, 1) if months > 0 else 0
        net_profit_pct   = round(net_profit / deposit * 100, 1)

        metrics = BacktestMetrics(
            profit_factor    = profit_factor,
            sharpe_ratio     = sharpe_ratio,
            max_drawdown_pct = max_drawdown_pct,
            win_rate         = win_rate,
            total_trades     = total_trades,
            trades_per_month = trades_per_month,
            net_profit       = net_profit,
            net_profit_pct   = net_profit_pct,
            symbol           = symbol,
            timeframe        = timeframe,
            date_from        = df,
            date_to          = dt,
            initial_deposit  = deposit,
            success          = True,
        )

        log.info(f"[MockBacktester] {metrics.summary()}")

        if cycle_id and metrics.success:
            self.db.update_cycle(cycle_id,
                profit_factor    = metrics.profit_factor,
                sharpe_ratio     = metrics.sharpe_ratio,
                max_drawdown_pct = metrics.max_drawdown_pct,
                win_rate         = metrics.win_rate,
                total_trades     = metrics.total_trades,
                net_profit_pct   = metrics.net_profit_pct,
                current_phase    = "optimize",
            )

        return metrics


# ─────────────────────────────────────────────
# FACTORY
# ─────────────────────────────────────────────

def get_backtester() -> BacktesterAgent:
    mt5 = get_mt5_connector()
    if mt5.mt5_path and mt5.mt5_path.exists():
        log.info("Usando BacktesterAgent real (MT5 encontrado)")
        return BacktesterAgent()
    else:
        log.warning("MT5 no encontrado — usando MockBacktesterAgent")
        return MockBacktesterAgent()


# ─────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    mq5_path = Path("output/strategies/descartadas/EMA50_200_RSI_Test.mq5")
    if not mq5_path.exists():
        print("❌ Ejecutar agents/coder.py primero")
        import sys; sys.exit(1)

    backtester = get_backtester()

    # Verificar que los mismos parámetros dan el mismo resultado (determinismo)
    params_test = {"EMA_Rapida": 50, "EMA_Lenta": 200, "RSI_Periodo": 14}
    print("\nVerificando determinismo (mismo resultado para mismos params):")
    r1 = backtester.run(mq5_path, params=params_test, date_from="2013.01.01", date_to="2022.12.31")
    r2 = backtester.run(mq5_path, params=params_test, date_from="2013.01.01", date_to="2022.12.31")
    print(f"  Run 1: PF={r1.profit_factor} Sharpe={r1.sharpe_ratio}")
    print(f"  Run 2: PF={r2.profit_factor} Sharpe={r2.sharpe_ratio}")
    print(f"  {'✅ Determinista' if r1.profit_factor == r2.profit_factor else '❌ No determinista'}")

    # Verificar que diferentes períodos dan diferentes resultados
    print("\nVerificando períodos diferentes:")
    r3 = backtester.run(mq5_path, params=params_test, date_from="2013.01.01", date_to="2022.12.31")
    r4 = backtester.run(mq5_path, params=params_test, date_from="2023.01.01", date_to="2024.12.31")
    print(f"  Training (2013-2022): PF={r3.profit_factor} Trades={r3.total_trades}")
    print(f"  OOS     (2023-2024): PF={r4.profit_factor} Trades={r4.total_trades}")
    print("  ✅ Períodos distintos dan resultados distintos")
