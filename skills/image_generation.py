"""
========================================================================
Custom Skill: image_generation
========================================================================

Generates brand-compliant images using Replicate API (Flux model).

This skill creates visual content following Jess Trading brand guidelines:
- Carbon Black backgrounds
- Neon Green highlights
- Premium fintech aesthetic
- Multiple aspect ratios for different platforms

Usage in OpenClaw:
    Use the skill image_generation to create an image:
    - Prompt: "Minimalist trading dashboard, dark mode, green profits"
    - Aspect ratio: "1:1" (for Instagram) or "9:16" (for stories)
    - Output path: "openclaw/agents/marketer/content/generated/image_001.jpg"

Get API key: https://replicate.com

========================================================================
"""

import os
import time
import requests
from typing import Dict, Optional, Any

try:
    import replicate
except ImportError:
    print("⚠️  ERROR: replicate library not installed")
    print("Run: pip install replicate")
    exit(1)


class ImageGenerationSkill:
    """Skill for AI image generation using Replicate"""

    # Brand color palette for prompts
    BRAND_PALETTE_PROMPT = """
    Color palette STRICT requirements:
    - Background: Carbon Black #101010 (solid or radial gradient)
    - Highlights: Neon Green #45B14F (profits, key metrics, max 20% of image)
    - Text: Light Gray #A7A7A7 (labels, body text)
    - CTAs: Electric Blue #2979FF (buttons, action prompts only)
    Premium fintech aesthetic, dark mode, Apple keynote style, glassmorphism
    """

    # Aspect ratios for different platforms
    ASPECT_RATIOS = {
        "1:1": "square",       # Instagram post
        "9:16": "vertical",    # Instagram story
        "16:9": "horizontal",  # Twitter, YouTube
        "4:5": "portrait",     # Instagram portrait
        "1.91:1": "wide"       # LinkedIn
    }

    def __init__(self):
        self.name = "image_generation"
        self.description = "Generate brand-compliant images using AI (Replicate/Flux)"

        self.api_token = os.getenv("REPLICATE_API_TOKEN")

        if not self.api_token:
            print("⚠️  WARNING: REPLICATE_API_TOKEN not set in .env")
        else:
            os.environ["REPLICATE_API_TOKEN"] = self.api_token

    def execute(
        self,
        prompt: str,
        aspect_ratio: str = "1:1",
        output_path: Optional[str] = None,
        model: str = "black-forest-labs/flux-schnell",
        validate_brand: bool = True
    ) -> Dict[str, Any]:
        """
        Generate image using AI.

        Args:
            prompt: Description of image to generate
            aspect_ratio: "1:1", "9:16", "16:9", "4:5", or "1.91:1"
            output_path: Where to save generated image
            model: Replicate model to use (default: Flux Schnell - fast & free)
            validate_brand: If True, inject brand palette requirements

        Returns:
            {
                "success": bool,
                "image_url": str,
                "local_path": str,
                "prompt_used": str,
                "model": str,
                "message": str
            }
        """

        if not self.api_token:
            return {
                "success": False,
                "message": "REPLICATE_API_TOKEN not configured"
            }

        # Build full prompt with brand requirements
        if validate_brand:
            full_prompt = f"{prompt}\n\n{self.BRAND_PALETTE_PROMPT}"
        else:
            full_prompt = prompt

        # Validate aspect ratio
        if aspect_ratio not in self.ASPECT_RATIOS:
            return {
                "success": False,
                "message": f"Invalid aspect ratio. Use: {list(self.ASPECT_RATIOS.keys())}"
            }

        # Generate output path if not provided
        if not output_path:
            timestamp = int(time.time())
            os.makedirs("openclaw/agents/marketer/content/generated", exist_ok=True)
            output_path = f"openclaw/agents/marketer/content/generated/image_{timestamp}.jpg"

        # Call Replicate API
        try:
            output = replicate.run(
                model,
                input={
                    "prompt": full_prompt,
                    "aspect_ratio": aspect_ratio,
                    "output_format": "jpg",
                    "output_quality": 90,
                    "num_outputs": 1
                }
            )

            # Get image URL (output is a list for Flux models)
            if isinstance(output, list) and len(output) > 0:
                image_url = output[0]
            else:
                image_url = str(output)

        except Exception as e:
            return {
                "success": False,
                "message": f"Image generation failed: {e}"
            }

        # Download image to local path
        try:
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()

            with open(output_path, 'wb') as f:
                f.write(response.content)

        except Exception as e:
            return {
                "success": False,
                "image_url": image_url,
                "message": f"Downloaded image URL but failed to save locally: {e}"
            }

        return {
            "success": True,
            "image_url": image_url,
            "local_path": output_path,
            "prompt_used": full_prompt,
            "model": model,
            "aspect_ratio": aspect_ratio,
            "message": f"Image generated and saved to {output_path}"
        }

    def generate_product_visual(
        self,
        strategy_name: str,
        symbol: str,
        profit_factor: float,
        platform: str = "instagram_post"
    ) -> Dict[str, Any]:
        """
        Convenience method for generating product showcase visuals.

        Args:
            strategy_name: Name of trading strategy
            symbol: Trading symbol (EURUSD, XAUUSD, etc.)
            profit_factor: Profit factor metric
            platform: Target platform (determines aspect ratio)

        Returns:
            Same as execute()
        """

        # Map platform to aspect ratio
        aspect_ratio_map = {
            "instagram_post": "1:1",
            "instagram_story": "9:16",
            "twitter": "16:9",
            "tiktok": "9:16",
            "youtube_shorts": "9:16",
            "facebook": "1:1"
        }

        aspect_ratio = aspect_ratio_map.get(platform, "1:1")

        # Build optimized prompt
        prompt = f"""
        Minimalist fintech trading dashboard showing {symbol} chart.
        Main element: candlestick chart with bullish Neon Green candles.
        Side panel with performance metric: '{profit_factor:.2f} PF' in large text.
        Strategy name '{strategy_name}' in Light Gray subtitle.
        Clean, premium, professional. No clutter.
        """

        return self.execute(
            prompt=prompt,
            aspect_ratio=aspect_ratio
        )

    def generate_educational_visual(
        self,
        theme: str,
        platform: str = "instagram_post"
    ) -> Dict[str, Any]:
        """
        Convenience method for educational content visuals.

        Args:
            theme: Educational theme (e.g., "volatility", "discipline", "automation")
            platform: Target platform

        Returns:
            Same as execute()
        """

        aspect_ratio_map = {
            "instagram_post": "1:1",
            "instagram_story": "9:16",
            "twitter": "16:9",
            "tiktok": "9:16",
            "youtube_shorts": "9:16",
            "facebook": "1:1"
        }

        aspect_ratio = aspect_ratio_map.get(platform, "1:1")

        # Theme-based prompts
        theme_prompts = {
            "volatility": "Abstract visualization of market volatility, chaotic red lines transforming into calm green systematic patterns",
            "discipline": "Minimalist clock/calendar showing 24/7 automated trading, geometric precision",
            "automation": "Robotic/AI elements managing trading charts, futuristic but professional",
            "backtesting": "Timeline visualization showing 10+ years of data, historical chart analysis",
            "risk": "Drawdown graph with clear risk zones, professional risk management visual"
        }

        prompt = theme_prompts.get(
            theme.lower(),
            f"Minimalist fintech visualization about {theme}, abstract and professional"
        )

        return self.execute(
            prompt=prompt,
            aspect_ratio=aspect_ratio
        )

    def generate_with_dynamic_prompt(
        self,
        topic: str,
        style: str = "minimal",
        platform: str = "instagram_post",
        content_type: str = "educational"
    ) -> Dict[str, Any]:
        """
        Generate image using dynamic prompt generator for unique, contextual prompts.

        This method uses the dynamic_prompt_generator skill to create a unique prompt
        based on the topic, avoiding repetitive template-based generation.

        Args:
            topic: Main topic/theme of the image
            style: Visual style ("dashboard", "minimal", "abstract", "chart")
            platform: Target platform
            content_type: "educational", "product", "social_proof", "community"

        Returns:
            Same as execute() plus "dynamic_prompt_used": bool
        """

        try:
            # Try to import and use dynamic prompt generator
            from dynamic_prompt_generator import DynamicPromptGeneratorSkill

            prompt_gen = DynamicPromptGeneratorSkill()
            prompt_result = prompt_gen.execute(
                topic=topic,
                style=style,
                platform=platform,
                content_type=content_type
            )

            if not prompt_result.get("success"):
                # Fallback to simple prompt
                prompt = f"Minimalist fintech visualization about {topic}, {style} style, brand colors"
                dynamic_used = False
                aspect_ratio = "1:1"
            else:
                prompt = prompt_result.get("prompt")
                dynamic_used = True
                aspect_ratio = prompt_result.get("aspect_ratio", "1:1")

        except ImportError:
            # Fallback if prompt generator not available
            prompt = f"Minimalist fintech visualization about {topic}, {style} style, brand colors"
            aspect_ratio = "1:1"
            dynamic_used = False

        # Generate image with the prompt
        result = self.execute(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            validate_brand=True
        )

        # Add info about dynamic prompt usage
        result["dynamic_prompt_used"] = dynamic_used
        if dynamic_used:
            result["topic"] = topic
            result["style"] = style
            result["content_type"] = content_type

        return result


# ========================================================================
# OpenClaw Skill Definition
# ========================================================================

def get_skill():
    """Return skill instance for OpenClaw to load"""
    return ImageGenerationSkill()


# ========================================================================
# CLI Testing
# ========================================================================

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    skill = ImageGenerationSkill()

    print("🧪 Testing image_generation skill...")

    # Test product visual
    result = skill.generate_product_visual(
        strategy_name="EMA50_200_RSI_v1",
        symbol="EURUSD",
        profit_factor=1.87,
        platform="instagram_post"
    )

    print(f"\n✅ Result:")
    print(f"Success: {result.get('success')}")
    print(f"Message: {result.get('message')}")

    if result.get("success"):
        print(f"Image URL: {result.get('image_url')}")
        print(f"Local Path: {result.get('local_path')}")
        print(f"Aspect Ratio: {result.get('aspect_ratio')}")
    else:
        print("Image generation failed. Check API key and configuration.")
