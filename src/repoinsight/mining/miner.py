"""Streaming Git repository miner with resilient fallback."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

from pydriller import ModificationType, Repository

from src.repoinsight.mining.models import ChangeType, CommitRecord, FileChangeRecord

logger = logging.getLogger(__name__)

# Map PyDriller modification types to our internal domain ChangeType enum
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
        """Initialize the miner with the target repository path."""
        self.repo_path = Path(repo_path).resolve()
        if not (self.repo_path / ".git").exists():
            raise ValueError(f"No valid .git directory found at '{self.repo_path}'.")

    def _convert_modification(self, mod) -> FileChangeRecord:
        """Convert a PyDriller modification object into a FileChangeRecord."""
        domain_change_type = _PYDRILLER_CHANGE_TYPE_MAP.get(
            mod.change_type, ChangeType.UNKNOWN
        )

        return FileChangeRecord(
            old_path=mod.old_path,
            new_path=mod.new_path,
            change_type=domain_change_type,
            added_lines=mod.added_lines or 0,
            deleted_lines=mod.deleted_lines or 0,
        )

    def _mine_with_git_cli(self, max_commits: int | None = None) -> Iterator[CommitRecord]:
        """Fallback commit extractor using native git log subprocess."""
        limit_args = ["-n", str(max_commits)] if max_commits else []
        cmd = ["git", "log"] + limit_args + ["--format=COMMIT:%H|%an|%ae|%aI|%s", "--numstat"]

        try:
            res = subprocess.run(cmd, cwd=str(self.repo_path), capture_output=True, text=True, check=False)
            if res.returncode != 0:
                return

            current_commit: dict | None = None
            changes: list[FileChangeRecord] = []

            for line in res.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue

                if line.startswith("COMMIT:"):
                    if current_commit:
                        yield CommitRecord(
                            hash=current_commit["hash"],
                            author_name=current_commit["name"],
                            author_email=current_commit["email"],
                            committed_at=current_commit["date"],
                            message=current_commit["msg"],
                            is_merge=False,
                            file_changes=tuple(changes),
                        )
                        changes = []

                    parts = line[7:].split("|", 4)
                    if len(parts) >= 5:
                        try:
                            dt = datetime.fromisoformat(parts[3])
                        except Exception:
                            dt = datetime.now(timezone.utc)

                        current_commit = {
                            "hash": parts[0],
                            "name": parts[1],
                            "email": parts[2],
                            "date": dt,
                            "msg": parts[4],
                        }
                elif current_commit and "\t" in line:
                    # numstat line: added \t deleted \t filename
                    num_parts = line.split("\t")
                    if len(num_parts) >= 3:
                        add_cnt = int(num_parts[0]) if num_parts[0].isdigit() else 0
                        del_cnt = int(num_parts[1]) if num_parts[1].isdigit() else 0
                        fpath = num_parts[2]
                        changes.append(
                            FileChangeRecord(
                                old_path=fpath,
                                new_path=fpath,
                                change_type=ChangeType.MODIFY,
                                added_lines=add_cnt,
                                deleted_lines=del_cnt,
                            )
                        )

            if current_commit:
                yield CommitRecord(
                    hash=current_commit["hash"],
                    author_name=current_commit["name"],
                    author_email=current_commit["email"],
                    committed_at=current_commit["date"],
                    message=current_commit["msg"],
                    is_merge=False,
                    file_changes=tuple(changes),
                )
        except Exception as exc:
            logger.error("Git CLI fallback failed: %s", exc)

    def mine_commits(
        self,
        max_commits: int | None = None,
        include_merges: bool = True,
        order: str = "chronological",
    ) -> Iterator[CommitRecord]:
        """Stream commits lazily from the Git repository."""
        try:
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

                file_changes = tuple(
                    self._convert_modification(mod) for mod in commit.modified_files
                )

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
        except Exception as exc:
            logger.warning("PyDriller encountered an issue (%s). Switching to native Git CLI miner fallback...", exc)
            yield from self._mine_with_git_cli(max_commits=max_commits)