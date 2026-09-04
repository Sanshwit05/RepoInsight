"""Master repository health engine and composite maintainability index calculator."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from src.repoinsight.analysis.scanner import RepositoryAnalysisSnapshot, RepositoryScanner
from src.repoinsight.graph.builder import DependencyGraphBuilder
from src.repoinsight.graph.metrics import GraphMetricsEngine, GraphTopologyReport
from src.repoinsight.health.churn import ChurnAggregator, RepositoryChurnSummary
from src.repoinsight.health.hotspots import HotspotAnalysisReport, HotspotDetector
from src.repoinsight.health.ownership import BusFactorReport, OwnershipEngine
from src.repoinsight.mining.miner import GitRepositoryMiner

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HealthSubScores:
    """Individual mathematical components of the repository health score (0-100)."""

    complexity_score: float
    hotspot_score: float
    architecture_score: float
    ownership_score: float


@dataclass(frozen=True)
class RepositoryHealthReport:
    """Consolidated executive health diagnosis for a software repository."""

    repo_path: str
    overall_score: float
    grade: str  # A+, A, B, C, D, F
    sub_scores: HealthSubScores
    total_files: int
    total_sloc: int
    total_commits: int
    bus_factor: int
    critical_hotspots_count: int
    circular_dependencies_count: int
    key_findings: tuple[str, ...] = field(default_factory=tuple)


class RepositoryHealthEngine:
    """Orchestrates all deterministic static, graph, churn, and ownership analytics."""

    def __init__(self) -> None:
        self.scanner = RepositoryScanner()
        self.graph_builder = DependencyGraphBuilder()
        self.graph_metrics = GraphMetricsEngine()
        self.churn_aggregator = ChurnAggregator()
        self.hotspot_detector = HotspotDetector()
        self.ownership_engine = OwnershipEngine()

    @staticmethod
    def _calculate_grade(score: float) -> str:
        """Convert a 0-100 continuous score into an academic letter grade."""
        if score >= 95:
            return "A+"
        if score >= 85:
            return "A"
        if score >= 75:
            return "B"
        if score >= 65:
            return "C"
        if score >= 50:
            return "D"
        return "F"

    def analyze(
        self,
        repo_path: str | Path,
        max_commits: int | None = 500,
    ) -> tuple[
        RepositoryHealthReport,
        RepositoryAnalysisSnapshot,
        GraphTopologyReport,
        RepositoryChurnSummary,
        HotspotAnalysisReport,
        BusFactorReport,
    ]:
        """Perform a full multi-dimensional health audit of a local Git repository.

        Args:
            repo_path: Local filesystem path of the repository.
            max_commits: Maximum commits to mine (None for full history).

        Returns:
            Tuple containing the consolidated report and all underlying detailed reports.
        """
        root = Path(repo_path).resolve()
        logger.info("Initiating full repository health audit for: %s", root)

        # 1. Static AST Scan
        snapshot = self.scanner.scan(root)

        # 2. Dependency Graph & Topology
        graph = self.graph_builder.build_graph(snapshot)
        graph_report = self.graph_metrics.compute_metrics(graph)

        # 3. Git Commit History Mining
        has_git = (root / ".git").exists()
        if has_git:
            miner = GitRepositoryMiner(root)
            commits = list(miner.mine_commits(max_commits=max_commits))
        else:
            commits = []

        # 4. Churn, Hotspots, and Ownership
        churn_summary = self.churn_aggregator.aggregate(commits)
        hotspot_report = self.hotspot_detector.detect(snapshot, churn_summary)
        bus_report = self.ownership_engine.compute(commits)

        # 5. Mathematical Sub-Scores Computation (0 - 100)
        # Pillar 1: Complexity
        avg_comp = snapshot.average_complexity
        comp_score = round(max(0.0, min(100.0, 100.0 - (avg_comp - 1.0) * 15.0)), 1)

        # Pillar 2: Hotspots / Debt
        total_f = max(1, snapshot.total_files)
        debt_ratio = (hotspot_report.critical_count + 0.5 * hotspot_report.high_count) / total_f
        hotspot_score = round(max(0.0, min(100.0, 100.0 * (1.0 - debt_ratio))), 1)

        # Pillar 3: Architecture / Coupling
        cycle_pen = len(graph_report.cycles) * 30.0
        bottleneck_pen = len(graph_report.top_bottlenecks) * 5.0
        arch_score = round(max(0.0, min(100.0, 100.0 - cycle_pen - bottleneck_pen)), 1)

        # Pillar 4: Ownership / Bus Factor
        bf = bus_report.bus_factor if has_git else 3
        bf_base = min(100.0, bf * 25.0)
        silo_pen = 1.0 - (0.4 * bus_report.siloed_ratio if has_git else 0.0)
        ownership_score = round(max(0.0, min(100.0, bf_base * silo_pen)), 1)

        # Weighted Composite Score
        overall_score = round(
            0.25 * comp_score + 0.30 * hotspot_score + 0.25 * arch_score + 0.20 * ownership_score,
            1,
        )
        grade = self._calculate_grade(overall_score)

        # 6. Generate Key Diagnostic Findings
        findings: list[str] = []
        if hotspot_report.critical_count > 0:
            findings.append(f"Detected {hotspot_report.critical_count} critical technical debt hotspots.")
        if not graph_report.is_dag:
            findings.append(f"Architectural cycles found ({len(graph_report.cycles)} circular dependencies).")
        if bus_report.bus_factor <= 1 and has_git:
            findings.append(f"Bus Factor is 1 (Single Point of Failure among {bus_report.total_contributors} authors).")
        if avg_comp > 4.0:
            findings.append(f"High average cognitive complexity ({avg_comp:.2f} per function).")
        if not findings:
            findings.append("Repository demonstrates clean architecture, low debt, and healthy metrics.")

        consolidated_report = RepositoryHealthReport(
            repo_path=str(root),
            overall_score=overall_score,
            grade=grade,
            sub_scores=HealthSubScores(
                complexity_score=comp_score,
                hotspot_score=hotspot_score,
                architecture_score=arch_score,
                ownership_score=ownership_score,
            ),
            total_files=snapshot.total_files,
            total_sloc=snapshot.total_sloc,
            total_commits=churn_summary.total_commits,
            bus_factor=bus_report.bus_factor,
            critical_hotspots_count=hotspot_report.critical_count,
            circular_dependencies_count=len(graph_report.cycles),
            key_findings=tuple(findings),
        )

        logger.info("Health audit complete: Score=%.1f (%s)", overall_score, grade)
        return (
            consolidated_report,
            snapshot,
            graph_report,
            churn_summary,
            hotspot_report,
            bus_report,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("================================================================")
    print("      REPOINSIGHT AI — REPOSITORY HEALTH AUDIT REPORT          ")
    print("================================================================")

    engine = RepositoryHealthEngine()
    report, snap, graph_rep, churn_rep, hot_rep, bus_rep = engine.analyze(".")

    print(f"\nTarget Repository : {report.repo_path}")
    print(f"Overall Health    : {report.overall_score} / 100 (Grade: {report.grade})")
    print(f"Total SLOC        : {report.total_sloc} across {report.total_files} files")
    print(f"Total Commits     : {report.total_commits} | Bus Factor: {report.bus_factor}")

    print("\n--- Sub-Pillar Scorecard (0 - 100) ---")
    print(f"  * [25%] Code Complexity & Cleanliness: {report.sub_scores.complexity_score} / 100")
    print(f"  * [30%] Technical Debt & Hotspots    : {report.sub_scores.hotspot_score} / 100")
    print(f"  * [25%] Architectural DAG & Coupling : {report.sub_scores.architecture_score} / 100")
    print(f"  * [20%] Knowledge & Bus Factor       : {report.sub_scores.ownership_score} / 100")

    print("\n--- Key Executive Findings ---")
    for finding in report.key_findings:
        print(f"  [!] {finding}")