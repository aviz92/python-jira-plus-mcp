import logging
import os
from typing import Optional, Union

from custom_python_logger import build_logger
from dotenv import load_dotenv
from mcp.server import FastMCP
from python_jira_plus import JiraPlus, ServerType
from python_jira_plus.jira_plus import UrlScheme

load_dotenv()

logger = build_logger(project_name="Jira Plus MCP Service")

# Create an MCP server
mcp = FastMCP(name="Jira Plus MCP Service")


@mcp.tool()
def ping() -> str:
    """Simple test tool to verify server stays running."""
    return "pong"


jira_plus_service = JiraPlus(
    base_url=os.getenv("BASE_URL"),
    server_type=ServerType.CLOUD,
    urllib3_log_level=logging.WARNING,
    jira_username=os.getenv("JIRA_USERNAME"),
    jira_token=os.getenv("JIRA_TOKEN"),
    verify_ssl=True,
    sso=False,
    url_scheme=UrlScheme.HTTPS
)


@mcp.tool()
def get_server_version() -> str:
    """ Get Jira server version."""
    ver_tuple = jira_plus_service.get_server_version()
    return ".".join(map(str, ver_tuple))


@mcp.tool()
def get_account_data(user_mail: str) -> list[dict]:
    """ Get account data by user email."""
    return jira_plus_service.get_account_data(
        user_mail=user_mail
    )


@mcp.tool()
def get_account_id(user_mail: str) -> str:
    """ Get account ID by user email."""
    return jira_plus_service.get_account_id(
        user_mail=user_mail
    )


@mcp.tool()
def get_account_display_name(user_display_name: str) -> str:
    """ Get account display name by user display name."""
    return jira_plus_service.get_account_display_name(
        user_display_name=user_display_name
    )


@mcp.tool()
def get_issue_by_key(
    key: str,
    specific_fields: str | list[str] = '*all',
) -> None | dict:
    """ Returns issue by its key. """
    return jira_plus_service.get_issue_by_key(
        key=key,
        specific_fields=specific_fields,
        json_result=True
    )


@mcp.tool()
def get_objects_by_query(
    query: str,
    max_results: int = 5000,
    specific_fields: Union[str, list[str]] = "*all",
    jira_err_count: int = 3,
) -> dict:
    """ Returns issues based on JQL query. """
    return jira_plus_service.get_objects_by_query(
        query=query,
        max_results=max_results,
        specific_fields=specific_fields,
        jira_err_count=jira_err_count,
        json_result=True
    )


@mcp.tool()
def get_allowed_values(project_key: str, issue_type: str, field_id_or_name: str) -> Optional[list]:
    """ Returns the allowed values for a specific field in a project and issue type context. """
    return jira_plus_service.get_allowed_values(
        project_key=project_key,
        issue_type=issue_type,
        field_id_or_name=field_id_or_name
    )


@mcp.tool()
def get_project_fields_metadata(project_key: str, issue_type: str) -> dict:
    """ Get project fields metadata for a specific project and issue type."""
    return jira_plus_service.get_project_fields_metadata(
        project_key=project_key,
        issue_type=issue_type
    )


@mcp.tool()
def create_issue(
    project_key: str,
    summary: str,
    description: str,
    issue_type: str,
    assignee: Optional[str] = None,
    custom_fields: Optional[dict] = None,
) -> dict:
    """ Create an issue in a project."""
    issue = jira_plus_service.create_issue(
        project_key=project_key,
        summary=summary,
        description=description,
        issue_type=issue_type,
        assignee=assignee,
        custom_fields=custom_fields
    )
    return issue.to_dict()


@mcp.tool()
def update_issue(issue_key: str, fields_to_update: dict) -> Optional[dict]:
    """ Update an issue by its key."""
    issue = jira_plus_service.update_issue(
        issue_key=issue_key,
        fields_to_update=fields_to_update
    )
    return issue.to_dict() if issue else None


@mcp.tool()
def delete_issue(issue_key: str) -> bool:
    """ Delete an issue by its key."""
    return jira_plus_service.delete_issue(
        issue_key=issue_key
    )


@mcp.tool()
def add_comment(issue: str, comment: str) -> None:
    """ Add a comment to an issue."""
    jira_plus_service.add_comment(
        issue=issue,
        comment=comment
    )


@mcp.tool()
def create_link(issue_key: str, link_type: str, in_issue_key: str) -> bool:
    """ Create a link between two issues."""
    return jira_plus_service.create_link(
        issue_key=issue_key,
        link_type=link_type,
        in_issue_key=in_issue_key
    )


@mcp.tool()
def transition_issue(
    issue_key: str,
    transition_name: str,
    fields: Optional[dict] = None,
    comment: Optional[str] = None,
) -> bool:
    """ Transition issue to a new status."""
    return jira_plus_service.transition_issue(
        issue_key=issue_key,
        transition_name=transition_name,
        fields=fields,
        comment=comment
    )


# Run the server
if __name__ == "__main__":
    mcp.run()
