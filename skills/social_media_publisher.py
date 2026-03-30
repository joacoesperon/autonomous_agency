"""
========================================================================
Custom Skill: social_media_publisher
========================================================================

Thin OpenClaw-facing wrapper around the real publisher in
`shared/social_publisher.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.social_publisher import SocialPublisher


class SocialMediaPublisherSkill:
    """Skill wrapper for real social publishing APIs."""

    def __init__(self):
        self.name = "social_media_publisher"
        self.description = "Publish approved content to Instagram, X, TikTok, YouTube Shorts, and Facebook"
        self.publisher = SocialPublisher()

    def execute(
        self,
        platforms: List[str],
        caption: Union[str, List[str]],
        media_paths: Optional[List[str]] = None,
        content_type: str = "post",
        scheduled_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.publisher.execute(
            platforms=platforms,
            caption=caption,
            media_paths=media_paths,
            content_type=content_type,
            scheduled_time=scheduled_time,
        )

    def publish_reel_cross_platform(self, video_path: str, caption: str) -> Dict[str, Any]:
        return self.publisher.publish_reel_cross_platform(video_path=video_path, caption=caption)

    def publish_carousel_with_posts(
        self,
        carousel_paths: List[str],
        caption: str,
        single_image_platforms: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return self.publisher.publish_carousel_with_posts(
            carousel_paths=carousel_paths,
            caption=caption,
            single_image_platforms=single_image_platforms,
        )

    def publish_content_bundle(self, approval_record: Dict[str, Any]) -> Dict[str, Any]:
        return self.publisher.publish_content_bundle(approval_record)


def get_skill():
    return SocialMediaPublisherSkill()


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    skill = SocialMediaPublisherSkill()
    print("social_media_publisher is configured. Use execute()/publish_content_bundle() to publish approved content.")
