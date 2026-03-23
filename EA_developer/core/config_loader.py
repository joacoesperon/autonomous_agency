"""
core/config_loader.py
=====================
Carga el perfil activo del config.yaml y gestiona la rotación automática.

El perfil determina: símbolo, timeframe, fechas de backtest y filtros de calidad.
Todos los agentes usan get_active_profile() en lugar de leer config.yaml directamente.
"""

import logging
from pathlib import Path
from typing import Optional

import yaml

log = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


def load_config() -> dict:
    """Carga el config.yaml completo."""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"No se encontró config.yaml en {CONFIG_PATH}")
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_active_profile(force_profile: Optional[str] = None) -> dict:
    """
    Retorna el perfil activo con todos sus parámetros.

    Si active_profile es "auto", elige el perfil menos usado recientemente.
    Si force_profile se especifica (ej: desde CLI), lo usa directamente.

    Returns:
        dict con symbol, timeframe, quality_filters, etc.
        Incluye el campo "profile_name" con el nombre del perfil.
    """
    config = load_config()
    profiles = config.get("profiles", {})

    if not profiles:
        raise ValueError("No hay perfiles definidos en config.yaml")

    # Determinar qué perfil usar
    if force_profile:
        profile_name = force_profile
    else:
        active = config.get("active_profile", "auto")
        if active == "auto":
            profile_name = _choose_rotation_profile(config)
        else:
            profile_name = active

    if profile_name not in profiles:
        available = list(profiles.keys())
        raise ValueError(
            f"Perfil '{profile_name}' no existe. "
            f"Disponibles: {available}"
        )

    profile = profiles[profile_name].copy()
    profile["profile_name"] = profile_name

    log.info(
        f"Perfil activo: {profile_name} | "
        f"{profile.get('symbol')} {profile.get('timeframe')} | "
        f"{profile.get('description', '')}"
    )

    return profile


def _choose_rotation_profile(config: dict) -> str:
    """
    Elige el siguiente perfil en la rotación según el historial en la DB.
    El perfil menos usado recientemente tiene prioridad.
    """
    rotation = config.get("rotation_schedule", [])
    if not rotation:
        # Si no hay rotación definida, usar el primer perfil disponible
        return list(config.get("profiles", {}).keys())[0]

    try:
        from core.database import get_database
        db = get_database()
        cycles = db.get_recent_cycles(limit=50)

        # Contar usos recientes por perfil
        profile_counts = {p: 0 for p in rotation}
        for cycle in cycles:
            # El perfil se guarda en el campo symbol+timeframe
            symbol = cycle.get("symbol", "")
            tf     = cycle.get("timeframe", "")
            for profile_name in rotation:
                cfg = config["profiles"].get(profile_name, {})
                if cfg.get("symbol") == symbol and cfg.get("timeframe") == tf:
                    profile_counts[profile_name] += 1
                    break

        # Elegir el menos usado
        min_count = min(profile_counts.values())
        candidates = [p for p, c in profile_counts.items() if c == min_count]

        # Si hay empate, mantener el orden de la rotación
        for p in rotation:
            if p in candidates:
                log.info(f"Rotación automática → {p} (usado {min_count} veces recientes)")
                return p

    except Exception as e:
        log.warning(f"No se pudo consultar DB para rotación: {e}")

    # Fallback: primer perfil de la rotación
    return rotation[0]


def get_validator_system_prompt(profile: dict) -> str:
    """
    Genera el system prompt del Validator dinámicamente según el perfil activo.
    Los criterios de evaluación se adaptan al símbolo y timeframe.
    """
    symbol    = profile.get("symbol", "EURUSD")
    timeframe = profile.get("timeframe", "H4")
    filters   = profile.get("quality_filters", {})
    desc      = profile.get("description", "")

    # Contexto específico por símbolo
    symbol_context = {
        "EURUSD": (
            "Par Forex major con alta liquidez y spreads bajos (~1 pip). "
            "Muy correlacionado con factores macro europeos y americanos. "
            "Baja volatilidad relativa, movimientos suaves y tendencias claras."
        ),
        "GBPUSD": (
            "Cable, más volátil que EURUSD con spreads algo más altos (~1.5 pips). "
            "Sensible a noticias del Reino Unido. "
            "Movimientos más bruscos, requiere SL más amplios."
        ),
        "XAUUSD": (
            "Oro físico, activo refugio con alta volatilidad y spreads amplios (~30-50 pips). "
            "Movimientos muy bruscos en momentos de crisis o datos macro. "
            "Los DrawDowns son naturalmente más altos. "
            "Requiere gestión de riesgo más conservadora. "
            "Una estrategia con PF=1.6 en oro es excelente dado los costos."
        ),
        "USDJPY": (
            "Yen japonés, correlacionado con el apetito por el riesgo global. "
            "Spreads bajos, buena liquidez. "
            "Muy sensible a política monetaria del Banco de Japón y datos americanos."
        ),
    }

    ctx = symbol_context.get(symbol, f"Par {symbol}")

    # Contexto por timeframe
    tf_context = {
        "H4": "Swing trading de 4 horas, típicamente 1-3 trades por semana.",
        "H1": "Intradía/swing corto, mayor frecuencia de trades, más sensible al spread.",
        "D1": "Trading diario, pocas señales pero muy filtradas.",
    }
    tf_ctx = tf_context.get(timeframe, f"Timeframe {timeframe}")

    return f"""Eres un analista cuantitativo especializado en evaluar estrategias de trading algorítmico.
Tu función es analizar métricas de backtesting y determinar si una estrategia es viable para trading real.

═══════════════════════════════════════════════════════════
CONTEXTO DEL ACTIVO
═══════════════════════════════════════════════════════════

Símbolo:    {symbol}
Timeframe:  {timeframe}
Descripción: {desc}

Características del activo:
{ctx}

Frecuencia esperada: {tf_ctx}

═══════════════════════════════════════════════════════════
CRITERIOS DE EVALUACIÓN PARA {symbol} {timeframe}
═══════════════════════════════════════════════════════════

MÉTRICAS MÍNIMAS REQUERIDAS (específicas para este activo):
- Profit Factor > {filters.get('min_profit_factor', 1.5)}
- Sharpe Ratio  > {filters.get('min_sharpe_ratio', 1.2)}
- Max DrawDown  < {filters.get('max_drawdown_pct', 25.0)}%
- Win Rate      > {filters.get('min_win_rate', 45.0)}%
- Total Trades  > {filters.get('min_total_trades', 200)} en el período
- Trades/mes    > {filters.get('min_trades_per_month', 1.5)}
- Walk-forward positivo en mayoría de ventanas

SEÑALES DE ALERTA (no descartatorias pero importantes):
- Profit Factor entre {filters.get('min_profit_factor', 1.5)} y {filters.get('min_profit_factor', 1.5) + 0.2:.1f} → estrategia marginal para {symbol}
- DrawDown entre {filters.get('max_drawdown_pct', 25.0) - 5:.0f}% y {filters.get('max_drawdown_pct', 25.0):.0f}% → riesgo elevado
- Menos de {int(filters.get('min_total_trades', 200) * 1.5)} trades → muestra pequeña para este timeframe
- Walk-forward con alta varianza entre ventanas → poca robustez temporal

CONSIDERACIONES ESPECIALES PARA {symbol}:
{"- Los spreads amplios impactan significativamente el PF. Un PF de 1.6 es excelente." if symbol == "XAUUSD" else ""}
{"- Considerar el impacto de eventos macro (NFP, BCE, Fed) en la estrategia." if symbol in ("EURUSD", "GBPUSD") else ""}
{"- Evaluar si la estrategia sobrevive los momentos de crisis de liquidez del yen." if symbol == "USDJPY" else ""}
{"- En H1, el spread consume más del beneficio por trade. Evaluar el net profit post-costos." if timeframe == "H1" else ""}

═══════════════════════════════════════════════════════════
FORMATO DE OUTPUT — JSON ESTRICTO
═══════════════════════════════════════════════════════════

Responde ÚNICAMENTE con JSON válido. Sin explicaciones, sin markdown.

{{
  "aprobada": true,
  "score_general": 0.82,
  "explicacion_estrategia": "La estrategia aprovecha...",
  "fortalezas": ["...", "..."],
  "debilidades": ["...", "..."],
  "alertas": ["..."],
  "recomendacion": "APROBAR/RECHAZAR - ...",
  "notas_para_trading": "Consideraciones específicas para operar {symbol} con esta estrategia..."
}}
"""


def list_profiles() -> None:
    """Imprime todos los perfiles disponibles."""
    config   = load_config()
    profiles = config.get("profiles", {})
    active   = config.get("active_profile", "auto")

    print(f"\nPerfil activo: {active}")
    print(f"{'─'*55}")
    for name, p in profiles.items():
        marker = "← activo" if name == active else ""
        print(
            f"  {name:<15} {p.get('symbol',''):<8} {p.get('timeframe',''):<5} "
            f"{p.get('description','')} {marker}"
        )
    print()
