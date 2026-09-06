import React, { useState } from 'react';
import { PredictionResult } from '../types';
import { GitPullRequest, Copy, Check, AlertCircle } from 'lucide-react';

interface Props {
  repoUrl: string;
}

export const PullRequestSimulator: React.FC<Props> = ({ repoUrl }) => {
  const [filePath, setFilePath] = useState('src/repoinsight/analysis/models.py');
  const [added, setAdded] = useState(65);
  const [deleted, setDeleted] = useState(15);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [copied, setCopied] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

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
      alert('Prediction Error: ' + err.message);
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
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6">
      <div className="border-b border-slate-800 pb-4 flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-slate-100 flex items-center space-x-2">
            <GitPullRequest className="w-5 h-5 text-cyan-400" />
            <span>Contribution Impact & Pull Request Risk Simulator</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Simulate a proposed file diff to evaluate downstream ripple radius and review scrutiny via Graph ML.
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="md:col-span-2 space-y-1">
          <label className="text-xs font-semibold text-slate-300">File Path to Modify</label>
          <input
            type="text"
            value={filePath}
            onChange={(e) => setFilePath(e.target.value)}
            className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-slate-200 focus:ring-2 focus:ring-cyan-500 focus:outline-none"
            required
          />
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-300">Added (+)</label>
            <input
              type="number"
              value={added}
              min="0"
              onChange={(e) => setAdded(parseInt(e.target.value) || 0)}
              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2.5 text-sm text-slate-200 focus:outline-none"
              required
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-300">Deleted (-)</label>
            <input
              type="number"
              value={deleted}
              min="0"
              onChange={(e) => setDeleted(parseInt(e.target.value) || 0)}
              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2.5 text-sm text-slate-200 focus:outline-none"
              required
            />
          </div>
        </div>

        <div className="md:col-span-3">
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-800 text-white font-semibold py-3 rounded-xl transition shadow-lg shadow-cyan-600/20 text-sm"
          >
            {loading ? 'Evaluating Impact via GNN & ML...' : 'Evaluate Contribution Impact'}
          </button>
        </div>
      </form>

      {result && (
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-5 space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
            <div className="flex items-center space-x-3">
              <span
                className={`px-3 py-1 rounded-full text-xs font-black uppercase tracking-wider border ${
                  result.risk_level === 'HIGH'
                    ? 'bg-rose-500/20 text-rose-400 border-rose-500/30'
                    : result.risk_level === 'MEDIUM'
                    ? 'bg-amber-500/20 text-amber-400 border-amber-500/30'
                    : 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                }`}
              >
                {result.risk_level} RISK
              </span>
              <span className="text-sm font-semibold text-slate-200">
                Impact Score: {result.impact_score.toFixed(2)} / 1.00
              </span>
            </div>
            <span className="text-xs text-slate-400">Confidence: {(result.confidence * 100).toFixed(1)}%</span>
          </div>

          <p className="text-xs text-slate-300 leading-relaxed">{result.summary_verdict}</p>

          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
              Simulated Downstream Blast Radius:
            </h4>
            {result.likely_affected_files.length === 0 ? (
              <p className="text-xs text-slate-500">None (Self-contained change)</p>
            ) : (
              <ul className="space-y-1 font-mono text-xs text-amber-300">
                {result.likely_affected_files.map((f, i) => (
                  <li key={i} className="flex items-center space-x-1.5">
                    <AlertCircle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Generated Pull Request Markdown Comment:
              </h4>
              <button
                onClick={handleCopy}
                className="flex items-center space-x-1 text-xs text-cyan-400 hover:text-cyan-300 transition"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? 'Copied!' : 'Copy Markdown'}</span>
              </button>
            </div>
            <pre className="bg-slate-900 border border-slate-800 p-3 rounded-lg text-xs text-slate-300 font-mono whitespace-pre-wrap overflow-x-auto">
              {result.markdown_pr_comment}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
};
