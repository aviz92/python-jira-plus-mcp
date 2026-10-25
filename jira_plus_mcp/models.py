from typing import Any

from pydantic import BaseModel
from python_jira_plus import IssueSummary


class SearchResult(BaseModel):
    issues: list[IssueSummary]
    returned: int
    truncated: bool


class FieldMeta(BaseModel):
    id: str
    name: str
    required: bool
    type: str | None = None
    allowed_values: list[str] | None = None
    allowed_values_truncated: bool = False


class Transition(BaseModel):
    id: str
    name: str


class WriteResult(BaseModel):
    ok: bool
    message: str
    key: str | None = None


class AllowedValues(BaseModel):
    values: list[dict[str, Any]]
    total: int
    truncated: bool


class LinkType(BaseModel):
    name: str
    inward: str
    outward: str
