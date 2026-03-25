"""
========================================================================
Custom Skill: video_to_tweet_thread
========================================================================

Converts video content into X/Twitter thread (5 tweets).

This skill analyzes a video script and generates a cohesive thread that:
- Maintains Jess Trading brand voice
- Follows 280-character limit per tweet
- Structures as: Hook → Value → Value → Value → CTA
- Includes disclaimers when showing metrics

Usage in OpenClaw:
    Use the skill video_to_tweet_thread to create a thread from a video:
    - Script: "The video script or path to video file"
    - Content type: "educational" | "product" | "social_proof"
    - Output: List of 5 tweets ready to publish

========================================================================
"""

import os
from typing import Dict, List, Any, Optional

try:
    import google.generativeai as genai
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️  ERROR: google-generativeai library not installed")
    print("Run: pip install google-generativeai")
    exit(1)


class VideoToTweetThreadSkill:
    """Skill for converting video content to X/Twitter threads"""

    # Brand voice guidelines
    BRAND_VOICE = """
    Jess Trading Brand Voice:
    - Professional but human (not corporate)
    - Concise and direct (no fluff)
    - Data-driven (lead with metrics)
    - Transparent (show risks, admit limitations)
    - Aspirational but not hypey
    - No: "guaranteed", "100%", "get rich quick", hype emojis
    """

    # Thread structure template
    THREAD_STRUCTURE = """
    Tweet Thread Structure (5 tweets):

    Tweet 1: HOOK (Attention-grabber, make them want to read more)
    - Max 280 characters
    - Question, bold statement, or surprising fact
    - No CTA yet

    Tweet 2-4: VALUE (Educational insights, data, explanation)
    - Each tweet stands alone but flows together
    - Lead with facts and metrics
    - Use short sentences, impactful

    Tweet 5: CTA + DISCLAIMER (Call to action + risk disclosure if needed)
    - Clear next step ("Link in bio", "Learn more")
    - Include disclaimer if showing metrics: "Past performance ≠ future results"
    """

    def __init__(self):
        self.name = "video_to_tweet_thread"
        self.description = "Convert video scripts into X/Twitter threads (5 tweets)"

        self.api_key = os.getenv("GEMINI_API_KEY")

        if not self.api_key:
            print("⚠️  WARNING: GEMINI_API_KEY not set in .env")
        else:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash')

    def execute(
        self,
        script: str,
        content_type: str = "educational",
        include_disclaimer: bool = False,
        max_tweets: int = 5
    ) -> Dict[str, Any]:
        """
        Generate X/Twitter thread from video script.

        Args:
            script: The video script or key points
            content_type: "educational", "product", "social_proof", "community"
            include_disclaimer: Force disclaimer in last tweet
            max_tweets: Number of tweets to generate (default 5)

        Returns:
            {
                "success": bool,
                "tweets": List[str],
                "content_type": str,
                "character_counts": List[int],
                "message": str
            }
        """

        if not self.api_key:
            return {
                "success": False,
                "message": "GEMINI_API_KEY not configured"
            }

        # Validate script
        if not script or len(script.strip()) < 20:
            return {
                "success": False,
                "message": "Script too short. Minimum 20 characters required."
            }

        # Auto-detect if metrics are present (requires disclaimer)
        metrics_keywords = ["profit factor", "sharpe", "drawdown", "win rate", "backtest", "pf", "return"]
        has_metrics = any(keyword in script.lower() for keyword in metrics_keywords)

        if has_metrics:
            include_disclaimer = True

        # Build LLM prompt
        prompt = f"""
        You are a social media expert for Jess Trading, a premium algorithmic trading brand.

        {self.BRAND_VOICE}

        {self.THREAD_STRUCTURE}

        TASK: Convert the following video script into a {max_tweets}-tweet thread.

        VIDEO SCRIPT:
        ---
        {script}
        ---

        CONTENT TYPE: {content_type}

        REQUIREMENTS:
        - Each tweet must be ≤280 characters (STRICT)
        - Follow the thread structure above
        - Maintain brand voice (professional, concise, transparent)
        - {"Include disclaimer in Tweet 5" if include_disclaimer else "No disclaimer needed"}
        - No hashtags (clean threads only)
        - Max 1 emoji per tweet (use sparingly)

        OUTPUT FORMAT:
        Return ONLY the tweets, one per line, numbered 1-{max_tweets}.

        Example:
        1. The market doesn't wait for you to wake up.
        2. In milliseconds, opportunities pass. This is why institutional traders automated decades ago.
        3. Today, retail traders have the same advantage. Systematic. Disciplined. Emotion-free.
        4. Automation doesn't guarantee profits. But it removes the biggest obstacle: human emotion.
        5. Link in bio to explore proven strategies. Past performance ≠ future results.

        NOW GENERATE THE THREAD:
        """

        # Call LLM
        try:
            response = self.model.generate_content(prompt)
            generated_text = response.text.strip()

        except Exception as e:
            return {
                "success": False,
                "message": f"LLM generation failed: {e}"
            }

        # Parse tweets from response
        tweets = self._parse_tweets(generated_text, max_tweets)

        if not tweets or len(tweets) < max_tweets:
            return {
                "success": False,
                "message": f"Failed to generate {max_tweets} valid tweets. Got {len(tweets)}."
            }

        # Validate character counts
        character_counts = [len(tweet) for tweet in tweets]
        invalid_tweets = [i+1 for i, count in enumerate(character_counts) if count > 280]

        if invalid_tweets:
            return {
                "success": False,
                "tweets": tweets,
                "character_counts": character_counts,
                "message": f"Tweets {invalid_tweets} exceed 280 characters. Regenerate required."
            }

        return {
            "success": True,
            "tweets": tweets,
            "content_type": content_type,
            "character_counts": character_counts,
            "has_disclaimer": include_disclaimer,
            "message": f"Generated {len(tweets)}-tweet thread successfully"
        }

    def _parse_tweets(self, text: str, expected_count: int) -> List[str]:
        """
        Parse numbered tweets from LLM response.

        Args:
            text: Raw LLM output
            expected_count: Expected number of tweets

        Returns:
            List of tweet strings
        """

        tweets = []
        lines = text.split('\n')

        for line in lines:
            line = line.strip()

            # Match numbered tweets (1. or 1: or Tweet 1:)
            if line and (line[0].isdigit() or line.lower().startswith('tweet')):
                # Remove numbering
                if '. ' in line:
                    tweet_text = line.split('. ', 1)[1]
                elif ': ' in line:
                    tweet_text = line.split(': ', 1)[1]
                else:
                    continue

                tweet_text = tweet_text.strip()

                if tweet_text:
                    tweets.append(tweet_text)

        return tweets[:expected_count]

    def generate_from_video_result(
        self,
        video_result: Dict[str, Any],
        content_type: str = "educational"
    ) -> Dict[str, Any]:
        """
        Convenience method: Generate thread from video generation result.

        Args:
            video_result: Output from video_generation skill
            content_type: Type of content

        Returns:
            Same as execute()
        """

        if not video_result.get("success"):
            return {
                "success": False,
                "message": "Video result indicates failure. Cannot generate thread."
            }

        script = video_result.get("script_used", "")

        return self.execute(
            script=script,
            content_type=content_type
        )

    def generate_educational_thread(
        self,
        topic: str,
        key_points: List[str]
    ) -> Dict[str, Any]:
        """
        Convenience method for educational threads.

        Args:
            topic: Main topic
            key_points: List of 2-4 key points

        Returns:
            Same as execute()
        """

        script = f"{topic}\n\n" + "\n".join(key_points)

        return self.execute(
            script=script,
            content_type="educational",
            include_disclaimer=False
        )

    def generate_product_thread(
        self,
        strategy_name: str,
        symbol: str,
        metrics: Dict[str, float],
        backtest_years: int
    ) -> Dict[str, Any]:
        """
        Convenience method for product launch threads.

        Args:
            strategy_name: Strategy name
            symbol: Trading pair
            metrics: Dict with PF, Sharpe, DD, Win Rate
            backtest_years: Years of backtesting

        Returns:
            Same as execute()
        """

        script = f"""
        New trading bot: {strategy_name}
        Symbol: {symbol}
        Profit Factor: {metrics.get('pf', 0):.2f}
        Sharpe Ratio: {metrics.get('sharpe', 0):.2f}
        Max Drawdown: {metrics.get('dd', 0):.1f}%
        Win Rate: {metrics.get('win_rate', 0):.1f}%
        Backtest: {backtest_years} years
        Out-of-sample validated
        """

        return self.execute(
            script=script,
            content_type="product",
            include_disclaimer=True  # Always include for product posts
        )


# ========================================================================
# OpenClaw Skill Definition
# ========================================================================

def get_skill():
    """Return skill instance for OpenClaw to load"""
    return VideoToTweetThreadSkill()


# ========================================================================
# CLI Testing
# ========================================================================

if __name__ == "__main__":
    skill = VideoToTweetThreadSkill()

    print("🧪 Testing video_to_tweet_thread skill...")

    # Test educational thread
    result = skill.generate_educational_thread(
        topic="Why emotional trading fails during volatility",
        key_points=[
            "Market volatility triggers fear and greed",
            "Humans make impulsive decisions under pressure",
            "Algorithms follow rules without emotion",
            "Consistency beats trying to time every move"
        ]
    )

    print(f"\n✅ Result:")
    print(f"Success: {result.get('success')}")
    print(f"Message: {result.get('message')}")

    if result.get("success"):
        print(f"\nGenerated Thread ({len(result.get('tweets', []))} tweets):")
        print("-" * 60)
        for i, tweet in enumerate(result.get('tweets', []), 1):
            char_count = len(tweet)
            print(f"\nTweet {i} ({char_count} chars):")
            print(tweet)
        print("-" * 60)
    else:
        print("Thread generation failed. Check API key and configuration.")
