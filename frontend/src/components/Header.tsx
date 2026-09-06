import React, { useEffect, useState } from 'react';
import { Terminal } from 'lucide-react';
export const Header: React.FC = () => {
  const [isOnline, setIsOnline] = useState<boolean>(false);
  useEffect(() => {
    fetch('/health')
      .then((res) => res.json())
      .then((data) => setIsOnline(data.status === 'ok'))
      .catch(() => setIsOnline(false));
  }, []);
  return (
    <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-cyan-500 flex items-center justify-center font-black text-white shadow-lg shadow-indigo-500/30">
            R
          </div>
          <div>
            <h1 className="font-bold text-base tracking-tight bg-gradient-to-r from-indigo-400 via-cyan-400 to-emerald-400 bg-clip-text text-transparent">
              RepoInsight AI
            </h1>
            <p className="text-[10px] text-slate-400">Intelligent Repository Health & Graph ML</p>
          </div>
        </div>
        <div className="flex items-center space-x-4 text-xs">
          {isOnline ? (
            <span className="inline-flex items-center px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1.5 animate-pulse" />
              FastAPI Connected (Port 8000)
            </span>
          ) : (
            <span className="inline-flex items-center px-2.5 py-1 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20">
              <span className="w-1.5 h-1.5 rounded-full bg-rose-400 mr-1.5" />
              Backend Offline
            </span>
          )}
          <a
            href="http://127.0.0.1:8000/docs"
            target="_blank"
            rel="noreferrer"
            className="flex items-center space-x-1.5 text-slate-400 hover:text-slate-200 transition bg-slate-800 px-3 py-1.5 rounded-lg border border-slate-700"
          >
            <Terminal className="w-3.5 h-3.5" />
            <span>API Docs</span>
          </a>
        </div>
      </div>
    </header>
  );
};
