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

    CRITICAL = "CRITICAL"  # High complexity + high churn
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
    moderate_count: int
    average_hotspot_score: float


class HotspotDetector:
    """Calculates behavioral hotspot metrics across repository files."""

    @staticmethod
    def _classify_risk(score: float) -> tuple[HotspotRiskTier, str]:
        """Classify hotspot score into an actionable risk tier and recommendation."""
        if score >= 0.55:
            return (
                HotspotRiskTier.CRITICAL,
                "URGENT: High complexity combined with heavy modification frequency. Target for modular refactoring.",
            )
        if score >= 0.35:
            return (
                HotspotRiskTier.HIGH,
                "WARNING: Active volatility in complex module. Require strict code review and add regression tests.",
            )
        if score >= 0.15:
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
        """Detect and rank architectural hotspots by joining AST complexity and Git churn."""
        all_files = set(snapshot.file_results.keys()) | set(churn_summary.file_churns.keys())
        if not all_files:
            return HotspotAnalysisReport(
                total_files_analyzed=0,
                hotspots=(),
                critical_count=0,
                high_count=0,
                moderate_count=0,
                average_hotspot_score=0.0,
            )

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

        max_comp = max(file_complexities.values(), default=1.0)
        min_comp = min(file_complexities.values(), default=1.0)
        max_churn = max(file_churns.values(), default=1)
        min_churn = min(file_churns.values(), default=0)

        comp_range = max(1e-5, max_comp - min_comp)
        churn_range = max(1e-5, max_churn - min_churn)

        hotspot_items: list[HotspotItem] = []
        for path in all_files:
            norm_comp = (file_complexities[path] - min_comp) / comp_range
            norm_churn = (file_churns[path] - min_churn) / churn_range

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

        hotspot_items.sort(key=lambda h: (h.hotspot_score, h.total_churn), reverse=True)

        critical_count = sum(1 for h in hotspot_items if h.risk_tier == HotspotRiskTier.CRITICAL)
        high_count = sum(1 for h in hotspot_items if h.risk_tier == HotspotRiskTier.HIGH)
        moderate_count = sum(1 for h in hotspot_items if h.risk_tier == HotspotRiskTier.MODERATE)
        avg_score = (
            round(sum(h.hotspot_score for h in hotspot_items) / len(hotspot_items), 3)
            if hotspot_items
            else 0.0
        )

        return HotspotAnalysisReport(
            total_files_analyzed=len(hotspot_items),
            hotspots=tuple(hotspot_items),
            critical_count=critical_count,
            high_count=high_count,
            moderate_count=moderate_count,
            average_hotspot_score=avg_score,
        )