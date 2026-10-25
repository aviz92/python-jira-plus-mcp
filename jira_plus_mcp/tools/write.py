from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from jira_plus_mcp.client import get_client
from jira_plus_mcp.errors import check_project_allowed, reject_reserved_fields, tool_errors, validate_issue_key
from jira_plus_mcp.models import Transition, WriteResult
from jira_plus_mcp.settings import Settings
from jira_plus_mcp.tools.read import project_of

WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True)
IDEMPOTENT_WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True)
DESTRUCTIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=True)
VALIDATION_FIELDS = ["project", "issuetype"]


def _require(ok: bool, message: str) -> None:
    """The library reports many failures as False/None (logged only); surface them to the model."""
    if not ok:
        raise ToolError(message)


def guard_issue(settings: Settings, issue_key: str) -> str:
    """Validate the key and enforce the allowlist; returns the normalised key to use for the API call."""
    key = validate_issue_key(issue_key)
    check_project_allowed(settings, project_of(key))
    if settings.jira_mcp_allowed_projects:
        # a moved issue keeps resolving under its old key, so also check where it lives now
        raw = get_client().get_issue_by_key(key, specific_fields=["project"], json_result=True)
        _require(raw is not None, f"Issue '{key}' not found or not accessible")
        check_project_allowed(settings, raw["fields"]["project"]["key"])
    return key


def register_write_tools(mcp: FastMCP, settings: Settings) -> None:
    def guard(issue_key: str) -> str:
        return guard_issue(settings, issue_key)

    @mcp.tool(name="jira_get_transitions", annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    @tool_errors
    def jira_get_transitions(issue_key: str) -> list[Transition]:
        """List the transitions currently available for an issue. Call before jira_transition_issue."""
        issue_key = guard(issue_key)
        return [Transition(id=t["id"], name=t["name"]) for t in get_client().jira_client.transitions(issue_key)]

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
        check_project_allowed(settings, project_key)
        reject_reserved_fields(custom_fields)
        issue = get_client().create_issue(project_key, summary, description, issue_type, assignee, custom_fields)
        _require(issue is not None, "Issue was not created")
        return WriteResult(ok=True, message=f"Created {issue.key}", key=issue.key)

    @mcp.tool(name="jira_update_issue", annotations=IDEMPOTENT_WRITE)
    @tool_errors
    def jira_update_issue(issue_key: str, fields_to_update: dict[str, Any]) -> WriteResult:
        """Update fields of an issue, e.g. {"summary": "new", "labels": ["a"]}."""
        issue_key = guard(issue_key)
        reject_reserved_fields(fields_to_update)
        client = get_client()
        current = client.get_issue_by_key(issue_key, specific_fields=VALIDATION_FIELDS, json_result=True)
        _require(current is not None, f"Issue '{issue_key}' not found or not accessible")
        # update_issue swallows validation errors, so validate here to give the model the "allowed values" message
        client.validate_fields(
            project_key=current["fields"]["project"]["key"],
            issue_type=current["fields"]["issuetype"]["name"],
            fields=fields_to_update,
        )
        _require(client.update_issue(issue_key, fields_to_update) is not None, f"Failed to update {issue_key}")
        return WriteResult(ok=True, message=f"Updated {issue_key}", key=issue_key)

    @mcp.tool(name="jira_add_comment", annotations=WRITE)
    @tool_errors
    def jira_add_comment(issue_key: str, comment: str) -> WriteResult:
        """Add a comment to an issue."""
        issue_key = guard(issue_key)
        get_client().add_comment(issue_key, comment)
        return WriteResult(ok=True, message=f"Commented on {issue_key}", key=issue_key)

    @mcp.tool(name="jira_transition_issue", annotations=IDEMPOTENT_WRITE)
    @tool_errors
    def jira_transition_issue(
        issue_key: str, transition_name: str, comment: str | None = None, fields: dict[str, Any] | None = None
    ) -> WriteResult:
        """Move an issue through a workflow transition by name (see jira_get_transitions)."""
        issue_key = guard(issue_key)
        client = get_client()
        available = [t["name"] for t in client.jira_client.transitions(issue_key)]
        # the library matches names case-sensitively, so pass it the exact name Jira reported
        match = next((n for n in available if n.lower() == transition_name.lower()), None)
        _require(
            match is not None,
            f"Transition '{transition_name}' not available for {issue_key}. Available: {', '.join(available)}",
        )
        _require(client.transition_issue(issue_key, match, fields, comment), f"Transition of {issue_key} failed")
        return WriteResult(ok=True, message=f"{issue_key} -> {match}", key=issue_key)

    @mcp.tool(name="jira_link_issues", annotations=WRITE)
    @tool_errors
    def jira_link_issues(inward_issue_key: str, outward_issue_key: str, link_type: str) -> WriteResult:
        """Link two issues. `inward_issue_key` gets the link type's `inward` wording and `outward_issue_key` its
        `outward` wording; check jira_get_link_types for the direction. `link_type` is matched case-insensitively."""
        inward_issue_key = guard(inward_issue_key)
        outward_issue_key = guard(outward_issue_key)
        client = get_client()
        names = [t.name for t in client.jira_client.issue_link_types()]
        # the library compares link type names case-sensitively, so pass it the exact name Jira reported
        match = next((n for n in names if n.lower() == link_type.lower()), None)
        _require(match is not None, f"Unknown link type '{link_type}'. Available: {', '.join(names)}")
        _require(
            client.create_link(inward_issue_key, match, outward_issue_key),
            f"Failed to link {inward_issue_key} and {outward_issue_key}",
        )
        return WriteResult(ok=True, message=f"Linked {inward_issue_key} and {outward_issue_key} ({match})")

    if settings.jira_mcp_enable_delete:

        @mcp.tool(name="jira_delete_issue", annotations=DESTRUCTIVE)
        @tool_errors
        def jira_delete_issue(issue_key: str) -> WriteResult:
            """Permanently delete an issue. Cannot be undone."""
            issue_key = guard(issue_key)
            _require(get_client().delete_issue(issue_key), f"Failed to delete {issue_key}")
            return WriteResult(ok=True, message=f"Deleted {issue_key}", key=issue_key)
