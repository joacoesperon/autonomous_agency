"""
Tool: search_docs
Busca en la documentación oficial de MQL5 (ChromaDB) usando búsqueda semántica.
"""

import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path


def get_chroma_collection():
    """Obtiene la colección de ChromaDB con la documentación MQL5."""
    chroma_dir = Path(__file__).parent.parent / "data" / "chromadb"
    client = chromadb.PersistentClient(path=str(chroma_dir))
    ef = embedding_functions.DefaultEmbeddingFunction()
    return client.get_or_create_collection(
        name="mql5_documentation",
        embedding_function=ef,
    )


def search_docs(query: str, n_results: int = 3, section_filter: str = None) -> str:
    """
    Busca en la documentación oficial de MQL5.

    Args:
        query:         Pregunta o término a buscar en lenguaje natural
        n_results:     Número de resultados a retornar (default: 3)
        section_filter: Filtrar por sección (ej: 'trading', 'indicators')

    Returns:
        Texto formateado con los resultados más relevantes
    """
    collection = get_chroma_collection()

    # Construir filtro de sección si se especifica
    where = {"section": section_filter} if section_filter else None

    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        where=where,
    )

    if not results["documents"] or not results["documents"][0]:
        return f"No se encontraron resultados para: '{query}'"

    output_parts = [f"# Resultados para: '{query}'\n"]

    for i, (doc, meta, distance) in enumerate(zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ), 1):
        similarity = max(0, 1 - distance)
        output_parts.append(
            f"## Resultado {i}: {meta.get('name', '?')} "
            f"[{meta.get('section_name', '?')}] "
            f"(relevancia: {similarity:.0%})\n"
        )
        output_parts.append(doc)
        output_parts.append("\n---\n")

    return "\n".join(output_parts)
