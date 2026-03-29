"""
check_system_setup.py
=====================

Preflight validator for the Jess Trading autonomous agency repo.

Current focus:
- Validate the enabled-agent wiring from config/openclaw.config.yml
- Deep-check the Marketer stack because it is the primary operational agent
- Make provider switching safer by surfacing the active LLM, image, and video setup

Usage:
    python3 check_system_setup.py
    python3 check_system_setup.py --mode bootstrap
    python3 check_system_setup.py --mode runtime
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import yaml

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from shared.provider_profiles import get_provider_catalog, load_brand_config


ROOT = Path(__file__).resolve().parent
OPENCLAW_CONFIG = ROOT / "config" / "openclaw.config.yml"
BRAND_CONFIG = ROOT / "shared" / "brand_config.yml"


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
    "youtube_shorts": ["YOUTUBE_API_KEY", "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET"],
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


def load_yaml(path: Path) -> Dict:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def read_enabled_agents(config: Dict) -> List[Dict]:
    return [agent for agent in config.get("agents", []) if agent.get("enabled")]


def check_core_files(ctx: CheckContext, openclaw_config: Dict, brand_config: Dict, provider_catalog: Dict):
    if not OPENCLAW_CONFIG.exists():
        ctx.error(f"Missing config file: {OPENCLAW_CONFIG}")
    if not BRAND_CONFIG.exists():
        ctx.error(f"Missing brand config: {BRAND_CONFIG}")

    for shared_dir in [
        ROOT / "shared" / "logs",
        ROOT / "shared" / "memory",
        ROOT / "agents" / "marketer" / "content" / "drafts",
        ROOT / "agents" / "marketer" / "content" / "generated",
        ROOT / "agents" / "marketer" / "content" / "published",
    ]:
        if not shared_dir.exists():
            ctx.warn(f"Directory not present yet: {shared_dir.relative_to(ROOT)}")

    enabled_agents = read_enabled_agents(openclaw_config)
    if not enabled_agents:
        ctx.warn("No enabled agents found in config/openclaw.config.yml")

    for agent in openclaw_config.get("agents", []):
        identity_file = agent.get("identity_file")
        if not identity_file:
            ctx.error(f"Agent '{agent.get('name')}' is missing identity_file in config")
            continue
        identity_path = ROOT / identity_file
        if not identity_path.exists():
            ctx.error(f"Agent '{agent.get('name')}' points to a missing identity file: {identity_file}")

    llm_block = openclaw_config.get("llm", {})
    runtime_env = llm_block.get("api_key_env")
    ctx.note(
        "OpenClaw runtime model: "
        f"{llm_block.get('provider', 'unknown')} / {llm_block.get('model', 'unknown')}"
    )
    if runtime_env:
        ctx.require(bool(os.getenv(runtime_env)), f"Active OpenClaw runtime requires env var {runtime_env}")

    llm_defaults = brand_config.get("llm_defaults", {})
    ctx.note(
        "Marketer content model: "
        f"{llm_defaults.get('provider', 'unknown')} / {llm_defaults.get('model', 'unknown')}"
    )
    ctx.note(f"Video provider: {brand_config.get('video_generation', {}).get('provider', 'unknown')}")
    ctx.note(f"Image provider: {brand_config.get('image_generation', {}).get('provider', 'unknown')}")
    selections = provider_catalog.get("selections", {})
    for selection_kind in ("llm", "image", "video"):
        selected_name = selections.get(selection_kind)
        if selected_name:
            ctx.note(f"Selected {selection_kind} profile: {selected_name}")


def check_marketer_stack(ctx: CheckContext, openclaw_config: Dict, brand_config: Dict):
    marketer = next((a for a in openclaw_config.get("agents", []) if a.get("name") == "marketer"), None)
    if marketer is None:
        ctx.error("Marketer agent is missing from config/openclaw.config.yml")
        return

    skills = set(marketer.get("skills", []))
    for required_skill in [
        "telegram_hitl",
        "content_script_generator",
        "dynamic_prompt_generator",
        "image_generation",
        "video_generation",
        "social_media_publisher",
    ]:
        if required_skill not in skills:
            ctx.error(f"Marketer is missing required skill '{required_skill}' in config/openclaw.config.yml")

    for env_var in ["TELEGRAM_BOT_TOKEN", "TELEGRAM_OWNER_CHAT_ID"]:
        ctx.require(bool(os.getenv(env_var)), f"Missing required HITL env var: {env_var}")

    llm_defaults = brand_config.get("llm_defaults", {})
    llm_provider = llm_defaults.get("provider")
    llm_model = llm_defaults.get("model")
    if llm_provider not in LLM_PROVIDER_ENV_VARS:
        ctx.error(
            "Unsupported llm_defaults.provider in shared/brand_config.yml: "
            f"{llm_provider}. Use one of {sorted(LLM_PROVIDER_ENV_VARS)}"
        )
    else:
        env_var = LLM_PROVIDER_ENV_VARS[llm_provider]
        ctx.require(
            bool(os.getenv(env_var)),
            f"Active marketer LLM provider '{llm_provider}' requires env var {env_var}",
        )
        ctx.note(f"Active marketer LLM model configured as {llm_model}")

    video_provider = brand_config.get("video_generation", {}).get("provider")
    video_meta = VIDEO_PROVIDERS.get(video_provider)
    if not video_meta:
        ctx.error(f"Unsupported video provider in shared/brand_config.yml: {video_provider}")
    else:
        if not video_meta["implemented"]:
            ctx.error(
                f"Video provider '{video_provider}' is configurable but not implemented yet in shared/video_provider.py"
            )
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
    if not image_meta:
        ctx.error(f"Unsupported image provider in shared/brand_config.yml: {image_provider}")
    else:
        if not image_meta["implemented"]:
            ctx.error(
                f"Image provider '{image_provider}' is configurable but not implemented yet in shared/image_provider.py"
            )
        ctx.require(
            bool(os.getenv(image_meta["env"])),
            f"Active image provider '{image_provider}' requires env var {image_meta['env']}",
        )

    publisher_platforms = (
        openclaw_config.get("skills", {})
        .get("social_media_publisher", {})
        .get("platforms", [])
    )
    for platform in publisher_platforms:
        required_envs = OPTIONAL_PUBLISHING_ENV.get(platform, [])
        if required_envs and not all(os.getenv(name) for name in required_envs):
            ctx.warn(
                f"Auto-publishing for '{platform}' is configured but missing one or more env vars: "
                f"{', '.join(required_envs)}"
            )


def check_disabled_agent_notes(ctx: CheckContext, openclaw_config: Dict):
    for agent in openclaw_config.get("agents", []):
        if agent.get("enabled"):
            continue
        ctx.note(f"Agent '{agent.get('name')}' is disabled; only wiring/basic file checks were applied")


def render_report(ctx: CheckContext):
    print("Jess Trading System Preflight")
    print("=" * 32)
    print(f"Mode: {ctx.mode}")
    print("")

    if ctx.info:
        print("Current stack:")
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
        print("All critical checks passed.")
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
    parser = argparse.ArgumentParser(description="Jess Trading system preflight validator")
    parser.add_argument(
        "--mode",
        choices=["bootstrap", "runtime"],
        default="runtime",
        help="bootstrap = relaxed env checks, runtime = fail on active stack requirements",
    )
    args = parser.parse_args()

    ctx = CheckContext(mode=args.mode)

    try:
        openclaw_config = load_yaml(OPENCLAW_CONFIG)
        provider_catalog = get_provider_catalog()
        brand_config = load_brand_config()
    except Exception as exc:
        print(f"Failed to load configuration: {exc}")
        return 1

    check_core_files(ctx, openclaw_config, brand_config, provider_catalog)
    check_marketer_stack(ctx, openclaw_config, brand_config)
    check_disabled_agent_notes(ctx, openclaw_config)
    render_report(ctx)
    return 1 if ctx.errors else 0


if __name__ == "__main__":
    sys.exit(main())
