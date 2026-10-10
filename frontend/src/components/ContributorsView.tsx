import React, { useMemo, useState } from 'react';
import { GuidanceReport, FileGuidance } from '../types';
import { Users, Sparkles, Flame, Lock } from 'lucide-react';
import { Badge, riskVariant } from './Badge';

interface Props {
  guidance: GuidanceReport;
}

interface ContributorRow {
  owner: string;
  filesOwned: number;
  highRisk: number;
  siloed: number;
  beginnerFriendly: number;
  avgHotspot: number;
}

/** Aggregates the file-level guidance data (already returned by the API) by primary_owner.
 * The backend does not expose per-contributor commit/PR counts, so this table is a derived
 * rollup of real file ownership data rather than a separate metric. */
function aggregateContributors(guidance: GuidanceReport): ContributorRow[] {
  const buckets: Array<{ file: FileGuidance; bucket: 'beginner' | 'high_risk' | 'other' }> = [
    ...guidance.beginner_friendly_files.map((file) => ({ file, bucket: 'beginner' as const })),
    ...guidance.high_risk_core_files.map((file) => ({ file, bucket: 'high_risk' as const })),
    ...guidance.siloed_files.map((file) => ({ file, bucket: 'other' as const })),
  ];

  const map = new Map<string, ContributorRow & { hotspotSum: number }>();
  for (const { file, bucket } of buckets) {
    const owner = file.primary_owner || 'Unknown';
    if (!map.has(owner)) {
      map.set(owner, { owner, filesOwned: 0, highRisk: 0, siloed: 0, beginnerFriendly: 0, avgHotspot: 0, hotspotSum: 0 });
    }
    const row = map.get(owner)!;
    row.filesOwned += 1;
    row.hotspotSum += file.hotspot_score;
    if (bucket === 'high_risk') row.highRisk += 1;
    if (bucket === 'beginner') row.beginnerFriendly += 1;
    if (file.is_siloed) row.siloed += 1;
  }

  return Array.from(map.values())
    .map((r) => ({ ...r, avgHotspot: r.filesOwned > 0 ? r.hotspotSum / r.filesOwned : 0 }))
    .sort((a, b) => b.filesOwned - a.filesOwned);
}

function contributorRisk(row: ContributorRow): 'LOW' | 'MEDIUM' | 'HIGH' {
  if (row.highRisk > 0) return 'HIGH';
  if (row.siloed > 0) return 'MEDIUM';
  return 'LOW';
}

export const ContributorsView: React.FC<Props> = ({ guidance }) => {
  const rows = useMemo(() => aggregateContributors(guidance), [guidance]);
  const [tab, setTab] = useState<'beginner' | 'high_risk' | 'silos'>('beginner');

  return (
    <div className="space-y-4">
      <div className="bg-white border border-gh-border rounded-md overflow-hidden">
        <div className="px-4 py-3 border-b border-gh-border flex flex-col sm:flex-row sm:items-center justify-between gap-1">
          <h2 className="text-base font-semibold text-gh-fg flex items-center gap-1.5">
            <Users className="w-4 h-4 text-gh-muted" strokeWidth={1.75} />
            Contributors
          </h2>
          <span className="text-xs text-gh-muted">{guidance.onboarding_summary}</span>
        </div>

        {rows.length === 0 ? (
          <p className="text-xs text-gh-muted px-4 py-6 text-center">No ownership data available for this repository.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gh-border bg-gh-canvas text-left text-xs uppercase tracking-wide text-gh-muted">
                  <th className="px-4 py-2 font-medium">Contributor</th>
                  <th className="px-4 py-2 font-medium text-right">Files Owned</th>
                  <th className="px-4 py-2 font-medium text-right">High-Risk</th>
                  <th className="px-4 py-2 font-medium text-right">Siloed</th>
                  <th className="px-4 py-2 font-medium text-right">Beginner-Friendly</th>
                  <th className="px-4 py-2 font-medium text-right">Avg Hotspot</th>
                  <th className="px-4 py-2 font-medium text-right">Risk</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.owner} className="border-b border-gh-border last:border-0 hover:bg-gh-canvas transition-colors">
                    <td className="px-4 py-2 font-mono text-gh-fg">{r.owner}</td>
                    <td className="px-4 py-2 text-right text-gh-fg tabular-nums">{r.filesOwned}</td>
                    <td className="px-4 py-2 text-right text-gh-fg tabular-nums">{r.highRisk}</td>
                    <td className="px-4 py-2 text-right text-gh-fg tabular-nums">{r.siloed}</td>
                    <td className="px-4 py-2 text-right text-gh-fg tabular-nums">{r.beginnerFriendly}</td>
                    <td className="px-4 py-2 text-right text-gh-fg tabular-nums">{r.avgHotspot.toFixed(2)}</td>
                    <td className="px-4 py-2 text-right">
                      <Badge variant={riskVariant(contributorRisk(r))}>{contributorRisk(r)}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Original file-level guidance breakdown, preserved */}
      <div className="bg-white border border-gh-border rounded-md p-4 space-y-4">
        <h3 className="text-base font-semibold text-gh-fg">File-Level Guidance</h3>

        <div className="flex space-x-2 border-b border-gh-border pb-2 text-xs">
          <button
            onClick={() => setTab('beginner')}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md font-medium transition-colors ${
              tab === 'beginner' ? 'bg-gh-successSubtle text-gh-success border border-gh-successBorder' : 'text-gh-muted hover:text-gh-fg'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Beginner Friendly ({guidance.beginner_friendly_files.length})</span>
          </button>

          <button
            onClick={() => setTab('high_risk')}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md font-medium transition-colors ${
              tab === 'high_risk' ? 'bg-gh-dangerSubtle text-gh-danger border border-gh-dangerBorder' : 'text-gh-muted hover:text-gh-fg'
            }`}
          >
            <Flame className="w-3.5 h-3.5" />
            <span>High-Risk Core ({guidance.high_risk_core_files.length})</span>
          </button>

          <button
            onClick={() => setTab('silos')}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md font-medium transition-colors ${
              tab === 'silos' ? 'bg-gh-warningSubtle text-gh-warning border border-gh-warningBorder' : 'text-gh-muted hover:text-gh-fg'
            }`}
          >
            <Lock className="w-3.5 h-3.5" />
            <span>Knowledge Silos ({guidance.siloed_files.length})</span>
          </button>
        </div>

        <div className="space-y-2 pt-1">
          {tab === 'beginner' &&
            guidance.beginner_friendly_files.map((g, i) => (
              <div key={i} className="bg-gh-canvas p-3 rounded-md border border-gh-border flex items-center justify-between text-xs">
                <div className="min-w-0">
                  <p className="font-mono text-gh-fg font-medium truncate">{g.file_path}</p>
                  <p className="text-gh-muted mt-0.5">{g.advice}</p>
                </div>
                <Badge variant="success" className="shrink-0 ml-2">{g.review_difficulty}</Badge>
              </div>
            ))}

          {tab === 'high_risk' &&
            guidance.high_risk_core_files.map((g, i) => (
              <div key={i} className="bg-gh-canvas p-3 rounded-md border border-gh-border flex items-center justify-between text-xs">
                <div className="min-w-0">
                  <p className="font-mono text-gh-fg font-medium truncate">{g.file_path}</p>
                  <p className="text-gh-muted mt-0.5">{g.advice}</p>
                </div>
                <Badge variant="danger" className="shrink-0 ml-2">{g.review_difficulty}</Badge>
              </div>
            ))}

          {tab === 'silos' &&
            guidance.siloed_files.map((g, i) => (
              <div key={i} className="bg-gh-canvas p-3 rounded-md border border-gh-border flex items-center justify-between text-xs">
                <div className="min-w-0">
                  <p className="font-mono text-gh-fg font-medium truncate">{g.file_path}</p>
                  <p className="text-gh-muted mt-0.5">{g.advice}</p>
                </div>
                <Badge variant="warning" className="shrink-0 ml-2">Owner: {g.primary_owner}</Badge>
              </div>
            ))}
        </div>
      </div>
    </div>
  );
};
