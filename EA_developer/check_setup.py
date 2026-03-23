"""
check_setup.py
==============
Verifica que todos los componentes del sistema están correctamente instalados.
Ejecutar antes de arrancar el sistema por primera vez.

Uso:
    python check_setup.py
"""

import sys
import os
from pathlib import Path

# Agregar raíz al path
sys.path.insert(0, str(Path(__file__).parent))

OK   = "✅"
WARN = "⚠️ "
ERR  = "❌"

results = []

def check(label, ok, detail=""):
    icon = OK if ok else ERR
    msg  = f"  {icon} {label}"
    if detail:
        msg += f"  →  {detail}"
    print(msg)
    results.append(ok)


print("\n" + "="*50)
print("  VERIFICACIÓN DEL SISTEMA")
print("="*50 + "\n")

# ── Python ──
print("[ Python ]")
check("Python 3.11+", sys.version_info >= (3, 11), f"v{sys.version.split()[0]}")

# ── Dependencias ──
print("\n[ Dependencias ]")
deps = [
    ("google.generativeai",  "google-generativeai"),
    ("chromadb",             "chromadb"),
    ("dotenv",               "python-dotenv"),
    ("yaml",                 "pyyaml"),
    ("fastmcp",              "fastmcp"),
    ("optuna",               "optuna"),
    ("pandas",               "pandas"),
    ("numpy",                "numpy"),
    ("requests",             "requests"),
    ("bs4",                  "beautifulsoup4"),
    ("apscheduler",          "apscheduler"),
]

for module, pkg in deps:
    try:
        __import__(module)
        check(pkg, True)
    except ImportError:
        check(pkg, False, f"pip install {pkg}")

# MT5 (solo Windows)
try:
    import MetaTrader5 as mt5
    check("MetaTrader5", True)
except ImportError:
    print(f"  {WARN} MetaTrader5  →  pip install MetaTrader5  (solo Windows)")

# ── .env ──
print("\n[ Configuración ]")
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY", "")
check(".env existe",        Path(".env").exists())
check("GEMINI_API_KEY set", bool(api_key), "*** oculto ***" if api_key else "FALTA — editar .env")
check("config.yaml existe", Path("config.yaml").exists())

# ── Estructura de carpetas ──
print("\n[ Estructura de carpetas ]")
required_dirs = [
    "mql5_mcp_server/tools",
    "mql5_mcp_server/data",
    "mql5_mcp_server/data/chromadb",
    "mql5_mcp_server/scraper",
    "agents",
    "core",
    "prompts",
    "output/strategies/aprobadas",
    "output/strategies/descartadas",
    "output/logs",
]
for d in required_dirs:
    check(d, Path(d).exists())

# ── Archivos clave ──
print("\n[ Archivos del sistema ]")
required_files = [
    "mql5_mcp_server/server.py",
    "mql5_mcp_server/tools/search_docs.py",
    "mql5_mcp_server/tools/get_function.py",
    "mql5_mcp_server/tools/get_pattern.py",
    "mql5_mcp_server/tools/get_template.py",
    "mql5_mcp_server/tools/check_forbidden.py",
    "mql5_mcp_server/tools/get_error_fix.py",
    "mql5_mcp_server/data/mql5_knowledge_base.md",
    "mql5_mcp_server/data/error_fixes.json",
    "mql5_mcp_server/data/mql5_functions.json",
    "mql5_mcp_server/scraper/mql5_scraper.py",
    "core/llm_client.py",
    "core/mt5_connector.py",
    "core/database.py",
    "core/memory.py",
]
for f in required_files:
    check(f, Path(f).exists())

# ── ChromaDB con datos ──
print("\n[ ChromaDB ]")
try:
    import chromadb
    from chromadb.utils import embedding_functions
    client = chromadb.PersistentClient(path="mql5_mcp_server/data/chromadb")
    ef     = embedding_functions.DefaultEmbeddingFunction()
    col    = client.get_or_create_collection("mql5_documentation", embedding_function=ef)
    count  = col.count()
    check("ChromaDB accesible",    True)
    check("Documentación indexada", count >= 300, f"{count} funciones indexadas")
except Exception as e:
    check("ChromaDB accesible", False, str(e))

# ── MT5 conectado ──
print("\n[ MetaTrader 5 ]")
try:
    import MetaTrader5 as mt5
    if mt5.initialize():
        info = mt5.terminal_info()
        check("MT5 conectado", True, f"{info.name} build {info.build}")
        mt5.shutdown()
    else:
        check("MT5 conectado", False, "Abrir MT5 antes de ejecutar el sistema")
except Exception:
    print(f"  {WARN} MT5 no verificado (asegurarse que MT5 está abierto)")

# ── Resumen ──
total  = len(results)
passed = sum(results)
failed = total - passed

print("\n" + "="*50)
if failed == 0:
    print(f"  ✅ Todo OK — {passed}/{total} checks pasaron")
    print("  Sistema listo para arrancar.")
else:
    print(f"  ⚠️  {passed}/{total} checks pasaron — {failed} problemas")
    print("  Resolver los ❌ antes de continuar.")
print("="*50 + "\n")
