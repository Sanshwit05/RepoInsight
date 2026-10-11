import React from 'react';
import { HealthReport, GraphData, GuidanceReport } from '../types';
import { CheckCircle2, GitBranch, Network } from 'lucide-react';
import { Badge } from './Badge';
import { MetricPanel } from './MetricPanel';

interface Props {
  report: HealthReport;
  graphData: GraphData | null;
  guidanceData: GuidanceReport | null;
}

function countDistinctOwners(guidance: GuidanceReport | null): number | null {
  if (!guidance) return null;
  const owners = new Set<string>();
  [...guidance.beginner_friendly_files, ...guidance.high_risk_core_files, ...guidance.siloed_files].forEach((f) => {
    if (f.primary_owner) owners.add(f.primary_owner);
  });
  return owners.size;
}

const round1 = (n: number) => Math.round(n * 10) / 10;

export const HealthOverview: React.FC<Props> = ({ report, graphData, guidanceData }) => {
  const contributorCount = countDistinctOwners(guidanceData);
  const riskScore = round1(100 - report.overall_score);

  return (
    <div className="space-y-4">
      {/* Repository identity strip */}
      <div className="bg-white border border-gh-border rounded-md px-4 py-3 flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs text-gh-muted uppercase tracking-wide">Repository</div>
          <div className="text-base font-semibold text-gh-fg font-mono truncate max-w-lg" title={report.repo_path}>
            {report.repo_path}
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant="accent">Grade {report.grade}</Badge>
          {report.circular_dependencies_count > 0 ? (
            <Badge variant="danger">{report.circular_dependencies_count} circular deps</Badge>
          ) : (
            <Badge variant="success">No circular deps</Badge>
          )}
        </div>
      </div>

      {/* Metric panels */}
      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3">
        <MetricPanel label="Overall Health" value={`${round1(report.overall_score)}`} hint="out of 100" />
        <MetricPanel label="Files" value={report.total_files.toLocaleString()} />
        <MetricPanel label="Dependencies" value={graphData ? graphData.total_edges.toLocaleString() : '—'} hint="graph edges" />
        <MetricPanel label="Contributors" value={contributorCount ?? '—'} />
        <MetricPanel label="Commits" value={report.total_commits.toLocaleString()} />
        <MetricPanel label="Risk Score" value={`${riskScore}%`} hint={`${report.critical_hotspots_count} hotspots`} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Repository Health */}
        <div className="lg:col-span-2 bg-white border border-gh-border rounded-md p-4 space-y-4">
          <h3 className="text-base font-semibold text-gh-fg">Repository Health</h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-gh-canvas p-3 rounded-md border border-gh-border">
              <span className="text-xs text-gh-muted">Complexity &amp; AST</span>
              <p className="text-base font-semibold text-gh-fg mt-0.5 tabular-nums">{round1(report.sub_scores.complexity_score)} / 100</p>
            </div>
            <div className="bg-gh-canvas p-3 rounded-md border border-gh-border">
              <span className="text-xs text-gh-muted">Hotspots &amp; Debt</span>
              <p className="text-base font-semibold text-gh-fg mt-0.5 tabular-nums">{round1(report.sub_scores.hotspot_score)} / 100</p>
            </div>
            <div className="bg-gh-canvas p-3 rounded-md border border-gh-border">
              <span className="text-xs text-gh-muted">Architecture DAG</span>
              <p className="text-base font-semibold text-gh-fg mt-0.5 tabular-nums">{round1(report.sub_scores.architecture_score)} / 100</p>
            </div>
            <div className="bg-gh-canvas p-3 rounded-md border border-gh-border">
              <span className="text-xs text-gh-muted">Ownership &amp; Silos</span>
              <p className="text-base font-semibold text-gh-fg mt-0.5 tabular-nums">{round1(report.sub_scores.ownership_score)} / 100</p>
            </div>
          </div>

          <div>
            <h4 className="text-xs font-semibold text-gh-muted mb-2 uppercase tracking-wide">Key Findings</h4>
            <div className="space-y-1.5">
              {report.key_findings.map((f, i) => (
                <div key={i} className="flex items-start space-x-2 text-sm text-gh-fg">
                  <CheckCircle2 className="w-3.5 h-3.5 text-gh-muted shrink-0 mt-0.5" />
                  <span>{f}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Dependency overview */}
        <div className="bg-white border border-gh-border rounded-md p-4 space-y-3">
          <h3 className="text-base font-semibold text-gh-fg flex items-center gap-1.5">
            <Network className="w-4 h-4 text-gh-muted" strokeWidth={1.75} />
            Dependency Overview
          </h3>

          {graphData ? (
            <div className="space-y-2 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-gh-muted">Nodes</span>
                <span className="text-gh-fg font-medium tabular-nums">{graphData.total_nodes}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gh-muted">Edges</span>
                <span className="text-gh-fg font-medium tabular-nums">{graphData.total_edges}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gh-muted">Density</span>
                <span className="text-gh-fg font-medium tabular-nums">{graphData.density.toFixed(3)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gh-muted">Structure</span>
                {graphData.is_dag ? (
                  <Badge variant="success">Acyclic (DAG)</Badge>
                ) : (
                  <Badge variant="danger">{graphData.cycles_count} cycle(s)</Badge>
                )}
              </div>
              {graphData.top_hubs.length > 0 && (
                <div className="pt-2 border-t border-gh-border">
                  <span className="text-xs text-gh-muted uppercase tracking-wide flex items-center gap-1">
                    <GitBranch className="w-3 h-3" /> Top Hubs
                  </span>
                  <ul className="mt-1 space-y-0.5">
                    {graphData.top_hubs.slice(0, 3).map((h, i) => (
                      <li key={i} className="font-mono text-xs text-gh-fg truncate">{h}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            <p className="text-xs text-gh-muted">Dependency graph unavailable for this repository.</p>
          )}
        </div>
      </div>
    </div>
  );
};
