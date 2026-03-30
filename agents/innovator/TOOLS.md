# Tools

This OpenClaw workspace is rooted at `agents/innovator`, while the canonical repo root is `../..`.

Important shared files:
- `../../SOUL.md`
- `../../shared/brand_config.yml`
- `../../shared/product_inventory.yml`

Important repo paths:
- `../../EA_developer/`
- `../../skills/content_parser.py`
- `../../shared/telegram_gateway.py`

Execution guidance:
- Translate repo-root references like `EA_developer/...` and `shared/...` from this workspace using `../../`.
- When running Python tools manually, prefer `cd ../.. && python3 ...`.
- The user will configure their own OpenClaw runtime/model. This workspace should stay portable and runtime-agnostic.
