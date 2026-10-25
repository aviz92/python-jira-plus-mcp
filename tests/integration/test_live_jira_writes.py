"""Write checks against a sandbox Jira project. Run with: uv run pytest -m integration

Needs the JIRA_* credentials used by test_live_jira.py, plus:
    JIRA_MCP_TEST_PROJECT     sandbox project key; issues are created there and deleted afterwards
    JIRA_MCP_TEST_EDIT_FIELD  id of a field on the edit screen but not the create screen (e.g. customfield_10050)
    JIRA_MCP_TEST_EDIT_VALUE  a valid value for that field, as JSON (e.g. "text" or {"value": "A"})
Optional: JIRA_MCP_TEST_ISSUE_TYPE (default Task).
"""

import json
import os
from collections.abc import AsyncIterator
from typing import Any

import pytest
from mcp.server.fastmcp import FastMCP

from jira_plus_mcp.server import create_server
from jira_plus_mcp.settings import Settings

pytestmark = pytest.mark.integration

REQUIRED_ENV = ("JIRA_MCP_TEST_PROJECT", "JIRA_MCP_TEST_EDIT_FIELD", "JIRA_MCP_TEST_EDIT_VALUE")


@pytest.fixture(name="server", scope="module")
def server_fixture() -> FastMCP:
    settings = Settings()
    if not (settings.jira_base_url and settings.jira_token.get_secret_value()):
        pytest.skip("JIRA_BASE_URL / JIRA_TOKEN not set")
    if missing := [name for name in REQUIRED_ENV if not os.getenv(name)]:
        pytest.skip(f"{', '.join(missing)} not set")
    sandbox = settings.model_copy(
        update={
            "jira_mcp_read_only": False,
            "jira_mcp_enable_delete": True,
            "jira_mcp_allowed_projects": [os.environ["JIRA_MCP_TEST_PROJECT"].upper()],
        }
    )
    return create_server(sandbox)


async def call(server: FastMCP, name: str, args: dict[str, Any]) -> Any:
    _, result = await server.call_tool(name, args)
    return result


async def create(server: FastMCP, summary: str) -> str:
    args = {
        "project_key": os.environ["JIRA_MCP_TEST_PROJECT"],
        "summary": summary,
        "description": "Created by python-jira-plus-mcp integration tests; safe to delete.",
        "issue_type": os.getenv("JIRA_MCP_TEST_ISSUE_TYPE", "Task"),
    }
    return (await call(server, "jira_create_issue", args))["key"]


@pytest.fixture(name="issues", scope="module")
async def issues_fixture(server: FastMCP) -> AsyncIterator[tuple[str, str]]:
    first = await create(server, "MCP integration test issue A")
    second = await create(server, "MCP integration test issue B")
    yield first, second
    for key in (first, second):
        await call(server, "jira_delete_issue", {"issue_key": key})


async def test_create_returns_readable_issue(server: FastMCP, issues: tuple[str, str]) -> None:
    detail = await call(server, "jira_get_issue", {"issue_key": issues[0]})
    assert detail["summary"] == "MCP integration test issue A"


async def test_update_accepts_edit_only_field(server: FastMCP, issues: tuple[str, str]) -> None:
    fields = {os.environ["JIRA_MCP_TEST_EDIT_FIELD"]: json.loads(os.environ["JIRA_MCP_TEST_EDIT_VALUE"])}
    result = await call(server, "jira_update_issue", {"issue_key": issues[0], "fields_to_update": fields})
    assert result["ok"] is True


async def test_transition_by_lowercase_name_with_comment(server: FastMCP, issues: tuple[str, str]) -> None:
    if not (transitions := (await call(server, "jira_get_transitions", {"issue_key": issues[0]}))["result"]):
        pytest.skip(f"No transitions available for {issues[0]}")
    name = transitions[0]["name"]
    args = {"issue_key": issues[0], "transition_name": name.lower(), "comment": "transition comment"}
    result = await call(server, "jira_transition_issue", args)
    assert result["ok"] is True
    assert "comment failed" not in result["message"]


async def test_link_issues(server: FastMCP, issues: tuple[str, str]) -> None:
    link_types = (await call(server, "jira_get_link_types", {}))["result"]
    args = {"inward_issue_key": issues[0], "outward_issue_key": issues[1], "link_type": link_types[0]["name"]}
    assert (await call(server, "jira_link_issues", args))["ok"] is True


async def test_add_comment(server: FastMCP, issues: tuple[str, str]) -> None:
    result = await call(server, "jira_add_comment", {"issue_key": issues[1], "comment": "integration comment"})
    assert result["ok"] is True
