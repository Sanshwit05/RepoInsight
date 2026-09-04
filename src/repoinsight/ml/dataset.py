"""Leak-free historical feature extraction and temporal time-series dataset builder."""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from src.repoinsight.analysis.scanner import RepositoryAnalysisSnapshot
from src.repoinsight.graph.metrics import GraphTopologyReport
from src.repoinsight.mining.models import CommitRecord
from src.repoinsight.ml.labels import ContributionImpactLabel, ImpactLabelGenerator

logger = logging.getLogger(__name__)

# Canonical ordered list of tabular feature names
FEATURE_NAMES: tuple[str, ...] = (
    # Change attributes
    "files_modified_count",
    "lines_added",
    "lines_deleted",
    "total_churn",
    "churn_ratio",
    # Static AST & complexity attributes
    "avg_sloc",
    "max_sloc",
    "avg_complexity",
    "max_complexity",
    "total_functions_touched",
    # Dependency graph attributes (incoming/outgoing imports)
    "avg_in_degree",
    "max_in_degree",
    "avg_out_degree",
    "avg_instability",
    "max_pagerank",
    "max_betweenness",
    # Point-in-time historical momentum (< t)
    "prior_file_changes_count",
    "prior_unique_authors_count",
)


@dataclass(frozen=True)
class ContributionSample:
    """Individual labeled training example for a proposed contribution."""

    commit_hash: str
    committed_at: datetime
    features: dict[str, float]
    impact_score: float  # Regression target [0.0, 1.0]
    risk_level: int  # Multi-class classification target (0=LOW, 1=MEDIUM, 2=HIGH)


@dataclass(frozen=True)
class TemporalDataset:
    """Chronologically split dataset free from lookahead temporal leakage."""

    train_samples: tuple[ContributionSample, ...]
    val_samples: tuple[ContributionSample, ...]
    test_samples: tuple[ContributionSample, ...]
    feature_names: tuple[str, ...] = field(default=FEATURE_NAMES)

    def to_pandas(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Convert train, val, test splits into Pandas DataFrames."""

        def _to_df(samples: tuple[ContributionSample, ...]) -> pd.DataFrame:
            rows = []
            for s in samples:
                row = dict(s.features)
                row["commit_hash"] = s.commit_hash
                row["impact_score"] = s.impact_score
                row["risk_level"] = s.risk_level
                rows.append(row)
            return pd.DataFrame(rows)

        return _to_df(self.train_samples), _to_df(self.val_samples), _to_df(self.test_samples)

    def to_numpy(
        self,
    ) -> tuple[
        np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray
    ]:
        """Convert splits into (X_train, y_train_reg, y_train_cls, X_val, y_val_reg, y_val_cls, X_test, y_test_reg, y_test_cls)."""

        def _extract(samples: tuple[ContributionSample, ...]):
            if not samples:
                return (
                    np.empty((0, len(self.feature_names))),
                    np.empty((0,)),
                    np.empty((0,), dtype=int),
                )
            X = np.array([[s.features[f] for f in self.feature_names] for s in samples], dtype=np.float32)
            y_reg = np.array([s.impact_score for s in samples], dtype=np.float32)
            y_cls = np.array([s.risk_level for s in samples], dtype=np.int64)
            return X, y_reg, y_cls

        X_tr, y_tr_r, y_tr_c = _extract(self.train_samples)
        X_va, y_va_r, y_va_c = _extract(self.val_samples)
        X_te, y_te_r, y_te_c = _extract(self.test_samples)

        return X_tr, y_tr_r, y_tr_c, X_va, y_va_r, y_va_c, X_te, y_te_r, y_te_c


class DatasetBuilder:
    """Builds leak-free machine learning datasets from repository history."""

    def build_dataset(
        self,
        commits: list[CommitRecord],
        snapshot: RepositoryAnalysisSnapshot,
        graph_report: GraphTopologyReport,
        labels: dict[str, ContributionImpactLabel],
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
    ) -> TemporalDataset:
        """Extract point-in-time features and chronologically split the dataset.

        Args:
            commits: List of CommitRecord instances in chronological order.
            snapshot: Static code analysis snapshot.
            graph_report: Topological graph metrics.
            labels: Ground truth labels generated from forward windows.
            train_ratio: Proportion of earliest history allocated to training.
            val_ratio: Proportion of middle history allocated to validation.

        Returns:
            TemporalDataset: Partitioned train, val, and test splits.
        """
        # Running point-in-time historical tallies (< t)
        running_file_changes: dict[str, int] = defaultdict(int)
        running_file_authors: dict[str, set[str]] = defaultdict(set)

        all_samples: list[ContributionSample] = []

        for commit in commits:
            label = labels.get(commit.hash)
            if not label:
                continue

            touched_paths = [fc.path for fc in commit.file_changes if fc.path and fc.path != "unknown_path"]
            if not touched_paths:
                continue

            # 1. Change Features
            added = commit.total_lines_added
            deleted = commit.total_lines_deleted
            churn = commit.total_churn
            churn_ratio = round(added / max(1, added + deleted), 4)

            # 2. Static AST & Complexity Features across modified files
            slocs = [snapshot.file_results[p].sloc for p in touched_paths if p in snapshot.file_results]
            comps = [snapshot.file_results[p].average_function_complexity for p in touched_paths if p in snapshot.file_results]
            funcs = [snapshot.file_results[p].total_functions for p in touched_paths if p in snapshot.file_results]

            avg_sloc = float(np.mean(slocs)) if slocs else 0.0
            max_sloc = float(np.max(slocs)) if slocs else 0.0
            avg_comp = float(np.mean(comps)) if comps else 1.0
            max_comp = float(np.max(comps)) if comps else 1.0
            total_funcs = float(sum(funcs)) if funcs else 0.0

            # 3. Graph & Import Topology Features across modified files
            in_degrees = [graph_report.node_metrics[p].in_degree for p in touched_paths if p in graph_report.node_metrics]
            out_degrees = [graph_report.node_metrics[p].out_degree for p in touched_paths if p in graph_report.node_metrics]
            instabilities = [graph_report.node_metrics[p].instability for p in touched_paths if p in graph_report.node_metrics]
            pageranks = [graph_report.node_metrics[p].pagerank for p in touched_paths if p in graph_report.node_metrics]
            betweenness = [graph_report.node_metrics[p].betweenness_centrality for p in touched_paths if p in graph_report.node_metrics]

            avg_in = float(np.mean(in_degrees)) if in_degrees else 0.0
            max_in = float(np.max(in_degrees)) if in_degrees else 0.0
            avg_out = float(np.mean(out_degrees)) if out_degrees else 0.0
            avg_inst = float(np.mean(instabilities)) if instabilities else 0.0
            max_pr = float(np.max(pageranks)) if pageranks else 0.0
            max_bet = float(np.max(betweenness)) if betweenness else 0.0

            # 4. Point-in-time Historical Momentum (< t)
            prior_changes = sum(running_file_changes[p] for p in touched_paths)
            prior_authors = len(set.union(*(running_file_authors[p] for p in touched_paths))) if touched_paths else 0

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
                "prior_file_changes_count": float(prior_changes),
                "prior_unique_authors_count": float(prior_authors),
            }

            all_samples.append(
                ContributionSample(
                    commit_hash=commit.hash,
                    committed_at=commit.committed_at,
                    features=feature_dict,
                    impact_score=label.impact_score,
                    risk_level=label.risk_level.value,
                )
            )

            # Update running tallies *after* extracting sample (strictly point-in-time)
            for p in touched_paths:
                running_file_changes[p] += 1
                running_file_authors[p].add(commit.author_email)

        # Chronological Temporal Split
        n = len(all_samples)
        train_end = int(n * train_ratio)
        val_end = int(n * (train_ratio + val_ratio))

        train_samples = tuple(all_samples[:train_end])
        val_samples = tuple(all_samples[train_end:val_end])
        test_samples = tuple(all_samples[val_end:])

        logger.info(
            "Temporal dataset created: Total=%d samples (Train=%d, Val=%d, Test=%d).",
            n,
            len(train_samples),
            len(val_samples),
            len(test_samples),
        )

        return TemporalDataset(
            train_samples=train_samples,
            val_samples=val_samples,
            test_samples=test_samples,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("--- Demonstrating Temporal Dataset Builder ---")
    from src.repoinsight.analysis.scanner import RepositoryScanner
    from src.repoinsight.graph.builder import DependencyGraphBuilder
    from src.repoinsight.graph.metrics import GraphMetricsEngine

    # 1. Prepare codebase static & graph metadata
    scanner = RepositoryScanner()
    snapshot = scanner.scan(".")
    graph = DependencyGraphBuilder().build_graph(snapshot)
    graph_report = GraphMetricsEngine().compute_metrics(graph)

    # 2. Build mock commits and labels
    from datetime import datetime, timezone
    from src.repoinsight.mining.models import ChangeType, FileChangeRecord

    mock_commits = []
    files_pool = list(snapshot.file_results.keys())[:3]
    for idx in range(20):
        mock_commits.append(
            CommitRecord(
                hash=f"hash_{idx:03d}",
                author_name=f"Author_{idx % 3}",
                author_email=f"author_{idx % 3}@example.com",
                committed_at=datetime.now(timezone.utc),
                message=f"Commit #{idx}",
                is_merge=False,
                file_changes=(
                    FileChangeRecord(
                        old_path=files_pool[idx % len(files_pool)],
                        new_path=files_pool[idx % len(files_pool)],
                        change_type=ChangeType.MODIFY,
                        added_lines=10 + idx,
                        deleted_lines=2 + idx,
                    ),
                ),
            )
        )

    label_gen = ImpactLabelGenerator(forward_window_size=3)
    labels = label_gen.generate_labels(mock_commits)

    # 3. Build leak-free dataset
    builder = DatasetBuilder()
    dataset = builder.build_dataset(mock_commits, snapshot, graph_report, labels)

    print(f"\n[OK] Features Extracted   : {len(dataset.feature_names)} features")
    print(f"[OK] Temporal Splits Size : Train={len(dataset.train_samples)}, Val={len(dataset.val_samples)}, Test={len(dataset.test_samples)}")

    # 4. Test Matrix Conversions
    X_tr, y_tr_r, y_tr_c, X_va, y_va_r, y_va_c, X_te, y_te_r, y_te_c = dataset.to_numpy()
    print(f"\n[OK] X_train Matrix Shape : {X_tr.shape} (float32)")
    print(f"[OK] y_train Reg Target   : {y_tr_r.shape} (impact scores)")
    print(f"[OK] y_train Cls Target   : {y_tr_c.shape} (risk levels 0/1/2)")