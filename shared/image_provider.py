"""
========================================================================
Image Provider Wrapper - Universal Interface
========================================================================

Unified API for multiple image generation providers.

Implemented providers:
- Flux via Replicate
- SDXL via Replicate
- DALL-E via OpenAI

Configurable placeholders are kept for Midjourney and Ideogram so the
active provider can still be selected from `shared/brand_config.yml`.
"""

import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests
import yaml


class ImageProvider:
    """Universal image generation provider wrapper."""

    PROVIDER_ENV_VARS = {
        "flux": "REPLICATE_API_TOKEN",
        "dalle": "OPENAI_API_KEY",
        "midjourney": "MIDJOURNEY_API_KEY",
        "sdxl": "REPLICATE_API_TOKEN",
        "ideogram": "IDEOGRAM_API_KEY",
    }

    VALID_ASPECT_RATIOS = {"1:1", "9:16", "16:9", "4:5", "1.91:1"}

    def __init__(self, provider: Optional[str] = None):
        self.project_root = Path(__file__).resolve().parent.parent
        self.config = self._load_brand_config()
        configured_provider = self.config["image_generation"]["provider"]
        self.provider = provider or configured_provider

        if self.provider not in self.config["image_generation"]:
            raise ValueError(f"Unsupported provider in brand_config.yml: {self.provider}")

        self.provider_config = self.config["image_generation"][self.provider]
        self.client = None

    def _load_brand_config(self) -> Dict[str, Any]:
        config_path = Path(__file__).parent / "brand_config.yml"
        if not config_path.exists():
            raise FileNotFoundError(f"brand_config.yml not found at {config_path}")
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _get_api_key(self, provider: Optional[str] = None) -> Optional[str]:
        provider_name = provider or self.provider
        env_var = self.PROVIDER_ENV_VARS.get(provider_name)
        if not env_var:
            return None
        return os.getenv(env_var)

    def _ensure_client(self):
        if self.client is not None:
            return self.client

        api_key = self._get_api_key()
        env_var = self.PROVIDER_ENV_VARS.get(self.provider, "API key")
        if not api_key:
            raise ValueError(f"{env_var} not set in environment")

        if self.provider in {"flux", "sdxl"}:
            import replicate

            os.environ["REPLICATE_API_TOKEN"] = api_key
            self.client = replicate
            return self.client

        if self.provider == "dalle":
            from openai import OpenAI

            self.client = OpenAI(api_key=api_key)
            return self.client

        self.client = None
        return self.client

    def _resolve_output_path(self, output_path: Optional[str], extension: str = "jpg") -> str:
        if output_path:
            resolved = Path(output_path)
            if not resolved.is_absolute():
                resolved = self.project_root / resolved
        else:
            generated_dir = self.project_root / "agents" / "marketer" / "content" / "generated"
            generated_dir.mkdir(parents=True, exist_ok=True)
            resolved = generated_dir / f"image_{int(time.time())}.{extension}"

        resolved.parent.mkdir(parents=True, exist_ok=True)
        return str(resolved)

    def _build_brand_palette(self) -> str:
        colors = self.config["visual_identity"]["color_palette"]
        aesthetic = self.config["visual_identity"]["aesthetic"]
        return (
            "Color palette STRICT requirements:\n"
            f"- Background: {colors['primary']} (solid or radial gradient)\n"
            f"- Highlights: {colors['secondary']} (profits, key metrics, max 20% of image)\n"
            f"- Text: {colors['tertiary']} (labels, body text)\n"
            f"- CTAs: {colors['accent']} (buttons, action prompts only)\n"
            f"{aesthetic['style']}, {aesthetic['reference']}"
        )

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = "1:1",
        output_path: Optional[str] = None,
        validate_brand: bool = True,
        model_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not prompt or len(prompt.strip()) < 5:
            return {
                "success": False,
                "provider": self.provider,
                "message": "Prompt too short. Minimum 5 characters.",
            }

        if aspect_ratio not in self.VALID_ASPECT_RATIOS:
            return {
                "success": False,
                "provider": self.provider,
                "message": f"Invalid aspect ratio. Use one of: {sorted(self.VALID_ASPECT_RATIOS)}",
            }

        full_prompt = prompt
        if validate_brand:
            full_prompt = f"{prompt}\n\n{self._build_brand_palette()}"

        resolved_output_path = self._resolve_output_path(output_path)

        try:
            if self.provider == "flux":
                self._ensure_client()
                return self._generate_flux(full_prompt, aspect_ratio, resolved_output_path, model_override)
            if self.provider == "dalle":
                self._ensure_client()
                return self._generate_dalle(full_prompt, aspect_ratio, resolved_output_path, model_override)
            if self.provider == "sdxl":
                self._ensure_client()
                return self._generate_sdxl(full_prompt, aspect_ratio, resolved_output_path, model_override)
            if self.provider == "midjourney":
                return self._not_implemented("Midjourney")
            if self.provider == "ideogram":
                return self._not_implemented("Ideogram")

            return {
                "success": False,
                "provider": self.provider,
                "message": f"Unsupported provider: {self.provider}",
            }
        except Exception as exc:
            return {
                "success": False,
                "provider": self.provider,
                "message": f"Image generation failed ({self.provider}): {exc}",
            }

    def _download_to_path(self, media_url: str, output_path: str) -> None:
        response = requests.get(media_url, timeout=30)
        response.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(response.content)

    def _generate_flux(
        self,
        prompt: str,
        aspect_ratio: str,
        output_path: str,
        model_override: Optional[str],
    ) -> Dict[str, Any]:
        model = model_override or self.provider_config["model"]
        output = self.client.run(
            model,
            input={
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "output_format": "jpg",
                "output_quality": 90,
                "num_outputs": 1,
            },
        )
        image_url = output[0] if isinstance(output, list) else str(output)
        self._download_to_path(image_url, output_path)
        return {
            "success": True,
            "provider": self.provider,
            "model": model,
            "image_url": image_url,
            "local_path": output_path,
            "prompt_used": prompt,
            "cost": self.provider_config.get("cost_per_image", 0.0),
            "aspect_ratio": aspect_ratio,
            "message": f"Image generated with {model}",
        }

    def _generate_dalle(
        self,
        prompt: str,
        aspect_ratio: str,
        output_path: str,
        model_override: Optional[str],
    ) -> Dict[str, Any]:
        size_map = {
            "1:1": "1024x1024",
            "16:9": "1792x1024",
            "9:16": "1024x1792",
        }
        model = model_override or self.provider_config["model"]
        size = size_map.get(aspect_ratio, self.provider_config.get("size", "1024x1024"))
        quality = self.provider_config.get("quality", "standard")

        response = self.client.images.generate(
            model=model,
            prompt=prompt,
            size=size,
            quality=quality,
            n=1,
        )

        image_url = response.data[0].url
        self._download_to_path(image_url, output_path)
        return {
            "success": True,
            "provider": self.provider,
            "model": model,
            "image_url": image_url,
            "local_path": output_path,
            "prompt_used": prompt,
            "cost": self.provider_config.get("cost_per_image", 0.0),
            "aspect_ratio": aspect_ratio,
            "message": f"Image generated with {model} ({quality})",
        }

    def _generate_sdxl(
        self,
        prompt: str,
        aspect_ratio: str,
        output_path: str,
        model_override: Optional[str],
    ) -> Dict[str, Any]:
        model = model_override or self.provider_config["model"]
        output = self.client.run(
            model,
            input={
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "output_format": "jpg",
                "num_outputs": 1,
            },
        )
        image_url = output[0] if isinstance(output, list) else str(output)
        self._download_to_path(image_url, output_path)
        return {
            "success": True,
            "provider": self.provider,
            "model": model,
            "image_url": image_url,
            "local_path": output_path,
            "prompt_used": prompt,
            "cost": self.provider_config.get("cost_per_image", 0.0),
            "aspect_ratio": aspect_ratio,
            "message": f"Image generated with {model}",
        }

    def _not_implemented(self, provider_label: str) -> Dict[str, Any]:
        env_var = self.PROVIDER_ENV_VARS.get(self.provider, "API key")
        return {
            "success": False,
            "provider": self.provider,
            "message": (
                f"{provider_label} is configurable in shared/brand_config.yml but its API integration "
                f"is not implemented yet. Configure {env_var} after adding the provider-specific client."
            ),
        }

    def get_provider_info(self) -> Dict[str, Any]:
        env_var = self.PROVIDER_ENV_VARS.get(self.provider)
        return {
            "provider": self.provider,
            "cost_per_image": self.provider_config.get("cost_per_image", 0),
            "speed": self.provider_config.get("speed", "unknown"),
            "notes": self.provider_config.get("notes", ""),
            "config": self.provider_config,
            "api_key_env": env_var,
            "api_key_configured": bool(self._get_api_key()),
        }


def create_image_provider(provider: Optional[str] = None) -> ImageProvider:
    return ImageProvider(provider=provider)


if __name__ == "__main__":
    print("Testing Image Provider Wrapper")
    print("=" * 70)

    image_provider = ImageProvider()
    info = image_provider.get_provider_info()
    print(f"Provider: {info['provider']}")
    print(f"API env var: {info['api_key_env']}")
    print(f"Configured: {info['api_key_configured']}")
    print(f"Notes: {info['notes']}")
