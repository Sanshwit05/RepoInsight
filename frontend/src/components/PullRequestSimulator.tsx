import React, { useState } from 'react';
import { PredictionResult } from '../types';
import { GitPullRequest, Copy, Check, AlertCircle, FileWarning } from 'lucide-react';
import { Badge, riskVariant } from './Badge';
import { MetricPanel } from './MetricPanel';

interface Props {
  repoUrl: string;
}

export const PullRequestSimulator: React.FC<Props> = ({ repoUrl }) => {
  const [filePath, setFilePath] = useState('src/repoinsight/analysis/models.py');
  const [added, setAdded] = useState(65);
  const [deleted, setDeleted] = useState(15);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await fetch('/api/v1/predict/contribution', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          repo_url: repoUrl,
          files: [{ file_path: filePath, added_lines: added, deleted_lines: deleted, change_type: 'MODIFY' }],
          author_email: 'developer@example.com',
          message: 'simulated contribution',
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data: PredictionResult = await res.json();
      setResult(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (result) {
      navigator.clipboard.writeText(result.markdown_pr_comment);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="bg-white border border-gh-border rounded-md p-4 space-y-5">
      <div className="border-b border-gh-border pb-3">
        <h2 className="text-base font-semibold text-gh-fg flex items-center gap-1.5">
          <GitPullRequest className="w-4 h-4 text-gh-muted" strokeWidth={1.75} />
          Pull Request Risk Simulator
        </h2>
        <p className="text-xs text-gh-muted mt-1">
          Simulate a proposed file diff to evaluate downstream ripple radius and review scrutiny via Graph ML.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="md:col-span-2 space-y-1">
          <label className="text-xs font-medium text-gh-muted">File to modify</label>
          <input
            type="text"
            value={filePath}
            onChange={(e) => setFilePath(e.target.value)}
            className="w-full h-9 bg-white border border-gh-border rounded-md px-3 text-sm font-mono text-gh-fg focus:outline-none focus:border-gh-accent focus:ring-2 focus:ring-gh-accentSubtle"
            required
          />
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1">
            <label className="text-xs font-medium text-gh-muted">Added (+)</label>
            <input
              type="number"
              value={added}
              min="0"
              onChange={(e) => setAdded(parseInt(e.target.value) || 0)}
              className="w-full h-9 bg-white border border-gh-border rounded-md px-3 text-sm text-gh-fg focus:outline-none focus:border-gh-accent focus:ring-2 focus:ring-gh-accentSubtle"
              required
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-gh-muted">Deleted (-)</label>
            <input
              type="number"
              value={deleted}
              min="0"
              onChange={(e) => setDeleted(parseInt(e.target.value) || 0)}
              className="w-full h-9 bg-white border border-gh-border rounded-md px-3 text-sm text-gh-fg focus:outline-none focus:border-gh-accent focus:ring-2 focus:ring-gh-accentSubtle"
              required
            />
          </div>
        </div>

        <div className="md:col-span-3 space-y-2">
          <button
            type="submit"
            disabled={loading}
            className="bg-gh-accent hover:bg-[#0860C4] disabled:bg-gh-border disabled:text-gh-muted text-white font-medium h-9 px-4 rounded-md transition-colors text-sm"
          >
            {loading ? 'Evaluating…' : 'Evaluate Contribution Impact'}
          </button>
          {error && (
            <div className="flex items-start gap-2 bg-gh-dangerSubtle border border-gh-dangerBorder text-gh-danger text-xs rounded-md px-3 py-2">
              <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              <span className="break-words">{error}</span>
            </div>
          )}
        </div>
      </form>

      {result && (
        <div className="border-t border-gh-border pt-4 space-y-4">
          <h3 className="text-base font-semibold text-gh-fg">Contribution Impact</h3>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <MetricPanel label="Ripple Radius" value={`${result.likely_affected_files.length} files`} />
            <MetricPanel label="Review Risk" value={`${(result.impact_score * 100).toFixed(0)}%`} />
            <MetricPanel
              label="Risk Level"
              value={<Badge variant={riskVariant(result.risk_level)} className="text-xs">{result.risk_level}</Badge>}
            />
            <MetricPanel label="Confidence" value={`${(result.confidence * 100).toFixed(0)}%`} />
          </div>

          <p className="text-sm text-gh-fg leading-relaxed">{result.summary_verdict}</p>

          {result.review_difficulty && (
            <div className="flex items-center gap-2 text-xs">
              <span className="text-gh-muted">Review Difficulty:</span>
              <Badge variant={riskVariant(result.review_difficulty)}>{result.review_difficulty}</Badge>
            </div>
          )}

          {result.primary_risk_factors?.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wide text-gh-muted mb-2">Primary Risk Factors</h4>
              <ul className="space-y-1">
                {result.primary_risk_factors.map((f, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-sm text-gh-fg">
                    <FileWarning className="w-3.5 h-3.5 text-gh-warning shrink-0 mt-0.5" />
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-gh-muted mb-2">Affected Components</h4>
            {result.likely_affected_files.length === 0 ? (
              <p className="text-xs text-gh-muted">None (self-contained change)</p>
            ) : (
              <ul className="divide-y divide-gh-border border border-gh-border rounded-md overflow-hidden">
                {result.likely_affected_files.map((f, i) => (
                  <li key={i} className="flex items-center gap-1.5 text-xs font-mono text-gh-fg px-3 py-1.5 bg-gh-canvas">
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div>
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-gh-muted">
                Generated Pull Request Markdown Comment
              </h4>
              <button
                onClick={handleCopy}
                className="flex items-center gap-1.5 text-xs text-gh-fg bg-white border border-gh-border hover:bg-gh-canvas px-2.5 py-1 rounded-md transition-colors self-start"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-gh-success" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? 'Copied!' : 'Copy Markdown'}</span>
              </button>
            </div>
            <pre className="bg-gh-canvas border border-gh-border p-3 rounded-md text-xs text-gh-fg font-mono whitespace-pre-wrap overflow-x-auto">
              {result.markdown_pr_comment}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
};
