"""Repository cloning and local workspace management module."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from src.repoinsight.ingestion.validator import RepositoryTarget, parse_repository_url

logger = logging.getLogger(__name__)


class RepositoryCloningError(RuntimeError):
    """Raised when a git clone or update operation fails."""


class RepositoryCloner:
    """Manages the local filesystem workspace and cloning of Git repositories."""

    def __init__(self, workspace_dir: str | Path = "data/repositories") -> None:
        """Initialize the cloner with a base workspace directory."""
        self.workspace_dir = Path(workspace_dir).resolve()
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def get_repo_path(self, target: RepositoryTarget) -> Path:
        """Compute the deterministic local storage path for a repository target."""
        return self.workspace_dir / target.host / target.owner / target.repo_name

    def is_cloned(self, repo_path: Path) -> bool:
        """Check if a valid Git repository exists at the specified path."""
        git_dir = repo_path / ".git"
        return repo_path.is_dir() and git_dir.is_dir() and any(git_dir.iterdir())

    def clone(self, target: RepositoryTarget, timeout_seconds: int = 240) -> Path:
        """Clone a remote repository into the isolated workspace if not already present."""
        destination_path = self.get_repo_path(target)

        # 1. Idempotent check: reuse existing clone if already present and healthy
        if self.is_cloned(destination_path):
            logger.info("Repository already exists locally and is healthy at: %s", destination_path)
            return destination_path

        # 2. If directory exists but is incomplete/corrupted, clean it up
        if destination_path.exists():
            logger.warning("Found incomplete clone at %s. Removing and recloning...", destination_path)
            shutil.rmtree(destination_path, ignore_errors=True)

        destination_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("Cloning '%s' into '%s'...", target.clone_url, destination_path)

        command = [
            "git",
            "clone",
            "--quiet",
            target.clone_url,
            str(destination_path),
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RepositoryCloningError(
                f"Cloning timed out after {timeout_seconds} seconds for: {target.clone_url}"
            ) from exc
        except FileNotFoundError as exc:
            raise RepositoryCloningError(
                "Git executable not found on system PATH. Please install Git."
            ) from exc

        if result.returncode != 0:
            error_details = result.stderr.strip() or "Unknown Git error"
            raise RepositoryCloningError(
                f"Failed to clone '{target.clone_url}' (exit code {result.returncode}): {error_details}"
            )

        logger.info("Successfully cloned repository to: %s", destination_path)
        return destination_path