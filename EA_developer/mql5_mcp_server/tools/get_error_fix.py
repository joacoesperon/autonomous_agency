"""
Tool: get_error_fix
Busca en la base de errores de compilación MQL5 y retorna el fix documentado.
"""

import json
import re
from pathlib import Path


def _load_error_fixes() -> list[dict]:
    fixes_path = Path(__file__).parent.parent / "data" / "error_fixes.json"
    if not fixes_path.exists():
        return []
    return json.loads(fixes_path.read_text(encoding="utf-8"))


def get_error_fix(error_message: str) -> str:
    """
    Busca el fix para un error de compilación de MT5/MQL5.

    Args:
        error_message: Mensaje de error exacto del compilador de MT5
                      Ej: "error 31: 'Ask' - undeclared identifier"
                      Ej: "error 130: invalid stops"

    Returns:
        Causa del error, fix detallado y ejemplo de código correcto
    """
    fixes = _load_error_fixes()
    if not fixes:
        return "ERROR: No se encontró la base de errores. Verificar error_fixes.json"

    error_lower = error_message.lower()

    # Buscar coincidencias en los patrones
    best_match = None
    best_score = 0

    for fix in fixes:
        pattern_lower = fix["pattern"].lower()
        pattern_words = set(pattern_lower.split())
        error_words   = set(error_lower.split())

        # Puntuación por palabras en común
        score = len(pattern_words & error_words)

        # Bonus si el patrón aparece como substring del error
        if pattern_lower in error_lower:
            score += 10

        if score > best_score:
            best_score = score
            best_match = fix

    if not best_match or best_score == 0:
        return (
            f"No se encontró un fix específico para:\n'{error_message}'\n\n"
            f"Sugerencias generales:\n"
            f"1. Verificar que no hay variables MQL4 (Ask, Bid, Point, Digits)\n"
            f"2. Verificar que los handles de indicadores son válidos (INVALID_HANDLE)\n"
            f"3. Verificar que ArraySetAsSeries() se llamó antes de CopyBuffer()\n"
            f"4. Verificar que el include <Trade\\Trade.mqh> está presente\n"
            f"5. Buscar el código de error en: https://www.mql5.com/en/docs/constants/errorswarnings"
        )

    return (
        f"# Fix para: '{error_message}'\n\n"
        f"**Causa:** {best_match['cause']}\n\n"
        f"**Fix:** {best_match['fix']}\n\n"
        f"**Ejemplo correcto:**\n```cpp\n{best_match['example']}\n```"
    )
