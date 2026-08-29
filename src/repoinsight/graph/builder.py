"""Multi-language module import resolution and directed dependency graph construction."""

from __future__ import annotations

import logging
from pathlib import PurePosixPath
from typing import Any

import networkx as nx

from src.repoinsight.analysis.models import ImportEntity
from src.repoinsight.analysis.scanner import RepositoryAnalysisSnapshot, RepositoryScanner

logger = logging.getLogger(__name__)

# Common extensions to probe during import resolution across languages
CANDIDATE_EXTENSIONS = ("", ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".java", ".rs", ".cpp", ".c", ".h", ".hpp")


class ImportResolver:
    """Resolves multi-language import entities to concrete repository file paths."""

    def __init__(self, known_files: set[str] | frozenset[str]) -> None:
        """Initialize resolver with the set of existing relative repository files."""
        self.known_files = frozenset(known_files)

    def resolve(self, importing_file: str, imp: ImportEntity) -> str | None:
        """Resolve an ImportEntity to an internal repository file path."""
        source_mod = imp.source_module.strip()
        imported_name = imp.imported_name.strip() if imp.imported_name else ""

        # Case 1: Relative Import (e.g., from .models import X, or from './Button')
        if imp.is_relative:
            importing_dir = PurePosixPath(importing_file).parent
            
            target_dir = importing_dir
            for _ in range(max(0, imp.level - 1)):
                target_dir = target_dir.parent

            clean_mod = source_mod.lstrip("./").lstrip("../")
            if clean_mod:
                mod_rel_path = (target_dir / clean_mod.replace(".", "/")).as_posix()
            else:
                mod_rel_path = target_dir.as_posix()

            candidate_paths = self._generate_candidates(mod_rel_path, imported_name)
            for candidate in candidate_paths:
                if candidate in self.known_files:
                    return candidate
            return None

        # Case 2: Absolute / Dotted Import (e.g., src.repoinsight.analysis.models)
        if source_mod:
            mod_as_path = source_mod.replace(".", "/")
            candidate_paths = self._generate_candidates(mod_as_path, imported_name)
            for candidate in candidate_paths:
                if candidate in self.known_files:
                    return candidate

        return None

    @staticmethod
    def _generate_candidates(base_path: str, imported_name: str) -> list[str]:
        """Generate possible filesystem file paths across Python and Polyglot language conventions."""
        candidates = []
        clean_base = base_path.strip("/")

        if clean_base:
            for ext in CANDIDATE_EXTENSIONS:
                candidates.append(f"{clean_base}{ext}")
            # Package index / init files
            candidates.append(f"{clean_base}/__init__.py")
            candidates.append(f"{clean_base}/index.ts")
            candidates.append(f"{clean_base}/index.tsx")
            candidates.append(f"{clean_base}/index.js")

        if clean_base and imported_name:
            for ext in CANDIDATE_EXTENSIONS:
                candidates.append(f"{clean_base}/{imported_name}{ext}")
            candidates.append(f"{clean_base}/{imported_name}/__init__.py")
            candidates.append(f"{clean_base}/{imported_name}/index.ts")

        return candidates


class DependencyGraphBuilder:
    """Constructs a NetworkX directed graph from a multi-language RepositoryAnalysisSnapshot."""

    def build_graph(
        self,
        snapshot: RepositoryAnalysisSnapshot,
        include_external: bool = False,
    ) -> nx.DiGraph:
        """Construct the directed dependency graph from analyzed file results."""
        graph = nx.DiGraph()
        known_files = set(snapshot.file_results.keys())
        resolver = ImportResolver(known_files)

        # 1. Add all internal source files as graph nodes with static telemetry attributes
        for file_path, analysis in snapshot.file_results.items():
            node_attributes: dict[str, Any] = {
                "language": analysis.language,
                "loc": analysis.loc,
                "sloc": analysis.sloc,
                "comment_lines": analysis.comment_lines,
                "blank_lines": analysis.blank_lines,
                "functions_count": analysis.total_functions,
                "classes_count": len(analysis.classes),
                "avg_complexity": round(analysis.average_function_complexity, 2),
                "is_internal": True,
            }
            graph.add_node(file_path, **node_attributes)

        # 2. Resolve imports and add directed dependency edges (importing_file -> imported_file)
        for file_path, analysis in snapshot.file_results.items():
            for imp in analysis.imports:
                resolved_target = resolver.resolve(file_path, imp)

                if resolved_target:
                    graph.add_edge(
                        file_path,
                        resolved_target,
                        dependency_type="internal",
                        imported_name=imp.imported_name,
                    )
                elif include_external and imp.source_module:
                    ext_node = f"ext:{imp.source_module}"
                    if not graph.has_node(ext_node):
                        graph.add_node(ext_node, is_internal=False, language="external")
                    graph.add_edge(
                        file_path,
                        ext_node,
                        dependency_type="external",
                        imported_name=imp.imported_name,
                    )

        logger.info(
            "Constructed dependency graph: %d nodes, %d directed edges.",
            graph.number_of_nodes(),
            graph.number_of_edges(),
        )
        return graph


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("--- Building Multi-Language Dependency Graph for Current Codebase ---")
    scanner = RepositoryScanner()
    snapshot = scanner.scan(".")

    builder = DependencyGraphBuilder()
    dep_graph = builder.build_graph(snapshot, include_external=False)

    print(f"\n[OK] Total Nodes (Files) : {dep_graph.number_of_nodes()}")
    print(f"[OK] Total Directed Edges: {dep_graph.number_of_edges()}")

    print("\n--- Directed Dependency Edges Sample ---")
    for u, v in list(dep_graph.edges())[:5]:
        print(f"  * {u} ──imports──> {v}")