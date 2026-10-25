"""Output caps that keep tool results small enough for a model's context. Jira logic lives in python-jira-plus."""

from typing import Any

from python_jira_plus import CreateField

from jira_plus_mcp.models import AllowedValues, FieldMeta

MAX_ALLOWED_VALUES = 50
ALLOWED_VALUE_KEYS = ("id", "key", "name", "value")


def cap_create_fields(fields: list[CreateField]) -> list[FieldMeta]:
    """Cut each field's allowed values to MAX_ALLOWED_VALUES and flag the ones that were cut."""
    capped = []
    for field in fields:
        values = field["allowed_values"]
        capped.append(
            FieldMeta(
                **(field | {"allowed_values": values[:MAX_ALLOWED_VALUES] if values else values}),
                allowed_values_truncated=bool(values) and len(values) > MAX_ALLOWED_VALUES,
            )
        )
    return capped


def format_allowed_values(allowed: list[Any] | None) -> AllowedValues:
    """Keep only the identifying keys of each value and flag when the list was cut."""
    items = allowed or []
    values = [
        {k: v[k] for k in ALLOWED_VALUE_KEYS if k in v} if isinstance(v, dict) else {"value": v}
        for v in items[:MAX_ALLOWED_VALUES]
    ]
    return AllowedValues(values=values, total=len(items), truncated=len(items) > MAX_ALLOWED_VALUES)
