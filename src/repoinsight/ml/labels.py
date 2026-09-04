"""Empirical ground-truth label formulation and forward-looking impact generator."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import IntEnum

from src.repoinsight.mining.models import CommitRecord

logger = logging.getLogger(__name__)

# Pattern to detect bug-fix, revert, or corrective follow-up commits
_FIX_COMMIT_PATTERN = re.compile(
    r"\b(?:fix|fixes|fixed|bug|revert|hotfix|patch|repair|regression|issue)\b",
    re.IGNORECASE,
)


class RiskLevel(IntEnum):
    """Categorical risk tiers for contribution impact classification."""

    LOW = 0
    MEDIUM = 1
    HIGH = 2

    @classmethod
    def from_score(cls, score: float) -> RiskLevel:
        """Map continuous impact score [0.0, 1.0] to discrete risk level."""
        if score >= 0.60:
            return cls.HIGH
        if score >= 0.25:
            return cls.MEDIUM
        return cls.LOW


@dataclass(frozen=True)
class ContributionImpactLabel:
    """Ground-truth impact labels and forward-looking observables for a historical change."""

    commit_hash: str
    impact_score: float  # Continuous regression target [0.0, 1.0]
    risk_level: RiskLevel  # Discrete 3-class classification target (0, 1, 2)
    subsequent_affected_files_count: int
    subsequent_churn: int
    has_followup_fix: bool
    affected_files_sample: tuple[str, ...]


class ImpactLabelGenerator:
    """Derives defensible ground-truth labels from future historical commit windows."""

    def __init__(self, forward_window_size: int = 15) -> None:
        """Initialize generator with the forward commit observation window size.

        Args:
            forward_window_size: Number of subsequent commits to evaluate for downstream ripple.
        """
        self.window_size = forward_window_size

    def generate_labels(
        self,
        commits: list[CommitRecord],
    ) -> dict[str, ContributionImpactLabel]:
        """Compute forward-looking impact labels for each commit in historical sequence.

        Args:
            commits: List of CommitRecord objects in strict chronological order.

        Returns:
            dict: Mapping of commit_hash -> ContributionImpactLabel.
        """
        total_commits = len(commits)
        labels: dict[str, ContributionImpactLabel] = {}

        if total_commits == 0:
            return labels

        for i in range(total_commits):
            current_commit = commits[i]
            current_files = {fc.path for fc in current_commit.file_changes if fc.path}

            if not current_files:
                continue

            # Forward window: look ahead up to window_size subsequent commits
            forward_window = commits[i + 1 : i + 1 + self.window_size]

            affected_downstream_files: set[str] = set()
            subsequent_churn = 0
            has_followup_fix = False

            for next_commit in forward_window:
                next_files = {fc.path for fc in next_commit.file_changes if fc.path}
                
                # Intersection: files modified in current commit that required follow-up changes
                overlapping_files = current_files & next_files
                if overlapping_files:
                    affected_downstream_files.update(overlapping_files)
                    subsequent_churn += sum(
                        fc.churn for fc in next_commit.file_changes if fc.path in overlapping_files
                    )
                    if _FIX_COMMIT_PATTERN.search(next_commit.message):
                        has_followup_fix = True

                # Also capture all files co-changed alongside these modules in the window
                if overlapping_files:
                    affected_downstream_files.update(next_files)

            # --- Multi-Signal Normalization ---
            # 1. Ripple ratio (files touched in window / max active files reference)
            file_ripple_count = len(affected_downstream_files)
            norm_ripple = min(1.0, file_ripple_count / 10.0)

            # 2. Churn ratio (subsequent lines touched)
            norm_churn = min(1.0, subsequent_churn / 200.0)

            # 3. Corrective fix signal
            fix_signal = 1.0 if has_followup_fix else 0.0

            # Composite continuous score in [0.0, 1.0]
            impact_score = round(
                min(1.0, 0.50 * norm_ripple + 0.30 * norm_churn + 0.20 * fix_signal),
                4,
            )
            risk_level = RiskLevel.from_score(impact_score)

            labels[current_commit.hash] = ContributionImpactLabel(
                commit_hash=current_commit.hash,
                impact_score=impact_score,
                risk_level=risk_level,
                subsequent_affected_files_count=file_ripple_count,
                subsequent_churn=subsequent_churn,
                has_followup_fix=has_followup_fix,
                affected_files_sample=tuple(sorted(affected_downstream_files)[:5]),
            )

        logger.info(
            "Generated ground-truth impact labels for %d commits (Window size=%d).",
            len(labels),
            self.window_size,
        )
        return labels


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("--- Demonstrating Impact Label Generator on Simulated History ---")
    from datetime import datetime, timezone
    from src.repoinsight.mining.models import ChangeType, FileChangeRecord

    # Create a simulated sequence of commits
    mock_commits = [
        CommitRecord(
            hash="c1",
            author_name="Alice",
            author_email="alice@example.com",
            committed_at=datetime.now(timezone.utc),
            message="feat: core architecture changes",
            is_merge=False,
            file_changes=(FileChangeRecord(None, "src/core.py", ChangeType.MODIFY, 120, 20),),
        ),
        CommitRecord(
            hash="c2",
            author_name="Bob",
            author_email="bob@example.com",
            committed_at=datetime.now(timezone.utc),
            message="fix(core): hotfix regression in core engine",
            is_merge=False,
            file_changes=(FileChangeRecord("src/core.py", "src/core.py", ChangeType.MODIFY, 15, 5),),
        ),
        CommitRecord(
            hash="c3",
            author_name="Charlie",
            author_email="charlie@example.com",
            committed_at=datetime.now(timezone.utc),
            message="docs: update readme instructions",
            is_merge=False,
            file_changes=(FileChangeRecord("README.md", "README.md", ChangeType.MODIFY, 5, 1),),
        ),
    ]

    generator = ImpactLabelGenerator(forward_window_size=2)
    labels = generator.generate_labels(mock_commits)

    for chash, lbl in labels.items():
        print(f"\n[OK] Commit: {chash}")
        print(f"     Impact Score  : {lbl.impact_score:.4f} -> Risk Level: {lbl.risk_level.name} ({lbl.risk_level.value})")
        print(f"     Ripple Files  : {lbl.subsequent_affected_files_count} | Follow-up Churn: {lbl.subsequent_churn}")
        print(f"     Follow-up Fix : {lbl.has_followup_fix}")