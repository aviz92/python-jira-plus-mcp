import re
from collections.abc import Callable
from functools import wraps
from typing import Any

from jira import JIRAError
from mcp.server.fastmcp.exceptions import ToolError

from jira_plus_mcp.settings import Settings

ISSUE_KEY_RE = re.compile(r"[A-Z][A-Z0-9_]*-[1-9][0-9]*")


def validate_issue_key(issue_key: str) -> str:
    """Reject anything that is not a plain issue key before it reaches the allowlist check or a Jira URL path."""
    key = issue_key.strip().upper()
    if not ISSUE_KEY_RE.fullmatch(key):
        raise ToolError(f"Invalid issue key '{issue_key}'. Expected a key like PROJ-123")
    return key


def check_project_allowed(settings: Settings, project_key: str) -> None:
    allowed = settings.jira_mcp_allowed_projects
    if allowed and project_key.upper() not in allowed:
        raise ToolError(f"Project '{project_key}' is not allowed. Allowed projects: {', '.join(allowed)}")


def to_tool_error(err: Exception) -> ToolError:
    """Map library/Jira exceptions to a message the model can act on."""
    if isinstance(err, ToolError):
        return err
    if isinstance(err, JIRAError):
        return ToolError(f"Jira error {err.status_code}: {err.text or err}")
    if isinstance(err, ValueError):  # raised by python-jira-plus validate_fields: "allowed values are ..."
        return ToolError(str(err))
    return ToolError(f"Unexpected error: {type(err).__name__}: {err}")


def tool_errors(func: Callable[..., Any]) -> Callable[..., Any]:
    """Convert any exception raised by a tool into a ToolError."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as err:  # pylint: disable=broad-exception-caught
            raise to_tool_error(err) from err

    return wrapper
