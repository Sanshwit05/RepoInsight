"""Contributor knowledge concentration, silo detection, and Bus Factor calculation."""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from src.repoinsight.mining.models import CommitRecord

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthorShare:
    """Author contribution share for a specific file or repository."""

    author_email: str
    author_name: str
    commit_count: int
    ownership_ratio: float


@dataclass(frozen=True)
class FileOwnershipProfile:
    """Ownership distribution and knowledge silo classification for an individual file."""

    file_path: str
    total_commits: int
    author_count: int
    primary_owner_email: str
    primary_owner_name: str
    primary_owner_share: float
    is_siloed: bool
    author_shares: tuple[AuthorShare, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class BusFactorReport:
    """Aggregated repository-wide contributor concentration and Bus Factor diagnosis."""

    bus_factor: int
    key_maintainers: tuple[str, ...]
    gini_coefficient: float
    total_contributors: int
    siloed_files_count: int
    total_active_files: int
    siloed_ratio: float
    risk_level: str
    file_profiles: dict[str, FileOwnershipProfile] = field(default_factory=dict)


class OwnershipEngine:
    """Calculates author knowledge distribution, siloed files, and the repository Bus Factor."""

    def __init__(self, silo_threshold: float = 0.70) -> None:
        self.silo_threshold = silo_threshold

    @staticmethod
    def _compute_gini(values: list[float]) -> float:
        """Calculate Gini coefficient of inequality for an array of values."""
        if not values or len(values) <= 1 or sum(values) == 0:
            return 0.0

        sorted_vals = sorted(values)
        n = len(sorted_vals)
        total_sum = sum(sorted_vals)

        weighted_sum = 0.0
        for i, val in enumerate(sorted_vals, 1):
            weighted_sum += i * val

        gini = (2.0 * weighted_sum) / (n * total_sum) - (n + 1.0) / n
        return round(max(0.0, min(1.0, gini)), 3)

    def compute(self, commits: Iterable[CommitRecord]) -> BusFactorReport:
        """Compute ownership profiles, Gini concentration, and the empirical Bus Factor."""
        file_author_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        author_names: dict[str, str] = {}
        repo_author_counts: dict[str, int] = defaultdict(int)

        for commit in commits:
            author_email = commit.author_email
            author_names[author_email] = commit.author_name
            repo_author_counts[author_email] += 1

            for change in commit.file_changes:
                path = change.path
                if path and path != "unknown_path":
                    # Normalize path slashes
                    norm_p = path.replace("\\", "/").lstrip("./")
                    file_author_counts[norm_p][author_email] += 1

        if not file_author_counts:
            return BusFactorReport(
                bus_factor=0,
                key_maintainers=(),
                gini_coefficient=0.0,
                total_contributors=len(repo_author_counts),
                siloed_files_count=0,
                total_active_files=0,
                siloed_ratio=0.0,
                risk_level="UNKNOWN",
            )

        # 1. Build File Ownership Profiles
        file_profiles: dict[str, FileOwnershipProfile] = {}
        file_authors_map: dict[str, set[str]] = {}
        siloed_files = 0

        for path, authors in file_author_counts.items():
            total_file_commits = sum(authors.values())
            shares_list: list[AuthorShare] = []

            for email, count in sorted(authors.items(), key=lambda x: x[1], reverse=True):
                ratio = count / total_file_commits
                shares_list.append(
                    AuthorShare(
                        author_email=email,
                        author_name=author_names.get(email, email),
                        commit_count=count,
                        ownership_ratio=round(ratio, 3),
                    )
                )

            top_share = shares_list[0]
            is_siloed = top_share.ownership_ratio >= self.silo_threshold
            if is_siloed:
                siloed_files += 1

            # Authors with >= 20% contribution have maintenance knowledge
            knowledge_authors = {
                email for email, count in authors.items() if (count / total_file_commits) >= 0.20
            }
            file_authors_map[path] = knowledge_authors or {top_share.author_email}

            file_profiles[path] = FileOwnershipProfile(
                file_path=path,
                total_commits=total_file_commits,
                author_count=len(authors),
                primary_owner_email=top_share.author_email,
                primary_owner_name=top_share.author_name,
                primary_owner_share=top_share.ownership_ratio,
                is_siloed=is_siloed,
                author_shares=tuple(shares_list),
            )

        # 2. True Rigby/Avelino Bus Factor: Minimum authors whose departure leaves > 50% files orphaned
        total_files = len(file_profiles)
        target_orphaned = total_files * 0.50

        # Rank authors by total commits
        sorted_authors = [
            email for email, _ in sorted(repo_author_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        removed_authors: set[str] = set()
        key_maintainers: list[str] = []

        for email in sorted_authors:
            removed_authors.add(email)
            key_maintainers.append(author_names.get(email, email))

            # Count how many files have ZERO remaining knowledge authors
            orphaned_count = sum(
                1 for path, authors in file_authors_map.items() if authors.issubset(removed_authors)
            )

            if orphaned_count >= target_orphaned or len(removed_authors) == len(sorted_authors):
                break

        bus_factor = max(1, len(key_maintainers))
        gini = self._compute_gini(list(repo_author_counts.values()))
        silo_ratio = round(siloed_files / total_files, 3)

        if bus_factor == 1:
            risk = "CRITICAL (Single Point of Failure)"
        elif bus_factor == 2:
            risk = "HIGH (Fragile Maintainership)"
        elif bus_factor <= 4:
            risk = "MODERATE"
        else:
            risk = "HEALTHY"

        return BusFactorReport(
            bus_factor=bus_factor,
            key_maintainers=tuple(key_maintainers),
            gini_coefficient=gini,
            total_contributors=len(repo_author_counts),
            siloed_files_count=siloed_files,
            total_active_files=total_files,
            siloed_ratio=silo_ratio,
            risk_level=risk,
            file_profiles=file_profiles,
        )