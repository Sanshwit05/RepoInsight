"""Python AST parser and structural metric extractor."""
from __future__ import annotations
import ast
import logging
from pathlib import Path
from src.repoinsight.analysis.models import (
    ClassEntity,
    FileAnalysisResult,
    FunctionEntity,
    ImportEntity,
)

logger = logging.getLogger(__name__)

class CyclomaticComplexityVisitor(ast.NodeVisitor):
    """Calculates McCabe's Cyclomatic Complexity for an AST subtree."""
    DECISION_NODES = (
        ast.If,
        ast.IfExp,
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.ExceptHandler,
        ast.With,
        ast.AsyncWith,
        ast.Assert,
    )
    def __init__(self) -> None:
        self.complexity: int = 1  

    def generic_visit(self, node: ast.AST) -> None:     
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return
        if isinstance(node, self.DECISION_NODES):
            self.complexity += 1
        elif isinstance(node, ast.BoolOp):
            self.complexity += max(0, len(node.values) - 1)
        super().generic_visit(node)

class PythonSourceAnalyzer:
    """Performs static AST analysis on Python source files."""

    @staticmethod
    def _compute_line_metrics(source_code: str) -> tuple[int, int, int, int]:
        """Calculate physical LOC, SLOC, comment lines, and blank lines.
        Returns:
            tuple[int, int, int, int]: (loc, sloc, comment_lines, blank_lines)
        """
        lines = source_code.splitlines()
        loc = len(lines)
        blank_lines = 0
        comment_lines = 0
        sloc = 0
        for line in lines:
            stripped = line.strip()
            if not stripped:
                blank_lines += 1
            elif stripped.startswith("#"):
                comment_lines += 1
            else:
                sloc += 1
        return loc, sloc, comment_lines, blank_lines

    @staticmethod
    def _calculate_function_complexity(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
        """Calculate cyclomatic complexity of a function/method node."""
        visitor = CyclomaticComplexityVisitor()
        for child in node.body:
            visitor.visit(child)
        return visitor.complexity

    def _extract_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> FunctionEntity:
        """Extract metadata and complexity from a function AST node."""
        has_docstring = ast.get_docstring(node) is not None
        complexity = self._calculate_function_complexity(node)
        param_count = len(node.args.args) + len(node.args.posonlyargs) + len(node.args.kwonlyargs)
        return FunctionEntity(
            name=node.name,
            start_line=node.lineno,
            end_line=getattr(node, "end_lineno", node.lineno),
            parameter_count=param_count,
            cyclomatic_complexity=complexity,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            has_docstring=has_docstring,
        )

    def analyze_source(self, source_code: str, file_path: str = "<memory>") -> FileAnalysisResult:
        """Parse source code string and extract structural AST entities and metrics.
        Args:
            source_code: Python source code text.
            file_path: Relative or absolute path identifier.
        Returns:
            FileAnalysisResult: Structured static analysis domain object.
        """
        loc, sloc, comment_lines, blank_lines = self._compute_line_metrics(source_code)
        try:
            tree = ast.parse(source_code, filename=file_path)
        except SyntaxError as exc:
            logger.warning("SyntaxError parsing %s: %s", file_path, exc)
            return FileAnalysisResult(
                file_path=file_path,
                language="python",
                loc=loc,
                sloc=sloc,
                comment_lines=comment_lines,
                blank_lines=blank_lines,
            )
        imports: list[ImportEntity] = []
        functions: list[FunctionEntity] = []
        classes: list[ClassEntity] = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(
                        ImportEntity(
                            source_module=alias.name,
                            alias=alias.asname,
                            is_relative=False,
                            level=0,
                        )
                    )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                is_relative = node.level > 0
                for alias in node.names:
                    imports.append(
                        ImportEntity(
                            source_module=module,
                            imported_name=alias.name,
                            alias=alias.asname,
                            is_relative=is_relative,
                            level=node.level,
                        )
                    )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(self._extract_function(node))
            elif isinstance(node, ast.ClassDef):
                base_classes = tuple(
                    ast.unparse(b) for b in node.bases if hasattr(ast, "unparse")
                )
                methods = tuple(
                    self._extract_function(m)
                    for m in node.body
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                )
                classes.append(
                    ClassEntity(
                        name=node.name,
                        start_line=node.lineno,
                        end_line=getattr(node, "end_lineno", node.lineno),
                        base_classes=base_classes,
                        methods=methods,
                        has_docstring=ast.get_docstring(node) is not None,
                    )
                )

        return FileAnalysisResult(
            file_path=file_path,
            language="python",
            loc=loc,
            sloc=sloc,
            comment_lines=comment_lines,
            blank_lines=blank_lines,
            imports=tuple(imports),
            functions=tuple(functions),
            classes=tuple(classes),
        )

    def analyze_file(self, file_path: str | Path) -> FileAnalysisResult:
        """Read and analyze a Python source file from disk.
        Args:
            file_path: Local filesystem path.
        Returns:
            FileAnalysisResult: Extraction results.
        """
        path_obj = Path(file_path).resolve()
        try:
            source_code = path_obj.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.error("Failed to read file %s: %s", file_path, exc)
            return FileAnalysisResult(
                file_path=str(file_path),
                language="python",
                loc=0,
                sloc=0,
                comment_lines=0,
                blank_lines=0,
            )
        return self.analyze_source(source_code, file_path=str(file_path))


if __name__ == "__main__":
    sample_code = """
import os
import sys
from pathlib import Path, PurePath
from .models import FileAnalysisResult
# Core calculation service
class RiskCalculator:
    \"\"\"Evaluates risk score from AST telemetry.\"\"\"
    def __init__(self, threshold: float = 0.75):
        self.threshold = threshold
    def evaluate_file(self, complexity: int, churn: int) -> str:
        # Complex multi-branch decision
        if complexity > 10 and churn > 100:
            return "CRITICAL"
        elif complexity > 5 or churn > 50:
            return "MODERATE"
        else:
            return "LOW"
async def async_fetch_metrics(url: str) -> dict:
    \"\"\"Fetches remote metrics asynchronously.\"\"\"
    return {"url": url}
"""
    print("--- Running Python AST Analyzer Test ---")
    analyzer = PythonSourceAnalyzer()
    result = analyzer.analyze_source(sample_code, file_path="example_module.py")
    print(f"[OK] File Analyzed      : {result.file_path}")
    print(f"[OK] LOC / SLOC / Blanks: {result.loc} / {result.sloc} / {result.blank_lines}")
    print(f"[OK] Comments Found     : {result.comment_lines}")
    print(f"\n[OK] Extracted Imports ({len(result.imports)}):")
    for imp in result.imports:
        rel_str = f" (relative level={imp.level})" if imp.is_relative else ""
        imported = f": {imp.imported_name}" if imp.imported_name else ""
        print(f"     -> {imp.source_module}{imported}{rel_str}")
    print(f"\n[OK] Extracted Classes ({len(result.classes)}):")
    for cls in result.classes:
        print(f"     -> {cls.name} (Lines {cls.start_line}-{cls.end_line}, Methods: {cls.method_count})")
        for m in cls.methods:
            print(f"        * Method '{m.name}' -> Complexity: {m.cyclomatic_complexity}, Params: {m.parameter_count}")
    print(f"\n[OK] Top-Level Functions ({len(result.functions)}):")
    for fn in result.functions:
        async_str = "async " if fn.is_async else ""
        print(f"     -> {async_str}{fn.name}() -> Complexity: {fn.cyclomatic_complexity}")
    print(f"\n[OK] Average Function Complexity: {result.average_function_complexity:.2f}")