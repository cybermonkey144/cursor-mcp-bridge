"""Install bundled Claude Code agent definitions into the user's Claude config."""

import argparse
import sys
from importlib.resources import files
from pathlib import Path


def _confirm_overwrite(path: Path) -> bool:
    try:
        reply = input(f"{path} exists. Overwrite? [y/N]: ").strip().lower()
    except EOFError:
        return False
    return reply == "y"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install bundled Claude Code agent definitions."
    )
    parser.add_argument(
        "--project",
        action="store_true",
        help="Install to ./.claude/agents/ instead of ~/.claude/agents/.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files without prompting.",
    )
    args = parser.parse_args()

    target_dir = (
        Path.cwd() / ".claude" / "agents"
        if args.project
        else Path.home() / ".claude" / "agents"
    )
    target_dir.mkdir(parents=True, exist_ok=True)

    package_root = files("claude_agent_install")
    md_resources = [r for r in package_root.iterdir() if r.name.endswith(".md")]

    if not md_resources:
        print("No agent .md files are bundled in this package.", file=sys.stderr)
        return 1

    installed = 0
    skipped = 0
    for resource in md_resources:
        dest = target_dir / resource.name
        if dest.exists() and not args.force:
            if not _confirm_overwrite(dest):
                print(f"Skipped: {dest}")
                skipped += 1
                continue
        dest.write_text(resource.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Installed: {dest}")
        installed += 1

    print(f"\nDone — {installed} installed, {skipped} skipped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
