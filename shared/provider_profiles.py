"""
Provider profile resolution for the Jess Trading Marketer stack.

This module lets the repo keep:
- stable fallback defaults in shared/brand_config.yml
- curated selectable profiles for LLM, image, and video
- one resolved config surface consumed by wrappers and skills
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


CONFIG_PATH = Path(__file__).resolve().parent / "brand_config.yml"
PROFILE_METADATA_KEYS = {
    "label",
    "description",
    "best_for",
    "status",
    "notes",
    "source_url",
    "as_of",
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def load_raw_brand_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"brand_config.yml not found at {CONFIG_PATH}")
    with CONFIG_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _apply_llm_profile(config: Dict[str, Any], selection_name: str) -> None:
    profiles = config.get("llm_profiles", {})
    profile = profiles.get(selection_name)
    if not profile:
        raise ValueError(f"Unknown llm profile '{selection_name}' in shared/brand_config.yml")

    llm_defaults = config.get("llm_defaults", {})
    override = deepcopy(profile.get("config", {}))
    override["provider"] = profile["provider"]
    config["llm_defaults"] = _deep_merge(llm_defaults, override)


def _apply_media_profile(
    config: Dict[str, Any],
    selection_name: str,
    selection_kind: str,
    config_key: str,
) -> None:
    profiles = config.get(config_key, {})
    profile = profiles.get(selection_name)
    if not profile:
        raise ValueError(f"Unknown {selection_kind} profile '{selection_name}' in shared/brand_config.yml")

    provider = profile["provider"]
    target_section = deepcopy(config.get(selection_kind, {}))
    provider_defaults = target_section.get(provider, {})
    provider_override = deepcopy(profile.get("config", {}))
    target_section["provider"] = provider
    target_section[provider] = _deep_merge(provider_defaults, provider_override)
    config[selection_kind] = target_section


def resolve_brand_config(raw_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = deepcopy(raw_config) if raw_config is not None else load_raw_brand_config()
    selections = deepcopy(config.get("provider_selections", {}))

    active = {
        "llm": selections.get("llm"),
        "image": selections.get("image"),
        "video": selections.get("video"),
    }

    if active["llm"]:
        _apply_llm_profile(config, active["llm"])
    if active["image"]:
        _apply_media_profile(config, active["image"], "image_generation", "image_profiles")
    if active["video"]:
        _apply_media_profile(config, active["video"], "video_generation", "video_profiles")

    config["_resolved_provider_selections"] = active
    return config


def load_brand_config() -> Dict[str, Any]:
    return resolve_brand_config(load_raw_brand_config())


def get_provider_catalog(raw_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = deepcopy(raw_config) if raw_config is not None else load_raw_brand_config()
    return {
        "selections": deepcopy(config.get("provider_selections", {})),
        "llm_profiles": deepcopy(config.get("llm_profiles", {})),
        "image_profiles": deepcopy(config.get("image_profiles", {})),
        "video_profiles": deepcopy(config.get("video_profiles", {})),
    }
