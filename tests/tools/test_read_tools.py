from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from jira_plus_mcp.server import create_server
from jira_plus_mcp.settings import Deployment, Settings

RAW = {"key": "PROJ-1", "fields": {"summary": "s", "status": {"name": "Open"}, "project": {"key": "PROJ"}}}


@pytest.fixture(name="client")
def client_fixture() -> Iterator[MagicMock]:
    client = MagicMock()
    with (
        patch("jira_plus_mcp.search.get_client", return_value=client),
        patch("jira_plus_mcp.tools.read.get_client", return_value=client),
    ):
        yield client


async def test_tool_names_prefixed_and_read_only() -> None:
    tools = await create_server(Settings()).list_tools()
    assert {t.name for t in tools} == {
        "jira_get_issue",
        "jira_search_issues",
        "jira_get_create_fields",
        "jira_get_allowed_values",
        "jira_find_user",
    }
    assert all(t.annotations.readOnlyHint for t in tools)


async def test_find_user_not_registered_on_premise() -> None:
    tools = await create_server(Settings(jira_deployment=Deployment.ON_PREMISE)).list_tools()
    assert "jira_find_user" not in {t.name for t in tools}


async def test_get_issue(client: MagicMock) -> None:
    client.get_issue_by_key.return_value = RAW
    _, result = await create_server(Settings()).call_tool("jira_get_issue", {"issue_key": "PROJ-1"})
    assert result["key"] == "PROJ-1"
    assert result["status"] == "Open"


async def test_get_issue_none_becomes_tool_error(client: MagicMock) -> None:
    client.get_issue_by_key.return_value = None
    with pytest.raises(ToolError, match="not found"):
        await create_server(Settings()).call_tool("jira_get_issue", {"issue_key": "PROJ-9"})


async def test_disallowed_project_rejected(client: MagicMock) -> None:
    server = create_server(Settings(jira_mcp_allowed_projects="OK"))
    with pytest.raises(ToolError, match="not allowed"):
        await server.call_tool("jira_get_issue", {"issue_key": "NO-1"})
    client.get_issue_by_key.assert_not_called()


async def test_search_truncates_and_flags(client: MagicMock) -> None:
    client.jira_client.enhanced_search_issues.return_value = {"issues": [RAW, RAW, RAW]}
    _, result = await create_server(Settings()).call_tool("jira_search_issues", {"jql": "x", "limit": 2})
    assert result["returned"] == 2
    assert result["truncated"] is True


async def test_validation_error_passes_through(client: MagicMock) -> None:
    client.get_allowed_values.side_effect = ValueError("Field 'x' not found; allowed values are [a, b]")
    with pytest.raises(ToolError, match="allowed values are"):
        await create_server(Settings()).call_tool(
            "jira_get_allowed_values", {"project_key": "P", "issue_type": "Bug", "field_id_or_name": "x"}
        )


async def test_search_post_filters_jql_escape(client: MagicMock) -> None:
    other = {"key": "SEC-1", "fields": {"project": {"key": "SEC"}}}
    client.jira_client.enhanced_search_issues.return_value = {"issues": [RAW, other]}
    server = create_server(Settings(jira_mcp_allowed_projects="PROJ"))
    _, result = await server.call_tool("jira_search_issues", {"jql": "x) OR (project = SEC"})
    assert [i["key"] for i in result["issues"]] == ["PROJ-1"]


async def test_get_issue_moved_to_disallowed_project_rejected(client: MagicMock) -> None:
    client.get_issue_by_key.return_value = {"key": "SEC-1", "fields": {"project": {"key": "SEC"}}}
    server = create_server(Settings(jira_mcp_allowed_projects="PROJ"))
    with pytest.raises(ToolError, match="not in an allowed project"):
        await server.call_tool("jira_get_issue", {"issue_key": "PROJ-1"})


async def test_get_create_fields_required_first(client: MagicMock) -> None:
    client.get_project_fields_metadata.return_value = {
        "b": {"name": "B", "required": False},
        "a": {"name": "A", "required": True},
    }
    _, result = await create_server(Settings()).call_tool(
        "jira_get_create_fields", {"project_key": "P", "issue_type": "Bug"}
    )
    assert [f["id"] for f in result["result"]] == ["a", "b"]


async def test_get_allowed_values_returns_values(client: MagicMock) -> None:
    client.get_allowed_values.return_value = [{"name": "High"}]
    _, result = await create_server(Settings()).call_tool(
        "jira_get_allowed_values", {"project_key": "P", "issue_type": "Bug", "field_id_or_name": "priority"}
    )
    assert result["result"] == [{"name": "High"}]


async def test_get_allowed_values_none_becomes_empty_list(client: MagicMock) -> None:
    client.get_allowed_values.return_value = None
    _, result = await create_server(Settings()).call_tool(
        "jira_get_allowed_values", {"project_key": "P", "issue_type": "Bug", "field_id_or_name": "summary"}
    )
    assert result["result"] == []


async def test_find_user_returns_only_safe_fields(client: MagicMock) -> None:
    client.get_account_data.return_value = [
        {"accountId": "abc", "displayName": "Ann", "active": True, "emailAddress": "ann@x.com"}
    ]
    with patch("jira_plus_mcp.tools.read.JiraCloud", MagicMock):
        _, result = await create_server(Settings()).call_tool("jira_find_user", {"query": "ann"})
    assert result["result"] == [{"accountId": "abc", "displayName": "Ann", "active": True}]


async def test_search_applies_allowlist_to_jql(client: MagicMock) -> None:
    client.jira_client.enhanced_search_issues.return_value = {"issues": []}
    server = create_server(Settings(jira_mcp_allowed_projects="A"))
    await server.call_tool("jira_search_issues", {"jql": "status = Open"})
    assert client.jira_client.enhanced_search_issues.call_args.kwargs["jql_str"] == "project in (A) AND (status = Open)"


async def test_search_limit_clamped_to_max_results(client: MagicMock) -> None:
    client.jira_client.enhanced_search_issues.return_value = {"issues": []}
    await create_server(Settings(jira_mcp_max_results=5)).call_tool("jira_search_issues", {"jql": "x", "limit": 999})
    assert client.jira_client.enhanced_search_issues.call_args.kwargs["maxResults"] == 6


async def test_search_fetches_one_page_of_limit_plus_one(client: MagicMock) -> None:
    client.jira_client.enhanced_search_issues.return_value = {"issues": [RAW]}
    await create_server(Settings()).call_tool("jira_search_issues", {"jql": "x", "limit": 20})
    client.jira_client.enhanced_search_issues.assert_called_once()
    assert client.jira_client.enhanced_search_issues.call_args.kwargs["maxResults"] == 21
    client.get_objects_by_query.assert_not_called()


async def test_search_on_premise_uses_search_issues_and_reports_truncation(client: MagicMock) -> None:
    client.jira_client.search_issues.return_value = {"issues": [RAW, RAW, RAW]}
    server = create_server(Settings(jira_deployment=Deployment.ON_PREMISE))
    _, result = await server.call_tool("jira_search_issues", {"jql": "x", "limit": 2})
    assert client.jira_client.search_issues.call_args.kwargs["maxResults"] == 3
    assert result["returned"] == 2
    assert result["truncated"] is True
