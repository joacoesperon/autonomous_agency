"""
core/llm_client.py
==================
Wrapper unificado para Gemini 2.0 Flash y Gemini 2.5 Pro.
Usa la nueva SDK google-genai (reemplaza google-generativeai deprecada).

Instalación:
    pip install google-genai

Uso:
    from core.llm_client import LLMClient
    llm = LLMClient()
    respuesta = llm.flash("Diseña una estrategia de trading...")
    codigo    = llm.pro("Genera el código MQL5 para...")
"""

import os
import re
import time
import logging
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────

FLASH_MODEL = "gemini-2.5-flash"
PRO_MODEL   = "gemini-2.5-flash"

FLASH_RPM   = 10
PRO_RPM     = 5
FLASH_DELAY = 60 / FLASH_RPM   # 4 segundos entre requests
PRO_DELAY   = 60 / PRO_RPM     # 30 segundos entre requests


# ─────────────────────────────────────────────
# CLIENTE
# ─────────────────────────────────────────────

class LLMClient:
    """
    Cliente unificado para Gemini Flash y Pro.
    Gestiona rate limiting, reintentos y logging automáticamente.
    """

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY no encontrada. "
                "Verificar que está en el archivo .env"
            )

        self.client      = genai.Client(api_key=api_key)
        self._last_flash = 0.0
        self._last_pro   = 0.0

        log.info("LLMClient inicializado (google-genai SDK)")

    # ── Gemini 2.0 Flash ──────────────────────────────────────────────

    def flash(
        self,
        prompt:      str,
        system:      Optional[str] = None,
        temperature: float = 0.3,
        max_retries: int = 3,
    ) -> str:
        """
        Llama a Gemini 2.0 Flash. Usar para tareas generales:
        orchestrator, researcher, designer, validator.
        Límite gratuito: 1,500 requests/día, 15/minuto.
        """
        return self._call(
            model_name  = FLASH_MODEL,
            prompt      = prompt,
            system      = system,
            temperature = temperature,
            min_delay   = FLASH_DELAY,
            last_attr   = "_last_flash",
            max_retries = max_retries,
        )

    # ── Gemini 2.5 Pro ────────────────────────────────────────────────

    def pro(
        self,
        prompt:      str,
        system:      Optional[str] = None,
        temperature: float = 0.2,
        max_retries: int = 3,
    ) -> str:
        """
        Llama a Gemini 2.5 Pro. Usar SOLO para generación de código MQL5
        y self-healing loop.
        Límite gratuito: 25 requests/día, 2/minuto.
        """
        return self._call(
            model_name  = PRO_MODEL,
            prompt      = prompt,
            system      = system,
            temperature = temperature,
            min_delay   = PRO_DELAY,
            last_attr   = "_last_pro",
            max_retries = max_retries,
        )

    # ── Llamada interna con rate limiting y reintentos ────────────────

    def _call(
        self,
        model_name:  str,
        prompt:      str,
        system:      Optional[str],
        temperature: float,
        min_delay:   float,
        last_attr:   str,
        max_retries: int,
    ) -> str:

        # Rate limiting local
        elapsed = time.time() - getattr(self, last_attr)
        if elapsed < min_delay:
            wait = min_delay - elapsed
            log.debug(f"[{model_name}] Esperando {wait:.1f}s (rate limit local)")
            time.sleep(wait)

        # Config de generación
        config = types.GenerateContentConfig(
            temperature        = temperature,
            max_output_tokens  = 8192,
            system_instruction = system,
        )

        # Reintentos con backoff exponencial
        for attempt in range(1, max_retries + 1):
            try:
                log.debug(f"[{model_name}] Intento {attempt} — {prompt[:80]}...")

                response = self.client.models.generate_content(
                    model    = model_name,
                    contents = prompt,
                    config   = config,
                )

                setattr(self, last_attr, time.time())
                text = response.text.strip()
                log.debug(f"[{model_name}] Respuesta OK — {len(text)} chars")
                return text

            except Exception as e:
                err = str(e).lower()

                if "429" in err or "quota" in err or "rate" in err:
                    wait = 60 * attempt
                    log.warning(f"[{model_name}] Rate limit servidor. Esperando {wait}s")
                    time.sleep(wait)

                elif "daily" in err or "exhausted" in err:
                    raise RuntimeError(
                        f"Límite diario de {model_name} agotado. "
                        "Esperar hasta mañana o revisar aistudio.google.com"
                    ) from e

                else:
                    wait = 10 * attempt
                    log.warning(f"[{model_name}] Error: {e}. Reintentando en {wait}s")
                    time.sleep(wait)

        raise RuntimeError(f"[{model_name}] Falló después de {max_retries} intentos.")

    # ── Utilidades ────────────────────────────────────────────────────

    def extract_code(self, text: str, language: str = "cpp") -> str:
        """
        Extrae el bloque de código de una respuesta con markdown.
        Útil cuando el modelo devuelve ```cpp ... ``` en lugar de código puro.
        """
        for pattern in [
            rf"```{language}\s*\n(.*?)```",
            r"```mql5\s*\n(.*?)```",
            r"```\s*\n(.*?)```",
        ]:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                return match.group(1).strip()
        return text.strip()

    def count_pro_calls_today(self) -> int:
        """Cuántas llamadas a Pro se hicieron hoy."""
        try:
            from core.database import get_database
            return get_database().count_llm_calls_today(model="pro")
        except Exception:
            return -1


# ─────────────────────────────────────────────
# SINGLETON
# ─────────────────────────────────────────────

_client: Optional[LLMClient] = None

def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client


# ─────────────────────────────────────────────
# TEST RÁPIDO
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Probando LLMClient (google-genai SDK)...\n")
    llm = LLMClient()

    print("[Flash] Enviando mensaje de prueba...")
    resp = llm.flash("Responde solo con: OK Flash funcionando")
    print(f"Respuesta: {resp}\n")

    print("[Pro] Enviando mensaje de prueba (usa 1 de 25 requests diarios)...")
    resp = llm.pro("Responde solo con: OK Pro funcionando")
    print(f"Respuesta: {resp}\n")

    print("✅ LLMClient funcionando correctamente")