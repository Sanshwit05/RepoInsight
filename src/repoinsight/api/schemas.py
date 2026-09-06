"""Pydantic request and response schemas for the RepoInsight AI REST API."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


# --- Ingestion & Analysis Schemas ---

class AnalyzeRepoRequest(BaseModel):
    """Request payload to ingest and analyze a remote or local repository."""

    repo_url: str = Field(
        ...,
        description="Remote GitHub/GitLab URL or local filesystem path.",
        examples=["https://github.com/octocat/Hello-World"],
    )
    max_commits: int = Field(
        default=200,
        ge=1,
        le=5000,
        description="Maximum historical commits to mine.",
    )


class SubScoresSchema(BaseModel):
    """Mathematical health sub-scores (0-100)."""

    complexity_score: float
    hotspot_score: float
    architecture_score: float
    ownership_score: float


class HealthReportResponse(BaseModel):
    """Repository health scorecard and executive summary."""

    repo_path: str
    overall_score: float
    grade: str
    sub_scores: SubScoresSchema
    total_files: int
    total_sloc: int
    total_commits: int
    bus_factor: int
    critical_hotspots_count: int
    circular_dependencies_count: int
    key_findings: list[str]


# --- Graph Schemas ---

class GraphDataResponse(BaseModel):
    """Cytoscape.js compatible graph elements and topological metrics."""

    total_nodes: int
    total_edges: int
    density: float
    is_dag: bool
    cycles_count: int
    top_hubs: list[str]
    top_bottlenecks: list[str]
    elements: dict[str, list[dict[str, Any]]]


# --- Contributor Guidance Schemas ---

class FileGuidanceItem(BaseModel):
    """Individual file guidance item."""

    file_path: str
    zone: str
    review_difficulty: str
    primary_owner: str
    in_degree: int
    avg_complexity: float
    hotspot_score: float
    is_siloed: bool
    advice: str


class GuidanceResponse(BaseModel):
    """Contributor onboarding and zone stratification report."""

    total_files: int
    onboarding_summary: str
    beginner_friendly_files: list[FileGuidanceItem]
    high_risk_core_files: list[FileGuidanceItem]
    siloed_files: list[FileGuidanceItem]


# --- Contribution Prediction Schemas ---

class ProposedFileChangeSchema(BaseModel):
    """Represents a proposed modification to an individual file in a Pull Request."""

    file_path: str = Field(..., description="Repository-relative POSIX path of the file.")
    added_lines: int = Field(default=0, ge=0, description="Lines of code added.")
    deleted_lines: int = Field(default=0, ge=0, description="Lines of code deleted.")
    change_type: str = Field(default="MODIFY", description="ADD, MODIFY, DELETE, or RENAME.")


class PredictContributionRequest(BaseModel):
    """Request payload to evaluate the impact of a proposed contribution."""

    repo_url: str = Field(
        ...,
        description="Target repository URL or workspace path.",
        examples=["https://github.com/octocat/Hello-World"],
    )
    files: list[ProposedFileChangeSchema] = Field(
        ...,
        min_length=1,
        description="List of proposed file modifications.",
    )
    author_email: str = Field(default="", description="Optional author email identifier.")
    message: str = Field(default="", description="Proposed commit or Pull Request title.")


class PredictContributionResponse(BaseModel):
    """Prediction diagnosis and evidence-grounded explainability report."""

    impact_score: float
    risk_level: str
    confidence: float
    review_difficulty: str
    likely_affected_files: list[str]
    primary_risk_factors: list[str]
    class_probabilities: dict[str, float]
    summary_verdict: str
    markdown_pr_comment: str


if __name__ == "__main__":
    print("--- Demonstrating Pydantic API Schemas ---")

    sample_req = AnalyzeRepoRequest(
        repo_url="https://github.com/pallets/flask",
        max_commits=150,
    )
    print(f"[OK] Validated Request: {sample_req.model_dump_json(indent=2)}")

    sample_change = ProposedFileChangeSchema(
        file_path="src/flask/app.py",
        added_lines=45,
        deleted_lines=10,
    )
    print(f"[OK] Validated File Change: {sample_change.model_dump_json(indent=2)}")