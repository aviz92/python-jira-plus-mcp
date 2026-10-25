from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import SecretStr

from jira_plus_mcp.client import build_client, get_client
from jira_plus_mcp.server import create_server
from jira_plus_mcp.settings import Deployment, Settings


def make_settings(**overrides: object) -> Settings:
    base = {"jira_base_url": "https://acme.atlassian.net", "jira_user_name": "u", "jira_token": SecretStr("t")}
    return Settings(**(base | overrides))


@pytest.fixture(name="isolated_env")
def isolated_env_fixture(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The library falls back to env vars and .env for empty arguments; keep real credentials out of these tests."""
    for name in ("JIRA_BASE_URL", "JIRA_USER_NAME", "JIRA_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    get_client.cache_clear()
    with patch("python_jira_plus.jira_base.load_dotenv"):
        yield
    get_client.cache_clear()


async def call_with(settings: Settings) -> None:
    """Build the client inside a tool call, where its ValueError becomes a ToolError."""
    with patch("jira_plus_mcp.client.get_settings", return_value=settings):
        await create_server(settings).call_tool("jira_get_issue", {"issue_key": "P-1"})


def test_build_client_cloud() -> None:
    with patch("jira_plus_mcp.client.JiraCloud") as cloud:
        build_client(make_settings())
    cloud.assert_called_once_with(
        base_url="https://acme.atlassian.net", jira_username="u", jira_token="t", verify_ssl=True, raise_on_error=True
    )


def test_build_client_on_premise_passes_sso_ssl_and_raise_on_error() -> None:
    settings = make_settings(jira_deployment=Deployment.ON_PREMISE, jira_sso=True, jira_verify_ssl=False)
    with patch("jira_plus_mcp.client.JiraOnPremise") as on_prem:
        build_client(settings)
    kwargs = on_prem.call_args.kwargs
    assert kwargs["sso"] is True
    assert kwargs["verify_ssl"] is False
    assert kwargs["raise_on_error"] is True


@pytest.mark.usefixtures("isolated_env")
def test_on_prem_pat_needs_token_but_not_username() -> None:
    jira = MagicMock()
    jira.server_info.return_value = {"versionNumbers": [9, 12, 0]}
    settings = make_settings(jira_deployment=Deployment.ON_PREMISE, jira_user_name="")
    with patch("python_jira_plus.jira_on_premise.JIRA", return_value=jira) as connect:
        build_client(settings)
    assert connect.call_args.kwargs["token_auth"] == "t"


@pytest.mark.usefixtures("isolated_env")
async def test_missing_token_is_tool_error_with_library_message() -> None:
    with pytest.raises(ToolError, match="Jira token is missing"):
        await call_with(make_settings(jira_deployment=Deployment.ON_PREMISE, jira_token=SecretStr("")))


@pytest.mark.usefixtures("isolated_env")
async def test_on_prem_sso_requires_username() -> None:
    settings = make_settings(jira_deployment=Deployment.ON_PREMISE, jira_sso=True, jira_user_name="")
    with pytest.raises(ToolError, match="Jira username is missing"):
        await call_with(settings)


@pytest.mark.usefixtures("isolated_env")
async def test_missing_base_url_is_tool_error() -> None:
    with pytest.raises(ToolError, match="Jira base URL is missing"):
        await call_with(make_settings(jira_base_url=""))
