"""
========================================================================
Custom Skill: social_media_publisher
========================================================================

Publishes approved content to social media platforms:
- Instagram (posts and stories)
- X/Twitter (tweets and threads)
- LinkedIn (company page posts)

CRITICAL: This skill should ONLY be called AFTER owner approval via HITL.

Usage in OpenClaw:
    Use the skill social_media_publisher to publish content:
    - Platforms: ["instagram", "twitter", "linkedin"]
    - Caption: "Your post text..."
    - Media path: "path/to/image.jpg"
    - Content type: "post" or "story" (for Instagram)

========================================================================
"""

import os
import time
from typing import Dict, List, Optional, Any

try:
    import requests
except ImportError:
    print("⚠️  ERROR: requests library not installed")
    print("Run: pip install requests")
    exit(1)


class SocialMediaPublisherSkill:
    """Skill for publishing content to social media platforms"""

    def __init__(self):
        self.name = "social_media_publisher"
        self.description = "Publish approved content to Instagram, X, and LinkedIn"

        # Load API credentials from environment
        self.instagram_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        self.twitter_api_key = os.getenv("X_API_KEY")
        self.twitter_api_secret = os.getenv("X_API_SECRET")
        self.twitter_access_token = os.getenv("X_ACCESS_TOKEN")
        self.twitter_access_secret = os.getenv("X_ACCESS_SECRET")
        self.linkedin_token = os.getenv("LINKEDIN_ACCESS_TOKEN")

        # Rate limiting
        self.last_post_time = {}

    def execute(
        self,
        platforms: List[str],
        caption: str,
        media_path: Optional[str] = None,
        content_type: str = "post",
        scheduled_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Publish content to specified platforms.

        Args:
            platforms: List of platforms ("instagram", "twitter", "linkedin")
            caption: Text content/caption
            media_path: Optional path to image/video
            content_type: "post" or "story" (for Instagram)
            scheduled_time: Optional ISO timestamp for scheduling

        Returns:
            {
                "success": bool,
                "results": {
                    "instagram": {"success": bool, "post_id": str, "message": str},
                    "twitter": {"success": bool, "tweet_id": str, "message": str},
                    "linkedin": {"success": bool, "post_id": str, "message": str}
                },
                "message": str
            }
        """

        results = {}
        overall_success = True

        # Validate platforms
        valid_platforms = ["instagram", "twitter", "linkedin"]
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

        # Publish to each platform
        if "instagram" in platforms:
            results["instagram"] = self._publish_instagram(
                caption=caption,
                media_path=media_path,
                content_type=content_type
            )
            if not results["instagram"]["success"]:
                overall_success = False

        if "twitter" in platforms:
            results["twitter"] = self._publish_twitter(
                text=caption,
                media_path=media_path
            )
            if not results["twitter"]["success"]:
                overall_success = False

        if "linkedin" in platforms:
            results["linkedin"] = self._publish_linkedin(
                text=caption,
                media_path=media_path
            )
            if not results["linkedin"]["success"]:
                overall_success = False

        # Log published content
        if overall_success:
            self._log_published_content(platforms, caption, results)

        return {
            "success": overall_success,
            "results": results,
            "message": "Content published" if overall_success else "Some publications failed"
        }

    def _publish_instagram(
        self,
        caption: str,
        media_path: Optional[str],
        content_type: str
    ) -> Dict[str, Any]:
        """Publish to Instagram using Graph API"""

        if not self.instagram_token:
            return {
                "success": False,
                "message": "Instagram access token not configured"
            }

        # Placeholder implementation
        # Real implementation requires:
        # 1. Upload media to Instagram
        # 2. Create media container
        # 3. Publish container

        return {
            "success": False,
            "message": "Instagram publishing not fully implemented yet. Use manual posting or integrate Graph API."
        }

    def _publish_twitter(
        self,
        text: str,
        media_path: Optional[str]
    ) -> Dict[str, Any]:
        """Publish to X/Twitter using API v2"""

        if not all([
            self.twitter_api_key,
            self.twitter_api_secret,
            self.twitter_access_token,
            self.twitter_access_secret
        ]):
            return {
                "success": False,
                "message": "Twitter API credentials not fully configured"
            }

        # Placeholder implementation
        # Real implementation requires:
        # 1. OAuth1 authentication
        # 2. Upload media (if applicable)
        # 3. Create tweet with or without media

        return {
            "success": False,
            "message": "Twitter publishing not fully implemented yet. Use tweepy library for full integration."
        }

    def _publish_linkedin(
        self,
        text: str,
        media_path: Optional[str]
    ) -> Dict[str, Any]:
        """Publish to LinkedIn using API"""

        if not self.linkedin_token:
            return {
                "success": False,
                "message": "LinkedIn access token not configured"
            }

        # Placeholder implementation
        # Real implementation requires:
        # 1. Upload media to LinkedIn (if applicable)
        # 2. Create share/post
        # 3. Publish to company page

        return {
            "success": False,
            "message": "LinkedIn publishing not fully implemented yet. Use LinkedIn API documentation."
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
        results: Dict[str, Any]
    ):
        """Log published content to file"""

        log_file = "openclaw/agents/marketer/content/published_log.yml"
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        import yaml

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

    def publish_thread(
        self,
        tweets: List[str],
        media_paths: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Publish a Twitter thread (multiple connected tweets).

        Args:
            tweets: List of tweet texts (each max 280 chars)
            media_paths: Optional list of media paths (one per tweet or None)

        Returns:
            Same as execute()
        """

        # Validate tweet lengths
        for i, tweet in enumerate(tweets):
            if len(tweet) > 280:
                return {
                    "success": False,
                    "message": f"Tweet {i+1} exceeds 280 characters ({len(tweet)} chars)"
                }

        # Placeholder for thread publishing
        return {
            "success": False,
            "message": "Thread publishing not fully implemented yet. Use tweepy for Twitter threads."
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

    # Test publishing (dry run)
    result = skill.execute(
        platforms=["instagram", "twitter"],
        caption="Test post: The future of trading is automated.",
        media_path="openclaw/agents/marketer/content/test_image.jpg",
        content_type="post"
    )

    print(f"\n✅ Result:")
    print(f"Success: {result['success']}")
    print(f"Message: {result['message']}")
    print(f"\nPlatform Results:")
    for platform, platform_result in result.get("results", {}).items():
        print(f"  {platform}: {platform_result['message']}")

    print("\n⚠️  NOTE: Full social media API integration requires:")
    print("  - Instagram: Graph API setup + Business account")
    print("  - X/Twitter: OAuth1 + tweepy library")
    print("  - LinkedIn: API app + Company page admin access")
    print("\nThis is a placeholder implementation. Integrate real APIs for production.")
