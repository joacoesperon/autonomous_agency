"""
========================================================================
Custom Skill: dynamic_prompt_generator
========================================================================

Generates unique, brand-compliant image prompts dynamically.

This skill prevents repetitive template-based prompts by creating
contextual, varied prompts that maintain brand consistency while
adapting to specific content topics and styles.

Usage in OpenClaw:
    Use the skill dynamic_prompt_generator to create an image prompt:
    - Topic: "Bitcoin volatility spike"
    - Style: "dashboard" | "minimal" | "abstract" | "chart"
    - Platform: "instagram_post" | "instagram_story" | "twitter"
    - Output: Unique, optimized prompt for image generation

========================================================================
"""

import os
import random
from typing import Dict, List, Any, Optional

try:
    import google.generativeai as genai
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️  ERROR: google-generativeai library not installed")
    print("Run: pip install google-generativeai")
    exit(1)


class DynamicPromptGeneratorSkill:
    """Skill for generating contextual, brand-compliant image prompts"""

    # Brand visual guidelines (strict)
    BRAND_GUIDELINES = """
    Jess Trading Brand Visual Guidelines (STRICT):

    COLOR PALETTE:
    - Carbon Black (#101010): Primary background, 80% of visual, dark mode aesthetic
    - Neon Green (#45B14F): Highlights only (profits, key metrics), max 20% of visual
    - Light Gray (#A7A7A7): Body text, labels, secondary information
    - Electric Blue (#2979FF): CTAs ONLY (buttons, action prompts)

    AESTHETIC:
    - Minimalist fintech / Apple keynote style
    - Dark mode, premium, professional
    - Clean typography, generous white space
    - Glassmorphism effects, subtle gradients
    - No stock photos, no generic imagery
    - No bright colors outside palette

    FORBIDDEN:
    - Red, orange, yellow, purple (except as part of charts showing loss)
    - Stock trader photos, lambos, cash stacks
    - Cluttered layouts, multiple fonts
    - Low-quality or pixelated images
    """

    # Visual style categories
    STYLE_APPROACHES = {
        "dashboard": [
            "trading terminal interface",
            "fintech app UI mockup",
            "professional trading dashboard",
            "clean data visualization panel"
        ],
        "minimal": [
            "minimalist geometric composition",
            "abstract financial visualization",
            "clean spacious layout with single focal point",
            "premium minimal design with negative space"
        ],
        "abstract": [
            "abstract algorithmic patterns",
            "geometric data flow visualization",
            "futuristic financial network",
            "modern tech-inspired abstract composition"
        ],
        "chart": [
            "candlestick chart visualization",
            "profit growth line graph",
            "financial metrics display",
            "backtest performance chart"
        ]
    }

    # Aspect ratio presets
    ASPECT_RATIOS = {
        "instagram_post": "1:1",
        "instagram_story": "9:16",
        "twitter": "16:9",
        "tiktok": "9:16",
        "youtube_shorts": "9:16",
        "facebook": "1:1"
    }

    def __init__(self):
        self.name = "dynamic_prompt_generator"
        self.description = "Generate unique, contextual image prompts with brand consistency"

        self.api_key = os.getenv("GEMINI_API_KEY")

        if not self.api_key:
            print("⚠️  WARNING: GEMINI_API_KEY not set in .env")
        else:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash')

    def execute(
        self,
        topic: str,
        style: str = "minimal",
        platform: str = "instagram_post",
        content_type: str = "educational",
        additional_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a unique, brand-compliant image prompt.

        Args:
            topic: Main topic/theme of the image (e.g., "Bitcoin volatility")
            style: Visual style ("dashboard", "minimal", "abstract", "chart")
            platform: Target platform (determines aspect ratio)
            content_type: "educational", "product", "social_proof", "community"
            additional_context: Extra context for prompt generation

        Returns:
            {
                "success": bool,
                "prompt": str,  # Full generation prompt
                "short_prompt": str,  # Concise version
                "aspect_ratio": str,
                "style": str,
                "message": str
            }
        """

        if not self.api_key:
            return {
                "success": False,
                "message": "GEMINI_API_KEY not configured"
            }

        # Validate style
        if style not in self.STYLE_APPROACHES:
            return {
                "success": False,
                "message": f"Invalid style. Choose from: {list(self.STYLE_APPROACHES.keys())}"
            }

        # Get aspect ratio
        aspect_ratio = self.ASPECT_RATIOS.get(platform, "1:1")

        # Get style approach variation
        style_approach = random.choice(self.STYLE_APPROACHES[style])

        # Build LLM prompt for generating image prompt
        llm_prompt = f"""
        You are an expert AI image prompt engineer for Jess Trading, a premium algorithmic trading brand.

        {self.BRAND_GUIDELINES}

        TASK: Generate a detailed image generation prompt for the following:

        TOPIC: {topic}
        VISUAL STYLE: {style} ({style_approach})
        PLATFORM: {platform} (aspect ratio: {aspect_ratio})
        CONTENT TYPE: {content_type}
        {f"ADDITIONAL CONTEXT: {additional_context}" if additional_context else ""}

        REQUIREMENTS:
        1. Strictly follow the brand color palette (Carbon Black, Neon Green, Light Gray, Electric Blue)
        2. Create a {style_approach} based on the topic
        3. Be specific about composition, lighting, and mood
        4. Include exact hex codes in the prompt
        5. Make it unique and contextual (not a generic template)
        6. Optimize for {aspect_ratio} aspect ratio
        7. Emphasize premium, minimalist, fintech aesthetic

        OUTPUT FORMAT:
        Return ONLY the image generation prompt text (no explanations, no labels).

        The prompt should be 2-4 sentences, detailed but concise.

        EXAMPLE (for reference, create something different):
        "Minimalist fintech dashboard showing EURUSD candlestick chart, Carbon Black #101010 background with subtle radial gradient fading to #000000, sharp Neon Green #45B14F bullish candles indicating profitable pattern, Light Gray #A7A7A7 axis labels and price levels, clean geometric UI elements with glassmorphism effect, premium trading terminal aesthetic, 4k resolution, {aspect_ratio} format"

        NOW GENERATE THE PROMPT FOR THE GIVEN TOPIC:
        """

        # Generate prompt using LLM
        try:
            response = self.model.generate_content(llm_prompt)
            generated_prompt = response.text.strip()

            # Remove any markdown or extra formatting
            generated_prompt = generated_prompt.replace('```', '').strip()

            # Create short version (first sentence)
            short_prompt = generated_prompt.split('.')[0] + '.'

        except Exception as e:
            return {
                "success": False,
                "message": f"Prompt generation failed: {e}"
            }

        # Validate prompt length
        if len(generated_prompt) < 50:
            return {
                "success": False,
                "message": f"Generated prompt too short ({len(generated_prompt)} chars). Retry."
            }

        if len(generated_prompt) > 1500:
            return {
                "success": False,
                "message": f"Generated prompt too long ({len(generated_prompt)} chars). Simplify."
            }

        return {
            "success": True,
            "prompt": generated_prompt,
            "short_prompt": short_prompt,
            "aspect_ratio": aspect_ratio,
            "style": style,
            "topic": topic,
            "content_type": content_type,
            "platform": platform,
            "message": "Prompt generated successfully"
        }

    def generate_batch(
        self,
        topics: List[str],
        style: str = "minimal",
        platform: str = "instagram_post"
    ) -> Dict[str, Any]:
        """
        Generate multiple prompts at once (batch processing).

        Args:
            topics: List of topics
            style: Visual style for all
            platform: Platform for all

        Returns:
            {
                "success": bool,
                "prompts": List[Dict],
                "count": int
            }
        """

        prompts = []

        for topic in topics:
            result = self.execute(
                topic=topic,
                style=style,
                platform=platform
            )

            if result.get("success"):
                prompts.append({
                    "topic": topic,
                    "prompt": result.get("prompt"),
                    "aspect_ratio": result.get("aspect_ratio")
                })
            else:
                # Continue with others even if one fails
                continue

        if not prompts:
            return {
                "success": False,
                "message": "All prompt generations failed"
            }

        return {
            "success": True,
            "prompts": prompts,
            "count": len(prompts),
            "message": f"Generated {len(prompts)}/{len(topics)} prompts successfully"
        }

    def generate_for_content_mix(
        self,
        content_schedule: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Generate prompts for a weekly content schedule.

        Args:
            content_schedule: Dict like {"Monday": "educational_volatility", "Tuesday": "product_new_bot", ...}

        Returns:
            Dict with prompts for each day
        """

        daily_prompts = {}

        for day, topic_type in content_schedule.items():
            # Parse topic type (format: "type_topic")
            if '_' in topic_type:
                content_type, topic = topic_type.split('_', 1)
            else:
                content_type = "educational"
                topic = topic_type

            # Select style based on content type
            style_map = {
                "educational": "minimal",
                "product": "dashboard",
                "social_proof": "abstract",
                "community": "minimal"
            }

            style = style_map.get(content_type, "minimal")

            result = self.execute(
                topic=topic,
                style=style,
                content_type=content_type
            )

            if result.get("success"):
                daily_prompts[day] = {
                    "topic": topic,
                    "content_type": content_type,
                    "style": style,
                    "prompt": result.get("prompt")
                }

        return {
            "success": len(daily_prompts) > 0,
            "daily_prompts": daily_prompts,
            "count": len(daily_prompts),
            "message": f"Generated prompts for {len(daily_prompts)} days"
        }


# ========================================================================
# OpenClaw Skill Definition
# ========================================================================

def get_skill():
    """Return skill instance for OpenClaw to load"""
    return DynamicPromptGeneratorSkill()


# ========================================================================
# CLI Testing
# ========================================================================

if __name__ == "__main__":
    skill = DynamicPromptGeneratorSkill()

    print("🧪 Testing dynamic_prompt_generator skill...")

    # Test single prompt generation
    result = skill.execute(
        topic="Bitcoin volatility spike and emotional trading",
        style="minimal",
        platform="instagram_post",
        content_type="educational"
    )

    print(f"\n✅ Result:")
    print(f"Success: {result.get('success')}")
    print(f"Message: {result.get('message')}")

    if result.get("success"):
        print(f"\nTopic: {result.get('topic')}")
        print(f"Style: {result.get('style')}")
        print(f"Aspect Ratio: {result.get('aspect_ratio')}")
        print(f"\n📝 Generated Prompt:")
        print("-" * 80)
        print(result.get('prompt'))
        print("-" * 80)
        print(f"\n📄 Short Version:")
        print(result.get('short_prompt'))
    else:
        print("Prompt generation failed. Check API key and configuration.")

    # Test batch generation
    print("\n\n🧪 Testing batch generation...")
    batch_result = skill.generate_batch(
        topics=[
            "Market automation advantages",
            "Backtesting methodology",
            "Risk management in algo trading"
        ],
        style="abstract",
        platform="instagram_story"
    )

    if batch_result.get("success"):
        print(f"✅ Generated {batch_result.get('count')} prompts")
        for i, prompt_data in enumerate(batch_result.get('prompts', []), 1):
            print(f"\n{i}. {prompt_data['topic']}")
            print(f"   {prompt_data['prompt'][:100]}...")
    else:
        print("Batch generation failed.")
