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
import sys
import time
from typing import Dict, List, Any, Optional
from pathlib import Path

try:
    import replicate
    import requests
    from dotenv import load_dotenv
    load_dotenv()
except ImportError as e:
    print(f"⚠️  ERROR: Required library not installed: {e}")
    print("Run: pip install replicate requests pyyaml")
    exit(1)

# Add parent directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from shared.llm_provider import LLMProvider
    from shared.provider_profiles import load_brand_config
except ImportError:
    print("⚠️  ERROR: Cannot import shared provider helpers")
    print("Make sure shared/llm_provider.py and shared/provider_profiles.py exist")
    exit(1)


class VideoToCarouselSkill:
    """Skill for converting video content to Instagram carousels"""

    def __init__(self):
        self.name = "video_to_carousel"
        self.description = "Convert video scripts into Instagram carousel posts"

        # Load brand configuration
        self.config = self._load_brand_config()

        # Initialize LLM provider
        try:
            self.llm = LLMProvider()
            print(f"✅ LLM initialized: {self.llm.provider} - {self.llm.model}")
        except Exception as e:
            print(f"⚠️  ERROR: Failed to initialize LLM: {e}")
            self.llm = None

        # Check Replicate API
        self.replicate_api_key = os.getenv("REPLICATE_API_TOKEN")
        if not self.replicate_api_key:
            print("⚠️  WARNING: REPLICATE_API_TOKEN not set in .env")
        else:
            os.environ["REPLICATE_API_TOKEN"] = self.replicate_api_key

    def _load_brand_config(self) -> Dict[str, Any]:
        """Load resolved brand configuration from centralized YAML"""
        return load_brand_config()

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

        if not self.llm or not self.replicate_api_key:
            return {
                "success": False,
                "message": "LLM provider or REPLICATE_API_TOKEN not configured"
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

        # Build brand voice from config
        voice_chars = "\n        - ".join(self.config["brand_voice"]["characteristics"][:4])

        prompt = f"""
        You are creating an Instagram carousel post for {self.config['brand_name']} (algorithmic trading brand).

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
        - {voice_chars}

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
            generated_text = self.llm.generate(prompt)

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

        # Get brand colors from config
        colors = self.config["visual_identity"]["color_palette"]

        # Build prompt based on slide type
        if slide_type == "title":
            visual_prompt = f"""
            Instagram carousel title slide, minimalist design.
            {colors['primary']} solid background.
            Large bold text in center: "{point}"
            Text color: White or {colors['secondary']}.
            Subtle geometric accent (thin lines or dots).
            Clean, premium, Apple keynote aesthetic.
            Square format 1080x1080px.
            """
        elif slide_type == "conclusion":
            visual_prompt = f"""
            Instagram carousel CTA slide, final slide design.
            {colors['primary']} background with subtle radial gradient.
            Main text: "{point}"
            {colors['accent']} accent for CTA emphasis.
            Small "Swipe back for more" hint at top.
            Minimalist, premium fintech aesthetic.
            Square format 1080x1080px.
            """
        else:  # point or data
            visual_prompt = f"""
            Instagram carousel content slide {slide_number} of {total_slides}.
            {colors['primary']} background.
            Main point displayed: "{point}"
            Slide number indicator "{slide_number}/{total_slides}" in corner ({colors['tertiary']}).
            {colors['secondary']} accent element (line, dot, or highlight).
            Clean typography, spacious layout, premium fintech style.
            Square format 1080x1080px.
            """

        # Add brand color enforcement from config
        full_prompt = f"""
        {visual_prompt}

        STRICT COLOR REQUIREMENTS:
        - Background: {colors['primary']}
        - Text: White or {colors['tertiary']}
        - Accents: {colors['secondary']} or {colors['accent']} only
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
