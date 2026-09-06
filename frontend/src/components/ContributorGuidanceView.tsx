import React, { useState } from 'react';
import { GuidanceReport } from '../types';
import { Compass, Sparkles, Flame, Lock } from 'lucide-react';

interface Props {
  guidance: GuidanceReport;
}

export const ContributorGuidanceView: React.FC<Props> = ({ guidance }) => {
  const [tab, setTab] = useState<'beginner' | 'high_risk' | 'silos'>('beginner');

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Compass className="w-5 h-5 text-emerald-400" />
          <h2 className="text-base font-bold text-slate-100">Deterministic Contributor Guidance</h2>
        </div>
        <p className="text-xs text-slate-400 hidden sm:block">{guidance.onboarding_summary}</p>
      </div>

      <div className="flex space-x-2 border-b border-slate-800 pb-2 text-xs">
        <button
          onClick={() => setTab('beginner')}
          className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg font-medium transition ${
            tab === 'beginner' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>Beginner Friendly ({guidance.beginner_friendly_files.length})</span>
        </button>

        <button
          onClick={() => setTab('high_risk')}
          className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg font-medium transition ${
            tab === 'high_risk' ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Flame className="w-3.5 h-3.5" />
          <span>High-Risk Core ({guidance.high_risk_core_files.length})</span>
        </button>

        <button
          onClick={() => setTab('silos')}
          className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg font-medium transition ${
            tab === 'silos' ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Lock className="w-3.5 h-3.5" />
          <span>Knowledge Silos ({guidance.siloed_files.length})</span>
        </button>
      </div>

      <div className="space-y-2 pt-2">
        {tab === 'beginner' &&
          guidance.beginner_friendly_files.map((g, i) => (
            <div key={i} className="bg-slate-950 p-3 rounded-xl border border-slate-800 flex items-center justify-between text-xs">
              <div>
                <p className="font-mono text-emerald-300 font-semibold">{g.file_path}</p>
                <p className="text-slate-400 text-[11px] mt-0.5">{g.advice}</p>
              </div>
              <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shrink-0 font-semibold">
                {g.review_difficulty}
              </span>
            </div>
          ))}

        {tab === 'high_risk' &&
          guidance.high_risk_core_files.map((g, i) => (
            <div key={i} className="bg-slate-950 p-3 rounded-xl border border-slate-800 flex items-center justify-between text-xs">
              <div>
                <p className="font-mono text-rose-300 font-semibold">{g.file_path}</p>
                <p className="text-slate-400 text-[11px] mt-0.5">{g.advice}</p>
              </div>
              <span className="px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20 shrink-0 font-semibold">
                {g.review_difficulty}
              </span>
            </div>
          ))}

        {tab === 'silos' &&
          guidance.siloed_files.map((g, i) => (
            <div key={i} className="bg-slate-950 p-3 rounded-xl border border-slate-800 flex items-center justify-between text-xs">
              <div>
                <p className="font-mono text-amber-300 font-semibold">{g.file_path}</p>
                <p className="text-slate-400 text-[11px] mt-0.5">{g.advice}</p>
              </div>
              <span className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 shrink-0 font-semibold">
                Owner: {g.primary_owner}
              </span>
            </div>
          ))}
      </div>
    </div>
  );
};
