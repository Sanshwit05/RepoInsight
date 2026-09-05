"""Baseline Machine Learning models for contribution impact and risk prediction."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.metrics import (
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
)

from src.repoinsight.ml.dataset import FEATURE_NAMES, TemporalDataset
from src.repoinsight.ml.labels import RiskLevel

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelEvaluationMetrics:
    """Rigorous evaluation metrics on held-out temporal evaluation splits."""

    split_name: str
    mae: float
    rmse: float
    r2: float
    precision_macro: float
    recall_macro: float
    f1_macro: float


@dataclass(frozen=True)
class BaselinePrediction:
    """Inference output for a proposed code contribution."""

    predicted_impact_score: float
    predicted_risk_level: RiskLevel
    confidence: float
    class_probabilities: dict[str, float]
    top_feature_attributions: dict[str, float] = field(default_factory=dict)


class BaselineModelPipeline:
    """Trains, evaluates, and serves baseline Random Forest & Gradient Boosting models."""

    def __init__(self, model_type: str = "random_forest") -> None:
        """Initialize pipeline with specified ensemble architecture.

        Args:
            model_type: 'random_forest' or 'gradient_boosting'.
        """
        self.model_type = model_type
        self.feature_names = list(FEATURE_NAMES)

        if model_type == "gradient_boosting":
            self.regressor = GradientBoostingRegressor(n_estimators=100, max_depth=4, random_state=42)
            self.classifier = GradientBoostingClassifier(n_estimators=100, max_depth=4, random_state=42)
        else:
            self.regressor = RandomForestRegressor(n_estimators=100, max_depth=6, random_state=42)
            self.classifier = RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42)

        self._is_trained = False
        self.feature_importances_: dict[str, float] = {}

    def train_and_evaluate(
        self,
        dataset: TemporalDataset,
    ) -> tuple[ModelEvaluationMetrics, ModelEvaluationMetrics]:
        """Train models on the past training split and evaluate on chronological validation and test splits.

        Args:
            dataset: TemporalDataset containing chronological splits.

        Returns:
            Tuple of (val_metrics, test_metrics).
        """
        X_tr, y_tr_r, y_tr_c, X_va, y_va_r, y_va_c, X_te, y_te_r, y_te_c = dataset.to_numpy()

        if len(X_tr) == 0:
            raise ValueError("Training dataset split is empty.")

        logger.info(
            "Training %s models on %d historical samples (%d features)...",
            self.model_type,
            len(X_tr),
            len(self.feature_names),
        )

        # 1. Fit models on Training past (< t_val)
        self.regressor.fit(X_tr, y_tr_r)
        self.classifier.fit(X_tr, y_tr_c)
        self._is_trained = True

        # Extract Gini Feature Importances
        importances = self.regressor.feature_importances_
        self.feature_importances_ = {
            name: round(float(imp), 4)
            for name, imp in sorted(zip(self.feature_names, importances), key=lambda x: x[1], reverse=True)
        }

        # 2. Evaluate on Validation & Test splits
        def _evaluate_split(X: np.ndarray, y_r: np.ndarray, y_c: np.ndarray, split_name: str) -> ModelEvaluationMetrics:
            if len(X) == 0:
                return ModelEvaluationMetrics(split_name, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

            pred_r = self.regressor.predict(X)
            pred_c = self.classifier.predict(X)

            mae = round(float(mean_absolute_error(y_r, pred_r)), 4)
            rmse = round(float(np.sqrt(mean_squared_error(y_r, pred_r))), 4)
            r2 = round(float(r2_score(y_r, pred_r)), 4) if len(y_r) > 1 else 0.0

            prec = round(float(precision_score(y_c, pred_c, average="macro", zero_division=0)), 4)
            rec = round(float(recall_score(y_c, pred_c, average="macro", zero_division=0)), 4)
            f1 = round(float(f1_score(y_c, pred_c, average="macro", zero_division=0)), 4)

            return ModelEvaluationMetrics(
                split_name=split_name,
                mae=mae,
                rmse=rmse,
                r2=r2,
                precision_macro=prec,
                recall_macro=rec,
                f1_macro=f1,
            )

        val_metrics = _evaluate_split(X_va, y_va_r, y_va_c, "Validation Split (Tuning)")
        test_metrics = _evaluate_split(X_te, y_te_r, y_te_c, "Test Split (Future Unseen)")

        logger.info("Evaluation complete: Val F1=%.3f, Test F1=%.3f", val_metrics.f1_macro, test_metrics.f1_macro)
        return val_metrics, test_metrics

    def predict(self, feature_dict: dict[str, float]) -> BaselinePrediction:
        """Predict impact score, risk tier, and confidence for a proposed contribution.

        Args:
            feature_dict: Mapping of feature names to numeric values.

        Returns:
            BaselinePrediction: Complete inference diagnosis.
        """
        if not self._is_trained:
            raise RuntimeError("Model pipeline has not been trained yet.")

        # Ensure canonical feature order
        x_vec = np.array([[feature_dict.get(f, 0.0) for f in self.feature_names]], dtype=np.float32)

        pred_score = float(np.clip(self.regressor.predict(x_vec)[0], 0.0, 1.0))
        probabilities = self.classifier.predict_proba(x_vec)[0]

        # Map probabilities to classes
        classes_present = self.classifier.classes_
        prob_dict: dict[str, float] = {
            "LOW": 0.0,
            "MEDIUM": 0.0,
            "HIGH": 0.0,
        }
        for cls_idx, prob in zip(classes_present, probabilities):
            tier_name = RiskLevel(cls_idx).name
            prob_dict[tier_name] = round(float(prob), 4)

        # Calibrated confidence = probability of highest-scoring class
        predicted_class_idx = int(np.argmax(probabilities))
        predicted_risk = RiskLevel(classes_present[predicted_class_idx])
        confidence = round(float(np.max(probabilities)), 4)

        # Local feature contributions (feature value * global importance)
        local_attributions = {
            feat: round(feature_dict.get(feat, 0.0) * self.feature_importances_.get(feat, 0.0), 3)
            for feat in list(self.feature_importances_.keys())[:5]
        }

        return BaselinePrediction(
            predicted_impact_score=round(pred_score, 4),
            predicted_risk_level=predicted_risk,
            confidence=confidence,
            class_probabilities=prob_dict,
            top_feature_attributions=local_attributions,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("--- Demonstrating Baseline Machine Learning Pipeline ---")
    from datetime import datetime, timezone
    from src.repoinsight.analysis.scanner import RepositoryScanner
    from src.repoinsight.graph.builder import DependencyGraphBuilder
    from src.repoinsight.graph.metrics import GraphMetricsEngine
    from src.repoinsight.mining.models import ChangeType, CommitRecord, FileChangeRecord
    from src.repoinsight.ml.dataset import DatasetBuilder
    from src.repoinsight.ml.labels import ImpactLabelGenerator

    # 1. Build test repository data
    scanner = RepositoryScanner()
    snapshot = scanner.scan(".")
    graph = DependencyGraphBuilder().build_graph(snapshot)
    graph_report = GraphMetricsEngine().compute_metrics(graph)

    files_pool = list(snapshot.file_results.keys())[:4]
    mock_commits = []
    for idx in range(40):
        mock_commits.append(
            CommitRecord(
                hash=f"hash_{idx:03d}",
                author_name=f"Author_{idx % 4}",
                author_email=f"author_{idx % 4}@example.com",
                committed_at=datetime.now(timezone.utc),
                message=f"Commit #{idx}",
                is_merge=False,
                file_changes=(
                    FileChangeRecord(
                        old_path=files_pool[idx % len(files_pool)],
                        new_path=files_pool[idx % len(files_pool)],
                        change_type=ChangeType.MODIFY,
                        added_lines=(idx * 7) % 50,
                        deleted_lines=(idx * 3) % 20,
                    ),
                ),
            )
        )

    labels = ImpactLabelGenerator(forward_window_size=4).generate_labels(mock_commits)
    dataset = DatasetBuilder().build_dataset(mock_commits, snapshot, graph_report, labels)

    # 2. Train and Evaluate Baseline Pipeline
    pipeline = BaselineModelPipeline(model_type="random_forest")
    val_metrics, test_metrics = pipeline.train_and_evaluate(dataset)

    print("\n================================================================")
    print("           BASELINE ML MODEL EVALUATION BENCHMARK               ")
    print("================================================================")
    print(f"\n[Validation Split] MAE: {val_metrics.mae:.4f} | RMSE: {val_metrics.rmse:.4f} | Macro F1: {val_metrics.f1_macro:.4f}")
    print(f"[Test Split (Unseen Future)] MAE: {test_metrics.mae:.4f} | RMSE: {test_metrics.rmse:.4f} | Macro F1: {test_metrics.f1_macro:.4f}")

    print("\n--- Global Feature Importances (Top 5 Drivers) ---")
    for feat, imp in list(pipeline.feature_importances_.items())[:5]:
        print(f"  * {feat:<28s}: {imp * 100:.1f}%")

    # 3. Test Real-Time Single-Contribution Inference
    sample_contribution_features = {
        "files_modified_count": 2.0,
        "lines_added": 120.0,
        "lines_deleted": 30.0,
        "total_churn": 150.0,
        "churn_ratio": 0.80,
        "avg_sloc": 180.0,
        "max_complexity": 7.0,
        "avg_in_degree": 4.0,
        "max_pagerank": 0.25,
    }

    prediction = pipeline.predict(sample_contribution_features)
    print("\n--- Real-Time Prediction Inference ---")
    print(f"  * Predicted Impact Score : {prediction.predicted_impact_score:.4f}")
    print(f"  * Predicted Risk Level   : {prediction.predicted_risk_level.name} (Class {prediction.predicted_risk_level.value})")
    print(f"  * Calibrated Confidence  : {prediction.confidence * 100:.1f}%")
    print(f"  * Class Probabilities    : {prediction.class_probabilities}")