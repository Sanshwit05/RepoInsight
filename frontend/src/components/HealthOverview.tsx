import React from 'react';
import { HealthReport } from '../types';
import { Award, Users, AlertTriangle, Code2, CheckCircle2 } from 'lucide-react';

interface Props {
  report: HealthReport;
}

export const HealthOverview: React.FC<Props> = ({ report }) => {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl relative overflow-hidden">
          <div className="flex items-center justify-between text-xs text-slate-400 font-medium">
            <span>Overall Health</span>
            <Award className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="mt-3 flex items-baseline justify-between">
            <span className="text-3xl font-black text-indigo-400">{report.overall_score}</span>
            <span className="text-xs font-bold px-2.5 py-1 rounded-lg bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
              Grade {report.grade}
            </span>
          </div>
          <div className="w-full bg-slate-800 h-1.5 rounded-full mt-4 overflow-hidden">
            <div className="bg-gradient-to-r from-indigo-500 to-cyan-400 h-full rounded-full" style={{ width: `${report.overall_score}%` }} />
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl">
          <div className="flex items-center justify-between text-xs text-slate-400 font-medium">
            <span>Empirical Bus Factor</span>
            <Users className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="mt-3 flex items-baseline justify-between">
            <span className="text-3xl font-black text-emerald-400">{report.bus_factor}</span>
            <span className="text-xs text-slate-400">Maintainers</span>
          </div>
          <p className="text-[11px] text-slate-400 mt-4 truncate">
            {report.bus_factor <= 1 ? '⚠️ Critical single point of failure' : '✅ Healthy knowledge distribution'}
          </p>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl">
          <div className="flex items-center justify-between text-xs text-slate-400 font-medium">
            <span>Critical Hotspots</span>
            <AlertTriangle className="w-4 h-4 text-rose-400" />
          </div>
          <div className="mt-3 flex items-baseline justify-between">
            <span className="text-3xl font-black text-rose-400">{report.critical_hotspots_count}</span>
            <span className="text-xs text-slate-400">Technical Debt</span>
          </div>
          <p className="text-[11px] text-slate-400 mt-4 truncate">High complexity & churn files</p>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl">
          <div className="flex items-center justify-between text-xs text-slate-400 font-medium">
            <span>Codebase Scale</span>
            <Code2 className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="mt-3 flex items-baseline justify-between">
            <span className="text-3xl font-black text-cyan-400">{report.total_sloc.toLocaleString()}</span>
            <span className="text-xs text-slate-400">SLOC</span>
          </div>
          <p className="text-[11px] text-slate-400 mt-4 truncate">
            {report.total_files} files | {report.total_commits} commits
          </p>
        </div>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">Health Pillars Breakdown (0 - 100)</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-slate-950 p-4 rounded-xl border border-slate-800/80">
            <span className="text-xs text-slate-400">Complexity & AST</span>
            <p className="text-xl font-bold text-slate-200 mt-1">{report.sub_scores.complexity_score} / 100</p>
          </div>
          <div className="bg-slate-950 p-4 rounded-xl border border-slate-800/80">
            <span className="text-xs text-slate-400">Hotspots & Debt</span>
            <p className="text-xl font-bold text-slate-200 mt-1">{report.sub_scores.hotspot_score} / 100</p>
          </div>
          <div className="bg-slate-950 p-4 rounded-xl border border-slate-800/80">
            <span className="text-xs text-slate-400">Architecture DAG</span>
            <p className="text-xl font-bold text-slate-200 mt-1">{report.sub_scores.architecture_score} / 100</p>
          </div>
          <div className="bg-slate-950 p-4 rounded-xl border border-slate-800/80">
            <span className="text-xs text-slate-400">Ownership & Silos</span>
            <p className="text-xl font-bold text-slate-200 mt-1">{report.sub_scores.ownership_score} / 100</p>
          </div>
        </div>

        <div className="pt-2">
          <h4 className="text-xs font-semibold text-slate-400 mb-2">Key Executive Findings:</h4>
          <div className="space-y-1.5">
            {report.key_findings.map((f, i) => (
              <div key={i} className="flex items-start space-x-2 text-xs text-slate-300">
                <CheckCircle2 className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
                <span>{f}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
