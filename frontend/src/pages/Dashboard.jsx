import { useEffect, useState } from 'react';
import { Activity, Clock, ShieldAlert, Target } from 'lucide-react';
import { api } from '../api/client';
import LiveLogFeed from '../components/LiveLogFeed';
import { Link } from 'react-router-dom';

function StatCard({ title, value, subtitle, icon: Icon, color = 'blue' }) {
  const colors = {
    blue: 'text-blue-400 bg-blue-400/10',
    red: 'text-red-400 bg-red-400/10',
    green: 'text-green-400 bg-green-400/10',
    purple: 'text-purple-400 bg-purple-400/10',
  };

  return (
    <div className="bg-devops-card rounded-xl border border-devops-border p-6 shadow-sm">
      <div className="flex justify-between items-start">
        <div>
          <p className="text-sm font-medium text-slate-400">{title}</p>
          <p className="text-3xl font-bold text-white mt-2">{value !== null ? value : '-'}</p>
        </div>
        <div className={`p-3 rounded-lg ${colors[color]}`}>
          <Icon className="w-6 h-6" />
        </div>
      </div>
      {subtitle && <p className="text-sm text-slate-500 mt-4">{subtitle}</p>}
    </div>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    api.getAnalyticsOverview().then(setStats).catch(console.error);
  }, []);

  const formatMTTR = (seconds) => {
    if (!seconds) return 'N/A';
    if (seconds < 60) return `${seconds}s`;
    const m = Math.floor(seconds / 60);
    return `${m}m`;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">System Overview</h1>
        <div className="flex gap-2">
          <Link to="/analytics" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white text-sm font-medium rounded-lg border border-devops-border transition-colors">
            View Analytics
          </Link>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard 
          title="Open Incidents" 
          value={stats?.open_incidents} 
          subtitle="Currently active and unresolved"
          icon={ShieldAlert}
          color="red"
        />
        <StatCard 
          title="Avg MTTR" 
          value={formatMTTR(stats?.avg_mttr_seconds)} 
          subtitle="Mean time to resolution"
          icon={Clock}
          color="blue"
        />
        <StatCard 
          title="Agent Accuracy" 
          value={stats?.agent_accuracy_percent ? `${stats.agent_accuracy_percent}%` : 'N/A'} 
          subtitle="Based on human feedback"
          icon={Target}
          color="purple"
        />
        <StatCard 
          title="Resolved Today" 
          value={stats?.resolved_today} 
          subtitle="Incidents fixed in last 24h"
          icon={Activity}
          color="green"
        />
      </div>

      {/* Live Feed */}
      <div className="bg-devops-card rounded-xl border border-devops-border shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-devops-border flex justify-between items-center bg-slate-800/50">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></span>
            Live Incident Feed
          </h2>
          <span className="text-xs text-slate-400">Auto-updating...</span>
        </div>
        <LiveLogFeed />
      </div>
    </div>
  );
}
