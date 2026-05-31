import { useEffect, useState } from 'react';
import { api } from '../api/client';
import SeverityBadge from './SeverityBadge';
import { formatDistanceToNow } from 'date-fns';
import { Link } from 'react-router-dom';

export default function LiveLogFeed() {
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchIncidents = async () => {
    try {
      const data = await api.getIncidents(1, 'open');
      setIncidents(data.incidents || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIncidents();
    const interval = setInterval(fetchIncidents, 15000); // Auto-refresh every 15s
    return () => clearInterval(interval);
  }, []);

  if (loading && incidents.length === 0) {
    return <div className="p-8 text-center text-slate-400 animate-pulse">Loading live incident feed...</div>;
  }

  if (incidents.length === 0) {
    return <div className="p-8 text-center text-slate-400">No open incidents. System is healthy.</div>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm text-left">
        <thead className="text-xs text-slate-400 uppercase bg-slate-800/50 border-b border-devops-border">
          <tr>
            <th className="px-4 py-3 font-medium">Severity</th>
            <th className="px-4 py-3 font-medium">Service</th>
            <th className="px-4 py-3 font-medium">Error Type</th>
            <th className="px-4 py-3 font-medium">Time</th>
            <th className="px-4 py-3 font-medium">Agent Confidence</th>
            <th className="px-4 py-3 font-medium">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-devops-border">
          {incidents.map((incident) => (
            <tr key={incident.id} className="hover:bg-slate-800/30 transition-colors">
              <td className="px-4 py-3">
                <SeverityBadge severity={incident.severity} />
              </td>
              <td className="px-4 py-3 text-slate-200 font-medium">
                {incident.affected_service || 'unknown'}
              </td>
              <td className="px-4 py-3 text-slate-300">
                {incident.error_type}
                {incident.is_correlated && (
                  <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20">
                    Correlated
                  </span>
                )}
              </td>
              <td className="px-4 py-3 text-slate-400 whitespace-nowrap">
                {incident.created_at ? formatDistanceToNow(new Date(incident.created_at), { addSuffix: true }) : 'N/A'}
              </td>
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  <div className="w-16 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-purple-500 rounded-full"
                      style={{ width: `${(incident.anomaly_confidence || 0) * 100}%` }}
                    />
                  </div>
                  <span className="text-xs text-slate-400">{Math.round((incident.anomaly_confidence || 0) * 100)}%</span>
                </div>
              </td>
              <td className="px-4 py-3">
                <Link 
                  to={`/incidents/${incident.id}`}
                  className="text-blue-400 hover:text-blue-300 text-sm font-medium"
                >
                  View Details &rarr;
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
