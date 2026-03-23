"""
Tool: get_template
Retorna la plantilla base completa de un EA MQL5 para swing trading H4.
"""

import re
from pathlib import Path


def get_template() -> str:
    """
    Retorna la plantilla base completa de un EA MQL5 correcto.
    Esta plantilla debe usarse siempre como punto de partida.

    Returns:
        Código MQL5 de la plantilla base completa (~200 líneas)
    """
    kb_path = Path(__file__).parent.parent / "data" / "mql5_knowledge_base.md"
    if not kb_path.exists():
        return "ERROR: No se encontró el archivo de knowledge base."

    kb_text = kb_path.read_text(encoding="utf-8")

    # Extraer el bloque de la plantilla base (Bloque 2)
    start = kb_text.find("## BLOQUE 2 — Plantilla Base EA Swing Trading H4")
    end   = kb_text.find("## BLOQUE 3 —")

    if start == -1 or end == -1:
        return "ERROR: No se encontró la plantilla base en el knowledge base."

    bloque2 = kb_text[start:end].strip()

    # Extraer solo el bloque de código MQL5 (entre ```cpp y ```)
    code_match = re.search(r"```cpp\n(.*?)```", bloque2, re.DOTALL)
    if code_match:
        template_code = code_match.group(1).strip()
        return (
            "# Plantilla Base EA MQL5 — Swing Trading H4\n\n"
            "INSTRUCCIONES:\n"
            "1. Usar esta plantilla como estructura base\n"
            "2. Mantener todos los includes y declaraciones globales\n"
            "3. Agregar los handles de indicadores específicos de la estrategia\n"
            "4. Reemplazar la lógica de entrada/salida con la estrategia diseñada\n"
            "5. NO modificar la estructura de OnInit/OnDeinit/OnTick\n\n"
            f"```cpp\n{template_code}\n```"
        )

    return bloque2
