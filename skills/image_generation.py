"""
========================================================================
Custom Skill: image_generation
========================================================================

Generates brand-compliant images using the provider configured in
`shared/brand_config.yml`.
"""

from pathlib import Path
import sys
from typing import Any, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.image_provider import ImageProvider


class ImageGenerationSkill:
    """Skill for configurable AI image generation."""

    def __init__(self):
        self.name = "image_generation"
        self.description = (
            "Generate brand-compliant images using the provider configured in shared/brand_config.yml"
        )

    def execute(
        self,
        prompt: str,
        aspect_ratio: str = "1:1",
        output_path: Optional[str] = None,
        model: Optional[str] = None,
        validate_brand: bool = True,
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        image_provider = ImageProvider(provider=provider)
        return image_provider.generate(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            output_path=output_path,
            validate_brand=validate_brand,
            model_override=model,
        )

    def generate_product_visual(
        self,
        strategy_name: str,
        symbol: str,
        profit_factor: float,
        platform: str = "instagram_post",
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        aspect_ratio_map = {
            "instagram_post": "1:1",
            "instagram_story": "9:16",
            "twitter": "16:9",
            "tiktok": "9:16",
            "youtube_shorts": "9:16",
            "facebook": "1:1",
        }
        aspect_ratio = aspect_ratio_map.get(platform, "1:1")
        prompt = f"""
        Minimalist fintech trading dashboard showing {symbol} chart.
        Main element: candlestick chart with bullish Neon Green candles.
        Side panel with performance metric: '{profit_factor:.2f} PF' in large text.
        Strategy name '{strategy_name}' in Light Gray subtitle.
        Clean, premium, professional. No clutter.
        """
        return self.execute(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            provider=provider,
        )

    def generate_educational_visual(
        self,
        theme: str,
        platform: str = "instagram_post",
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        aspect_ratio_map = {
            "instagram_post": "1:1",
            "instagram_story": "9:16",
            "twitter": "16:9",
            "tiktok": "9:16",
            "youtube_shorts": "9:16",
            "facebook": "1:1",
        }
        aspect_ratio = aspect_ratio_map.get(platform, "1:1")
        theme_prompts = {
            "volatility": "Abstract visualization of market volatility, chaotic red lines transforming into calm green systematic patterns",
            "discipline": "Minimalist clock/calendar showing 24/7 automated trading, geometric precision",
            "automation": "Robotic or AI elements managing trading charts, futuristic but professional",
            "backtesting": "Timeline visualization showing 10 plus years of data, historical chart analysis",
            "risk": "Drawdown graph with clear risk zones, professional risk management visual",
        }
        prompt = theme_prompts.get(
            theme.lower(),
            f"Minimalist fintech visualization about {theme}, abstract and professional",
        )
        return self.execute(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            provider=provider,
        )

    def generate_with_dynamic_prompt(
        self,
        topic: str,
        style: str = "minimal",
        platform: str = "instagram_post",
        content_type: str = "educational",
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            from skills.dynamic_prompt_generator import DynamicPromptGeneratorSkill

            prompt_gen = DynamicPromptGeneratorSkill()
            prompt_result = prompt_gen.execute(
                topic=topic,
                style=style,
                platform=platform,
                content_type=content_type,
            )

            if prompt_result.get("success"):
                prompt = prompt_result.get("prompt")
                aspect_ratio = prompt_result.get("aspect_ratio", "1:1")
                dynamic_used = True
            else:
                prompt = f"Minimalist fintech visualization about {topic}, {style} style, brand colors"
                aspect_ratio = "1:1"
                dynamic_used = False
        except ImportError:
            prompt = f"Minimalist fintech visualization about {topic}, {style} style, brand colors"
            aspect_ratio = "1:1"
            dynamic_used = False

        result = self.execute(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            validate_brand=True,
            provider=provider,
        )
        result["dynamic_prompt_used"] = dynamic_used
        if dynamic_used:
            result["topic"] = topic
            result["style"] = style
            result["content_type"] = content_type
        return result


def get_skill():
    return ImageGenerationSkill()


if __name__ == "__main__":
    skill = ImageGenerationSkill()

    print("Testing image_generation skill...")
    result = skill.generate_product_visual(
        strategy_name="EMA50_200_RSI_v1",
        symbol="EURUSD",
        profit_factor=1.87,
        platform="instagram_post",
    )

    print(f"Success: {result.get('success')}")
    print(f"Message: {result.get('message')}")
    if result.get("success"):
        print(f"Provider: {result.get('provider')}")
        print(f"Image URL: {result.get('image_url')}")
        print(f"Local Path: {result.get('local_path')}")
