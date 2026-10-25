from functools import lru_cache

from mcp.server.fastmcp.exceptions import ToolError
from python_jira_plus import JiraCloud, JiraOnPremise, UrlScheme
from python_jira_plus.jira_base import JiraBase

from jira_plus_mcp.settings import Deployment, Settings, get_settings


def _split_scheme(base_url: str) -> tuple[str, UrlScheme]:
    """The library expects the host without a scheme and takes the scheme separately."""
    if base_url.startswith("http://"):
        return base_url.removeprefix("http://").rstrip("/"), UrlScheme.HTTP
    return base_url.removeprefix("https://").rstrip("/"), UrlScheme.HTTPS


def _check_required(settings: Settings) -> None:
    required = {"JIRA_BASE_URL": settings.jira_base_url, "JIRA_TOKEN": settings.jira_token.get_secret_value()}
    # Cloud and on-prem SSO use basic auth (username + token); on-prem without SSO uses the token alone
    if settings.jira_deployment is Deployment.CLOUD or settings.jira_sso:
        required["JIRA_USER_NAME"] = settings.jira_user_name
    if missing := [name for name, value in required.items() if not value]:
        raise ToolError(f"{', '.join(missing)} not set. Configure the server's environment and restart it")


def build_client(settings: Settings) -> JiraBase:
    _check_required(settings)
    host, scheme = _split_scheme(settings.jira_base_url)
    common = {
        "base_url": host,
        "jira_username": settings.jira_user_name,
        "jira_token": settings.jira_token.get_secret_value(),
        "verify_ssl": settings.jira_verify_ssl,
        "url_scheme": scheme,
    }
    if settings.jira_deployment is Deployment.CLOUD:
        return JiraCloud(**common)
    return JiraOnPremise(sso=settings.jira_sso, **common)


@lru_cache(maxsize=1)
def get_client() -> JiraBase:
    """Connect on first tool call, not at server start, so a bad credential doesn't kill the server."""
    return build_client(get_settings())
