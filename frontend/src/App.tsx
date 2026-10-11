import React, { useState } from 'react';
import { Sidebar, View } from './components/Sidebar';
import { TopBar } from './components/TopBar';
import { EmptyState } from './components/EmptyState';
import { HealthOverview } from './components/HealthOverview';
import { DependencyGraphView } from './components/DependencyGraphView';
import { ContributorsView } from './components/ContributorsView';
import { PullRequestSimulator } from './components/PullRequestSimulator';
import { HealthReport, GraphData, GuidanceReport } from './types';
import { LayoutDashboard, Network, Users } from 'lucide-react';

export const App: React.FC = () => {
  const [view, setView] = useState<View>('overview');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [repoUrl, setRepoUrl] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [healthData, setHealthData] = useState<HealthReport | null>(null);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [guidanceData, setGuidanceData] = useState<GuidanceReport | null>(null);

  const handleAudit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const healthRes = await fetch('/api/v1/repository/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_url: repoUrl, max_commits: 200 }),
      });
      if (!healthRes.ok) throw new Error(await healthRes.text());
      setHealthData(await healthRes.json());

      const graphRes = await fetch('/api/v1/repository/graph', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_url: repoUrl }),
      });
      if (graphRes.ok) setGraphData(await graphRes.json());

      const guidanceRes = await fetch('/api/v1/repository/guidance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_url: repoUrl }),
      });
      if (guidanceRes.ok) setGuidanceData(await guidanceRes.json());

      setView('overview');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen bg-gh-canvas text-gh-fg font-sans overflow-hidden">
      <Sidebar view={view} onChangeView={setView} open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="flex-1 flex flex-col min-w-0">
        <TopBar
          repoUrl={repoUrl}
          onRepoUrlChange={setRepoUrl}
          onSubmit={handleAudit}
          loading={loading}
          error={error}
          onMenuClick={() => setSidebarOpen(true)}
        />

        <main className="flex-1 overflow-y-auto px-4 sm:px-6 py-5">
          {view === 'overview' &&
            (healthData ? (
              <HealthOverview report={healthData} graphData={graphData} guidanceData={guidanceData} />
            ) : (
              <EmptyState
                icon={LayoutDashboard}
                title="No audit run yet"
                description="Enter a local path or GitHub URL above and run an audit to see the repository health breakdown."
              />
            ))}

          {view === 'graph' &&
            (graphData ? (
              <DependencyGraphView graphData={graphData} repoUrl={repoUrl} />
            ) : (
              <EmptyState
                icon={Network}
                title="No dependency graph yet"
                description="Run an audit to generate the module dependency graph and topology metrics."
              />
            ))}

          {view === 'contributors' &&
            (guidanceData ? (
              <ContributorsView guidance={guidanceData} />
            ) : (
              <EmptyState
                icon={Users}
                title="No contributor data yet"
                description="Run an audit to see contributor ownership, onboarding guidance, and knowledge silos."
              />
            ))}

          {view === 'simulator' && <PullRequestSimulator repoUrl={repoUrl} />}
        </main>
      </div>
    </div>
  );
};

export default App;
