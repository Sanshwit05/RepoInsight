import React from 'react';
import { Search, Loader2, AlertCircle, Menu } from 'lucide-react';

interface Props {
  repoUrl: string;
  onRepoUrlChange: (v: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  loading: boolean;
  error: string | null;
  onMenuClick: () => void;
}

export const TopBar: React.FC<Props> = ({ repoUrl, onRepoUrlChange, onSubmit, loading, error, onMenuClick }) => {
  return (
    <div className="border-b border-gh-border bg-white">
      <form onSubmit={onSubmit} className="h-14 flex items-center gap-3 px-4 sm:px-6">
        <button
          type="button"
          onClick={onMenuClick}
          className="md:hidden p-1.5 -ml-1 rounded-md text-gh-muted hover:bg-gh-canvas shrink-0"
          aria-label="Toggle navigation"
        >
          <Menu className="w-5 h-5" />
        </button>

        <span className="hidden sm:inline text-sm font-medium text-gh-fg shrink-0">RepoInsight</span>

        <div className="relative flex-1 min-w-0 max-w-xl">
          <Search className="w-4 h-4 text-gh-muted absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={repoUrl}
            onChange={(e) => onRepoUrlChange(e.target.value)}
            placeholder="Search repositories..."
            className="w-full h-9 bg-white border border-gh-border rounded-md pl-9 pr-3 text-sm text-gh-fg placeholder:text-gh-muted focus:outline-none focus:border-gh-accent focus:ring-2 focus:ring-gh-accentSubtle"
            required
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className="flex items-center gap-2 bg-gh-accent hover:bg-[#0860C4] disabled:bg-gh-border disabled:text-gh-muted text-white text-sm font-medium px-3.5 h-9 rounded-md transition-colors shrink-0"
        >
          {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
          <span>{loading ? 'Analyzing…' : 'Run Audit'}</span>
        </button>
      </form>

      {error && (
        <div className="mx-4 sm:mx-6 mb-3 flex items-start gap-2 bg-gh-dangerSubtle border border-gh-dangerBorder text-gh-danger text-xs rounded-md px-3 py-2">
          <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
          <span className="break-words">{error}</span>
        </div>
      )}
    </div>
  );
};
