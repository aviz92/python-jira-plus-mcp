from pydantic import BaseModel


class IssueSummary(BaseModel):
    key: str
    summary: str | None = None
    status: str | None = None
    issue_type: str | None = None
    priority: str | None = None
    assignee: str | None = None
    updated: str | None = None


class IssueDetail(IssueSummary):
    project: str | None = None
    reporter: str | None = None
    created: str | None = None
    labels: list[str] = []
    resolution: str | None = None
    parent: str | None = None
    description: str | None = None


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


class Transition(BaseModel):
    id: str
    name: str


class WriteResult(BaseModel):
    ok: bool
    message: str
    key: str | None = None
