import React, { useState } from 'react';
import { Header } from './components/Header';
import { HealthOverview } from './components/HealthOverview';
import { DependencyGraphView } from './components/DependencyGraphView';
import { ContributorGuidanceView } from './components/ContributorGuidanceView';
import { PullRequestSimulator } from './components/PullRequestSimulator';
import { HealthReport, GraphData, GuidanceReport } from './types';
import { Search, Loader2 } from 'lucide-react';

export const App: React.FC = () => {
  const [repoUrl, setRepoUrl] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [healthData, setHealthData] = useState<HealthReport | null>(null);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [guidanceData, setGuidanceData] = useState<GuidanceReport | null>(null);

  const handleAudit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const healthRes = await fetch('/api/v1/repository/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_url: repoUrl, max_commits: 200 }),
      });
      if (!healthRes.ok) throw new Error(await healthRes.text());
      const hData: HealthReport = await healthRes.json();
      setHealthData(hData);

      const graphRes = await fetch('/api/v1/repository/graph', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_url: repoUrl }),
      });
      if (graphRes.ok) {
        const gData: GraphData = await graphRes.json();
        setGraphData(gData);
      }

      const guidanceRes = await fetch('/api/v1/repository/guidance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_url: repoUrl }),
      });
      if (guidanceRes.ok) {
        const guiData: GuidanceReport = await guidanceRes.json();
        setGuidanceData(guiData);
      }
    } catch (err: any) {
      alert('Audit Error: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <Header />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        <section className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
          <form onSubmit={handleAudit} className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="w-5 h-5 text-slate-500 absolute left-4 top-3.5" />
              <input
                type="text"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                placeholder="Enter local path (.) or GitHub URL (https://github.com/owner/repo)"
                className="w-full bg-slate-950 border border-slate-700 rounded-xl pl-12 pr-4 py-3 text-sm focus:ring-2 focus:ring-indigo-500 text-slate-200 focus:outline-none"
                required
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 text-white font-semibold px-6 py-3 rounded-xl transition shadow-lg shadow-indigo-600/20 flex items-center justify-center space-x-2 shrink-0 text-sm"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
              <span>{loading ? 'Analyzing Codebase...' : 'Run Repository Audit'}</span>
            </button>
          </form>
        </section>

        {healthData && <HealthOverview report={healthData} />}
        {graphData && <DependencyGraphView graphData={graphData} />}
        {guidanceData && <ContributorGuidanceView guidance={guidanceData} />}

        <PullRequestSimulator repoUrl={repoUrl} />
      </main>
    </div>
  );
};

export default App;
