from collections.abc import Callable
from functools import partial, wraps
from typing import Any

import anyio.to_thread
from jira import JIRAError
from mcp.server.fastmcp.exceptions import ToolError


def to_tool_error(err: Exception) -> ToolError:
    """Map library/Jira exceptions to a message the model can act on."""
    if isinstance(err, ToolError):
        return err
    if isinstance(err, JIRAError):
        return ToolError(f"Jira error {err.status_code}: {err.text or err}")
    if isinstance(err, ValueError):  # python-jira-plus validation, invalid issue keys, missing credentials
        return ToolError(str(err))
    return ToolError(f"Unexpected error: {type(err).__name__}: {err}")


def tool_errors(func: Callable[..., Any]) -> Callable[..., Any]:
    """Run a blocking tool in a worker thread and convert any exception into a ToolError.

    python-jira-plus is synchronous; FastMCP runs sync tools on the event loop,
    which would stall every client of a streamable-http server.
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await anyio.to_thread.run_sync(partial(func, *args, **kwargs))
        except Exception as err:  # pylint: disable=broad-exception-caught
            raise to_tool_error(err) from err

    return wrapper
