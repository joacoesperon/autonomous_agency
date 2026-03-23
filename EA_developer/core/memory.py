"""
core/memory.py
==============
Memoria del sistema usando ChromaDB.
Evita que el Orchestrator genere estrategias duplicadas o muy similares
a las que ya se generaron anteriormente.

Uso:
    from core.memory import Memory
    mem = Memory()
    score = mem.similarity_score("EMA crossover con RSI filter")
    mem.save_strategy_idea("EMA crossover con RSI filter", metadata)
"""

import logging
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.utils import embedding_functions

log = logging.getLogger(__name__)

MEMORY_DIR        = Path(__file__).parent.parent / "output" / "memory_db"
COLLECTION_NAME   = "strategy_ideas"
SIMILARITY_THRESHOLD = 0.85   # si similitud > 85%, se considera duplicado


class Memory:
    """
    Memoria semántica del sistema.
    Indexa todas las ideas de estrategias generadas para detectar duplicados.
    """

    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(path=str(MEMORY_DIR))
        self.ef     = embedding_functions.DefaultEmbeddingFunction()

        self.collection = self.client.get_or_create_collection(
            name             = COLLECTION_NAME,
            embedding_function = self.ef,
            metadata         = {"description": "Strategy ideas memory for deduplication"}
        )

        log.info(f"Memory inicializada: {self.collection.count()} ideas guardadas")

    def is_duplicate(self, idea: str, threshold: float = SIMILARITY_THRESHOLD) -> bool:
        """
        Verifica si una idea de estrategia ya fue generada anteriormente.

        Args:
            idea:      Descripción de la idea (texto libre)
            threshold: Umbral de similitud (0-1). Default: 0.85

        Returns:
            True si la idea es demasiado similar a una existente
        """
        if self.collection.count() == 0:
            return False

        results = self.collection.query(
            query_texts = [idea],
            n_results   = 1,
        )

        if not results["distances"] or not results["distances"][0]:
            return False

        distance   = results["distances"][0][0]
        similarity = max(0, 1 - distance)

        if similarity >= threshold:
            similar_name = results["metadatas"][0][0].get("strategy_name", "desconocida")
            log.info(
                f"Idea duplicada detectada (similitud: {similarity:.0%}) "
                f"— similar a: '{similar_name}'"
            )
            return True

        return False

    def similarity_score(self, idea: str) -> float:
        """
        Retorna el score de similitud con la idea más parecida en memoria.

        Returns:
            Float entre 0 y 1. 0 = completamente nueva, 1 = idéntica
        """
        if self.collection.count() == 0:
            return 0.0

        results = self.collection.query(
            query_texts = [idea],
            n_results   = 1,
        )

        if not results["distances"] or not results["distances"][0]:
            return 0.0

        return max(0, 1 - results["distances"][0][0])

    def save_strategy_idea(
        self,
        idea:          str,
        strategy_name: str = "",
        cycle_id:      Optional[int] = None,
        approved:      bool = False,
    ):
        """
        Guarda una idea de estrategia en la memoria.
        Llamar después de que el Designer define la estrategia.

        Args:
            idea:          Descripción completa de la estrategia
            strategy_name: Nombre de la estrategia
            cycle_id:      ID del ciclo asociado
            approved:      Si la estrategia fue aprobada
        """
        doc_id = f"strategy_{cycle_id or self.collection.count() + 1}"

        self.collection.upsert(
            documents = [idea],
            ids       = [doc_id],
            metadatas = [{
                "strategy_name": strategy_name,
                "cycle_id":      str(cycle_id or ""),
                "approved":      str(approved),
            }]
        )

        log.info(f"Idea guardada en memoria: '{strategy_name}' (ID: {doc_id})")

    def get_similar_strategies(self, idea: str, n: int = 3) -> list[dict]:
        """
        Retorna las N estrategias más similares a la idea dada.
        Útil para el Research Agent para saber qué ya se exploró.

        Returns:
            Lista de dicts con {name, similarity, approved}
        """
        if self.collection.count() == 0:
            return []

        n_results = min(n, self.collection.count())
        results   = self.collection.query(
            query_texts = [idea],
            n_results   = n_results,
        )

        similar = []
        for meta, dist in zip(
            results["metadatas"][0],
            results["distances"][0],
        ):
            similar.append({
                "strategy_name": meta.get("strategy_name", ""),
                "similarity":    max(0, 1 - dist),
                "approved":      meta.get("approved") == "True",
            })

        return similar

    def count(self) -> int:
        """Retorna el número de ideas guardadas en memoria."""
        return self.collection.count()

    def clear(self):
        """Limpia toda la memoria. Usar con cuidado."""
        self.client.delete_collection(COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name             = COLLECTION_NAME,
            embedding_function = self.ef,
        )
        log.warning("Memoria limpiada completamente")


# ─────────────────────────────────────────────
# SINGLETON
# ─────────────────────────────────────────────

_memory: Optional[Memory] = None

def get_memory() -> Memory:
    global _memory
    if _memory is None:
        _memory = Memory()
    return _memory


# ─────────────────────────────────────────────
# TEST RÁPIDO
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Probando Memory...")
    mem = Memory()

    # Guardar algunas ideas
    mem.save_strategy_idea(
        "EMA 50/200 crossover en H4 con filtro RSI mayor a 50",
        strategy_name = "EMA_RSI_Swing_v1",
        cycle_id      = 1,
        approved      = True,
    )
    mem.save_strategy_idea(
        "MACD crossover en H4 con filtro de tendencia en D1",
        strategy_name = "MACD_Trend_v1",
        cycle_id      = 2,
        approved      = False,
    )

    # Test de duplicado
    score = mem.similarity_score("EMA 50 y 200 cruce en H4 con RSI como filtro")
    print(f"\nSimilitud con idea existente: {score:.0%}")

    es_dup = mem.is_duplicate("EMA 50 y 200 cruce en H4 con RSI como filtro")
    print(f"¿Es duplicado? {es_dup}")

    # Idea nueva
    score2 = mem.similarity_score("Bollinger Bands breakout con volumen en D1")
    print(f"\nSimilitud idea nueva: {score2:.0%}")

    print(f"\nTotal ideas en memoria: {mem.count()}")
    print("✅ Memory funcionando correctamente")

    # Limpiar
    mem.clear()
