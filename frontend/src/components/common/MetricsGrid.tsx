import React from 'react';
import {
  BarChart3, CheckCircle2, XCircle, Trophy, Clock, Cpu, DollarSign, Zap,
  Activity, TrendingUp, Database, Layers
} from 'lucide-react';

export interface MetricData {
  label: string;
  value: string | number;
  color: string;
  type: string;
  sub: string;
  icon?: React.ComponentType<{ className?: string }>;
}

interface MetricsGridProps {
  metrics: MetricData[];
  onMetricClick: (type: string) => void;
}

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  total: BarChart3,
  succeeded: CheckCircle2,
  errored: XCircle,
  gold: Trophy,
  latency: Clock,
  tokens: Cpu,
  cost: DollarSign,
  llm: Zap,
  evaluated: Activity,
  trending: TrendingUp,
  database: Database,
  layers: Layers,
};

const COLOR_MAP: Record<string, string> = {
  blue:    'text-sky-400 bg-sky-500/10 border-sky-500/25',
  emerald: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
  rose:    'text-rose-400 bg-rose-500/10 border-rose-500/20',
  indigo:  'text-indigo-400 bg-indigo-500/10 border-indigo-500/20',
  cyan:    'text-cyan-400 bg-cyan-500/10 border-cyan-500/20',
  fuchsia: 'text-fuchsia-400 bg-fuchsia-500/10 border-fuchsia-500/20',
  amber:   'text-amber-400 bg-amber-500/10 border-amber-500/20',
  violet:  'text-violet-400 bg-violet-500/10 border-violet-500/20',
  purple:  'text-purple-400 bg-purple-500/10 border-purple-500/20',
  teal:    'text-teal-400 bg-teal-500/10 border-teal-500/20',
};

export const MetricsGrid: React.FC<MetricsGridProps> = ({ metrics, onMetricClick }) => {
  if (!metrics || metrics.length === 0) return null;

  return (
    <section className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3.5">
      {metrics.map(m => {
        const IconComp = m.icon || ICON_MAP[m.type] || BarChart3;
        const iconClass = COLOR_MAP[m.color] || 'text-slate-400 bg-slate-500/10 border-slate-500/20';
        return (
          <div
            key={m.label}
            onClick={() => onMetricClick(m.type)}
            className="bg-[#1e2d40] border border-[#2c3e55] hover:border-violet-500/40 p-3.5 rounded-xl shadow-sm relative overflow-hidden flex flex-col justify-between group cursor-pointer transition-all hover:scale-[1.02]"
          >
            <div className="flex justify-between items-center mb-1.5">
              <span className="text-slate-400 text-[9px] font-mono font-bold uppercase tracking-wider leading-tight">{m.label}</span>
              <div className={`w-6 h-6 rounded-lg border flex items-center justify-center shrink-0 ${iconClass}`}>
                <IconComp className="w-3 h-3" />
              </div>
            </div>
            <div className="flex items-baseline gap-1.5">
              <span className="text-2xl font-mono font-extrabold tracking-tight text-white">{m.value}</span>
              <span className="text-[9px] font-mono text-slate-400 font-bold bg-white/5 px-1 py-0.5 rounded uppercase">{m.sub}</span>
            </div>
          </div>
        );
      })}
    </section>
  );
};
