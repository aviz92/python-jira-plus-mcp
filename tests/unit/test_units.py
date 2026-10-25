from jira_plus_mcp.formatters import format_detail, format_fields_metadata
from jira_plus_mcp.settings import Settings
from jira_plus_mcp.tools.read import scope_jql

RAW = {
    "key": "PROJ-1",
    "fields": {
        "summary": "s",
        "status": {"name": "Open"},
        "assignee": {"displayName": "Ann"},
        "project": {"key": "PROJ"},
        "labels": ["a"],
    },
}


def test_allowed_projects_parsed_from_csv() -> None:
    assert Settings(jira_mcp_allowed_projects="proj1, PROJ2").jira_mcp_allowed_projects == ["PROJ1", "PROJ2"]


def test_read_only_is_default() -> None:
    assert Settings().jira_mcp_read_only is True


def test_scope_jql_keeps_order_by_outside() -> None:
    settings = Settings(jira_mcp_allowed_projects="A,B")
    assert scope_jql(settings, "status = Open ORDER BY created DESC") == (
        "project in (A, B) AND (status = Open) ORDER BY created DESC"
    )


def test_scope_jql_noop_without_allowlist() -> None:
    assert scope_jql(Settings(), "status = Open") == "status = Open"


def test_format_detail_compacts_issue() -> None:
    detail = format_detail(RAW)
    assert (detail.key, detail.status, detail.assignee, detail.project) == ("PROJ-1", "Open", "Ann", "PROJ")


def test_fields_metadata_required_first_and_trimmed() -> None:
    meta = {
        "b": {"name": "B", "required": False},
        "a": {"name": "A", "required": True, "allowedValues": [{"name": "x"}], "schema": {"type": "option"}},
    }
    fields = format_fields_metadata(meta)
    assert [f.id for f in fields] == ["a", "b"]
    assert fields[0].allowed_values == ["x"]
