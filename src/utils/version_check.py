"""
Version Check Module
====================

Provides functions to check whether the local repository is up-to-date with
the latest version on the GitHub ``main`` branch.

Uses the ``gh`` (GitHub CLI) for authentication — especially important while
the repository is private — and ``git`` for fetching and comparing commit counts.

Usage:
    >>> from src.utils.version_check import check_for_update
    >>> result = check_for_update()
    >>> if result["update_available"]:
    ...     print(f"Behind by {result['behind_count']} commit(s)")

Author: Synapic Project
"""

import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GH_INSTALL_PATHS = [
    os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "GitHub CLI"),
    os.path.join(
        os.environ.get("LocalAppData", os.path.expanduser("~\\AppData\\Local")),
        "GitHub CLI",
    ),
]

REMOTE = "origin"
BRANCH = "main"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class UpdateCheckResult:
    """Structured result from a version check."""

    update_available: bool = False
    behind_count: int = 0
    current_sha: str = ""
    latest_sha: str = ""
    error: Optional[str] = None
    details: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_cmd(
    args: list[str],
    timeout: int = 30,
    cwd: Optional[str] = None,
) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except FileNotFoundError:
        return -1, "", f"Command not found: {args[0]}"
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout}s: {args[0]}"
    except Exception as e:
        return -1, "", str(e)


def _find_gh() -> Optional[str]:
    """Locate the ``gh`` executable on PATH or in known install directories."""
    path = shutil.which("gh")
    if path:
        return path
    # Fall back to probing known install directories
    for directory in GH_INSTALL_PATHS:
        candidate = os.path.join(directory, "gh.exe")
        if os.path.isfile(candidate):
            return candidate
    return None


def _is_git_repo(project_root: str) -> bool:
    """Check whether ``project_root`` contains a ``.git`` directory or file."""
    git_path = os.path.join(project_root, ".git")
    return os.path.exists(git_path)


def _get_project_root() -> str:
    """Return the absolute path to the project root (where ``.git`` lives)."""
    # Walk up from this file's directory
    here = os.path.dirname(os.path.abspath(__file__))
    # src/utils/ -> src/ -> project root
    for _ in range(3):
        parent = os.path.dirname(here)
        if _is_git_repo(parent):
            return parent
        here = parent
    # If we didn't find .git, use the module root (3 levels up from this file)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_for_update(project_root: Optional[str] = None) -> UpdateCheckResult:
    """
    Check whether the local repository is up-to-date with ``origin/main``.

    Uses ``gh`` for authentication and ``git`` to fetch and compare commits.
    Gracefully handles missing tools, network errors, and non-git directories.

    Args:
        project_root: Path to the repository root. If ``None``, it is auto-detected.

    Returns:
        An ``UpdateCheckResult`` dataclass.
    """
    if project_root is None:
        project_root = _get_project_root()

    # ------------------------------------------------------------------
    # 1. Must be a git repository
    # ------------------------------------------------------------------
    if not _is_git_repo(project_root):
        return UpdateCheckResult(
            error=None,
            details="Not a git repository — skipping version check.",
        )

    # ------------------------------------------------------------------
    # 2. Locate ``gh`` CLI
    # ------------------------------------------------------------------
    gh_path = _find_gh()
    if not gh_path:
        # Attempt to install via winget
        logger.info("GitHub CLI not found — attempting install via winget...")
        rc, _, _ = _run_cmd(
            [
                "winget",
                "install",
                "-e",
                "--id",
                "GitHub.cli",
                "--source",
                "winget",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ],
            timeout=120,
        )
        if rc == 0:
            logger.info("GitHub CLI installed successfully via winget.")
            gh_path = _find_gh()
        else:
            return UpdateCheckResult(
                error=None,
                details="GitHub CLI not available and could not be installed. "
                "Install it manually from https://cli.github.com/.",
            )

    # ------------------------------------------------------------------
    # 3. Verify ``gh`` authentication (required for private repos)
    # ------------------------------------------------------------------
    rc, _, _ = _run_cmd([gh_path, "auth", "status"])
    if rc != 0:
        return UpdateCheckResult(
            error=None,
            details="GitHub CLI is installed but not authenticated. "
            'Run "gh auth login" to authenticate.',
        )

    # ------------------------------------------------------------------
    # 4. Fetch latest remote refs
    # ------------------------------------------------------------------
    rc, _, stderr = _run_cmd(
        ["git", "fetch", REMOTE, BRANCH],
        cwd=project_root,
    )
    if rc != 0:
        return UpdateCheckResult(
            error=None,
            details=f"Could not fetch latest version: {stderr or 'network error'}",
        )

    # ------------------------------------------------------------------
    # 5. Compare local HEAD with origin/main
    # ------------------------------------------------------------------
    # Get current SHA
    _, current_sha, _ = _run_cmd(
        ["git", "rev-parse", "HEAD"],
        cwd=project_root,
    )

    # Get latest SHA on origin/main
    _, latest_sha, _ = _run_cmd(
        ["git", "rev-parse", f"{REMOTE}/{BRANCH}"],
        cwd=project_root,
    )

    # Count commits behind
    behind_count = 0
    rc, stdout, _ = _run_cmd(
        ["git", "rev-list", "--count", f"HEAD..{REMOTE}/{BRANCH}"],
        cwd=project_root,
    )
    if rc == 0 and stdout:
        try:
            behind_count = int(stdout)
        except ValueError:
            behind_count = 0

    update_available = behind_count > 0

    details = (
        f"You are running the latest version ({current_sha[:8]})."
        if not update_available
        else f"You are {behind_count} commit(s) behind {latest_sha[:8]} "
        f"(current: {current_sha[:8]})."
    )

    return UpdateCheckResult(
        update_available=update_available,
        behind_count=behind_count,
        current_sha=current_sha,
        latest_sha=latest_sha,
        error=None,
        details=details,
    )


def pull_latest(project_root: Optional[str] = None) -> UpdateCheckResult:
    """
    Pull the latest changes from ``origin/main``.

    Returns an ``UpdateCheckResult`` indicating success/failure.
    """
    if project_root is None:
        project_root = _get_project_root()

    if not _is_git_repo(project_root):
        return UpdateCheckResult(
            error="Not a git repository.",
            details="Cannot pull — not a git repository.",
        )

    rc, stdout, stderr = _run_cmd(
        ["git", "pull", REMOTE, BRANCH],
        cwd=project_root,
        timeout=120,
    )

    if rc == 0:
        # Re-check version after pull
        return check_for_update(project_root=project_root)
    else:
        return UpdateCheckResult(
            error=f"git pull failed: {stderr}",
            details=stderr or stdout,
        )


# ---------------------------------------------------------------------------
# CLI entry point (for testing)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    import argparse

    parser = argparse.ArgumentParser(description="Check Synapic version")
    parser.add_argument("--pull", action="store_true", help="Pull latest changes")
    args = parser.parse_args()

    if args.pull:
        result = pull_latest()
    else:
        result = check_for_update()

    print(f"Update available: {result.update_available}")
    print(f"Behind count:    {result.behind_count}")
    print(f"Current SHA:     {result.current_sha[:8] if result.current_sha else 'N/A'}")
    print(f"Latest SHA:      {result.latest_sha[:8] if result.latest_sha else 'N/A'}")
    print(f"Details:         {result.details}")
    if result.error:
        print(f"Error:           {result.error}")
