from jira_plus_mcp.formatters import MAX_ALLOWED_VALUES, cap_create_fields
from jira_plus_mcp.settings import Settings


def test_allowed_projects_parsed_from_csv() -> None:
    assert Settings(jira_mcp_allowed_projects="proj1, PROJ2").jira_mcp_allowed_projects == ["PROJ1", "PROJ2"]


def test_read_only_is_default() -> None:
    assert Settings().jira_mcp_read_only is True


def test_http_host_and_port_default_to_loopback() -> None:
    settings = Settings()
    assert (settings.jira_mcp_host, settings.jira_mcp_port) == ("127.0.0.1", 8000)


def test_cap_create_fields_keeps_library_fields_and_order() -> None:
    fields = cap_create_fields(
        [
            {"id": "a", "name": "A", "required": True, "type": "option", "allowed_values": ["x"]},
            {"id": "b", "name": "B", "required": False, "type": None, "allowed_values": None},
        ]
    )
    assert [(f.id, f.required, f.allowed_values, f.allowed_values_truncated) for f in fields] == [
        ("a", True, ["x"], False),
        ("b", False, None, False),
    ]


def test_cap_create_fields_cuts_long_lists() -> None:
    values = [str(i) for i in range(MAX_ALLOWED_VALUES + 1)]
    field = cap_create_fields([{"id": "a", "name": "A", "required": True, "type": None, "allowed_values": values}])[0]
    assert (len(field.allowed_values), field.allowed_values_truncated) == (MAX_ALLOWED_VALUES, True)
