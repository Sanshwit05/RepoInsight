"""Historical code churn, change frequency, and file volatility analytics."""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from src.repoinsight.mining.miner import GitRepositoryMiner
from src.repoinsight.mining.models import CommitRecord

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FileChurnRecord:
    """Aggregated historical churn metrics for an individual file."""

    file_path: str
    commit_count: int
    lines_added: int
    lines_deleted: int
    total_churn: int
    unique_authors: tuple[str, ...]
    first_committed_at: datetime | None = None
    last_committed_at: datetime | None = None

    @property
    def author_count(self) -> int:
        """Number of unique authors who modified this file."""
        return len(self.unique_authors)

    @property
    def net_line_growth(self) -> int:
        """Net line expansion (added - deleted)."""
        return self.lines_added - self.lines_deleted


@dataclass(frozen=True)
class RepositoryChurnSummary:
    """Macro-level repository churn and activity metrics."""

    total_commits: int
    total_lines_added: int
    total_lines_deleted: int
    total_churn: int
    active_files_count: int
    file_churns: dict[str, FileChurnRecord] = field(default_factory=dict)
    top_churned_files: tuple[str, ...] = field(default_factory=tuple)


class ChurnAggregator:
    """Aggregates Git commit streams into structured per-file churn telemetry."""

    def aggregate(self, commits: Iterable[CommitRecord]) -> RepositoryChurnSummary:
        """Process a stream of commits and calculate cumulative churn metrics.

        Args:
            commits: Iterable sequence of CommitRecord instances.

        Returns:
            RepositoryChurnSummary: Complete historical churn analysis.
        """
        file_commit_counts: dict[str, int] = defaultdict(int)
        file_lines_added: dict[str, int] = defaultdict(int)
        file_lines_deleted: dict[str, int] = defaultdict(int)
        file_authors: dict[str, set[str]] = defaultdict(set)
        file_first_date: dict[str, datetime] = {}
        file_last_date: dict[str, datetime] = {}

        total_commits = 0
        total_repo_added = 0
        total_repo_deleted = 0

        for commit in commits:
            total_commits += 1
            total_repo_added += commit.total_lines_added
            total_repo_deleted += commit.total_lines_deleted

            for change in commit.file_changes:
                path = change.path
                if not path or path == "unknown_path":
                    continue

                file_commit_counts[path] += 1
                file_lines_added[path] += change.added_lines
                file_lines_deleted[path] += change.deleted_lines
                file_authors[path].add(commit.author_email)

                # Track temporal boundaries
                if path not in file_first_date or commit.committed_at < file_first_date[path]:
                    file_first_date[path] = commit.committed_at
                if path not in file_last_date or commit.committed_at > file_last_date[path]:
                    file_last_date[path] = commit.committed_at

        # Build immutable per-file records
        file_churn_records: dict[str, FileChurnRecord] = {}
        for path, count in file_commit_counts.items():
            added = file_lines_added[path]
            deleted = file_lines_deleted[path]
            file_churn_records[path] = FileChurnRecord(
                file_path=path,
                commit_count=count,
                lines_added=added,
                lines_deleted=deleted,
                total_churn=added + deleted,
                unique_authors=tuple(sorted(file_authors[path])),
                first_committed_at=file_first_date.get(path),
                last_committed_at=file_last_date.get(path),
            )

        # Identify files with highest total churn
        sorted_files = sorted(
            file_churn_records.values(),
            key=lambda fc: (fc.total_churn, fc.commit_count),
            reverse=True,
        )
        top_churned = tuple(fc.file_path for fc in sorted_files[:10])

        total_churn = total_repo_added + total_repo_deleted
        logger.info(
            "Churn aggregation finished: %d commits, %d files tracked, %d total churn.",
            total_commits,
            len(file_churn_records),
            total_churn,
        )

        return RepositoryChurnSummary(
            total_commits=total_commits,
            total_lines_added=total_repo_added,
            total_lines_deleted=total_repo_deleted,
            total_churn=total_churn,
            active_files_count=len(file_churn_records),
            file_churns=file_churn_records,
            top_churned_files=top_churned,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("--- Running Churn Aggregator on Test Repository ---")
    local_repo = Path("data/repositories/github.com/octocat/Hello-World")

    if not local_repo.exists():
        print("Cloned repository not found at data/repositories/github.com/octocat/Hello-World. Running standalone test...")
        # Standalone mock demonstration
        from datetime import datetime, timezone
        from src.repoinsight.mining.models import ChangeType, FileChangeRecord

        c1 = CommitRecord(
            hash="c1",
            author_name="Dev1",
            author_email="dev1@example.com",
            committed_at=datetime.now(timezone.utc),
            message="Initial commit",
            is_merge=False,
            file_changes=(
                FileChangeRecord(None, "src/main.py", ChangeType.ADD, 50, 0),
                FileChangeRecord(None, "src/config.py", ChangeType.ADD, 20, 0),
            ),
        )
        c2 = CommitRecord(
            hash="c2",
            author_name="Dev2",
            author_email="dev2@example.com",
            committed_at=datetime.now(timezone.utc),
            message="Refactor main logic",
            is_merge=False,
            file_changes=(
                FileChangeRecord("src/main.py", "src/main.py", ChangeType.MODIFY, 35, 10),
            ),
        )
        aggregator = ChurnAggregator()
        summary = aggregator.aggregate([c1, c2])
    else:
        miner = GitRepositoryMiner(local_repo)
        commits_stream = miner.mine_commits()
        aggregator = ChurnAggregator()
        summary = aggregator.aggregate(commits_stream)

    print(f"\n[OK] Commits Processed   : {summary.total_commits}")
    print(f"[OK] Total Lines Added   : +{summary.total_lines_added}")
    print(f"[OK] Total Lines Deleted : -{summary.total_lines_deleted}")
    print(f"[OK] Aggregate Churn     : {summary.total_churn}")
    print(f"[OK] Active Files Tracked: {summary.active_files_count}")

    print("\n--- Top Churned Files ---")
    for file_path in summary.top_churned_files:
        fc = summary.file_churns[file_path]
        print(f"  * {file_path:<30s} | Churn: {fc.total_churn:<4d} (+{fc.lines_added}/-{fc.lines_deleted}) | Commits: {fc.commit_count} | Authors: {fc.author_count}")