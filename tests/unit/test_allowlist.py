from unittest.mock import MagicMock

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from jira_plus_mcp.allowlist import check_key_prefix, guard_issue, in_allowed_project, scope_jql
from jira_plus_mcp.settings import Settings

SCOPED = Settings(jira_mcp_allowed_projects="A,B")


def test_scope_jql_keeps_order_by_outside() -> None:
    assert scope_jql(SCOPED, "status = Open ORDER BY created DESC") == (
        "project in (A, B) AND (status = Open) ORDER BY created DESC"
    )


def test_scope_jql_empty_where() -> None:
    assert scope_jql(SCOPED, "order by created") == "project in (A, B) ORDER BY created"


def test_scope_jql_noop_without_allowlist() -> None:
    assert scope_jql(Settings(), "status = Open") == "status = Open"


def test_key_prefix_is_case_insensitive() -> None:
    check_key_prefix(SCOPED, "a-1")
    with pytest.raises(ToolError, match="Project 'C' is not allowed. Allowed projects: A, B"):
        check_key_prefix(SCOPED, "C-1")


def test_in_allowed_project_handles_missing_project() -> None:
    assert in_allowed_project(SCOPED, {"key": "A-1", "fields": {"project": {"key": "a"}}})
    assert not in_allowed_project(SCOPED, {"key": "X-1"})
    assert in_allowed_project(Settings(), {"key": "X-1"})


def test_guard_issue_makes_no_request_without_allowlist() -> None:
    client = MagicMock()
    guard_issue(Settings(), client, "ANY-1")
    client.get_issue_by_key.assert_not_called()


def test_guard_issue_checks_current_project_of_an_id() -> None:
    client = MagicMock()
    client.get_issue_by_key.return_value = {"fields": {"project": {"key": "SECRET"}}}
    with pytest.raises(ToolError, match="Project 'SECRET' is not allowed"):
        guard_issue(SCOPED, client, "10001")
    client.get_issue_by_key.assert_called_once_with("10001", specific_fields=["project"])


def test_guard_issue_checks_every_key() -> None:
    client = MagicMock()
    client.get_issue_by_key.return_value = {"fields": {"project": {"key": "A"}}}
    with pytest.raises(ToolError, match="Project 'C' is not allowed"):
        guard_issue(SCOPED, client, "A-1", "C-2")
    client.get_issue_by_key.assert_called_once_with("A-1", specific_fields=["project"])
