"""
core/mt5_connector.py
=====================
Bridge entre el sistema Python y MetaTrader 5.
Maneja la conexión, desconexión, y todas las operaciones con MT5.

IMPORTANTE: Solo funciona en Windows con MT5 instalado.

Uso:
    from core.mt5_connector import MT5Connector
    mt5 = MT5Connector()
    mt5.connect()
    datos = mt5.get_historical_data("EURUSD", "H4", 2013, 2024)
    resultado = mt5.run_backtest("EA_nombre", params)
    mt5.disconnect()
"""

import os
import time
import shutil
import logging
import subprocess
from pathlib import Path
from typing import Optional
from datetime import datetime
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# ESTRUCTURAS DE DATOS
# ─────────────────────────────────────────────

@dataclass
class BacktestResult:
    """Resultado de un backtest en MT5 Strategy Tester."""
    profit_factor:    float = 0.0
    sharpe_ratio:     float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate:         float = 0.0
    total_trades:     int   = 0
    net_profit:       float = 0.0
    gross_profit:     float = 0.0
    gross_loss:       float = 0.0
    avg_win:          float = 0.0
    avg_loss:         float = 0.0
    trades_per_month: float = 0.0
    initial_deposit:  float = 0.0
    final_balance:    float = 0.0
    raw_report:       str   = ""   # reporte XML/HTML crudo de MT5
    success:          bool  = False
    error_message:    str   = ""


@dataclass
class CompileResult:
    """Resultado de compilar un archivo .mq5."""
    success:       bool
    errors:        list[str]
    warnings:      list[str]
    log_content:   str
    compiled_path: Optional[Path] = None


# ─────────────────────────────────────────────
# CONECTOR MT5
# ─────────────────────────────────────────────

class MT5Connector:
    """
    Gestiona toda la interacción con MetaTrader 5.
    Compilación de EAs, backtesting y lectura de resultados.
    """

    def __init__(self):
        # Paths de MT5 — detectar automáticamente o usar los del config
        self.mt5_path       = self._find_mt5_path()
        self.metaeditor_path = self._find_metaeditor_path()
        self.experts_dir    = self._find_experts_dir()
        self.tester_dir     = self._find_tester_dir()

        # Credenciales opcionales (para cuenta demo)
        self.login    = os.getenv("MT5_LOGIN")
        self.password = os.getenv("MT5_PASSWORD")
        self.server   = os.getenv("MT5_SERVER")

        self._mt5_lib = None   # librería MetaTrader5 Python (se importa lazy)

        log.info(f"MT5Connector inicializado")
        log.info(f"  MT5 path:        {self.mt5_path}")
        log.info(f"  MetaEditor path: {self.metaeditor_path}")
        log.info(f"  Experts dir:     {self.experts_dir}")

    # ── Detección de paths ────────────────────────────────────────────

    def _find_mt5_path(self) -> Optional[Path]:
        """Busca el ejecutable de MT5 en las ubicaciones estándar."""
        candidates = [
            Path("C:/Program Files/MetaTrader 5/terminal64.exe"),
            Path("C:/Program Files (x86)/MetaTrader 5/terminal64.exe"),
            Path(os.getenv("APPDATA", "")) / "MetaQuotes/Terminal",
        ]
        for p in candidates:
            if p.exists():
                return p
        log.warning("MT5 no encontrado en ubicaciones estándar")
        return None

    def _find_metaeditor_path(self) -> Optional[Path]:
        """Busca el compilador MetaEditor."""
        candidates = [
            Path("C:/Program Files/MetaTrader 5/metaeditor64.exe"),
            Path("C:/Program Files (x86)/MetaTrader 5/metaeditor64.exe"),
        ]
        for p in candidates:
            if p.exists():
                return p
        log.warning("MetaEditor no encontrado")
        return None

    def _find_experts_dir(self) -> Optional[Path]:
        """Busca el directorio de Experts de MT5."""
        # El directorio de datos de MT5 suele estar en AppData
        appdata = Path(os.getenv("APPDATA", ""))
        candidates = [
            appdata / "MetaQuotes/Terminal",
        ]
        for base in candidates:
            if base.exists():
                # Buscar subdirectorios que contengan MQL5/Experts
                for subdir in base.iterdir():
                    experts = subdir / "MQL5/Experts"
                    if experts.exists():
                        return experts
        # Fallback: directorio de instalación
        fallback = Path("C:/Program Files/MetaTrader 5/MQL5/Experts")
        return fallback if fallback.exists() else None

    def _find_tester_dir(self) -> Optional[Path]:
        """Busca el directorio del Strategy Tester."""
        appdata = Path(os.getenv("APPDATA", ""))
        base = appdata / "MetaQuotes/Terminal"
        if base.exists():
            for subdir in base.iterdir():
                tester = subdir / "tester"
                if tester.exists():
                    return tester
        return None

    # ── Conexión con MT5 Python API ───────────────────────────────────

    def connect(self) -> bool:
        """
        Conecta con MT5 usando la librería Python.
        Necesario para obtener datos históricos y ejecutar backtests.
        """
        try:
            import MetaTrader5 as mt5
            self._mt5_lib = mt5

            # Inicializar MT5
            if not mt5.initialize():
                log.error(f"Error inicializando MT5: {mt5.last_error()}")
                return False

            # Login si hay credenciales
            if self.login and self.password and self.server:
                if not mt5.login(int(self.login), self.password, self.server):
                    log.warning(f"Login MT5 fallido: {mt5.last_error()}")
                    # Continuar sin login — puede funcionar con cuenta ya abierta

            info = mt5.terminal_info()
            log.info(f"MT5 conectado: {info.name} build {info.build}")
            return True

        except ImportError:
            log.error(
                "Librería MetaTrader5 no instalada. "
                "Ejecutar: pip install MetaTrader5"
            )
            return False
        except Exception as e:
            log.error(f"Error conectando MT5: {e}")
            return False

    def disconnect(self):
        """Desconecta de MT5."""
        if self._mt5_lib:
            self._mt5_lib.shutdown()
            log.info("MT5 desconectado")

    # ── Compilación de EAs ────────────────────────────────────────────

    def compile_ea(self, mq5_path: Path) -> CompileResult:
        """
        Compila un archivo .mq5 usando MetaEditor.

        Args:
            mq5_path: Path al archivo .mq5 a compilar

        Returns:
            CompileResult con éxito/error y mensajes del compilador
        """
        if not self.metaeditor_path:
            return CompileResult(
                success=False,
                errors=["MetaEditor no encontrado. Verificar instalación de MT5."],
                warnings=[],
                log_content="",
            )

        if not mq5_path.exists():
            return CompileResult(
                success=False,
                errors=[f"Archivo no encontrado: {mq5_path}"],
                warnings=[],
                log_content="",
            )

        log_path = mq5_path.with_suffix(".log")

        try:
            # Ejecutar MetaEditor en modo compilación
            cmd = [
                str(self.metaeditor_path),
                "/compile:" + str(mq5_path),
                "/log:" + str(log_path),
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )

            # Leer el log de compilación
            log_content = ""
            if log_path.exists():
                # MT5 genera el log en UTF-16
                try:
                    log_content = log_path.read_text(encoding="utf-16")
                except Exception:
                    log_content = log_path.read_text(encoding="utf-8", errors="ignore")

            # Parsear errores y warnings del log
            errors   = []
            warnings = []
            for line in log_content.splitlines():
                line_lower = line.lower()
                if " error " in line_lower or line_lower.strip().startswith("error"):
                    errors.append(line.strip())
                elif " warning " in line_lower:
                    warnings.append(line.strip())

            # Verificar si existe el .ex5 compilado
            ex5_path = mq5_path.with_suffix(".ex5")
            success  = ex5_path.exists() and len(errors) == 0

            if success:
                log.info(f"✅ Compilación exitosa: {mq5_path.name}")
            else:
                log.warning(f"❌ Compilación fallida: {mq5_path.name} — {len(errors)} errores")
                for err in errors[:3]:
                    log.warning(f"   {err}")

            return CompileResult(
                success        = success,
                errors         = errors,
                warnings       = warnings,
                log_content    = log_content,
                compiled_path  = ex5_path if success else None,
            )

        except subprocess.TimeoutExpired:
            return CompileResult(
                success=False,
                errors=["Timeout: compilación tardó más de 60 segundos"],
                warnings=[],
                log_content="",
            )
        except Exception as e:
            return CompileResult(
                success=False,
                errors=[f"Error ejecutando MetaEditor: {e}"],
                warnings=[],
                log_content="",
            )

    def copy_ea_to_experts(self, mq5_path: Path) -> Path:
        """
        Copia el archivo .mq5 al directorio de Experts de MT5.
        Necesario para que MT5 pueda compilarlo y ejecutarlo.

        Args:
            mq5_path: Path al archivo .mq5 fuente

        Returns:
            Path de destino en el directorio de Experts
        """
        if not self.experts_dir:
            raise RuntimeError("Directorio de Experts de MT5 no encontrado")

        dest = self.experts_dir / mq5_path.name
        shutil.copy2(mq5_path, dest)
        log.info(f"EA copiado a Experts: {dest}")
        return dest

    # ── Backtesting ───────────────────────────────────────────────────

    def run_backtest(
        self,
        ea_name:        str,
        symbol:         str = "EURUSD",
        timeframe:      str = "H4",
        date_from:      str = "2013.01.01",
        date_to:        str = "2024.12.31",
        deposit:        float = 10000.0,
        params:         Optional[dict] = None,
    ) -> BacktestResult:
        """
        Ejecuta un backtest en MT5 Strategy Tester vía Python API.

        Args:
            ea_name:    Nombre del EA (sin extensión)
            symbol:     Par a testear (ej: "EURUSD")
            timeframe:  Timeframe (ej: "H4", "D1")
            date_from:  Inicio del backtest (ej: "2013.01.01")
            date_to:    Fin del backtest
            deposit:    Capital inicial simulado
            params:     Diccionario de parámetros del EA {nombre: valor}

        Returns:
            BacktestResult con todas las métricas extraídas
        """
        if not self._mt5_lib:
            if not self.connect():
                return BacktestResult(
                    success=False,
                    error_message="No se pudo conectar con MT5"
                )

        mt5 = self._mt5_lib

        try:
            # Mapear timeframe string a constante MT5
            tf_map = {
                "M1": mt5.TIMEFRAME_M1,   "M5": mt5.TIMEFRAME_M5,
                "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30,
                "H1": mt5.TIMEFRAME_H1,   "H4": mt5.TIMEFRAME_H4,
                "D1": mt5.TIMEFRAME_D1,   "W1": mt5.TIMEFRAME_W1,
            }
            tf = tf_map.get(timeframe, mt5.TIMEFRAME_H4)

            # Parsear fechas
            dt_from = datetime.strptime(date_from, "%Y.%m.%d")
            dt_to   = datetime.strptime(date_to,   "%Y.%m.%d")

            log.info(f"Ejecutando backtest: {ea_name} | {symbol} {timeframe} | {date_from} → {date_to}")

            # Configurar y ejecutar el backtest
            # MT5 Python API no tiene backtest directo, se hace via Strategy Tester
            # Usamos el método de leer el reporte XML después de ejecutar el tester
            result = self._run_strategy_tester(
                ea_name   = ea_name,
                symbol    = symbol,
                tf        = tf,
                dt_from   = dt_from,
                dt_to     = dt_to,
                deposit   = deposit,
                params    = params or {},
            )

            return result

        except Exception as e:
            log.error(f"Error en backtest {ea_name}: {e}")
            return BacktestResult(success=False, error_message=str(e))

    def _run_strategy_tester(
        self,
        ea_name: str,
        symbol:  str,
        tf:      int,
        dt_from: datetime,
        dt_to:   datetime,
        deposit: float,
        params:  dict,
    ) -> BacktestResult:
        """
        Ejecuta el Strategy Tester de MT5 y parsea el reporte XML.
        """
        mt5 = self._mt5_lib

        # Generar archivo .ini de configuración para el tester
        ini_content = self._build_tester_ini(
            ea_name = ea_name,
            symbol  = symbol,
            tf      = tf,
            dt_from = dt_from,
            dt_to   = dt_to,
            deposit = deposit,
            params  = params,
        )

        # Guardar el .ini temporalmente
        ini_path    = Path("output") / "temp_backtest.ini"
        report_path = Path("output") / f"report_{ea_name}.xml"
        ini_path.parent.mkdir(exist_ok=True)
        ini_path.write_text(ini_content, encoding="utf-8")

        # Ejecutar MT5 con el .ini de configuración
        if not self.mt5_path:
            return BacktestResult(
                success=False,
                error_message="MT5 no encontrado para ejecutar el Strategy Tester"
            )

        cmd = [
            str(self.mt5_path),
            f"/config:{ini_path}",
        ]

        log.info(f"Ejecutando Strategy Tester: {' '.join(cmd)}")

        try:
            subprocess.run(cmd, timeout=300)  # 5 minutos máximo por backtest
        except subprocess.TimeoutExpired:
            return BacktestResult(success=False, error_message="Timeout en Strategy Tester (>5 min)")

        # Esperar a que el reporte esté listo
        time.sleep(5)

        # Parsear el reporte XML
        if report_path.exists():
            return self._parse_backtest_report(report_path)
        else:
            return BacktestResult(
                success=False,
                error_message=f"Reporte no generado: {report_path}"
            )

    def _build_tester_ini(
        self,
        ea_name: str,
        symbol:  str,
        tf:      int,
        dt_from: datetime,
        dt_to:   datetime,
        deposit: float,
        params:  dict,
    ) -> str:
        """Genera el archivo .ini de configuración para el Strategy Tester."""
        tf_names = {1: "M1", 5: "M5", 15: "M15", 30: "M30",
                    16385: "H1", 16388: "H4", 16408: "D1"}
        tf_name = tf_names.get(tf, "H4")

        lines = [
            "[Tester]",
            f"Expert={ea_name}",
            f"Symbol={symbol}",
            f"Period={tf_name}",
            f"FromDate={dt_from.strftime('%Y.%m.%d')}",
            f"ToDate={dt_to.strftime('%Y.%m.%d')}",
            f"Deposit={deposit}",
            "Currency=USD",
            "Leverage=100",
            "Model=1",         # 1 = OHLC por barra (más rápido para H4)
            "Optimization=0",  # 0 = sin optimización (backtest simple)
            "Report=report",
            "ReplaceReport=1",
        ]

        # Agregar parámetros del EA si se especifican
        if params:
            lines.append("[TesterInputs]")
            for name, value in params.items():
                lines.append(f"{name}={value}")

        return "\n".join(lines)

    def _parse_backtest_report(self, report_path: Path) -> BacktestResult:
        """
        Parsea el reporte XML/HTML generado por MT5 Strategy Tester
        y extrae las métricas clave.
        """
        try:
            content = report_path.read_text(encoding="utf-8", errors="ignore")

            import re

            def extract(pattern, text, default=0.0):
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    try:
                        return float(match.group(1).replace(",", ".").replace(" ", ""))
                    except Exception:
                        return default
                return default

            result = BacktestResult(
                profit_factor    = extract(r"Profit Factor[^>]*>([0-9.,]+)", content),
                sharpe_ratio     = extract(r"Sharpe Ratio[^>]*>([0-9.,]+)", content),
                max_drawdown_pct = extract(r"Drawdown[^>]*>([0-9.,]+)\s*%", content),
                win_rate         = extract(r"Win Trades[^>]*>(\d+)\s*\(([0-9.,]+)%\)", content),
                total_trades     = int(extract(r"Total Trades[^>]*>(\d+)", content)),
                net_profit       = extract(r"Net Profit[^>]*>([0-9.,\-]+)", content),
                gross_profit     = extract(r"Gross Profit[^>]*>([0-9.,]+)", content),
                gross_loss       = extract(r"Gross Loss[^>]*>([0-9.,\-]+)", content),
                raw_report       = content[:5000],
                success          = True,
            )

            # Calcular trades por mes
            if result.total_trades > 0:
                # 11 años = 132 meses
                result.trades_per_month = result.total_trades / 132

            log.info(
                f"Backtest parseado: PF={result.profit_factor:.2f} | "
                f"Sharpe={result.sharpe_ratio:.2f} | "
                f"DD={result.max_drawdown_pct:.1f}% | "
                f"Trades={result.total_trades}"
            )

            return result

        except Exception as e:
            return BacktestResult(
                success=False,
                error_message=f"Error parseando reporte: {e}"
            )

    # ── Datos históricos ──────────────────────────────────────────────

    def get_historical_data(
        self,
        symbol:    str,
        timeframe: str,
        date_from: datetime,
        date_to:   datetime,
    ) -> Optional[list]:
        """
        Obtiene datos históricos OHLCV directamente de MT5.

        Returns:
            Lista de barras o None si hay error
        """
        if not self._mt5_lib:
            if not self.connect():
                return None

        mt5 = self._mt5_lib

        tf_map = {
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
            "H1": mt5.TIMEFRAME_H1,
        }
        tf = tf_map.get(timeframe, mt5.TIMEFRAME_H4)

        rates = mt5.copy_rates_range(symbol, tf, date_from, date_to)

        if rates is None or len(rates) == 0:
            log.error(f"No se obtuvieron datos para {symbol} {timeframe}")
            return None

        log.info(f"Datos históricos: {symbol} {timeframe} — {len(rates)} barras")
        return rates

    def is_connected(self) -> bool:
        """Verifica si MT5 está conectado."""
        if not self._mt5_lib:
            return False
        try:
            info = self._mt5_lib.terminal_info()
            return info is not None
        except Exception:
            return False


# ─────────────────────────────────────────────
# SINGLETON
# ─────────────────────────────────────────────

_connector: Optional[MT5Connector] = None

def get_mt5_connector() -> MT5Connector:
    """Retorna la instancia singleton del MT5Connector."""
    global _connector
    if _connector is None:
        _connector = MT5Connector()
    return _connector


# ─────────────────────────────────────────────
# TEST RÁPIDO
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Probando MT5Connector...")
    connector = MT5Connector()

    print(f"MT5 path:        {connector.mt5_path}")
    print(f"MetaEditor path: {connector.metaeditor_path}")
    print(f"Experts dir:     {connector.experts_dir}")

    print("\nIntentando conectar con MT5...")
    if connector.connect():
        print("✅ MT5 conectado correctamente")
        connector.disconnect()
    else:
        print("⚠️  MT5 no conectado (asegurarse que MT5 está abierto)")
