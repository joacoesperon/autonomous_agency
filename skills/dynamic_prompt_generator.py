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

import random
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️  WARNING: python-dotenv not installed")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from shared.llm_provider import LLMProvider
    from shared.provider_profiles import load_brand_config
except ImportError:
    print("⚠️  ERROR: Cannot import LLMProvider from shared/")
    print("Make sure shared/llm_provider.py and shared/provider_profiles.py exist")
    exit(1)


class DynamicPromptGeneratorSkill:
    """Skill for generating contextual, brand-compliant image prompts"""

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
        self.config = load_brand_config()

        try:
            self.llm = LLMProvider()
            print(f"✅ LLM initialized: {self.llm.provider} - {self.llm.model}")
        except Exception as e:
            print(f"⚠️  ERROR: Failed to initialize LLM: {e}")
            self.llm = None

    def _resolve_llm(
        self,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
    ) -> Optional[LLMProvider]:
        if llm_provider or llm_model:
            return LLMProvider(provider=llm_provider, model=llm_model)
        return self.llm

    def _build_brand_guidelines(self) -> str:
        visual = self.config.get("visual_identity", {})
        palette = visual.get("color_palette", {})
        aesthetic = visual.get("aesthetic", {})
        constraints = visual.get("image_constraints", {})
        brand_name = self.config.get("brand_name", "the brand")

        forbidden_words = self.config.get("brand_voice", {}).get("forbidden_words", [])
        forbidden_text = ", ".join(forbidden_words[:8]) if forbidden_words else "none"

        return f"""
    {brand_name} visual guidelines (STRICT):

    COLOR PALETTE:
    - Primary background: {palette.get('primary', '#101010')}
    - Highlight color: {palette.get('secondary', '#45B14F')} (max {constraints.get('highlight_percentage', 20)}% of image)
    - Text color: {palette.get('tertiary', '#A7A7A7')}
    - CTA color: {palette.get('accent', '#2979FF')}

    AESTHETIC:
    - Style: {aesthetic.get('style', 'Minimalist premium fintech')}
    - Reference: {aesthetic.get('reference', 'Apple keynote presentation style')}

    CONSTRAINTS:
    - Background rule: {constraints.get('background_rule', 'Always dark background')}
    - Max colors: {constraints.get('max_colors', 4)}
    - Forbidden language cues: {forbidden_text}
    """

    def execute(
        self,
        topic: str,
        style: str = "minimal",
        platform: str = "instagram_post",
        content_type: str = "educational",
        additional_context: Optional[str] = None,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
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

        try:
            llm = self._resolve_llm(llm_provider=llm_provider, llm_model=llm_model)
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to initialize LLM override: {e}"
            }

        if not llm:
            return {
                "success": False,
                "message": "LLM provider not initialized. Check API keys and brand_config.yml."
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
        brand_name = self.config.get("brand_name", "the brand")
        llm_prompt = f"""
        You are an expert AI image prompt engineer for {brand_name}, a premium algorithmic trading brand.

        {self._build_brand_guidelines()}

        TASK: Generate a detailed image generation prompt for the following:

        TOPIC: {topic}
        VISUAL STYLE: {style} ({style_approach})
        PLATFORM: {platform} (aspect ratio: {aspect_ratio})
        CONTENT TYPE: {content_type}
        {f"ADDITIONAL CONTEXT: {additional_context}" if additional_context else ""}

        REQUIREMENTS:
        1. Strictly follow the configured brand color palette and visual identity.
        2. Create a {style_approach} based on the topic
        3. Be specific about composition, lighting, and mood
        4. Include exact hex codes in the prompt
        5. Make it unique and contextual (not a generic template)
        6. Optimize for {aspect_ratio} aspect ratio
        7. Emphasize premium, minimalist, fintech aesthetic

        OUTPUT FORMAT:
        Return ONLY the image generation prompt text (no explanations, no labels).

        The prompt should be 2-4 sentences, detailed but concise.

        NOW GENERATE THE PROMPT FOR THE GIVEN TOPIC:
        """

        # Generate prompt using LLM
        try:
            generated_prompt = llm.generate(llm_prompt).strip()

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
