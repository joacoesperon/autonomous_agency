# Marketer Model Routing - Practical Guide

## Why this exists

There are two separate model layers in this repo:

1. OpenClaw session model (the agent brain)
2. Python skill providers (script/image/video tools)

If you only change one layer, the other can still fail or use expensive defaults.

## Layer 1: OpenClaw session model (agent brain)

This is configured in OpenClaw itself (dashboard, slash commands, or openclaw.json).

Use this for:
- reasoning quality
- planning quality
- tool calling reliability

Examples:
- Shees: fast/cheap model
- Marketer: stronger model

## Layer 2: Skill providers (script, image, video)

These are controlled by:
- shared/brand_config.yml (simple default selector in `active_models`)
- per-run override arguments in skills

Primary default keys:
- active_models.copy
- active_models.image
- active_models.video

Fallback/advanced keys:
- provider_selections.llm
- provider_selections.image
- provider_selections.video

## Recommended operating mode

### Single-run request (temporary)

If user says:
"Generate one content block using model X for script, flux for image, and d-id for video"

Do NOT rewrite defaults.
Use per-run overrides:
- content_script_generator.execute(..., llm_provider=..., llm_model=...)
- dynamic_prompt_generator.execute(..., llm_provider=..., llm_model=...)
- image_generation.execute(..., provider=..., model=...)
- video_generation.execute(..., provider=...)

### Persistent request (new default)

If user says:
"From now on, use this stack by default"

Then update only:
- shared/brand_config.yml -> active_models

Do not rewrite unrelated brand sections.

## Ollama notes

For Python skills to use local OpenAI-compatible endpoints:
- set OPENAI_BASE_URL to local endpoint
- set OPENAI_MODEL to local model id
- set OPENAI_API_KEY to a placeholder (for example: ollama)

If script generation still fails, the issue is usually tool-calling quality of the selected local model, not routing.

## Fast troubleshooting checklist

1. Verify OpenClaw model in current session
2. Verify env keys exist (especially REPLICATE_API_TOKEN and D_ID_API_KEY)
3. Verify active_models uses valid provider:model values
4. Run one skill directly to isolate failures
5. Only then test full marketer workflow
