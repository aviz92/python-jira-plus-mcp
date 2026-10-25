from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from jira import JIRAError
from mcp.server.fastmcp.exceptions import ToolError
from python_jira_plus import JiraCloud

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


async def test_write_respects_allowlist(client: MagicMock) -> None:
    server = create_server(Settings(**WRITABLE, jira_mcp_allowed_projects="OK"))
    with pytest.raises(ToolError, match="not allowed"):
        await server.call_tool("jira_add_comment", {"issue_key": "NO-1", "comment": "x"})
    client.add_comment.assert_not_called()


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
    client.get_transitions.return_value = [{"id": "1", "name": "Done"}]
    _, result = await create_server(Settings(**WRITABLE)).call_tool("jira_get_transitions", {"issue_key": "P-1"})
    assert result["result"] == [{"id": "1", "name": "Done"}]


async def test_add_comment(client: MagicMock) -> None:
    await create_server(Settings(**WRITABLE)).call_tool("jira_add_comment", {"issue_key": "P-1", "comment": "hi"})
    client.add_comment.assert_called_once_with("P-1", "hi")


async def test_link_checks_both_keys_against_allowlist(client: MagicMock) -> None:
    server = create_server(Settings(**WRITABLE, jira_mcp_allowed_projects="OK"))
    client.get_issue_by_key.return_value = {"fields": {"project": {"key": "OK"}}}
    args = {"inward_issue_key": "OK-1", "outward_issue_key": "NO-2", "link_type": "Blocks"}
    with pytest.raises(ToolError, match="not allowed"):
        await server.call_tool("jira_link_issues", args)
    client.create_link.assert_not_called()


async def test_delete_success(client: MagicMock) -> None:
    client.delete_issue.return_value = True
    server = create_server(Settings(**WRITABLE, jira_mcp_enable_delete=True))
    _, result = await server.call_tool("jira_delete_issue", {"issue_key": "P-1"})
    assert result["message"] == "Deleted P-1"


@pytest.fixture(name="real_write_client")
def real_write_client_fixture(real_client: JiraCloud) -> Iterator[JiraCloud]:
    with patch("jira_plus_mcp.tools.write.get_client", return_value=real_client):
        yield real_client


CREATE_ARGS = {"project_key": "OK", "summary": "s", "description": "d", "issue_type": "Bug"}


async def test_update_issue_only_calls_update(client: MagicMock) -> None:
    _, result = await create_server(Settings(**WRITABLE)).call_tool(
        "jira_update_issue", {"issue_key": "p-1", "fields_to_update": {"summary": "x"}}
    )
    assert result["key"] == "P-1"
    client.update_issue.assert_called_once_with("P-1", {"summary": "x"})
    client.get_issue_by_key.assert_not_called()
    client.validate_fields.assert_not_called()


async def test_update_accepts_edit_only_field(real_write_client: JiraCloud) -> None:
    jira = real_write_client.jira_client
    jira.editmeta.return_value = {"fields": {"customfield_100": {"name": "Edit only", "schema": {"type": "string"}}}}
    await create_server(Settings(**WRITABLE)).call_tool(
        "jira_update_issue", {"issue_key": "P-1", "fields_to_update": {"customfield_100": "x"}}
    )
    jira.issue.return_value.update.assert_called_once_with(fields={"customfield_100": "x"})
    jira.createmeta.assert_not_called()


async def test_update_invalid_value_surfaces_allowed_values(real_write_client: JiraCloud) -> None:
    real_write_client.jira_client.editmeta.return_value = {
        "fields": {"priority": {"name": "Priority", "allowedValues": [{"name": "High"}]}}
    }
    with pytest.raises(ToolError, match="allowed values"):
        await create_server(Settings(**WRITABLE)).call_tool(
            "jira_update_issue", {"issue_key": "P-1", "fields_to_update": {"priority": {"name": "Nope"}}}
        )
    real_write_client.jira_client.issue.return_value.update.assert_not_called()


async def test_create_rejects_project_override_in_custom_fields(real_write_client: JiraCloud) -> None:
    args = CREATE_ARGS | {"custom_fields": {"project": {"key": "OTHER"}}}
    with pytest.raises(ToolError, match="conflicts with the dedicated argument for 'project'"):
        await create_server(Settings(**WRITABLE)).call_tool("jira_create_issue", args)
    real_write_client.jira_client.create_issue.assert_not_called()


async def test_create_library_error_becomes_tool_error(client: MagicMock) -> None:
    client.create_issue.side_effect = JIRAError(status_code=400, text="summary is required")
    with pytest.raises(ToolError, match="Jira error 400: summary is required"):
        await create_server(Settings(**WRITABLE)).call_tool("jira_create_issue", CREATE_ARGS)


async def test_transition_name_is_case_insensitive(real_write_client: JiraCloud) -> None:
    jira = real_write_client.jira_client
    jira.transitions.return_value = [{"id": "31", "name": "Done", "fields": {}}]
    _, result = await create_server(Settings(**WRITABLE)).call_tool(
        "jira_transition_issue", {"issue_key": "P-1", "transition_name": "done"}
    )
    assert jira.transition_issue.call_args.kwargs["transition"] == "31"
    assert result["ok"] is True


async def test_transition_unknown_name_lists_available(real_write_client: JiraCloud) -> None:
    real_write_client.jira_client.transitions.return_value = [{"id": "1", "name": "Done"}, {"id": "2", "name": "Open"}]
    with pytest.raises(ToolError, match=r"Available transitions: \['Done', 'Open'\]"):
        await create_server(Settings(**WRITABLE)).call_tool(
            "jira_transition_issue", {"issue_key": "P-1", "transition_name": "Nope"}
        )
    real_write_client.jira_client.transition_issue.assert_not_called()


async def test_transition_comment_added_separately(client: MagicMock) -> None:
    _, result = await create_server(Settings(**WRITABLE)).call_tool(
        "jira_transition_issue", {"issue_key": "P-1", "transition_name": "Done", "comment": "c"}
    )
    client.transition_issue.assert_called_once_with("P-1", "Done", fields=None, comment=None)
    client.add_comment.assert_called_once_with("P-1", "c")
    assert result == {"ok": True, "message": "Transitioned P-1 to Done", "key": "P-1"}


async def test_transition_failed_comment_is_partial_success(client: MagicMock) -> None:
    client.add_comment.side_effect = JIRAError(status_code=403, text="no comment permission")
    _, result = await create_server(Settings(**WRITABLE)).call_tool(
        "jira_transition_issue", {"issue_key": "P-1", "transition_name": "Done", "comment": "c"}
    )
    assert result["ok"] is True
    assert result["message"] == (
        "Transitioned P-1 to Done, but the comment failed: Jira error 403: no comment permission"
    )


async def test_transition_failure_raises_without_commenting(client: MagicMock) -> None:
    client.transition_issue.side_effect = JIRAError(status_code=400, text="resolution required")
    with pytest.raises(ToolError, match="resolution required"):
        await create_server(Settings(**WRITABLE)).call_tool(
            "jira_transition_issue", {"issue_key": "P-1", "transition_name": "Done", "comment": "c"}
        )
    client.add_comment.assert_not_called()


def link_type(name: str) -> MagicMock:
    link = MagicMock(inward=f"{name} in", outward=f"{name} out")
    link.name = name
    return link


async def test_link_type_is_case_insensitive(real_write_client: JiraCloud) -> None:
    jira = real_write_client.jira_client
    jira.issue_link_types.return_value = [link_type("Blocks")]
    args = {"inward_issue_key": "P-1", "outward_issue_key": "P-2", "link_type": "blocks"}
    await create_server(Settings(**WRITABLE)).call_tool("jira_link_issues", args)
    jira.create_issue_link.assert_called_once_with(type="Blocks", inwardIssue="P-1", outwardIssue="P-2")


async def test_link_unknown_type_lists_available(real_write_client: JiraCloud) -> None:
    real_write_client.jira_client.issue_link_types.return_value = [link_type("Blocks"), link_type("Relates")]
    args = {"inward_issue_key": "P-1", "outward_issue_key": "P-2", "link_type": "Nope"}
    with pytest.raises(ToolError, match=r"Available link types: \['Blocks', 'Relates'\]"):
        await create_server(Settings(**WRITABLE)).call_tool("jira_link_issues", args)
    real_write_client.jira_client.create_issue_link.assert_not_called()


async def test_delete_library_error_becomes_tool_error(client: MagicMock) -> None:
    client.delete_issue.side_effect = JIRAError(status_code=403, text="no delete permission")
    server = create_server(Settings(**WRITABLE, jira_mcp_enable_delete=True))
    with pytest.raises(ToolError, match="Jira error 403"):
        await server.call_tool("jira_delete_issue", {"issue_key": "P-1"})
