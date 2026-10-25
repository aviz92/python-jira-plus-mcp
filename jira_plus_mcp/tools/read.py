import re
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from python_jira_plus import BASIC_FIELDS
from python_jira_plus.jira_cloud import JiraCloud

from jira_plus_mcp.client import get_client
from jira_plus_mcp.errors import check_project_allowed, tool_errors, validate_issue_key
from jira_plus_mcp.formatters import format_detail, format_fields_metadata, format_summary
from jira_plus_mcp.models import FieldMeta, IssueDetail, SearchResult
from jira_plus_mcp.search import search_page
from jira_plus_mcp.settings import Deployment, Settings

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True)
DEFAULT_SEARCH_LIMIT = 20
ORDER_BY = re.compile(r"\border\s+by\b", re.IGNORECASE)


def scope_jql(settings: Settings, jql: str) -> str:
    """Restrict a JQL query to the allowed projects, keeping any ORDER BY clause outside the filter."""
    if not (allowed := settings.jira_mcp_allowed_projects):
        return jql
    parts = ORDER_BY.split(jql, maxsplit=1)
    where = parts[0].strip()
    scoped = f"project in ({', '.join(allowed)})" + (f" AND ({where})" if where else "")
    return f"{scoped} ORDER BY {parts[1].strip()}" if len(parts) > 1 else scoped


def _in_allowed_project(settings: Settings, raw: dict[str, Any]) -> bool:
    """Enforce the allowlist on the server's own output; the JQL wrapper alone can be escaped with parentheses."""
    allowed = settings.jira_mcp_allowed_projects
    project = ((raw.get("fields") or {}).get("project") or {}).get("key", "")
    return not allowed or project.upper() in allowed


def project_of(key: str) -> str:
    return key.rsplit("-", 1)[0]


def register_read_tools(mcp: FastMCP, settings: Settings) -> None:
    @mcp.tool(name="jira_get_issue", annotations=READ_ONLY)
    @tool_errors
    def jira_get_issue(issue_key: str) -> IssueDetail:
        """Get one Jira issue by key (e.g. PROJ-123) with its core fields."""
        issue_key = validate_issue_key(issue_key)
        check_project_allowed(settings, project_of(issue_key))
        raw = get_client().get_issue_by_key(key=issue_key, specific_fields=BASIC_FIELDS, json_result=True)
        if raw is None:
            raise ToolError(f"Issue '{issue_key}' not found or not accessible")
        if not _in_allowed_project(settings, raw):
            raise ToolError(f"Issue '{issue_key}' is not in an allowed project")
        return format_detail(raw)

    @mcp.tool(name="jira_search_issues", annotations=READ_ONLY)
    @tool_errors
    def jira_search_issues(jql: str, limit: int = DEFAULT_SEARCH_LIMIT) -> SearchResult:
        """Search issues with JQL. Returns compact summaries; `truncated` is true if more matched than `limit`."""
        limit = min(max(limit, 1), settings.jira_mcp_max_results)
        found = search_page(settings, scope_jql(settings, jql), BASIC_FIELDS, limit)
        visible = [raw for raw in found if _in_allowed_project(settings, raw)]
        issues = [format_summary(raw) for raw in visible[:limit]]
        return SearchResult(issues=issues, returned=len(issues), truncated=len(visible) > limit)

    @mcp.tool(name="jira_get_create_fields", annotations=READ_ONLY)
    @tool_errors
    def jira_get_create_fields(project_key: str, issue_type: str) -> list[FieldMeta]:
        """List fields for creating an issue (required first, with allowed values). Call before jira_create_issue."""
        check_project_allowed(settings, project_key)
        return format_fields_metadata(get_client().get_project_fields_metadata(project_key, issue_type))

    @mcp.tool(name="jira_get_allowed_values", annotations=READ_ONLY)
    @tool_errors
    def jira_get_allowed_values(project_key: str, issue_type: str, field_id_or_name: str) -> list[Any]:
        """Get the allowed values of one field for a project and issue type."""
        check_project_allowed(settings, project_key)
        return get_client().get_allowed_values(project_key, issue_type, field_id_or_name) or []

    if settings.jira_deployment is Deployment.CLOUD:

        @mcp.tool(name="jira_find_user", annotations=READ_ONLY)
        @tool_errors
        def jira_find_user(query: str) -> list[dict[str, Any]]:
            """Find Cloud users by email or name. Returns accountId, needed to assign issues."""
            client = get_client()
            assert isinstance(client, JiraCloud)
            users = client.get_account_data(user_mail=query)
            return [
                {"accountId": u["accountId"], "displayName": u.get("displayName"), "active": u.get("active")}
                for u in users
            ]
