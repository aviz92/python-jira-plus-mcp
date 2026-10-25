# python-jira-plus-mcp

An MCP server that lets Claude, and any other MCP client, work with Jira Cloud and Jira Data Center:
search and read issues, then optionally create, update, comment, transition, link and delete them.

It is a thin layer over [python-jira-plus](https://github.com/aviz92/python-jira-plus), which does the Jira work
(validation, pagination, error handling). This package only defines the tools and shapes their results for a model.

## Requirements

- [uv](https://docs.astral.sh/uv/) (it provides `uvx`, and installs Python 3.12+ if needed)
- git, to install straight from GitHub
- A Jira account with an API token (Cloud) or a personal access token (Data Center)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # once, if uv is not installed
```

## Quick start

### Claude Desktop

Add the server to `claude_desktop_config.json`, then restart the app:

```json
{
  "mcpServers": {
    "jira": {
      "command": "/Users/you/.local/bin/uvx",
      "args": [
        "--from", "git+https://github.com/aviz92/python-jira-plus-mcp@main",
        "python-jira-plus-mcp"
      ],
      "env": {
        "JIRA_BASE_URL": "your-site.atlassian.net",
        "JIRA_USER_NAME": "you@example.com",
        "JIRA_TOKEN": "your-api-token"
      }
    }
  }
}
```

- Use the full path to `uvx` (`which uvx` prints it). Claude Desktop does not load your shell's `PATH`.
- With `@main`, every restart of the app picks up the latest commit on `main`. To stay on one version,
  pin a tag instead, e.g. `@v0.1.0`.
- The token lives only in this local file. Never commit it.

### Claude Code

```bash
claude mcp add jira \
  -e JIRA_BASE_URL=your-site.atlassian.net \
  -e JIRA_USER_NAME=you@example.com \
  -e JIRA_TOKEN=your-api-token \
  -- uvx --from git+https://github.com/aviz92/python-jira-plus-mcp@main python-jira-plus-mcp
```

The server starts **read-only**. To let the model change issues, see [Enabling writes](#enabling-writes).

## Authentication

| Jira | Settings |
|---|---|
| Cloud | `JIRA_USER_NAME` = your email, `JIRA_TOKEN` = an [API token](https://id.atlassian.com/manage-profile/security/api-tokens) |
| Data Center, personal access token | `JIRA_DEPLOYMENT=on_premise`, `JIRA_TOKEN` = the token (no username needed) |
| Data Center, username and password/token | `JIRA_DEPLOYMENT=on_premise`, `JIRA_SSO=true`, `JIRA_USER_NAME`, `JIRA_TOKEN` |

`JIRA_BASE_URL` may include the scheme; `https://` is assumed when it doesn't.

## Configuration

All settings are environment variables (or a `.env` file in the working directory; see `env.template`).

| Variable | Default | Meaning |
|---|---|---|
| `JIRA_BASE_URL` | | Jira site, e.g. `your-site.atlassian.net` |
| `JIRA_USER_NAME` | | Email (Cloud) or username (Data Center with `JIRA_SSO=true`) |
| `JIRA_TOKEN` | | API token or personal access token |
| `JIRA_DEPLOYMENT` | `cloud` | `cloud` or `on_premise` |
| `JIRA_SSO` | `false` | Data Center: authenticate with username and token instead of a personal access token |
| `JIRA_VERIFY_SSL` | `true` | Verify the server's TLS certificate |
| `JIRA_MCP_READ_ONLY` | `true` | When `true`, write tools are not registered at all |
| `JIRA_MCP_ENABLE_DELETE` | `false` | Register `jira_delete_issue` (also needs `JIRA_MCP_READ_ONLY=false`) |
| `JIRA_MCP_MAX_RESULTS` | `100` | Upper bound for a search's `limit` |
| `JIRA_MCP_TRANSPORT` | `stdio` | `stdio` or `streamable-http` |
| `JIRA_MCP_HOST` | `127.0.0.1` | HTTP transport only |
| `JIRA_MCP_PORT` | `8000` | HTTP transport only |

## Tools

| Tool | Available | What it does |
|---|---|---|
| `jira_search_issues` | always | Search with JQL; returns compact summaries and `truncated` when more matched than `limit` |
| `jira_get_issue` | always | One issue by key, with its core fields |
| `jira_get_create_fields` | always | The fields for creating an issue in a project and issue type, required first, with `has_allowed_values` |
| `jira_get_allowed_values` | always | All allowed values of one field |
| `jira_get_link_types` | always | Link types with the wording of each direction |
| `jira_find_user` | always, Cloud only | Find a user by name or email; returns the `accountId` needed to assign issues |
| `jira_get_transitions` | writes enabled | The transitions currently available for an issue |
| `jira_create_issue` | writes enabled | Create an issue; fields are validated against Jira's create metadata first |
| `jira_update_issue` | writes enabled | Update fields; validated against the issue's edit metadata |
| `jira_add_comment` | writes enabled | Add a comment |
| `jira_transition_issue` | writes enabled | Move an issue through a workflow transition by name, optionally with a comment |
| `jira_link_issues` | writes enabled | Link two issues |
| `jira_delete_issue` | delete enabled | Permanently delete an issue |

Names of issue types, transitions and link types are matched case-insensitively. Invalid values are rejected
with the list of allowed values, so the model can correct itself.

### Enabling writes

Add to the server's `env`:

```json
"JIRA_MCP_READ_ONLY": "false"
```

This registers the six write tools. Deletion has its own switch because it cannot be undone:

```json
"JIRA_MCP_ENABLE_DELETE": "true"
```

## Access and safety

- **The server can do whatever the token's Jira user can do.** To limit the model to certain projects, give it a
  dedicated Jira user whose permissions cover only those projects; Jira then enforces it on every request.
- Read-only by default, and deletion needs a second, explicit switch.
- Issue keys are validated before any request, so a crafted key such as `PROJ-1/../myself` cannot reach another
  Jira endpoint.
- `upload_attachment` is not exposed: a local file path means nothing across the MCP boundary.

## Notes

- **Jira Cloud rejects searches without a restriction.** A query like `ORDER BY created DESC` alone fails with
  *"Unbounded JQL queries are not allowed here"*. Add a condition, e.g. `project = KAN ORDER BY created DESC`.
  Data Center accepts unrestricted queries.
- To create an issue, the model calls `jira_get_create_fields`, then `jira_get_allowed_values` for each field it
  needs that has `has_allowed_values`, then `jira_create_issue`.
- Errors come back as tool errors carrying Jira's own message (e.g. `Jira error 404: Issue does not exist ...`).

## Docker and the HTTP transport (experimental)

```bash
docker build -t python-jira-plus-mcp .
docker run -i --rm -e JIRA_BASE_URL -e JIRA_USER_NAME -e JIRA_TOKEN python-jira-plus-mcp
```

The image runs over stdio by default. `JIRA_MCP_TRANSPORT=streamable-http` serves on
`JIRA_MCP_HOST:JIRA_MCP_PORT` instead; in Docker, set `JIRA_MCP_HOST=0.0.0.0` and publish the port.

**The HTTP transport has no authentication.** Anyone who can reach the port acts with the configured Jira token.
Bind to loopback, or put an authenticating reverse proxy in front.

## Development

```bash
git clone https://github.com/aviz92/python-jira-plus-mcp
cd python-jira-plus-mcp
uv sync --group dev
uv run pytest                                 # unit tests; integration tests are skipped
uv run pre-commit run --files <changed_files>
```

To run a client against your working copy, point it at the checkout:

```json
"command": "/Users/you/.local/bin/uv",
"args": ["--directory", "/path/to/python-jira-plus-mcp", "run", "python-jira-plus-mcp"]
```

### Integration tests

`uv run pytest -m integration` runs against a real Jira, with the `JIRA_*` credentials from the environment or
`.env`. The write tests also need a sandbox project; the issues they create are deleted afterwards:

| Variable | Meaning |
|---|---|
| `JIRA_MCP_TEST_PROJECT` | Sandbox project key |
| `JIRA_MCP_TEST_EDIT_FIELD` | Id of a field on the edit screen but not the create screen (e.g. `customfield_10050`) |
| `JIRA_MCP_TEST_EDIT_VALUE` | A valid value for that field, as JSON (e.g. `"text"` or `{"value": "A"}`) |
| `JIRA_MCP_TEST_ISSUE_TYPE` | Issue type to create (default `Task`) |

## License

MIT
