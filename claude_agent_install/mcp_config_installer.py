"""Write the cursor-agent MCP server entry to .agents/mcp_config.json."""

import argparse
import json
import sys
from pathlib import Path

from ._common import confirm_overwrite

SERVER_NAME = "cursor-agent"
SERVER_ENTRY = {"command": "cursor-agent-mcp"}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Register the cursor-agent MCP server in .agents/mcp_config.json."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing cursor-agent entry without prompting.",
    )
    args = parser.parse_args()

    dest = Path.cwd() / ".agents" / "mcp_config.json"
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        config = json.loads(dest.read_text(encoding="utf-8"))
    else:
        config = {}

    servers = config.setdefault("mcpServers", {})

    if SERVER_NAME in servers and servers[SERVER_NAME] != SERVER_ENTRY and not args.force:
        if not confirm_overwrite(dest):
            print(f"Skipped: {dest}")
            return 0

    servers[SERVER_NAME] = SERVER_ENTRY
    dest.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(f"Installed: {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
