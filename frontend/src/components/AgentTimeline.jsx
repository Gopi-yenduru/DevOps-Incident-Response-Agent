import { useState } from 'react';
import { CheckCircle2, AlertTriangle, Code, Send, BrainCircuit, ChevronDown, ChevronUp } from 'lucide-react';
import clsx from 'clsx';

function StepCard({ title, icon: Icon, confidence, isExpanded, onToggle, children, completed = true }) {
  return (
    <div className="relative pl-12 pb-8 last:pb-0">
      {/* Timeline vertical line */}
      <div className="absolute left-4 top-10 bottom-0 w-0.5 bg-devops-border -ml-[1px] last:hidden" />
      
      {/* Timeline icon */}
      <div className={clsx(
        "absolute left-0 top-2 h-8 w-8 rounded-full border-2 flex items-center justify-center bg-devops-card z-10",
        completed ? "border-blue-500 text-blue-400" : "border-devops-border text-slate-500"
      )}>
        <Icon className="h-4 w-4" />
      </div>

      <div className="bg-slate-800/50 rounded-lg border border-devops-border overflow-hidden">
        <button 
          onClick={onToggle}
          className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-800 transition-colors"
        >
          <div className="flex items-center gap-3">
            <h3 className="font-medium text-slate-200">{title}</h3>
            {confidence !== undefined && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-slate-700 text-slate-300">
                Confidence: {Math.round(confidence * 100)}%
              </span>
            )}
          </div>
          {isExpanded ? <ChevronUp className="h-4 w-4 text-slate-400" /> : <ChevronDown className="h-4 w-4 text-slate-400" />}
        </button>
        
        {isExpanded && (
          <div className="p-4 border-t border-devops-border bg-devops-card/50 text-sm overflow-x-auto">
            {children}
          </div>
        )}
      </div>
    </div>
  );
}

export default function AgentTimeline({ incident }) {
  const [expandedStep, setExpandedStep] = useState(0); // auto-expand first step
  
  if (!incident || !incident.agent_outputs) return null;

  const toggle = (idx) => setExpandedStep(prev => prev === idx ? -1 : idx);
  
  const anomaly = incident.agent_outputs.anomaly_detector || {};
  const correlation = incident.agent_outputs.incident_correlator || {};
  const rca = incident.agent_outputs.root_cause_analyzer || {};
  const fix = incident.agent_outputs.fix_suggestion || {};
  const response = incident.agent_outputs.response_orchestrator || {};

  return (
    <div className="mt-8">
      <h2 className="text-lg font-semibold mb-6 flex items-center gap-2">
        <BrainCircuit className="h-5 w-5 text-purple-400" />
        Agent Reasoning Timeline
      </h2>
      
      <div className="relative">
        <StepCard
          title="1. Anomaly Detection"
          icon={AlertTriangle}
          confidence={anomaly.confidence}
          isExpanded={expandedStep === 0}
          onToggle={() => toggle(0)}
        >
          <pre className="text-xs text-slate-300 whitespace-pre-wrap font-mono">
            {JSON.stringify(anomaly, null, 2)}
          </pre>
        </StepCard>

        <StepCard
          title="2. Incident Correlation"
          icon={CheckCircle2}
          confidence={correlation.confidence}
          isExpanded={expandedStep === 1}
          onToggle={() => toggle(1)}
        >
          <p className="mb-2 text-slate-300"><span className="font-semibold text-slate-200">Is Correlated:</span> {correlation.is_correlated ? 'Yes' : 'No'}</p>
          <p className="mb-4 text-slate-300"><span className="font-semibold text-slate-200">Reason:</span> {correlation.correlation_reason}</p>
          <pre className="text-xs text-slate-300 whitespace-pre-wrap font-mono">
            {JSON.stringify(correlation, null, 2)}
          </pre>
        </StepCard>

        <StepCard
          title="3. Root Cause Analysis"
          icon={BrainCircuit}
          confidence={rca.confidence}
          isExpanded={expandedStep === 2}
          onToggle={() => toggle(2)}
        >
          <pre className="text-xs text-slate-300 whitespace-pre-wrap font-mono">
            {JSON.stringify(rca, null, 2)}
          </pre>
        </StepCard>

        <StepCard
          title="4. Fix Suggestion"
          icon={Code}
          confidence={fix.confidence}
          isExpanded={expandedStep === 3}
          onToggle={() => toggle(3)}
        >
          <pre className="text-xs text-slate-300 whitespace-pre-wrap font-mono">
            {JSON.stringify(fix, null, 2)}
          </pre>
        </StepCard>

        <StepCard
          title="5. Response Orchestrator"
          icon={Send}
          isExpanded={expandedStep === 4}
          onToggle={() => toggle(4)}
        >
          <div className="space-y-2">
            <p className="text-slate-300"><span className="font-semibold text-slate-200">Actions taken:</span> {response.actions_taken?.join(', ') || 'None'}</p>
            {response.github_issue_url && (
              <p><a href={response.github_issue_url} target="_blank" rel="noreferrer" className="text-blue-400 hover:underline">View GitHub Issue ↗</a></p>
            )}
            {response.github_pr_url && (
              <p><a href={response.github_pr_url} target="_blank" rel="noreferrer" className="text-blue-400 hover:underline">View Pull Request ↗</a></p>
            )}
            <pre className="text-xs text-slate-300 whitespace-pre-wrap font-mono mt-4">
              {JSON.stringify(response, null, 2)}
            </pre>
          </div>
        </StepCard>
      </div>
    </div>
  );
}
