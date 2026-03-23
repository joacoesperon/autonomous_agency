"""
========================================================================
Custom Skill: visual_validator
========================================================================

Validates that generated images follow Jess Trading brand guidelines:
- Correct color palette (Carbon Black, Neon Green, Light Gray, Electric Blue)
- Appropriate aspect ratios for platforms
- Quality thresholds (resolution, clarity)

This skill analyzes images using PIL/Pillow and color detection to ensure
brand consistency before sending content for approval.

Usage in OpenClaw:
    Use the skill visual_validator to check an image:
    - Image path: "path/to/image.jpg"
    - Platform: "instagram" (for aspect ratio validation)

    Returns validation results and recommendations.

========================================================================
"""

import os
from typing import Dict, List, Tuple, Any
from collections import Counter

try:
    from PIL import Image
    import numpy as np
except ImportError:
    print("⚠️  ERROR: PIL/Pillow not installed")
    print("Run: pip install Pillow numpy")
    exit(1)


class VisualValidatorSkill:
    """Skill for validating brand compliance of generated images"""

    # Jess Trading Brand Palette (RGB values)
    BRAND_COLORS = {
        "carbon_black": (16, 16, 16),    # #101010
        "neon_green": (69, 177, 79),     # #45B14F
        "light_gray": (167, 167, 167),   # #A7A7A7
        "electric_blue": (41, 121, 255)  # #2979FF
    }

    # Platform aspect ratio requirements
    ASPECT_RATIOS = {
        "instagram_post": (1, 1),      # 1:1 square
        "instagram_story": (9, 16),    # 9:16 vertical
        "twitter": (16, 9),            # 16:9 horizontal
        "linkedin": (1.91, 1),         # 1.91:1 horizontal
    }

    def __init__(self):
        self.name = "visual_validator"
        self.description = "Validate images for brand compliance (colors, aspect ratio, quality)"

    def execute(
        self,
        image_path: str,
        platform: str = "instagram_post",
        strict_mode: bool = True
    ) -> Dict[str, Any]:
        """
        Validate image for brand compliance.

        Args:
            image_path: Path to image file
            platform: Target platform for aspect ratio check
            strict_mode: If True, fail on any violation

        Returns:
            {
                "success": bool,
                "valid": bool,
                "issues": List[str],
                "warnings": List[str],
                "recommendations": List[str],
                "color_analysis": {
                    "dominant_color": str,
                    "background_color": str,
                    "brand_colors_detected": List[str],
                    "non_brand_colors": bool
                },
                "aspect_ratio": {
                    "actual": Tuple[int, int],
                    "expected": Tuple[int, int],
                    "valid": bool
                },
                "quality": {
                    "resolution": Tuple[int, int],
                    "file_size_mb": float,
                    "adequate": bool
                },
                "message": str
            }
        """

        # Check if file exists
        if not os.path.exists(image_path):
            return {
                "success": False,
                "valid": False,
                "message": f"Image file not found: {image_path}"
            }

        # Load image
        try:
            img = Image.open(image_path)
        except Exception as e:
            return {
                "success": False,
                "valid": False,
                "message": f"Failed to load image: {e}"
            }

        # Run validations
        issues = []
        warnings = []
        recommendations = []

        # 1. Color analysis
        color_analysis = self._analyze_colors(img)
        if color_analysis["non_brand_colors"] and strict_mode:
            issues.append("Image contains colors outside brand palette")

        if color_analysis["background_color"] != "carbon_black":
            warnings.append("Background is not Carbon Black (#101010)")

        # 2. Aspect ratio check
        aspect_ratio_check = self._check_aspect_ratio(img, platform)
        if not aspect_ratio_check["valid"]:
            issues.append(
                f"Aspect ratio {aspect_ratio_check['actual']} doesn't match "
                f"{platform} requirement {aspect_ratio_check['expected']}"
            )

        # 3. Quality check
        quality_check = self._check_quality(img, image_path)
        if not quality_check["adequate"]:
            warnings.append("Image quality below recommended threshold")
            recommendations.append("Regenerate at higher resolution (min 1080px)")

        # 4. Green overuse check
        green_percentage = self._calculate_color_percentage(
            img,
            self.BRAND_COLORS["neon_green"]
        )
        if green_percentage > 25:
            issues.append(
                f"Neon Green used in {green_percentage:.1f}% of image (max 20%)"
            )
            recommendations.append("Reduce Neon Green usage, use more Carbon Black")

        # Determine if valid
        valid = len(issues) == 0

        return {
            "success": True,
            "valid": valid,
            "issues": issues,
            "warnings": warnings,
            "recommendations": recommendations,
            "color_analysis": color_analysis,
            "aspect_ratio": aspect_ratio_check,
            "quality": quality_check,
            "message": "Image validated" if valid else f"{len(issues)} issues found"
        }

    def _analyze_colors(self, img: Image.Image) -> Dict[str, Any]:
        """Analyze color palette of image"""

        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # Get all pixels
        pixels = list(img.getdata())

        # Sample pixels for efficiency (max 10,000)
        if len(pixels) > 10000:
            import random
            pixels = random.sample(pixels, 10000)

        # Find dominant color (most common)
        color_counts = Counter(pixels)
        dominant_color_rgb = color_counts.most_common(1)[0][0]

        # Detect background color (top-left region)
        bg_region = img.crop((0, 0, img.width // 10, img.height // 10))
        bg_pixels = list(bg_region.getdata())
        bg_color_rgb = Counter(bg_pixels).most_common(1)[0][0]

        # Match to brand colors
        dominant_color_name = self._match_brand_color(dominant_color_rgb)
        bg_color_name = self._match_brand_color(bg_color_rgb)

        # Detect which brand colors are present
        brand_colors_detected = []
        for color_name, color_rgb in self.BRAND_COLORS.items():
            if self._color_present(pixels, color_rgb):
                brand_colors_detected.append(color_name)

        # Check for non-brand colors
        non_brand_colors = len(brand_colors_detected) < len(set(pixels)) // 100

        return {
            "dominant_color": dominant_color_name or "unknown",
            "background_color": bg_color_name or "unknown",
            "brand_colors_detected": brand_colors_detected,
            "non_brand_colors": non_brand_colors
        }

    def _match_brand_color(self, rgb: Tuple[int, int, int], tolerance: int = 30) -> str:
        """Match RGB to nearest brand color"""
        for color_name, brand_rgb in self.BRAND_COLORS.items():
            distance = sum(abs(a - b) for a, b in zip(rgb, brand_rgb))
            if distance < tolerance:
                return color_name
        return None

    def _color_present(self, pixels: List[Tuple[int, int, int]], target_rgb: Tuple[int, int, int], tolerance: int = 30) -> bool:
        """Check if color is present in pixel list"""
        for pixel in pixels:
            distance = sum(abs(a - b) for a, b in zip(pixel, target_rgb))
            if distance < tolerance:
                return True
        return False

    def _calculate_color_percentage(self, img: Image.Image, target_rgb: Tuple[int, int, int], tolerance: int = 30) -> float:
        """Calculate percentage of image using target color"""
        if img.mode != 'RGB':
            img = img.convert('RGB')

        pixels = list(img.getdata())
        matching_pixels = sum(
            1 for pixel in pixels
            if sum(abs(a - b) for a, b in zip(pixel, target_rgb)) < tolerance
        )

        return (matching_pixels / len(pixels)) * 100

    def _check_aspect_ratio(self, img: Image.Image, platform: str) -> Dict[str, Any]:
        """Check if aspect ratio matches platform requirements"""

        width, height = img.size
        actual_ratio = (width / height)

        expected = self.ASPECT_RATIOS.get(platform)

        if expected:
            expected_ratio = expected[0] / expected[1]
            # Allow 5% tolerance
            valid = abs(actual_ratio - expected_ratio) / expected_ratio < 0.05
        else:
            valid = True  # Unknown platform, assume OK
            expected = None

        return {
            "actual": (width, height),
            "expected": expected,
            "valid": valid
        }

    def _check_quality(self, img: Image.Image, image_path: str) -> Dict[str, Any]:
        """Check image quality metrics"""

        width, height = img.size
        file_size_mb = os.path.getsize(image_path) / (1024 * 1024)

        # Minimum resolution: 1080px on shortest side
        adequate = min(width, height) >= 1080

        return {
            "resolution": (width, height),
            "file_size_mb": round(file_size_mb, 2),
            "adequate": adequate
        }


# ========================================================================
# OpenClaw Skill Definition
# ========================================================================

def get_skill():
    """Return skill instance for OpenClaw to load"""
    return VisualValidatorSkill()


# ========================================================================
# CLI Testing
# ========================================================================

if __name__ == "__main__":
    import json

    skill = VisualValidatorSkill()

    print("🧪 Testing visual_validator skill...")

    # Test with example image (if exists)
    test_image = "openclaw/agents/marketer/content/test_image.jpg"

    if os.path.exists(test_image):
        result = skill.execute(test_image, platform="instagram_post")
        print(f"\n✅ Result:\n{json.dumps(result, indent=2)}")
    else:
        print(f"\n⚠️  Test image not found: {test_image}")
        print("Create a test image or specify a different path.")

        # Show brand colors
        print("\n🎨 Brand Colors (RGB):")
        for name, rgb in skill.BRAND_COLORS.items():
            print(f"  {name}: {rgb} (#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x})")
