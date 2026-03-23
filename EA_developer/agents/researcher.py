"""
agents/researcher.py
====================
Research Agent — genera ideas de estrategias de trading algorítmico.

Dos modos de operación:
1. CATÁLOGO: usa ideas predefinidas (sin internet, siempre disponible)
2. WEB: genera ideas basadas en conceptos de trading con el LLM

El Research Agent no hace web scraping real para evitar dependencias frágiles.
En su lugar usa el LLM para generar ideas variadas y originales basadas
en su conocimiento de literatura de trading y estrategias cuantitativas.

Flujo:
1. Consulta la DB para ver qué tipos de estrategias ya se generaron
2. Selecciona un tipo de estrategia poco explorado
3. Genera ideas via LLM (o desde catálogo)
4. Filtra por originalidad vs memoria de ChromaDB
5. Retorna la mejor idea para el Designer
"""

import json
import logging
import random
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
# CATÁLOGO DE IDEAS BASE
# ─────────────────────────────────────────────

IDEAS_CATALOG = [
    # ── Tendencia ──
    {
        "titulo":      "EMA Golden Cross con Filtro ADX",
        "descripcion": "Cruce alcista/bajista de EMA 50/200 en H4, solo operar cuando ADX > 25 confirma tendencia fuerte",
        "tipo":        "tendencia",
        "indicadores": ["EMA", "ADX"],
        "timeframe":   "H4",
        "originalidad": 0.70,
        "viabilidad":  0.95,
        "fuente":      "catálogo base",
    },
    {
        "titulo":      "Triple EMA Alignment",
        "descripcion": "Entrar cuando EMA 10, EMA 30 y EMA 100 están alineadas en la misma dirección en H4",
        "tipo":        "tendencia",
        "indicadores": ["EMA"],
        "timeframe":   "H4",
        "originalidad": 0.72,
        "viabilidad":  0.90,
        "fuente":      "catálogo base",
    },
    {
        "titulo":      "MACD Crossover con Tendencia D1",
        "descripcion": "Cruce de líneas MACD en H4 confirmado por precio sobre EMA 200 en D1",
        "tipo":        "tendencia",
        "indicadores": ["MACD", "EMA"],
        "timeframe":   "H4",
        "originalidad": 0.68,
        "viabilidad":  0.92,
        "fuente":      "catálogo base",
    },
    {
        "titulo":      "EMA Price Action con ATR",
        "descripcion": "Precio cruza EMA 21 en H4 con SL dinámico de 2xATR y TP de 4xATR",
        "tipo":        "tendencia",
        "indicadores": ["EMA", "ATR"],
        "timeframe":   "H4",
        "originalidad": 0.75,
        "viabilidad":  0.93,
        "fuente":      "catálogo base",
    },

    # ── Reversión ──
    {
        "titulo":      "RSI Extremo con Confirmación EMA",
        "descripcion": "RSI < 30 o > 70 en H4, entrar solo si precio está cerca de EMA 200 como soporte/resistencia",
        "tipo":        "reversion",
        "indicadores": ["RSI", "EMA"],
        "timeframe":   "H4",
        "originalidad": 0.73,
        "viabilidad":  0.91,
        "fuente":      "catálogo base",
    },
    {
        "titulo":      "Bollinger Bands Mean Reversion",
        "descripcion": "Precio toca banda exterior de BB(20,2) en H4 y RSI diverge, entrar hacia la media",
        "tipo":        "reversion",
        "indicadores": ["BB", "RSI"],
        "timeframe":   "H4",
        "originalidad": 0.78,
        "viabilidad":  0.88,
        "fuente":      "catálogo base",
    },
    {
        "titulo":      "Stochastic Oversold con Tendencia",
        "descripcion": "Stochastic < 20 en H4 con precio sobre EMA 100, señal de compra en cruce del Stochastic",
        "tipo":        "reversion",
        "indicadores": ["Stochastic", "EMA"],
        "timeframe":   "H4",
        "originalidad": 0.71,
        "viabilidad":  0.89,
        "fuente":      "catálogo base",
    },

    # ── Momentum ──
    {
        "titulo":      "RSI Momentum Breakout",
        "descripcion": "RSI cruza nivel 50 hacia arriba/abajo con MACD en la misma dirección en H4",
        "tipo":        "momentum",
        "indicadores": ["RSI", "MACD"],
        "timeframe":   "H4",
        "originalidad": 0.76,
        "viabilidad":  0.90,
        "fuente":      "catálogo base",
    },
    {
        "titulo":      "CCI Momentum con EMA Filter",
        "descripcion": "CCI cruza cero desde zona negativa/positiva en H4, filtro de tendencia con EMA 50/200",
        "tipo":        "momentum",
        "indicadores": ["CCI", "EMA"],
        "timeframe":   "H4",
        "originalidad": 0.80,
        "viabilidad":  0.87,
        "fuente":      "catálogo base",
    },
    {
        "titulo":      "Bollinger Bands Squeeze Breakout",
        "descripcion": "Detectar contracción de BB (squeeze) en H4 y entrar en la dirección del breakout",
        "tipo":        "momentum",
        "indicadores": ["BB", "ATR"],
        "timeframe":   "H4",
        "originalidad": 0.82,
        "viabilidad":  0.85,
        "fuente":      "catálogo base",
    },

    # ── Breakout ──
    {
        "titulo":      "Higher High / Lower Low Breakout",
        "descripcion": "Entrar cuando precio supera el máximo/mínimo de las últimas 20 velas H4 con ADX > 20",
        "tipo":        "breakout",
        "indicadores": ["ADX"],
        "timeframe":   "H4",
        "originalidad": 0.77,
        "viabilidad":  0.86,
        "fuente":      "catálogo base",
    },
    {
        "titulo":      "Donchian Channel Breakout",
        "descripcion": "Precio rompe el canal de máximos/mínimos de 20 períodos en H4, confirmado por RSI > 50",
        "tipo":        "breakout",
        "indicadores": ["RSI"],
        "timeframe":   "H4",
        "originalidad": 0.83,
        "viabilidad":  0.84,
        "fuente":      "catálogo base",
    },

    # ── Multi-timeframe ──
    {
        "titulo":      "D1 Trend H4 Entry",
        "descripcion": "Tendencia definida por EMA 50/200 en D1, entrada en retroceso a EMA 21 en H4",
        "tipo":        "tendencia",
        "indicadores": ["EMA"],
        "timeframe":   "H4",
        "originalidad": 0.79,
        "viabilidad":  0.88,
        "fuente":      "catálogo base",
    },
    {
        "titulo":      "RSI Divergence Multi-TF",
        "descripcion": "Divergencia alcista/bajista de RSI en H4 confirmada por misma dirección en D1",
        "tipo":        "reversion",
        "indicadores": ["RSI", "EMA"],
        "timeframe":   "H4",
        "originalidad": 0.85,
        "viabilidad":  0.83,
        "fuente":      "catálogo base",
    },
]

# Tipos de estrategia disponibles
STRATEGY_TYPES = ["tendencia", "reversion", "momentum", "breakout"]


# ─────────────────────────────────────────────
# RESEARCH AGENT
# ─────────────────────────────────────────────

class ResearcherAgent:
    """
    Genera ideas de estrategias de trading para el Designer Agent.
    Usa catálogo predefinido + generación LLM para variedad.
    """

    def __init__(self):
        self.llm    = get_llm_client()
        self.db     = get_database()
        self.memory = get_memory()
        self._system_prompt = self._load_system_prompt()
        log.info("ResearcherAgent inicializado")

    def _load_system_prompt(self) -> str:
        path = PROMPTS_DIR / "researcher_system.txt"
        if not path.exists():
            raise FileNotFoundError(f"No se encontró: {path}")
        return path.read_text(encoding="utf-8")

    # ── Método principal ──────────────────────────────────────────────

    def research(
        self,
        strategy_type: Optional[str] = None,
        use_llm:       bool = True,
        cycle_id:      Optional[int] = None,
    ) -> Optional[dict]:
        """
        Genera una idea de estrategia original.

        Args:
            strategy_type: Tipo preferido ('tendencia', 'reversion', 'momentum', 'breakout')
                          Si es None, elige el tipo menos explorado automáticamente
            use_llm:       Si True, usa el LLM para generar ideas adicionales
                          Si False, solo usa el catálogo predefinido
            cycle_id:      ID del ciclo para logging

        Returns:
            Diccionario con la idea seleccionada, o None si no hay ideas disponibles
        """
        # Elegir tipo de estrategia
        chosen_type = strategy_type or self._choose_underexplored_type()
        log.info(f"[Researcher] Buscando idea de tipo: {chosen_type}")

        # ── Obtener candidatos ──
        candidates = []

        # 1. Filtrar catálogo por tipo
        catalog_candidates = [
            idea for idea in IDEAS_CATALOG
            if idea["tipo"] == chosen_type
        ]
        candidates.extend(catalog_candidates)

        # 2. Generar ideas adicionales con LLM si está habilitado
        if use_llm:
            llm_ideas = self._generate_with_llm(chosen_type)
            candidates.extend(llm_ideas)

        if not candidates:
            log.warning(f"[Researcher] No hay candidatos para tipo: {chosen_type}")
            return None

        # ── Filtrar por originalidad vs memoria ──
        filtered = self._filter_by_originality(candidates)

        if not filtered:
            log.warning("[Researcher] Todos los candidatos son demasiado similares a ideas previas")
            # Intentar con otro tipo
            alt_type = random.choice([t for t in STRATEGY_TYPES if t != chosen_type])
            log.info(f"[Researcher] Intentando tipo alternativo: {alt_type}")
            alt_candidates = [i for i in IDEAS_CATALOG if i["tipo"] == alt_type]
            filtered = self._filter_by_originality(alt_candidates)

            if not filtered:
                return None

        # ── Seleccionar la mejor idea ──
        # Ordenar por score combinado de originalidad + viabilidad
        filtered.sort(
            key=lambda x: x.get("originalidad", 0.5) * 0.6 + x.get("viabilidad", 0.5) * 0.4,
            reverse=True
        )
        selected = filtered[0]

        log.info(
            f"[Researcher] ✅ Idea seleccionada: '{selected['titulo']}' "
            f"(originalidad: {selected.get('originalidad', 0):.0%}, "
            f"viabilidad: {selected.get('viabilidad', 0):.0%})"
        )

        return selected

    # ── Elegir tipo poco explorado ────────────────────────────────────

    def _choose_underexplored_type(self) -> str:
        """
        Elige el tipo de estrategia menos generado hasta ahora.
        Así el sistema explora variedad automáticamente.
        """
        # Contar estrategias por tipo en la DB
        cycles = self.db.get_recent_cycles(limit=50)
        type_counts = {t: 0 for t in STRATEGY_TYPES}

        for cycle in cycles:
            stype = cycle.get("strategy_type", "")
            if stype in type_counts:
                type_counts[stype] += 1

        # Elegir el tipo con menos estrategias (con algo de aleatoriedad)
        min_count  = min(type_counts.values())
        candidates = [t for t, c in type_counts.items() if c <= min_count + 1]

        chosen = random.choice(candidates)
        log.info(f"[Researcher] Conteos por tipo: {type_counts} → eligiendo: {chosen}")
        return chosen

    # ── Generar ideas con LLM ─────────────────────────────────────────

    def _generate_with_llm(self, strategy_type: str) -> list[dict]:
        """
        Usa el LLM para generar ideas adicionales más allá del catálogo.
        """
        # Obtener nombres de estrategias ya generadas para evitar repetición
        existing_names = self.db.get_strategy_names()
        existing_text  = ""
        if existing_names:
            existing_text = (
                f"\nEstrategias ya generadas (no repetir):\n"
                + "\n".join(f"- {n}" for n in existing_names[-10:])
            )

        prompt = f"""Genera 3 ideas originales de estrategias de swing trading H4 para EURUSD.
Tipo de estrategia: {strategy_type}
{existing_text}

Las ideas deben usar solo indicadores técnicos estándar disponibles en MetaTrader 5.
Cada idea debe tener lógica clara de entrada y salida.
Responde SOLO con el JSON, sin texto adicional ni markdown.
"""
        try:
            log.info(f"[Researcher] Generando ideas con LLM (tipo: {strategy_type})...")
            raw = self.llm.flash(prompt=prompt, system=self._system_prompt)

            # Parsear JSON
            import re
            for pattern in [r"```json\s*\n(.*?)```", r"```\s*\n(.*?)```"]:
                match = re.search(pattern, raw, re.DOTALL)
                if match:
                    raw = match.group(1)
                    break

            # Buscar JSON directo
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            if start != -1 and end > start:
                data  = json.loads(raw[start:end])
                ideas = data.get("ideas", [])
                log.info(f"[Researcher] LLM generó {len(ideas)} ideas adicionales")
                return ideas

        except Exception as e:
            log.warning(f"[Researcher] LLM falló, usando solo catálogo: {e}")

        return []

    # ── Filtrar por originalidad ──────────────────────────────────────

    def _filter_by_originality(
        self,
        candidates: list[dict],
        threshold:  float = 0.80,
    ) -> list[dict]:
        """
        Filtra ideas que son demasiado similares a las ya generadas.
        Usa ChromaDB (memory) para la comparación semántica.
        """
        filtered = []
        for idea in candidates:
            description = f"{idea.get('titulo', '')} {idea.get('descripcion', '')}"
            similarity  = self.memory.similarity_score(description)

            if similarity < threshold:
                idea["_similarity"] = similarity
                filtered.append(idea)
            else:
                log.debug(
                    f"[Researcher] Descartada por similitud ({similarity:.0%}): "
                    f"'{idea.get('titulo')}'"
                )

        log.info(
            f"[Researcher] {len(filtered)}/{len(candidates)} candidatos "
            f"pasan el filtro de originalidad (umbral: {threshold:.0%})"
        )
        return filtered


# ─────────────────────────────────────────────
# TEST RÁPIDO
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\nProbando ResearcherAgent...\n")
    researcher = ResearcherAgent()

    # Test 1: idea del catálogo
    print("Test 1: Idea de tendencia del catálogo")
    idea = researcher.research(strategy_type="tendencia", use_llm=False)
    if idea:
        print(f"  ✅ '{idea['titulo']}'")
        print(f"     {idea['descripcion']}")
        print(f"     Indicadores: {idea['indicadores']}")
        print(f"     Originalidad: {idea.get('originalidad', 0):.0%}")
    else:
        print("  ❌ No se encontró idea")

    print()

    # Test 2: idea generada con LLM
    print("Test 2: Idea generada con LLM (tipo: reversion)")
    idea2 = researcher.research(strategy_type="reversion", use_llm=True)
    if idea2:
        print(f"  ✅ '{idea2['titulo']}'")
        print(f"     {idea2['descripcion']}")
        print(f"     Fuente: {idea2.get('fuente', 'LLM')}")
    else:
        print("  ❌ No se encontró idea")

    print()

    # Test 3: tipo automático (poco explorado)
    print("Test 3: Tipo automático")
    idea3 = researcher.research()
    if idea3:
        print(f"  ✅ '{idea3['titulo']}' (tipo: {idea3['tipo']})")
    else:
        print("  ❌ No se encontró idea")

    print("\n✅ ResearcherAgent funcionando correctamente")
