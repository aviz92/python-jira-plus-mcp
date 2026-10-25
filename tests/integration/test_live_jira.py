"""Read-only checks against a real Jira. Run with: uv run pytest -m integration

Needs JIRA_BASE_URL, JIRA_USER_NAME, JIRA_TOKEN (and JIRA_DEPLOYMENT / JIRA_SSO as usual), from env or .env.
Optional: JIRA_MCP_ALLOWED_PROJECTS narrows the search. Nothing here writes to Jira.
"""

from typing import Any

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from jira_plus_mcp.server import create_server
from jira_plus_mcp.settings import Deployment, Settings

pytestmark = pytest.mark.integration


@pytest.fixture(name="settings", scope="module")
def settings_fixture() -> Settings:
    settings = Settings()
    if not (settings.jira_base_url and settings.jira_user_name and settings.jira_token.get_secret_value()):
        pytest.skip("JIRA_BASE_URL / JIRA_USER_NAME / JIRA_TOKEN not set")
    return settings


@pytest.fixture(name="server")
def server_fixture(settings: Settings) -> FastMCP:
    return create_server(settings)


async def call(server: FastMCP, name: str, args: dict[str, Any]) -> Any:
    _, result = await server.call_tool(name, args)
    return result


@pytest.fixture(name="issue", scope="module")
async def issue_fixture(settings: Settings) -> dict[str, Any]:
    result = await call(create_server(settings), "jira_search_issues", {"jql": "ORDER BY created DESC", "limit": 1})
    if not result["issues"]:
        pytest.skip("No visible issues to test with")
    return result["issues"][0]


async def test_search_respects_limit(server: FastMCP) -> None:
    result = await call(server, "jira_search_issues", {"jql": "ORDER BY created DESC", "limit": 3})
    assert 0 < result["returned"] <= 3


async def test_get_issue_matches_search_hit(server: FastMCP, issue: dict[str, Any]) -> None:
    detail = await call(server, "jira_get_issue", {"issue_key": issue["key"]})
    assert detail["key"] == issue["key"]
    assert detail["project"] == issue["key"].rsplit("-", 1)[0]
    assert detail["issue_type"]


async def test_get_missing_issue_is_tool_error(server: FastMCP) -> None:
    with pytest.raises(ToolError):
        await call(server, "jira_get_issue", {"issue_key": "ZZZZZ-99999999"})


async def test_invalid_jql_is_tool_error_not_crash(server: FastMCP) -> None:
    with pytest.raises(ToolError):
        await call(server, "jira_search_issues", {"jql": "this is ((not jql"})


async def test_create_fields_include_summary_and_required_first(server: FastMCP, issue: dict[str, Any]) -> None:
    project = issue["key"].rsplit("-", 1)[0]
    fields = (
        await call(server, "jira_get_create_fields", {"project_key": project, "issue_type": issue["issue_type"]})
    )["result"]
    assert "summary" in {f["id"] for f in fields}
    required = [f["required"] for f in fields]
    assert required == sorted(required, reverse=True)


async def test_allowed_values_for_priority_or_clear_error(server: FastMCP, issue: dict[str, Any]) -> None:
    project = issue["key"].rsplit("-", 1)[0]
    args = {"project_key": project, "issue_type": issue["issue_type"], "field_id_or_name": "priority"}
    try:
        values = (await call(server, "jira_get_allowed_values", args))["result"]
    except ToolError as err:
        assert "priority" in str(err).lower()
    else:
        assert isinstance(values, list)


async def test_find_user_cloud_only(settings: Settings, server: FastMCP) -> None:
    if settings.jira_deployment is not Deployment.CLOUD:
        pytest.skip("jira_find_user is Cloud only")
    result = await call(server, "jira_find_user", {"query": settings.jira_user_name})
    assert any("accountId" in user for user in result["result"])


async def test_allowlist_blocks_other_project(settings: Settings, issue: dict[str, Any]) -> None:
    scoped = create_server(settings.model_copy(update={"jira_mcp_allowed_projects": ["NOPE"]}))
    with pytest.raises(ToolError, match="not allowed"):
        await call(scoped, "jira_get_issue", {"issue_key": issue["key"]})
