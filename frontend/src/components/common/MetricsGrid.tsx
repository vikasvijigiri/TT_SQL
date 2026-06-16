import React from 'react';

export interface MetricData {
  label: string;
  value: string | number;
  color: string;
  type: string;
  sub: string;
}

interface MetricsGridProps {
  metrics: MetricData[];
  onMetricClick: (type: string) => void;
}

export const MetricsGrid: React.FC<MetricsGridProps> = ({ metrics, onMetricClick }) => {
  if (!metrics || metrics.length === 0) return null;

  return (
    <section className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3.5">
      {metrics.map(m => (
        <div
          key={m.label}
          onClick={() => onMetricClick(m.type)}
          className="bg-[#0b0a12] border border-[#1e1933] hover:border-purple-500/50 p-3.5 rounded-xl shadow-sm relative overflow-hidden flex flex-col justify-between group cursor-pointer transition-all hover:scale-[1.02]"
        >
          <div className="flex justify-between items-center text-slate-400 text-[10px] font-mono font-bold uppercase tracking-wider">
            <span>{m.label}</span>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-mono font-extrabold tracking-tight text-white">{m.value}</span>
            <span className="text-[10px] font-mono text-slate-400 font-bold bg-white/5 px-1.5 py-0.5 rounded uppercase">{m.sub}</span>
          </div>
        </div>
      ))}
    </section>
  );
};
