"""Graph topology metrics, centrality calculation, and cycle detection."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import networkx as nx

from src.repoinsight.analysis.scanner import RepositoryScanner
from src.repoinsight.graph.builder import DependencyGraphBuilder

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NodeGraphMetrics:
    """Graph topological metrics for an individual file/module node."""

    file_path: str
    in_degree: int
    out_degree: int
    total_degree: int
    instability: float
    pagerank: float
    betweenness_centrality: float


@dataclass(frozen=True)
class GraphTopologyReport:
    """Aggregated topological analysis report for the repository dependency graph."""

    total_nodes: int
    total_edges: int
    density: float
    is_dag: bool
    cycles: tuple[tuple[str, ...], ...] = field(default_factory=tuple)
    node_metrics: dict[str, NodeGraphMetrics] = field(default_factory=dict)
    top_hubs: tuple[str, ...] = field(default_factory=tuple)  # Highest in-degree / PageRank
    top_bottlenecks: tuple[str, ...] = field(default_factory=tuple)  # Highest betweenness


class GraphMetricsEngine:
    """Calculates network topology and centrality metrics on a dependency graph."""

    def compute_metrics(self, graph: nx.DiGraph) -> GraphTopologyReport:
        """Compute all topological metrics, centralities, and cycle diagnostics.

        Args:
            graph: Directed dependency graph (networkx.DiGraph).

        Returns:
            GraphTopologyReport: Comprehensive graph metrics report.
        """
        total_nodes = graph.number_of_nodes()
        total_edges = graph.number_of_edges()

        if total_nodes == 0:
            return GraphTopologyReport(
                total_nodes=0,
                total_edges=0,
                density=0.0,
                is_dag=True,
            )

        # 1. Graph-level diagnostics
        density = round(nx.density(graph), 4)
        is_dag = nx.is_directed_acyclic_graph(graph)

        # 2. Cycle detection
        detected_cycles: list[tuple[str, ...]] = []
        if not is_dag:
            for cycle in nx.simple_cycles(graph):
                detected_cycles.append(tuple(cycle))

        # 3. Centrality algorithms
        # PageRank with standard damping factor 0.85
        try:
            pagerank_scores = nx.pagerank(graph, alpha=0.85, max_iter=200)
        except Exception:
            pagerank_scores = {n: 1.0 / total_nodes for n in graph.nodes()}

        # Betweenness Centrality
        betweenness_scores = nx.betweenness_centrality(graph, normalized=True)

        # 4. Compute per-node metrics
        node_metrics: dict[str, NodeGraphMetrics] = {}
        for node in graph.nodes():
            in_deg = graph.in_degree(node)
            out_deg = graph.out_degree(node)
            tot_deg = in_deg + out_deg

            # Martin's Instability Metric: I = Ce / (Ca + Ce)
            instability = round(out_deg / tot_deg, 3) if tot_deg > 0 else 0.0

            node_metrics[node] = NodeGraphMetrics(
                file_path=node,
                in_degree=in_deg,
                out_degree=out_deg,
                total_degree=tot_deg,
                instability=instability,
                pagerank=round(pagerank_scores.get(node, 0.0), 5),
                betweenness_centrality=round(betweenness_scores.get(node, 0.0), 5),
            )

        # 5. Identify key architectural hubs and bottlenecks
        sorted_by_pagerank = sorted(
            node_metrics.values(),
            key=lambda m: (m.in_degree, m.pagerank),
            reverse=True,
        )
        sorted_by_betweenness = sorted(
            node_metrics.values(),
            key=lambda m: m.betweenness_centrality,
            reverse=True,
        )

        top_hubs = tuple(m.file_path for m in sorted_by_pagerank[:5] if m.in_degree > 0)
        top_bottlenecks = tuple(
            m.file_path for m in sorted_by_betweenness[:5] if m.betweenness_centrality > 0
        )

        logger.info(
            "Graph analysis complete: DAG=%s, Density=%.4f, Hubs=%d, Bottlenecks=%d",
            is_dag,
            density,
            len(top_hubs),
            len(top_bottlenecks),
        )

        return GraphTopologyReport(
            total_nodes=total_nodes,
            total_edges=total_edges,
            density=density,
            is_dag=is_dag,
            cycles=tuple(detected_cycles),
            node_metrics=node_metrics,
            top_hubs=top_hubs,
            top_bottlenecks=top_bottlenecks,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("--- Running Graph Metrics Engine on Current Repository ---")
    scanner = RepositoryScanner()
    snapshot = scanner.scan(".")

    builder = DependencyGraphBuilder()
    graph = builder.build_graph(snapshot, include_external=False)

    engine = GraphMetricsEngine()
    report = engine.compute_metrics(graph)

    print(f"\n[OK] Graph Structure   : {report.total_nodes} nodes, {report.total_edges} edges")
    print(f"[OK] Graph Density     : {report.density}")
    print(f"[OK] Is Clean DAG?     : {report.is_dag} (Cycles detected: {len(report.cycles)})")

    print("\n--- Top Architectural Hubs (High In-Degree / Central Core) ---")
    for hub in report.top_hubs:
        m = report.node_metrics[hub]
        print(f"  * {hub:<40s} | In-Degree: {m.in_degree} | PageRank: {m.pagerank:.4f} | Instability: {m.instability}")

    print("\n--- Per-Node Topological Telemetry ---")
    for path, m in sorted(report.node_metrics.items()):
        print(f"  * {path:<40s} | In:{m.in_degree:<2d} | Out:{m.out_degree:<2d} | Instability:{m.instability:.2f} | Betweenness:{m.betweenness_centrality:.4f}")