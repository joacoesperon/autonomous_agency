# Tools

This OpenClaw workspace is rooted at `agents/operator`, while the canonical repo root is `../..`.

Important shared files:
- `../../SOUL.md`
- `../../shared/brand_config.yml`
- `../../shared/financial_dashboard.yml`

Important repo paths:
- `../../skills/telegram_hitl.py`
- `../../shared/telegram_gateway.py`

Execution guidance:
- Translate repo-root paths like `shared/...` and `skills/...` into `../../shared/...` and `../../skills/...` from this workspace.
- When running Python tools manually, prefer `cd ../.. && python3 ...`.
- The user's OpenClaw runtime/model/profile remains their responsibility; this workspace should remain repo-centric and portable.
