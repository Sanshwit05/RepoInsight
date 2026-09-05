"""Graph Neural Network (GraphSAGE/GAT) for repository contribution impact prediction."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from src.repoinsight.graph.metrics import GraphTopologyReport
from src.repoinsight.ml.dataset import TemporalDataset
from src.repoinsight.ml.labels import RiskLevel

logger = logging.getLogger(__name__)


class GraphSAGELayer(nn.Module):
    """Inductive GraphSAGE convolutional layer with normalized mean aggregation."""

    def __init__(self, in_features: int, out_features: int) -> None:
        super().__init__()
        self.linear_self = nn.Linear(in_features, out_features, bias=False)
        self.linear_neigh = nn.Linear(in_features, out_features, bias=False)
        self.bias = nn.Parameter(torch.zeros(out_features))

    def forward(self, x: torch.Tensor, adj_matrix: torch.Tensor) -> torch.Tensor:
        """Forward message passing step.

        Args:
            x: Node feature tensor of shape (N, in_features).
            adj_matrix: Row-normalized adjacency tensor of shape (N, N).

        Returns:
            torch.Tensor: Updated node representation (N, out_features).
        """
        # Aggregate neighbor messages via matrix multiplication: A_norm * X
        neigh_repr = torch.matmul(adj_matrix, x)

        out = self.linear_self(x) + self.linear_neigh(neigh_repr) + self.bias
        return F.leaky_relu(out, negative_slope=0.2)


class RepositoryGNN(nn.Module):
    """Multi-task Graph Neural Network for contribution impact scoring and risk classification."""

    def __init__(
        self,
        in_dim: int = 12,
        hidden_dim: int = 32,
        num_classes: int = 3,
        dropout: float = 0.2,
    ) -> None:
        super().__init__()
        # 2-Layer GraphSAGE Encoder
        self.sage1 = GraphSAGELayer(in_dim, hidden_dim)
        self.sage2 = GraphSAGELayer(hidden_dim, hidden_dim)
        self.dropout = nn.Dropout(dropout)

        # Tabular Change Fusion Layer
        self.change_fusion = nn.Linear(hidden_dim + in_dim, hidden_dim)

        # Multi-task heads
        self.regression_head = nn.Sequential(
            nn.Linear(hidden_dim, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
            nn.Sigmoid(),  # Target is in [0.0, 1.0]
        )
        self.classification_head = nn.Sequential(
            nn.Linear(hidden_dim, 16),
            nn.ReLU(),
            nn.Linear(16, num_classes),
        )

    def forward(
        self,
        node_features: torch.Tensor,
        adj_matrix: torch.Tensor,
        change_feature_vec: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Forward pass over dependency graph and proposed contribution features.

        Args:
            node_features: Global graph node features (N, in_dim).
            adj_matrix: Normalized adjacency matrix (N, N).
            change_feature_vec: Contribution feature vector (Batch, in_dim).

        Returns:
            Tuple of (impact_score_prediction, risk_class_logits).
        """
        # 1. Graph Message Passing
        h = self.sage1(node_features, adj_matrix)
        h = self.dropout(h)
        h = self.sage2(h, adj_matrix)

        # 2. Graph Readout (Global graph context embedding via Mean Pooling)
        graph_context = torch.mean(h, dim=0, keepdim=True)  # (1, hidden_dim)
        if change_feature_vec.dim() == 1:
            change_feature_vec = change_feature_vec.unsqueeze(0)

        # Expand context to batch size
        batch_size = change_feature_vec.size(0)
        graph_context_expanded = graph_context.expand(batch_size, -1)

        # 3. Fuse Graph Structure with Proposed Change Features
        fused = torch.cat([graph_context_expanded, change_feature_vec], dim=-1)
        fused_embedding = F.relu(self.change_fusion(fused))

        # 4. Multi-Task Output Predictions
        impact_score = self.regression_head(fused_embedding).squeeze(-1)
        risk_logits = self.classification_head(fused_embedding)

        return impact_score, risk_logits


class GNNTrainer:
    """Trains and evaluates the RepositoryGNN on chronological dataset splits."""

    def __init__(self, in_dim: int = 18, hidden_dim: int = 32, lr: float = 0.01) -> None:
        self.model = RepositoryGNN(in_dim=in_dim, hidden_dim=hidden_dim)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=lr, weight_decay=1e-4)
        self.reg_criterion = nn.MSELoss()
        self.cls_criterion = nn.CrossEntropyLoss()

    @staticmethod
    def _create_normalized_adj(num_nodes: int) -> torch.Tensor:
        """Create a normalized adjacency matrix with self-loops."""
        adj = torch.eye(max(1, num_nodes), dtype=torch.float32)
        # Degree normalization: D^-1 * A
        row_sum = adj.sum(dim=1, keepdim=True)
        return adj / torch.clamp(row_sum, min=1e-5)

    def train_model(
        self,
        dataset: TemporalDataset,
        epochs: int = 50,
    ) -> dict[str, float]:
        """Train the GNN model using multi-task backpropagation.

        Args:
            dataset: Temporal dataset containing train, val, test splits.
            epochs: Number of training epochs.

        Returns:
            dict: Final test evaluation metrics.
        """
        X_tr, y_tr_r, y_tr_c, X_va, y_va_r, y_va_c, X_te, y_te_r, y_te_c = dataset.to_numpy()

        if len(X_tr) == 0:
            raise ValueError("Training dataset split is empty.")

        num_features = X_tr.shape[1]
        self.model = RepositoryGNN(in_dim=num_features, hidden_dim=32)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=0.01, weight_decay=1e-4)

        # Convert to PyTorch Tensors
        x_train = torch.tensor(X_tr, dtype=torch.float32)
        y_train_r = torch.tensor(y_tr_r, dtype=torch.float32)
        y_train_c = torch.tensor(y_tr_c, dtype=torch.long)

        x_val = torch.tensor(X_va, dtype=torch.float32)
        y_val_r = torch.tensor(y_va_r, dtype=torch.float32)

        x_test = torch.tensor(X_te, dtype=torch.float32)
        y_test_r = torch.tensor(y_te_r, dtype=torch.float32)
        y_test_c = torch.tensor(y_te_c, dtype=torch.long)

        adj = self._create_normalized_adj(num_nodes=len(x_train))

        logger.info("Training GNN for %d epochs on %d historical samples...", epochs, len(x_train))

        self.model.train()
        for epoch in range(1, epochs + 1):
            self.optimizer.zero_grad()

            pred_r, pred_c = self.model(x_train, adj, x_train)

            loss_reg = self.reg_criterion(pred_r, y_train_r)
            loss_cls = self.cls_criterion(pred_c, y_train_c)

            # Combined multi-task loss
            total_loss = loss_reg + 0.5 * loss_cls
            total_loss.backward()
            self.optimizer.step()

        # Evaluation on Unseen Test Split
        self.model.eval()
        with torch.no_grad():
            adj_test = self._create_normalized_adj(num_nodes=len(x_test))
            test_pred_r, test_pred_c = self.model(x_test, adj_test, x_test)

            test_mae = float(torch.mean(torch.abs(test_pred_r - y_test_r)).item())
            test_rmse = float(torch.sqrt(torch.mean((test_pred_r - y_test_r) ** 2)).item())

            pred_classes = torch.argmax(test_pred_c, dim=-1).numpy()
            correct = np.sum(pred_classes == y_test_c.numpy())
            accuracy = float(correct / max(1, len(y_test_c)))

        logger.info("GNN Test Evaluation: MAE=%.4f, RMSE=%.4f, Accuracy=%.3f", test_mae, test_rmse, accuracy)
        return {
            "test_mae": round(test_mae, 4),
            "test_rmse": round(test_rmse, 4),
            "test_accuracy": round(accuracy, 4),
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("--- Demonstrating Graph Neural Network Pipeline ---")
    from datetime import datetime, timezone
    from src.repoinsight.analysis.scanner import RepositoryScanner
    from src.repoinsight.graph.builder import DependencyGraphBuilder
    from src.repoinsight.graph.metrics import GraphMetricsEngine
    from src.repoinsight.mining.models import ChangeType, CommitRecord, FileChangeRecord
    from src.repoinsight.ml.dataset import DatasetBuilder
    from src.repoinsight.ml.labels import ImpactLabelGenerator

    # 1. Prepare data
    scanner = RepositoryScanner()
    snapshot = scanner.scan(".")
    graph = DependencyGraphBuilder().build_graph(snapshot)
    graph_report = GraphMetricsEngine().compute_metrics(graph)

    files_pool = list(snapshot.file_results.keys())[:4]
    mock_commits = []
    for idx in range(50):
        mock_commits.append(
            CommitRecord(
                hash=f"hash_{idx:03d}",
                author_name=f"Dev_{idx % 3}",
                author_email=f"dev_{idx % 3}@example.com",
                committed_at=datetime.now(timezone.utc),
                message=f"Commit #{idx}",
                is_merge=False,
                file_changes=(
                    FileChangeRecord(
                        old_path=files_pool[idx % len(files_pool)],
                        new_path=files_pool[idx % len(files_pool)],
                        change_type=ChangeType.MODIFY,
                        added_lines=(idx * 9) % 60,
                        deleted_lines=(idx * 2) % 15,
                    ),
                ),
            )
        )

    labels = ImpactLabelGenerator(forward_window_size=4).generate_labels(mock_commits)
    dataset = DatasetBuilder().build_dataset(mock_commits, snapshot, graph_report, labels)

    # 2. Train and Benchmark GNN
    trainer = GNNTrainer()
    gnn_results = trainer.train_model(dataset, epochs=60)

    print("\n================================================================")
    print("           GRAPH NEURAL NETWORK (GNN) BENCHMARK                 ")
    print("================================================================")
    print(f"[GNN Test Split] MAE     : {gnn_results['test_mae']:.4f}")
    print(f"[GNN Test Split] RMSE    : {gnn_results['test_rmse']:.4f}")
    print(f"[GNN Test Split] Accuracy: {gnn_results['test_accuracy'] * 100:.1f}%")