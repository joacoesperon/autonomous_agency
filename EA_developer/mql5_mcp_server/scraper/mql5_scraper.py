"""
MQL5 Documentation Scraper — Fase 2
====================================
Descarga la documentación oficial de mql5.com y la almacena en ChromaDB local.
Se ejecuta UNA SOLA VEZ durante el setup del sistema.

Uso:
    python mql5_scraper.py                  # scraping completo
    python mql5_scraper.py --test           # solo 5 funciones para probar
    python mql5_scraper.py --section trade  # solo una sección

Requisitos:
    pip install requests beautifulsoup4 chromadb lxml
"""

import os
import sys
import json
import time
import argparse
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

import requests
from bs4 import BeautifulSoup
import chromadb
from chromadb.utils import embedding_functions

# ─────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────

BASE_URL    = "https://www.mql5.com/en/docs"
DATA_DIR    = Path(__file__).parent.parent / "data"
CHROMA_DIR  = DATA_DIR / "chromadb"
CACHE_DIR   = DATA_DIR / "scraper_cache"   # cache HTML para no re-descargar
LOG_FILE    = DATA_DIR / "scraper.log"

# Delay entre requests para no sobrecargar el servidor (segundos)
REQUEST_DELAY = 1.5

# Headers para parecer un navegador real
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# ─────────────────────────────────────────────
# SECCIONES A SCRAPEAR (URL slug → nombre legible)
# Orden de prioridad: las más importantes para swing trading primero
# ─────────────────────────────────────────────

SECTIONS = {
    # PRIORIDAD CRÍTICA — sin estas el EA no funciona
    "trading":              "Trade Functions",
    "indicators":           "Technical Indicators",
    "series":               "Timeseries and Indicators Access",
    "marketinformation":    "Market Info",
    "account":              "Account Information",      # era: accountinformation

    # PRIORIDAD ALTA — necesarias para lógica y cálculos
    "array":                "Array Functions",
    "math":                 "Math Functions",
    "convert":              "Conversion Functions",
    "common":               "Common Functions",

    # PRIORIDAD MEDIA — útiles pero no críticas para un EA básico
    "strings":              "String Functions",          # era: string
    "dateandtime":          "Date and Time",             # era: datetime
    "files":                "File Functions",
    "chart_operations":     "Chart Operations",
}

# ─────────────────────────────────────────────
# ESTRUCTURA DE DATOS
# ─────────────────────────────────────────────

@dataclass
class MQL5Function:
    """Representa una función documentada de MQL5"""
    name:        str
    section:     str
    section_name: str
    url:         str
    signature:   str          = ""
    description: str          = ""
    parameters:  list[dict]   = field(default_factory=list)
    return_value: str         = ""
    example:     str          = ""
    notes:       str          = ""

    def to_chroma_document(self) -> str:
        """Genera el texto que se indexará en ChromaDB"""
        parts = [
            f"FUNCIÓN: {self.name}",
            f"SECCIÓN: {self.section_name}",
            f"URL: {self.url}",
        ]
        if self.signature:
            parts.append(f"FIRMA: {self.signature}")
        if self.description:
            parts.append(f"DESCRIPCIÓN: {self.description}")
        if self.parameters:
            param_text = "\n".join(
                f"  - {p.get('name','')}: {p.get('description','')}"
                for p in self.parameters
            )
            parts.append(f"PARÁMETROS:\n{param_text}")
        if self.return_value:
            parts.append(f"RETORNO: {self.return_value}")
        if self.example:
            parts.append(f"EJEMPLO:\n{self.example}")
        if self.notes:
            parts.append(f"NOTAS: {self.notes}")
        return "\n\n".join(parts)

    def to_chroma_metadata(self) -> dict:
        """Metadata para filtrar búsquedas en ChromaDB"""
        return {
            "name":         self.name,
            "section":      self.section,
            "section_name": self.section_name,
            "url":          self.url,
            "has_example":  bool(self.example),
        }


# ─────────────────────────────────────────────
# SCRAPER
# ─────────────────────────────────────────────

class MQL5Scraper:

    def __init__(self, test_mode: bool = False, target_section: Optional[str] = None):
        self.test_mode      = test_mode
        self.target_section = target_section
        self.session        = requests.Session()
        self.session.headers.update(HEADERS)
        self.functions: list[MQL5Function] = []
        self.errors:    list[str]          = []

        # Setup directorios
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(LOG_FILE, encoding="utf-8"),
            ]
        )
        self.log = logging.getLogger(__name__)

    def fetch_url(self, url: str) -> Optional[BeautifulSoup]:
        """Descarga una URL con cache local para no re-descargar."""
        # Nombre de archivo de cache basado en la URL
        cache_name = url.replace("https://www.mql5.com/en/docs/", "").replace("/", "_") + ".html"
        cache_path = CACHE_DIR / cache_name

        if cache_path.exists():
            self.log.debug(f"Cache hit: {cache_name}")
            html = cache_path.read_text(encoding="utf-8")
        else:
            self.log.debug(f"Descargando: {url}")
            try:
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
                html = response.text
                cache_path.write_text(html, encoding="utf-8")
                time.sleep(REQUEST_DELAY)
            except requests.RequestException as e:
                self.log.error(f"Error descargando {url}: {e}")
                self.errors.append(f"FETCH_ERROR: {url} — {e}")
                return None

        return BeautifulSoup(html, "lxml")

    def get_function_links(self, section: str) -> list[str]:
        """
        Obtiene la lista de URLs de funciones de una sección.
        La documentación de mql5.com tiene una página índice por sección
        con links a cada función individual.
        """
        url  = f"{BASE_URL}/{section}"
        soup = self.fetch_url(url)
        if not soup:
            return []

        links = []
        # Los links a funciones están en la tabla de contenidos lateral
        # o en el cuerpo principal como lista de links
        for a in soup.find_all("a", href=True):
            href = a["href"]
            # Filtrar solo links a funciones de esta sección
            if f"/en/docs/{section}/" in href:
                full_url = href if href.startswith("http") else f"https://www.mql5.com{href}"
                if full_url not in links:
                    links.append(full_url)

        self.log.info(f"Sección '{section}': {len(links)} funciones encontradas")
        return links

    def parse_function_page(self, url: str, section: str, section_name: str) -> Optional[MQL5Function]:
        """
        Parsea la página de documentación de una función individual.
        Extrae: nombre, firma, descripción, parámetros, retorno, ejemplo.
        """
        soup = self.fetch_url(url)
        if not soup:
            return None

        func = MQL5Function(
            name         = url.split("/")[-1].split("?")[0],
            section      = section,
            section_name = section_name,
            url          = url,
        )

        # ── Nombre de la función (título de la página) ──
        title = soup.find("h1") or soup.find("h2", class_="title")
        if title:
            func.name = title.get_text(strip=True).split("(")[0].strip()

        # ── Firma de la función ──
        # En mql5.com la firma aparece en un bloque <div class="code_block"> o <pre>
        code_blocks = soup.find_all(["pre", "code"])
        for block in code_blocks:
            text = block.get_text(strip=True)
            # La firma suele ser la primera declaración con el nombre de la función
            if func.name.lower() in text.lower() and "(" in text and ")" in text:
                # Tomar solo la primera línea que parece una firma
                lines = text.split("\n")
                for line in lines:
                    if func.name.lower() in line.lower() and "(" in line:
                        func.signature = line.strip()
                        break
                if func.signature:
                    break

        # ── Descripción principal ──
        # El primer párrafo de texto después del título
        main_content = soup.find("div", class_=["body", "content", "article-content"])
        if not main_content:
            main_content = soup.find("div", id="content")
        if not main_content:
            main_content = soup

        paragraphs = main_content.find_all("p") if main_content else []
        desc_parts = []
        for p in paragraphs[:3]:  # primeros 3 párrafos
            text = p.get_text(strip=True)
            if text and len(text) > 20:
                desc_parts.append(text)
        func.description = " ".join(desc_parts)[:800]  # máximo 800 chars

        # ── Parámetros ──
        # En mql5.com los parámetros están en tablas o listas con [in] [out]
        param_tables = soup.find_all("table")
        for table in param_tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    name_cell = cells[0].get_text(strip=True)
                    desc_cell = cells[-1].get_text(strip=True)
                    # Filtrar filas que parecen parámetros (tienen [in] o [out])
                    if ("[in]" in desc_cell or "[out]" in desc_cell or
                        "[in,out]" in desc_cell or name_cell.startswith("_")):
                        func.parameters.append({
                            "name":        name_cell,
                            "description": desc_cell[:300]
                        })

        # ── Valor de retorno ──
        # Buscar sección "Return Value" o "Returned value"
        for heading in soup.find_all(["h3", "h4", "b", "strong"]):
            text = heading.get_text(strip=True).lower()
            if "return" in text and "value" in text:
                next_elem = heading.find_next_sibling()
                if next_elem:
                    func.return_value = next_elem.get_text(strip=True)[:400]
                break

        # ── Ejemplo de código ──
        # El último bloque de código de la página suele ser el ejemplo
        all_code = soup.find_all("pre")
        if all_code:
            # Preferir el bloque más largo (más completo)
            largest = max(all_code, key=lambda x: len(x.get_text()))
            example_text = largest.get_text()
            # Solo incluir si parece código MQL5 real
            if any(kw in example_text for kw in ["OnInit", "OnTick", "void ", "int ", "double ", "bool "]):
                func.example = example_text[:1500]  # máximo 1500 chars

        return func

    def scrape_section(self, section: str, section_name: str) -> list[MQL5Function]:
        """Scraping completo de una sección."""
        self.log.info(f"\n{'='*50}")
        self.log.info(f"Scrapeando sección: {section_name} ({section})")
        self.log.info(f"{'='*50}")

        links = self.get_function_links(section)

        if self.test_mode:
            links = links[:5]
            self.log.info(f"Modo test: limitando a {len(links)} funciones")

        functions = []
        for i, url in enumerate(links, 1):
            self.log.info(f"  [{i}/{len(links)}] {url.split('/')[-1]}")
            func = self.parse_function_page(url, section, section_name)
            if func:
                functions.append(func)
            else:
                self.log.warning(f"  ⚠️  No se pudo parsear: {url}")

        self.log.info(f"✅ Sección '{section_name}': {len(functions)} funciones scrapeadas")
        return functions

    def run(self) -> list[MQL5Function]:
        """Ejecuta el scraping completo o de una sección específica."""
        sections_to_scrape = (
            {self.target_section: SECTIONS[self.target_section]}
            if self.target_section and self.target_section in SECTIONS
            else SECTIONS
        )

        all_functions = []
        for section, section_name in sections_to_scrape.items():
            funcs = self.scrape_section(section, section_name)
            all_functions.extend(funcs)

        self.functions = all_functions
        self.log.info(f"\n{'='*50}")
        self.log.info(f"SCRAPING COMPLETADO: {len(all_functions)} funciones totales")
        self.log.info(f"Errores: {len(self.errors)}")
        self.log.info(f"{'='*50}")

        # Guardar resumen JSON para debugging
        summary_path = DATA_DIR / "scraper_summary.json"
        summary = [
            {"name": f.name, "section": f.section, "url": f.url,
             "has_signature": bool(f.signature), "has_example": bool(f.example)}
            for f in all_functions
        ]
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
        self.log.info(f"Resumen guardado en: {summary_path}")

        return all_functions


# ─────────────────────────────────────────────
# CHROMADB INDEXER
# ─────────────────────────────────────────────

class MQL5ChromaIndexer:
    """Indexa las funciones scrapeadas en ChromaDB para búsqueda semántica."""

    COLLECTION_NAME = "mql5_documentation"

    def __init__(self):
        self.client = chromadb.PersistentClient(path=str(CHROMA_DIR))

        # Usar el embedding function por defecto de ChromaDB (sentence-transformers)
        # Es gratuito y corre localmente sin API key
        self.ef = embedding_functions.DefaultEmbeddingFunction()

        # Crear o recuperar la colección
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=self.ef,
            metadata={"description": "MQL5 official documentation for swing trading EA generation"}
        )

        self.log = logging.getLogger(__name__)

    def index_functions(self, functions: list[MQL5Function], batch_size: int = 50):
        """Indexa todas las funciones en ChromaDB en batches."""
        total = len(functions)
        self.log.info(f"\nIndexando {total} funciones en ChromaDB...")

        # Preparar datos
        documents = []
        metadatas = []
        ids       = []

        for i, func in enumerate(functions):
            doc_text = func.to_chroma_document()
            metadata = func.to_chroma_metadata()
            doc_id   = f"{func.section}_{func.name}_{i}"

            documents.append(doc_text)
            metadatas.append(metadata)
            ids.append(doc_id)

        # Indexar en batches para no sobrecargar la memoria
        for start in range(0, total, batch_size):
            end   = min(start + batch_size, total)
            batch_docs  = documents[start:end]
            batch_meta  = metadatas[start:end]
            batch_ids   = ids[start:end]

            self.collection.upsert(
                documents=batch_docs,
                metadatas=batch_meta,
                ids=batch_ids,
            )
            self.log.info(f"  Indexados {end}/{total} ({end/total*100:.0f}%)")

        count = self.collection.count()
        self.log.info(f"✅ ChromaDB: {count} documentos indexados en '{self.COLLECTION_NAME}'")

    def test_search(self):
        """Prueba básica de búsqueda para verificar que ChromaDB funciona."""
        test_queries = [
            "how to open a buy order",
            "moving average indicator handle",
            "get account balance",
            "stop loss take profit order",
        ]

        print("\n" + "="*50)
        print("TEST DE BÚSQUEDA EN CHROMADB")
        print("="*50)

        for query in test_queries:
            results = self.collection.query(
                query_texts=[query],
                n_results=2,
            )
            print(f"\nQuery: '{query}'")
            for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
                print(f"  → {meta.get('name','?')} [{meta.get('section_name','?')}]")


# ─────────────────────────────────────────────
# PIPELINE COMPLETO
# ─────────────────────────────────────────────

def run_full_pipeline(test_mode: bool = False, section: Optional[str] = None):
    """
    Pipeline completo:
    1. Scraping de mql5.com
    2. Guardado de funciones en JSON
    3. Indexado en ChromaDB
    4. Test de búsqueda
    """
    print("\n" + "="*60)
    print("MQL5 DOCUMENTATION SCRAPER — Fase 2")
    print("="*60)
    print(f"Modo test: {test_mode}")
    print(f"Sección específica: {section or 'TODAS'}")
    print(f"Directorio de datos: {DATA_DIR}")
    print("="*60 + "\n")

    # ── PASO 1: Scraping ──
    scraper   = MQL5Scraper(test_mode=test_mode, target_section=section)
    functions = scraper.run()

    if not functions:
        print("\n❌ ERROR: No se obtuvieron funciones. Verificar conexión a internet.")
        print("   Consejo: ejecutar este script en tu máquina local con acceso a mql5.com")
        sys.exit(1)

    # ── PASO 2: Guardar en JSON (backup) ──
    json_path = DATA_DIR / "mql5_functions.json"
    functions_data = [asdict(f) for f in functions]
    json_path.write_text(
        json.dumps(functions_data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print(f"\n✅ Funciones guardadas en JSON: {json_path}")

    # ── PASO 3: Indexar en ChromaDB ──
    indexer = MQL5ChromaIndexer()
    indexer.index_functions(functions)

    # ── PASO 4: Verificar con búsquedas de prueba ──
    indexer.test_search()

    # ── RESUMEN FINAL ──
    print("\n" + "="*60)
    print("SETUP COMPLETADO")
    print("="*60)
    print(f"✅ Funciones scrapeadas: {len(functions)}")
    print(f"✅ JSON backup:          {json_path}")
    print(f"✅ ChromaDB:             {CHROMA_DIR}")
    print(f"⚠️  Errores durante scraping: {len(scraper.errors)}")
    if scraper.errors:
        for err in scraper.errors[:5]:
            print(f"   - {err}")
    print("\nEl MCP Server ya puede usar la base de datos.")
    print("="*60)


# ─────────────────────────────────────────────
# UTILIDADES ADICIONALES
# ─────────────────────────────────────────────

def load_from_json_to_chroma():
    """
    Alternativa al scraping: carga funciones desde el JSON de backup.
    Útil si el scraping falló parcialmente o si se quiere re-indexar.
    """
    json_path = DATA_DIR / "mql5_functions.json"
    if not json_path.exists():
        print(f"❌ No se encontró {json_path}")
        print("   Ejecutar primero el scraping completo.")
        return

    print(f"Cargando funciones desde {json_path}...")
    data = json.loads(json_path.read_text(encoding="utf-8"))

    functions = []
    for item in data:
        func = MQL5Function(**item)
        functions.append(func)

    print(f"✅ {len(functions)} funciones cargadas del JSON")

    indexer = MQL5ChromaIndexer()
    indexer.index_functions(functions)
    indexer.test_search()


def search_chromadb(query: str, n: int = 3):
    """Herramienta de debug: busca directamente en ChromaDB."""
    indexer = MQL5ChromaIndexer()
    results = indexer.collection.query(
        query_texts=[query],
        n_results=n,
    )
    print(f"\nResultados para: '{query}'")
    print("-" * 40)
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        print(f"📄 {meta.get('name')} [{meta.get('section_name')}]")
        print(f"   Similitud: {1 - dist:.2%}")
        print(f"   URL: {meta.get('url')}")
        print()


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="MQL5 Documentation Scraper para el sistema de trading algorítmico"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Modo test: scraping de solo 5 funciones por sección"
    )
    parser.add_argument(
        "--section",
        type=str,
        choices=list(SECTIONS.keys()),  # ver SECTIONS dict para valores válidos
        help="Scrapear solo una sección específica"
    )
    parser.add_argument(
        "--reload-json",
        action="store_true",
        help="Re-indexar ChromaDB desde el JSON de backup (sin hacer scraping)"
    )
    parser.add_argument(
        "--search",
        type=str,
        help="Probar una búsqueda en ChromaDB (ej: --search 'open buy order')"
    )

    args = parser.parse_args()

    if args.search:
        search_chromadb(args.search)
    elif args.reload_json:
        load_from_json_to_chroma()
    else:
        run_full_pipeline(test_mode=args.test, section=args.section)