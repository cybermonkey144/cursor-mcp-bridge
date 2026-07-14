# cursor-agent-tool

An MCP bridge that lets tools like **Claude Code** harness [Cursor's agent](https://cursor.com/docs/cli) — including its codebase indexing, project-wide context, and tool access — as a delegatable sub-agent.

Cursor's strength is understanding a codebase as a whole: it can pull in semantically-related files, navigate large projects, and reason about how pieces connect. This server exposes that capability through MCP, so a Claude Code session (or any MCP-compatible LLM) can hand off a task — "refactor the auth flow", "explain how X talks to Y" — to a full Cursor agent and get back a structured result with the agent's text, tool calls, and token usage.

The package also ships ready-made **Claude Code subagents** (`cursor-delegator`, `plan-with-cursor`) that already know how to drive these MCP tools. Install them with a single command (see [Install the bundled Claude agents](#install-the-bundled-claude-agents-optional)) and Claude Code can delegate to Cursor with no extra setup.

## Requirements

- [Cursor agent CLI](https://cursor.com/docs/cli) installed and authenticated (`agent login`)
- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## Install

The recommended way is as a Claude Code plugin — it registers the MCP server and both bundled subagents in one step, with no separate Python install:

```
/plugin marketplace add cybermonkey144/cursor-mcp-bridge
/plugin install cursor-agent-tool@cursor-agent-tool
```

Claude Code runs the server via `uvx --from <plugin dir> cursor-agent-mcp`, so it always executes in place from wherever the plugin is cached — no `uv tool install` step, no manual `claude mcp add`.

Verify the Cursor agent itself is authenticated:

```bash
agent status
```

### Manual install (without the plugin system)

Install the package with `uv` and register it with Claude Code yourself:

```bash
uv tool install git+https://github.com/cybermonkey144/cursor-mcp-bridge
claude mcp add cursor-agent -- cursor-agent-mcp
```

## Install the bundled Claude agents (optional, manual-install only)

Plugin installs already get both subagents automatically (see [Install](#install) above). If you used the manual install path instead, the package ships console scripts to place the same two subagent definitions:

- **`cursor-delegator`** — delegates coding tasks to Cursor and reports back.
- **`plan-with-cursor`** — drafts an implementation plan, sends it to Cursor for review, revises until approved.

Install them with:

```bash
claude-agent-install             # → ~/.claude/agents/ (global, default)
claude-agent-install --project   # → ./.claude/agents/ (cwd-local)
claude-agent-install --force     # overwrite existing files without prompting
```

Global installs make the agents available in every Claude Code session; `--project` scopes them to a single repo.

## Install for Antigravity

Two additional commands populate a project-local `.agents/` directory at the repository root, matching the config layout Antigravity reads:

```bash
cursor-agent-mcp-config    # → ./.agents/mcp_config.json (registers the cursor-agent MCP server)
cursor-agent-agents-install # → ./.agents/agents/{agent_name}/agent.json (one per bundled agent)
```

Both accept `--force` to overwrite existing files without prompting. `cursor-agent-mcp-config` merges the `cursor-agent` entry into any existing `mcpServers` map rather than replacing the whole file.

### Running from a source checkout (development)

If you're hacking on the server, skip the `uv tool install` step and point Claude at the venv directly:

```bash
git clone https://github.com/cybermonkey144/cursor-mcp-bridge
cd cursor-mcp-bridge
uv sync
```

```json
{
  "mcpServers": {
    "cursor-agent": {
      "command": "/path/to/cursor-mcp-bridge/.venv/bin/python3",
      "args": ["/path/to/cursor-mcp-bridge/server.py"]
    }
  }
}
```

## Connecting to Cursor IDE

Add to `.cursor/mcp.json` (project) or `~/.cursor/mcp.json` (global):

```json
{
  "mcpServers": {
    "cursor-agent": {
      "command": "/path/to/cursor_agent_tool/.venv/bin/python3",
      "args": ["/path/to/cursor_agent_tool/server.py"]
    }
  }
}
```

## Tools

### One-shot

| Tool | Description |
|------|-------------|
| `run` | Send a prompt, get a response. Full tool access (files, shell, web). |
| `plan` | Read-only analysis — the agent proposes changes but makes none. |
| `ask` | Q&A only, no tools. Fastest and cheapest. |

### Sessions (multi-turn)

| Tool | Description |
|------|-------------|
| `create_session` | Create a persistent session, returns a `session_id`. |
| `send_message` | Send a message to an existing session. Agent remembers prior turns. |
| `list_sessions` | List saved sessions, most recently used first. |
| `delete_session` | Remove a session from local storage. |

### Introspection

| Tool | Description |
|------|-------------|
| `available_models` | List all models available on the Cursor account. |
| `agent_status` | Check authentication status. |

## Common parameters

All tools that call the agent accept:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `workspace` | `str` | server cwd | Absolute path the agent operates in. |
| `model` | `str` | `auto` | Model ID override (see `available_models`). |
| `yolo` | `bool` | `false` | Auto-approve all agent tool calls. |

## Response format

Every tool that invokes the agent returns:

```json
{
  "text": "The agent's response",
  "session_id": "uuid",
  "model": "Auto",
  "tool_calls": [
    { "tool": "read_file", "args": { "path": "/repo/main.py" }, "status": "completed", "result": {} }
  ],
  "usage": { "inputTokens": 1234, "outputTokens": 56, "cacheReadTokens": 789 },
  "duration_ms": 3200,
  "is_error": false
}
```

`tool_calls` shows exactly what the agent did — file reads, shell commands, web fetches — not just the final answer.

## Example usage

**One-shot task:**
```
run("Add error handling to src/api.py", workspace="/home/user/myproject", yolo=true)
```

**Multi-turn session:**
```
sid = create_session(label="api-refactor", workspace="/home/user/myproject")
send_message(sid, "What's the current structure of the API layer?")
send_message(sid, "Now refactor it to use async/await throughout")
```

**Read-only analysis before committing:**
```
plan("How should we migrate the database schema to add user roles?", workspace="/home/user/myproject")
```

## Sessions

Session IDs are UUIDs persisted to `~/.cursor/mcp_sessions.json`. They survive MCP server restarts and can be resumed at any time with `send_message`.

## Default model

`auto` — Cursor selects the best available model. Override per-call with the `model` parameter using any ID from `available_models`.

## Troubleshooting

### MCP server fails to start: "Cannot find the Cursor `agent` binary"

The server resolves the `agent` CLI at startup. If it is not on the PATH that the MCP server inherits (common in non-interactive shells, such as the one Claude Code uses), set the `CURSOR_AGENT_PATH` environment variable to its absolute path.

In your Claude Code MCP config (`~/.claude/settings.json` or project `.claude/settings.json`):

```json
{
  "mcpServers": {
    "cursor-agent": {
      "command": "cursor-agent-mcp",
      "env": {
        "CURSOR_AGENT_PATH": "/home/youruser/.local/bin/agent"
      }
    }
  }
}
```

Find the path with `which agent` in a terminal where Cursor is installed.
