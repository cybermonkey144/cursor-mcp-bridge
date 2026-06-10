"""Install bundled agent definitions into .agents/agents/{agent_name}/agent.json."""

import argparse
import json
import sys
from importlib.resources import files
from pathlib import Path

from ._common import confirm_overwrite


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install bundled agent definitions into .agents/agents/{agent_name}/agent.json."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files without prompting.",
    )
    args = parser.parse_args()

    target_dir = Path.cwd() / ".agents" / "agents"

    package_root = files("claude_agent_install")
    md_resources = [r for r in package_root.iterdir() if r.name.endswith(".md")]

    if not md_resources:
        print("No agent .md files are bundled in this package.", file=sys.stderr)
        return 1

    installed = 0
    skipped = 0
    for resource in md_resources:
        agent_name = resource.name.removesuffix(".md")
        dest = target_dir / agent_name / "agent.json"
        if dest.exists() and not args.force:
            if not confirm_overwrite(dest):
                print(f"Skipped: {dest}")
                skipped += 1
                continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        agent_json = {
            "name": agent_name,
            "definition": resource.read_text(encoding="utf-8"),
        }
        dest.write_text(json.dumps(agent_json, indent=2) + "\n", encoding="utf-8")
        print(f"Installed: {dest}")
        installed += 1

    print(f"\nDone — {installed} installed, {skipped} skipped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
