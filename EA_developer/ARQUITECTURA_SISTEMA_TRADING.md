# Sistema Multi-Agente de Trading Algorítmico Autónomo — MT5/MQL5

> **Documento de referencia de arquitectura**  
> Versión: 2.0 | Estado: Sistema construido y validado  
> Última actualización: Marzo 2026

---

## Índice

1. [Visión General](#1-visión-general)
2. [Stack Tecnológico](#2-stack-tecnológico)
3. [Estructura de Capas](#3-estructura-de-capas)
4. [Capa 0 — Setup Único](#4-capa-0--setup-único)
5. [Capa 1 — MCP Server MQL5](#5-capa-1--mcp-server-mql5)
6. [Capa 2 — Pipeline de Agentes](#6-capa-2--pipeline-de-agentes)
7. [Self-Healing Loop](#7-self-healing-loop)
8. [Separación de Períodos — Optimizer](#8-separación-de-períodos--optimizer)
9. [Filtros de Calidad por Perfil](#9-filtros-de-calidad-por-perfil)
10. [Perfiles Multi-Símbolo](#10-perfiles-multi-símbolo)
11. [Estructura de Carpetas](#11-estructura-de-carpetas)
12. [Output Esperado](#12-output-esperado)
13. [Uso del Sistema](#13-uso-del-sistema)
14. [Hoja de Ruta de Construcción](#14-hoja-de-ruta-de-construcción)
15. [Decisiones Tomadas Durante la Construcción](#15-decisiones-tomadas-durante-la-construcción)

---

## 1. Visión General

Sistema autónomo que opera de forma continua buscando, diseñando, codificando,
compilando, backtesting y validando estrategias de trading algorítmico para
MetaTrader 5. El usuario final solo recibe archivos `.mq5` listos para copiar
y pegar en MT5, acompañados de un reporte `.txt` con las métricas.

### Objetivos clave

- **Autónomo**: corre sin intervención humana 24/7
- **Calidad sobre cantidad**: 1-2 estrategias/día bien testeadas
- **Sin data leakage**: optimización sobre training set, validación sobre OOS nunca visto
- **Costo $0/mes**: usando tier gratuito de Gemini 2.5 Flash
- **MQL5 correcto**: el sistema nunca confunde MQL4 con MQL5 gracias al MCP server propio
- **Multi-símbolo**: rota entre EURUSD, GBPUSD, XAUUSD, USDJPY con filtros específicos

### Restricciones de hardware

```
Máquina objetivo:
├── RAM:  8GB o menos
├── GPU:  Sin GPU dedicada (gráficos integrados)
├── OS:   Windows (requerido para MT5)
└── MT5:  Instalado y configurado
```

Por estas restricciones no se usa Ollama ni ningún modelo local.
Todo el procesamiento LLM va a APIs en la nube (gratuitas).

---

## 2. Stack Tecnológico

| Componente | Tecnología | Costo |
|---|---|---|
| LLM único (todos los agentes) | Gemini 2.5 Flash | $0 (~20 req/día free tier) |
| Orquestación | Python puro + APScheduler | $0 |
| Memoria / deduplicación | ChromaDB local | $0 |
| Documentación MQL5 | ChromaDB + scraper propio | $0 |
| MCP Server MQL5 | FastMCP (Python) | $0 |
| Backtesting | MT5 Python API + MetaEditor | $0 |
| Optimización | Optuna (Python) | $0 |
| Base de datos interna | SQLite | $0 |
| **Total** | | **$0/mes** |

### Modelos Gemini — Situación real (Marzo 2026)

```
⚠️  CAMBIO IMPORTANTE respecto al diseño original:
    Gemini 2.0 Flash fue retirado el 3 de marzo 2026.
    Gemini 2.5 Pro en free tier tiene 429 frecuentes.
    Decisión: usar Gemini 2.5 Flash para TODOS los agentes.
    Gemini 2.5 Flash iguala a Pro en benchmarks de código.

Gemini 2.5 Flash:  ~10 RPM · ~20 RPD (free tier)

Consumo estimado por estrategia: ~5-8 llamadas LLM
Capacidad resultante: 2 estrategias/día
Cadencia recomendada: 1 estrategia cada 12 horas
```

### Migración futura a Claude API (opcional)

El sistema está diseñado para migrar a Claude Haiku/Sonnet sin reescribir nada.
Solo se cambia el `llm_client.py`. Costo estimado: ~$5-30/mes con mayor calidad.

---

## 3. Estructura de Capas

```
┌──────────────────────────────────────────────────┐
│         CAPA 0 — SETUP ÚNICO                     │
│   (se ejecuta una sola vez al instalar)          │
│   · Scraper docs oficiales mql5.com → ChromaDB   │
│   · Knowledge Base MQL5 manual                  │
└──────────────────────┬───────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────┐
│         CAPA 1 — MCP SERVER MQL5                 │
│   (corre como proceso en background)             │
│   · 7 herramientas de consulta MQL5              │
│   · Consultado por el Coder antes de codificar   │
└──────────────────────┬───────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────┐
│         CAPA 2 — PIPELINE DE AGENTES             │
│   (el sistema principal, corre continuamente)    │
│   · 7 agentes especializados en secuencia        │
│   · Produce .mq5 + reporte .txt por estrategia   │
└──────────────────────────────────────────────────┘
```

---

## 4. Capa 0 — Setup Único

### MQL5 Documentation Scraper

Descarga la documentación oficial de `mql5.com/en/docs` en ChromaDB local.
Se ejecuta una sola vez durante la instalación.

**Resultado real del scraper:** 335 funciones indexadas en 13 secciones,
380 documentos en ChromaDB (incluyendo subsecciones).

**URLs correctas (corregidas durante construcción):**
```
accountinformation → account       (era: accountinformation)
string             → strings       (era: string)
datetime           → dateandtime   (era: datetime)
```

### Knowledge Base MQL5 Manual

Archivo `mql5_knowledge_base.md` con:
- **Bloque 1**: 30+ prohibiciones MQL4 con equivalente MQL5 exacto
- **Bloque 2**: Plantilla base EA swing trading H4 (~200 líneas)
- **Bloque 3**: 30 patrones de código MQL5 para swing trading
- **Bloque 4**: 10 errores de compilación frecuentes con fix exacto
- **Bloque 5**: 15 reglas absolutas para el Coder Agent

---

## 5. Capa 1 — MCP Server MQL5

Servidor FastMCP que expone conocimiento de MQL5 como herramientas consultables.
**Diferencia clave respecto a repos existentes**: los repos de GitHub
(`mcp-metatrader5-server`, `metatrader-mcp-server`) son puentes para
**ejecutar trades en vivo**. Este MCP server expone **conocimiento de MQL5**
para que los agentes generen código correcto. Son propósitos completamente distintos.

### Herramientas expuestas (7)

| Herramienta | Función |
|---|---|
| `search_docs(query)` | Búsqueda semántica en las 335 funciones de ChromaDB |
| `get_function(name)` | Ficha completa de una función específica |
| `get_pattern(name)` | Fragmento de código probado (30 patrones disponibles) |
| `list_patterns()` | Lista todos los patrones disponibles |
| `get_template()` | Plantilla base del EA (~200 líneas) |
| `check_forbidden(code)` | Detector de 20+ construcciones MQL4 prohibidas |
| `get_error_fix(error)` | Fix documentado para 20 errores de compilación frecuentes |

---

## 6. Capa 2 — Pipeline de Agentes

### Diagrama de flujo

```
ORCHESTRATOR (APScheduler, cada 12 horas)
    │
    ├── Elige perfil activo (rotación automática)
    ├── Verifica límite diario de API (<18 calls usadas)
    └── Lanza el pipeline
         │
         ▼
RESEARCH AGENT (Gemini 2.5 Flash)
    ├── Catálogo de 14 ideas base (sin internet)
    ├── Generación LLM de ideas adicionales
    ├── Filtro de originalidad via ChromaDB (umbral 80%)
    └── Elige el tipo de estrategia menos explorado
         │
         ▼
DESIGNER AGENT (Gemini 2.5 Flash)
    ├── Recibe idea + símbolo/timeframe del perfil activo
    ├── Genera diseño técnico en JSON estructurado
    ├── Valida campos obligatorios y ratio R/R mínimo 1:2
    └── Guarda idea en memoria ChromaDB
         │
         ▼
CODER AGENT (Gemini 2.5 Flash) ← consulta MCP intensivamente
    ├── get_template() → estructura base
    ├── get_function() → firma exacta de cada indicador
    ├── get_pattern() → fragmentos de código probados
    ├── Genera .mq5 ensamblando piezas conocidas
    └── check_forbidden() → verifica antes de entregar
         │
         ▼
COMPILER + SELF-HEALING LOOP (ver Sección 7)
         │
         ▼ (código compilado)
BACKTESTER AGENT (Python puro — sin LLM)
    ├── Lee símbolo/timeframe/fechas del perfil activo
    ├── Acepta date_from y date_to explícitos (para Optimizer)
    ├── MT5 Strategy Tester con datos reales del broker
    └── MockBacktesterAgent en desarrollo (determinista por params)
         │
         ▼
OPTIMIZER AGENT (Python puro — Optuna)
    ├── Ver Sección 8 para separación de períodos
    ├── 200 trials Optuna TPE Sampler (seed=42)
    ├── Walk-forward dentro del training set
    └── Out-of-sample sobre últimos 2 años (nunca vistos)
         │
         ▼
VALIDATOR AGENT (Gemini 2.5 Flash)
    ├── System prompt DINÁMICO según perfil activo
    │   (criterios diferentes para XAUUSD vs EURUSD)
    ├── Aplica filtros del perfil (ver Sección 9)
    ├── Análisis cualitativo LLM
    ├── Genera reporte .txt detallado
    └── Mueve .mq5 a output/strategies/aprobadas/
```

### Detalle de cada agente

#### RESEARCHER — Gemini 2.5 Flash

Tipos de estrategia en el catálogo: **tendencia, reversión, momentum, breakout**

El Orchestrator elige el tipo menos generado recientemente para garantizar variedad.
Con `use_llm=False` usa solo el catálogo predefinido (sin consumir API).

#### DESIGNER — Gemini 2.5 Flash

Output JSON estructurado con:
- Nombre, tipo, descripción
- Lista de indicadores con período, timeframe y variable_nombre
- Condiciones de entrada long y short (texto exacto)
- SL/TP con tipo (pips o ATR) y valor
- Filtros (spread, día, sesión)
- Parámetros externos con tipo, default y descripción

**Enriquecimiento de idea:** el pipeline inyecta el símbolo y timeframe del
perfil activo en el prompt del Designer antes de llamarlo.

#### CODER — Gemini 2.5 Flash

**System prompt:** incluye las 3 reglas absolutas + Knowledge Base completa
embebida (~37KB). El placeholder `{KNOWLEDGE_BASE}` se reemplaza en runtime.

**Flujo de consultas MCP por estrategia típica:**
```
get_template()              → estructura base (siempre)
get_pattern('ema handle')   → por cada indicador EMA/SMA
get_pattern('rsi handle')   → por cada indicador RSI
get_pattern('nueva vela')   → siempre
get_pattern('abrir buy')    → siempre
get_pattern('abrir sell')   → siempre
get_pattern('calcular lote')→ siempre
check_forbidden(codigo)     → siempre al final
```

#### BACKTESTER — Python puro

**Modo real (MT5 conectado):** llama a MetaEditor para compilar y al
Strategy Tester de MT5 para ejecutar el backtest. Lee el reporte XML generado.

**Modo mock (desarrollo):** resultados **deterministas** por parámetros.
Mismo EA + mismos parámetros + mismo período = mismo resultado siempre.
Esto permite que Optuna realmente encuentre los mejores parámetros en mock.

#### OPTIMIZER — Python puro + Optuna

Ver Sección 8 para el diseño completo de períodos.

#### VALIDATOR — Gemini 2.5 Flash

**System prompt dinámico:** generado por `config_loader.get_validator_system_prompt(profile)`.
Los criterios de evaluación se adaptan al símbolo y timeframe activo.
El archivo `validator_system.txt` existe solo como fallback de emergencia.

---

## 7. Self-Healing Loop

```
Coder Agent genera .mq5
        │
        ▼
check_forbidden() del MCP
        │
  ¿Violaciones MQL4?
  │              │
 NO             SÍ → LLM corrige → check de nuevo
  │
  ▼
MockCompiler/MetaEditor intenta compilar
        │
  ¿Compiló?
  │        │
 ✅ SÍ    ❌ NO
  │        │
  │   MCP: get_error_fix(mensaje_error)
  │        │
  │   LLM recibe:
  │   ├── código actual
  │   ├── error exacto del compilador
  │   ├── fix documentado del MCP
  │   └── temperatura 0.1 (muy precisa)
  │        │
  │   reintenta (max 4 veces)
  │        │
  │   ¿Sigue fallando?
  │   └── Designer rediseña desde cero
  │
  ▼
Backtester Agent
```

**Estadística observada con MockCompiler:**
- Intento 1 exitoso: ~85% de los casos (check_forbidden previene la mayoría)
- Intentos 2-4: resuelven el resto

---

## 8. Separación de Períodos — Optimizer

Este es el diseño más crítico para evitar overfitting y data leakage.

```
Período total del perfil (ej: 2013-2024, 11 años)
│
├── Training set: 2013 → (end - 2 años) = 2013-2021  [9 años]
│   │
│   ├── FASE 1: Optuna optimiza aquí (200 trials)
│   │   Cada trial = backtest real de 9 años completos
│   │   Objetivo: maximizar Sharpe - DD/100
│   │   Mismo params + mismo período = mismo resultado (determinista)
│   │
│   └── FASE 3: Walk-forward (5 ventanas dentro de 2013-2021)
│       Cada ventana: 70% train / 30% test
│       Verifica robustez temporal sin tocar el OOS
│
├── FASE 2: Backtest período completo (2013-2024)
│   Con los mejores parámetros de Optuna
│   Para las métricas del reporte final
│
└── FASE 4: Out-of-sample: (end - 2 años) → end = 2022-2024  [2 años]
    NUNCA se toca durante la optimización
    Prueba final con los parámetros óptimos
    Si falla aquí → estrategia descartada aunque sea buena en training
```

**Separación de períodos en código:**
```python
OOS_YEARS = 2  # constante en optimizer.py

# Optuna optimiza sobre training set únicamente
metrics = backtester.run(mq5_path, params=params,
    date_from=train_start,   # ej: 2013.01.01
    date_to=train_end,       # ej: 2021.12.31
)

# Backtest final sobre período completo
full_metrics = backtester.run(mq5_path, params=best_params,
    date_from=full_start,    # ej: 2013.01.01
    date_to=full_end,        # ej: 2024.12.31
)

# OOS: datos nunca vistos durante optimización
oos_metrics = backtester.run(mq5_path, params=best_params,
    date_from=oos_start,     # ej: 2022.01.01
    date_to=oos_end,         # ej: 2024.12.31
)
```

---

## 9. Filtros de Calidad por Perfil

Todos los filtros son AND — fallar uno descarta la estrategia.
Cada perfil tiene sus propios umbrales adaptados al activo.

| Métrica | EURUSD H4 | GBPUSD H4 | XAUUSD H1 | USDJPY H4 | EURUSD H1 |
|---|---|---|---|---|---|
| Min Profit Factor | 1.5 | 1.5 | **1.6** | 1.5 | 1.5 |
| Min Sharpe Ratio | 1.2 | 1.2 | **1.3** | 1.2 | **1.3** |
| Max DrawDown % | 25 | **27** | **30** | 25 | **20** |
| Min Win Rate % | 45 | **44** | **43** | 45 | **47** |
| Min Total Trades | 200 | **180** | **400** | **180** | **500** |
| Min Trades/mes | 1.5 | **1.4** | **3.5** | **1.4** | **6.0** |
| WF min ventanas pass | 4/5 | 4/5 | 4/5 | 4/5 | 4/5 |

**Justificación de diferencias:**
- XAUUSD: spreads altos (~30-50 pips), PF mínimo mayor; volatilidad alta, DD permitido mayor
- EURUSD H1: más trades por período, exigimos mayor frecuencia mínima
- GBPUSD/USDJPY H4: mayor volatilidad que EURUSD, relajamos levemente trade mínimo

**Filtros adicionales en el Validator:**
- Walk-forward: al menos 4 de 5 ventanas positivas
- Overfitting score: máximo 0.5 (0=ninguno, 1=severo)
- OOS: profit_factor >= 1.0 y net_profit > 0

---

## 10. Perfiles Multi-Símbolo

### Rotación automática

```yaml
active_profile: auto   # rota automáticamente

rotation_schedule:
  - eurusd_h4    # Lunes (aprox)
  - xauusd_h1    # Martes
  - gbpusd_h4    # Miércoles
  - usdjpy_h4    # Jueves
  - eurusd_h1    # Viernes
```

El Orchestrator cuenta cuántas estrategias se generaron de cada tipo
en los últimos 50 ciclos y elige el menos explorado.

### Forzar un perfil específico

```bash
python main.py --once --profile xauusd_h1
python main.py --once --profile gbpusd_h4
python main.py --profiles   # listar todos los perfiles
```

### Impacto del perfil en el pipeline

El perfil activo se propaga a TODOS los agentes:
- **Designer**: recibe símbolo y timeframe en el prompt
- **Backtester**: usa symbol, timeframe, date_from, date_to, deposit del perfil
- **Optimizer**: calcula los períodos training/OOS desde las fechas del perfil
- **Validator**: genera un system prompt dinámico con criterios específicos del activo

---

## 11. Estructura de Carpetas

```
strategy_developer/
│
├── main.py                    ← punto de entrada
├── check_setup.py             ← verificación del sistema
├── config.yaml                ← perfiles y configuración global
├── requirements.txt
├── .env                       ← GEMINI_API_KEY (no subir a git)
│
├── mql5_mcp_server/           ← CAPA 1
│   ├── __init__.py
│   ├── server.py              ← FastMCP server
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── search_docs.py
│   │   ├── get_function.py
│   │   ├── get_pattern.py
│   │   ├── get_template.py
│   │   ├── check_forbidden.py
│   │   └── get_error_fix.py
│   ├── data/
│   │   ├── mql5_knowledge_base.md   ← Knowledge Base manual
│   │   ├── error_fixes.json
│   │   ├── mql5_functions.json      ← generado por scraper
│   │   ├── scraper_summary.json     ← generado por scraper
│   │   ├── chromadb/                ← 380 docs indexados
│   │   └── scraper_cache/           ← cache HTML mql5.com
│   └── scraper/
│       └── mql5_scraper.py
│
├── agents/                    ← CAPA 2
│   ├── __init__.py
│   ├── orchestrator.py        ← scheduler + rotación de perfiles
│   ├── researcher.py          ← 14 ideas catálogo + generación LLM
│   ├── designer.py            ← diseño técnico en JSON
│   ├── coder.py               ← generación MQL5 con MCP
│   ├── compiler.py            ← self-healing loop (max 4 intentos)
│   ├── backtester.py          ← MT5 real + MockBacktester determinista
│   ├── optimizer.py           ← Optuna + walk-forward + OOS
│   └── validator.py           ← filtros + reporte + system prompt dinámico
│
├── core/
│   ├── __init__.py
│   ├── llm_client.py          ← Gemini 2.5 Flash, rate limiting, reintentos
│   ├── mt5_connector.py       ← bridge MT5, compilación, backtesting
│   ├── database.py            ← SQLite, registro de ciclos y métricas
│   ├── memory.py              ← ChromaDB, deduplicación de ideas
│   ├── pipeline.py            ← orquesta agentes, propaga perfil
│   └── config_loader.py       ← carga perfiles, rotación, system prompt dinámico
│
├── prompts/
│   ├── coder_system.txt       ← 3 reglas absolutas + {KNOWLEDGE_BASE}
│   ├── designer_system.txt    ← principios de diseño + schema JSON
│   ├── researcher_system.txt  ← criterios de calidad + formato JSON
│   └── validator_system.txt   ← fallback (normalmente no se usa)
│
└── output/
    ├── sistema.db             ← SQLite con historial completo
    ├── strategies/
    │   ├── aprobadas/
    │   │   └── NombreEA/
    │   │       ├── NombreEA.mq5        ← copiar a MT5
    │   │       └── NombreEA_reporte.txt
    │   └── descartadas/
    │       └── NombreEA.mq5           ← para debugging
    └── logs/
        └── sistema.log
```

---

## 12. Output Esperado

Por cada estrategia aprobada el sistema produce:

```
output/strategies/aprobadas/EMA50_200_RSI_v1/
├── EMA50_200_RSI_v1.mq5          ← copiar en MT5/MQL5/Experts/
└── EMA50_200_RSI_v1_reporte.txt  ← reporte completo
```

### Contenido del reporte .txt

```
============================================================
ESTRATEGIA APROBADA: EMA50_200_RSI_v1
Generada el: 2026-03-16 14:30
============================================================

DESCRIPCIÓN
-----------
Cruce EMA 50/200 con filtro RSI en H4
Tipo: tendencia

EXPLICACIÓN DE LA LÓGICA
------------------------
[Explicación en español generada por el LLM]

MÉTRICAS (EURUSD H4 | 2013-2024)
---------------------------------
  Profit Factor:   1.87
  Sharpe Ratio:    1.94
  Max DrawDown:    12.9%
  Win Rate:        57.7%
  Total Trades:    616
  Trades/mes:      4.7
  Net Profit:      $8,450.00 (84.5%)

WALK-FORWARD (5 ventanas dentro de 2013-2021)
----------------------------------------------
  Ventana 1: 2013 → 2014  PF=1.72  ✅
  Ventana 2: 2014 → 2016  PF=1.91  ✅
  Ventana 3: 2016 → 2018  PF=1.64  ✅
  Ventana 4: 2018 → 2019  PF=1.55  ✅
  Ventana 5: 2019 → 2021  PF=1.88  ✅

OUT-OF-SAMPLE (2022-2024, nunca visto durante optimización)
------------------------------------------------------------
  PF=1.71  Sharpe=1.52  DD=11.2%  ✅

OVERFITTING SCORE: 15%

PARÁMETROS ÓPTIMOS
------------------
  EMA_Rapida:  70
  EMA_Lenta:   377
  RSI_Periodo: 8
  RSI_Nivel:   39.5
  SL_Pips:     28.0
  TP_Pips:     148.0

ANÁLISIS CUALITATIVO
--------------------
Score general: 82%
[Fortalezas, debilidades, alertas y recomendación del LLM]

INSTRUCCIONES DE USO
--------------------
1. Copiar NombreEA.mq5 a: MetaTrader 5/MQL5/Experts/
2. Abrir MetaEditor (F4) y compilar el archivo
3. En MT5: arrastrar el EA a un gráfico EURUSD H4
4. Verificar que AutoTrading está activado
5. Usar los parámetros óptimos indicados arriba
6. Comenzar con cuenta demo antes de cuenta real
```

---

## 13. Uso del Sistema

```bash
# Verificar que todo está configurado correctamente
python check_setup.py

# Ver perfiles disponibles
python main.py --profiles

# Un solo ciclo (modo manual/debug)
python main.py --once

# Un ciclo con perfil específico
python main.py --once --profile xauusd_h1
python main.py --once --profile eurusd_h4
python main.py --once --profile gbpusd_h4

# Sistema continuo (rotación automática, ciclo cada 12 horas)
python main.py

# Ver estadísticas del sistema
python main.py --stats
```

### Para usar la estrategia generada en MT5

1. Abrir la carpeta `output/strategies/aprobadas/NombreEA/`
2. Copiar `NombreEA.mq5` a `C:\Users\...\AppData\Roaming\MetaQuotes\Terminal\...\MQL5\Experts\`
3. En MT5: abrir MetaEditor con F4 y compilar el archivo
4. Arrastrar el EA al gráfico del símbolo/timeframe correspondiente
5. Ingresar los parámetros óptimos del reporte
6. Activar AutoTrading

---

## 14. Hoja de Ruta de Construcción

| Fase | Componente | Estado |
|---|---|---|
| **1** | Knowledge Base manual (KB MQL5) | ✅ Completado |
| **2** | MQL5 Doc Scraper (335 funciones, 0 errores) | ✅ Completado |
| **3** | MCP Server MQL5 (7 herramientas) | ✅ Completado |
| **4** | Core: LLM client, MT5 connector, DB, Memory | ✅ Completado |
| **5** | Coder Agent + Compiler + Self-Healing Loop | ✅ Completado |
| **6** | Designer Agent | ✅ Completado |
| **7** | Backtester Agent (real + mock determinista) | ✅ Completado |
| **8** | Optimizer Agent (Optuna + WF + OOS separados) | ✅ Completado |
| **9** | Research Agent (catálogo + LLM) | ✅ Completado |
| **10** | Validator Agent + reporte .txt | ✅ Completado |
| **11** | Orchestrator + Pipeline + main.py | ✅ Completado |
| **12** | Multi-símbolo: 5 perfiles + config_loader | ✅ Completado |
| **13** | Fix determinismo MockBacktester | ✅ Completado |
| **14** | Fix separación training/OOS en Optimizer | ✅ Completado |
| **15** | Conectar MT5 real + validación end-to-end | 🔜 Pendiente |
| **16** | Ajuste de filtros con datos reales | 🔜 Pendiente |

---

## 15. Decisiones Tomadas Durante la Construcción

| # | Decisión | Resolución |
|---|---|---|
| 1 | Modelo LLM | Gemini 2.5 Flash para todos los agentes (2.0 Flash retirado, Pro inutilizable en free tier) |
| 2 | MCP servers de GitHub | No sirven — son para ejecutar trades, no para generar código. Se construyó propio. |
| 3 | Sintaxis MQL5 | Solución: MCP propio + Knowledge Base embebida en system prompt del Coder |
| 4 | Ollama local | Descartado — 8GB RAM insuficiente para modelos útiles |
| 5 | Multi-símbolo | Opción C: un sistema configurable con perfiles, rotación automática cada 12h |
| 6 | validator_system.txt | Reemplazado por system prompt dinámico en `config_loader.py` |
| 7 | MockBacktester aleatorio | Corregido a determinista con seed por parámetros — Optuna ahora realmente optimiza |
| 8 | Períodos de optimización | Optuna solo ve training set; últimos 2 años reservados como OOS nunca visto |
| 9 | Scraper URLs | 3 URLs incorrectas corregidas: account, strings, dateandtime |
| 10 | google-generativeai deprecada | Migrado a google-genai SDK nueva |
| 11 | PDF reportes | Cambiado a .txt — evita dependencia WeasyPrint, más portable |
| 12 | LangGraph | No se usó — pipeline secuencial Python puro más simple y suficiente |
| 13 | Filtros universales | Reemplazados por filtros específicos por perfil (XAUUSD ≠ EURUSD) |

---

*Fin del documento de arquitectura v2.0*
*Actualizar la Sección 14 a medida que se completen las fases pendientes.*