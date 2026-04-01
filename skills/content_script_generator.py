"""
========================================================================
Custom Skill: content_script_generator
========================================================================

Generates optimized content scripts with all derivatives in ONE LLM call.

This skill is the CORE of the content pipeline. It generates:
1. Video script (15-60 seconds)
2. Carousel key points (6-10 slides)
3. Tweet thread key points (5 tweets)

All in a single LLM call, ensuring coherence and reducing API costs.

Usage in OpenClaw:
    Use the skill content_script_generator to create content:
    - Topic: "Why algo trading beats manual trading"
    - Content type: "educational" | "product" | "social_proof" | "community"
    - Duration: 30 (seconds for video)
    - Output: {script, carousel_points, tweet_points}

KEY BENEFIT: 3 LLM calls → 1 LLM call (3x cost reduction)

========================================================================
"""

import os
import sys
import json
from typing import Dict, List, Any, Optional
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️  WARNING: python-dotenv not installed")

# Add parent directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from shared.llm_provider import LLMProvider
    from shared.provider_profiles import load_brand_config
except ImportError:
    print("⚠️  ERROR: Cannot import shared provider helpers")
    print("Make sure shared/llm_provider.py and shared/provider_profiles.py exist")
    exit(1)


class ContentScriptGeneratorSkill:
    """Skill for generating comprehensive content scripts with all derivatives"""

    def __init__(self):
        self.name = "content_script_generator"
        self.description = "Generate video scripts + carousel points + tweet points in ONE optimized LLM call"

        # Load brand configuration
        self.config = self._load_brand_config()

        # Initialize LLM provider (reads from config, supports Gemini/OpenAI/Claude)
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
        """
        Resolve LLM instance for a run.

        If overrides are provided, instantiate a temporary provider/model;
        otherwise use the default initialized client.
        """
        if llm_provider or llm_model:
            return LLMProvider(provider=llm_provider, model=llm_model)
        return self.llm

    def _load_brand_config(self) -> Dict[str, Any]:
        """Load resolved brand configuration from centralized YAML"""
        return load_brand_config()

    def _build_brand_voice_section(self) -> str:
        """Build brand voice section from config"""
        voice = self.config["brand_voice"]

        forbidden = ", ".join([f'"{w}"' for w in voice["forbidden_words"][:6]])

        characteristics = "\n    ".join([f"- {c}" for c in voice["characteristics"]])

        return f"""
    {self.config['brand_name']} Brand Voice:
    {characteristics}
    - FORBIDDEN WORDS: {forbidden}
    """

    def _build_mascot_section(self) -> str:
        """Build optional mascot guidance section from config"""
        mascot = self.config.get("brand_mascot", {})
        if not mascot.get("enabled") or not mascot.get("use_in_content_scripts", True):
            return ""

        dialogue_style = mascot.get("dialogue_style", [])
        dialogue_guidance = (
            "\n".join([f"      - {rule}" for rule in dialogue_style])
            if dialogue_style
            else "      - Keep the mascot on-brand."
        )

        return f"""
    MASCOT MODE:
    - On-screen speaker: {mascot.get('name', 'Brand mascot')}
    - Description: {mascot.get('description', '')}
    - Persona: {mascot.get('persona', '')}
    - Visual style: {mascot.get('visual_style', '')}
    - Speaking role: {mascot.get('speaking_role', '')}
    - Dialogue guidance:
{dialogue_guidance}
    - Write the video script so it can be spoken naturally by this mascot on camera.
    """

    def _get_content_guidelines(self, content_type: str) -> Dict[str, Any]:
        """Get guidelines for specific content type from config"""
        if content_type not in self.config["content_types"]:
            raise ValueError(f"Invalid content_type: {content_type}")

        return self.config["content_types"][content_type]

    def execute(
        self,
        topic: str,
        content_type: str = "educational",
        duration: int = 30,
        carousel_slides: int = 6,
        num_tweets: int = 5,
        context: Optional[Dict[str, Any]] = None,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate complete content package in ONE LLM call.

        Args:
            topic: Main topic/idea for the content
            content_type: "educational", "product", "social_proof", "community"
            duration: Video duration in seconds (15-60)
            carousel_slides: Number of carousel slides (5-10)
            num_tweets: Number of tweets in thread (usually 5)
            context: Optional dict with extra data (metrics, user info, etc.)

        Returns:
            {
                "success": bool,
                "video_script": str,
                "carousel_points": List[str],
                "tweet_points": List[str],
                "topic": str,
                "content_type": str,
                "estimated_duration": int,
                "message": str
            }
        """

        try:
            llm = self._resolve_llm(llm_provider=llm_provider, llm_model=llm_model)
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to initialize LLM override: {e}",
            }

        if not llm:
            return {
                "success": False,
                "message": "LLM provider not initialized. Check API keys."
            }

        # Validate inputs
        if not topic or len(topic.strip()) < 10:
            return {
                "success": False,
                "message": "Topic too short. Minimum 10 characters required."
            }

        if content_type not in self.config["content_types"]:
            return {
                "success": False,
                "message": f"Invalid content_type. Must be: {list(self.config['content_types'].keys())}"
            }

        video_settings = self.config["video_settings"]
        if duration < video_settings["min_duration"] or duration > video_settings["max_duration"]:
            return {
                "success": False,
                "message": f"Duration must be between {video_settings['min_duration']}-{video_settings['max_duration']} seconds"
            }

        carousel_spec = self.config["platforms"]["instagram"]["carousel"]
        if carousel_slides < carousel_spec["slides_min"] or carousel_slides > carousel_spec["slides_max"]:
            return {
                "success": False,
                "message": f"Carousel slides must be between {carousel_spec['slides_min']}-{carousel_spec['slides_max']}"
            }

        # Get content guidelines
        guidelines = self._get_content_guidelines(content_type)

        # Build context section if provided
        context_section = ""
        if context:
            context_section = f"""
ADDITIONAL CONTEXT:
{json.dumps(context, indent=2)}

Use this context to make the content specific and data-driven.
"""

        # Build brand voice section
        brand_voice_section = self._build_brand_voice_section()
        mascot_section = self._build_mascot_section()

        # Build comprehensive prompt
        prompt = f"""
You are the content strategist for {self.config['brand_name']}, a premium algorithmic trading brand.

{brand_voice_section}
{mascot_section}

CONTENT TYPE: {content_type}
GUIDELINES FOR THIS TYPE:
- Focus: {guidelines['focus']}
- Hook Style: {guidelines['hook_style']}
- Metrics Usage: {guidelines['metrics_usage']}
- CTA Style: {guidelines['cta']}
{"- DISCLAIMER REQUIRED: " + guidelines.get('disclaimer_text', '') if guidelines.get('disclaimer_required') else ""}

{context_section}

TASK: Generate a complete content package for the following topic:

TOPIC: "{topic}"

TARGET VIDEO DURATION: {duration} seconds

OUTPUT 3 COMPONENTS:

═══════════════════════════════════════════════════════════════

1. VIDEO SCRIPT ({duration} seconds):

Structure:
- HOOK (first 3-5 seconds): {guidelines['hook_style']}
- MAIN CONTENT (next {duration - 10} seconds): 3-4 key points, rapid-fire
- CTA (last 5-7 seconds): {guidelines['cta']}

Requirements:
- Write EXACTLY for {duration} seconds (estimate ~{self.config['video_settings']['script_pacing']['words_per_second']} words per second)
- Use short, punchy sentences
- Natural spoken language (contractions OK)
- Include verbal pauses with "{self.config['video_settings']['script_pacing']['pause_markers']}" where natural
- NO stage directions, NO [brackets], just pure spoken text
- Professional but conversational

═══════════════════════════════════════════════════════════════

2. CAROUSEL KEY POINTS ({carousel_slides} slides):

Structure:
- Slide 1: Title/Hook (max 8 words, engaging question or statement)
- Slides 2-{carousel_slides-1}: Key insights (each 10-15 words, 1-2 sentences)
- Slide {carousel_slides}: CTA/Conclusion (max 12 words, clear call to action)

Requirements:
- Each point should work as standalone text overlay on an image
- Use simple, impactful language
- Can include 1 emoji per point (optional, use sparingly)
- Extract different angles than the video (complement, don't duplicate)

═══════════════════════════════════════════════════════════════

3. TWEET THREAD KEY POINTS ({num_tweets} tweets):

Structure:
- Tweet 1: HOOK (attention-grabbing, make them want thread)
- Tweets 2-{num_tweets-1}: VALUE (insights, data, explanation)
- Tweet {num_tweets}: CTA + DISCLAIMER (if metrics present)

Requirements:
- Plan for ≤{self.config['platforms']['twitter']['tweet']['max_chars']} characters per tweet (will be formatted later)
- Extract essence, not full sentences (these are KEY POINTS)
- Different perspective than video (repurpose, don't copy)
- No hashtags needed (key points only)

═══════════════════════════════════════════════════════════════

OUTPUT FORMAT (STRICT JSON):

{{
  "video_script": "Your {duration}-second script here...",
  "carousel_points": [
    "Slide 1 text here",
    "Slide 2 text here",
    ...
    "Slide {carousel_slides} text here"
  ],
  "tweet_points": [
    "Tweet 1 key point",
    "Tweet 2 key point",
    ...
    "Tweet {num_tweets} key point"
  ]
}}

CRITICAL: Return ONLY valid JSON. No markdown formatting, no ```json```, just the JSON object.

Now generate the content package:
"""

        # Call LLM
        try:
            generated_text = llm.generate(prompt, json_mode=True)

            # Remove markdown formatting if present
            if generated_text.startswith("```json"):
                generated_text = generated_text.replace("```json", "").replace("```", "").strip()
            elif generated_text.startswith("```"):
                generated_text = generated_text.replace("```", "").strip()

            # Parse JSON
            content_package = json.loads(generated_text)

            # Validate structure
            required_keys = ["video_script", "carousel_points", "tweet_points"]
            if not all(key in content_package for key in required_keys):
                return {
                    "success": False,
                    "message": f"LLM output missing required keys. Got: {list(content_package.keys())}"
                }

            # Validate counts
            if len(content_package["carousel_points"]) != carousel_slides:
                return {
                    "success": False,
                    "message": f"Expected {carousel_slides} carousel points, got {len(content_package['carousel_points'])}"
                }

            if len(content_package["tweet_points"]) != num_tweets:
                return {
                    "success": False,
                    "message": f"Expected {num_tweets} tweet points, got {len(content_package['tweet_points'])}"
                }

            return {
                "success": True,
                "video_script": content_package["video_script"],
                "carousel_points": content_package["carousel_points"],
                "tweet_points": content_package["tweet_points"],
                "topic": topic,
                "content_type": content_type,
                "estimated_duration": duration,
                "carousel_slides": carousel_slides,
                "num_tweets": num_tweets,
                "llm_provider": llm.get_provider_info(),
                "message": f"Content package generated successfully ({duration}s video, {carousel_slides} slides, {num_tweets} tweets)"
            }

        except json.JSONDecodeError as e:
            return {
                "success": False,
                "message": f"Failed to parse LLM JSON output: {e}",
                "raw_output": generated_text[:500] if 'generated_text' in locals() else "No output"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Content generation failed: {e}"
            }

    def generate_product_package(
        self,
        strategy_name: str,
        symbol: str,
        metrics: Dict[str, float],
        backtest_years: int,
        duration: int = 45
    ) -> Dict[str, Any]:
        """
        Convenience method for product launch content.

        Args:
            strategy_name: Name of the trading strategy
            symbol: Trading pair (e.g., "EURUSD", "XAUUSD")
            metrics: Dict with PF, Sharpe, DD, Win Rate
            backtest_years: Years of backtesting
            duration: Video duration (default 45s for product content)

        Returns:
            Same as execute()
        """

        topic = f"New trading bot: {strategy_name} for {symbol}"

        context = {
            "strategy_name": strategy_name,
            "symbol": symbol,
            "profit_factor": metrics.get("pf", 0),
            "sharpe_ratio": metrics.get("sharpe", 0),
            "max_drawdown": metrics.get("dd", 0),
            "win_rate": metrics.get("win_rate", 0),
            "backtest_years": backtest_years,
            "out_of_sample_validated": True
        }

        return self.execute(
            topic=topic,
            content_type="product",
            duration=duration,
            carousel_slides=8,
            num_tweets=5,
            context=context
        )

    def generate_educational_package(
        self,
        topic: str,
        key_concepts: Optional[List[str]] = None,
        duration: int = 30
    ) -> Dict[str, Any]:
        """
        Convenience method for educational content.

        Args:
            topic: Educational topic
            key_concepts: Optional list of concepts to cover
            duration: Video duration (default 30s for educational)

        Returns:
            Same as execute()
        """

        context = None
        if key_concepts:
            context = {"key_concepts_to_cover": key_concepts}

        return self.execute(
            topic=topic,
            content_type="educational",
            duration=duration,
            carousel_slides=6,
            num_tweets=5,
            context=context
        )


# ========================================================================
# OpenClaw Skill Definition
# ========================================================================

def get_skill():
    """Return skill instance for OpenClaw to load"""
    return ContentScriptGeneratorSkill()


# ========================================================================
# CLI Testing
# ========================================================================

if __name__ == "__main__":
    skill = ContentScriptGeneratorSkill()

    print("🧪 Testing content_script_generator skill...")
    print("=" * 70)
    print(f"LLM Provider: {skill.llm.get_provider_info() if skill.llm else 'NOT INITIALIZED'}")
    print("=" * 70)

    # Test educational content
    print("\n📚 Test 1: Educational Content")
    print("-" * 70)

    result = skill.generate_educational_package(
        topic="Why emotional trading fails during high volatility",
        key_concepts=[
            "Fear and greed dominate during volatility",
            "Humans can't execute consistently under pressure",
            "Algorithms follow rules without emotion"
        ],
        duration=30
    )

    print(f"\n✅ Result: {result.get('success')}")
    print(f"📝 Message: {result.get('message')}")

    if result.get("success"):
        print(f"\n🎬 VIDEO SCRIPT ({result.get('estimated_duration')}s):")
        print("-" * 70)
        print(result.get('video_script'))

        print(f"\n📱 CAROUSEL POINTS ({len(result.get('carousel_points', []))} slides):")
        print("-" * 70)
        for i, point in enumerate(result.get('carousel_points', []), 1):
            print(f"{i}. {point}")

        print(f"\n🐦 TWEET POINTS ({len(result.get('tweet_points', []))} tweets):")
        print("-" * 70)
        for i, point in enumerate(result.get('tweet_points', []), 1):
            print(f"{i}. {point}")

        print(f"\n🤖 LLM Info: {result.get('llm_provider')}")

    else:
        print(f"❌ Generation failed: {result.get('message')}")

    # Test product content
    print("\n\n" + "=" * 70)
    print("🤖 Test 2: Product Launch Content")
    print("-" * 70)

    result2 = skill.generate_product_package(
        strategy_name="EMA50_200_RSI_Scalper",
        symbol="EURUSD",
        metrics={
            "pf": 1.87,
            "sharpe": 2.34,
            "dd": 12.5,
            "win_rate": 68.3
        },
        backtest_years=10,
        duration=45
    )

    print(f"\n✅ Result: {result2.get('success')}")
    print(f"📝 Message: {result2.get('message')}")

    if result2.get("success"):
        print(f"\n🎬 VIDEO SCRIPT:")
        print(result2.get('video_script')[:200] + "...")
        print(f"\n(Full script: {len(result2.get('video_script', ''))} characters)")

    print("\n" + "=" * 70)
    print("✅ Testing complete!")
