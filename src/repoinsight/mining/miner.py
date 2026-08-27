"""Streaming Git repository miner using PyDriller."""

from __future__ import annotations
import logging
from collections.abc import Iterator
from pathlib import Path

from pydriller import ModificationType, Repository

from src.repoinsight.mining.models import ChangeType, CommitRecord, FileChangeRecord

logger = logging.getLogger(__name__)

_PYDRILLER_CHANGE_TYPE_MAP: dict[ModificationType, ChangeType] = {
    ModificationType.ADD: ChangeType.ADD,
    ModificationType.MODIFY: ChangeType.MODIFY,
    ModificationType.DELETE: ChangeType.DELETE,
    ModificationType.RENAME: ChangeType.RENAME,
    ModificationType.COPY: ChangeType.ADD,
}

class GitRepositoryMiner:
    """Extracts and streams commit history and file diffs from a local Git repository."""

    def __init__(self, repo_path: str | Path) -> None:
        """Initialize the miner with the target repository path.
        Args:
            repo_path: Local path to the cloned Git repository.
        """
        self.repo_path = Path(repo_path).resolve()
        if not (self.repo_path / ".git").exists():
            raise ValueError(f"No valid .git directory found at '{self.repo_path}'.")

    def _convert_modification(self, mod) -> FileChangeRecord:
        """Convert a PyDriller modification object into a FileChangeRecord.
        Args:
            mod: Raw PyDriller modification object.
        Returns:
            FileChangeRecord: Clean domain record.
        """
        domain_change_type = _PYDRILLER_CHANGE_TYPE_MAP.get(mod.change_type, ChangeType.UNKNOWN)

        return FileChangeRecord(
            old_path=mod.old_path,
            new_path=mod.new_path,
            change_type=domain_change_type,
            added_lines=mod.added_lines or 0,
            deleted_lines=mod.deleted_lines or 0,
        )
    def mine_commits(
            self,
            max_commits: int | None = None,
            include_merges: bool = True,
            order: str = "chronological",
    ) -> Iterator[CommitRecord]:
        """Stream commits lazily from the Git repository.
        Args:
            max_commits: Maximum number of commits to yield (None for all).
            include_merges: Whether to include merge commits in the stream.
            order: Commit order ('chronological' or 'reverse').
        Yields:
            CommitRecord: Domain commit objects yielded sequentially.
        """
        order_flag = order == "reverse"

        repo_walker = Repository(
            str(self.repo_path),
            order="reverse" if order_flag else None,
        )

        count = 0
        for commit in repo_walker.traverse_commits():
            is_merge = len(commit.parents) > 1

            if not include_merges and is_merge:
                continue

            file_changes = tuple(self._convert_modification(mod) for mod in commit.modified_files)

            record = CommitRecord(
                hash=commit.hash,
                author_name=commit.author.name or "Unknown",
                author_email=commit.author.email or "unknown@example.com",
                committed_at=commit.committer_date,
                message=commit.msg.strip(),
                is_merge=is_merge,
                parents=tuple(commit.parents),
                file_changes=file_changes,
            )

            yield record
            count += 1

            if max_commits is not None and count >= max_commits:
                break


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    # Test miner against the locally cloned Hello-World repository from Step 2
    local_repo = Path("data/repositories/github.com/octocat/Hello-World")
    if not local_repo.exists():
        print(f"Repository not found at {local_repo}. Please run Step 2 first.")
    else:
        print(f"--- Mining Commits from {local_repo} ---")
        miner = GitRepositoryMiner(local_repo)
        commit_count = 0
        for mined_commit in miner.mine_commits(max_commits=10):
            commit_count += 1
            print(f"\n[{commit_count}] Commit: {mined_commit.hash[:8]} | Date: {mined_commit.committed_at}")
            print(f"    Author : {mined_commit.author_name}")
            print(f"    Message: {mined_commit.message}")
            print(f"    Churn  : +{mined_commit.total_lines_added} / -{mined_commit.total_lines_deleted} lines across {mined_commit.modified_file_count} files")
            for change in mined_commit.file_changes:
                print(f"      -> [{change.change_type.value}] {change.path}")