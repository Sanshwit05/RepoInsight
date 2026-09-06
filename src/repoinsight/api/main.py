"""FastAPI application providing REST API endpoints for RepoInsight AI."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from src.repoinsight.analysis.scanner import RepositoryScanner
from src.repoinsight.api.schemas import (
    AnalyzeRepoRequest,
    FileGuidanceItem,
    GraphDataResponse,
    GuidanceResponse,
    HealthReportResponse,
    PredictContributionRequest,
    PredictContributionResponse,
    SubScoresSchema,
)
from src.repoinsight.graph.builder import DependencyGraphBuilder
from src.repoinsight.graph.exporter import GraphExporter
from src.repoinsight.graph.metrics import GraphMetricsEngine
from src.repoinsight.guidance.recommender import ContributorGuidanceEngine
from src.repoinsight.health.churn import ChurnAggregator
from src.repoinsight.health.engine import RepositoryHealthEngine
from src.repoinsight.health.hotspots import HotspotDetector
from src.repoinsight.health.ownership import OwnershipEngine
from src.repoinsight.ingestion.cloner import RepositoryCloner
from src.repoinsight.ingestion.validator import parse_repository_url
from src.repoinsight.mining.miner import GitRepositoryMiner
from src.repoinsight.ml.explainer import ContributionExplainer
from src.repoinsight.ml.predictor import (
    ContributionImpactPredictor,
    ProposedContribution,
    ProposedFileChange,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Initialize FastAPI application
app = FastAPI(
    title="RepoInsight AI — REST API",
    description="Intelligent Repository Health Analysis and Contribution Impact Prediction using Graph ML.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for React frontend (localhost:5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared singletons
cloner = RepositoryCloner(workspace_dir="data/repositories")
health_engine = RepositoryHealthEngine()
guidance_engine = ContributorGuidanceEngine()
explainer = ContributionExplainer()


def _resolve_repo_path(repo_input: str) -> Path:
    """Resolve a URL or local directory string to a verified local Path."""
    clean_input = repo_input.strip()

    # Case 1: Existing local directory path
    local_candidate = Path(clean_input).resolve()
    if local_candidate.exists() and local_candidate.is_dir():
        return local_candidate

    # Case 2: Remote Git repository URL (HTTPS or SSH)
    try:
        target = parse_repository_url(clean_input)
        return cloner.clone(target)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to resolve or clone repository '{repo_input}': {exc}",
        ) from exc


# --- API Routes ---

@app.get("/", tags=["System"])
async def root_landing() -> dict[str, Any]:
    """Root landing endpoint providing system status and API entry points."""
    return {
        "title": "RepoInsight AI — REST API",
        "status": "online",
        "docs_url": "/docs",
        "health_check": "/health",
        "version": "1.0.0",
    }


@app.get("/health", tags=["System"])
async def system_health_check() -> dict[str, str]:
    """Basic service health and readiness probe."""
    return {"status": "ok", "service": "RepoInsight AI Backend", "version": "1.0.0"}


@app.post("/api/v1/repository/analyze", response_model=HealthReportResponse, tags=["Repository Health"])
async def analyze_repository(request: AnalyzeRepoRequest) -> HealthReportResponse:
    """Ingest, scan, and compute a multi-pillar health audit for a repository."""
    repo_path = _resolve_repo_path(request.repo_url)

    try:
        report, snapshot, graph_rep, churn_rep, hot_rep, bus_rep = health_engine.analyze(
            repo_path=repo_path,
            max_commits=request.max_commits,
        )
    except Exception as exc:
        logger.error("Health analysis failed for %s: %s", repo_path, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis pipeline error: {exc}",
        ) from exc

    return HealthReportResponse(
        repo_path=str(repo_path),
        overall_score=report.overall_score,
        grade=report.grade,
        sub_scores=SubScoresSchema(
            complexity_score=report.sub_scores.complexity_score,
            hotspot_score=report.sub_scores.hotspot_score,
            architecture_score=report.sub_scores.architecture_score,
            ownership_score=report.sub_scores.ownership_score,
        ),
        total_files=report.total_files,
        total_sloc=report.total_sloc,
        total_commits=report.total_commits,
        bus_factor=report.bus_factor,
        critical_hotspots_count=report.critical_hotspots_count,
        circular_dependencies_count=report.circular_dependencies_count,
        key_findings=list(report.key_findings),
    )


@app.post("/api/v1/repository/graph", response_model=GraphDataResponse, tags=["Dependency Graph"])
async def get_repository_graph(request: AnalyzeRepoRequest) -> GraphDataResponse:
    """Generate and return the Cytoscape.js dependency graph and centralities."""
    repo_path = _resolve_repo_path(request.repo_url)

    scanner = RepositoryScanner()
    snapshot = scanner.scan(repo_path)
    builder = DependencyGraphBuilder()
    graph = builder.build_graph(snapshot)
    graph_report = GraphMetricsEngine().compute_metrics(graph)

    cy_data = GraphExporter.to_cytoscape_json(graph, graph_report)

    return GraphDataResponse(
        total_nodes=graph_report.total_nodes,
        total_edges=graph_report.total_edges,
        density=graph_report.density,
        is_dag=graph_report.is_dag,
        cycles_count=len(graph_report.cycles),
        top_hubs=list(graph_report.top_hubs),
        top_bottlenecks=list(graph_report.top_bottlenecks),
        elements=cy_data["elements"],
    )


@app.post("/api/v1/repository/guidance", response_model=GuidanceResponse, tags=["Contributor Guidance"])
async def get_contributor_guidance(request: AnalyzeRepoRequest) -> GuidanceResponse:
    """Retrieve deterministic onboarding guidance, safe zones, and knowledge silos."""
    repo_path = _resolve_repo_path(request.repo_url)

    scanner = RepositoryScanner()
    snapshot = scanner.scan(repo_path)
    graph = DependencyGraphBuilder().build_graph(snapshot)
    graph_report = GraphMetricsEngine().compute_metrics(graph)

    has_git = (repo_path / ".git").exists()
    commits = list(GitRepositoryMiner(repo_path).mine_commits(max_commits=request.max_commits)) if has_git else []

    churn_summary = ChurnAggregator().aggregate(commits)
    hotspot_report = HotspotDetector().detect(snapshot, churn_summary)
    bus_report = OwnershipEngine().compute(commits)

    guidance_report = guidance_engine.generate_guidance(
        snapshot, graph_report, churn_summary, hotspot_report, bus_report
    )

    def _to_schema_item(g) -> FileGuidanceItem:
        return FileGuidanceItem(
            file_path=g.file_path,
            zone=g.zone.value,
            review_difficulty=g.review_difficulty.value,
            primary_owner=g.primary_owner,
            in_degree=g.in_degree,
            avg_complexity=g.avg_complexity,
            hotspot_score=g.hotspot_score,
            is_siloed=g.is_siloed,
            advice=g.advice,
        )

    return GuidanceResponse(
        total_files=guidance_report.total_files,
        onboarding_summary=guidance_report.onboarding_summary,
        beginner_friendly_files=[_to_schema_item(g) for g in guidance_report.beginner_friendly_files],
        high_risk_core_files=[_to_schema_item(g) for g in guidance_report.high_risk_core_files],
        siloed_files=[_to_schema_item(g) for g in guidance_report.siloed_files],
    )


@app.post("/api/v1/predict/contribution", response_model=PredictContributionResponse, tags=["Contribution Impact ML"])
async def predict_contribution_impact(request: PredictContributionRequest) -> PredictContributionResponse:
    """Predict the impact score, risk level, confidence, and blast radius of a proposed change."""
    repo_path = _resolve_repo_path(request.repo_url)

    predictor = ContributionImpactPredictor(repo_path=repo_path)

    proposed_files = tuple(
        ProposedFileChange(
            file_path=f.file_path,
            added_lines=f.added_lines,
            deleted_lines=f.deleted_lines,
            change_type=f.change_type,
        )
        for f in request.files
    )
    contribution = ProposedContribution(
        files=proposed_files,
        author_email=request.author_email,
        message=request.message,
    )

    diagnosis = predictor.predict_contribution(contribution)
    explanation = explainer.explain(diagnosis, contribution, predictor.graph, predictor.snapshot)

    return PredictContributionResponse(
        impact_score=diagnosis.impact_score,
        risk_level=diagnosis.risk_level.name,
        confidence=diagnosis.confidence,
        review_difficulty=diagnosis.review_difficulty.value,
        likely_affected_files=list(diagnosis.likely_affected_files),
        primary_risk_factors=list(diagnosis.primary_risk_factors),
        class_probabilities=diagnosis.class_probabilities,
        summary_verdict=diagnosis.summary_verdict,
        markdown_pr_comment=explanation.markdown_pr_comment,
    )


if __name__ == "__main__":
    import uvicorn

    print("--- Starting RepoInsight AI FastAPI Server on http://localhost:8000 ---")
    uvicorn.run("src.repoinsight.api.main:app", host="0.0.0.0", port=8000, reload=True)