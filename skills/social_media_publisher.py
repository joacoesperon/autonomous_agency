"""
========================================================================
Custom Skill: social_media_publisher
========================================================================

Publishes approved content to social media platforms:
- Instagram (posts, stories, carousels, reels)
- X/Twitter (tweets and threads)
- TikTok (videos)
- YouTube Shorts (videos)
- Facebook (posts and reels)

CRITICAL: This skill should ONLY be called AFTER owner approval via HITL.

Usage in OpenClaw:
    Use the skill social_media_publisher to publish content:
    - Platforms: ["instagram", "twitter", "tiktok", "youtube_shorts", "facebook"]
    - Caption: "Your post text..."
    - Media paths: ["path/to/image.jpg"] or ["path/to/video.mp4"]
    - Content type: "post", "story", "carousel", "reel", "thread"

========================================================================
"""

import os
import time
from typing import Dict, List, Optional, Any

try:
    import requests
    import yaml
except ImportError:
    print("⚠️  ERROR: Required libraries not installed")
    print("Run: pip install requests pyyaml")
    exit(1)


class SocialMediaPublisherSkill:
    """Skill for publishing content to social media platforms"""

    def __init__(self):
        self.name = "social_media_publisher"
        self.description = "Publish approved content to Instagram, X, TikTok, YouTube Shorts, and Facebook"

        # Load API credentials from environment
        self.instagram_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        self.instagram_user_id = os.getenv("INSTAGRAM_USER_ID")

        self.twitter_bearer_token = os.getenv("X_BEARER_TOKEN")
        self.twitter_api_key = os.getenv("X_API_KEY")
        self.twitter_api_secret = os.getenv("X_API_SECRET")
        self.twitter_access_token = os.getenv("X_ACCESS_TOKEN")
        self.twitter_access_secret = os.getenv("X_ACCESS_SECRET")

        self.tiktok_access_token = os.getenv("TIKTOK_ACCESS_TOKEN")

        self.youtube_api_key = os.getenv("YOUTUBE_API_KEY")
        self.youtube_client_id = os.getenv("YOUTUBE_CLIENT_ID")
        self.youtube_client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")

        self.facebook_access_token = os.getenv("FACEBOOK_ACCESS_TOKEN")
        self.facebook_page_id = os.getenv("FACEBOOK_PAGE_ID")

        # Rate limiting
        self.last_post_time = {}

    def execute(
        self,
        platforms: List[str],
        caption: str,
        media_paths: Optional[List[str]] = None,
        content_type: str = "post",
        scheduled_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Publish content to specified platforms.

        Args:
            platforms: List of platforms ("instagram", "twitter", "tiktok", "youtube_shorts", "facebook")
            caption: Text content/caption
            media_paths: List of paths to images/videos
            content_type: "post", "story", "carousel", "reel", "thread"
            scheduled_time: Optional ISO timestamp for scheduling

        Returns:
            {
                "success": bool,
                "results": {
                    "platform_name": {"success": bool, "post_id": str, "message": str},
                    ...
                },
                "message": str
            }
        """

        results = {}
        overall_success = True

        # Validate platforms
        valid_platforms = ["instagram", "twitter", "tiktok", "youtube_shorts", "facebook"]
        for platform in platforms:
            if platform not in valid_platforms:
                return {
                    "success": False,
                    "message": f"Invalid platform: {platform}. Use: {valid_platforms}"
                }

        # Check rate limiting
        for platform in platforms:
            if not self._check_rate_limit(platform):
                return {
                    "success": False,
                    "message": f"Rate limit exceeded for {platform}. Wait before posting."
                }

        # Validate content type and media
        if content_type in ["carousel", "reel"] and not media_paths:
            return {
                "success": False,
                "message": f"Content type '{content_type}' requires media_paths"
            }

        # Publish to each platform
        if "instagram" in platforms:
            results["instagram"] = self._publish_instagram(
                caption=caption,
                media_paths=media_paths or [],
                content_type=content_type
            )
            if not results["instagram"]["success"]:
                overall_success = False

        if "twitter" in platforms:
            # If thread, tweets should be passed separately
            if content_type == "thread" and isinstance(caption, list):
                results["twitter"] = self._publish_twitter_thread(
                    tweets=caption,
                    media_paths=media_paths
                )
            else:
                results["twitter"] = self._publish_twitter(
                    text=caption,
                    media_path=media_paths[0] if media_paths else None
                )
            if not results["twitter"]["success"]:
                overall_success = False

        if "tiktok" in platforms:
            if content_type == "reel" and media_paths:
                results["tiktok"] = self._publish_tiktok(
                    caption=caption,
                    video_path=media_paths[0]
                )
            else:
                results["tiktok"] = {
                    "success": False,
                    "message": "TikTok requires video content (reel type)"
                }
            if not results["tiktok"]["success"]:
                overall_success = False

        if "youtube_shorts" in platforms:
            if content_type == "reel" and media_paths:
                results["youtube_shorts"] = self._publish_youtube_shorts(
                    title=caption[:100],  # YouTube title limit
                    description=caption,
                    video_path=media_paths[0]
                )
            else:
                results["youtube_shorts"] = {
                    "success": False,
                    "message": "YouTube Shorts requires video content (reel type)"
                }
            if not results["youtube_shorts"]["success"]:
                overall_success = False

        if "facebook" in platforms:
            results["facebook"] = self._publish_facebook(
                caption=caption,
                media_paths=media_paths or [],
                content_type=content_type
            )
            if not results["facebook"]["success"]:
                overall_success = False

        # Log published content
        if overall_success:
            self._log_published_content(platforms, caption, content_type, results)

        return {
            "success": overall_success,
            "results": results,
            "message": "Content published successfully" if overall_success else "Some publications failed"
        }

    def _publish_instagram(
        self,
        caption: str,
        media_paths: List[str],
        content_type: str
    ) -> Dict[str, Any]:
        """Publish to Instagram using Graph API"""

        if not self.instagram_token or not self.instagram_user_id:
            return {
                "success": False,
                "message": "Instagram access token or user ID not configured"
            }

        # Different endpoints for different content types
        if content_type == "story":
            return self._publish_instagram_story(caption, media_paths[0] if media_paths else None)
        elif content_type == "carousel":
            return self._publish_instagram_carousel(caption, media_paths)
        elif content_type == "reel":
            return self._publish_instagram_reel(caption, media_paths[0] if media_paths else None)
        else:  # post
            return self._publish_instagram_post(caption, media_paths[0] if media_paths else None)

    def _publish_instagram_post(self, caption: str, media_path: Optional[str]) -> Dict[str, Any]:
        """Publish Instagram post"""
        # Implementation placeholder
        # Real: Upload media → Create container → Publish
        return {
            "success": False,
            "message": "Instagram Post API integration pending. Use Meta Graph API."
        }

    def _publish_instagram_story(self, caption: str, media_path: Optional[str]) -> Dict[str, Any]:
        """Publish Instagram story"""
        return {
            "success": False,
            "message": "Instagram Story API integration pending. Use Meta Graph API."
        }

    def _publish_instagram_carousel(self, caption: str, media_paths: List[str]) -> Dict[str, Any]:
        """Publish Instagram carousel (up to 10 images)"""
        if len(media_paths) < 2 or len(media_paths) > 10:
            return {
                "success": False,
                "message": "Instagram carousels require 2-10 images"
            }

        return {
            "success": False,
            "message": "Instagram Carousel API integration pending. Use Meta Graph API with carousel_item."
        }

    def _publish_instagram_reel(self, caption: str, video_path: Optional[str]) -> Dict[str, Any]:
        """Publish Instagram Reel"""
        if not video_path:
            return {
                "success": False,
                "message": "Instagram Reel requires video file"
            }

        return {
            "success": False,
            "message": "Instagram Reel API integration pending. Use Meta Graph API video endpoint."
        }

    def _publish_twitter(
        self,
        text: str,
        media_path: Optional[str]
    ) -> Dict[str, Any]:
        """Publish to X/Twitter (single tweet)"""

        if not self.twitter_bearer_token:
            return {
                "success": False,
                "message": "Twitter bearer token not configured"
            }

        # Placeholder implementation
        # Real: Use Twitter API v2 with tweepy or requests
        return {
            "success": False,
            "message": "Twitter API integration pending. Use tweepy library or Twitter API v2."
        }

    def _publish_twitter_thread(
        self,
        tweets: List[str],
        media_paths: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Publish Twitter thread (multiple connected tweets)"""

        # Validate tweet lengths
        for i, tweet in enumerate(tweets):
            if len(tweet) > 280:
                return {
                    "success": False,
                    "message": f"Tweet {i+1} exceeds 280 characters ({len(tweet)} chars)"
                }

        return {
            "success": False,
            "message": "Twitter thread API integration pending. Use tweepy with reply_to_tweet_id."
        }

    def _publish_tiktok(
        self,
        caption: str,
        video_path: str
    ) -> Dict[str, Any]:
        """Publish to TikTok"""

        if not self.tiktok_access_token:
            return {
                "success": False,
                "message": "TikTok access token not configured"
            }

        if not video_path or not os.path.exists(video_path):
            return {
                "success": False,
                "message": "Valid video path required for TikTok"
            }

        # Placeholder implementation
        # Real: Use TikTok Content Posting API
        return {
            "success": False,
            "message": "TikTok API integration pending. Use TikTok Content Posting API v2."
        }

    def _publish_youtube_shorts(
        self,
        title: str,
        description: str,
        video_path: str
    ) -> Dict[str, Any]:
        """Publish to YouTube Shorts"""

        if not self.youtube_api_key:
            return {
                "success": False,
                "message": "YouTube API key not configured"
            }

        if not video_path or not os.path.exists(video_path):
            return {
                "success": False,
                "message": "Valid video path required for YouTube Shorts"
            }

        # Placeholder implementation
        # Real: Use YouTube Data API v3 with #Shorts in title/description
        return {
            "success": False,
            "message": "YouTube Shorts API integration pending. Use YouTube Data API v3."
        }

    def _publish_facebook(
        self,
        caption: str,
        media_paths: List[str],
        content_type: str
    ) -> Dict[str, Any]:
        """Publish to Facebook Page"""

        if not self.facebook_access_token or not self.facebook_page_id:
            return {
                "success": False,
                "message": "Facebook access token or page ID not configured"
            }

        if content_type == "reel" and media_paths:
            return self._publish_facebook_reel(caption, media_paths[0])
        else:
            return self._publish_facebook_post(caption, media_paths[0] if media_paths else None)

    def _publish_facebook_post(self, caption: str, media_path: Optional[str]) -> Dict[str, Any]:
        """Publish Facebook post"""
        return {
            "success": False,
            "message": "Facebook Post API integration pending. Use Meta Graph API."
        }

    def _publish_facebook_reel(self, caption: str, video_path: str) -> Dict[str, Any]:
        """Publish Facebook Reel"""
        return {
            "success": False,
            "message": "Facebook Reel API integration pending. Use Meta Graph API video endpoint."
        }

    def _check_rate_limit(self, platform: str) -> bool:
        """Check if rate limit allows posting (max 10 posts/hour per platform)"""

        current_time = time.time()
        last_post = self.last_post_time.get(platform, 0)

        # Min 6 minutes between posts (10 posts/hour max)
        min_interval = 360  # seconds

        if (current_time - last_post) < min_interval:
            return False

        # Update last post time
        self.last_post_time[platform] = current_time
        return True

    def _log_published_content(
        self,
        platforms: List[str],
        caption: str,
        content_type: str,
        results: Dict[str, Any]
    ):
        """Log published content to file"""

        log_file = "agents/marketer/content/published_log.yml"
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        # Load existing log
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                log = yaml.safe_load(f) or []
        else:
            log = []

        # Add new entry
        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "platforms": platforms,
            "content_type": content_type,
            "caption": caption[:100] + "..." if len(caption) > 100 else caption,
            "post_ids": {
                platform: results[platform].get("post_id", "N/A")
                for platform in platforms
                if platform in results
            },
            "success": all(results[p]["success"] for p in platforms if p in results)
        }

        log.append(entry)

        # Save log
        with open(log_file, 'w') as f:
            yaml.dump(log, f, default_flow_style=False)

    def publish_reel_cross_platform(
        self,
        video_path: str,
        caption: str
    ) -> Dict[str, Any]:
        """
        Convenience method: Publish a reel to all video platforms.

        Args:
            video_path: Path to video file
            caption: Caption/description

        Returns:
            Same as execute()
        """

        return self.execute(
            platforms=["instagram", "tiktok", "youtube_shorts", "facebook"],
            caption=caption,
            media_paths=[video_path],
            content_type="reel"
        )

    def publish_carousel_with_posts(
        self,
        carousel_paths: List[str],
        caption: str,
        single_image_platforms: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Convenience method: Publish carousel to Instagram, single image to other platforms.

        Args:
            carousel_paths: List of image paths for carousel
            caption: Caption for post
            single_image_platforms: Platforms to post first image only (default: ["twitter", "facebook"])

        Returns:
            Combined results from all platforms
        """

        if not single_image_platforms:
            single_image_platforms = ["twitter", "facebook"]

        # Publish carousel to Instagram
        ig_result = self.execute(
            platforms=["instagram"],
            caption=caption,
            media_paths=carousel_paths,
            content_type="carousel"
        )

        # Publish first image to other platforms
        other_result = self.execute(
            platforms=single_image_platforms,
            caption=caption,
            media_paths=[carousel_paths[0]],
            content_type="post"
        )

        # Combine results
        all_results = {**ig_result.get("results", {}), **other_result.get("results", {})}
        overall_success = ig_result.get("success", False) and other_result.get("success", False)

        return {
            "success": overall_success,
            "results": all_results,
            "message": "Published carousel and images" if overall_success else "Some publications failed"
        }


# ========================================================================
# OpenClaw Skill Definition
# ========================================================================

def get_skill():
    """Return skill instance for OpenClaw to load"""
    return SocialMediaPublisherSkill()


# ========================================================================
# CLI Testing
# ========================================================================

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    skill = SocialMediaPublisherSkill()

    print("🧪 Testing social_media_publisher skill...")
    print("\n📱 Supported Platforms:")
    print("  ✅ Instagram (posts, stories, carousels, reels)")
    print("  ✅ X/Twitter (tweets, threads)")
    print("  ✅ TikTok (videos)")
    print("  ✅ YouTube Shorts (videos)")
    print("  ✅ Facebook (posts, reels)")
    print("  ❌ LinkedIn (removed)")

    # Test reel cross-platform publishing
    print("\n🎥 Testing reel cross-platform publishing...")
    result = skill.publish_reel_cross_platform(
        video_path="agents/marketer/content/generated/video_test.mp4",
        caption="The future of trading is automated. #AlgoTrading #SystematicTrading"
    )

    print(f"\n✅ Result:")
    print(f"Success: {result['success']}")
    print(f"Message: {result['message']}")
    print(f"\nPlatform Results:")
    for platform, platform_result in result.get("results", {}).items():
        print(f"  {platform}: {platform_result['message']}")

    print("\n⚠️  NOTE: Full social media API integration requires:")
    print("  - Instagram: Meta Graph API + Business account")
    print("  - X/Twitter: Twitter API v2 + Bearer token")
    print("  - TikTok: TikTok Content Posting API v2")
    print("  - YouTube: YouTube Data API v3")
    print("  - Facebook: Meta Graph API + Page access")
    print("\nThis is a structure implementation. Integrate real APIs for production.")
