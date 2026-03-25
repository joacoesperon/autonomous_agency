"""
========================================================================
Custom Skill: video_to_carousel
========================================================================

Converts video content into Instagram carousel (5-10 slides).

This skill analyzes a video script and generates a carousel post where:
- Each slide highlights one key point
- Visual consistency across all slides
- Brand-compliant design (Carbon Black + Neon Green)
- Text overlays with key takeaways
- Perfect for educational and product content

Usage in OpenClaw:
    Use the skill video_to_carousel to create a carousel from a video:
    - Script: "The video script or key points"
    - Slides: 5-8 (optimal for engagement)
    - Output: List of image paths ready for Instagram carousel

========================================================================
"""

import os
import time
from typing import Dict, List, Any, Optional

try:
    import google.generativeai as genai
    import replicate
    import requests
    from dotenv import load_dotenv
    load_dotenv()
except ImportError as e:
    print(f"⚠️  ERROR: Required library not installed: {e}")
    print("Run: pip install google-generativeai replicate requests")
    exit(1)


class VideoToCarouselSkill:
    """Skill for converting video content to Instagram carousels"""

    # Brand visual guidelines
    BRAND_COLORS = {
        "background": "#101010",  # Carbon Black
        "highlight": "#45B14F",   # Neon Green
        "text": "#A7A7A7",        # Light Gray
        "cta": "#2979FF"          # Electric Blue
    }

    # Carousel design templates
    SLIDE_TEMPLATES = {
        "title": "Bold statement or question, minimal design, centered text",
        "point": "Key point with supporting detail, bullet or number format",
        "data": "Metric or statistic, large number with context",
        "conclusion": "Summary or CTA, call to action prominent"
    }

    def __init__(self):
        self.name = "video_to_carousel"
        self.description = "Convert video scripts into Instagram carousel posts"

        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.replicate_api_key = os.getenv("REPLICATE_API_TOKEN")

        if not self.gemini_api_key:
            print("⚠️  WARNING: GEMINI_API_KEY not set in .env")
        else:
            genai.configure(api_key=self.gemini_api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash')

        if not self.replicate_api_key:
            print("⚠️  WARNING: REPLICATE_API_TOKEN not set in .env")
        else:
            os.environ["REPLICATE_API_TOKEN"] = self.replicate_api_key

    def execute(
        self,
        script: str,
        num_slides: int = 6,
        content_type: str = "educational",
        output_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate Instagram carousel from video script.

        Args:
            script: The video script or key points
            num_slides: Number of slides to generate (5-10 recommended)
            content_type: "educational", "product", "social_proof"
            output_dir: Directory to save generated images

        Returns:
            {
                "success": bool,
                "slides": List[Dict] with paths and captions,
                "num_slides": int,
                "message": str
            }
        """

        if not self.gemini_api_key or not self.replicate_api_key:
            return {
                "success": False,
                "message": "GEMINI_API_KEY or REPLICATE_API_TOKEN not configured"
            }

        # Validate inputs
        if not script or len(script.strip()) < 20:
            return {
                "success": False,
                "message": "Script too short. Minimum 20 characters required."
            }

        if num_slides < 5 or num_slides > 10:
            return {
                "success": False,
                "message": "num_slides must be between 5-10 for optimal engagement"
            }

        # Create output directory
        if not output_dir:
            timestamp = int(time.time())
            output_dir = f"agents/marketer/content/generated/carousel_{timestamp}"

        os.makedirs(output_dir, exist_ok=True)

        # Step 1: Extract key points from script using LLM
        key_points_result = self._extract_key_points(script, num_slides, content_type)

        if not key_points_result.get("success"):
            return key_points_result

        key_points = key_points_result.get("points", [])

        # Step 2: Generate images for each slide
        slides = []

        for i, point in enumerate(key_points, 1):
            slide_type = self._determine_slide_type(i, num_slides)

            image_result = self._generate_slide_image(
                point=point,
                slide_number=i,
                total_slides=num_slides,
                slide_type=slide_type,
                output_dir=output_dir
            )

            if image_result.get("success"):
                slides.append({
                    "slide_number": i,
                    "text": point,
                    "image_path": image_result.get("local_path"),
                    "slide_type": slide_type
                })
            else:
                return {
                    "success": False,
                    "message": f"Failed to generate slide {i}: {image_result.get('message')}"
                }

        return {
            "success": True,
            "slides": slides,
            "num_slides": len(slides),
            "output_dir": output_dir,
            "content_type": content_type,
            "message": f"Generated {len(slides)}-slide carousel successfully"
        }

    def _extract_key_points(
        self,
        script: str,
        num_points: int,
        content_type: str
    ) -> Dict[str, Any]:
        """
        Use LLM to extract key points from script for carousel.

        Args:
            script: Video script
            num_points: Number of points to extract
            content_type: Type of content

        Returns:
            {"success": bool, "points": List[str]}
        """

        prompt = f"""
        You are creating an Instagram carousel post for Jess Trading (algorithmic trading brand).

        TASK: Extract {num_points} key points from the video script below for a carousel post.

        VIDEO SCRIPT:
        ---
        {script}
        ---

        CONTENT TYPE: {content_type}

        REQUIREMENTS:
        - Point 1: Title/Hook (engaging statement or question, max 8 words)
        - Points 2-{num_points-1}: Key insights (each 1-2 sentences, max 15 words per point)
        - Point {num_points}: CTA/Conclusion (call to action, max 10 words)

        BRAND VOICE:
        - Professional and concise
        - Data-driven when possible
        - No hype language
        - Transparent and educational

        OUTPUT FORMAT:
        Return ONLY the points, one per line, numbered 1-{num_points}.

        Example:
        1. The market doesn't wait for you
        2. Opportunities pass in milliseconds
        3. Institutional traders automated decades ago
        4. Retail traders now have the same tools
        5. Systematic trading removes emotion
        6. Link in bio to explore strategies

        NOW EXTRACT THE KEY POINTS:
        """

        try:
            response = self.model.generate_content(prompt)
            generated_text = response.text.strip()

            # Parse points
            points = []
            lines = generated_text.split('\n')

            for line in lines:
                line = line.strip()
                if line and line[0].isdigit():
                    # Remove numbering
                    if '. ' in line:
                        point_text = line.split('. ', 1)[1]
                    elif ': ' in line:
                        point_text = line.split(': ', 1)[1]
                    else:
                        continue

                    point_text = point_text.strip()
                    if point_text:
                        points.append(point_text)

            if len(points) < num_points:
                return {
                    "success": False,
                    "message": f"Failed to extract {num_points} points. Got {len(points)}."
                }

            return {
                "success": True,
                "points": points[:num_points]
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"LLM extraction failed: {e}"
            }

    def _determine_slide_type(self, slide_num: int, total_slides: int) -> str:
        """Determine visual template for slide based on position."""
        if slide_num == 1:
            return "title"
        elif slide_num == total_slides:
            return "conclusion"
        else:
            return "point"

    def _generate_slide_image(
        self,
        point: str,
        slide_number: int,
        total_slides: int,
        slide_type: str,
        output_dir: str
    ) -> Dict[str, Any]:
        """
        Generate image for a single carousel slide.

        Args:
            point: The text/key point for this slide
            slide_number: Current slide number
            total_slides: Total slides in carousel
            slide_type: "title", "point", "data", or "conclusion"
            output_dir: Directory to save image

        Returns:
            {"success": bool, "local_path": str, "message": str}
        """

        # Build prompt based on slide type
        if slide_type == "title":
            visual_prompt = f"""
            Instagram carousel title slide, minimalist design.
            Carbon Black #101010 solid background.
            Large bold text in center: "{point}"
            Text color: White or Neon Green #45B14F.
            Subtle geometric accent (thin lines or dots).
            Clean, premium, Apple keynote aesthetic.
            Square format 1080x1080px.
            """
        elif slide_type == "conclusion":
            visual_prompt = f"""
            Instagram carousel CTA slide, final slide design.
            Carbon Black #101010 background with subtle radial gradient.
            Main text: "{point}"
            Electric Blue #2979FF accent for CTA emphasis.
            Small "Swipe back for more" hint at top.
            Minimalist, premium fintech aesthetic.
            Square format 1080x1080px.
            """
        else:  # point or data
            visual_prompt = f"""
            Instagram carousel content slide {slide_number} of {total_slides}.
            Carbon Black #101010 background.
            Main point displayed: "{point}"
            Slide number indicator "{slide_number}/{total_slides}" in corner (Light Gray #A7A7A7).
            Neon Green #45B14F accent element (line, dot, or highlight).
            Clean typography, spacious layout, premium fintech style.
            Square format 1080x1080px.
            """

        # Add brand color enforcement
        full_prompt = f"""
        {visual_prompt}

        STRICT COLOR REQUIREMENTS:
        - Background: Carbon Black #101010
        - Text: White or Light Gray #A7A7A7
        - Accents: Neon Green #45B14F or Electric Blue #2979FF only
        - NO other colors allowed
        """

        # Generate image using Replicate
        try:
            output = replicate.run(
                "black-forest-labs/flux-schnell",
                input={
                    "prompt": full_prompt,
                    "aspect_ratio": "1:1",
                    "output_format": "jpg",
                    "output_quality": 90,
                    "num_outputs": 1
                }
            )

            # Get image URL
            if isinstance(output, list) and len(output) > 0:
                image_url = output[0]
            else:
                image_url = str(output)

        except Exception as e:
            return {
                "success": False,
                "message": f"Image generation failed: {e}"
            }

        # Download image
        try:
            output_path = os.path.join(output_dir, f"slide_{slide_number:02d}.jpg")

            response = requests.get(image_url, timeout=30)
            response.raise_for_status()

            with open(output_path, 'wb') as f:
                f.write(response.content)

            return {
                "success": True,
                "local_path": output_path,
                "image_url": image_url,
                "message": f"Slide {slide_number} generated"
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to download slide {slide_number}: {e}"
            }

    def generate_from_video_result(
        self,
        video_result: Dict[str, Any],
        num_slides: int = 6
    ) -> Dict[str, Any]:
        """
        Convenience method: Generate carousel from video generation result.

        Args:
            video_result: Output from video_generation skill
            num_slides: Number of slides

        Returns:
            Same as execute()
        """

        if not video_result.get("success"):
            return {
                "success": False,
                "message": "Video result indicates failure. Cannot generate carousel."
            }

        script = video_result.get("script_used", "")

        return self.execute(
            script=script,
            num_slides=num_slides
        )


# ========================================================================
# OpenClaw Skill Definition
# ========================================================================

def get_skill():
    """Return skill instance for OpenClaw to load"""
    return VideoToCarouselSkill()


# ========================================================================
# CLI Testing
# ========================================================================

if __name__ == "__main__":
    skill = VideoToCarouselSkill()

    print("🧪 Testing video_to_carousel skill...")

    # Test educational carousel
    test_script = """
    The market doesn't wait for you to wake up.
    In milliseconds, opportunities pass.
    Institutional traders solved this decades ago with automation.
    Now retail traders have the same advantage.
    Systematic. Disciplined. Emotion-free.
    The future of trading is automated.
    Link in bio to explore proven strategies.
    """

    result = skill.execute(
        script=test_script,
        num_slides=6,
        content_type="educational"
    )

    print(f"\n✅ Result:")
    print(f"Success: {result.get('success')}")
    print(f"Message: {result.get('message')}")

    if result.get("success"):
        print(f"\nGenerated Carousel ({result.get('num_slides')} slides):")
        print(f"Output directory: {result.get('output_dir')}")
        print("\nSlides:")
        for slide in result.get('slides', []):
            print(f"  {slide['slide_number']}. {slide['text'][:50]}... ({slide['slide_type']})")
            print(f"     Path: {slide['image_path']}")
    else:
        print("Carousel generation failed. Check API keys and configuration.")
