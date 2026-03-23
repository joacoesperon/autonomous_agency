"""
========================================================================
Custom Skill: tavily_search
========================================================================

Performs web search using Tavily API for trend monitoring and research.

Tavily is optimized for LLM-friendly search results, returning clean,
relevant content perfect for content ideation and trend analysis.

Usage in OpenClaw:
    Use the skill tavily_search to find recent trends:
    - Query: "algorithmic trading news last 24 hours"
    - Max results: 5

    Returns list of relevant articles with summaries.

Get API key: https://tavily.com

========================================================================
"""

import os
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

try:
    import requests
except ImportError:
    print("⚠️  ERROR: requests library not installed")
    print("Run: pip install requests")
    exit(1)


class TavilySearchSkill:
    """Skill for web search using Tavily API"""

    def __init__(self):
        self.name = "tavily_search"
        self.description = "Search the web for trends, news, and research using Tavily API"
        self.api_key = os.getenv("TAVILY_API_KEY")

        if not self.api_key:
            print("⚠️  WARNING: TAVILY_API_KEY not set in .env")

        self.base_url = "https://api.tavily.com/search"

    def execute(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        time_range: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Perform web search.

        Args:
            query: Search query string
            max_results: Maximum number of results (default: 5, max: 10)
            search_depth: "basic" or "advanced" (uses more credits)
            include_domains: Optional list of domains to include
            exclude_domains: Optional list of domains to exclude
            time_range: Optional time filter ("day", "week", "month", "year")

        Returns:
            {
                "success": bool,
                "query": str,
                "results": [
                    {
                        "title": str,
                        "url": str,
                        "content": str,
                        "score": float,
                        "published_date": str
                    }
                ],
                "message": str
            }
        """

        if not self.api_key:
            return {
                "success": False,
                "query": query,
                "results": [],
                "message": "TAVILY_API_KEY not configured"
            }

        # Build request payload
        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": min(max_results, 10),
            "search_depth": search_depth,
            "include_answer": False,  # We don't need AI summary
            "include_raw_content": False  # Just clean content
        }

        # Add optional filters
        if include_domains:
            payload["include_domains"] = include_domains

        if exclude_domains:
            payload["exclude_domains"] = exclude_domains

        # Add time range to query if specified
        if time_range:
            time_suffix = {
                "day": "past 24 hours",
                "week": "past week",
                "month": "past month",
                "year": "past year"
            }.get(time_range, "")

            if time_suffix:
                payload["query"] = f"{query} {time_suffix}"

        # Make API request
        try:
            response = requests.post(
                self.base_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            response.raise_for_status()
            data = response.json()

        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "query": query,
                "results": [],
                "message": f"API request failed: {e}"
            }

        # Parse results
        results = []
        for item in data.get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
                "score": item.get("score", 0.0),
                "published_date": item.get("published_date", "")
            })

        return {
            "success": True,
            "query": payload["query"],
            "results": results,
            "message": f"Found {len(results)} results"
        }

    def search_trends(
        self,
        topic: str,
        time_range: str = "day"
    ) -> Dict[str, Any]:
        """
        Convenience method for trend searching.

        Args:
            topic: Topic to search (e.g., "algorithmic trading", "crypto")
            time_range: Time filter ("day", "week", "month")

        Returns:
            Same as execute()
        """

        query = f"{topic} news trends updates"
        return self.execute(
            query=query,
            max_results=5,
            time_range=time_range
        )


# ========================================================================
# OpenClaw Skill Definition
# ========================================================================

def get_skill():
    """Return skill instance for OpenClaw to load"""
    return TavilySearchSkill()


# ========================================================================
# CLI Testing
# ========================================================================

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    skill = TavilySearchSkill()

    print("🧪 Testing tavily_search skill...")

    # Test search
    result = skill.search_trends("algorithmic trading", time_range="day")

    print(f"\n✅ Result:\n")
    print(f"Query: {result['query']}")
    print(f"Success: {result['success']}")
    print(f"Message: {result['message']}\n")

    if result["results"]:
        print("Results:")
        for i, item in enumerate(result["results"], 1):
            print(f"\n{i}. {item['title']}")
            print(f"   URL: {item['url']}")
            print(f"   Score: {item['score']}")
            print(f"   Content: {item['content'][:150]}...")
    else:
        print("No results found or API key not configured.")
