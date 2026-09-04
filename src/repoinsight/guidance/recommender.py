"""Deterministic contributor guidance, zone stratification, and review recommendations."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from src.repoinsight.analysis.scanner import RepositoryAnalysisSnapshot, RepositoryScanner
from src.repoinsight.graph.builder import DependencyGraphBuilder
from src.repoinsight.graph.metrics import GraphMetricsEngine, GraphTopologyReport
from src.repoinsight.health.churn import ChurnAggregator, RepositoryChurnSummary
from src.repoinsight.health.hotspots import HotspotAnalysisReport, HotspotDetector, HotspotRiskTier
from src.repoinsight.health.ownership import BusFactorReport, OwnershipEngine
from src.repoinsight.mining.miner import GitRepositoryMiner

logger = logging.getLogger(__name__)


class ContributorZone(str, Enum):
    """Architectural classification for contributor safety and onboarding."""

    BEGINNER_FRIENDLY = "BEGINNER_FRIENDLY"
    HIGH_RISK_CORE = "HIGH_RISK_CORE"
    HIGH_COUPLING = "HIGH_COUPLING"
    SINGLE_MAINTAINER_SILO = "SINGLE_MAINTAINER_SILO"
    ACTIVE_VOLATILE = "ACTIVE_VOLATILE"
    DORMANT_STABLE = "DORMANT_STABLE"
    STANDARD = "STANDARD"


class ReviewDifficulty(str, Enum):
    """Estimated difficulty and scrutiny required for code reviews."""

    EASY = "EASY"
    MODERATE = "MODERATE"
    HARD = "HARD"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class FileGuidance:
    """Actionable contributor guidance and review advice for a specific file."""

    file_path: str
    zone: ContributorZone
    review_difficulty: ReviewDifficulty
    primary_owner: str
    in_degree: int
    avg_complexity: float
    hotspot_score: float
    is_siloed: bool
    advice: str


@dataclass(frozen=True)
class RepositoryGuidanceReport:
    """Aggregated contributor guidance and onboarding report for the repository."""

    total_files: int
    beginner_friendly_files: tuple[FileGuidance, ...] = field(default_factory=tuple)
    high_risk_core_files: tuple[FileGuidance, ...] = field(default_factory=tuple)
    siloed_files: tuple[FileGuidance, ...] = field(default_factory=tuple)
    all_guidance: dict[str, FileGuidance] = field(default_factory=dict)
    onboarding_summary: str = ""


class ContributorGuidanceEngine:
    """Evaluates multi-pillar metrics to generate deterministic contributor recommendations."""

    def generate_guidance(
        self,
        snapshot: RepositoryAnalysisSnapshot,
        graph_report: GraphTopologyReport,
        churn_summary: RepositoryChurnSummary,
        hotspot_report: HotspotAnalysisReport,
        bus_report: BusFactorReport,
    ) -> RepositoryGuidanceReport:
        """Generate comprehensive contributor advice for all files in the repository.

        Args:
            snapshot: Static AST analysis snapshot.
            graph_report: Topological graph metrics.
            churn_summary: Historical Git churn summary.
            hotspot_report: Hotspot and technical debt analysis.
            bus_report: Contributor ownership and Bus Factor report.

        Returns:
            RepositoryGuidanceReport: Complete developer onboarding and risk guide.
        """
        all_files = set(snapshot.file_results.keys())
        guidance_map: dict[str, FileGuidance] = {}

        # Pre-index hotspot scores for O(1) lookup
        hotspot_map = {h.file_path: h for h in hotspot_report.hotspots}

        for path in all_files:
            ast_res = snapshot.file_results.get(path)
            node_m = graph_report.node_metrics.get(path)
            churn_m = churn_summary.file_churns.get(path)
            own_m = bus_report.file_profiles.get(path)
            hot_m = hotspot_map.get(path)

            in_deg = node_m.in_degree if node_m else 0
            out_deg = node_m.out_degree if node_m else 0
            comp = ast_res.average_function_complexity if ast_res else 1.0
            hot_score = hot_m.hotspot_score if hot_m else 0.0
            is_silo = own_m.is_siloed if own_m else False
            owner = own_m.primary_owner_name if own_m else "Unassigned"
            total_churn = churn_m.total_churn if churn_m else 0

            # --- Deterministic Zone Stratification Rules ---
            if hot_m and hot_m.risk_tier == HotspotRiskTier.CRITICAL:
                zone = ContributorZone.HIGH_RISK_CORE
                difficulty = ReviewDifficulty.CRITICAL
                advice = "CRITICAL HOTSPOT: High complexity combined with heavy churn. Significant risk of regression."
            elif in_deg >= 3 or path in graph_report.top_hubs:
                zone = ContributorZone.HIGH_RISK_CORE
                difficulty = ReviewDifficulty.CRITICAL
                advice = f"ARCHITECTURAL HUB: Depended upon by {in_deg} modules. Changes create wide downstream ripple effects."
            elif out_deg >= 4 or (node_m and node_m.betweenness_centrality >= 0.15):
                zone = ContributorZone.HIGH_COUPLING
                difficulty = ReviewDifficulty.HARD
                advice = f"HIGH COUPLING: Imports {out_deg} modules. Test integration contracts thoroughly."
            elif is_silo:
                zone = ContributorZone.SINGLE_MAINTAINER_SILO
                difficulty = ReviewDifficulty.HARD
                advice = f"KNOWLEDGE SILO: Maintained primarily by {owner} ({own_m.primary_owner_share*100:.0f}% ownership). Request review from {owner}."
            elif in_deg <= 1 and comp <= 2.5 and hot_score <= 0.20:
                zone = ContributorZone.BEGINNER_FRIENDLY
                difficulty = ReviewDifficulty.EASY
                advice = "BEGINNER FRIENDLY: Low coupling, low complexity, and low ripple risk. Excellent entry point for new contributors."
            elif total_churn > 100:
                zone = ContributorZone.ACTIVE_VOLATILE
                difficulty = ReviewDifficulty.MODERATE
                advice = "ACTIVE AREA: Frequently modified. Rebase frequently against main branch to prevent merge conflicts."
            elif total_churn == 0 and comp <= 2.0:
                zone = ContributorZone.DORMANT_STABLE
                difficulty = ReviewDifficulty.EASY
                advice = "STABLE MODULE: Proven stability with no recent churn. Keep modifications minimal and focused."
            else:
                zone = ContributorZone.STANDARD
                difficulty = ReviewDifficulty.MODERATE
                advice = "STANDARD MODULE: Follow standard pull request review guidelines and unit tests."

            guidance_map[path] = FileGuidance(
                file_path=path,
                zone=zone,
                review_difficulty=difficulty,
                primary_owner=owner,
                in_degree=in_deg,
                avg_complexity=round(comp, 2),
                hotspot_score=round(hot_score, 3),
                is_siloed=is_silo,
                advice=advice,
            )

        beginner_list = tuple(
            g for g in guidance_map.values() if g.zone == ContributorZone.BEGINNER_FRIENDLY
        )
        high_risk_list = tuple(
            g for g in guidance_map.values() if g.zone == ContributorZone.HIGH_RISK_CORE
        )
        siloed_list = tuple(
            g for g in guidance_map.values() if g.zone == ContributorZone.SINGLE_MAINTAINER_SILO
        )

        onboarding_summary = (
            f"Repository contains {len(beginner_list)} beginner-friendly entry points, "
            f"{len(high_risk_list)} high-risk architectural core modules, and "
            f"{len(siloed_list)} single-maintainer knowledge silos."
        )

        logger.info(
            "Contributor guidance generated: %d files (Beginner: %d, High Risk: %d, Siloed: %d)",
            len(guidance_map),
            len(beginner_list),
            len(high_risk_list),
            len(siloed_list),
        )

        return RepositoryGuidanceReport(
            total_files=len(guidance_map),
            beginner_friendly_files=beginner_list,
            high_risk_core_files=high_risk_list,
            siloed_files=siloed_list,
            all_guidance=guidance_map,
            onboarding_summary=onboarding_summary,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("================================================================")
    print("      REPOINSIGHT AI — CONTRIBUTOR GUIDANCE REPORT             ")
    print("================================================================")

    # 1. Collect all underlying reports
    root = Path(".")
    scanner = RepositoryScanner()
    snapshot = scanner.scan(root)

    builder = DependencyGraphBuilder()
    graph = builder.build_graph(snapshot)
    graph_report = GraphMetricsEngine().compute_metrics(graph)

    miner = GitRepositoryMiner(root) if (root / ".git").exists() else None
    commits = list(miner.mine_commits(max_commits=200)) if miner else []

    churn_summary = ChurnAggregator().aggregate(commits)
    hotspot_report = HotspotDetector().detect(snapshot, churn_summary)
    bus_report = OwnershipEngine().compute(commits)

    # 2. Run Contributor Guidance Engine
    engine = ContributorGuidanceEngine()
    report = engine.generate_guidance(
        snapshot,
        graph_report,
        churn_summary,
        hotspot_report,
        bus_report,
    )

    print(f"\n[OK] Onboarding Summary: {report.onboarding_summary}")

    print("\n--- 🟢 Recommended Beginner-Friendly Files ---")
    for g in report.beginner_friendly_files[:3]:
        print(f"  * {g.file_path:<35s} | Difficulty: {g.review_difficulty.value:<8s} | Comp: {g.avg_complexity}")
        print(f"    -> {g.advice}")

    print("\n--- 🔴 High-Risk Core Modules (Require Senior Review) ---")
    for g in report.high_risk_core_files[:3]:
        print(f"  * {g.file_path:<35s} | In-Degree: {g.in_degree:<2d} | Difficulty: {g.review_difficulty.value}")
        print(f"    -> {g.advice}")

    print("\n--- 🟡 Knowledge Siloed Modules ---")
    for g in report.siloed_files[:3]:
        print(f"  * {g.file_path:<35s} | Primary Owner: {g.primary_owner}")
        print(f"    -> {g.advice}")