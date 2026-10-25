# python-jira-plus-mcp

MCP server for Jira (Cloud and Data Center), built on [python-jira-plus](https://github.com/aviz92/python-jira-plus).

## Run

```bash
uvx python-jira-plus-mcp
```

Configure through environment variables (see `env.template`). The server is **read-only by default**:
write tools are not registered unless `JIRA_MCP_READ_ONLY=false`.

## Claude Code / Desktop

```json
{
  "mcpServers": {
    "jira": {
      "command": "uvx",
      "args": ["python-jira-plus-mcp"],
      "env": {
        "JIRA_BASE_URL": "instance.atlassian.net",
        "JIRA_USER_NAME": "you@example.com",
        "JIRA_TOKEN": "..."
      }
    }
  }
}
```

## Tools

Always on: `jira_get_issue`, `jira_search_issues`, `jira_get_create_fields`, `jira_get_allowed_values`, `jira_get_link_types`, `jira_find_user` (Cloud only).

With `JIRA_MCP_READ_ONLY=false`: `jira_get_transitions`, `jira_create_issue`, `jira_update_issue`, `jira_add_comment`, `jira_transition_issue`, `jira_link_issues`.

With `JIRA_MCP_ENABLE_DELETE=true` as well: `jira_delete_issue`.

`upload_attachment` is not exposed: a local file path means nothing across the MCP boundary.

## HTTP transport (experimental)

`JIRA_MCP_TRANSPORT=streamable-http` serves on `JIRA_MCP_HOST:JIRA_MCP_PORT` (default `127.0.0.1:8000`).
In Docker, set `JIRA_MCP_HOST=0.0.0.0` and publish the port.

**There is no authentication.** Anyone who can reach the port acts with the configured Jira token.
Bind to loopback, or put an authenticating reverse proxy in front, and use a token scoped to the projects you allow.

## Development

```bash
uv sync --group dev
uv run pytest
```
