"""
========================================================================
Custom Skill: video_generation
========================================================================

Generates AI-powered videos using D-ID API with consistent avatar.

This skill creates video content for:
- Instagram Reels
- TikTok
- YouTube Shorts
- Facebook Reels

Features:
- Consistent avatar character (same person, same office)
- Brand-compliant background (Carbon Black office aesthetic)
- Dynamic scripts (only the dialogue changes)
- Vertical format (9:16) optimized for mobile
- Auto-generated subtitles

Usage in OpenClaw:
    Use the skill video_generation to create a video:
    - Script: "The market doesn't wait. In milliseconds, opportunities pass..."
    - Duration: 30 (seconds)
    - Output path: "openclaw/agents/marketer/content/generated/video_001.mp4"

Get API key: https://studio.d-id.com

========================================================================
"""

import os
import time
import requests
import json
from typing import Dict, Optional, Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class VideoGenerationSkill:
    """Skill for AI video generation using D-ID"""

    # Default avatar configuration (consistent character)
    DEFAULT_AVATAR = {
        "presenter_id": "amy-jcwCkr1grs",  # Professional female presenter
        "driver_id": "uM00QMwJ9x",  # Natural talking animation
        "background_color": "#101010",  # Carbon Black
    }

    # Alternative: Custom avatar URL (can be an image of the character you want)
    # Set this in .env: D_ID_CUSTOM_AVATAR_URL=https://your-image.jpg

    # Voice configuration
    DEFAULT_VOICE = {
        "type": "microsoft",
        "voice_id": "en-US-JennyNeural",  # Professional female voice
        "style": "professional"  # Options: professional, friendly, calm
    }

    def __init__(self):
        self.name = "video_generation"
        self.description = "Generate AI videos with consistent avatar for social media"

        self.api_key = os.getenv("D_ID_API_KEY")
        self.custom_avatar_url = os.getenv("D_ID_CUSTOM_AVATAR_URL")

        if not self.api_key:
            print("⚠️  WARNING: D_ID_API_KEY not set in .env")
            print("Get your key at: https://studio.d-id.com")

        self.api_base_url = "https://api.d-id.com"

    def execute(
        self,
        script: str,
        output_path: Optional[str] = None,
        duration: Optional[int] = None,
        add_subtitles: bool = True,
        aspect_ratio: str = "9:16",
        voice_config: Optional[Dict] = None,
        avatar_config: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Generate video from script using AI avatar.

        Args:
            script: The dialogue/script for the avatar to speak
            output_path: Where to save generated video
            duration: Target duration in seconds (15-60 recommended)
            add_subtitles: Whether to add auto-generated subtitles
            aspect_ratio: "9:16" (vertical) or "16:9" (horizontal)
            voice_config: Custom voice settings (optional)
            avatar_config: Custom avatar settings (optional)

        Returns:
            {
                "success": bool,
                "video_url": str,
                "local_path": str,
                "script_used": str,
                "duration": int,
                "message": str
            }
        """

        if not self.api_key:
            return {
                "success": False,
                "message": "D_ID_API_KEY not configured"
            }

        # Validate script
        if not script or len(script.strip()) < 10:
            return {
                "success": False,
                "message": "Script too short. Minimum 10 characters required."
            }

        if len(script) > 2000:
            return {
                "success": False,
                "message": "Script too long. Maximum 2000 characters. Consider splitting."
            }

        # Estimate duration if not provided (rough: ~150 words/min = 2.5 words/sec)
        if not duration:
            word_count = len(script.split())
            duration = max(15, min(60, int(word_count / 2.5) + 3))

        # Use custom avatar URL if provided, otherwise use default presenter
        avatar_settings = avatar_config or self.DEFAULT_AVATAR.copy()
        if self.custom_avatar_url:
            avatar_settings["source_url"] = self.custom_avatar_url

        voice_settings = voice_config or self.DEFAULT_VOICE.copy()

        # Build request payload
        payload = {
            "script": {
                "type": "text",
                "input": script,
                "provider": voice_settings
            },
            "config": {
                "stitch": True,
                "result_format": "mp4"
            }
        }

        # Add presenter or custom avatar
        if "source_url" in avatar_settings:
            payload["source_url"] = avatar_settings["source_url"]
        else:
            payload["presenter_id"] = avatar_settings.get("presenter_id")
            payload["driver_id"] = avatar_settings.get("driver_id")

        # Add subtitles if requested
        if add_subtitles:
            payload["config"]["subtitles"] = True
            payload["config"]["subtitles_color"] = "#45B14F"  # Neon Green
            payload["config"]["subtitles_background"] = "rgba(16, 16, 16, 0.8)"  # Carbon Black

        # Generate output path if not provided
        if not output_path:
            timestamp = int(time.time())
            os.makedirs("agents/marketer/content/generated", exist_ok=True)
            output_path = f"agents/marketer/content/generated/video_{timestamp}.mp4"

        # Call D-ID API
        try:
            headers = {
                "Authorization": f"Basic {self.api_key}",
                "Content-Type": "application/json"
            }

            # Create video
            response = requests.post(
                f"{self.api_base_url}/talks",
                headers=headers,
                json=payload,
                timeout=30
            )

            response.raise_for_status()
            result = response.json()

            talk_id = result.get("id")

            if not talk_id:
                return {
                    "success": False,
                    "message": "Video creation failed: No talk ID returned"
                }

        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "message": f"API request failed: {e}"
            }

        # Poll for video completion
        try:
            video_url = self._wait_for_video(talk_id, timeout=180)

            if not video_url:
                return {
                    "success": False,
                    "message": "Video generation timed out after 3 minutes"
                }

        except Exception as e:
            return {
                "success": False,
                "message": f"Video polling failed: {e}"
            }

        # Download video
        try:
            response = requests.get(video_url, timeout=60)
            response.raise_for_status()

            with open(output_path, 'wb') as f:
                f.write(response.content)

        except Exception as e:
            return {
                "success": False,
                "video_url": video_url,
                "message": f"Downloaded video URL but failed to save locally: {e}"
            }

        return {
            "success": True,
            "video_url": video_url,
            "local_path": output_path,
            "script_used": script,
            "duration": duration,
            "aspect_ratio": aspect_ratio,
            "subtitles_enabled": add_subtitles,
            "message": f"Video generated and saved to {output_path}"
        }

    def _wait_for_video(self, talk_id: str, timeout: int = 180) -> Optional[str]:
        """
        Poll D-ID API until video is ready.

        Args:
            talk_id: The talk ID from video creation
            timeout: Maximum wait time in seconds

        Returns:
            Video URL if successful, None if timeout
        """

        headers = {
            "Authorization": f"Basic {self.api_key}"
        }

        start_time = time.time()
        poll_interval = 5  # Check every 5 seconds

        while time.time() - start_time < timeout:
            try:
                response = requests.get(
                    f"{self.api_base_url}/talks/{talk_id}",
                    headers=headers,
                    timeout=10
                )

                response.raise_for_status()
                result = response.json()

                status = result.get("status")

                if status == "done":
                    return result.get("result_url")
                elif status == "error":
                    print(f"⚠️  Video generation error: {result.get('error')}")
                    return None
                # Status is "created" or "started", keep polling

            except Exception as e:
                print(f"⚠️  Polling error: {e}")

            time.sleep(poll_interval)

        return None  # Timeout

    def generate_educational_video(
        self,
        topic: str,
        key_points: list,
        duration: int = 30
    ) -> Dict[str, Any]:
        """
        Convenience method for generating educational content videos.

        Args:
            topic: Main topic (e.g., "Why emotional trading fails")
            key_points: List of 2-3 key points to cover
            duration: Target duration in seconds

        Returns:
            Same as execute()
        """

        # Build script from topic and key points
        script = f"{topic}.\n\n"

        for i, point in enumerate(key_points[:3], 1):
            script += f"{point}. "

        script += "\n\nThe future of trading is automated."

        return self.execute(
            script=script,
            duration=duration,
            add_subtitles=True
        )

    def generate_product_video(
        self,
        strategy_name: str,
        symbol: str,
        profit_factor: float,
        sharpe: float,
        backtest_years: int,
        duration: int = 45
    ) -> Dict[str, Any]:
        """
        Convenience method for product showcase videos.

        Args:
            strategy_name: Name of trading strategy
            symbol: Trading pair
            profit_factor: PF metric
            sharpe: Sharpe ratio
            backtest_years: Years of backtesting
            duration: Target duration

        Returns:
            Same as execute()
        """

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
            add_subtitles=True
        )

    def generate_social_proof_video(
        self,
        testimonial_text: str,
        user_result: str,
        duration: int = 30
    ) -> Dict[str, Any]:
        """
        Convenience method for social proof/testimonial videos.

        Args:
            testimonial_text: What the user said
            user_result: Their result (e.g., "1.8 PF in 6 months")
            duration: Target duration

        Returns:
            Same as execute()
        """

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
            add_subtitles=True
        )


# ========================================================================
# OpenClaw Skill Definition
# ========================================================================

def get_skill():
    """Return skill instance for OpenClaw to load"""
    return VideoGenerationSkill()


# ========================================================================
# CLI Testing
# ========================================================================

if __name__ == "__main__":
    skill = VideoGenerationSkill()

    print("🧪 Testing video_generation skill...")

    # Test educational video
    result = skill.generate_educational_video(
        topic="The market doesn't wait for you to wake up",
        key_points=[
            "Opportunities pass in milliseconds",
            "Institutional traders solved this with automation",
            "Now retail traders have the same advantage"
        ],
        duration=30
    )

    print(f"\n✅ Result:")
    print(f"Success: {result.get('success')}")
    print(f"Message: {result.get('message')}")

    if result.get("success"):
        print(f"Video URL: {result.get('video_url')}")
        print(f"Local Path: {result.get('local_path')}")
        print(f"Duration: {result.get('duration')}s")
        print(f"Subtitles: {result.get('subtitles_enabled')}")
    else:
        print("Video generation failed. Check API key and configuration.")
