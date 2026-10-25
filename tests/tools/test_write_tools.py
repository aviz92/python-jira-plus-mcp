from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from jira_plus_mcp.server import create_server
from jira_plus_mcp.settings import Settings

WRITABLE = {"jira_mcp_read_only": False}


@pytest.fixture(name="client")
def client_fixture() -> Iterator[MagicMock]:
    client = MagicMock()
    with patch("jira_plus_mcp.tools.write.get_client", return_value=client):
        yield client


async def names(settings: Settings) -> set[str]:
    return {t.name for t in await create_server(settings).list_tools()}


async def test_read_only_hides_write_tools() -> None:
    assert not {"jira_create_issue", "jira_delete_issue", "jira_get_transitions"} & await names(Settings())


async def test_delete_needs_explicit_opt_in() -> None:
    assert "jira_delete_issue" not in await names(Settings(**WRITABLE))
    assert "jira_delete_issue" in await names(Settings(**WRITABLE, jira_mcp_enable_delete=True))


async def test_create_issue(client: MagicMock) -> None:
    client.create_issue.return_value.key = "P-1"
    args = {"project_key": "P", "summary": "s", "description": "d", "issue_type": "Bug"}
    _, result = await create_server(Settings(**WRITABLE)).call_tool("jira_create_issue", args)
    assert result["key"] == "P-1"


async def test_update_surfaces_validation_error(client: MagicMock) -> None:
    client.get_issue_by_key.return_value = {"fields": {"project": {"key": "P"}, "issuetype": {"name": "Bug"}}}
    client.validate_fields.side_effect = ValueError("Priority: allowed values are [High, Low]")
    with pytest.raises(ToolError, match="allowed values are"):
        await create_server(Settings(**WRITABLE)).call_tool(
            "jira_update_issue", {"issue_key": "P-1", "fields_to_update": {"priority": "x"}}
        )
    client.update_issue.assert_not_called()


async def test_transition_lists_available_on_bad_name(client: MagicMock) -> None:
    client.jira_client.transitions.return_value = [{"id": "1", "name": "Done"}]
    with pytest.raises(ToolError, match="Available: Done"):
        await create_server(Settings(**WRITABLE)).call_tool(
            "jira_transition_issue", {"issue_key": "P-1", "transition_name": "Nope"}
        )


async def test_write_respects_allowlist(client: MagicMock) -> None:
    server = create_server(Settings(**WRITABLE, jira_mcp_allowed_projects="OK"))
    with pytest.raises(ToolError, match="not allowed"):
        await server.call_tool("jira_add_comment", {"issue_key": "NO-1", "comment": "x"})
    client.add_comment.assert_not_called()


async def test_delete_false_becomes_error(client: MagicMock) -> None:
    client.delete_issue.return_value = False
    server = create_server(Settings(**WRITABLE, jira_mcp_enable_delete=True))
    with pytest.raises(ToolError, match="Failed to delete"):
        await server.call_tool("jira_delete_issue", {"issue_key": "P-1"})


@pytest.mark.parametrize("bad_key", ["../../rest/api/2/user", "P-1/../Q-2", "P-0", "P1", ""])
async def test_malformed_key_rejected_before_api_call(client: MagicMock, bad_key: str) -> None:
    server = create_server(Settings(**WRITABLE, jira_mcp_enable_delete=True))
    with pytest.raises(ToolError, match="Invalid issue key"):
        await server.call_tool("jira_delete_issue", {"issue_key": bad_key})
    client.delete_issue.assert_not_called()


async def test_moved_issue_blocked_by_current_project(client: MagicMock) -> None:
    client.get_issue_by_key.return_value = {"key": "OK-1", "fields": {"project": {"key": "SEC"}}}
    server = create_server(Settings(**WRITABLE, jira_mcp_allowed_projects="OK"))
    with pytest.raises(ToolError, match="not allowed"):
        await server.call_tool("jira_add_comment", {"issue_key": "OK-1", "comment": "x"})
    client.add_comment.assert_not_called()


async def test_get_transitions(client: MagicMock) -> None:
    client.jira_client.transitions.return_value = [{"id": "1", "name": "Done", "extra": "ignored"}]
    _, result = await create_server(Settings(**WRITABLE)).call_tool("jira_get_transitions", {"issue_key": "P-1"})
    assert result["result"] == [{"id": "1", "name": "Done"}]


async def test_update_issue_success_validates_before_update(client: MagicMock) -> None:
    client.get_issue_by_key.return_value = {"fields": {"project": {"key": "P"}, "issuetype": {"name": "Bug"}}}
    _, result = await create_server(Settings(**WRITABLE)).call_tool(
        "jira_update_issue", {"issue_key": "p-1", "fields_to_update": {"summary": "x"}}
    )
    assert result["key"] == "P-1"
    client.validate_fields.assert_called_once_with(project_key="P", issue_type="Bug", fields={"summary": "x"})
    client.update_issue.assert_called_once_with("P-1", {"summary": "x"})


async def test_update_issue_library_none_becomes_error(client: MagicMock) -> None:
    client.get_issue_by_key.return_value = {"fields": {"project": {"key": "P"}, "issuetype": {"name": "Bug"}}}
    client.update_issue.return_value = None
    with pytest.raises(ToolError, match="Failed to update"):
        await create_server(Settings(**WRITABLE)).call_tool(
            "jira_update_issue", {"issue_key": "P-1", "fields_to_update": {"summary": "x"}}
        )


async def test_update_issue_missing_issue(client: MagicMock) -> None:
    client.get_issue_by_key.return_value = None
    with pytest.raises(ToolError, match="not found"):
        await create_server(Settings(**WRITABLE)).call_tool(
            "jira_update_issue", {"issue_key": "P-1", "fields_to_update": {}}
        )


async def test_add_comment(client: MagicMock) -> None:
    await create_server(Settings(**WRITABLE)).call_tool("jira_add_comment", {"issue_key": "P-1", "comment": "hi"})
    client.add_comment.assert_called_once_with("P-1", "hi")


async def test_transition_name_is_case_insensitive(client: MagicMock) -> None:
    client.jira_client.transitions.return_value = [{"id": "1", "name": "Done"}]
    client.transition_issue.return_value = True
    await create_server(Settings(**WRITABLE)).call_tool(
        "jira_transition_issue", {"issue_key": "P-1", "transition_name": "done", "comment": "c"}
    )
    client.transition_issue.assert_called_once_with("P-1", "Done", None, "c")  # exact Jira name, not "done"


async def test_transition_library_false_becomes_error(client: MagicMock) -> None:
    client.jira_client.transitions.return_value = [{"id": "1", "name": "Done"}]
    client.transition_issue.return_value = False
    with pytest.raises(ToolError, match="failed"):
        await create_server(Settings(**WRITABLE)).call_tool(
            "jira_transition_issue", {"issue_key": "P-1", "transition_name": "Done"}
        )


async def test_link_issues_maps_parameters(client: MagicMock) -> None:
    client.create_link.return_value = True
    args = {"inward_issue_key": "P-1", "outward_issue_key": "P-2", "link_type": "Blocks"}
    await create_server(Settings(**WRITABLE)).call_tool("jira_link_issues", args)
    client.create_link.assert_called_once_with("P-1", "Blocks", "P-2")


async def test_link_checks_both_keys_against_allowlist(client: MagicMock) -> None:
    server = create_server(Settings(**WRITABLE, jira_mcp_allowed_projects="OK"))
    client.get_issue_by_key.return_value = {"fields": {"project": {"key": "OK"}}}
    args = {"inward_issue_key": "OK-1", "outward_issue_key": "NO-2", "link_type": "Blocks"}
    with pytest.raises(ToolError, match="not allowed"):
        await server.call_tool("jira_link_issues", args)
    client.create_link.assert_not_called()


async def test_create_issue_none_becomes_error(client: MagicMock) -> None:
    client.create_issue.return_value = None
    args = {"project_key": "P", "summary": "s", "description": "d", "issue_type": "Bug"}
    with pytest.raises(ToolError, match="not created"):
        await create_server(Settings(**WRITABLE)).call_tool("jira_create_issue", args)


async def test_delete_success(client: MagicMock) -> None:
    client.delete_issue.return_value = True
    server = create_server(Settings(**WRITABLE, jira_mcp_enable_delete=True))
    _, result = await server.call_tool("jira_delete_issue", {"issue_key": "P-1"})
    assert result["message"] == "Deleted P-1"
