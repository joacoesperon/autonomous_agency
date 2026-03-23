"""
core/database.py
================
Base de datos SQLite para registrar el estado de cada ciclo del sistema.
Guarda qué estrategias se generaron, sus métricas, y el historial completo.

Uso:
    from core.database import Database
    db = Database()
    db.save_cycle(ciclo)
    db.get_approved_strategies()
"""

import json
import logging
import sqlite3
from datetime import datetime, date
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

log = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "output" / "sistema.db"


# ─────────────────────────────────────────────
# ESTRUCTURAS DE DATOS
# ─────────────────────────────────────────────

@dataclass
class CycleRecord:
    """Registro de un ciclo completo del pipeline."""
    id:               Optional[int]  = None
    timestamp:        str            = ""
    strategy_name:    str            = ""
    strategy_type:    str            = ""      # tendencia, reversión, momentum
    symbol:           str            = "EURUSD"
    timeframe:        str            = "H4"

    # Estado del ciclo
    status:           str            = "en_proceso"  # en_proceso|completado|descartado|error
    current_phase:    str            = "research"    # research|design|code|compile|backtest|optimize|validate

    # Métricas del backtest (si llegó a esa fase)
    profit_factor:    float          = 0.0
    sharpe_ratio:     float          = 0.0
    max_drawdown_pct: float          = 0.0
    win_rate:         float          = 0.0
    total_trades:     int            = 0
    net_profit_pct:   float          = 0.0

    # Resultado
    approved:         bool           = False
    discard_reason:   str            = ""
    output_path:      str            = ""      # path al .mq5 aprobado

    # Self-healing
    compile_attempts: int            = 0

    # LLM calls
    flash_calls:      int            = 0
    pro_calls:        int            = 0

    # Metadata
    design_json:      str            = ""      # JSON del diseño de la estrategia
    notes:            str            = ""


# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────

class Database:
    """Gestiona la base de datos SQLite del sistema."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        log.info(f"Database inicializada: {self.db_path}")

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Crea las tablas si no existen."""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS cycles (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp        TEXT    NOT NULL,
                    strategy_name    TEXT    DEFAULT '',
                    strategy_type    TEXT    DEFAULT '',
                    symbol           TEXT    DEFAULT 'EURUSD',
                    timeframe        TEXT    DEFAULT 'H4',
                    status           TEXT    DEFAULT 'en_proceso',
                    current_phase    TEXT    DEFAULT 'research',
                    profit_factor    REAL    DEFAULT 0.0,
                    sharpe_ratio     REAL    DEFAULT 0.0,
                    max_drawdown_pct REAL    DEFAULT 0.0,
                    win_rate         REAL    DEFAULT 0.0,
                    total_trades     INTEGER DEFAULT 0,
                    net_profit_pct   REAL    DEFAULT 0.0,
                    approved         INTEGER DEFAULT 0,
                    discard_reason   TEXT    DEFAULT '',
                    output_path      TEXT    DEFAULT '',
                    compile_attempts INTEGER DEFAULT 0,
                    flash_calls      INTEGER DEFAULT 0,
                    pro_calls        INTEGER DEFAULT 0,
                    design_json      TEXT    DEFAULT '',
                    notes            TEXT    DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS llm_calls (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp  TEXT NOT NULL,
                    model      TEXT NOT NULL,
                    agent      TEXT NOT NULL,
                    cycle_id   INTEGER,
                    prompt_len INTEGER DEFAULT 0,
                    resp_len   INTEGER DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_cycles_status
                    ON cycles(status);
                CREATE INDEX IF NOT EXISTS idx_cycles_approved
                    ON cycles(approved);
                CREATE INDEX IF NOT EXISTS idx_llm_timestamp
                    ON llm_calls(timestamp);
            """)

    # ── CRUD de ciclos ────────────────────────────────────────────────

    def create_cycle(self, strategy_type: str = "", symbol: str = "EURUSD") -> int:
        """Crea un nuevo ciclo y retorna su ID."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                """INSERT INTO cycles (timestamp, strategy_type, symbol, status)
                   VALUES (?, ?, ?, 'en_proceso')""",
                (datetime.now().isoformat(), strategy_type, symbol)
            )
            cycle_id = cursor.lastrowid
            log.info(f"Ciclo creado: ID={cycle_id}")
            return cycle_id

    def update_cycle(self, cycle_id: int, **kwargs):
        """Actualiza campos específicos de un ciclo."""
        if not kwargs:
            return

        set_clause = ", ".join(f"{k} = ?" for k in kwargs)
        values     = list(kwargs.values()) + [cycle_id]

        with self._get_conn() as conn:
            conn.execute(
                f"UPDATE cycles SET {set_clause} WHERE id = ?",
                values
            )

    def get_cycle(self, cycle_id: int) -> Optional[dict]:
        """Obtiene un ciclo por ID."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM cycles WHERE id = ?", (cycle_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_approved_strategies(self) -> list[dict]:
        """Retorna todas las estrategias aprobadas."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM cycles
                   WHERE approved = 1
                   ORDER BY sharpe_ratio DESC"""
            ).fetchall()
            return [dict(r) for r in rows]

    def get_recent_cycles(self, limit: int = 20) -> list[dict]:
        """Retorna los últimos N ciclos."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM cycles
                   ORDER BY timestamp DESC
                   LIMIT ?""",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_strategy_names(self) -> list[str]:
        """
        Retorna los nombres de todas las estrategias generadas.
        Usado por el Orchestrator para evitar duplicados.
        """
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT strategy_name FROM cycles WHERE strategy_name != ''"
            ).fetchall()
            return [r["strategy_name"] for r in rows]

    def get_design_jsons(self) -> list[str]:
        """
        Retorna los JSONs de diseño de estrategias anteriores.
        Usado para detectar ideas duplicadas.
        """
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT design_json FROM cycles WHERE design_json != ''"
            ).fetchall()
            return [r["design_json"] for r in rows]

    # ── LLM calls ────────────────────────────────────────────────────

    def log_llm_call(
        self,
        model:      str,
        agent:      str,
        cycle_id:   Optional[int] = None,
        prompt_len: int = 0,
        resp_len:   int = 0,
    ):
        """Registra una llamada al LLM para monitoreo de uso."""
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO llm_calls
                   (timestamp, model, agent, cycle_id, prompt_len, resp_len)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (datetime.now().isoformat(), model, agent, cycle_id, prompt_len, resp_len)
            )

    def count_llm_calls_today(self, model: str = "pro") -> int:
        """Cuenta las llamadas al LLM de hoy. Útil para monitorear el límite diario."""
        today = date.today().isoformat()
        with self._get_conn() as conn:
            row = conn.execute(
                """SELECT COUNT(*) as cnt FROM llm_calls
                   WHERE model = ? AND timestamp LIKE ?""",
                (model, f"{today}%")
            ).fetchone()
            return row["cnt"] if row else 0

    # ── Estadísticas ──────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Retorna estadísticas globales del sistema."""
        with self._get_conn() as conn:
            total = conn.execute(
                "SELECT COUNT(*) as cnt FROM cycles"
            ).fetchone()["cnt"]

            approved = conn.execute(
                "SELECT COUNT(*) as cnt FROM cycles WHERE approved = 1"
            ).fetchone()["cnt"]

            discarded = conn.execute(
                "SELECT COUNT(*) as cnt FROM cycles WHERE status = 'descartado'"
            ).fetchone()["cnt"]

            best = conn.execute(
                """SELECT strategy_name, sharpe_ratio, profit_factor
                   FROM cycles WHERE approved = 1
                   ORDER BY sharpe_ratio DESC LIMIT 1"""
            ).fetchone()

            flash_today = self.count_llm_calls_today("flash")
            pro_today   = self.count_llm_calls_today("pro")

            return {
                "total_ciclos":        total,
                "aprobadas":           approved,
                "descartadas":         discarded,
                "tasa_aprobacion":     f"{approved/total*100:.1f}%" if total > 0 else "0%",
                "mejor_estrategia":    dict(best) if best else None,
                "flash_calls_hoy":     flash_today,
                "pro_calls_hoy":       pro_today,
                "pro_restantes_hoy":   max(0, 25 - pro_today),
            }

    def print_stats(self):
        """Imprime un resumen del estado del sistema."""
        stats = self.get_stats()
        print("\n" + "="*40)
        print("ESTADO DEL SISTEMA")
        print("="*40)
        print(f"Ciclos totales:     {stats['total_ciclos']}")
        print(f"Aprobadas:          {stats['aprobadas']} ({stats['tasa_aprobacion']})")
        print(f"Descartadas:        {stats['descartadas']}")
        if stats["mejor_estrategia"]:
            m = stats["mejor_estrategia"]
            print(f"Mejor estrategia:   {m['strategy_name']} (Sharpe {m['sharpe_ratio']:.2f})")
        print(f"Flash calls hoy:    {stats['flash_calls_hoy']}/1500")
        print(f"Pro calls hoy:      {stats['pro_calls_hoy']}/25 ({stats['pro_restantes_hoy']} restantes)")
        print("="*40 + "\n")


# ─────────────────────────────────────────────
# SINGLETON
# ─────────────────────────────────────────────

_db: Optional[Database] = None

def get_database() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db


# ─────────────────────────────────────────────
# TEST RÁPIDO
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Probando Database...")
    db = Database(Path("output/test.db"))

    # Crear ciclo
    cid = db.create_cycle("tendencia", "EURUSD")
    print(f"Ciclo creado: ID={cid}")

    # Actualizar
    db.update_cycle(cid,
        strategy_name    = "EMA_RSI_Test",
        status           = "completado",
        approved         = 1,
        profit_factor    = 1.87,
        sharpe_ratio     = 1.64,
        max_drawdown_pct = 14.3,
        total_trades     = 412,
    )

    # Verificar
    db.print_stats()
    print("✅ Database funcionando correctamente")

    # Limpiar test
    Path("output/test.db").unlink(missing_ok=True)
