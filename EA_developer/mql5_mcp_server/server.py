"""
MQL5 MCP Server — Fase 3
=========================
Servidor MCP que expone conocimiento de MQL5 a los agentes del sistema.
Los agentes lo consultan ANTES de generar código para asegurar sintaxis correcta.

Inicio:
    python server.py

El servidor corre en background en localhost:8765
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path para imports
sys.path.insert(0, str(Path(__file__).parent))

from fastmcp import FastMCP
from tools.search_docs    import search_docs    as _search_docs
from tools.get_function   import get_function   as _get_function
from tools.get_pattern    import get_pattern    as _get_pattern, list_patterns as _list_patterns
from tools.get_template   import get_template   as _get_template
from tools.check_forbidden import check_forbidden as _check_forbidden
from tools.get_error_fix  import get_error_fix  as _get_error_fix

# ─────────────────────────────────────────────
# Inicializar servidor MCP
# ─────────────────────────────────────────────

mcp = FastMCP(
    name        = "MQL5 Knowledge Server",
    description = (
        "Servidor de conocimiento MQL5 para generación de Expert Advisors correctos. "
        "Provee documentación oficial, patrones de código probados, plantilla base, "
        "detección de errores MQL4 y fixes de compilación. "
        "Consultar SIEMPRE antes de generar código MQL5."
    )
)

# ─────────────────────────────────────────────
# HERRAMIENTA 1: search_docs
# ─────────────────────────────────────────────

@mcp.tool()
def search_docs(query: str, n_results: int = 3, section_filter: str = "") -> str:
    """
    Busca en la documentación oficial de MQL5 usando búsqueda semántica.
    Usar cuando se necesita saber cómo funciona algo en MQL5.

    Args:
        query:          Pregunta en lenguaje natural. Ej: "how to open a buy order",
                        "moving average indicator handle", "get account balance"
        n_results:      Número de resultados a retornar (default: 3, máx: 5)
        section_filter: Opcional. Filtrar por sección: 'trading', 'indicators',
                        'series', 'marketinformation', 'account', 'array', 'math'

    Returns:
        Documentación relevante con firmas, parámetros y ejemplos de código oficial
    """
    n_results = min(max(1, n_results), 5)
    return _search_docs(
        query         = query,
        n_results     = n_results,
        section_filter = section_filter if section_filter else None,
    )


# ─────────────────────────────────────────────
# HERRAMIENTA 2: get_function
# ─────────────────────────────────────────────

@mcp.tool()
def get_function(function_name: str) -> str:
    """
    Retorna la documentación completa de una función MQL5 específica.
    Usar cuando se conoce el nombre exacto de la función que se necesita.

    Args:
        function_name: Nombre de la función. Ej: 'iMA', 'CopyBuffer', 'PositionsTotal',
                       'AccountInfoDouble', 'SymbolInfoDouble', 'NormalizeDouble'

    Returns:
        Documentación completa: firma exacta, parámetros, valor de retorno y ejemplo
    """
    return _get_function(function_name)


# ─────────────────────────────────────────────
# HERRAMIENTA 3: get_pattern
# ─────────────────────────────────────────────

@mcp.tool()
def get_pattern(pattern_name: str) -> str:
    """
    Retorna un fragmento de código MQL5 probado para un patrón de programación común.
    Usar para obtener código correcto en lugar de generarlo desde cero.
    SIEMPRE preferir estos patrones por sobre generar código nuevo.

    Args:
        pattern_name: Nombre o descripción del patrón. Ejemplos:
            - 'nueva vela' / 'new bar detection'
            - 'ema handle' / 'moving average'
            - 'rsi handle'
            - 'macd handle'
            - 'atr handle'
            - 'cruce de medias' / 'crossover'
            - 'abrir buy' / 'buy order'
            - 'abrir sell' / 'sell order'
            - 'trailing stop'
            - 'breakeven'
            - 'calcular lote' / 'lot size' / 'position size'
            - 'filtro spread'
            - 'filtro horario' / 'session filter'
            - 'filtro dia' / 'day filter'
            - 'precio cierre' / 'ohlc'
            - 'maximo minimo' / 'highest lowest'
            - 'sl atr' / 'stop loss atr'
            - 'filtro tendencia' / 'trend filter'
            - 'higher high lower low'
            - 'soporte resistencia' / 'swing point'
            - 'multiples posiciones'
            - 'profit flotante'
            - 'divergencia rsi'
            - 'manejo errores'
            - 'normalizar'
            - 'validacion oninit'

    Returns:
        Fragmento de código MQL5 completo, comentado y listo para integrar
    """
    return _get_pattern(pattern_name)


@mcp.tool()
def list_patterns() -> str:
    """
    Lista todos los patrones de código MQL5 disponibles con sus descripciones.
    Usar para ver qué patrones existen antes de pedirlos con get_pattern.

    Returns:
        Lista numerada de todos los patrones disponibles
    """
    return _list_patterns()


# ─────────────────────────────────────────────
# HERRAMIENTA 4: get_template
# ─────────────────────────────────────────────

@mcp.tool()
def get_template() -> str:
    """
    Retorna la plantilla base completa de un EA MQL5 para swing trading H4.
    USAR SIEMPRE como punto de partida al generar un nuevo EA.
    La plantilla incluye toda la estructura correcta: includes, globals,
    OnInit, OnDeinit, OnTick, y funciones auxiliares estándar.

    Returns:
        Código MQL5 completo de la plantilla base (~200 líneas)
    """
    return _get_template()


# ─────────────────────────────────────────────
# HERRAMIENTA 5: check_forbidden
# ─────────────────────────────────────────────

@mcp.tool()
def check_forbidden(code: str) -> str:
    """
    Verifica que el código MQL5 no contiene construcciones prohibidas de MQL4.
    USAR SIEMPRE después de generar código y ANTES de enviarlo a compilar.

    Detecta: Bid/Ask como variables, funciones de cuenta MQL4 (AccountBalance etc),
    funciones de órdenes MQL4 (OrdersTotal, OrderSelect etc),
    indicadores con sintaxis NULL (iMA(NULL,...)), RefreshRates(), y más.

    Args:
        code: Código MQL5 completo a verificar

    Returns:
        '✅ VERIFICACIÓN PASADA' si no hay problemas, o lista detallada de
        violaciones con número de línea y fix sugerido para cada una
    """
    return _check_forbidden(code)


# ─────────────────────────────────────────────
# HERRAMIENTA 6: get_error_fix
# ─────────────────────────────────────────────

@mcp.tool()
def get_error_fix(error_message: str) -> str:
    """
    Busca el fix documentado para un error de compilación de MT5.
    Usar en el self-healing loop cuando el compilador retorna un error.

    Args:
        error_message: Mensaje de error exacto del compilador MT5.
                      Ejemplos:
                      - "error 31: 'Ask' - undeclared identifier"
                      - "error 29: 'OrderSend' - wrong parameters count"
                      - "error 130: invalid stops"
                      - "unsupported filling mode"
                      - "invalid handle"
                      - "array out of range"

    Returns:
        Causa del error, fix detallado con explicación, y ejemplo de código correcto
    """
    return _get_error_fix(error_message)


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("MQL5 Knowledge MCP Server")
    print("=" * 50)
    print("Herramientas disponibles:")
    print("  1. search_docs     — búsqueda semántica en docs oficiales")
    print("  2. get_function    — ficha completa de una función")
    print("  3. get_pattern     — fragmento de código probado")
    print("  4. list_patterns   — lista de patrones disponibles")
    print("  5. get_template    — plantilla base del EA")
    print("  6. check_forbidden — detector de sintaxis MQL4")
    print("  7. get_error_fix   — fix para errores de compilación")
    print("=" * 50)
    print("Iniciando servidor...")

    mcp.run()
