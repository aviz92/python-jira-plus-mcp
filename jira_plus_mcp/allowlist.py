"""The project allowlist (`JIRA_MCP_ALLOWED_PROJECTS`): which projects the model may touch."""

import re
from typing import Any

from mcp.server.fastmcp.exceptions import ToolError
from python_jira_plus.jira_base import JiraBase

from jira_plus_mcp.settings import Settings

ORDER_BY = re.compile(r"\border\s+by\b", re.IGNORECASE)


def check_project_allowed(settings: Settings, project_key: str) -> None:
    allowed = settings.jira_mcp_allowed_projects
    if allowed and project_key.upper() not in allowed:
        raise ToolError(f"Project '{project_key}' is not allowed. Allowed projects: {', '.join(allowed)}")


def check_key_prefix(settings: Settings, issue_key: str) -> None:
    """Reject a key whose prefix is outside the allowlist, before any request is made."""
    if "-" in issue_key:
        check_project_allowed(settings, issue_key.rsplit("-", 1)[0])


def project_of(raw: dict[str, Any]) -> str:
    return ((raw.get("fields") or {}).get("project") or {}).get("key", "")


def in_allowed_project(settings: Settings, raw: dict[str, Any]) -> bool:
    allowed = settings.jira_mcp_allowed_projects
    return not allowed or project_of(raw).upper() in allowed


def scope_jql(settings: Settings, jql: str) -> str:
    """Restrict a JQL query to the allowed projects, keeping any ORDER BY clause outside the filter.

    The wrapper can be escaped with unbalanced parentheses, so callers also filter the results.
    """
    if not (allowed := settings.jira_mcp_allowed_projects):
        return jql
    parts = ORDER_BY.split(jql, maxsplit=1)
    where = parts[0].strip()
    scoped = f"project in ({', '.join(allowed)})" + (f" AND ({where})" if where else "")
    return f"{scoped} ORDER BY {parts[1].strip()}" if len(parts) > 1 else scoped


def guard_issue(settings: Settings, client: JiraBase, *issue_keys: str) -> None:
    """Check every issue is in an allowed project before acting on it.

    A moved issue keeps resolving under its old key, and an id has no prefix,
    so with an allowlist each issue's current project is fetched and checked too.
    """
    if not settings.jira_mcp_allowed_projects:
        return
    for issue_key in issue_keys:
        check_key_prefix(settings, issue_key)
        check_project_allowed(settings, project_of(client.get_issue_by_key(issue_key, specific_fields=["project"])))
