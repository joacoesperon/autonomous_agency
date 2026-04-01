"""
========================================================================
LLM Provider Wrapper - Universal Interface
========================================================================

Unified API for multiple LLM providers (Gemini, OpenAI, Claude).

This allows switching between LLM providers without changing skill code.

Usage:
    from shared.llm_provider import LLMProvider

    llm = LLMProvider()  # Uses config from brand_config.yml
    response = llm.generate("Your prompt here")

    # Or specify provider explicitly:
    llm = LLMProvider(provider="openai", model="gpt-4o-mini")

Supports:
- Google Gemini (gemini-2.5-flash and related models)
- OpenAI (gpt-4o, gpt-4o-mini, etc.)
- Anthropic Claude (claude-3-5-sonnet, claude-3-5-haiku, etc.)

========================================================================
"""

import os
from typing import Optional, Dict, Any

from shared.provider_profiles import load_brand_config


class LLMProvider:
    """Universal LLM provider wrapper"""

    # Mapping of provider names to required env vars
    PROVIDER_ENV_VARS = {
        "gemini": "GEMINI_API_KEY",
        "openai": "OPENAI_API_KEY",
        "claude": "ANTHROPIC_API_KEY"
    }

    PROVIDER_ALIASES = {
        "chatgpt": "openai",
        "anthropic": "claude",
        "google": "gemini",
        "google-gemini": "gemini",
        "ollama": "openai",
        "openai-compatible": "openai",
    }

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ):
        """
        Initialize LLM provider.

        Args:
            provider: "gemini" | "openai" | "claude" (defaults to config)
            model: Model name (defaults to config)
            temperature: Sampling temperature (defaults to config)
            max_tokens: Max output tokens (defaults to config)
        """

        # Load brand config for defaults
        self.config = self._load_brand_config()

        # Use provided values or fall back to config
        configured_provider = provider or self.config["llm_defaults"]["provider"]
        self.provider = self._normalize_provider_name(configured_provider)

        configured_model = model or self.config["llm_defaults"]["model"]
        # Allow OpenAI-compatible local runtimes (like Ollama) to override model via env.
        if model is None and self.provider == "openai":
            configured_model = os.getenv("OPENAI_MODEL", configured_model)
        self.model = configured_model
        self.temperature = temperature if temperature is not None else self.config["llm_defaults"]["temperature"]
        self.max_tokens = max_tokens or self.config["llm_defaults"]["max_tokens"]

        # Initialize the appropriate client
        self.client = self._init_client()

    def _load_brand_config(self) -> Dict[str, Any]:
        """Load brand config from YAML"""
        return load_brand_config()

    def _normalize_provider_name(self, provider_name: str) -> str:
        normalized = provider_name.strip().lower()
        return self.PROVIDER_ALIASES.get(normalized, normalized)

    def _get_openai_base_url(self) -> Optional[str]:
        """Resolve OpenAI-compatible base URL (OpenAI, Ollama, or other compatible APIs)."""
        return os.getenv("OPENAI_BASE_URL") or os.getenv("OLLAMA_BASE_URL")

    def _resolve_openai_api_key(self, current_api_key: Optional[str]) -> Optional[str]:
        """
        Resolve API key for OpenAI-compatible clients.

        For local OpenAI-compatible runtimes (e.g. Ollama), allow a dummy key when
        no real OpenAI key is present.
        """
        if current_api_key:
            return current_api_key

        base_url = self._get_openai_base_url() or ""
        if "localhost" in base_url or "127.0.0.1" in base_url:
            return os.getenv("OLLAMA_API_KEY") or "ollama"

        return current_api_key

    def _init_client(self):
        """Initialize the appropriate LLM client"""

        env_var = self.PROVIDER_ENV_VARS.get(self.provider)
        api_key = os.getenv(env_var) if env_var else None

        if self.provider == "openai":
            api_key = self._resolve_openai_api_key(api_key)

        if not api_key:
            # Try fallback provider
            fallback_provider = self.config["llm_defaults"].get("fallback_provider")
            if fallback_provider and fallback_provider != self.provider:
                fallback_provider = self._normalize_provider_name(fallback_provider)
                print(f"⚠️  WARNING: {env_var} not set. Trying fallback: {fallback_provider}")
                self.provider = fallback_provider
                fallback_model = self.config["llm_defaults"].get("fallback_model", self.model)
                if self.provider == "openai":
                    # Respect local OpenAI-compatible runtime model override (e.g. Ollama).
                    fallback_model = os.getenv("OPENAI_MODEL", fallback_model)
                self.model = fallback_model
                env_var = self.PROVIDER_ENV_VARS.get(self.provider)
                api_key = os.getenv(env_var) if env_var else None

                if self.provider == "openai":
                    api_key = self._resolve_openai_api_key(api_key)

                if not api_key:
                    raise ValueError(f"{env_var} not set in environment")
            else:
                raise ValueError(f"{env_var} not set in environment")

        if self.provider == "gemini":
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            return genai.GenerativeModel(self.model)

        elif self.provider == "openai":
            from openai import OpenAI
            base_url = self._get_openai_base_url()
            if base_url:
                return OpenAI(api_key=api_key, base_url=base_url)
            return OpenAI(api_key=api_key)

        elif self.provider == "claude":
            import anthropic
            return anthropic.Anthropic(api_key=api_key)

        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def generate(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_mode: bool = False
    ) -> str:
        """
        Generate text from prompt (universal interface).

        Args:
            prompt: Input prompt
            temperature: Override default temperature
            max_tokens: Override default max_tokens
            json_mode: Force JSON output (if supported)

        Returns:
            Generated text string
        """

        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens or self.max_tokens

        try:
            if self.provider == "gemini":
                return self._generate_gemini(prompt, temp, tokens, json_mode)
            elif self.provider == "openai":
                return self._generate_openai(prompt, temp, tokens, json_mode)
            elif self.provider == "claude":
                return self._generate_claude(prompt, temp, tokens, json_mode)
        except Exception as e:
            raise RuntimeError(f"LLM generation failed ({self.provider}): {e}")

    def _generate_gemini(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
        json_mode: bool
    ) -> str:
        """Generate using Google Gemini"""

        generation_config = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }

        if json_mode:
            generation_config["response_mime_type"] = "application/json"

        response = self.client.generate_content(
            prompt,
            generation_config=generation_config
        )

        return response.text.strip()

    def _generate_openai(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
        json_mode: bool
    ) -> str:
        """Generate using OpenAI"""

        params = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if json_mode:
            params["response_format"] = {"type": "json_object"}

        response = self.client.chat.completions.create(**params)
        return response.choices[0].message.content.strip()

    def _generate_claude(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
        json_mode: bool
    ) -> str:
        """Generate using Anthropic Claude"""

        system_message = ""
        if json_mode:
            system_message = "You must respond with valid JSON only. No markdown, no explanations."

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_message,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.content[0].text.strip()

    def get_provider_info(self) -> Dict[str, Any]:
        """Get current provider configuration"""
        return {
            "provider": self.provider,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }


# ========================================================================
# Convenience Functions
# ========================================================================

def create_llm(provider: Optional[str] = None) -> LLMProvider:
    """
    Convenience function to create LLM provider.

    Usage:
        llm = create_llm()  # Uses config defaults
        llm = create_llm("openai")  # Force OpenAI
    """
    return LLMProvider(provider=provider)


# ========================================================================
# CLI Testing
# ========================================================================

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    print("🧪 Testing LLM Provider Wrapper")
    print("=" * 70)

    # Test with config defaults
    print("\n1️⃣  Testing with config defaults...")
    try:
        llm = LLMProvider()
        info = llm.get_provider_info()
        print(f"✅ Initialized: {info['provider']} - {info['model']}")

        response = llm.generate("Say 'Hello, I am working!' in 5 words or less.")
        print(f"📝 Response: {response}")

    except Exception as e:
        print(f"❌ Default provider test failed: {e}")

    # Test JSON mode
    print("\n2️⃣  Testing JSON mode...")
    try:
        llm = LLMProvider()
        prompt = """
        Return a JSON object with:
        - "status": "ok"
        - "message": "Testing JSON mode"

        Return ONLY valid JSON, no markdown.
        """
        response = llm.generate(prompt, json_mode=True)
        print(f"📝 JSON Response: {response}")

    except Exception as e:
        print(f"❌ JSON mode test failed: {e}")

    # Test provider switching (if other keys available)
    print("\n3️⃣  Testing provider auto-detection...")
    providers_to_test = ["gemini", "openai", "claude"]

    for provider in providers_to_test:
        env_var = LLMProvider.PROVIDER_ENV_VARS[provider]
        if os.getenv(env_var):
            print(f"  ✅ {provider.upper()} available")
        else:
            print(f"  ⚠️  {provider.upper()} not configured ({env_var} missing)")

    print("\n" + "=" * 70)
    print("✅ Testing complete!")
