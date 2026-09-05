"""End-to-end Contribution Impact Predictor and downstream ripple simulation service."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np

from src.repoinsight.analysis.scanner import RepositoryAnalysisSnapshot, RepositoryScanner
from src.repoinsight.graph.builder import DependencyGraphBuilder
from src.repoinsight.graph.metrics import GraphMetricsEngine, GraphTopologyReport
from src.repoinsight.guidance.recommender import ReviewDifficulty
from src.repoinsight.mining.miner import GitRepositoryMiner
from src.repoinsight.ml.baseline import BaselineModelPipeline, BaselinePrediction
from src.repoinsight.ml.dataset import DatasetBuilder
from src.repoinsight.ml.labels import ImpactLabelGenerator, RiskLevel

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProposedFileChange:
    """Represents a proposed modification to an individual file."""

    file_path: str
    added_lines: int
    deleted_lines: int
    change_type: str = "MODIFY"


@dataclass(frozen=True)
class ProposedContribution:
    """Represents a full proposed code contribution / Pull Request."""

    files: tuple[ProposedFileChange, ...]
    author_email: str = ""
    message: str = ""

    @property
    def total_added(self) -> int:
        return sum(f.added_lines for f in self.files)

    @property
    def total_deleted(self) -> int:
        return sum(f.deleted_lines for f in self.files)

    @property
    def total_churn(self) -> int:
        return self.total_added + self.total_deleted


@dataclass(frozen=True)
class ContributionImpactDiagnosis:
    """Executive prediction output and risk assessment for a proposed contribution."""

    impact_score: float  # [0.0, 1.0]
    risk_level: RiskLevel  # LOW, MEDIUM, HIGH
    confidence: float  # [0.0, 1.0]
    review_difficulty: ReviewDifficulty
    likely_affected_files: tuple[str, ...]
    primary_risk_factors: tuple[str, ...]
    class_probabilities: dict[str, float] = field(default_factory=dict)
    summary_verdict: str = ""


class ContributionImpactPredictor:
    """Orchestrates live feature extraction, ML inference, and downstream ripple simulation."""

    def __init__(
        self,
        repo_path: str | Path,
        pipeline: BaselineModelPipeline | None = None,
    ) -> None:
        """Initialize predictor for a specific repository workspace."""
        self.repo_path = Path(repo_path).resolve()

        # 1. Extract static AST & dependency graph snapshot
        self.scanner = RepositoryScanner()
        self.snapshot = self.scanner.scan(self.repo_path)

        self.graph_builder = DependencyGraphBuilder()
        self.graph = self.graph_builder.build_graph(self.snapshot)
        self.graph_report = GraphMetricsEngine().compute_metrics(self.graph)

        # 2. Initialize and ensure trained ML model
        self.pipeline = pipeline or BaselineModelPipeline(model_type="random_forest")
        self._ensure_trained_model()

    def _ensure_trained_model(self) -> None:
        """Ensure the underlying ML pipeline is fitted on historical repository evolution."""
        has_git = (self.repo_path / ".git").exists()
        commits = []
        if has_git:
            miner = GitRepositoryMiner(self.repo_path)
            commits = list(miner.mine_commits(max_commits=300))

        if len(commits) >= 10:
            labels = ImpactLabelGenerator(forward_window_size=4).generate_labels(commits)
            dataset = DatasetBuilder().build_dataset(commits, self.snapshot, self.graph_report, labels)
            self.pipeline.train_and_evaluate(dataset)
        else:
            logger.info("Insufficient Git history (<10 commits). Bootstrapping baseline estimator.")
            # Bootstrap fallback training on synthetic representation
            from src.repoinsight.mining.models import ChangeType, CommitRecord, FileChangeRecord
            from datetime import datetime, timezone

            boot_commits = []
            files_pool = list(self.snapshot.file_results.keys()) or ["app.py"]
            for idx in range(30):
                f = files_pool[idx % len(files_pool)]
                boot_commits.append(
                    CommitRecord(
                        hash=f"boot_{idx:03d}",
                        author_name="Dev",
                        author_email="dev@example.com",
                        committed_at=datetime.now(timezone.utc),
                        message="Bootstrap commit",
                        is_merge=False,
                        file_changes=(FileChangeRecord(f, f, ChangeType.MODIFY, 10 + idx, 5),),
                    )
                )
            labels = ImpactLabelGenerator(forward_window_size=3).generate_labels(boot_commits)
            dataset = DatasetBuilder().build_dataset(boot_commits, self.snapshot, self.graph_report, labels)
            self.pipeline.train_and_evaluate(dataset)

    def _simulate_affected_files(self, touched_paths: list[str], max_hops: int = 2) -> list[str]:
        """Simulate downstream blast radius using reverse BFS over incoming import edges."""
        affected: set[str] = set()

        for path in touched_paths:
            if not self.graph.has_node(path):
                continue

            # In a dependency graph: u -> v means u imports v.
            # When v changes, dependents are the predecessors of v (nodes with edges pointing to v).
            current_level = {path}
            for _ in range(max_hops):
                next_level = set()
                for node in current_level:
                    predecessors = set(self.graph.predecessors(node))
                    next_level.update(predecessors)
                affected.update(next_level)
                current_level = next_level

        # Exclude the modified files themselves from the downstream affected list
        affected.difference_update(touched_paths)

        # Rank affected files by architectural centrality (in-degree & PageRank)
        ranked = sorted(
            affected,
            key=lambda p: (
                self.graph_report.node_metrics[p].in_degree if p in self.graph_report.node_metrics else 0,
                self.graph_report.node_metrics[p].pagerank if p in self.graph_report.node_metrics else 0.0,
            ),
            reverse=True,
        )
        return ranked

    def predict_contribution(
        self,
        contribution: ProposedContribution,
    ) -> ContributionImpactDiagnosis:
        """Predict the impact score, risk level, confidence, and affected modules for a proposed change.

        Args:
            contribution: The ProposedContribution DTO containing modified files and lines.

        Returns:
            ContributionImpactDiagnosis: Comprehensive risk verdict.
        """
        touched_paths = [f.file_path for f in contribution.files]
        added = contribution.total_added
        deleted = contribution.total_deleted
        churn = contribution.total_churn
        churn_ratio = round(added / max(1, added + deleted), 4)

        # 1. Extract live static AST features across modified files
        slocs = [self.snapshot.file_results[p].sloc for p in touched_paths if p in self.snapshot.file_results]
        comps = [self.snapshot.file_results[p].average_function_complexity for p in touched_paths if p in self.snapshot.file_results]
        funcs = [self.snapshot.file_results[p].total_functions for p in touched_paths if p in self.snapshot.file_results]

        avg_sloc = float(np.mean(slocs)) if slocs else 0.0
        max_sloc = float(np.max(slocs)) if slocs else 0.0
        avg_comp = float(np.mean(comps)) if comps else 1.0
        max_comp = float(np.max(comps)) if comps else 1.0
        total_funcs = float(sum(funcs)) if funcs else 0.0

        # 2. Extract live graph & import topology features
        in_degrees = [self.graph_report.node_metrics[p].in_degree for p in touched_paths if p in self.graph_report.node_metrics]
        out_degrees = [self.graph_report.node_metrics[p].out_degree for p in touched_paths if p in self.graph_report.node_metrics]
        instabilities = [self.graph_report.node_metrics[p].instability for p in touched_paths if p in self.graph_report.node_metrics]
        pageranks = [self.graph_report.node_metrics[p].pagerank for p in touched_paths if p in self.graph_report.node_metrics]
        betweenness = [self.graph_report.node_metrics[p].betweenness_centrality for p in touched_paths if p in self.graph_report.node_metrics]

        avg_in = float(np.mean(in_degrees)) if in_degrees else 0.0
        max_in = float(np.max(in_degrees)) if in_degrees else 0.0
        avg_out = float(np.mean(out_degrees)) if out_degrees else 0.0
        avg_inst = float(np.mean(instabilities)) if instabilities else 0.0
        max_pr = float(np.max(pageranks)) if pageranks else 0.0
        max_bet = float(np.max(betweenness)) if betweenness else 0.0

        feature_dict: dict[str, float] = {
            "files_modified_count": float(len(touched_paths)),
            "lines_added": float(added),
            "lines_deleted": float(deleted),
            "total_churn": float(churn),
            "churn_ratio": churn_ratio,
            "avg_sloc": avg_sloc,
            "max_sloc": max_sloc,
            "avg_complexity": avg_comp,
            "max_complexity": max_comp,
            "total_functions_touched": total_funcs,
            "avg_in_degree": avg_in,
            "max_in_degree": max_in,
            "avg_out_degree": avg_out,
            "avg_instability": avg_inst,
            "max_pagerank": max_pr,
            "max_betweenness": max_bet,
            "prior_file_changes_count": 5.0,  # Prior baseline estimate
            "prior_unique_authors_count": 2.0,
        }

        # 3. Model Inference
        raw_pred: BaselinePrediction = self.pipeline.predict(feature_dict)

        # 4. Simulate Downstream Affected Files
        likely_affected = self._simulate_affected_files(touched_paths, max_hops=2)

        # 5. Map Review Difficulty
        if raw_pred.predicted_risk_level == RiskLevel.HIGH or raw_pred.predicted_impact_score >= 0.60:
            difficulty = ReviewDifficulty.CRITICAL
        elif raw_pred.predicted_risk_level == RiskLevel.MEDIUM:
            difficulty = ReviewDifficulty.HARD if len(likely_affected) > 2 else ReviewDifficulty.MODERATE
        else:
            difficulty = ReviewDifficulty.EASY

        # 6. Extract Key Risk Drivers
        drivers = []
        if max_in >= 3:
            drivers.append(f"High in-degree ({int(max_in)} incoming dependencies on modified files).")
        if churn > 100:
            drivers.append(f"Heavy code churn ({churn} lines modified).")
        if max_comp > 4.0:
            drivers.append(f"High cognitive complexity (max complexity {max_comp:.1f}).")
        if likely_affected:
            drivers.append(f"Transitive blast radius reaches {len(likely_affected)} downstream modules.")
        if not drivers:
            drivers.append("Isolated modification with low topological coupling.")

        verdict = (
            f"Predicted {raw_pred.predicted_risk_level.name} risk impact "
            f"(Score: {raw_pred.predicted_impact_score:.2f}, Confidence: {raw_pred.confidence*100:.1f}%). "
            f"Estimated Review Difficulty: {difficulty.value}."
        )

        logger.info("Contribution evaluated: %s", verdict)

        return ContributionImpactDiagnosis(
            impact_score=raw_pred.predicted_impact_score,
            risk_level=raw_pred.predicted_risk_level,
            confidence=raw_pred.confidence,
            review_difficulty=difficulty,
            likely_affected_files=tuple(likely_affected),
            primary_risk_factors=tuple(drivers),
            class_probabilities=raw_pred.class_probabilities,
            summary_verdict=verdict,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("================================================================")
    print("      REPOINSIGHT AI — CONTRIBUTION IMPACT PREDICTOR           ")
    print("================================================================")

    # Initialize predictor on current repository workspace
    predictor = ContributionImpactPredictor(repo_path=".")

    # Simulate a proposed Pull Request that modifies core architectural models
    sample_pr = ProposedContribution(
        files=(
            ProposedFileChange(
                file_path="src/repoinsight/analysis/models.py",
                added_lines=60,
                deleted_lines=15,
            ),
        ),
        author_email="contributor@example.com",
        message="refactor: update static analysis AST models",
    )

    diagnosis = predictor.predict_contribution(sample_pr)

    print(f"\n[OK] Verdict             : {diagnosis.summary_verdict}")
    print(f"[OK] Impact Score        : {diagnosis.impact_score:.4f} / 1.0000")
    print(f"[OK] Risk Tier           : {diagnosis.risk_level.name} (Class {diagnosis.risk_level.value})")
    print(f"[OK] Calibrated Conf.    : {diagnosis.confidence * 100:.1f}%")
    print(f"[OK] Review Difficulty   : {diagnosis.review_difficulty.value}")

    print("\n--- Downstream Blast Radius (Likely Affected Files) ---")
    for affected in diagnosis.likely_affected_files:
        print(f"  * ⚠️  {affected}")

    print("\n--- Primary Risk Drivers ---")
    for driver in diagnosis.primary_risk_factors:
        print(f"  * 🔍 {driver}")