from enum import StrEnum
from functools import lru_cache
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DEFAULT_MAX_RESULTS = 100


class Deployment(StrEnum):
    CLOUD = "cloud"
    ON_PREMISE = "on_premise"


class Transport(StrEnum):
    STDIO = "stdio"
    STREAMABLE_HTTP = "streamable-http"


class Settings(BaseSettings):
    """Server configuration. Reuses the python-jira-plus env var names so one .env serves both."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    jira_base_url: str = ""
    jira_user_name: str = ""
    jira_token: SecretStr = SecretStr("")
    jira_deployment: Deployment = Deployment.CLOUD
    jira_sso: bool = False
    jira_verify_ssl: bool = True

    jira_mcp_read_only: bool = True
    jira_mcp_enable_delete: bool = False
    jira_mcp_allowed_projects: Annotated[list[str], NoDecode] = Field(default_factory=list)
    jira_mcp_transport: Transport = Transport.STDIO
    jira_mcp_max_results: int = Field(default=DEFAULT_MAX_RESULTS, ge=1)

    @field_validator("jira_mcp_allowed_projects", mode="before")
    @classmethod
    def _split_projects(cls, value: object) -> object:
        if isinstance(value, str):
            return [p.strip().upper() for p in value.split(",") if p.strip()]
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
