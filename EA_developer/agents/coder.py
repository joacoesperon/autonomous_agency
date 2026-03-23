"""
agents/coder.py
===============
Coder Agent — convierte diseños de estrategias en código MQL5 correcto.

Flujo interno por cada estrategia:
1. Recibe el diseño estructurado del Designer Agent
2. Consulta el MCP Server para obtener plantilla, patrones y docs
3. Genera el código MQL5 ensamblando piezas conocidas
4. Verifica el código con check_forbidden()
5. Corrige violaciones si las hay
6. Entrega el .mq5 al Compiler Agent
"""

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Agregar raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.llm_client import get_llm_client
from core.database   import get_database

log = logging.getLogger(__name__)

# Paths
PROMPTS_DIR  = Path(__file__).parent.parent / "prompts"
KB_PATH      = Path(__file__).parent.parent / "mql5_mcp_server" / "data" / "mql5_knowledge_base.md"
OUTPUT_DIR   = Path(__file__).parent.parent / "output" / "strategies"
MCP_TOOLS    = Path(__file__).parent.parent / "mql5_mcp_server" / "tools"

# Agregar tools al path para importar directamente
sys.path.insert(0, str(Path(__file__).parent.parent / "mql5_mcp_server"))


# ─────────────────────────────────────────────
# CODER AGENT
# ─────────────────────────────────────────────

class CoderAgent:
    """
    Genera código MQL5 correcto a partir de un diseño de estrategia.
    Usa el MCP Server como fuente de verdad para la sintaxis MQL5.
    """

    def __init__(self):
        self.llm = get_llm_client()
        self.db  = get_database()
        self._system_prompt = self._build_system_prompt()

        # Importar herramientas del MCP Server directamente
        from tools.get_template    import get_template
        from tools.get_pattern     import get_pattern
        from tools.search_docs     import search_docs
        from tools.check_forbidden import check_forbidden

        self._get_template    = get_template
        self._get_pattern     = get_pattern
        self._search_docs     = search_docs
        self._check_forbidden = check_forbidden

        log.info("CoderAgent inicializado")

    def _build_system_prompt(self) -> str:
        """Construye el system prompt con la Knowledge Base embebida."""
        template_path = PROMPTS_DIR / "coder_system.txt"

        if not template_path.exists():
            raise FileNotFoundError(f"No se encontró: {template_path}")
        if not KB_PATH.exists():
            raise FileNotFoundError(f"No se encontró knowledge base: {KB_PATH}")

        template = template_path.read_text(encoding="utf-8")
        kb_text  = KB_PATH.read_text(encoding="utf-8")

        return template.replace("{KNOWLEDGE_BASE}", kb_text)

    # ── Método principal ──────────────────────────────────────────────

    def generate(
        self,
        design: dict,
        cycle_id: Optional[int] = None,
        output_dir: Optional[Path] = None,
    ) -> Optional[Path]:
        """
        Genera el archivo .mq5 para una estrategia diseñada.

        Args:
            design:     Diccionario con el diseño de la estrategia (del Designer Agent)
            cycle_id:   ID del ciclo para logging
            output_dir: Carpeta donde guardar el .mq5 (default: output/strategies/)

        Returns:
            Path al archivo .mq5 generado, o None si falló
        """
        strategy_name = design.get("nombre", "EA_Sin_Nombre")
        log.info(f"[Coder] Generando código para: {strategy_name}")

        # Directorio de output
        save_dir = output_dir or OUTPUT_DIR / "descartadas"
        save_dir.mkdir(parents=True, exist_ok=True)
        mq5_path = save_dir / f"{strategy_name}.mq5"

        # ── PASO 1: Recopilar contexto del MCP Server ──
        context = self._gather_mcp_context(design)

        # ── PASO 2: Construir el prompt de generación ──
        prompt = self._build_generation_prompt(design, context)

        # ── PASO 3: Generar código con el LLM ──
        log.info("[Coder] Generando código MQL5...")
        raw_code = self.llm.flash(
            prompt = prompt,
            system = self._system_prompt,
        )

        # Extraer código limpio (sin markdown si el modelo lo incluyó)
        code = self.llm.extract_code(raw_code, language="cpp")

        # ── PASO 4: Verificar con check_forbidden ──
        log.info("[Coder] Verificando sintaxis MQL5...")
        check_result = self._check_forbidden(code)

        if "VERIFICACIÓN FALLIDA" in check_result:
            log.warning("[Coder] Violaciones MQL4 detectadas, corrigiendo...")
            code = self._fix_forbidden_violations(code, check_result)

        # ── PASO 5: Guardar el archivo ──
        mq5_path.write_text(code, encoding="utf-8")
        log.info(f"[Coder] Archivo guardado: {mq5_path}")

        # Registrar en DB
        if cycle_id:
            self.db.update_cycle(cycle_id,
                current_phase = "compile",
                flash_calls   = self.db.get_cycle(cycle_id).get("flash_calls", 0) + 2,
            )

        return mq5_path

    # ── Recopilar contexto del MCP Server ────────────────────────────

    def _gather_mcp_context(self, design: dict) -> dict:
        """
        Consulta el MCP Server para obtener toda la información
        necesaria antes de generar el código.
        """
        context = {}

        # 1. Plantilla base siempre
        log.info("[Coder→MCP] get_template()")
        context["template"] = self._get_template()

        # 2. Patrones para cada indicador del diseño
        indicadores = design.get("indicadores", [])
        patterns    = []

        for ind in indicadores:
            tipo = ind.get("tipo", "").lower()
            pattern_query = self._indicator_to_pattern(tipo)
            if pattern_query:
                log.info(f"[Coder→MCP] get_pattern('{pattern_query}')")
                pat = self._get_pattern(pattern_query)
                patterns.append(pat)

        # 3. Patrones para la lógica de entrada/salida
        entrada = design.get("entrada_long", "") + " " + design.get("entrada_short", "")

        if "cruce" in entrada.lower() or "cross" in entrada.lower():
            patterns.append(self._get_pattern("cruce de medias"))

        if "atr" in entrada.lower():
            patterns.append(self._get_pattern("sl atr"))

        # 4. Siempre incluir patrones base para swing trading
        patterns.append(self._get_pattern("nueva vela"))
        patterns.append(self._get_pattern("abrir buy"))
        patterns.append(self._get_pattern("abrir sell"))
        patterns.append(self._get_pattern("calcular lote"))
        patterns.append(self._get_pattern("verificar posicion"))

        context["patterns"] = "\n\n---\n\n".join(patterns)

        return context

    def _indicator_to_pattern(self, indicator_type: str) -> Optional[str]:
        """Mapea un tipo de indicador al nombre de patrón correspondiente."""
        mapping = {
            "ema":         "ema handle",
            "sma":         "ema handle",
            "ma":          "ema handle",
            "rsi":         "rsi handle",
            "macd":        "macd handle",
            "bollinger":   "bollinger",
            "bb":          "bollinger",
            "atr":         "atr handle",
            "stochastic":  "rsi handle",   # similar estructura
            "cci":         "rsi handle",
        }
        for key, pattern in mapping.items():
            if key in indicator_type:
                return pattern
        return None

    # ── Construir prompt de generación ───────────────────────────────

    def _build_generation_prompt(self, design: dict, context: dict) -> str:
        """Construye el prompt completo para la generación de código."""

        # Serializar el diseño de forma legible
        design_text = json.dumps(design, ensure_ascii=False, indent=2)

        return f"""Genera el código MQL5 completo para este Expert Advisor de swing trading.

═══════════════════════════════════════
DISEÑO DE LA ESTRATEGIA
═══════════════════════════════════════
{design_text}

═══════════════════════════════════════
PLANTILLA BASE (usar como estructura)
═══════════════════════════════════════
{context.get('template', '')}

═══════════════════════════════════════
PATRONES DE CÓDIGO MQL5 (usar estos fragmentos)
═══════════════════════════════════════
{context.get('patterns', '')}

═══════════════════════════════════════
INSTRUCCIONES
═══════════════════════════════════════
1. Usar la plantilla base como estructura principal
2. Integrar los patrones de código para implementar la lógica
3. Implementar EXACTAMENTE la lógica del diseño
4. Todos los parámetros del diseño deben ser inputs externos (input)
5. Magic number = 100001 por defecto
6. El EA solo opera en EURUSD H4 (hardcoded en comentario, configurable via input)
7. Máximo 1 posición abierta a la vez
8. Incluir comentarios en español explicando cada sección
9. Output: SOLO el código MQL5, sin explicaciones ni markdown
"""

    # ── Corregir violaciones MQL4 ─────────────────────────────────────

    def _fix_forbidden_violations(self, code: str, check_report: str) -> str:
        """
        Pide al LLM que corrija las violaciones MQL4 encontradas por check_forbidden.
        """
        fix_prompt = f"""El siguiente código MQL5 tiene violaciones de sintaxis MQL4 que deben corregirse.

REPORTE DE VIOLACIONES:
{check_report}

CÓDIGO A CORREGIR:
{code}

Corrige ÚNICAMENTE las violaciones listadas.
No cambies ninguna otra parte del código.
Responde SOLO con el código corregido, sin explicaciones ni markdown.
"""
        fixed_raw  = self.llm.flash(prompt=fix_prompt, system=self._system_prompt)
        fixed_code = self.llm.extract_code(fixed_raw, language="cpp")

        # Verificar que la corrección no introdujo nuevas violaciones
        from tools.check_forbidden import check_forbidden
        second_check = check_forbidden(fixed_code)
        if "VERIFICACIÓN PASADA" in second_check:
            log.info("[Coder] Violaciones corregidas exitosamente")
        else:
            log.warning("[Coder] Aún hay violaciones después de la corrección")

        return fixed_code


# ─────────────────────────────────────────────
# TEST RÁPIDO
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Diseño de ejemplo (normalmente viene del Designer Agent)
    diseño_test = {
        "nombre": "EMA50_200_RSI_Test",
        "indicadores": [
            {"tipo": "EMA", "periodo": 50,  "timeframe": "H4"},
            {"tipo": "EMA", "periodo": 200, "timeframe": "H4"},
            {"tipo": "RSI", "periodo": 14,  "timeframe": "H4"},
        ],
        "entrada_long":  "EMA50 cruza EMA200 hacia arriba Y RSI > 50",
        "entrada_short": "EMA50 cruza EMA200 hacia abajo Y RSI < 50",
        "salida":        "SL 50 pips, TP 150 pips",
        "filtros":       ["Spread < 20 pips", "Solo Lunes a Jueves"],
        "parametros_externos": [
            {"nombre": "EMA_Rapida",  "tipo": "int",    "default": 50},
            {"nombre": "EMA_Lenta",   "tipo": "int",    "default": 200},
            {"nombre": "RSI_Periodo", "tipo": "int",    "default": 14},
            {"nombre": "RSI_Nivel",   "tipo": "double", "default": 50.0},
            {"nombre": "SL_Pips",     "tipo": "double", "default": 50.0},
            {"nombre": "TP_Pips",     "tipo": "double", "default": 150.0},
            {"nombre": "Riesgo_Porc", "tipo": "double", "default": 1.0},
        ]
    }

    print("Probando CoderAgent...")
    coder  = CoderAgent()
    output = coder.generate(diseño_test)

    if output and output.exists():
        print(f"\n✅ Código generado: {output}")
        print(f"   Tamaño: {output.stat().st_size} bytes")
        print("\nPrimeras 20 líneas:")
        lines = output.read_text(encoding="utf-8").splitlines()
        for line in lines[:20]:
            print(f"  {line}")
    else:
        print("❌ No se generó el código")
