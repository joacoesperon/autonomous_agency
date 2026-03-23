"""
agents/designer.py
==================
Designer Agent — convierte ideas de estrategias en diseños técnicos estructurados.

Recibe una idea del Research Agent (o del Orchestrator directamente)
y produce un JSON de diseño que el Coder Agent puede implementar.

Flujo:
1. Recibe idea de estrategia (texto libre)
2. Verifica que no es demasiado similar a diseños anteriores
3. Genera el diseño técnico estructurado (JSON)
4. Valida que el JSON es completo y coherente
5. Retorna el diseño listo para el Coder
"""

import json
import logging
import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.llm_client import get_llm_client
from core.database   import get_database
from core.memory     import get_memory

log = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


# ─────────────────────────────────────────────
# DESIGNER AGENT
# ─────────────────────────────────────────────

class DesignerAgent:
    """
    Convierte ideas de estrategias en diseños técnicos estructurados.
    Output: diccionario JSON listo para el Coder Agent.
    """

    def __init__(self):
        self.llm    = get_llm_client()
        self.db     = get_database()
        self.memory = get_memory()
        self._system_prompt = self._load_system_prompt()
        log.info("DesignerAgent inicializado")

    def _load_system_prompt(self) -> str:
        path = PROMPTS_DIR / "designer_system.txt"
        if not path.exists():
            raise FileNotFoundError(f"No se encontró: {path}")
        return path.read_text(encoding="utf-8")

    # ── Método principal ──────────────────────────────────────────────

    def design(
        self,
        idea: str,
        cycle_id: Optional[int] = None,
        strategy_type: str = "tendencia",
    ) -> Optional[dict]:
        """
        Genera el diseño técnico de una estrategia.

        Args:
            idea:          Descripción libre de la idea de estrategia
            cycle_id:      ID del ciclo para logging
            strategy_type: 'tendencia', 'reversion', 'momentum'

        Returns:
            Diccionario con el diseño completo, o None si falló
        """
        log.info(f"[Designer] Diseñando estrategia: {idea[:80]}...")

        # ── Verificar duplicado ──
        similarity = self.memory.similarity_score(idea)
        if similarity > 0.85:
            similar = self.memory.get_similar_strategies(idea, n=1)
            similar_name = similar[0]["strategy_name"] if similar else "desconocida"
            log.warning(
                f"[Designer] Idea muy similar a '{similar_name}' "
                f"(similitud: {similarity:.0%}) — descartando"
            )
            if cycle_id:
                self.db.update_cycle(cycle_id,
                    status        = "descartado",
                    discard_reason = f"Idea duplicada: similar a '{similar_name}' ({similarity:.0%})"
                )
            return None

        # ── Generar diseño ──
        prompt = self._build_prompt(idea, strategy_type)

        log.info("[Designer] Generando diseño técnico...")
        raw_response = self.llm.flash(
            prompt = prompt,
            system = self._system_prompt,
        )

        # ── Parsear JSON ──
        design = self._parse_json(raw_response)
        if not design:
            log.error("[Designer] No se pudo parsear el JSON de diseño")
            if cycle_id:
                self.db.update_cycle(cycle_id,
                    status        = "error",
                    discard_reason = "Designer no generó JSON válido"
                )
            return None

        # ── Validar diseño ──
        validation_error = self._validate(design)
        if validation_error:
            log.warning(f"[Designer] Diseño inválido: {validation_error} — corrigiendo...")
            design = self._fix_design(design, validation_error)
            if not design:
                return None

        # ── Guardar en memoria y DB ──
        self.memory.save_strategy_idea(
            idea          = idea,
            strategy_name = design.get("nombre", ""),
            cycle_id      = cycle_id,
            approved      = False,
        )

        if cycle_id:
            self.db.update_cycle(cycle_id,
                strategy_name = design.get("nombre", ""),
                strategy_type = design.get("tipo", strategy_type),
                current_phase = "code",
                design_json   = json.dumps(design, ensure_ascii=False),
                flash_calls   = self.db.get_cycle(cycle_id).get("flash_calls", 0) + 1,
            )

        log.info(f"[Designer] ✅ Diseño generado: {design.get('nombre')}")
        return design

    # ── Construir prompt ──────────────────────────────────────────────

    def _build_prompt(self, idea: str, strategy_type: str) -> str:
        """Construye el prompt de diseño con contexto de estrategias previas."""

        # Obtener nombres de estrategias ya generadas para evitar repetición
        existing = self.db.get_strategy_names()
        existing_text = ""
        if existing:
            existing_text = (
                f"\n\nESTRATEGIAS YA GENERADAS (no repetir combinaciones similares):\n"
                + "\n".join(f"- {n}" for n in existing[-10:])  # últimas 10
            )

        return f"""Diseña una estrategia de swing trading H4 basada en esta idea:

IDEA: {idea}
TIPO: {strategy_type}
{existing_text}

Genera el JSON de diseño técnico completo siguiendo el formato indicado.
La estrategia debe ser implementable en MQL5 con indicadores estándar.
Responde SOLO con el JSON, sin texto adicional ni markdown.
"""

    # ── Parsear JSON ──────────────────────────────────────────────────

    def _parse_json(self, text: str) -> Optional[dict]:
        """Extrae y parsea el JSON de la respuesta del LLM."""

        # Intentar parsear directamente
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # Buscar bloque JSON entre ```json ... ``` o ``` ... ```
        for pattern in [r"```json\s*\n(.*?)```", r"```\s*\n(.*?)```"]:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1).strip())
                except json.JSONDecodeError:
                    pass

        # Buscar el primer { ... } en el texto
        start = text.find("{")
        end   = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

        log.error(f"[Designer] No se pudo parsear JSON. Respuesta: {text[:200]}")
        return None

    # ── Validar diseño ────────────────────────────────────────────────

    def _validate(self, design: dict) -> Optional[str]:
        """
        Valida que el diseño tiene todos los campos necesarios.
        Retorna None si es válido, o mensaje de error si no.
        """
        required_fields = [
            "nombre", "tipo", "indicadores",
            "entrada_long", "entrada_short", "salida",
            "sl_tipo", "sl_valor", "tp_tipo", "tp_valor",
            "parametros_externos"
        ]

        for field in required_fields:
            if field not in design:
                return f"Campo faltante: '{field}'"
            if design[field] is None or design[field] == "":
                return f"Campo vacío: '{field}'"

        # Validar ratio riesgo/recompensa mínimo 1:2
        if design.get("sl_tipo") == design.get("tp_tipo"):
            sl = float(design.get("sl_valor", 0))
            tp = float(design.get("tp_valor", 0))
            if sl > 0 and tp > 0 and tp < sl * 1.5:
                return f"Ratio R/R insuficiente: SL={sl} TP={tp} (mínimo 1:2)"

        # Validar que hay al menos un indicador
        if not design.get("indicadores") or len(design["indicadores"]) == 0:
            return "No hay indicadores definidos"

        # Validar nombre sin espacios
        nombre = design.get("nombre", "")
        if " " in nombre:
            design["nombre"] = nombre.replace(" ", "_")

        return None

    # ── Corregir diseño ───────────────────────────────────────────────

    def _fix_design(self, design: dict, error: str) -> Optional[dict]:
        """Pide al LLM que corrija un diseño con problemas."""

        fix_prompt = f"""El siguiente diseño de estrategia tiene un problema:

PROBLEMA: {error}

DISEÑO ACTUAL:
{json.dumps(design, ensure_ascii=False, indent=2)}

Corrige el problema y devuelve el JSON completo corregido.
Responde SOLO con el JSON corregido, sin explicaciones.
"""
        raw = self.llm.flash(prompt=fix_prompt, system=self._system_prompt)
        fixed = self._parse_json(raw)

        if fixed:
            # Verificar que la corrección resolvió el problema
            remaining_error = self._validate(fixed)
            if remaining_error:
                log.error(f"[Designer] No se pudo corregir: {remaining_error}")
                return None
            log.info("[Designer] Diseño corregido exitosamente")

        return fixed


# ─────────────────────────────────────────────
# CATÁLOGO DE IDEAS BASE
# ─────────────────────────────────────────────

# Ideas predefinidas para que el Orchestrator tenga variedad
# El Research Agent puede agregar más ideas desde fuentes externas

STRATEGY_IDEAS_CATALOG = [
    # Tendencia
    ("EMA 50/200 crossover en H4 con filtro de tendencia en D1 usando EMA 200", "tendencia"),
    ("MACD crossover en H4 con histograma creciente y precio sobre EMA 100", "tendencia"),
    ("Precio cruza EMA 21 en H4 confirmado por ADX mayor a 25", "tendencia"),
    ("Triple EMA: EMA 10 cruza EMA 30, ambas sobre EMA 100 en H4", "tendencia"),
    ("Bollinger Bands squeeze seguido de breakout en H4 con volumen", "momentum"),

    # Reversión
    ("RSI en sobreventa/sobrecompra extrema en H4 con confirmación en D1", "reversion"),
    ("Precio toca banda exterior Bollinger con RSI divergente en H4", "reversion"),
    ("Stochastic crossover en zona extrema con EMA como filtro de tendencia", "reversion"),
    ("CCI vuelve a cruzar cero desde extremos con precio en soporte/resistencia", "reversion"),

    # Momentum
    ("RSI cruza nivel 50 con MACD en la misma dirección en H4", "momentum"),
    ("MACD positivo con EMA 50 sobre EMA 200 y RSI entre 50 y 70", "momentum"),
    ("Precio hace Higher High con RSI también en Higher High en H4", "momentum"),
]


# ─────────────────────────────────────────────
# TEST RÁPIDO
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Probando DesignerAgent...\n")
    designer = DesignerAgent()

    idea = "EMA 50 cruza EMA 200 hacia arriba en H4, con RSI mayor a 50 como filtro de momentum"

    print(f"Idea: {idea}\n")
    design = designer.design(idea, strategy_type="tendencia")

    if design:
        print("✅ Diseño generado:\n")
        print(json.dumps(design, ensure_ascii=False, indent=2))
    else:
        print("❌ No se generó el diseño")
