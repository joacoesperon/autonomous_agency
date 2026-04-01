# Tools

This OpenClaw workspace is rooted at `agents/marketer`, but the canonical repo root is `../..`.

Important shared files:
- `../../shared/brand_config.yml`
- `../../shared/provider_profiles.py`
- `../../shared/llm_provider.py`
- `../../shared/image_provider.py`
- `../../shared/video_provider.py`
- `../../shared/telegram_gateway.py`

Important repo tools:
- `../../skills/content_script_generator.py`
- `../../skills/dynamic_prompt_generator.py`
- `../../skills/marketer_runtime.py`
- `../../skills/video_generation.py`
- `../../skills/image_generation.py`
- `../../skills/social_media_publisher.py`
- `../../skills/telegram_hitl.py`
- `../../skills/tavily_search.py`
- `../../skills/video_to_carousel.py`
- `../../skills/video_to_tweet_thread.py`

Mascot and brand assets:
- `../../assets/mascot/`

Execution guidance:
- When running repo scripts manually, prefer `cd ../.. && python3 skills/...` so imports resolve from the repo root.
- If a document references repo-root paths like `shared/...` or `skills/...`, translate them from this workspace as `../../shared/...` and `../../skills/...`.
- The repo owns the Marketer's internal `content_schedule`, queue state, autopublish logic, and media stack.
- The user's own OpenClaw install still controls runtime model selection, bindings, external invocation cadence, and deployment style.

Model/provider routing playbook:
- Session brain model (OpenClaw): selected in OpenClaw per agent session (`/model`, dashboard, or `agents.list[].model`).
- Script and copy model (repo skills): controlled by `content_script_generator` and `dynamic_prompt_generator` via `llm_provider` and `llm_model` args.
- Image provider/model (repo skills): controlled by `image_generation` via `provider`/`model` args or by `../../shared/brand_config.yml -> active_models.image`.
- Video provider (repo skills): controlled by `video_generation` via `provider` arg or by `../../shared/brand_config.yml -> active_models.video`.
- Rule: single-run requests use per-run args; permanent defaults require updating `active_models` in `../../shared/brand_config.yml`.
