from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from python_jira_plus.jira_base import JiraBase

from jira_plus_mcp.errors import to_tool_error, tool_errors
from jira_plus_mcp.models import Transition, WriteResult
from jira_plus_mcp.settings import Settings

WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True)
IDEMPOTENT_WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True)
DESTRUCTIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=True)


def comment_after_transition(client: JiraBase, issue_key: str, comment: str | None) -> str:
    """Add the comment; on failure return a note for the message, so the model doesn't retry the transition."""
    try:
        if comment:
            client.add_comment(issue_key, comment)
    except Exception as err:  # pylint: disable=broad-exception-caught
        return f", but the comment failed: {to_tool_error(err)}"
    return ""


def register_write_tools(mcp: FastMCP, settings: Settings, get_client: Callable[[], JiraBase]) -> None:
    @mcp.tool(name="jira_get_transitions", annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    @tool_errors
    def jira_get_transitions(issue_key: str) -> list[Transition]:
        """List the transitions currently available for an issue. Call before jira_transition_issue."""
        return [Transition(**transition) for transition in get_client().get_transitions(issue_key)]

    @mcp.tool(name="jira_create_issue", annotations=WRITE)
    @tool_errors
    def jira_create_issue(
        project_key: str,
        summary: str,
        description: str,
        issue_type: str,
        assignee: str | None = None,
        custom_fields: dict[str, Any] | None = None,
    ) -> WriteResult:
        """Create an issue. `assignee` is an accountId on Cloud (see jira_find_user).
        Use jira_get_create_fields first."""
        issue = get_client().create_issue(project_key, summary, description, issue_type, assignee, custom_fields)
        return WriteResult(ok=True, message=f"Created {issue.key}", key=issue.key)

    @mcp.tool(name="jira_update_issue", annotations=IDEMPOTENT_WRITE)
    @tool_errors
    def jira_update_issue(issue_key: str, fields_to_update: dict[str, Any]) -> WriteResult:
        """Update fields of an issue, e.g. {"summary": "new", "labels": ["a"]}."""
        get_client().update_issue(issue_key, fields_to_update)
        return WriteResult(ok=True, message=f"Updated {issue_key}", key=issue_key)

    @mcp.tool(name="jira_add_comment", annotations=WRITE)
    @tool_errors
    def jira_add_comment(issue_key: str, comment: str) -> WriteResult:
        """Add a comment to an issue."""
        get_client().add_comment(issue_key, comment)
        return WriteResult(ok=True, message=f"Commented on {issue_key}", key=issue_key)

    @mcp.tool(name="jira_transition_issue", annotations=IDEMPOTENT_WRITE)
    @tool_errors
    def jira_transition_issue(
        issue_key: str, transition_name: str, comment: str | None = None, fields: dict[str, Any] | None = None
    ) -> WriteResult:
        """Move an issue through a workflow transition by name (see jira_get_transitions)."""
        client = get_client()
        # comment separately: a failed comment must not report a transition that happened as failed
        client.transition_issue(issue_key, transition_name, fields=fields, comment=None)
        note = comment_after_transition(client, issue_key, comment)
        return WriteResult(ok=True, message=f"Transitioned {issue_key} to {transition_name}{note}", key=issue_key)

    @mcp.tool(name="jira_link_issues", annotations=WRITE)
    @tool_errors
    def jira_link_issues(inward_issue_key: str, outward_issue_key: str, link_type: str) -> WriteResult:
        """Link two issues. `inward_issue_key` gets the link type's `inward` wording and `outward_issue_key` its
        `outward` wording; check jira_get_link_types for the direction. `link_type` is matched case-insensitively."""
        get_client().create_link(inward_issue_key, link_type, outward_issue_key)
        return WriteResult(ok=True, message=f"Linked {inward_issue_key} and {outward_issue_key} ({link_type})")

    if settings.jira_mcp_enable_delete:

        @mcp.tool(name="jira_delete_issue", annotations=DESTRUCTIVE)
        @tool_errors
        def jira_delete_issue(issue_key: str) -> WriteResult:
            """Permanently delete an issue. Cannot be undone."""
            get_client().delete_issue(issue_key)
            return WriteResult(ok=True, message=f"Deleted {issue_key}", key=issue_key)
