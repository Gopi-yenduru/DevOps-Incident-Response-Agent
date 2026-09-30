import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { 
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, PieChart, Pie, Cell, Legend
} from 'recharts';

const COLORS = ['#ef4444', '#f97316', '#eab308', '#22c55e', '#3b82f6'];

export default function Analytics() {
  const [mttrTrend, setMttrTrend] = useState([]);
  const [severityData, setSeverityData] = useState([]);
  const [errorRanking, setErrorRanking] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.getMttrTrend(),
      api.getSeverityBreakdown(),
      api.getAnalyticsOverview() // using for top errors if implemented, else mock or skip
    ]).then(([mttr, sev]) => {
      setMttrTrend(mttr?.trend || []);
      setSeverityData(sev?.breakdown || []);
    }).catch(console.error)
      .finally(() => setLoading(false));

    api.getErrorRanking()
      .then(res => setErrorRanking(res.error_types || []))
      .catch(console.error);
  }, []);

  if (loading) return <div className="p-8 text-center text-slate-400">Loading analytics...</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white mb-6">Analytics & Trends</h1>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* MTTR Trend */}
        <div className="bg-devops-card rounded-xl border border-devops-border p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-white mb-4">Mean Time To Resolution (MTTR) Trend</h2>
          <div className="h-72 w-full">
            {mttrTrend.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={mttrTrend} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorMttr" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="date" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', color: '#f8fafc' }}
                    itemStyle={{ color: '#3b82f6' }}
                  />
                  <Area type="monotone" dataKey="avg_mttr_seconds" name="Avg MTTR (s)" stroke="#3b82f6" fillOpacity={1} fill="url(#colorMttr)" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
               <div className="h-full flex items-center justify-center text-slate-500">Not enough data for MTTR trend</div>
            )}
          </div>
        </div>

        {/* Severity Breakdown */}
        <div className="bg-devops-card rounded-xl border border-devops-border p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-white mb-4">Incidents by Severity</h2>
          <div className="h-72 w-full">
             {severityData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={severityData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={100}
                      paddingAngle={5}
                      dataKey="count"
                      nameKey="severity"
                    >
                      {severityData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', color: '#f8fafc' }} />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
             ) : (
                <div className="h-full flex items-center justify-center text-slate-500">No severity data available</div>
             )}
          </div>
        </div>

        {/* Top Error Types */}
        <div className="bg-devops-card rounded-xl border border-devops-border p-6 shadow-sm lg:col-span-2">
           <h2 className="text-lg font-semibold text-white mb-4">Top 10 Most Frequent Error Types</h2>
           <div className="h-80 w-full">
              {errorRanking.length > 0 ? (
                 <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={errorRanking} layout="vertical" margin={{ top: 5, right: 30, left: 150, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" horizontal={false} />
                      <XAxis type="number" stroke="#94a3b8" fontSize={12} />
                      <YAxis dataKey="error_type" type="category" stroke="#94a3b8" fontSize={11} tick={{fill: '#cbd5e1'}} width={140} />
                      <Tooltip contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', color: '#f8fafc' }} cursor={{fill: '#334155'}} />
                      <Bar dataKey="count" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
                    </BarChart>
                 </ResponsiveContainer>
              ) : (
                 <div className="h-full flex items-center justify-center text-slate-500">No error types recorded yet</div>
              )}
           </div>
        </div>

      </div>
    </div>
  );
}
