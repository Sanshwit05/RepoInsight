"""Behavioral hotspot detection combining static complexity and Git churn telemetry."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from enum import Enum

from src.repoinsight.analysis.scanner import RepositoryAnalysisSnapshot
from src.repoinsight.health.churn import RepositoryChurnSummary

logger = logging.getLogger(__name__)


class HotspotRiskTier(str, Enum):
    """Categorical risk classification for repository files."""

    CRITICAL = "CRITICAL"  # High complexity + high churn (urgent refactoring candidate)
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    HEALTHY = "HEALTHY"


@dataclass(frozen=True)
class HotspotItem:
    """Individual file hotspot evaluation record."""

    file_path: str
    sloc: int
    avg_complexity: float
    total_churn: int
    commit_count: int
    normalized_complexity: float
    normalized_churn: float
    hotspot_score: float
    risk_tier: HotspotRiskTier
    recommendation: str


@dataclass(frozen=True)
class HotspotAnalysisReport:
    """Aggregated hotspot analysis and technical debt report."""

    total_files_analyzed: int
    hotspots: tuple[HotspotItem, ...]
    critical_count: int
    high_count: int
    average_hotspot_score: float


class HotspotDetector:
    """Calculates behavioral hotspot metrics across repository files."""

    @staticmethod
    def _classify_risk(score: float) -> tuple[HotspotRiskTier, str]:
        """Classify hotspot score into an actionable risk tier and recommendation."""
        if score >= 0.70:
            return (
                HotspotRiskTier.CRITICAL,
                "URGENT: High complexity combined with heavy modification frequency. Target for modular refactoring.",
            )
        if score >= 0.50:
            return (
                HotspotRiskTier.HIGH,
                "WARNING: Active volatility in complex module. Require strict code review and add regression tests.",
            )
        if score >= 0.30:
            return (
                HotspotRiskTier.MODERATE,
                "MODERATE: Moderate churn. Monitor during upcoming contribution sprints.",
            )
        return (
            HotspotRiskTier.HEALTHY,
            "HEALTHY: Low evolutionary risk. Maintain current standards.",
        )

    def detect(
        self,
        snapshot: RepositoryAnalysisSnapshot,
        churn_summary: RepositoryChurnSummary,
    ) -> HotspotAnalysisReport:
        """Detect and rank architectural hotspots by joining AST complexity and Git churn.

        Args:
            snapshot: Static code analysis snapshot.
            churn_summary: Historical Git churn summary.

        Returns:
            HotspotAnalysisReport: Prioritized hotspot diagnosis.
        """
        all_files = set(snapshot.file_results.keys()) | set(churn_summary.file_churns.keys())
        if not all_files:
            return HotspotAnalysisReport(
                total_files_analyzed=0,
                hotspots=(),
                critical_count=0,
                high_count=0,
                average_hotspot_score=0.0,
            )

        # 1. Collect raw values
        file_complexities: dict[str, float] = {}
        file_churns: dict[str, int] = {}
        file_slocs: dict[str, int] = {}
        file_commits: dict[str, int] = {}

        for path in all_files:
            ast_res = snapshot.file_results.get(path)
            churn_rec = churn_summary.file_churns.get(path)

            comp = ast_res.average_function_complexity if ast_res else 1.0
            sloc = ast_res.sloc if ast_res else 0
            churn = churn_rec.total_churn if churn_rec else 0
            commits = churn_rec.commit_count if churn_rec else 0

            file_complexities[path] = comp
            file_slocs[path] = sloc
            file_churns[path] = churn
            file_commits[path] = commits

        # 2. Compute min-max boundaries for normalization
        max_comp = max(file_complexities.values(), default=1.0)
        min_comp = min(file_complexities.values(), default=1.0)
        max_churn = max(file_churns.values(), default=1)
        min_churn = min(file_churns.values(), default=0)

        comp_range = max(1e-5, max_comp - min_comp)
        churn_range = max(1e-5, max_churn - min_churn)

        # 3. Compute normalized scores and geometric mean
        hotspot_items: list[HotspotItem] = []
        for path in all_files:
            norm_comp = (file_complexities[path] - min_comp) / comp_range
            norm_churn = (file_churns[path] - min_churn) / churn_range

            # Geometric mean: sqrt(norm_comp * norm_churn)
            hotspot_score = round(math.sqrt(norm_comp * norm_churn), 4)
            risk_tier, rec = self._classify_risk(hotspot_score)

            hotspot_items.append(
                HotspotItem(
                    file_path=path,
                    sloc=file_slocs[path],
                    avg_complexity=round(file_complexities[path], 2),
                    total_churn=file_churns[path],
                    commit_count=file_commits[path],
                    normalized_complexity=round(norm_comp, 3),
                    normalized_churn=round(norm_churn, 3),
                    hotspot_score=hotspot_score,
                    risk_tier=risk_tier,
                    recommendation=rec,
                )
            )

        # Sort descending by hotspot score
        hotspot_items.sort(key=lambda h: (h.hotspot_score, h.total_churn), reverse=True)

        critical_count = sum(1 for h in hotspot_items if h.risk_tier == HotspotRiskTier.CRITICAL)
        high_count = sum(1 for h in hotspot_items if h.risk_tier == HotspotRiskTier.HIGH)
        avg_score = (
            round(sum(h.hotspot_score for h in hotspot_items) / len(hotspot_items), 3)
            if hotspot_items
            else 0.0
        )

        logger.info(
            "Hotspot detection completed: %d files analyzed (%d critical, %d high).",
            len(hotspot_items),
            critical_count,
            high_count,
        )

        return HotspotAnalysisReport(
            total_files_analyzed=len(hotspot_items),
            hotspots=tuple(hotspot_items),
            critical_count=critical_count,
            high_count=high_count,
            average_hotspot_score=avg_score,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("--- Demonstrating Hotspot Detection Engine ---")
    from src.repoinsight.analysis.scanner import RepositoryScanner
    from src.repoinsight.health.churn import ChurnAggregator
    from src.repoinsight.mining.miner import GitRepositoryMiner
    from pathlib import Path

    # Scan current repo static AST metrics
    scanner = RepositoryScanner()
    snapshot = scanner.scan(".")

    # Aggregate churn from cloned sample or mock
    local_repo = Path("data/repositories/github.com/octocat/Hello-World")
    if local_repo.exists():
        miner = GitRepositoryMiner(local_repo)
        churn_summary = ChurnAggregator().aggregate(miner.mine_commits())
    else:
        churn_summary = ChurnAggregator().aggregate([])

    detector = HotspotDetector()
    report = detector.detect(snapshot, churn_summary)

    print(f"\n[OK] Files Analyzed     : {report.total_files_analyzed}")
    print(f"[OK] Critical Hotspots  : {report.critical_count}")
    print(f"[OK] High Risk Hotspots : {report.high_count}")
    print(f"[OK] Avg Hotspot Score  : {report.average_hotspot_score:.3f}")

    print("\n--- Hotspot Ranking Sample ---")
    for h in report.hotspots[:5]:
        print(f"  * [{h.risk_tier.value:<8s}] {h.file_path:<35s} | Score: {h.hotspot_score:.3f} (Comp:{h.avg_complexity} | Churn:{h.total_churn})")
        print(f"    -> {h.recommendation}")