#!/usr/bin/env python3
"""
Repository preflight checks for Jess Trading agency.

This script does NOT run OpenClaw. It validates local repo readiness:
- Python syntax compile
- brand_config resolution
- provider selection/profile consistency
- .env.example coverage against os.getenv() usage
- marketer heartbeat mode
- required file presence
"""

from __future__ import annotations

import py_compile
import re
import sys
from pathlib import Path
from typing import List, Tuple

import yaml


ROOT = Path(__file__).resolve().parent


def collect_python_files() -> List[Path]:
    return [p for p in ROOT.rglob("*.py") if ".venv" not in str(p)]


def check_compile(py_files: List[Path]) -> Tuple[bool, str]:
    try:
        for p in py_files:
            py_compile.compile(str(p), doraise=True)
        return True, f"compiled={len(py_files)}"
    except Exception as exc:
        return False, str(exc)


def check_brand_config_resolve() -> Tuple[bool, str]:
    try:
        sys.path.insert(0, str(ROOT))
        from shared.provider_profiles import load_brand_config

        cfg = load_brand_config()
        resolved_models = cfg.get("_resolved_active_models", {})
        resolved_profiles = cfg.get("_resolved_provider_selections", {})
        return True, f"active_models={resolved_models}; provider_selections={resolved_profiles}"
    except Exception as exc:
        return False, str(exc)


def _parse_active_model_entry(value: object) -> Tuple[str, str]:
    if value is None:
        return "", ""

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return "", ""
        if text.lower() == "none":
            return "none", ""
        if ":" in text:
            provider, model = text.split(":", 1)
            return provider.strip(), model.strip()
        return text, ""

    if isinstance(value, dict):
        provider = str(value.get("provider", "")).strip()
        model = str(value.get("model", "")).strip()
        return provider, model

    raise ValueError("active_models entries must be string or mapping")


def check_provider_links() -> Tuple[bool, str]:
    try:
        raw = yaml.safe_load((ROOT / "shared" / "brand_config.yml").read_text(encoding="utf-8"))
        active_raw = raw.get("active_models", {})
        if active_raw and not isinstance(active_raw, dict):
            return False, "active_models must be a mapping"

        active = {
            "copy": ("", ""),
            "image": ("", ""),
            "video": ("", ""),
        }
        if isinstance(active_raw, dict):
            for channel in active:
                if channel in active_raw:
                    active[channel] = _parse_active_model_entry(active_raw.get(channel))

        llm_provider, _ = active["copy"]
        if llm_provider and llm_provider != "none":
            valid_llm_providers = {"openai", "claude", "gemini", "ollama", "openai-compatible"}
            if llm_provider not in valid_llm_providers:
                return False, f"unknown active_models.copy provider: {llm_provider}"

        image_provider, _ = active["image"]
        if image_provider and image_provider != "none" and image_provider not in raw.get("image_generation", {}):
            return False, f"unknown active_models.image provider: {image_provider}"

        video_provider, _ = active["video"]
        if video_provider and video_provider != "none" and video_provider not in raw.get("video_generation", {}):
            return False, f"unknown active_models.video provider: {video_provider}"

        sels = raw.get("provider_selections", {})
        llm = sels.get("llm") if "copy" not in active_raw else None
        image = sels.get("image") if "image" not in active_raw else None
        video = sels.get("video") if "video" not in active_raw else None

        if llm and llm not in raw.get("llm_profiles", {}):
            return False, f"unknown llm profile: {llm}"
        if image and image not in raw.get("image_profiles", {}):
            return False, f"unknown image profile: {image}"
        if video and video != "none" and video not in raw.get("video_profiles", {}):
            return False, f"unknown video profile: {video}"

        return True, (
            f"active_copy={active['copy']}, active_image={active['image']}, active_video={active['video']}, "
            f"fallback_llm={llm}, fallback_image={image}, fallback_video={video}"
        )
    except Exception as exc:
        return False, str(exc)


def check_env_coverage(py_files: List[Path]) -> Tuple[bool, str]:
    try:
        env_pattern = re.compile(r'os\.getenv\("([A-Z0-9_]+)"')
        env_used = set()
        for p in py_files:
            txt = p.read_text(encoding="utf-8", errors="ignore")
            env_used.update(env_pattern.findall(txt))

        env_text = (ROOT / ".env.example").read_text(encoding="utf-8", errors="ignore")
        env_defined = set(re.findall(r'^([A-Z][A-Z0-9_]+)\s*=.*$', env_text, flags=re.MULTILINE))

        missing = sorted(v for v in env_used if v not in env_defined and v not in {"APPDATA"})
        if missing:
            return False, "missing in .env.example: " + ", ".join(missing)

        return True, f"env_used={len(env_used)}, env_defined={len(env_defined)}"
    except Exception as exc:
        return False, str(exc)


def check_marketer_heartbeat() -> Tuple[bool, str]:
    try:
        hb_path = ROOT / "agents" / "marketer" / "HEARTBEAT.md"
        hb = hb_path.read_text(encoding="utf-8", errors="ignore").strip()
        if hb in {"", "# HEARTBEAT.md"}:
            return True, "passive"
        return False, "non-passive content detected"
    except Exception as exc:
        return False, str(exc)


def check_required_files() -> Tuple[bool, str]:
    required = [
        ROOT / "base" / "AGENTS.md",
        ROOT / "base" / "IDENTITY.md",
        ROOT / "base" / "SOUL.md",
        ROOT / "skills" / "telegram_hitl.py",
        ROOT / "shared" / "telegram_gateway.py",
        ROOT / "shared" / "llm_provider.py",
        ROOT / "shared" / "brand_config.yml",
    ]
    missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
    if missing:
        return False, "missing: " + ", ".join(missing)
    return True, f"present={len(required)}"


def main() -> int:
    checks = []
    py_files = collect_python_files()

    checks.append(("compile",) + check_compile(py_files))
    checks.append(("brand_config_resolve",) + check_brand_config_resolve())
    checks.append(("provider_links",) + check_provider_links())
    checks.append(("env_coverage",) + check_env_coverage(py_files))
    checks.append(("marketer_heartbeat",) + check_marketer_heartbeat())
    checks.append(("required_files",) + check_required_files())

    failures = 0
    for name, status, detail in checks:
        marker = "OK" if status else "FAIL"
        print(f"[{marker}] {name}: {detail}")
        if not status:
            failures += 1

    print(f"\nSUMMARY: total={len(checks)} failed={failures}")
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
