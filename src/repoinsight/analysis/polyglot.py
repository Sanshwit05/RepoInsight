"""Polyglot static analysis engine supporting multi-language codebases."""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from pathlib import Path

from src.repoinsight.analysis.models import (
    ClassEntity,
    FileAnalysisResult,
    FunctionEntity,
    ImportEntity,
)
from src.repoinsight.analysis.python_parser import PythonSourceAnalyzer

logger = logging.getLogger(__name__)


class BaseLanguageParser(ABC):
    """Abstract base class for programming language static parsers."""

    @abstractmethod
    def supported_extensions(self) -> frozenset[str]:
        """Return the set of file extensions supported by this parser."""

    @abstractmethod
    def analyze_source(self, source_code: str, file_path: str) -> FileAnalysisResult:
        """Parse source code string and extract structural AST entities and metrics."""


class PythonLanguageParser(BaseLanguageParser):
    """Python static analyzer adapter wrapping PythonSourceAnalyzer."""

    def __init__(self) -> None:
        self._analyzer = PythonSourceAnalyzer()

    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".py", ".pyw"})

    def analyze_source(self, source_code: str, file_path: str) -> FileAnalysisResult:
        return self._analyzer.analyze_source(source_code, file_path=file_path)


class PolyglotSourceAnalyzer(BaseLanguageParser):
    """Universal parser for C-family and modern languages (JS, TS, Java, Go, Rust, C/C++, C#)."""

    # Supported file extensions mapped to language names
    EXTENSION_LANGUAGE_MAP: dict[str, str] = {
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".cpp": "cpp",
        ".c": "c",
        ".h": "c",
        ".hpp": "cpp",
        ".cs": "csharp",
    }

    # Regex patterns for imports across languages
    IMPORT_PATTERNS = (
        # JS/TS: import ... from 'module' or import 'module'
        re.compile(r"""(?:import\s+(?:[\w*\s{},$]+from\s+)?['"](?P<js_mod>[^'"]+)['"]|require\(['"](?P<req_mod>[^'"]+)['"]\))"""),
        # Java: import [static] package.name.Class;
        re.compile(r"""import\s+(?:static\s+)?(?P<java_mod>[a-zA-Z0-9_.]+);"""),
        # Go: import "path/to/pkg" or import ( ... )
        re.compile(r"""(?:import\s+['"](?P<go_mod>[^'"]+)['"]|import\s*\((?P<go_block>[^)]+)\))"""),
        # C/C++: #include "file.h" or #include <lib>
        re.compile(r"""#include\s+[<"](?P<c_mod>[^>"]+)[>"]"""),
        # Rust: use crate::module::symbol;
        re.compile(r"""use\s+(?P<rust_mod>[a-zA-Z0-9_:]+);"""),
    )

    # Regex for function declarations
    FUNCTION_PATTERN = re.compile(
        r"""(?m)(?:"""
        # JS/TS/Java/C/C++: function name() or returnType name()
        r"""(?:(?:async\s+)?function\s+(?P<fn1>[a-zA-Z0-9_$]+)\s*\()|"""
        # JS/TS: const/let/var name = (async)? (...) =>
        r"""(?:(?:const|let|var)\s+(?P<fn2>[a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)|"""
        # Go: func [(receiver)] name(...)
        r"""(?:func\s+(?:\([^)]+\)\s+)?(?P<fn_go>[a-zA-Z0-9_]+)\s*\()|"""
        # Rust: fn name(...)
        r"""(?:fn\s+(?P<fn_rust>[a-zA-Z0-9_]+)\s*\()|"""
        # Java/C#/C++: public/private/protected [static] returnType name(...)
        r"""(?:(?:public|private|protected|static|\s)+\s+[a-zA-Z0-9_<>[\]]+\s+(?P<fn_oop>[a-zA-Z0-9_]+)\s*\()"""
        r""")"""
    )

    # Regex for class/struct/interface declarations
    CLASS_PATTERN = re.compile(
        r"""(?m)\b(?:class|interface|struct|type)\s+(?P<cls_name>[a-zA-Z0-9_$]+)"""
    )

    # Regex for complexity decision branches
    DECISION_PATTERN = re.compile(
        r"""\b(?:if|else\s+if|for|while|switch|case|catch)\b|&&|\|\||\?"""
    )

    def supported_extensions(self) -> frozenset[str]:
        return frozenset(self.EXTENSION_LANGUAGE_MAP.keys())

    def analyze_source(self, source_code: str, file_path: str) -> FileAnalysisResult:
        ext = Path(file_path).suffix.lower()
        language = self.EXTENSION_LANGUAGE_MAP.get(ext, "generic")

        lines = source_code.splitlines()
        loc = len(lines)
        blank_lines = 0
        comment_lines = 0
        sloc = 0
        in_block_comment = False

        for line in lines:
            stripped = line.strip()
            if not stripped:
                blank_lines += 1
                continue

            # Handle block comments /* ... */
            if in_block_comment:
                comment_lines += 1
                if "*/" in stripped:
                    in_block_comment = False
                continue
            if stripped.startswith("/*"):
                comment_lines += 1
                if "*/" not in stripped:
                    in_block_comment = True
                continue

            # Line comments
            if stripped.startswith("//") or stripped.startswith("#"):
                comment_lines += 1
            else:
                sloc += 1

        # 1. Extract imports
        imports: list[ImportEntity] = []
        for pattern in self.IMPORT_PATTERNS:
            for match in pattern.finditer(source_code):
                mod_name = (
                    match.groupdict().get("js_mod")
                    or match.groupdict().get("req_mod")
                    or match.groupdict().get("java_mod")
                    or match.groupdict().get("go_mod")
                    or match.groupdict().get("c_mod")
                    or match.groupdict().get("rust_mod")
                )
                if mod_name:
                    is_rel = mod_name.startswith("./") or mod_name.startswith("../")
                    level = 1 if mod_name.startswith("./") else (2 if mod_name.startswith("../") else 0)
                    imports.append(
                        ImportEntity(
                            source_module=mod_name,
                            is_relative=is_rel,
                            level=level,
                        )
                    )
                elif match.groupdict().get("go_block"):
                    # Multi-line Go import block
                    block_content = match.group("go_block")
                    for sub in re.finditer(r"""['"]([^'"]+)['"]""", block_content):
                        imports.append(
                            ImportEntity(source_module=sub.group(1), is_relative=False)
                        )

        # 2. Extract classes
        classes: list[ClassEntity] = []
        for match in self.CLASS_PATTERN.finditer(source_code):
            name = match.group("cls_name")
            line_no = source_code[: match.start()].count("\n") + 1
            classes.append(
                ClassEntity(name=name, start_line=line_no, end_line=line_no)
            )

        # 3. Extract functions
        functions: list[FunctionEntity] = []
        for match in self.FUNCTION_PATTERN.finditer(source_code):
            fn_name = (
                match.groupdict().get("fn1")
                or match.groupdict().get("fn2")
                or match.groupdict().get("fn_go")
                or match.groupdict().get("fn_rust")
                or match.groupdict().get("fn_oop")
            )
            if fn_name and fn_name not in {"if", "for", "while", "switch"}:
                line_no = source_code[: match.start()].count("\n") + 1
                # Estimate local complexity in the surrounding function body
                functions.append(
                    FunctionEntity(
                        name=fn_name,
                        start_line=line_no,
                        end_line=line_no,
                        parameter_count=0,
                        cyclomatic_complexity=1,
                    )
                )

        # 4. Overall decision complexity estimate
        total_decisions = len(self.DECISION_PATTERN.findall(source_code))
        if functions:
            avg_comp = max(1, 1 + total_decisions // len(functions))
            # Update functions with distributed complexity estimate
            functions = [
                FunctionEntity(
                    name=f.name,
                    start_line=f.start_line,
                    end_line=f.end_line,
                    parameter_count=f.parameter_count,
                    cyclomatic_complexity=avg_comp,
                )
                for f in functions
            ]

        return FileAnalysisResult(
            file_path=file_path,
            language=language,
            loc=loc,
            sloc=sloc,
            comment_lines=comment_lines,
            blank_lines=blank_lines,
            imports=tuple(imports),
            functions=tuple(functions),
            classes=tuple(classes),
        )


class ParserRegistry:
    """Registry managing available language parsers and file extension routing."""

    def __init__(self) -> None:
        self._parsers: dict[str, BaseLanguageParser] = {}
        self._default_polyglot = PolyglotSourceAnalyzer()

        # Register default parsers
        self.register(PythonLanguageParser())
        self.register(self._default_polyglot)

    def register(self, parser: BaseLanguageParser) -> None:
        """Register a parser instance for all its supported extensions."""
        for ext in parser.supported_extensions():
            self._parsers[ext.lower()] = parser

    def get_parser_for_file(self, file_path: str | Path) -> BaseLanguageParser | None:
        """Retrieve the appropriate parser for a given file path based on extension."""
        ext = Path(file_path).suffix.lower()
        return self._parsers.get(ext)

    def supported_extensions(self) -> set[str]:
        """Return all supported file extensions across registered parsers."""
        return set(self._parsers.keys())


if __name__ == "__main__":
    print("--- Demonstrating Polyglot Multi-Language Parser ---")
    registry = ParserRegistry()

    # Sample TypeScript snippet
    ts_code = """
import React, { useState } from 'react';
import { Button } from './components/Button';
import axios from 'axios';

/* Component Interface */
interface UserDashboardProps {
    userId: string;
}

export const UserDashboard = ({ userId }: UserDashboardProps) => {
    const [count, setCount] = useState(0);

    const handleClick = () => {
        if (count > 10 || userId === 'admin') {
            setCount(0);
        } else {
            setCount(count + 1);
        }
    };

    return <Button onClick={handleClick}>Click</Button>;
};
"""

    # Sample Go snippet
    go_code = """
package main

import (
    "fmt"
    "net/http"
)

type ServerConfig struct {
    Port int
}

func StartServer(cfg ServerConfig) error {
    if cfg.Port == 0 {
        return fmt.Errorf("invalid port")
    }
    return http.ListenAndServe(fmt.Sprintf(":%d", cfg.Port), nil)
}
"""

    # 1. Test TypeScript
    ts_parser = registry.get_parser_for_file("src/Dashboard.tsx")
    assert ts_parser is not None
    ts_result = ts_parser.analyze_source(ts_code, "src/Dashboard.tsx")
    print(f"\n[OK] TypeScript File : {ts_result.file_path} ({ts_result.language})")
    print(f"     SLOC / Comments : {ts_result.sloc} / {ts_result.comment_lines}")
    print(f"     Imports Extracted ({len(ts_result.imports)}): {[i.source_module for i in ts_result.imports]}")
    print(f"     Classes/Types   ({len(ts_result.classes)}): {[c.name for c in ts_result.classes]}")
    print(f"     Functions Found ({len(ts_result.functions)}): {[f.name for f in ts_result.functions]}")

    # 2. Test Go
    go_parser = registry.get_parser_for_file("pkg/server.go")
    assert go_parser is not None
    go_result = go_parser.analyze_source(go_code, "pkg/server.go")
    print(f"\n[OK] Go File         : {go_result.file_path} ({go_result.language})")
    print(f"     SLOC / Comments : {go_result.sloc} / {go_result.comment_lines}")
    print(f"     Imports Extracted ({len(go_result.imports)}): {[i.source_module for i in go_result.imports]}")
    print(f"     Structs/Types   ({len(go_result.classes)}): {[c.name for c in go_result.classes]}")
    print(f"     Functions Found ({len(go_result.functions)}): {[f.name for f in go_result.functions]}")