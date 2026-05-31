import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../api/client';
import SeverityBadge from '../components/SeverityBadge';
import AgentTimeline from '../components/AgentTimeline';
import CorrelationGraph from '../components/CorrelationGraph';
import AccuracyFeedback from '../components/AccuracyFeedback';
import { ArrowLeft, CheckCircle, Clock, AlertTriangle, ExternalLink } from 'lucide-react';
import { format } from 'date-fns';

export default function IncidentDetail() {
  const { id } = useParams();
  const [incident, setIncident] = useState(null);
  const [correlated, setCorrelated] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [incData, corrData] = await Promise.all([
          api.getIncident(id),
          api.getCorrelatedIncidents(id).catch(() => ({ correlated_incidents: [] }))
        ]);
        setIncident(incData);
        setCorrelated(corrData.correlated_incidents || []);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [id]);

  const handleResolve = async () => {
    try {
      const updated = await api.resolveIncident(id);
      setIncident(updated);
    } catch (err) {
      console.error(err);
    }
  };

  if (loading) return <div className="p-8 text-center text-slate-400">Loading incident details...</div>;
  if (!incident) return <div className="p-8 text-center text-red-400">Incident not found</div>;

  const isResolved = incident.status === 'resolved';

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-20">
      <Link to="/" className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors">
        <ArrowLeft className="h-4 w-4" /> Back to Dashboard
      </Link>

      {/* Header Card */}
      <div className="bg-devops-card rounded-xl border border-devops-border p-6 shadow-sm">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-devops-border pb-6 mb-6">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <SeverityBadge severity={incident.severity} />
              <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700 uppercase">
                {incident.status}
              </span>
              <span className="text-sm text-slate-400">{incident.created_at ? format(new Date(incident.created_at), 'PP p') : ''}</span>
            </div>
            <h1 className="text-2xl font-bold text-white">{incident.title}</h1>
          </div>
          
          <div className="flex items-center gap-3">
            {!isResolved && (
              <button 
                onClick={handleResolve}
                className="px-4 py-2 bg-green-500/10 hover:bg-green-500/20 text-green-400 border border-green-500/20 rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
              >
                <CheckCircle className="h-4 w-4" />
                Mark Resolved
              </button>
            )}
            <AccuracyFeedback incidentId={incident.id} initialRating={incident.fix_accuracy_rating} />
          </div>
        </div>

        {/* RCA Summary */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="md:col-span-2 space-y-4">
            <div>
              <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-2">AI Root Cause Analysis</h3>
              <p className="text-slate-200 leading-relaxed bg-slate-800/50 p-4 rounded-lg border border-devops-border">
                {incident.root_cause || 'Analysis pending...'}
              </p>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-2">Suggested Fix</h3>
              <div className="bg-slate-800/50 p-4 rounded-lg border border-devops-border">
                <p className="text-slate-200 font-medium mb-3">{incident.fix_summary}</p>
                <ul className="list-decimal pl-5 space-y-2 text-slate-300 text-sm">
                  {(incident.fix_steps || []).map((step, idx) => (
                    <li key={idx}>{step}</li>
                  ))}
                </ul>
                {incident.fix_code_snippet && (
                  <div className="mt-4">
                    <p className="text-xs text-slate-400 mb-1">Code Fix:</p>
                    <pre className="bg-slate-900 p-3 rounded border border-slate-700 text-xs text-green-400 overflow-x-auto">
                      <code>{incident.fix_code_snippet}</code>
                    </pre>
                  </div>
                )}
              </div>
            </div>
          </div>
          
          <div className="space-y-6">
            <div>
              <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-2">Context</h3>
              <ul className="space-y-3 bg-slate-800/50 p-4 rounded-lg border border-devops-border text-sm">
                <li className="flex justify-between"><span className="text-slate-400">Service:</span> <span className="text-slate-200 font-medium">{incident.affected_service}</span></li>
                <li className="flex justify-between"><span className="text-slate-400">Blast Radius:</span> <span className="text-orange-400 font-medium capitalize">{incident.blast_radius}</span></li>
                <li className="flex justify-between"><span className="text-slate-400">Complexity:</span> <span className="text-slate-200 capitalize">{incident.fix_complexity}</span></li>
                <li className="flex justify-between"><span className="text-slate-400">Est. Time:</span> <span className="text-slate-200">{incident.estimated_time}</span></li>
              </ul>
            </div>
            
            <div>
              <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-2">Automated Actions</h3>
              <div className="space-y-2 bg-slate-800/50 p-4 rounded-lg border border-devops-border text-sm">
                {incident.github_issue_url ? (
                  <a href={incident.github_issue_url} target="_blank" rel="noreferrer" className="flex items-center gap-2 text-blue-400 hover:underline">
                    <ExternalLink className="h-4 w-4" /> GitHub Issue Created
                  </a>
                ) : (
                  <span className="text-slate-500">No GitHub Issue</span>
                )}
                {incident.github_pr_url ? (
                   <a href={incident.github_pr_url} target="_blank" rel="noreferrer" className="flex items-center gap-2 text-blue-400 hover:underline">
                   <ExternalLink className="h-4 w-4" /> Fix PR Created
                 </a>
                ) : (
                  <span className="block text-slate-500 mt-1">No Fix PR (Requires trivial complexity)</span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <AgentTimeline incident={incident} />
        </div>
        <div>
           <h2 className="text-lg font-semibold mb-6 mt-8 flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-orange-400" />
            Correlated Incidents
          </h2>
          <CorrelationGraph mainIncident={incident} correlatedIncidents={correlated} />
        </div>
      </div>

    </div>
  );
}
