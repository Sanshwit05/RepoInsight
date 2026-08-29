"""Graph serialization, Cytoscape.js export, and ML feature matrix compilation."""

from __future__ import annotations

import json
import logging
from typing import Any

import networkx as nx

from src.repoinsight.analysis.scanner import RepositoryScanner
from src.repoinsight.graph.builder import DependencyGraphBuilder
from src.repoinsight.graph.metrics import GraphMetricsEngine, GraphTopologyReport

logger = logging.getLogger(__name__)


class GraphExporter:
    """Serializes dependency graphs into UI visualizer formats and ML feature matrices."""

    @staticmethod
    def to_cytoscape_json(
        graph: nx.DiGraph,
        report: GraphTopologyReport | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Convert a dependency graph into Cytoscape.js compatible JSON format.

        Args:
            graph: The NetworkX directed graph.
            report: Optional GraphTopologyReport containing computed centralities.

        Returns:
            dict: Standard Cytoscape.js dictionary with 'nodes' and 'edges'.
        """
        nodes_list: list[dict[str, Any]] = []
        edges_list: list[dict[str, Any]] = []

        # 1. Export Nodes with visual and topological telemetry
        for node_id, attrs in graph.nodes(data=True):
            node_metrics = report.node_metrics.get(node_id) if report else None

            node_data: dict[str, Any] = {
                "id": node_id,
                "label": node_id.split("/")[-1],  # Short filename for clean display
                "path": node_id,
                "language": attrs.get("language", "unknown"),
                "sloc": attrs.get("sloc", 0),
                "avg_complexity": attrs.get("avg_complexity", 1.0),
                "functions_count": attrs.get("functions_count", 0),
                "classes_count": attrs.get("classes_count", 0),
                "is_internal": attrs.get("is_internal", True),
                "in_degree": node_metrics.in_degree if node_metrics else graph.in_degree(node_id),
                "out_degree": node_metrics.out_degree if node_metrics else graph.out_degree(node_id),
                "pagerank": node_metrics.pagerank if node_metrics else 0.0,
                "betweenness": node_metrics.betweenness_centrality if node_metrics else 0.0,
            }
            nodes_list.append({"data": node_data})

        # 2. Export Directed Edges
        for source, target, edge_attrs in graph.edges(data=True):
            edge_data: dict[str, Any] = {
                "id": f"{source}->{target}",
                "source": source,
                "target": target,
                "dependency_type": edge_attrs.get("dependency_type", "internal"),
                "imported_name": edge_attrs.get("imported_name", ""),
            }
            edges_list.append({"data": edge_data})

        return {"elements": {"nodes": nodes_list, "edges": edges_list}}

    @staticmethod
    def to_node_feature_dict(
        graph: nx.DiGraph,
        report: GraphTopologyReport,
    ) -> dict[str, dict[str, float]]:
        """Compile a combined static + topological numerical feature dictionary per file.

        Args:
            graph: The NetworkX directed graph.
            report: The computed GraphTopologyReport.

        Returns:
            dict: Mapping of file_path -> {feature_name: numerical_value}.
        """
        features_by_node: dict[str, dict[str, float]] = {}

        for node_id, attrs in graph.nodes(data=True):
            m = report.node_metrics.get(node_id)
            if not m:
                continue

            features_by_node[node_id] = {
                "loc": float(attrs.get("loc", 0)),
                "sloc": float(attrs.get("sloc", 0)),
                "comment_lines": float(attrs.get("comment_lines", 0)),
                "functions_count": float(attrs.get("functions_count", 0)),
                "classes_count": float(attrs.get("classes_count", 0)),
                "avg_complexity": float(attrs.get("avg_complexity", 1.0)),
                "in_degree": float(m.in_degree),
                "out_degree": float(m.out_degree),
                "total_degree": float(m.total_degree),
                "instability": float(m.instability),
                "pagerank": float(m.pagerank),
                "betweenness_centrality": float(m.betweenness_centrality),
            }

        return features_by_node


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("--- Demonstrating Graph Serialization and Exporter ---")
    scanner = RepositoryScanner()
    snapshot = scanner.scan(".")

    builder = DependencyGraphBuilder()
    graph = builder.build_graph(snapshot, include_external=False)

    engine = GraphMetricsEngine()
    report = engine.compute_metrics(graph)

    exporter = GraphExporter()

    # 1. Test Cytoscape.js export
    cy_data = exporter.to_cytoscape_json(graph, report)
    print(f"\n[OK] Cytoscape Nodes Exported: {len(cy_data['elements']['nodes'])}")
    print(f"[OK] Cytoscape Edges Exported: {len(cy_data['elements']['edges'])}")
    print("     Sample Cytoscape Node JSON:")
    print("     " + json.dumps(cy_data['elements']['nodes'][0], indent=2).replace("\n", "\n     "))

    # 2. Test Combined ML Node Feature Extraction
    feature_dict = exporter.to_node_feature_dict(graph, report)
    print(f"\n[OK] ML Node Feature Vectors Extracted: {len(feature_dict)} files")
    sample_file = list(feature_dict.keys())[0]
    print(f"     Sample Feature Vector for '{sample_file}':")
    for feat_name, val in feature_dict[sample_file].items():
        print(f"       * {feat_name:<24s}: {val:.4f}")