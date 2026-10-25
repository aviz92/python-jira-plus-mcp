import threading
from unittest.mock import MagicMock, patch

import pytest
from jira import JIRAError
from mcp.server.fastmcp.exceptions import ToolError
from python_jira_plus import ProjectNotAllowedError

from jira_plus_mcp.__main__ import main
from jira_plus_mcp.errors import to_tool_error, tool_errors
from jira_plus_mcp.settings import Settings, Transport


def test_jira_error_keeps_status_and_text() -> None:
    err = to_tool_error(JIRAError(status_code=404, text="Issue does not exist"))
    assert "404" in str(err)
    assert "Issue does not exist" in str(err)


def test_unexpected_error_names_type() -> None:
    assert "KeyError" in str(to_tool_error(KeyError("x")))


def test_tool_error_passes_through_unchanged() -> None:
    original = ToolError("keep me")
    assert to_tool_error(original) is original


async def test_tool_errors_wraps_exceptions() -> None:
    @tool_errors
    def boom() -> None:
        raise ValueError("allowed values are [a]")

    with pytest.raises(ToolError, match="allowed values are"):
        await boom()


def test_project_not_allowed_keeps_library_message() -> None:
    err = to_tool_error(ProjectNotAllowedError("Project 'NO' is not allowed. Allowed projects: ['OK']"))
    assert str(err) == "Project 'NO' is not allowed. Allowed projects: ['OK']"


@pytest.mark.parametrize("transport", list(Transport))
def test_main_runs_server_with_configured_transport(transport: Transport) -> None:
    server = MagicMock()
    with (
        patch("jira_plus_mcp.__main__.create_server", return_value=server),
        patch("jira_plus_mcp.__main__.get_settings", return_value=Settings(jira_mcp_transport=transport)),
    ):
        main()
    server.run.assert_called_once_with(transport=transport.value)


async def test_tool_errors_runs_in_worker_thread() -> None:
    @tool_errors
    def which_thread() -> int:
        return threading.get_ident()

    assert await which_thread() != threading.get_ident()
