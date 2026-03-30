# User

The human using this workspace is installing Jess Trading agents into their own OpenClaw setup.

Assumptions:
- Their OpenClaw runtime model/provider is their choice.
- Their channel bindings, approvals flow, and gateway config are local concerns.
- This repo is responsible for agent behavior, prompts, Python tooling, brand assets, and shared state conventions.

When helping:
- Separate repo-level agent logic from user-specific OpenClaw runtime setup.
- Prefer editing repo files over telling the user to patch their global OpenClaw config unless they explicitly ask.
