 The Smart Release Notes Generator (MCP Server)

An AI-native **Model Context Protocol (MCP)** server built with Python and `FastMCP`. This tool allows LLMs (like Claude Desktop) to securely interact with your local Git repositories and your Jira instance to track development updates, cross-reference tickets, and automatically generate professional release notes.

---

 Features

- Model Context Protocol (MCP) Integration: Exposes local tools seamlessly to Claude Desktop or any MCP-compatible AI client.
- Git History Parsing: Interacts with local repositories using `GitPython` to read and evaluate recent commit logs.
- Jira Integration: Uses the official `jira` Python SDK to pull task descriptions, statuses, and cross-reference them with your code updates.
- Environment Driven: Completely configured via standard environment variables and local JSON configurations.

---

 Tech Stack

- Language: Python 3.10+
- Framework: FastMCP (Model Context Protocol SDK)
- APIs & SDKs: GitPython, Jira SDK
- Configuration: Python-dotenv, JSON

---

 Project Structure

```text
├── .env                         # Local environment configurations (DO NOT COMMIT)
├── claude_desktop_config.json   # Configuration mapping for Claude Desktop app
├── requirements.txt             # Python project dependencies
└── server.py                    # Main FastMCP Server implementation

