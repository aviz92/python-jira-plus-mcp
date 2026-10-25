from unittest.mock import MagicMock, patch

import pytest
from jira import JIRAError
from mcp.server.fastmcp.exceptions import ToolError
from python_jira_plus import BASIC_FIELDS

from jira_plus_mcp.server import create_server
from jira_plus_mcp.settings import Deployment, Settings
from tests.tools.common import issue_in, make_settings

RAW = {"key": "PROJ-1", "fields": {"summary": "s", "status": {"name": "Open"}, "project": {"key": "PROJ"}}}


async def test_tool_names_prefixed_and_read_only() -> None:
    tools = await create_server(Settings()).list_tools()
    assert {t.name for t in tools} == {
        "jira_get_issue",
        "jira_search_issues",
        "jira_get_create_fields",
        "jira_get_allowed_values",
        "jira_get_link_types",
        "jira_find_user",
    }
    assert all(t.annotations.readOnlyHint for t in tools)


async def test_find_user_not_registered_on_premise() -> None:
    tools = await create_server(Settings(jira_deployment=Deployment.ON_PREMISE)).list_tools()
    assert "jira_find_user" not in {t.name for t in tools}


async def test_get_issue(client: MagicMock) -> None:
    client.get_issue_by_key.return_value = RAW
    _, result = await create_server(Settings()).call_tool("jira_get_issue", {"issue_key": "PROJ-1"})
    assert (result["key"], result["status"], result["project"]) == ("PROJ-1", "Open", "PROJ")
    client.get_issue_by_key.assert_called_once_with("PROJ-1", specific_fields=BASIC_FIELDS)


async def test_get_issue_library_error_becomes_tool_error(client: MagicMock) -> None:
    client.get_issue_by_key.side_effect = JIRAError(status_code=404, text="Issue does not exist")
    with pytest.raises(ToolError, match="Jira error 404: Issue does not exist"):
        await create_server(Settings()).call_tool("jira_get_issue", {"issue_key": "PROJ-9"})


async def test_disallowed_project_rejected_before_request(jira: MagicMock) -> None:
    server = create_server(make_settings(jira_mcp_allowed_projects="OK"))
    with pytest.raises(ToolError, match="Project 'NO' is not allowed"):
        await server.call_tool("jira_get_issue", {"issue_key": "NO-1"})
    jira.issue.assert_not_called()


async def test_get_issue_moved_to_disallowed_project_rejected(jira: MagicMock) -> None:
    jira.issue.return_value = issue_in("SEC")
    server = create_server(make_settings(jira_mcp_allowed_projects="PROJ"))
    with pytest.raises(ToolError, match="Project 'SEC' is not allowed"):
        await server.call_tool("jira_get_issue", {"issue_key": "PROJ-1"})


async def test_invalid_issue_key_rejected_before_request(jira: MagicMock) -> None:
    with pytest.raises(ToolError, match="Invalid issue key"):
        await create_server(make_settings()).call_tool("jira_get_issue", {"issue_key": "PROJ-1/../myself"})
    jira.issue.assert_not_called()


async def test_search_truncates_and_flags(client: MagicMock) -> None:
    client.get_objects_by_query.return_value = [RAW, RAW, RAW]
    _, result = await create_server(Settings()).call_tool("jira_search_issues", {"jql": "x", "limit": 2})
    assert (result["returned"], result["truncated"]) == (2, True)


async def test_search_is_scoped_and_filtered_by_allowlist(jira: MagicMock) -> None:
    other = {"key": "SEC-1", "fields": {"project": {"key": "SEC"}}}
    jira.enhanced_search_issues.return_value = {"issues": [RAW, other], "isLast": True}
    server = create_server(make_settings(jira_mcp_allowed_projects="PROJ"))
    _, result = await server.call_tool("jira_search_issues", {"jql": "x) OR (project = SEC"})
    assert jira.enhanced_search_issues.call_args.kwargs["jql_str"].startswith("project in (PROJ) AND (")
    assert [i["key"] for i in result["issues"]] == ["PROJ-1"]


async def test_search_limit_clamped_to_max_results(client: MagicMock) -> None:
    client.get_objects_by_query.return_value = []
    await create_server(Settings(jira_mcp_max_results=5)).call_tool("jira_search_issues", {"jql": "x", "limit": 999})
    assert client.get_objects_by_query.call_args.kwargs["limit"] == 6


async def test_search_asks_library_for_limit_plus_one(client: MagicMock) -> None:
    client.get_objects_by_query.return_value = [RAW]
    _, result = await create_server(Settings()).call_tool("jira_search_issues", {"jql": "x", "limit": 20})
    client.get_objects_by_query.assert_called_once_with(
        "x", limit=21, max_results=21, specific_fields=BASIC_FIELDS, json_result=True
    )
    assert (result["returned"], result["truncated"]) == (1, False)


async def test_cloud_short_pages_not_last_still_truncated(jira: MagicMock) -> None:
    jira.enhanced_search_issues.side_effect = [
        {"issues": [RAW] * 10, "isLast": False, "nextPageToken": "a"},
        {"issues": [RAW] * 11, "isLast": False, "nextPageToken": "b"},
    ]
    _, result = await create_server(make_settings()).call_tool("jira_search_issues", {"jql": "x", "limit": 20})
    assert (result["returned"], result["truncated"]) == (20, True)


async def test_cloud_last_page_not_truncated(jira: MagicMock) -> None:
    jira.enhanced_search_issues.return_value = {"issues": [RAW], "isLast": True}
    _, result = await create_server(make_settings()).call_tool("jira_search_issues", {"jql": "x"})
    assert (result["returned"], result["truncated"]) == (1, False)


async def test_get_create_fields_caps_allowed_values(client: MagicMock) -> None:
    client.get_create_fields.return_value = [
        {"id": "a", "name": "A", "required": True, "type": "option", "allowed_values": [f"v{i}" for i in range(60)]},
        {"id": "b", "name": "B", "required": False, "type": "string", "allowed_values": None},
    ]
    _, result = await create_server(Settings()).call_tool(
        "jira_get_create_fields", {"project_key": "P", "issue_type": "Bug"}
    )
    first, second = result["result"]
    assert (len(first["allowed_values"]), first["allowed_values_truncated"]) == (50, True)
    assert (second["allowed_values"], second["allowed_values_truncated"]) == (None, False)


async def test_get_create_fields_disallowed_project(jira: MagicMock) -> None:
    server = create_server(make_settings(jira_mcp_allowed_projects="OK"))
    with pytest.raises(ToolError, match="Project 'NO' is not allowed"):
        await server.call_tool("jira_get_create_fields", {"project_key": "NO", "issue_type": "Bug"})
    jira.createmeta.assert_not_called()


async def test_validation_error_passes_through(client: MagicMock) -> None:
    client.get_allowed_values.side_effect = ValueError("Field 'x' not found; allowed values are [a, b]")
    with pytest.raises(ToolError, match="allowed values are"):
        await create_server(Settings()).call_tool(
            "jira_get_allowed_values", {"project_key": "P", "issue_type": "Bug", "field_id_or_name": "x"}
        )


async def test_get_allowed_values_returns_values(client: MagicMock) -> None:
    client.get_allowed_values.return_value = [{"name": "High"}]
    _, result = await create_server(Settings()).call_tool(
        "jira_get_allowed_values", {"project_key": "P", "issue_type": "Bug", "field_id_or_name": "priority"}
    )
    assert result == {"values": [{"name": "High"}], "total": 1, "truncated": False}


async def test_get_allowed_values_none_becomes_empty_list(client: MagicMock) -> None:
    client.get_allowed_values.return_value = None
    _, result = await create_server(Settings()).call_tool(
        "jira_get_allowed_values", {"project_key": "P", "issue_type": "Bug", "field_id_or_name": "summary"}
    )
    assert result == {"values": [], "total": 0, "truncated": False}


async def test_allowed_values_trimmed_and_flagged_when_cut(client: MagicMock) -> None:
    client.get_allowed_values.return_value = [
        {"id": str(i), "name": f"v{i}", "self": "http://noise"} for i in range(60)
    ]
    _, result = await create_server(Settings()).call_tool(
        "jira_get_allowed_values", {"project_key": "P", "issue_type": "Bug", "field_id_or_name": "x"}
    )
    assert (result["total"], len(result["values"]), result["truncated"]) == (60, 50, True)
    assert "self" not in result["values"][0]


async def test_find_user_returns_only_safe_fields(client: MagicMock) -> None:
    client.get_account_data.return_value = [
        {"accountId": "abc", "displayName": "Ann", "active": True, "emailAddress": "ann@x.com"}
    ]
    with patch("jira_plus_mcp.tools.read.JiraCloud", MagicMock):
        _, result = await create_server(Settings()).call_tool("jira_find_user", {"query": "ann"})
    assert result["result"] == [{"accountId": "abc", "displayName": "Ann", "active": True}]


async def test_get_link_types(client: MagicMock) -> None:
    client.get_link_types.return_value = [{"name": "Blocks", "inward": "is blocked by", "outward": "blocks"}]
    _, result = await create_server(Settings()).call_tool("jira_get_link_types", {})
    assert result["result"] == [{"name": "Blocks", "inward": "is blocked by", "outward": "blocks"}]


async def test_each_server_gets_a_client_with_its_own_allowlist(jira: MagicMock) -> None:
    jira.issue.return_value = issue_in("PROJ")
    open_server = create_server(make_settings())
    scoped_server = create_server(make_settings(jira_mcp_allowed_projects="OTHER"))
    await open_server.call_tool("jira_get_issue", {"issue_key": "PROJ-1"})
    with pytest.raises(ToolError, match="not allowed"):
        await scoped_server.call_tool("jira_get_issue", {"issue_key": "PROJ-1"})
