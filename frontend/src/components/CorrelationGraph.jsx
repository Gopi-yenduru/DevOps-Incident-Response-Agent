import { Link } from 'react-router-dom';

// A simple visual representation of correlated incidents
export default function CorrelationGraph({ mainIncident, correlatedIncidents = [] }) {
  if (!correlatedIncidents || correlatedIncidents.length === 0) {
    return (
      <div className="text-sm text-slate-400 p-4 bg-slate-800/30 rounded border border-devops-border text-center">
        No correlated incidents found. This appears to be an isolated issue.
      </div>
    );
  }

  return (
    <div className="bg-slate-800/30 border border-devops-border rounded p-4">
      <div className="mb-4">
        <p className="text-sm text-slate-300">
          <span className="font-semibold text-slate-200">AI Reasoning:</span> {mainIncident.correlation_reason}
        </p>
      </div>
      
      <div className="space-y-2">
        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Related Incidents</h4>
        {correlatedIncidents.map(inc => (
          <Link 
            key={inc.id}
            to={`/incidents/${inc.id}`}
            className="block p-3 bg-devops-card hover:bg-slate-700 border border-devops-border rounded transition-colors group"
          >
            <div className="flex justify-between items-start">
              <div>
                <p className="text-sm font-medium text-slate-200 group-hover:text-blue-400 transition-colors">
                  {inc.title || `${inc.error_type} in ${inc.affected_service}`}
                </p>
                <p className="text-xs text-slate-400 mt-1">
                  Status: <span className="text-slate-300">{inc.status}</span>
                </p>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
