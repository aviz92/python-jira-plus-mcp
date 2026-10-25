from typing import Any

from jira_plus_mcp.models import AllowedValues, FieldMeta, IssueDetail, IssueSummary

MAX_ALLOWED_VALUES = 50
ALLOWED_VALUE_KEYS = ("id", "key", "name", "value")


def _name(obj: dict[str, Any] | None, key: str = "name") -> str | None:
    return obj.get(key) if obj else None


def _person(obj: dict[str, Any] | None) -> str | None:
    return _name(obj, "displayName")


def format_summary(raw: dict[str, Any]) -> IssueSummary:
    fields = raw.get("fields", {})
    return IssueSummary(
        key=raw["key"],
        summary=fields.get("summary"),
        status=_name(fields.get("status")),
        issue_type=_name(fields.get("issuetype")),
        priority=_name(fields.get("priority")),
        assignee=_person(fields.get("assignee")),
        updated=fields.get("updated"),
    )


def format_detail(raw: dict[str, Any]) -> IssueDetail:
    fields = raw.get("fields", {})
    return IssueDetail(
        **format_summary(raw).model_dump(),
        project=_name(fields.get("project"), "key"),
        reporter=_person(fields.get("reporter")),
        created=fields.get("created"),
        labels=fields.get("labels") or [],
        resolution=_name(fields.get("resolution")),
        parent=_name(fields.get("parent"), "key"),
        description=fields.get("description"),
    )


def _allowed_value_label(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or value.get("value") or value.get("key") or value.get("id"))
    return str(value)


def format_fields_metadata(metadata: dict[str, Any]) -> list[FieldMeta]:
    """Trim createmeta down to what a model needs to build a valid create call."""
    result = []
    for field_id, meta in metadata.items():
        allowed = meta.get("allowedValues")
        result.append(
            FieldMeta(
                id=field_id,
                name=meta.get("name", field_id),
                required=bool(meta.get("required")),
                type=(meta.get("schema") or {}).get("type"),
                allowed_values=[_allowed_value_label(v) for v in allowed[:MAX_ALLOWED_VALUES]] if allowed else None,
                allowed_values_truncated=bool(allowed) and len(allowed) > MAX_ALLOWED_VALUES,
            )
        )
    return sorted(result, key=lambda f: (not f.required, f.name))


def format_allowed_values(allowed: list[Any] | None) -> AllowedValues:
    """Keep only the identifying keys of each value and flag when the list was cut."""
    items = allowed or []
    values = [
        {k: v[k] for k in ALLOWED_VALUE_KEYS if k in v} if isinstance(v, dict) else {"value": v}
        for v in items[:MAX_ALLOWED_VALUES]
    ]
    return AllowedValues(values=values, total=len(items), truncated=len(items) > MAX_ALLOWED_VALUES)
