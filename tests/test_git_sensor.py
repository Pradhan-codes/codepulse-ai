"""Unit tests for local Git activity sensor."""

from pathlib import Path
import subprocess
import pytest

from codepulse.collector.git_sensor import (
    GitCommit,
    GitSensor,
    _parse_shortstat,
    _run_git_command,
    get_current_branch,
    get_recent_commits,
    get_repo_name,
    is_git_repository,
)


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    """Fixture to create an initialized temporary Git repository with commits."""
    repo_dir = tmp_path / "sample-project"
    repo_dir.mkdir()

    # Initialize repo
    subprocess.run(["git", "init"], cwd=str(repo_dir), capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.name", "CodePulse Tester"],
        cwd=str(repo_dir),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@codepulse.ai"],
        cwd=str(repo_dir),
        capture_output=True,
        check=True,
    )

    # First commit
    file1 = repo_dir / "README.md"
    file1.write_text("# Sample Project\nInitial documentation.\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo_dir), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "docs: initial commit"],
        cwd=str(repo_dir),
        capture_output=True,
        check=True,
    )

    # Second commit
    file2 = repo_dir / "app.py"
    file2.write_text("def main():\n    print('hello world')\n", encoding="utf-8")
    subprocess.run(["git", "add", "app.py"], cwd=str(repo_dir), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "feat: add main function"],
        cwd=str(repo_dir),
        capture_output=True,
        check=True,
    )

    return repo_dir


def test_is_git_repository(temp_git_repo: Path, tmp_path: Path):
    """Test detecting valid and invalid Git repositories."""
    assert is_git_repository(temp_git_repo) is True

    non_git_dir = tmp_path / "empty_dir"
    non_git_dir.mkdir()
    assert is_git_repository(non_git_dir) is False

    non_existent = tmp_path / "does_not_exist"
    assert is_git_repository(non_existent) is False


def test_get_repo_name_and_branch(temp_git_repo: Path):
    """Test retrieving repository name and active branch."""
    assert get_repo_name(temp_git_repo) == "sample-project"

    branch = get_current_branch(temp_git_repo)
    assert branch in ("main", "master")


def test_get_recent_commits(temp_git_repo: Path):
    """Test extracting commit log metadata with diff statistics."""
    commits = get_recent_commits(temp_git_repo, limit=5)
    assert len(commits) == 2

    # Newest commit first
    c0 = commits[0]
    assert c0.commit_message == "feat: add main function"
    assert c0.repo_name == "sample-project"
    assert len(c0.commit_hash) == 40
    assert c0.files_changed == 1
    assert c0.insertions == 2
    assert c0.deletions == 0

    # Oldest commit second
    c1 = commits[1]
    assert c1.commit_message == "docs: initial commit"
    assert c1.files_changed == 1
    assert c1.insertions == 2
    assert c1.deletions == 0


def test_git_sensor_deduplication(temp_git_repo: Path):
    """Test GitSensor avoids emitting duplicate commits on repeated polls."""
    sensor = GitSensor(temp_git_repo)
    assert sensor.is_valid is True
    assert sensor.repo_name == "sample-project"

    # 1. First poll: 2 new commits
    new_commits_1 = sensor.get_new_commits()
    assert len(new_commits_1) == 2

    # 2. Second poll: no new commits
    new_commits_2 = sensor.get_new_commits()
    assert len(new_commits_2) == 0

    # 3. Create a 3rd commit
    file3 = temp_git_repo / "utils.py"
    file3.write_text("def helper(): pass\n", encoding="utf-8")
    subprocess.run(["git", "add", "utils.py"], cwd=str(temp_git_repo), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "feat: add helper utility"],
        cwd=str(temp_git_repo),
        capture_output=True,
        check=True,
    )

    # 4. Third poll: only the 3rd commit returned
    new_commits_3 = sensor.get_new_commits()
    assert len(new_commits_3) == 1
    assert new_commits_3[0].commit_message == "feat: add helper utility"

    # 5. Clear seen and poll again: all 3 returned
    sensor.clear_seen()
    new_commits_all = sensor.get_new_commits()
    assert len(new_commits_all) == 3


def test_parse_shortstat_patterns():
    """Test regex parsing of various git --shortstat outputs."""
    assert _parse_shortstat("") == (0, 0, 0)
    assert _parse_shortstat("1 file changed, 10 insertions(+)") == (1, 10, 0)
    assert _parse_shortstat("3 files changed, 25 insertions(+), 8 deletions(-)") == (3, 25, 8)
    assert _parse_shortstat("2 files changed, 5 deletions(-)") == (2, 0, 5)


def test_git_commit_to_dict():
    """Test serializing GitCommit to dictionary."""
    commit = GitCommit(
        commit_hash="abc1234567890",
        timestamp="2026-08-17T12:00:00Z",
        commit_message="test: message",
        repo_name="my-repo",
        branch="main",
        files_changed=2,
        insertions=10,
        deletions=3,
    )
    d = commit.to_dict()
    assert d["commit_hash"] == "abc1234567890"
    assert d["files_changed"] == 2
    assert d["insertions"] == 10
    assert d["deletions"] == 3


def test_graceful_failures_on_non_git_path(tmp_path: Path):
    """Test functions handle non-git directory safely."""
    dummy_dir = tmp_path / "not_git"
    dummy_dir.mkdir()

    sensor = GitSensor(dummy_dir)
    assert sensor.is_valid is False
    assert sensor.get_recent_commits() == []
    assert sensor.get_new_commits() == []
    assert get_current_branch(dummy_dir) is None
    assert get_recent_commits(dummy_dir) == []


def test_run_git_command_timeout(temp_git_repo: Path):
    """Test git command timeout handling."""
    # Running with 0 timeout triggers timeout safely
    res = _run_git_command(["log"], cwd=temp_git_repo, timeout=0.00001)
    assert res is None
