# 🧱 Python Jira Plus MCP Service
This repository contains the Python implementation of the Jira Plus MCP (Model Conttext Protocol) Service. <br>
This service is designed to facilitate seamless integration between Jira and various MCP-compatible tools, enhancing project management capabilities.

---

## 🚀 Features
- **Get server version**: Retrieve the current version of the Jira server.
- **Get issue details**: Fetch detailed information about specific Jira issues.
- **Create and update issues**: Programmatically create new issues or update existing ones.
- **Search issues**: Perform advanced searches to find issues based on various criteria.
- **User management**: Manage Jira users, including creating, updating, and deleting user accounts.
- **Project management**: Create and manage Jira projects with ease.
- **Custom field handling**: Work with custom fields in Jira issues.

## Connecting to Claude Desktop
1. clone this repository and build the Docker image with the following command:
    ```bash
      docker build -t jira-plus-mcp .
    ```

2. add the following json configuration to your Claude Desktop setup:
```json
{
  "mcpServers": {
    "jira-plus-service": {
      "command": "docker",
      "args": [
        "run", "--rm",
        "-e", "BASE_URL=<your_jira_instance_url>",
        "-e", "JIRA_USERNAME=<your_jira_username>",
        "-e", "JIRA_TOKEN=<your_jira_api_token>",
        "-i", "jira-plus-mcp"
      ]
    }
  }
}
```

---

## 🤝 Contributing
If you have a helpful tool, pattern, or improvement to suggest:
Fork the repo <br>
Create a new branch <br>
Submit a pull request <br>
I welcome additions that promote clean, productive, and maintainable development. <br>

---

## 🙏 Thanks
Thanks for exploring this repository! <br>
Happy coding! <br>
