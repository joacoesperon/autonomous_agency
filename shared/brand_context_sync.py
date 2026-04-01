"""
Sync brand context from an external document URL into a local markdown file.

Primary use case:
- Keep long-form brand strategy in Google Docs
- Pull latest content before running marketer workflows

Environment variables:
- BRAND_CONTEXT_SOURCE_URL: required (Google Doc share URL or direct export URL)
- BRAND_CONTEXT_OUTPUT_PATH: optional (default: docs/brand_context_live.md)
- BRAND_CONTEXT_YAML_OUTPUT_PATH: optional (default: docs/brand_context_live.yml)
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

import requests
import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "docs" / "brand_context_live.md"
DEFAULT_YAML_OUTPUT = PROJECT_ROOT / "docs" / "brand_context_live.yml"


def _normalize_google_docs_export_url(url: str) -> str:
    """Convert common Google Docs share URL variants to a txt export URL."""
    match = re.search(r"docs\.google\.com/document/d/([a-zA-Z0-9_-]+)", url)
    if not match:
        return url

    doc_id = match.group(1)
    return f"https://docs.google.com/document/d/{doc_id}/export?format=txt"


def _extract_yaml_block(text: str) -> Dict[str, Any] | None:
        """
        Extract first fenced YAML block from text.

        Expected block:
        ```yaml
        brand_voice:
            ...
        visual_identity:
            ...
        ```
        """
        match = re.search(r"```yaml\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
        if not match:
                return None

        raw_yaml = match.group(1).strip()
        if not raw_yaml:
                return None

        parsed = yaml.safe_load(raw_yaml)
        return parsed if isinstance(parsed, dict) else None


def sync_brand_context(
    source_url: str,
    output_path: str | None = None,
    yaml_output_path: str | None = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    if not source_url or len(source_url.strip()) < 10:
        return {"success": False, "message": "source_url is required"}

    normalized_url = _normalize_google_docs_export_url(source_url.strip())
    output_file = Path(output_path) if output_path else DEFAULT_OUTPUT
    yaml_output_file = Path(yaml_output_path) if yaml_output_path else DEFAULT_YAML_OUTPUT
    if not output_file.is_absolute():
        output_file = PROJECT_ROOT / output_file
    if not yaml_output_file.is_absolute():
        yaml_output_file = PROJECT_ROOT / yaml_output_file

    try:
        response = requests.get(normalized_url, timeout=timeout)
        response.raise_for_status()
        body = response.text.strip()
        if len(body) < 50:
            return {
                "success": False,
                "message": "Downloaded content looks too short. Check doc visibility and URL.",
                "source_url": normalized_url,
            }

        output_file.parent.mkdir(parents=True, exist_ok=True)
        generated_at = datetime.now(timezone.utc).isoformat()

        content = (
            "# Live Brand Context Snapshot\n\n"
            f"Source: {normalized_url}\n"
            f"Synced at (UTC): {generated_at}\n\n"
            "---\n\n"
            f"{body}\n"
        )

        output_file.write_text(content, encoding="utf-8")

        yaml_written = False
        yaml_data = _extract_yaml_block(body)
        if isinstance(yaml_data, dict):
            yaml_output_file.parent.mkdir(parents=True, exist_ok=True)
            yaml_output_file.write_text(
                yaml.safe_dump(yaml_data, sort_keys=False, allow_unicode=False),
                encoding="utf-8",
            )
            yaml_written = True

        return {
            "success": True,
            "message": "Brand context synced successfully",
            "source_url": normalized_url,
            "output_path": str(output_file),
            "yaml_output_path": str(yaml_output_file) if yaml_written else None,
            "yaml_extracted": yaml_written,
            "chars": len(body),
        }
    except Exception as exc:
        return {
            "success": False,
            "message": f"Failed to sync brand context: {exc}",
            "source_url": normalized_url,
        }


def sync_from_env() -> Dict[str, Any]:
    source_url = os.getenv("BRAND_CONTEXT_SOURCE_URL", "").strip()
    output_path = os.getenv("BRAND_CONTEXT_OUTPUT_PATH", "").strip() or None
    yaml_output_path = os.getenv("BRAND_CONTEXT_YAML_OUTPUT_PATH", "").strip() or None
    return sync_brand_context(
        source_url=source_url,
        output_path=output_path,
        yaml_output_path=yaml_output_path,
    )


if __name__ == "__main__":
    result = sync_from_env()
    print(result)
