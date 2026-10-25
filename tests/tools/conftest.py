from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(name="client")
def client_fixture() -> Iterator[MagicMock]:
    """A fully mocked library client, for what the MCP itself does with results."""
    client = MagicMock()
    with patch("jira_plus_mcp.client.build_client", return_value=client):
        yield client


@pytest.fixture(name="jira")
def jira_fixture() -> Iterator[MagicMock]:
    """The real library client over a mocked jira-python connection, for behaviour the library owns.

    Build the server with `tests.tools.common.make_settings(...)` so the client has credentials.
    """
    jira = MagicMock()
    jira.server_info.return_value = {"versionNumbers": [1001, 0, 0]}
    with patch("python_jira_plus.jira_cloud.JIRA", return_value=jira):
        yield jira
