from jira_plus_mcp.formatters import format_allowed_values, format_detail, format_summary
from jira_plus_mcp.settings import Settings

RAW = {
    "key": "PROJ-1",
    "fields": {
        "summary": "s",
        "status": {"name": "Open", "self": "https://x/status/1", "statusCategory": {"key": "new"}},
        "assignee": {"displayName": "Ann", "accountId": "abc", "avatarUrls": {"48x48": "https://x/a.png"}},
        "project": {"key": "PROJ", "name": "Project"},
        "parent": {"key": "PROJ-0"},
        "labels": ["a"],
    },
}


def test_format_summary_flattens_nested_objects() -> None:
    summary = format_summary(RAW)
    assert (summary.key, summary.status, summary.assignee, summary.priority) == ("PROJ-1", "Open", "Ann", None)


def test_format_detail_adds_project_parent_and_labels() -> None:
    detail = format_detail(RAW)
    assert (detail.project, detail.parent, detail.labels, detail.reporter) == ("PROJ", "PROJ-0", ["a"], None)


def test_format_detail_with_no_fields() -> None:
    detail = format_detail({"key": "PROJ-2"})
    assert (detail.key, detail.status, detail.labels) == ("PROJ-2", None, [])


def test_read_only_is_default() -> None:
    assert Settings().jira_mcp_read_only is True


def test_http_host_and_port_default_to_loopback() -> None:
    settings = Settings()
    assert (settings.jira_mcp_host, settings.jira_mcp_port) == ("127.0.0.1", 8000)


def test_format_allowed_values_keeps_identifying_keys() -> None:
    assert format_allowed_values([{"id": "1", "value": "High", "self": "http://x"}, "plain"]) == [
        {"id": "1", "value": "High"},
        {"value": "plain"},
    ]


def test_format_allowed_values_none_is_empty() -> None:
    assert format_allowed_values(None) == []
