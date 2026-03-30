# Tools

This OpenClaw workspace is rooted at `agents/support`, while the canonical repo root is `../..`.

Important shared files:
- `../../SOUL.md`
- `../../shared/brand_config.yml`
- `../../shared/approval_queue.yml`

Important repo paths:
- `../../skills/telegram_hitl.py`
- `../../shared/telegram_gateway.py`

Execution guidance:
- Convert repo-root paths like `shared/...` and `skills/...` into `../../shared/...` and `../../skills/...` from this workspace.
- When running Python tools manually, prefer `cd ../.. && python3 ...`.
- Keep support guidance portable for users who will wire their own runtime and channels later.
