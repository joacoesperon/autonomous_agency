"""
Register Jess Trading agent workspaces with a user's local OpenClaw install.

This script does NOT configure the user's runtime model, bindings, secrets,
or channel setup. It only registers the repo's agent workspaces so the user
can connect them to their own OpenClaw profile.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parent
AGENTS_DIR = ROOT / "agents"
DEFAULT_AGENTS = ["marketer", "innovator", "support", "operator"]


def run_command(command: List[str], capture_output: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=capture_output,
        text=True,
    )


def ensure_openclaw_installed() -> None:
    if shutil.which("openclaw"):
        return
    print("ERROR: `openclaw` command not found. Install OpenClaw first.", file=sys.stderr)
    sys.exit(1)


def list_existing_agents() -> Dict[str, Dict]:
    result = run_command(["openclaw", "agents", "list", "--json"])
    if result.returncode != 0:
        print(result.stderr or result.stdout, file=sys.stderr)
        print("ERROR: failed to list current OpenClaw agents.", file=sys.stderr)
        sys.exit(1)

    try:
        payload = json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        print(f"ERROR: failed to parse `openclaw agents list --json`: {exc}", file=sys.stderr)
        sys.exit(1)

    return {item["id"]: item for item in payload if isinstance(item, dict) and item.get("id")}


def register_agent(agent_name: str, existing: Dict[str, Dict]) -> None:
    workspace = AGENTS_DIR / agent_name
    identity_file = workspace / "IDENTITY.md"

    if not workspace.exists():
        print(f"SKIP {agent_name}: workspace not found at {workspace}")
        return
    if not identity_file.exists():
        print(f"SKIP {agent_name}: missing IDENTITY.md at {identity_file}")
        return

    current = existing.get(agent_name)
    if current is None:
        add_result = run_command(
            [
                "openclaw",
                "agents",
                "add",
                agent_name,
                "--workspace",
                str(workspace),
                "--non-interactive",
            ]
        )
        if add_result.returncode != 0:
            print(add_result.stderr or add_result.stdout, file=sys.stderr)
            print(f"ERROR: failed to register agent `{agent_name}`.", file=sys.stderr)
            sys.exit(1)
        print(f"ADDED {agent_name} -> {workspace}")
    else:
        current_workspace = current.get("workspace")
        if current_workspace and Path(current_workspace).resolve() != workspace.resolve():
            print(
                f"WARN {agent_name}: already exists in OpenClaw with workspace {current_workspace}. "
                f"Expected {workspace}. Leaving it unchanged."
            )
        else:
            print(f"OK   {agent_name} already registered")

    identity_result = run_command(
        [
            "openclaw",
            "agents",
            "set-identity",
            "--agent",
            agent_name,
            "--identity-file",
            str(identity_file),
        ]
    )
    if identity_result.returncode != 0:
        print(identity_result.stderr or identity_result.stdout, file=sys.stderr)
        print(f"ERROR: failed to load identity for `{agent_name}`.", file=sys.stderr)
        sys.exit(1)
    print(f"SYNC {agent_name} identity from {identity_file}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Register repo agents with local OpenClaw")
    parser.add_argument(
        "agents",
        nargs="*",
        default=DEFAULT_AGENTS,
        help="agent ids to register (default: marketer innovator support operator)",
    )
    args = parser.parse_args()

    ensure_openclaw_installed()
    existing = list_existing_agents()

    for agent_name in args.agents:
        register_agent(agent_name, existing)

    print("")
    print("Next steps:")
    print("- Configure your own OpenClaw runtime/model/profile separately.")
    print("- Bind channels if needed: `openclaw agents bind --help`.")
    print("- Inspect installed agents: `openclaw agents list --bindings`.")
    print('- Test one turn locally: `openclaw agent --local --agent marketer --message "status check"`.')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
