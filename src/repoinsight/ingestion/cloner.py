"""Repository cloning and local workspace management module."""

from __future__ import annotations
import logging
import subprocess
from pathlib import Path

from src.repoinsight.ingestion.validator import RepositoryTarget, parse_repository_url

logger = logging.getLogger(__name__)

class RepositoryCloningError(RuntimeError):
    """Raised when a git clone or update operation fails."""

class RepositoryCloner:
    """Manages the local filesystem workspace and cloning of Git repositories."""

    def __init__(self,workspace_dir: str | Path = "data/repositories") -> None:
        """Initialize the cloner with a base workspace directory.
        Args:
            workspace_dir: Directory where repositories will be cloned and stored.
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def get_repo_path(self,target: RepositoryTarget) -> Path:
        """Compute the deterministic local storage path for a repository target.
        Args:
            target: The validated RepositoryTarget.
        Returns:
            Path: The absolute path where the repository is or will be stored.
        """
        return self.workspace_dir / target.host / target.owner / target.repo_name

    def is_cloned(self, repo_path: Path) -> bool:
        """Check if a valid Git repository exists at the specified path.
        Args:
            repo_path: The local directory path to inspect.
        Returns:
            bool: True if the path contains a valid .git directory, False otherwise.
        """
        git_dir = repo_path / ".git"
        return repo_path.is_dir() and git_dir.exists()

    def clone(self, target: RepositoryTarget, timeout_seconds: int = 180) -> Path:
        """Clone a remote repository into the isolated workspace if not already present.
        Args:
            target: The validated RepositoryTarget to clone.
            timeout_seconds: Maximum allowed time in seconds for the clone operation.
        Returns:
            Path: The local path of the cloned repository.
        Raises:
            RepositoryCloningError: If the git command times out or returns a non-zero exit code.
        """
        destination_path = self.get_repo_path(target)

        if self.is_cloned(destination_path):
            logger.info("Repository already exists locally at: %s", destination_path)
            return destination_path

        logger.info("Cloning '%s' into '%s' ...", target.clone_url,destination_path)

        command = [
            "git",
            "clone",
            "--quiet",
            target.clone_url,
            str(destination_path)
        ]

        try:
            result = subprocess.run(command,capture_output=True,text=True,timeout=timeout_seconds,check=False,)
        except FileNotFoundError as exc:
            raise RepositoryCloningError("Git executable not found on system PATH. Please install Git.") from exc


        if result.returncode != 0:
            error_details = result.stderr.strip() or "Unknown Git error"
            raise RepositoryCloningError(
                f"Failed to clone '{target.clone_url}' (exit code {result.returncode}): {error_details}"
            )
        logger.info("Successfully cloned repository to: %s", destination_path)
        return destination_path

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    # Test with a lightweight public repository (GitHub's standard test repo)
    sample_url = "https://github.com/octocat/Hello-World"
    print("--- Testing Repository Cloner ---")
    
    target_repo = parse_repository_url(sample_url)
    cloner = RepositoryCloner(workspace_dir="data/repositories")
    
    print(f"Target: {target_repo.identifier}")
    local_path = cloner.clone(target_repo)
    print(f"[OK] Repository ready at local path: {local_path}")
    print(f"[OK] Verified .git presence: {cloner.is_cloned(local_path)}")