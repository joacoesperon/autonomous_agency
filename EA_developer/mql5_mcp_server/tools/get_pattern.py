"""
Tool: get_pattern
Retorna fragmentos de código MQL5 probados desde la Knowledge Base manual.
Los patrones están organizados por nombre y también son buscables semánticamente.
"""

import re
from pathlib import Path


# Mapa de alias para nombres de patrones comunes
PATTERN_ALIASES = {
    # Detección de velas
    "nueva vela":            "01",
    "new bar":               "01",
    "nueva barra":           "01",
    "deteccion vela":        "01",

    # Indicadores
    "ema handle":            "02",
    "media movil":           "02",
    "moving average":        "02",
    "rsi handle":            "03",
    "rsi":                   "03",
    "macd handle":           "04",
    "macd":                  "04",
    "bollinger":             "05",
    "bands":                 "05",
    "atr handle":            "06",
    "atr":                   "06",

    # Lógica de trading
    "cruce de medias":       "07",
    "crossover":             "07",
    "golden cross":          "07",
    "cruce precio ema":      "08",
    "precio sobre ema":      "08",

    # Órdenes
    "abrir buy":             "09",
    "open buy":              "09",
    "buy order":             "09",
    "compra":                "09",
    "abrir sell":            "10",
    "open sell":             "10",
    "sell order":            "10",
    "venta":                 "10",

    # Gestión de posiciones
    "verificar posicion":    "11",
    "hay posicion":          "11",
    "check position":        "11",
    "cerrar posicion":       "12",
    "close position":        "12",
    "trailing stop":         "13",
    "trailing":              "13",
    "breakeven":             "14",
    "break even":            "14",

    # Cálculos
    "calcular lote":         "15",
    "lot size":              "15",
    "position size":         "15",
    "riesgo":                "15",
    "spread":                "16",
    "filtro spread":         "16",
    "horario":               "17",
    "sesion":                "17",
    "session filter":        "17",
    "dia semana":            "18",
    "day filter":            "18",

    # Datos de precio
    "precio cierre":         "19",
    "close price":           "19",
    "ohlc":                  "19",
    "maximo minimo":         "20",
    "highest lowest":        "20",
    "sl atr":                "21",
    "stop loss atr":         "21",
    "atr sl":                "21",

    # Filtros de tendencia
    "filtro tendencia":      "22",
    "trend filter":          "22",
    "ema d1":                "22",
    "higher high":           "23",
    "lower low":             "23",
    "estructura mercado":    "23",
    "soporte resistencia":   "24",
    "swing point":           "24",

    # Gestión avanzada
    "multiples posiciones":  "25",
    "multiple positions":    "25",
    "profit flotante":       "26",
    "floating profit":       "26",
    "divergencia rsi":       "27",
    "divergence":            "27",
    "manejo errores":        "28",
    "error handling":        "28",
    "normalizar":            "29",
    "normalize":             "29",
    "validacion oninit":     "30",
    "oninit validation":     "30",
    "inicializacion":        "30",
}


def _load_knowledge_base() -> str:
    """Carga el archivo de knowledge base."""
    kb_path = Path(__file__).parent.parent / "data" / "mql5_knowledge_base.md"
    if not kb_path.exists():
        return ""
    return kb_path.read_text(encoding="utf-8")


def _extract_pattern(kb_text: str, pattern_number: str) -> str:
    """Extrae un patrón específico del knowledge base por su número."""
    # Buscar el patrón por número (ej: "### Patrón 07")
    pattern_num = pattern_number.zfill(2)
    search_str  = f"### Patrón {pattern_num}"

    start = kb_text.find(search_str)
    if start == -1:
        return ""

    # El patrón termina en el siguiente "### Patrón" o al final del bloque
    next_pattern = kb_text.find("### Patrón", start + 1)
    if next_pattern == -1:
        # Buscar el siguiente encabezado de bloque
        next_block = kb_text.find("\n## BLOQUE", start + 1)
        end = next_block if next_block != -1 else len(kb_text)
    else:
        end = next_pattern

    return kb_text[start:end].strip()


def _search_pattern_semantic(kb_text: str, query: str) -> str:
    """
    Búsqueda semántica simple en el knowledge base.
    Busca el patrón cuyo contenido tiene más palabras clave en común con la query.
    """
    query_words = set(query.lower().split())

    best_score   = 0
    best_pattern = ""

    # Extraer todos los patrones y puntuar por relevancia
    pattern_blocks = re.split(r"### Patrón \d+", kb_text)

    for i, block in enumerate(pattern_blocks[1:], 1):  # skip intro
        block_words = set(re.sub(r"[^a-zA-Z\s]", " ", block.lower()).split())
        score = len(query_words & block_words)
        if score > best_score:
            best_score   = score
            best_pattern = f"### Patrón {str(i).zfill(2)}{block}"

    return best_pattern.strip() if best_score > 0 else ""


def get_pattern(pattern_name: str) -> str:
    """
    Retorna un fragmento de código MQL5 probado para un patrón específico.

    Args:
        pattern_name: Nombre o descripción del patrón buscado.
                     Ejemplos: 'cruce de medias', 'abrir buy', 'trailing stop',
                               'calcular lote', 'nueva vela', 'rsi handle'

    Returns:
        Fragmento de código MQL5 listo para usar
    """
    kb_text = _load_knowledge_base()
    if not kb_text:
        return "ERROR: No se encontró el archivo de knowledge base."

    query_lower = pattern_name.lower().strip()

    # 1. Buscar por alias exacto
    pattern_num = None
    for alias, num in PATTERN_ALIASES.items():
        if alias in query_lower or query_lower in alias:
            pattern_num = num
            break

    # 2. Si encontró número, extraer el patrón
    if pattern_num:
        pattern = _extract_pattern(kb_text, pattern_num)
        if pattern:
            return f"# Patrón MQL5: {pattern_name}\n\n{pattern}"

    # 3. Búsqueda semántica como fallback
    pattern = _search_pattern_semantic(kb_text, query_lower)
    if pattern:
        return f"# Patrón más relevante para: '{pattern_name}'\n\n{pattern}"

    return (
        f"No se encontró patrón para '{pattern_name}'.\n\n"
        f"Patrones disponibles: nueva vela, ema handle, rsi handle, macd, atr, "
        f"cruce de medias, abrir buy/sell, trailing stop, breakeven, "
        f"calcular lote, filtro spread/horario/dia, maximo minimo, "
        f"filtro tendencia, higher high/lower low, manejo errores, normalizar."
    )


def list_patterns() -> str:
    """Lista todos los patrones disponibles."""
    patterns = [
        "01 - Detectar nueva vela en cualquier timeframe",
        "02 - Crear handle de EMA y leer su valor",
        "03 - Crear handle de RSI y leer su valor",
        "04 - Crear handle de MACD y leer líneas",
        "05 - Crear handle de Bollinger Bands",
        "06 - Crear handle de ATR y leer su valor",
        "07 - Detectar cruce de dos EMAs (Golden/Death Cross)",
        "08 - Detectar cruce del precio sobre una EMA",
        "09 - Abrir orden BUY con SL y TP en pips",
        "10 - Abrir orden SELL con SL y TP en pips",
        "11 - Verificar que no hay posición abierta del EA",
        "12 - Cerrar posición abierta del EA por símbolo",
        "13 - Trailing Stop",
        "14 - Breakeven automático",
        "15 - Calcular lote por porcentaje de riesgo",
        "16 - Filtro de spread máximo",
        "17 - Filtro de sesión por horario",
        "18 - Filtro de día de la semana",
        "19 - Leer precio OHLC de velas anteriores",
        "20 - Encontrar máximo y mínimo de N velas",
        "21 - SL dinámico basado en ATR",
        "22 - Filtro de tendencia con EMA larga en D1",
        "23 - Detectar Higher High y Lower Low",
        "24 - Niveles de soporte y resistencia por swing points",
        "25 - Gestión de múltiples posiciones del mismo EA",
        "26 - Profit/Loss flotante de posiciones abiertas",
        "27 - Divergencia RSI básica",
        "28 - Manejo de errores con GetLastError()",
        "29 - Normalización correcta de precios y lotes",
        "30 - Validación completa en OnInit()",
    ]
    return "# Patrones MQL5 disponibles\n\n" + "\n".join(f"- {p}" for p in patterns)
