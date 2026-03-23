"""
agents/compiler.py
==================
Compiler Agent — compila el .mq5 y ejecuta el self-healing loop.

Flujo:
1. Recibe el .mq5 del Coder Agent
2. Llama a MetaEditor para compilar
3. Si hay errores → consulta MCP get_error_fix() → pide al LLM que corrija
4. Reintenta compilación (máx 4 veces)
5. Si sigue fallando → señaliza al Coder para rediseñar desde cero
6. Si compila → pasa el .ex5 al Backtester
"""

import re
import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "mql5_mcp_server"))

from core.llm_client    import get_llm_client
from core.database      import get_database
from core.mt5_connector import get_mt5_connector

log = logging.getLogger(__name__)

MAX_FIX_ATTEMPTS = 4   # intentos máximos del self-healing loop
KB_PATH = Path(__file__).parent.parent / "mql5_mcp_server" / "data" / "mql5_knowledge_base.md"


# ─────────────────────────────────────────────
# RESULTADO DE COMPILACIÓN
# ─────────────────────────────────────────────

class CompilationResult:
    def __init__(
        self,
        success:       bool,
        mq5_path:      Optional[Path] = None,
        ex5_path:      Optional[Path] = None,
        errors:        list[str]      = None,
        warnings:      list[str]      = None,
        attempts:      int            = 0,
        final_code:    str            = "",
    ):
        self.success    = success
        self.mq5_path   = mq5_path
        self.ex5_path   = ex5_path
        self.errors     = errors or []
        self.warnings   = warnings or []
        self.attempts   = attempts
        self.final_code = final_code


# ─────────────────────────────────────────────
# COMPILER AGENT
# ─────────────────────────────────────────────

class CompilerAgent:
    """
    Compila archivos .mq5 y ejecuta el self-healing loop cuando hay errores.
    """

    def __init__(self):
        self.llm       = get_llm_client()
        self.db        = get_database()
        self.mt5       = get_mt5_connector()
        self._kb_text  = self._load_knowledge_base()

        from tools.get_error_fix   import get_error_fix
        from tools.check_forbidden import check_forbidden
        self._get_error_fix    = get_error_fix
        self._check_forbidden  = check_forbidden

        log.info("CompilerAgent inicializado")

    def _load_knowledge_base(self) -> str:
        if KB_PATH.exists():
            return KB_PATH.read_text(encoding="utf-8")
        log.warning("Knowledge base no encontrada")
        return ""

    # ── Método principal ──────────────────────────────────────────────

    def compile(
        self,
        mq5_path: Path,
        cycle_id: Optional[int] = None,
    ) -> CompilationResult:
        """
        Compila un .mq5 con self-healing loop automático.

        Args:
            mq5_path: Path al archivo .mq5 a compilar
            cycle_id: ID del ciclo para logging

        Returns:
            CompilationResult con éxito/fallo y el código final
        """
        log.info(f"[Compiler] Compilando: {mq5_path.name}")

        current_code = mq5_path.read_text(encoding="utf-8")
        all_errors   = []

        for attempt in range(1, MAX_FIX_ATTEMPTS + 1):
            log.info(f"[Compiler] Intento {attempt}/{MAX_FIX_ATTEMPTS}")

            # ── Guardar código actual al archivo ──
            mq5_path.write_text(current_code, encoding="utf-8")

            # ── Intentar compilar ──
            result = self.mt5.compile_ea(mq5_path)

            if result.success:
                log.info(f"[Compiler] ✅ Compiló en intento {attempt}")

                # Registrar en DB
                if cycle_id:
                    self.db.update_cycle(cycle_id,
                        compile_attempts = attempt,
                        current_phase    = "backtest",
                    )

                return CompilationResult(
                    success    = True,
                    mq5_path   = mq5_path,
                    ex5_path   = result.compiled_path,
                    warnings   = result.warnings,
                    attempts   = attempt,
                    final_code = current_code,
                )

            # ── Compilación falló — self-healing ──
            errors = result.errors
            all_error_text = "\n".join(errors)
            all_errors.extend(errors)

            log.warning(f"[Compiler] ❌ Falló — {len(errors)} errores:")
            for err in errors[:3]:
                log.warning(f"   {err}")

            if attempt < MAX_FIX_ATTEMPTS:
                log.info(f"[Compiler] Iniciando self-healing (intento {attempt})...")
                current_code = self._heal(current_code, all_error_text, attempt)
            else:
                log.error(f"[Compiler] Agotados {MAX_FIX_ATTEMPTS} intentos")

        # Falló después de todos los intentos
        if cycle_id:
            self.db.update_cycle(cycle_id,
                compile_attempts = MAX_FIX_ATTEMPTS,
                current_phase    = "error",
                discard_reason   = f"No compiló tras {MAX_FIX_ATTEMPTS} intentos",
            )

        return CompilationResult(
            success  = False,
            mq5_path = mq5_path,
            errors   = all_errors,
            attempts = MAX_FIX_ATTEMPTS,
        )

    # ── Self-Healing Loop ─────────────────────────────────────────────

    def _heal(self, code: str, error_text: str, attempt: int) -> str:
        """
        Corrige el código usando el error del compilador + MCP + LLM.

        Args:
            code:       Código MQL5 actual (con errores)
            error_text: Mensajes de error del compilador MT5
            attempt:    Número de intento actual

        Returns:
            Código corregido
        """
        # ── 1. Consultar MCP por fixes documentados ──
        fixes_context = []
        error_lines   = error_text.strip().splitlines()

        for error_line in error_lines[:5]:   # máximo 5 errores a la vez
            if error_line.strip():
                fix = self._get_error_fix(error_line)
                if "No se encontró" not in fix:
                    fixes_context.append(fix)

        fixes_text = "\n\n".join(fixes_context) if fixes_context else \
            "No se encontraron fixes específicos. Analizar el error y corregir."

        # ── 2. Verificar también con check_forbidden ──
        forbidden_check = self._check_forbidden(code)
        forbidden_context = ""
        if "VERIFICACIÓN FALLIDA" in forbidden_check:
            forbidden_context = f"\n\nADICIONAL — Violaciones MQL4 detectadas:\n{forbidden_check}"

        # ── 3. Construir prompt de corrección ──
        prompt = f"""Eres un experto en MQL5. El siguiente código tiene errores de compilación en MetaTrader 5.
Corrígelo siguiendo las instrucciones.

═══════════════════════════
ERRORES DEL COMPILADOR MT5
═══════════════════════════
{error_text}

═══════════════════════════
FIXES DOCUMENTADOS (aplicar estos)
═══════════════════════════
{fixes_text}{forbidden_context}

═══════════════════════════
REGLAS DE CORRECCIÓN
═══════════════════════════
- Corregir TODOS los errores listados
- NO usar variables MQL4: Bid, Ask, Point, Digits
- NO usar funciones MQL4: AccountBalance(), OrderSend() con 10 params, etc
- SIEMPRE usar ArraySetAsSeries(buffer, true) antes de CopyBuffer()
- SIEMPRE validar handles != INVALID_HANDLE en OnInit()
- SIEMPRE usar NormalizeDouble(precio, _Digits) antes de órdenes
- No cambiar la lógica de trading, solo corregir errores de sintaxis/compilación
- Responde SOLO con el código corregido, sin explicaciones ni markdown

═══════════════════════════
CÓDIGO A CORREGIR
═══════════════════════════
{code}
"""

        # ── 4. Pedir corrección al LLM ──
        log.info(f"[Self-Healing] Pidiendo corrección al LLM (intento {attempt})...")

        raw_response = self.llm.flash(
            prompt = prompt,
            system = (
                "Eres un experto en MQL5. Solo corriges errores de compilación. "
                "Nunca usas sintaxis MQL4. Siempre respondes solo con código MQL5 limpio."
            ),
            temperature = 0.1,   # muy baja temperatura para correcciones precisas
        )

        fixed_code = self.llm.extract_code(raw_response, language="cpp")

        # Si el LLM devolvió algo vacío, retornar el código original
        if len(fixed_code) < 100:
            log.warning("[Self-Healing] LLM devolvió respuesta demasiado corta, usando código original")
            return code

        log.info(f"[Self-Healing] Código corregido recibido ({len(fixed_code)} chars)")
        return fixed_code


# ─────────────────────────────────────────────
# FALLBACK: compilar sin MT5 (modo simulado para testing)
# ─────────────────────────────────────────────

class MockCompilerAgent(CompilerAgent):
    """
    Versión de prueba del CompilerAgent que no necesita MT5.
    Simula la compilación verificando sintaxis básica con check_forbidden.
    Útil para desarrollo y testing sin MT5 conectado.
    """

    def compile(
        self,
        mq5_path: Path,
        cycle_id: Optional[int] = None,
    ) -> CompilationResult:

        log.info(f"[MockCompiler] Verificando (sin MT5): {mq5_path.name}")
        code = mq5_path.read_text(encoding="utf-8")

        # Verificar con check_forbidden como proxy de compilación
        check = self._check_forbidden(code)

        if "VERIFICACIÓN PASADA" in check:
            log.info("[MockCompiler] ✅ Código pasa verificación MQL5")
            return CompilationResult(
                success    = True,
                mq5_path   = mq5_path,
                attempts   = 1,
                final_code = code,
            )
        else:
            log.warning("[MockCompiler] Violaciones encontradas, aplicando self-healing...")
            fixed_code = self._heal(code, check, 1)
            mq5_path.write_text(fixed_code, encoding="utf-8")

            # Segunda verificación
            check2 = self._check_forbidden(fixed_code)
            success = "VERIFICACIÓN PASADA" in check2

            return CompilationResult(
                success    = success,
                mq5_path   = mq5_path,
                attempts   = 2,
                final_code = fixed_code,
                errors     = [] if success else ["Violaciones MQL4 persistentes"],
            )


# ─────────────────────────────────────────────
# FACTORY — elige el compiler según si MT5 está disponible
# ─────────────────────────────────────────────

def get_compiler() -> CompilerAgent:
    """
    Retorna el compiler apropiado:
    - CompilerAgent real si MT5 está disponible
    - MockCompilerAgent si MT5 no está conectado (modo desarrollo)
    """
    mt5 = get_mt5_connector()
    if mt5.metaeditor_path and mt5.metaeditor_path.exists():
        log.info("Usando CompilerAgent real (MetaEditor encontrado)")
        return CompilerAgent()
    else:
        log.warning("MetaEditor no encontrado — usando MockCompilerAgent")
        return MockCompilerAgent()


# ─────────────────────────────────────────────
# TEST RÁPIDO
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Crear un .mq5 de prueba con un error MQL4 intencional
    test_dir  = Path("output/strategies/descartadas")
    test_dir.mkdir(parents=True, exist_ok=True)
    # Usar el EA ya generado por el Coder
    test_file = Path("output/strategies/descartadas/EMA50_200_RSI_Test.mq5")

    if not test_file.exists():
        print("❌ No se encontró EMA50_200_RSI_Test.mq5 — ejecutar agents/coder.py primero")
        sys.exit(1)

    print(f"Compilando: {test_file}")
    compiler = get_compiler()
    result   = compiler.compile(test_file)

    print(f"\nResultado:")
    print(f"  Éxito:    {result.success}")
    print(f"  Intentos: {result.attempts}")
    if result.errors:
        for err in result.errors[:5]:
            print(f"  Error: {err}")
    if result.success:
        print("✅ Compilación exitosa")