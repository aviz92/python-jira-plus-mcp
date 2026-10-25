from unittest.mock import patch

import pytest
from pydantic import SecretStr
from python_jira_plus import UrlScheme

from jira_plus_mcp.client import _split_scheme, build_client
from jira_plus_mcp.settings import Deployment, Settings


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("acme.atlassian.net", ("acme.atlassian.net", UrlScheme.HTTPS)),
        ("https://acme.atlassian.net/", ("acme.atlassian.net", UrlScheme.HTTPS)),
        ("http://jira.local:8080", ("jira.local:8080", UrlScheme.HTTP)),
    ],
)
def test_split_scheme(raw: str, expected: tuple[str, UrlScheme]) -> None:
    assert _split_scheme(raw) == expected


def make_settings(**overrides: object) -> Settings:
    base = {"jira_base_url": "https://acme.atlassian.net", "jira_user_name": "u", "jira_token": SecretStr("t")}
    return Settings(**(base | overrides))


def test_build_client_cloud() -> None:
    with patch("jira_plus_mcp.client.JiraCloud") as cloud:
        build_client(make_settings())
    cloud.assert_called_once_with(
        base_url="acme.atlassian.net", jira_username="u", jira_token="t", verify_ssl=True, url_scheme=UrlScheme.HTTPS
    )


def test_build_client_on_premise_passes_sso_and_ssl() -> None:
    settings = make_settings(jira_deployment=Deployment.ON_PREMISE, jira_sso=True, jira_verify_ssl=False)
    with patch("jira_plus_mcp.client.JiraOnPremise") as on_prem:
        build_client(settings)
    kwargs = on_prem.call_args.kwargs
    assert kwargs["sso"] is True
    assert kwargs["verify_ssl"] is False
