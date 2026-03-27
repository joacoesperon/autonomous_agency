"""
========================================================================
Custom Skill: video_generation
========================================================================

Generates AI-powered videos for the marketer workflow using the provider
configured in `shared/brand_config.yml`.

The skill keeps a stable interface for OpenClaw while delegating the
provider-specific work to `shared.video_provider.VideoProvider`.
"""

import sys
from pathlib import Path
from typing import Any, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.video_provider import VideoProvider


class VideoGenerationSkill:
    """Skill for configurable AI video generation."""

    def __init__(self):
        self.name = "video_generation"
        self.description = (
            "Generate AI videos for social media using the provider configured in shared/brand_config.yml"
        )

    def execute(
        self,
        script: str,
        output_path: Optional[str] = None,
        duration: Optional[int] = None,
        add_subtitles: bool = True,
        aspect_ratio: str = "9:16",
        voice_config: Optional[Dict[str, Any]] = None,
        avatar_config: Optional[Dict[str, Any]] = None,
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        video_provider = VideoProvider(provider=provider)
        return video_provider.generate(
            script=script,
            duration=duration,
            output_path=output_path,
            add_subtitles=add_subtitles,
            aspect_ratio=aspect_ratio,
            voice_config=voice_config,
            avatar_config=avatar_config,
        )

    def generate_educational_video(
        self,
        topic: str,
        key_points: list,
        duration: int = 30,
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        script = f"{topic}.\n\n"
        for point in key_points[:3]:
            script += f"{point}. "
        script += "\n\nThe future of trading is automated."
        return self.execute(
            script=script,
            duration=duration,
            add_subtitles=True,
            provider=provider,
        )

    def generate_product_video(
        self,
        strategy_name: str,
        symbol: str,
        profit_factor: float,
        sharpe: float,
        backtest_years: int,
        duration: int = 45,
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        script = f"""
        New trading bot just dropped: {strategy_name}.

        Built for {symbol}, tested on {backtest_years} years of data.

        Profit Factor: {profit_factor:.2f}. Sharpe Ratio: {sharpe:.2f}.

        Out-of-sample validated. Ready to deploy.

        The future of trading is automated.

        Link in bio.
        """
        return self.execute(
            script=script,
            duration=duration,
            add_subtitles=True,
            provider=provider,
        )

    def generate_social_proof_video(
        self,
        testimonial_text: str,
        user_result: str,
        duration: int = 30,
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        script = f"""
        {testimonial_text}

        Their result: {user_result}.

        This is what systematic trading looks like.

        No emotions. Just discipline.

        Link in bio to start your journey.
        """
        return self.execute(
            script=script,
            duration=duration,
            add_subtitles=True,
            provider=provider,
        )


def get_skill():
    return VideoGenerationSkill()


if __name__ == "__main__":
    skill = VideoGenerationSkill()

    print("Testing video_generation skill...")
    result = skill.generate_educational_video(
        topic="The market doesn't wait for you to wake up",
        key_points=[
            "Opportunities pass in milliseconds",
            "Institutional traders solved this with automation",
            "Now retail traders have the same advantage",
        ],
        duration=30,
    )

    print(f"Success: {result.get('success')}")
    print(f"Message: {result.get('message')}")
    if result.get("success"):
        print(f"Provider: {result.get('provider')}")
        print(f"Video URL: {result.get('video_url')}")
        print(f"Local Path: {result.get('local_path')}")
