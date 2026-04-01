"""
Provider profile resolution for the Jess Trading Marketer stack.

This module lets the repo keep:
- stable fallback defaults in shared/brand_config.yml
- curated selectable profiles for LLM, image, and video
- one resolved config surface consumed by wrappers and skills
"""

from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


CONFIG_PATH = Path(__file__).resolve().parent / "brand_config.yml"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
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


def _load_external_brand_override(base_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Optionally merge brand sections from an external YAML snapshot.

    This enables Drive-first brand voice/visual identity while keeping
    brand_config.yml as resilient local fallback.
    """
    source_cfg = deepcopy(base_config.get("brand_source", {}))

    mode = str(source_cfg.get("mode", "local_only")).strip().lower()
    if mode in {"", "local", "local_only", "off", "disabled"}:
        local_cfg = deepcopy(base_config)
        local_cfg["_brand_source"] = {
            "mode": "local_only",
            "applied": False,
            "reason": "using local brand_config.yml only",
        }
        return local_cfg

    override_path_value = (
        os.getenv("BRAND_CONTEXT_YAML_OUTPUT_PATH", "").strip()
        or str(source_cfg.get("override_yaml_path", "")).strip()
        or "docs/brand_context_live.yml"
    )
    override_path = Path(override_path_value)
    if not override_path.is_absolute():
        override_path = PROJECT_ROOT / override_path

    if not override_path.exists():
        if bool(source_cfg.get("strict", False)):
            raise FileNotFoundError(
                f"brand_source enabled but override file not found: {override_path}"
            )
        base_config["_brand_source"] = {
            "mode": mode,
            "override_yaml_path": str(override_path),
            "applied": False,
            "reason": "override file missing",
        }
        return base_config

    with override_path.open(encoding="utf-8") as handle:
        external = yaml.safe_load(handle) or {}
    if not isinstance(external, dict):
        if bool(source_cfg.get("strict", False)):
            raise ValueError(f"Invalid override YAML (not a mapping): {override_path}")
        base_config["_brand_source"] = {
            "mode": mode,
            "override_yaml_path": str(override_path),
            "applied": False,
            "reason": "invalid override YAML",
        }
        return base_config

    sections = source_cfg.get("override_sections", ["brand_voice", "visual_identity"])
    if not isinstance(sections, list):
        sections = ["brand_voice", "visual_identity"]

    merged = deepcopy(base_config)
    applied_sections = []
    for section in sections:
        if section in external and isinstance(external.get(section), dict):
            current = merged.get(section, {})
            if not isinstance(current, dict):
                current = {}
            merged[section] = _deep_merge(current, external[section])
            applied_sections.append(section)

    merged["_brand_source"] = {
        "mode": mode,
        "override_yaml_path": str(override_path),
        "applied": bool(applied_sections),
        "applied_sections": applied_sections,
    }
    return merged


def load_raw_brand_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"brand_config.yml not found at {CONFIG_PATH}")
    with CONFIG_PATH.open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    return _load_external_brand_override(loaded)


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


def _parse_active_model_entry(entry: Any, channel: str) -> Optional[Dict[str, Optional[str]]]:
    """
    Parse active model selector for one channel.

    Supported formats:
    - "provider:model"
    - "provider"
    - "none"
    - {provider: "...", model: "..."}
    """
    if entry is None:
        return None

    if isinstance(entry, str):
        value = entry.strip()
        if not value:
            return None
        if value.lower() == "none":
            return {"provider": "none", "model": None}
        if ":" in value:
            provider, model = value.split(":", 1)
            provider = provider.strip()
            model = model.strip() or None
            if not provider:
                raise ValueError(f"Invalid active_models.{channel}: missing provider")
            return {"provider": provider, "model": model}
        return {"provider": value, "model": None}

    if isinstance(entry, dict):
        provider = entry.get("provider")
        model = entry.get("model")
        provider_value = str(provider).strip() if provider is not None else None
        model_value = str(model).strip() if model is not None else None
        provider_value = provider_value or None
        model_value = model_value or None

        if model_value and not provider_value:
            raise ValueError(f"Invalid active_models.{channel}: model requires provider")
        if not provider_value:
            return None
        if provider_value.lower() == "none":
            return {"provider": "none", "model": None}
        return {"provider": provider_value, "model": model_value}

    raise ValueError(f"Invalid active_models.{channel}: expected string or mapping")


def _apply_llm_model_override(
    config: Dict[str, Any],
    provider: Optional[str],
    model: Optional[str],
) -> None:
    if not provider or provider == "none":
        return

    llm_defaults = config.get("llm_defaults", {})
    override: Dict[str, Any] = {"provider": provider}
    if model:
        override["model"] = model
    config["llm_defaults"] = _deep_merge(llm_defaults, override)


def _apply_media_model_override(
    config: Dict[str, Any],
    selection_kind: str,
    provider: Optional[str],
    model: Optional[str],
) -> None:
    if not provider or provider == "none":
        return

    target_section = deepcopy(config.get(selection_kind, {}))
    if provider not in target_section:
        raise ValueError(
            f"Unknown provider '{provider}' for {selection_kind} in shared/brand_config.yml"
        )

    target_section["provider"] = provider
    if model:
        provider_defaults = target_section.get(provider, {})
        target_section[provider] = _deep_merge(provider_defaults, {"model": model})
    config[selection_kind] = target_section


def _resolved_media_channel(config: Dict[str, Any], selection_kind: str) -> Dict[str, Optional[str]]:
    section = config.get(selection_kind, {})
    provider = section.get("provider")
    model = None
    if provider and provider in section and isinstance(section.get(provider), dict):
        model = section[provider].get("model")
    return {"provider": provider, "model": model}


def resolve_brand_config(raw_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = deepcopy(raw_config) if raw_config is not None else load_raw_brand_config()
    selections = deepcopy(config.get("provider_selections", {}))
    active_models_raw = deepcopy(config.get("active_models", {}))
    if active_models_raw and not isinstance(active_models_raw, dict):
        raise ValueError("active_models must be a mapping in shared/brand_config.yml")

    active_model_entries: Dict[str, Optional[Dict[str, Optional[str]]]] = {}
    for channel in ("copy", "image", "video"):
        if isinstance(active_models_raw, dict) and channel in active_models_raw:
            active_model_entries[channel] = _parse_active_model_entry(active_models_raw.get(channel), channel)

    active = {
        "llm": selections.get("llm"),
        "image": selections.get("image"),
        "video": selections.get("video"),
    }

    if "copy" not in active_model_entries and active["llm"]:
        _apply_llm_profile(config, active["llm"])
    if "image" not in active_model_entries and active["image"]:
        _apply_media_profile(config, active["image"], "image_generation", "image_profiles")
    if "video" not in active_model_entries and active["video"] and active["video"] != "none":
        _apply_media_profile(config, active["video"], "video_generation", "video_profiles")

    if "copy" in active_model_entries:
        entry = active_model_entries["copy"] or {}
        _apply_llm_model_override(
            config,
            provider=entry.get("provider"),
            model=entry.get("model"),
        )

    if "image" in active_model_entries:
        entry = active_model_entries["image"] or {}
        _apply_media_model_override(
            config,
            selection_kind="image_generation",
            provider=entry.get("provider"),
            model=entry.get("model"),
        )

    if "video" in active_model_entries:
        entry = active_model_entries["video"] or {}
        _apply_media_model_override(
            config,
            selection_kind="video_generation",
            provider=entry.get("provider"),
            model=entry.get("model"),
        )

    resolved_copy = {
        "provider": config.get("llm_defaults", {}).get("provider"),
        "model": config.get("llm_defaults", {}).get("model"),
    }
    if "copy" in active_model_entries and active_model_entries["copy"]:
        resolved_copy = {
            "provider": active_model_entries["copy"].get("provider") or resolved_copy.get("provider"),
            "model": active_model_entries["copy"].get("model") or resolved_copy.get("model"),
        }

    resolved_image = _resolved_media_channel(config, "image_generation")
    if "image" in active_model_entries and active_model_entries["image"]:
        image_entry = active_model_entries["image"]
        if image_entry.get("provider") == "none":
            resolved_image = {"provider": "none", "model": None}
        else:
            resolved_image = {
                "provider": image_entry.get("provider") or resolved_image.get("provider"),
                "model": image_entry.get("model") or resolved_image.get("model"),
            }

    resolved_video = _resolved_media_channel(config, "video_generation")
    if "video" in active_model_entries and active_model_entries["video"]:
        video_entry = active_model_entries["video"]
        if video_entry.get("provider") == "none":
            resolved_video = {"provider": "none", "model": None}
        else:
            resolved_video = {
                "provider": video_entry.get("provider") or resolved_video.get("provider"),
                "model": video_entry.get("model") or resolved_video.get("model"),
            }

    config["_resolved_provider_selections"] = active
    config["_resolved_active_models"] = {
        "copy": resolved_copy,
        "image": resolved_image,
        "video": resolved_video,
    }
    return config


def load_brand_config() -> Dict[str, Any]:
    return resolve_brand_config(load_raw_brand_config())


def get_provider_catalog(raw_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = deepcopy(raw_config) if raw_config is not None else load_raw_brand_config()
    return {
        "active_models": deepcopy(config.get("active_models", {})),
        "selections": deepcopy(config.get("provider_selections", {})),
        "llm_profiles": deepcopy(config.get("llm_profiles", {})),
        "image_profiles": deepcopy(config.get("image_profiles", {})),
        "video_profiles": deepcopy(config.get("video_profiles", {})),
    }
