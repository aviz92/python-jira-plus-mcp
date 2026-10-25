from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from python_jira_plus import BASIC_FIELDS, IssueDetail, simplify_issue
from python_jira_plus.jira_base import JiraBase
from python_jira_plus.jira_cloud import JiraCloud

from jira_plus_mcp.errors import tool_errors
from jira_plus_mcp.formatters import cap_create_fields, format_allowed_values
from jira_plus_mcp.models import AllowedValues, FieldMeta, LinkType, SearchResult
from jira_plus_mcp.settings import Deployment, Settings

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True)
DEFAULT_SEARCH_LIMIT = 20


def register_read_tools(mcp: FastMCP, settings: Settings, get_client: Callable[[], JiraBase]) -> None:
    @mcp.tool(name="jira_get_issue", annotations=READ_ONLY)
    @tool_errors
    def jira_get_issue(issue_key: str) -> IssueDetail:
        """Get one Jira issue by key (e.g. PROJ-123) with its core fields."""
        return simplify_issue(get_client().get_issue_by_key(issue_key, specific_fields=BASIC_FIELDS), detail=True)

    @mcp.tool(name="jira_search_issues", annotations=READ_ONLY)
    @tool_errors
    def jira_search_issues(jql: str, limit: int = DEFAULT_SEARCH_LIMIT) -> SearchResult:
        """Search issues with JQL. Returns compact summaries; `truncated` is true if more matched than `limit`."""
        limit = min(max(limit, 1), settings.jira_mcp_max_results)
        # one extra issue tells us whether more matched than `limit`
        found = get_client().get_objects_by_query(
            jql, limit=limit + 1, max_results=limit + 1, specific_fields=BASIC_FIELDS, json_result=True
        )
        issues = [simplify_issue(raw) for raw in found[:limit]]
        # with an allowlist, issues the library filters out can make `truncated` miss further matches
        return SearchResult(issues=issues, returned=len(issues), truncated=len(found) > limit)

    @mcp.tool(name="jira_get_create_fields", annotations=READ_ONLY)
    @tool_errors
    def jira_get_create_fields(project_key: str, issue_type: str) -> list[FieldMeta]:
        """List fields for creating an issue (required first, with allowed values). Call before jira_create_issue."""
        return cap_create_fields(get_client().get_create_fields(project_key, issue_type))

    @mcp.tool(name="jira_get_allowed_values", annotations=READ_ONLY)
    @tool_errors
    def jira_get_allowed_values(project_key: str, issue_type: str, field_id_or_name: str) -> AllowedValues:
        """Get the allowed values of one field for a project and issue type (`truncated` if the list was cut)."""
        return format_allowed_values(get_client().get_allowed_values(project_key, issue_type, field_id_or_name))

    @mcp.tool(name="jira_get_link_types", annotations=READ_ONLY)
    @tool_errors
    def jira_get_link_types() -> list[LinkType]:
        """List link types with their inward/outward wording. Use before jira_link_issues to get the direction right."""
        return [LinkType(**link_type) for link_type in get_client().get_link_types()]

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
