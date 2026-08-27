"""Domain models for static code analysis and structural metrics."""

from __future__ import annotations
from dataclasses import dataclass, field

@dataclass(frozen=True)
class ImportEntity:
    """Representation of an imported module or symbol."""
    source_module: str
    imported_name: str | None = None
    alias: str | None = None
    is_relative: bool = False
    level: int = 0

@dataclass(frozen=True)
class FunctionEntity:
    """Representation of a function or method definition."""
    name: str
    start_line: int
    end_line: int
    parameter_count: int
    cyclomatic_complexity: int = 1
    is_async: bool = False
    has_docstring: bool = False

    @property
    def line_count(self) -> int:
        """Total lines spanned by the function definition."""
        return max(1, self.end_line - self.start_line + 1)

@dataclass(frozen=True)
class ClassEntity:
    """Representation of a class declaration and its encapsulated methods."""
    name: str
    start_line: int
    end_line: int
    base_classes: tuple[str, ...] = field(default_factory=tuple)
    methods: tuple[FunctionEntity, ...] = field(default_factory=tuple)
    has_docstring: bool = False

    @property
    def line_count(self) -> int:
        """Total lines spanned by the class declaration."""
        return max(1, self.end_line - self.start_line + 1)
    @property
    def method_count(self) -> int:
        """Total number of methods declared within this class."""
        return len(self.methods)


@dataclass(frozen=True)
class FileAnalysisResult:
    """Aggregated structural and metric analysis result for a single source file."""
    file_path: str
    language: str
    loc: int  # Total physical lines
    sloc: int  # Source lines of code (excluding blanks and comments)
    comment_lines: int
    blank_lines: int
    imports: tuple[ImportEntity, ...] = field(default_factory=tuple)
    functions: tuple[FunctionEntity, ...] = field(default_factory=tuple)
    classes: tuple[ClassEntity, ...] = field(default_factory=tuple)

    @property
    def total_functions(self) -> int:
        """Total top-level and class-level functions."""
        class_methods = sum(len(c.methods) for c in self.classes)
        return len(self.functions) + class_methods
    @property
    def average_function_complexity(self) -> float:
        """Average cyclomatic complexity across all functions and methods in the file."""
        all_complexities = [f.cyclomatic_complexity for f in self.functions]
        for c in self.classes:
            all_complexities.extend(m.cyclomatic_complexity for m in c.methods)
        if not all_complexities:
            return 1.0
        return sum(all_complexities) / len(all_complexities)

if __name__ == "__main__":
    print("--- Demonstrating Static Analysis Domain Models ---")
    imp = ImportEntity(
        source_module="pathlib",
        imported_name="Path",
    )
    fn = FunctionEntity(
        name="calculate_metrics",
        start_line=10,
        end_line=25,
        parameter_count=2,
        cyclomatic_complexity=3,
        has_docstring=True,
    )
    cls_entity = ClassEntity(
        name="MetricsEngine",
        start_line=5,
        end_line=30,
        base_classes=("BaseEngine",),
        methods=(fn,),
        has_docstring=True,
    )
    file_result = FileAnalysisResult(
        file_path="src/engine.py",
        language="python",
        loc=35,
        sloc=24,
        comment_lines=6,
        blank_lines=5,
        imports=(imp,),
        classes=(cls_entity,),
    )
    print(f"[OK] File Analyzed      : {file_result.file_path} ({file_result.language})")
    print(f"[OK] LOC / SLOC / Blanks: {file_result.loc} / {file_result.sloc} / {file_result.blank_lines}")
    print(f"[OK] Imports Found      : {len(file_result.imports)} (from {file_result.imports[0].source_module} import {file_result.imports[0].imported_name})")
    print(f"[OK] Classes Declared   : {len(file_result.classes)} ({file_result.classes[0].name})")
    print(f"[OK] Total Functions    : {file_result.total_functions}")
    print(f"[OK] Avg Complexity     : {file_result.average_function_complexity:.2f}")