"""
check_system_setup.py
=====================

Repo-focused preflight validator for the Jess Trading autonomous agency.

What this script validates:
- agent workspace completeness for current OpenClaw-style workspaces
- resolved Marketer provider stack from shared/brand_config.yml
- repo files/directories that should exist on any machine cloning this repo
- optional environment variables for the selected Marketer stack

What this script does NOT do:
- configure the user's OpenClaw runtime model
- mutate the user's ~/.openclaw config
- assume the current machine is the canonical deployment target

Usage:
    python3 check_system_setup.py
    python3 check_system_setup.py --mode bootstrap
    python3 check_system_setup.py --mode runtime
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, List

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from shared.marketer_state import MarketerStateManager
from shared.provider_profiles import get_provider_catalog, load_brand_config


ROOT = Path(__file__).resolve().parent
BRAND_CONFIG = ROOT / "shared" / "brand_config.yml"
REGISTER_SCRIPT = ROOT / "register_openclaw_agents.py"

AGENT_WORKSPACES = {
    "marketer": ROOT / "agents" / "marketer",
    "innovator": ROOT / "agents" / "innovator",
    "support": ROOT / "agents" / "support",
    "operator": ROOT / "agents" / "operator",
}

WORKSPACE_REQUIRED_FILES = [
    "AGENTS.md",
    "IDENTITY.md",
    "HEARTBEAT.md",
    "SOUL.md",
    "TOOLS.md",
    "USER.md",
]

LLM_PROVIDER_ENV_VARS = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
}

VIDEO_PROVIDERS = {
    "d-id": {"implemented": True, "env": "D_ID_API_KEY"},
    "heygen": {"implemented": True, "env": "HEYGEN_API_KEY"},
    "openai-sora": {"implemented": True, "env": "OPENAI_API_KEY"},
    "veo": {"implemented": True, "env": "GOOGLE_CLOUD_PROJECT"},
    "synthesia": {"implemented": False, "env": "SYNTHESIA_API_KEY"},
    "runway": {"implemented": False, "env": "RUNWAY_API_KEY"},
    "pika": {"implemented": False, "env": "PIKA_API_KEY"},
}

IMAGE_PROVIDERS = {
    "flux": {"implemented": True, "env": "REPLICATE_API_TOKEN"},
    "dalle": {"implemented": True, "env": "OPENAI_API_KEY"},
    "openai-image": {"implemented": True, "env": "OPENAI_API_KEY"},
    "sdxl": {"implemented": True, "env": "REPLICATE_API_TOKEN"},
    "midjourney": {"implemented": False, "env": "MIDJOURNEY_API_KEY"},
    "ideogram": {"implemented": False, "env": "IDEOGRAM_API_KEY"},
}

OPTIONAL_PUBLISHING_ENV = {
    "instagram": ["INSTAGRAM_ACCESS_TOKEN", "INSTAGRAM_USER_ID"],
    "twitter": ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"],
    "tiktok": ["TIKTOK_ACCESS_TOKEN"],
    "youtube_shorts": ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET"],
    "facebook": ["FACEBOOK_ACCESS_TOKEN", "FACEBOOK_PAGE_ID"],
}


class CheckContext:
    def __init__(self, mode: str):
        self.mode = mode
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []

    def require(self, condition: bool, message: str):
        if condition:
            return
        if self.mode == "runtime":
            self.errors.append(message)
        else:
            self.warnings.append(message)

    def error(self, message: str):
        self.errors.append(message)

    def warn(self, message: str):
        self.warnings.append(message)

    def note(self, message: str):
        self.info.append(message)


def check_repo_structure(ctx: CheckContext):
    for path in [
        ROOT / "SOUL.md",
        ROOT / "README.md",
        ROOT / "requirements.txt",
        ROOT / "shared",
        ROOT / "skills",
        ROOT / "assets",
        ROOT / "assets" / "mascot",
        REGISTER_SCRIPT,
    ]:
        if not path.exists():
            ctx.error(f"Missing required repo path: {path.relative_to(ROOT)}")

    for path in [
        ROOT / "shared" / "logs",
        ROOT / "shared" / "memory",
        ROOT / "agents" / "marketer" / "content" / "drafts",
        ROOT / "agents" / "marketer" / "content" / "generated",
        ROOT / "agents" / "marketer" / "content" / "published",
    ]:
        if not path.exists():
            ctx.warn(f"Directory not present yet: {path.relative_to(ROOT)}")

    for agent_name, workspace in AGENT_WORKSPACES.items():
        if not workspace.exists():
            ctx.error(f"Missing agent workspace: {workspace.relative_to(ROOT)}")
            continue
        for filename in WORKSPACE_REQUIRED_FILES:
            if not (workspace / filename).exists():
                ctx.error(f"Agent `{agent_name}` is missing workspace file: {workspace.relative_to(ROOT) / filename}")

    if not shutil.which("openclaw"):
        ctx.warn("`openclaw` command not found in PATH. Install it before registering these workspaces.")
    else:
        ctx.note("OpenClaw CLI detected")

    legacy_config = ROOT / "config" / "openclaw.config.yml"
    if legacy_config.exists():
        ctx.note("config/openclaw.config.yml exists as legacy reference and is not required by current OpenClaw workspaces")


def check_provider_stack(ctx: CheckContext, brand_config: Dict, provider_catalog: Dict):
    llm_defaults = brand_config.get("llm_defaults", {})
    llm_provider = llm_defaults.get("provider", "unknown")
    llm_model = llm_defaults.get("model", "unknown")
    image_provider = brand_config.get("image_generation", {}).get("provider", "unknown")
    video_provider = brand_config.get("video_generation", {}).get("provider", "unknown")
    mascot_enabled = bool(brand_config.get("brand_mascot", {}).get("enabled"))

    ctx.note(f"Resolved Marketer LLM: {llm_provider} / {llm_model}")
    ctx.note(f"Resolved Marketer image provider: {image_provider}")
    ctx.note(f"Resolved Marketer video provider: {video_provider}")
    ctx.note(f"Brand mascot enabled: {mascot_enabled}")

    selections = provider_catalog.get("selections", {})
    for selection_kind in ("llm", "image", "video"):
        selected_name = selections.get(selection_kind)
        if selected_name:
            ctx.note(f"Selected {selection_kind} profile: {selected_name}")

    if llm_provider not in LLM_PROVIDER_ENV_VARS:
        ctx.error(f"Unsupported llm_defaults.provider in shared/brand_config.yml: {llm_provider}")

    image_meta = IMAGE_PROVIDERS.get(image_provider)
    if not image_meta:
        ctx.error(f"Unsupported image provider in shared/brand_config.yml: {image_provider}")
    elif not image_meta["implemented"]:
        ctx.error(f"Image provider '{image_provider}' is selectable but not implemented yet")

    video_meta = VIDEO_PROVIDERS.get(video_provider)
    if not video_meta:
        ctx.error(f"Unsupported video provider in shared/brand_config.yml: {video_provider}")
    elif not video_meta["implemented"]:
        ctx.error(f"Video provider '{video_provider}' is selectable but not implemented yet")

    mascot_config = brand_config.get("brand_mascot", {})
    if mascot_enabled and video_provider == "veo":
        reference_images = mascot_config.get("reference_images", [])
        if not reference_images:
            ctx.warn("brand_mascot is enabled with Veo but reference_images is empty")

    try:
        marketer_state = MarketerStateManager()
        slots = marketer_state.get_today_slots()
        ctx.note(f"Resolved Marketer content_schedule slots today: {len(slots)}")
    except Exception as exc:
        ctx.error(f"content_schedule in shared/brand_config.yml could not be resolved: {exc}")


def check_runtime_readiness(ctx: CheckContext, brand_config: Dict):
    llm_provider = brand_config.get("llm_defaults", {}).get("provider")
    llm_env = LLM_PROVIDER_ENV_VARS.get(llm_provider)
    if llm_env:
        ctx.require(bool(os.getenv(llm_env)), f"Active marketer LLM provider '{llm_provider}' requires env var {llm_env}")

    for env_var in ["TELEGRAM_BOT_TOKEN", "TELEGRAM_OWNER_CHAT_ID"]:
        ctx.require(bool(os.getenv(env_var)), f"Missing required HITL env var: {env_var}")

    video_provider = brand_config.get("video_generation", {}).get("provider")
    video_meta = VIDEO_PROVIDERS.get(video_provider)
    if video_meta:
        ctx.require(
            bool(os.getenv(video_meta["env"])),
            f"Active video provider '{video_provider}' requires env var {video_meta['env']}",
        )
        if video_provider == "veo" and not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            ctx.warn(
                "Veo is active. If you are not using `gcloud auth application-default login`, "
                "set GOOGLE_APPLICATION_CREDENTIALS for ADC."
            )

    image_provider = brand_config.get("image_generation", {}).get("provider")
    image_meta = IMAGE_PROVIDERS.get(image_provider)
    if image_meta:
        ctx.require(
            bool(os.getenv(image_meta["env"])),
            f"Active image provider '{image_provider}' requires env var {image_meta['env']}",
        )

    for platform, required_envs in OPTIONAL_PUBLISHING_ENV.items():
        if not all(os.getenv(name) for name in required_envs):
            ctx.warn(
                f"Auto-publishing for '{platform}' will need env vars: {', '.join(required_envs)}"
            )

    if not os.getenv("PUBLIC_MEDIA_BASE_URL"):
        ctx.warn(
            "Instagram autopublish from local generated media usually requires PUBLIC_MEDIA_BASE_URL "
            "unless the workflow passes already-public media URLs."
        )


def render_report(ctx: CheckContext):
    print("Jess Trading Repo Preflight")
    print("=" * 29)
    print(f"Mode: {ctx.mode}")
    print("")

    if ctx.info:
        print("Current repo state:")
        for item in ctx.info:
            print(f"- {item}")
        print("")

    if ctx.warnings:
        print("Warnings:")
        for item in ctx.warnings:
            print(f"- {item}")
        print("")

    if ctx.errors:
        print("Errors:")
        for item in ctx.errors:
            print(f"- {item}")
        print("")

    if not ctx.errors and not ctx.warnings:
        print("All checks passed.")
        print("")

    print(
        "Result: "
        + (
            "FAILED"
            if ctx.errors
            else "OK WITH WARNINGS"
            if ctx.warnings
            else "OK"
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Jess Trading repo/workspace preflight validator")
    parser.add_argument(
        "--mode",
        choices=["bootstrap", "runtime"],
        default="bootstrap",
        help="bootstrap = repo/workspace validation, runtime = also require env vars for the selected Marketer stack",
    )
    args = parser.parse_args()

    ctx = CheckContext(mode=args.mode)

    try:
        provider_catalog = get_provider_catalog()
        brand_config = load_brand_config()
    except Exception as exc:
        print(f"Failed to load repo configuration: {exc}")
        return 1

    check_repo_structure(ctx)
    check_provider_stack(ctx, brand_config, provider_catalog)
    if args.mode == "runtime":
        check_runtime_readiness(ctx, brand_config)

    render_report(ctx)
    return 1 if ctx.errors else 0


if __name__ == "__main__":
    sys.exit(main())
