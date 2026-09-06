export interface SubScores {
  complexity_score: number;
  hotspot_score: number;
  architecture_score: number;
  ownership_score: number;
}
export interface HealthReport {
  repo_path: string;
  overall_score: number;
  grade: string;
  sub_scores: SubScores;
  total_files: number;
  total_sloc: number;
  total_commits: number;
  bus_factor: number;
  critical_hotspots_count: number;
  circular_dependencies_count: number;
  key_findings: string[];
}
export interface GraphData {
  total_nodes: number;
  total_edges: number;
  density: number;
  is_dag: boolean;
  cycles_count: number;
  top_hubs: string[];
  top_bottlenecks: string[];
  elements: {
    nodes: Array<{ data: any }>;
    edges: Array<{ data: any }>;
  };
}
export interface FileGuidance {
  file_path: string;
  zone: string;
  review_difficulty: string;
  primary_owner: string;
  in_degree: number;
  avg_complexity: number;
  hotspot_score: number;
  is_siloed: boolean;
  advice: string;
}
export interface GuidanceReport {
  total_files: number;
  onboarding_summary: string;
  beginner_friendly_files: FileGuidance[];
  high_risk_core_files: FileGuidance[];
  siloed_files: FileGuidance[];
}
export interface PredictionResult {
  impact_score: number;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH';
  confidence: number;
  review_difficulty: string;
  likely_affected_files: string[];
  primary_risk_factors: string[];
  class_probabilities: Record<string, number>;
  summary_verdict: string;
  markdown_pr_comment: string;
}
