"""Repository-wide static analysis scanner and metric aggregator."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from src.repoinsight.analysis.models import FileAnalysisResult
from src.repoinsight.analysis.polyglot import ParserRegistry

logger = logging.getLogger(__name__)

# Standard directories to exclude during repository scanning
DEFAULT_IGNORE_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        "data",
    }
)


@dataclass(frozen=True)
class RepositoryAnalysisSnapshot:
    """Aggregated static analysis snapshot for an entire repository."""

    repo_path: str
    file_results: dict[str, FileAnalysisResult] = field(default_factory=dict)

    @property
    def total_files(self) -> int:
        """Total number of analyzed source files."""
        return len(self.file_results)

    @property
    def total_loc(self) -> int:
        """Total physical lines of code across all files."""
        return sum(f.loc for f in self.file_results.values())

    @property
    def total_sloc(self) -> int:
        """Total source lines of code (excluding comments and blanks)."""
        return sum(f.sloc for f in self.file_results.values())

    @property
    def total_comment_lines(self) -> int:
        """Total comment lines across all files."""
        return sum(f.comment_lines for f in self.file_results.values())

    @property
    def total_functions(self) -> int:
        """Total functions and methods declared in the repository."""
        return sum(f.total_functions for f in self.file_results.values())

    @property
    def total_classes(self) -> int:
        """Total classes declared in the repository."""
        return sum(len(f.classes) for f in self.file_results.values())

    @property
    def languages(self) -> dict[str, int]:
        """Breakdown of files per programming language."""
        breakdown: dict[str, int] = {}
        for f in self.file_results.values():
            breakdown[f.language] = breakdown.get(f.language, 0) + 1
        return breakdown

    @property
    def average_complexity(self) -> float:
        """Codebase-wide average cyclomatic complexity per function."""
        all_complexities: list[int] = []
        for f in self.file_results.values():
            for fn in f.functions:
                all_complexities.append(fn.cyclomatic_complexity)
            for cls_entity in f.classes:
                all_complexities.extend(m.cyclomatic_complexity for m in cls_entity.methods)

        if not all_complexities:
            return 1.0
        return sum(all_complexities) / len(all_complexities)


class RepositoryScanner:
    """Recursively discovers and analyzes multi-language source files in a target repository."""

    def __init__(
        self,
        ignore_dirs: set[str] | frozenset[str] = DEFAULT_IGNORE_DIRS,
        registry: ParserRegistry | None = None,
    ) -> None:
        """Initialize scanner with directory exclusion rules and language parser registry."""
        self.ignore_dirs = frozenset(ignore_dirs)
        self.registry = registry or ParserRegistry()

    def _should_skip_dir(self, dir_name: str) -> bool:
        """Check if a directory matches exclusion rules."""
        return dir_name in self.ignore_dirs or dir_name.endswith(".egg-info")

    def scan(self, repo_path: str | Path) -> RepositoryAnalysisSnapshot:
        """Scan and analyze all supported multi-language source files in the repository."""
        root_path = Path(repo_path).resolve()
        if not root_path.exists() or not root_path.is_dir():
            raise ValueError(f"Invalid repository directory: '{root_path}'")

        file_results: dict[str, FileAnalysisResult] = {}
        logger.info("Starting static scan of repository: %s", root_path)

        for current_dir, dirs, files in self._walk_dir(root_path):
            # Prune ignored directories in-place during traversal
            dirs[:] = [d for d in dirs if not self._should_skip_dir(d)]

            for file_name in files:
                full_file_path = current_dir / file_name
                parser = self.registry.get_parser_for_file(full_file_path)

                if parser is not None:
                    # Compute relative POSIX path for portable representation
                    try:
                        relative_path = full_file_path.relative_to(root_path).as_posix()
                    except ValueError:
                        relative_path = str(full_file_path)

                    try:
                        source_code = full_file_path.read_text(encoding="utf-8", errors="replace")
                    except OSError as exc:
                        logger.error("Failed to read %s: %s", full_file_path, exc)
                        continue

                    analysis = parser.analyze_source(source_code, file_path=relative_path)
                    file_results[relative_path] = analysis

        logger.info("Completed static scan: %d source files analyzed across languages.", len(file_results))
        return RepositoryAnalysisSnapshot(
            repo_path=str(root_path),
            file_results=file_results,
        )

    @staticmethod
    def _walk_dir(root: Path):
        """Standard filesystem traversal utility."""
        import os

        for root_dir, dirs, files in os.walk(root):
            yield Path(root_dir), dirs, files


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("--- Running Multi-Language Codebase Scanner on Current Project ---")
    scanner = RepositoryScanner()
    snapshot = scanner.scan(".")

    print(f"\n[OK] Repository Scanned    : {snapshot.repo_path}")
    print(f"[OK] Total Source Files    : {snapshot.total_files}")
    print(f"[OK] Total LOC / SLOC      : {snapshot.total_loc} / {snapshot.total_sloc}")
    print(f"[OK] Languages Breakdown   : {snapshot.languages}")
    print(f"[OK] Total Classes / Types : {snapshot.total_classes}")
    print(f"[OK] Total Functions       : {snapshot.total_functions}")
    print(f"[OK] Codebase Avg Complexity: {snapshot.average_complexity:.2f}")