# cursor-agent-tool

An MCP bridge that lets tools like **Claude Code** harness [Cursor's agent](https://cursor.com/docs/cli) — including its codebase indexing, project-wide context, and tool access — as a delegatable sub-agent.

Cursor's strength is understanding a codebase as a whole: it can pull in semantically-related files, navigate large projects, and reason about how pieces connect. This server exposes that capability through MCP, so a Claude Code session (or any MCP-compatible LLM) can hand off a task — "refactor the auth flow", "explain how X talks to Y" — to a full Cursor agent and get back a structured result with the agent's text, tool calls, and token usage.

The package also ships ready-made **Claude Code subagents** (`cursor-delegator`, `plan-with-cursor`) that already know how to drive these MCP tools. Install them with a single command (see [Install the bundled Claude agents](#install-the-bundled-claude-agents-optional)) and Claude Code can delegate to Cursor with no extra setup.

## Requirements

- [Cursor agent CLI](https://cursor.com/docs/cli) installed and authenticated (`agent login`)
- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## Install

Install the package with `uv` and register it with Claude Code:

```bash
uv tool install git+https://github.com/cybermonkey144/cursor-mcp-bridge
claude mcp add cursor-agent -- cursor-agent-mcp
```

That's it. Verify the Cursor agent itself is authenticated:

```bash
agent status
```

## Install the bundled Claude agents (optional)

The package ships two Claude Code subagent definitions that already know how to use these MCP tools:

- **`cursor-delegator`** — delegates coding tasks to Cursor and reports back.
- **`plan-with-cursor`** — drafts an implementation plan, sends it to Cursor for review, revises until approved.

Install them with:

```bash
claude-agent-install             # → ~/.claude/agents/ (global, default)
claude-agent-install --project   # → ./.claude/agents/ (cwd-local)
claude-agent-install --force     # overwrite existing files without prompting
```

Global installs make the agents available in every Claude Code session; `--project` scopes them to a single repo.

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
