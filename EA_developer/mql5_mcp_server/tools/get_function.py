"""
Tool: get_function
Retorna la ficha completa de una función MQL5 específica desde ChromaDB.
"""

import json
import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path


def get_chroma_collection():
    chroma_dir = Path(__file__).parent.parent / "data" / "chromadb"
    client = chromadb.PersistentClient(path=str(chroma_dir))
    ef = embedding_functions.DefaultEmbeddingFunction()
    return client.get_or_create_collection(
        name="mql5_documentation",
        embedding_function=ef,
    )


def get_function(function_name: str) -> str:
    """
    Retorna la documentación completa de una función MQL5 específica.

    Args:
        function_name: Nombre exacto de la función (ej: 'iMA', 'CTrade', 'CopyBuffer')

    Returns:
        Documentación completa de la función con firma, parámetros y ejemplo
    """
    collection = get_chroma_collection()

    # Búsqueda exacta por nombre (case-insensitive)
    name_lower = function_name.lower()

    # Intentar primero búsqueda exacta por metadata
    try:
        results = collection.query(
            query_texts=[function_name],
            n_results=5,
        )

        if results["documents"] and results["documents"][0]:
            # Buscar coincidencia exacta en los resultados
            for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
                if meta.get("name", "").lower() == name_lower:
                    return f"# Documentación: {meta['name']}\n\n{doc}"

            # Si no hay coincidencia exacta, retornar el más relevante
            best_doc  = results["documents"][0][0]
            best_meta = results["metadatas"][0][0]
            return (
                f"# Función más cercana a '{function_name}': {best_meta.get('name','?')}\n\n"
                f"{best_doc}\n\n"
                f"⚠️ No se encontró '{function_name}' exacto. "
                f"Verificar el nombre en la documentación oficial."
            )

    except Exception as e:
        return f"Error buscando función '{function_name}': {e}"

    return f"No se encontró documentación para '{function_name}'. Verificar el nombre."
