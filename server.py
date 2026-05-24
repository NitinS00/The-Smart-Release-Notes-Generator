import argparse
import io
import os
import re
import sys
from io import TextIOWrapper
from typing import Optional

try:
    from mcp.server.fastmcp import FastMCP
    import mcp.server.stdio as mcp_stdio
    import mcp.server.fastmcp.server as fastmcp_server
except ImportError:
    FastMCP = None
    mcp_stdio = None
    fastmcp_server = None

try:
    from git import Repo
except ImportError:  # pragma: no cover
    Repo = None

try:
    from jira import JIRA
except ImportError:  # pragma: no cover
    JIRA = None

from dotenv import load_dotenv

# Automatically load environment keys from .env file
load_dotenv()


class MCPFallback:
    def tool(self, func):
        return func

    def run(self):
        raise RuntimeError(
            "FastMCP is not installed. Use python server.py <from_ref> [to_ref] "
            "or install requirements from requirements.txt."
        )


mcp = FastMCP("Smart Release Notes Generator") if FastMCP else MCPFallback()


def get_repo_path() -> Optional[str]:
    repo_path = os.getenv("GIT_REPO_PATH") or os.getenv("GIT REPO PATH")
    if repo_path:
        return repo_path.strip('"\' ')
    return None


def get_jira_client() -> JIRA:
    """Sets up an authenticated Jira client using environment variables."""
    if JIRA is None:
        raise RuntimeError("jira package is not installed. Install requirements.txt.")

    jira_url = os.getenv("JIRA_URL")
    email = os.getenv("JIRA_EMAIL")
    token = os.getenv("JIRA_API_TOKEN")

    if not jira_url or not email or not token:
        raise RuntimeError(
            "Missing Jira environment variables. Please set JIRA_URL, JIRA_EMAIL, and JIRA_API_TOKEN."
        )

    return JIRA(server=jira_url, basic_auth=(email, token))


def _install_stdio_json_filter() -> None:
    if mcp_stdio is None or fastmcp_server is None:
        return

    class FilteredRawBuffer(io.RawIOBase):
        def __init__(self, raw):
            self._raw = raw

        def readable(self) -> bool:
            return True

        def read(self, size: int = -1) -> bytes:
            return self._raw.read(size)

        def readinto(self, b) -> int:
            data = self._raw.read(len(b))
            if not data:
                return 0
            b[: len(data)] = data
            return len(data)

        def readline(self, size: int = -1) -> bytes:
            while True:
                line = self._raw.readline(size)
                if not line:
                    return line
                if line.lstrip().startswith(b"{") or line.lstrip().startswith(b"["):
                    return line
                continue

    original_stdio_server = mcp_stdio.stdio_server

    def stdio_server_filtered(stdin=None, stdout=None):
        if stdin is None:
            wrapped = TextIOWrapper(FilteredRawBuffer(sys.stdin.buffer), encoding="utf-8", errors="replace")
            stdin = __import__("anyio").wrap_file(wrapped)
        if stdout is None:
            stdout = __import__("anyio").wrap_file(TextIOWrapper(sys.stdout.buffer, encoding="utf-8"))
        return original_stdio_server(stdin=stdin, stdout=stdout)

    mcp_stdio.stdio_server = stdio_server_filtered
    fastmcp_server.stdio_server = stdio_server_filtered


@mcp.tool()
def generate_release_report(from_ref: str, to_ref: str = "HEAD") -> str:
    """
    Scans local Git history for Jira ticket keys and cross-checks their status.

    Args:
        from_ref: The starting git tag or commit SHA (e.g., 'v1.0.0').
        to_ref: The ending git tag or commit SHA. Defaults to 'HEAD'.
    """
    repo_path = get_repo_path()
    if not repo_path:
        return (
            "Setup Error: GIT_REPO_PATH is missing from your environment setup. "
            "Use GIT_REPO_PATH or GIT REPO PATH in .env."
        )

    if Repo is None:
        return "GitPython is not installed. Install requirements.txt."

    try:
        repo = Repo(repo_path)
    except Exception as exc:
        return f"Git Processing Error: Could not open repository at '{repo_path}'. Info: {exc}"

    commit_range = f"{from_ref}..{to_ref}"
    try:
        commits = list(repo.iter_commits(commit_range))
    except Exception as exc:
        return f"Git Processing Error: Could not evaluate range {commit_range}. Info: {exc}"

    if not commits:
        return f"Zero new commits found within the range {commit_range}."

    jira_regex = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")
    ticket_keys = set()

    for commit in commits:
        ticket_keys.update(jira_regex.findall(commit.message))

    if not ticket_keys:
        return f"Analyzed {len(commits)} commits, but no valid Jira ticket prefixes were matched."

    if JIRA is None:
        return "jira package is not installed. Install requirements.txt."

    try:
        jira = get_jira_client()
        jql_keys = ", ".join(f'"{key}"' for key in sorted(ticket_keys))
        issues = jira.search_issues(
            f"key in ({jql_keys})",
            fields=["summary", "status"],
            maxResults=1000,
        )
    except Exception as exc:
        return f"Jira Server Exception: Data retrieval failed. Info: {exc}"

    jira_url = os.getenv("JIRA_URL", "").rstrip("/")
    report_lines = [
        f"### Smart Release Audit ({from_ref} ➔ {to_ref})",
        f"Matched **{len(issues)}** Jira tickets across **{len(commits)}** commits.\n",
    
    ]

    for issue in issues:
        status_name = issue.fields.status.name
        category = getattr(issue.fields.status.statusCategory, "key", "")
        is_ready = "Yes" if category.lower() == "done" else "Blocked/Open"
        ticket_link = (
            f"[{issue.key}]({jira_url}/browse/{issue.key})"
            if jira_url
            else issue.key
        )
        report_lines.append(f"| {ticket_link} | {issue.fields.summary} | `{status_name}` | {is_ready} |")

    return "\n".join(report_lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a Jira release report from Git commits.")
    parser.add_argument("from_ref", help="Starting Git ref or tag (for example v1.0.0)")
    parser.add_argument("to_ref", nargs="?", default="HEAD", help="Ending Git ref or tag (default: HEAD)")
    return parser.parse_args()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        args = parse_args()
        print(generate_release_report(args.from_ref, args.to_ref))
    elif FastMCP:
        _install_stdio_json_filter()
        mcp.run()
    else:
        print(
            "No command-line arguments provided and FastMCP is not available.\n"
            "Usage: python server.py <from_ref> [to_ref]"
        )
        sys.exit(1)
