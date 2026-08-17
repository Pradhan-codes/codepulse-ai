"""Local Git Activity Sensor for CodePulse.

Inspects local Git repositories via the Git CLI to extract commit metadata
and activity statistics (files changed, insertions, deletions) without reading
or storing source code contents.
"""

from dataclasses import dataclass
import logging
from pathlib import Path
import re
import subprocess
from typing import Any, Dict, List, Optional, Set, Union

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GitCommit:
    """Represents metadata of a single Git commit."""

    commit_hash: str
    timestamp: str  # ISO-8601 format string
    commit_message: str
    repo_name: str
    branch: str
    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert commit metadata to dictionary."""
        return {
            "commit_hash": self.commit_hash,
            "timestamp": self.timestamp,
            "commit_message": self.commit_message,
            "repo_name": self.repo_name,
            "branch": self.branch,
            "files_changed": self.files_changed,
            "insertions": self.insertions,
            "deletions": self.deletions,
        }


def _run_git_command(args: List[str], cwd: Path, timeout: float = 5.0) -> Optional[str]:
    """Execute a Git CLI command safely without shell=True.

    Args:
        args: Command line arguments (e.g. ['rev-parse', '--show-toplevel']).
        cwd: Directory where the command will be executed.
        timeout: Execution timeout in seconds.

    Returns:
        Standard output stripped of whitespace, or None if failed.
    """
    if not cwd.exists() or not cwd.is_dir():
        return None

    try:
        cmd = ["git"] + args
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (subprocess.SubprocessError, FileNotFoundError, PermissionError, OSError) as e:
        logger.debug("Git command %s failed in %s: %s", args, cwd, e)
        return None


def is_git_repository(repo_path: Union[str, Path]) -> bool:
    """Check if the given directory is inside a valid Git work tree."""
    path = Path(repo_path)
    output = _run_git_command(["rev-parse", "--is-inside-work-tree"], cwd=path)
    return output == "true"


def get_repo_name(repo_path: Union[str, Path]) -> Optional[str]:
    """Retrieve the root directory name of the Git repository."""
    path = Path(repo_path)
    output = _run_git_command(["rev-parse", "--show-toplevel"], cwd=path)
    if output:
        # Handles both forward and backward slashes correctly across OS
        return Path(output).name
    return None


def get_current_branch(repo_path: Union[str, Path]) -> Optional[str]:
    """Retrieve the currently checked out Git branch name."""
    path = Path(repo_path)
    output = _run_git_command(["branch", "--show-current"], cwd=path)
    if output:
        return output

    # Fallback for detached HEAD or older git versions
    head_output = _run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], cwd=path)
    if head_output and head_output != "HEAD":
        return head_output
    return "HEAD (detached)" if head_output else None


def _parse_shortstat(stat_text: str) -> tuple[int, int, int]:
    """Extract files_changed, insertions, deletions from git --shortstat line."""
    files_changed = 0
    insertions = 0
    deletions = 0

    if not stat_text:
        return files_changed, insertions, deletions

    files_match = re.search(r"(\d+)\s+file", stat_text)
    if files_match:
        files_changed = int(files_match.group(1))

    ins_match = re.search(r"(\d+)\s+insertion", stat_text)
    if ins_match:
        insertions = int(ins_match.group(1))

    del_match = re.search(r"(\d+)\s+deletion", stat_text)
    if del_match:
        deletions = int(del_match.group(1))

    return files_changed, insertions, deletions


def get_recent_commits(
    repo_path: Union[str, Path],
    limit: int = 10,
) -> List[GitCommit]:
    """Retrieve the most recent Git commits with diff statistics.

    Args:
        repo_path: Path to the local Git repository.
        limit: Maximum number of commits to retrieve.

    Returns:
        List of GitCommit objects ordered from newest to oldest.
    """
    path = Path(repo_path)
    if not is_git_repository(path):
        return []

    repo_name = get_repo_name(path) or path.name
    branch = get_current_branch(path) or "unknown"

    # Git log formatted with a unique delimiter and shortstat
    # Format: COMMIT_START\n<hash>\n<iso_time>\n<subject>
    delimiter = "---COMMIT_RECORD_START---"
    cmd_args = [
        "log",
        f"-n{max(1, limit)}",
        f"--format=format:{delimiter}%n%H%n%aI%n%s",
        "--shortstat",
    ]

    output = _run_git_command(cmd_args, cwd=path)
    if not output:
        return []

    commits: List[GitCommit] = []
    raw_blocks = output.split(delimiter)

    for block in raw_blocks:
        trimmed = block.strip()
        if not trimmed:
            continue

        lines = [line.strip() for line in trimmed.splitlines() if line.strip()]
        if len(lines) < 2:
            continue

        commit_hash = lines[0]
        timestamp = lines[1]
        commit_message = lines[2] if len(lines) >= 3 else ""

        # Stat line is typically the last line if diff stats exist
        stat_line = ""
        if len(lines) >= 4 and ("file" in lines[-1] or "changed" in lines[-1]):
            stat_line = lines[-1]
        elif len(lines) == 3 and ("file" in lines[-1] or "changed" in lines[-1]):
            # Subject was empty, line 2 is the stat line
            commit_message = ""
            stat_line = lines[-1]

        files_changed, insertions, deletions = _parse_shortstat(stat_line)

        commits.append(
            GitCommit(
                commit_hash=commit_hash,
                timestamp=timestamp,
                commit_message=commit_message,
                repo_name=repo_name,
                branch=branch,
                files_changed=files_changed,
                insertions=insertions,
                deletions=deletions,
            )
        )

    return commits


class GitSensor:
    """Sensor interface for tracking Git events on a local repository."""

    def __init__(self, repo_path: Union[str, Path]) -> None:
        self.repo_path = Path(repo_path)
        self._seen_commit_hashes: Set[str] = set()

    @property
    def is_valid(self) -> bool:
        """Check if target path is a valid Git repository."""
        return is_git_repository(self.repo_path)

    @property
    def repo_name(self) -> str:
        """Get repository name."""
        return get_repo_name(self.repo_path) or self.repo_path.name

    @property
    def current_branch(self) -> str:
        """Get current branch name."""
        return get_current_branch(self.repo_path) or "unknown"

    def get_recent_commits(self, limit: int = 10) -> List[GitCommit]:
        """Fetch recent commits without updating deduplication state."""
        return get_recent_commits(self.repo_path, limit=limit)

    def get_new_commits(self, limit: int = 50) -> List[GitCommit]:
        """
        Retrieve only commits that have not been observed previously by this sensor.
        Tracks returned commit hashes to avoid duplicate emissions.
        """
        commits = self.get_recent_commits(limit=limit)
        new_commits: List[GitCommit] = []

        for commit in commits:
            if commit.commit_hash not in self._seen_commit_hashes:
                self._seen_commit_hashes.add(commit.commit_hash)
                new_commits.append(commit)

        return new_commits

    def clear_seen(self) -> None:
        """Reset the set of known commit hashes."""
        self._seen_commit_hashes.clear()
