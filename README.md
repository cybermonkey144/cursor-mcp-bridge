# cursor-agent-tool

MCP server that exposes [Cursor's agent CLI](https://cursor.com/docs/cli) as tools, letting any MCP-compatible LLM delegate tasks to a full Cursor agent with filesystem, shell, and web access.

## Requirements

- [Cursor agent CLI](https://cursor.com/docs/cli) installed and authenticated (`agent login`)
- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## Setup

```bash
git clone <repo>
cd cursor_agent_tool
uv sync
```

Verify the agent is authenticated:

```bash
agent status
```

## Connecting to Claude Code

Add to `~/.claude/mcp.json`:

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
