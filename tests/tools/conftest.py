from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from python_jira_plus import JiraCloud


@pytest.fixture(name="real_client")
def real_client_fixture() -> Iterator[JiraCloud]:
    """A real JiraCloud over a mocked jira-python connection, for behaviour the library itself now owns."""
    jira = MagicMock()
    jira.server_info.return_value = {"versionNumbers": [1001, 0, 0]}
    with patch("python_jira_plus.jira_cloud.JIRA", return_value=jira):
        yield JiraCloud(base_url="https://acme.atlassian.net", jira_username="u", jira_token="t", raise_on_error=True)
