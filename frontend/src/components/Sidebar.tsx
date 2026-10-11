import React, { useEffect, useState } from 'react';
import { LayoutDashboard, Network, Users, GitPullRequest, ExternalLink, Settings } from 'lucide-react';

export type View = 'overview' | 'graph' | 'contributors' | 'simulator';

interface NavItem {
  id: View;
  label: string;
  icon: React.ElementType;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'graph', label: 'Dependency Graph', icon: Network },
  { id: 'contributors', label: 'Contributors', icon: Users },
  { id: 'simulator', label: 'PR Simulator', icon: GitPullRequest },
];

interface Props {
  view: View;
  onChangeView: (v: View) => void;
  open: boolean;
  onClose: () => void;
}

export const Sidebar: React.FC<Props> = ({ view, onChangeView, open, onClose }) => {
  const [isOnline, setIsOnline] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const check = () => {
      fetch('/health')
        .then((res) => res.json())
        .then((data) => !cancelled && setIsOnline(data.status === 'ok'))
        .catch(() => !cancelled && setIsOnline(false));
    };
    check();
    const interval = setInterval(check, 15000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <>
      {open && (
        <div className="fixed inset-0 bg-black/30 z-30 md:hidden" onClick={onClose} aria-hidden="true" />
      )}
      <aside
        className={`w-60 shrink-0 border-r border-gh-border bg-white flex flex-col fixed md:static inset-y-0 left-0 z-40 transform transition-transform duration-150 ${
          open ? 'translate-x-0' : '-translate-x-full'
        } md:translate-x-0`}
      >
        <div className="h-14 flex items-center gap-2.5 px-4 border-b border-gh-border">
          <div className="w-6 h-6 rounded-md bg-gh-accent flex items-center justify-center text-xs font-bold text-white shrink-0">
            R
          </div>
          <div className="min-w-0">
            <div className="text-sm font-semibold text-gh-fg leading-tight truncate">RepoInsight</div>
            <div className="text-xs text-gh-muted leading-tight truncate">Repository Intelligence</div>
          </div>
        </div>

        <nav className="flex-1 px-2 py-3 space-y-0.5">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = view === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  onChangeView(item.id);
                  onClose();
                }}
                className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-md text-sm transition-colors ${
                  active ? 'bg-gh-selected text-gh-fg font-medium' : 'text-gh-muted hover:bg-gh-canvas hover:text-gh-fg'
                }`}
              >
                <Icon className="w-4 h-4 shrink-0" strokeWidth={1.75} />
                <span className="truncate">{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="p-3 border-t border-gh-border space-y-2.5">
          <button
            type="button"
            title="Settings are not yet available"
            className="w-full flex items-center justify-between gap-2.5 px-2.5 py-1.5 rounded-md text-sm text-gh-muted opacity-70 cursor-not-allowed"
          >
            <span className="flex items-center gap-2.5">
              <Settings className="w-4 h-4 shrink-0" strokeWidth={1.75} />
              <span>Settings</span>
            </span>
            <span className="text-xs px-1.5 py-0.5 rounded border border-gh-border text-gh-muted">Soon</span>
          </button>

          <div className="flex items-center gap-1.5 px-1 text-xs">
            <span className={`w-1.5 h-1.5 rounded-full ${isOnline ? 'bg-gh-success' : 'bg-gh-danger'}`} />
            <span className="text-gh-muted">{isOnline ? 'Backend connected' : 'Backend offline'}</span>
          </div>
          <a
            href="http://127.0.0.1:8000/docs"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 px-1 text-xs text-gh-muted hover:text-gh-accent transition-colors"
          >
            <ExternalLink className="w-3 h-3" />
            <span>API Docs</span>
          </a>
        </div>
      </aside>
    </>
  );
};
