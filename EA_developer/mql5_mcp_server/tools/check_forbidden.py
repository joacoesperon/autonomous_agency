"""
Tool: check_forbidden
Escanea código MQL5 buscando funciones y variables de MQL4 prohibidas.
Es la última línea de defensa antes de enviar el código al compilador.
"""

from dataclasses import dataclass


@dataclass
class Violation:
    line_number: int
    line_content: str
    forbidden:   str
    replacement: str
    severity:    str  # "error" = no compila, "warning" = compila pero incorrecto


# Mapa completo de prohibiciones: patrón → (reemplazo, severidad)
FORBIDDEN_PATTERNS = {
    # Variables globales eliminadas
    r"\bAsk\b":          ("SymbolInfoDouble(_Symbol, SYMBOL_ASK)", "error"),
    r"\bBid\b":          ("SymbolInfoDouble(_Symbol, SYMBOL_BID)", "error"),
    r"\bPoint\b":        ("_Point", "error"),
    r"\bDigits\b":       ("_Digits", "error"),
    r"\bBars\b(?!\s*\()": ("Bars(_Symbol, _Period)", "warning"),

    # Funciones de cuenta MQL4
    r"\bAccountBalance\s*\(\s*\)":    ("AccountInfoDouble(ACCOUNT_BALANCE)", "error"),
    r"\bAccountEquity\s*\(\s*\)":     ("AccountInfoDouble(ACCOUNT_EQUITY)", "error"),
    r"\bAccountFreeMargin\s*\(\s*\)": ("AccountInfoDouble(ACCOUNT_MARGIN_FREE)", "error"),
    r"\bAccountLeverage\s*\(\s*\)":   ("AccountInfoInteger(ACCOUNT_LEVERAGE)", "error"),
    r"\bAccountProfit\s*\(\s*\)":     ("AccountInfoDouble(ACCOUNT_PROFIT)", "error"),

    # Funciones de órdenes MQL4
    r"\bOrdersTotal\s*\(\s*\)":       ("PositionsTotal()", "error"),
    r"\bOrderSelect\s*\(":            ("posInfo.SelectByIndex(i)", "error"),
    r"\bOrderLots\s*\(\s*\)":         ("PositionGetDouble(POSITION_VOLUME)", "error"),
    r"\bOrderProfit\s*\(\s*\)":       ("PositionGetDouble(POSITION_PROFIT)", "error"),
    r"\bOrderSymbol\s*\(\s*\)":       ("PositionGetString(POSITION_SYMBOL)", "error"),
    r"\bOrderType\s*\(\s*\)":         ("PositionGetInteger(POSITION_TYPE)", "error"),
    r"\bOrderMagicNumber\s*\(\s*\)":  ("PositionGetInteger(POSITION_MAGIC)", "error"),
    r"\bOrderOpenPrice\s*\(\s*\)":    ("PositionGetDouble(POSITION_PRICE_OPEN)", "error"),
    r"\bOrderStopLoss\s*\(\s*\)":     ("PositionGetDouble(POSITION_SL)", "error"),
    r"\bOrderTakeProfit\s*\(\s*\)":   ("PositionGetDouble(POSITION_TP)", "error"),
    r"\bOrderTicket\s*\(\s*\)":       ("PositionGetInteger(POSITION_TICKET)", "error"),
    r"\bOrderComment\s*\(\s*\)":      ("PositionGetString(POSITION_COMMENT)", "error"),
    r"\bOrderClose\s*\(":             ("trade.PositionClose(ticket)", "error"),

    # Funciones de mercado MQL4
    r"\bMarketInfo\s*\(":             ("SymbolInfoDouble/Integer/String()", "error"),
    r"\bRefreshRates\s*\(\s*\)":      ("(eliminar, no es necesario en MQL5)", "error"),

    # Indicadores con sintaxis MQL4 (NULL como primer parámetro)
    r"\biMA\s*\(\s*NULL":             ("iMA(_Symbol, PERIOD_H4, ...)", "error"),
    r"\biRSI\s*\(\s*NULL":            ("iRSI(_Symbol, PERIOD_H4, ...)", "error"),
    r"\biMACD\s*\(\s*NULL":           ("iMACD(_Symbol, PERIOD_H4, ...)", "error"),
    r"\biBands\s*\(\s*NULL":          ("iBands(_Symbol, PERIOD_H4, ...)", "error"),
    r"\biATR\s*\(\s*NULL":            ("iATR(_Symbol, PERIOD_H4, ...)", "error"),
    r"\biStochastic\s*\(\s*NULL":     ("iStochastic(_Symbol, PERIOD_H4, ...)", "error"),
    r"\biCCI\s*\(\s*NULL":            ("iCCI(_Symbol, PERIOD_H4, ...)", "error"),

    # Patrones peligrosos
    r"\bSleep\s*\(":                  ("(no usar Sleep en OnTick, congela el terminal)", "warning"),
}


def check_forbidden(code: str) -> str:
    """
    Escanea código MQL5 buscando construcciones prohibidas de MQL4.

    Args:
        code: Código MQL5 a verificar (string completo del archivo .mq5)

    Returns:
        Reporte de violaciones encontradas con línea, problema y fix sugerido.
        Si no hay violaciones, confirma que el código pasó la verificación.
    """
    import re

    lines      = code.split("\n")
    violations = []

    for line_num, line in enumerate(lines, 1):
        # Saltar líneas de comentarios
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue

        for pattern, (replacement, severity) in FORBIDDEN_PATTERNS.items():
            if re.search(pattern, line):
                violations.append(Violation(
                    line_number  = line_num,
                    line_content = line.rstrip(),
                    forbidden    = pattern.replace(r"\b", "").replace(r"\s*\(", "()").replace(r"\s*\)\s*", "()"),
                    replacement  = replacement,
                    severity     = severity,
                ))

    if not violations:
        return (
            "✅ VERIFICACIÓN PASADA\n"
            "No se encontraron construcciones MQL4 prohibidas.\n"
            "El código puede proceder a compilación."
        )

    # Separar errores de warnings
    errors   = [v for v in violations if v.severity == "error"]
    warnings = [v for v in violations if v.severity == "warning"]

    lines_out = [
        f"❌ VERIFICACIÓN FALLIDA — {len(violations)} violación(es) encontrada(s)\n",
        f"Errores críticos (no compilarán): {len(errors)}",
        f"Warnings (pueden compilar pero son incorrectos): {len(warnings)}\n",
    ]

    if errors:
        lines_out.append("## ERRORES CRÍTICOS (corregir obligatoriamente)\n")
        for v in errors:
            lines_out.append(f"Línea {v.line_number}: {v.line_content.strip()}")
            lines_out.append(f"  Problema:   '{v.forbidden}' es sintaxis MQL4")
            lines_out.append(f"  Reemplazar: {v.replacement}\n")

    if warnings:
        lines_out.append("## WARNINGS (corregir recomendado)\n")
        for v in warnings:
            lines_out.append(f"Línea {v.line_number}: {v.line_content.strip()}")
            lines_out.append(f"  Atención:   '{v.forbidden}'")
            lines_out.append(f"  Sugerencia: {v.replacement}\n")

    lines_out.append("Corregir todos los errores críticos antes de compilar.")
    return "\n".join(lines_out)
