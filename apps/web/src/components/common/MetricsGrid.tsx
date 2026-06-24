import React from 'react';
import {
  BarChart3, CheckCircle2, XCircle, Target, Clock, Cpu, DollarSign,
  Activity, TrendingUp, Database, Layers, Zap,
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
  theme?: 'light' | 'dark';
}

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  total:     BarChart3,
  succeeded: CheckCircle2,
  errored:   XCircle,
  gold:      Target,
  latency:   Clock,
  tokens:    Cpu,
  cost:      DollarSign,
  llm:       Zap,
  evaluated: Activity,
  trending:  TrendingUp,
  database:  Database,
  layers:    Layers,
};

interface ColorConfig {
  bg: string;
  bar: string;
  border: string;
  valueCls: string;
  iconBg: string;
  iconText: string;
  watermark: string;
  subCls: string;
  glow: string;
  labelCls: string;
}

type ThemeMap = Record<string, ColorConfig>;

const DARK: ThemeMap = {
  blue: {
    bg:        'bg-gradient-to-br from-blue-950/70 via-blue-950/30 to-slate-950',
    bar:       'bg-blue-400',
    border:    'border-blue-700/30',
    valueCls:  'text-blue-300',
    iconBg:    'bg-blue-500/15',
    iconText:  'text-blue-400',
    watermark: 'text-blue-400/[0.07]',
    subCls:    'text-blue-400/70',
    glow:      'hover:shadow-blue-900/60 hover:border-blue-600/50',
    labelCls:  'text-blue-400/80',
  },
  indigo: {
    bg:        'bg-gradient-to-br from-indigo-950/70 via-indigo-950/30 to-slate-950',
    bar:       'bg-indigo-400',
    border:    'border-indigo-700/30',
    valueCls:  'text-indigo-300',
    iconBg:    'bg-indigo-500/15',
    iconText:  'text-indigo-400',
    watermark: 'text-indigo-400/[0.07]',
    subCls:    'text-indigo-400/70',
    glow:      'hover:shadow-indigo-900/60 hover:border-indigo-600/50',
    labelCls:  'text-indigo-400/80',
  },
  emerald: {
    bg:        'bg-gradient-to-br from-emerald-950/70 via-emerald-950/30 to-slate-950',
    bar:       'bg-emerald-400',
    border:    'border-emerald-700/30',
    valueCls:  'text-emerald-300',
    iconBg:    'bg-emerald-500/15',
    iconText:  'text-emerald-400',
    watermark: 'text-emerald-400/[0.07]',
    subCls:    'text-emerald-400/70',
    glow:      'hover:shadow-emerald-900/60 hover:border-emerald-600/50',
    labelCls:  'text-emerald-400/80',
  },
  rose: {
    bg:        'bg-gradient-to-br from-rose-950/70 via-rose-950/30 to-slate-950',
    bar:       'bg-rose-400',
    border:    'border-rose-700/30',
    valueCls:  'text-rose-300',
    iconBg:    'bg-rose-500/15',
    iconText:  'text-rose-400',
    watermark: 'text-rose-400/[0.07]',
    subCls:    'text-rose-400/70',
    glow:      'hover:shadow-rose-900/60 hover:border-rose-600/50',
    labelCls:  'text-rose-400/80',
  },
  violet: {
    bg:        'bg-gradient-to-br from-violet-950/70 via-violet-950/30 to-slate-950',
    bar:       'bg-violet-400',
    border:    'border-violet-700/30',
    valueCls:  'text-violet-300',
    iconBg:    'bg-violet-500/15',
    iconText:  'text-violet-400',
    watermark: 'text-violet-400/[0.07]',
    subCls:    'text-violet-400/70',
    glow:      'hover:shadow-violet-900/60 hover:border-violet-600/50',
    labelCls:  'text-violet-400/80',
  },
  cyan: {
    bg:        'bg-gradient-to-br from-cyan-950/70 via-cyan-950/30 to-slate-950',
    bar:       'bg-cyan-400',
    border:    'border-cyan-700/30',
    valueCls:  'text-cyan-300',
    iconBg:    'bg-cyan-500/15',
    iconText:  'text-cyan-400',
    watermark: 'text-cyan-400/[0.07]',
    subCls:    'text-cyan-400/70',
    glow:      'hover:shadow-cyan-900/60 hover:border-cyan-600/50',
    labelCls:  'text-cyan-400/80',
  },
  fuchsia: {
    bg:        'bg-gradient-to-br from-fuchsia-950/70 via-fuchsia-950/30 to-slate-950',
    bar:       'bg-fuchsia-400',
    border:    'border-fuchsia-700/30',
    valueCls:  'text-fuchsia-300',
    iconBg:    'bg-fuchsia-500/15',
    iconText:  'text-fuchsia-400',
    watermark: 'text-fuchsia-400/[0.07]',
    subCls:    'text-fuchsia-400/70',
    glow:      'hover:shadow-fuchsia-900/60 hover:border-fuchsia-600/50',
    labelCls:  'text-fuchsia-400/80',
  },
  amber: {
    bg:        'bg-gradient-to-br from-amber-950/70 via-amber-950/30 to-slate-950',
    bar:       'bg-amber-400',
    border:    'border-amber-700/30',
    valueCls:  'text-amber-300',
    iconBg:    'bg-amber-500/15',
    iconText:  'text-amber-400',
    watermark: 'text-amber-400/[0.07]',
    subCls:    'text-amber-400/70',
    glow:      'hover:shadow-amber-900/60 hover:border-amber-600/50',
    labelCls:  'text-amber-400/80',
  },
  purple: {
    bg:        'bg-gradient-to-br from-purple-950/70 via-purple-950/30 to-slate-950',
    bar:       'bg-purple-400',
    border:    'border-purple-700/30',
    valueCls:  'text-purple-300',
    iconBg:    'bg-purple-500/15',
    iconText:  'text-purple-400',
    watermark: 'text-purple-400/[0.07]',
    subCls:    'text-purple-400/70',
    glow:      'hover:shadow-purple-900/60 hover:border-purple-600/50',
    labelCls:  'text-purple-400/80',
  },
  teal: {
    bg:        'bg-gradient-to-br from-teal-950/70 via-teal-950/30 to-slate-950',
    bar:       'bg-teal-400',
    border:    'border-teal-700/30',
    valueCls:  'text-teal-300',
    iconBg:    'bg-teal-500/15',
    iconText:  'text-teal-400',
    watermark: 'text-teal-400/[0.07]',
    subCls:    'text-teal-400/70',
    glow:      'hover:shadow-teal-900/60 hover:border-teal-600/50',
    labelCls:  'text-teal-400/80',
  },
};

const LIGHT: ThemeMap = {
  blue: {
    bg:        'bg-gradient-to-br from-blue-50 to-blue-100/60',
    bar:       'bg-blue-500',
    border:    'border-blue-200',
    valueCls:  'text-blue-700',
    iconBg:    'bg-blue-500/10',
    iconText:  'text-blue-600',
    watermark: 'text-blue-400/[0.12]',
    subCls:    'text-blue-500/80',
    glow:      'hover:shadow-blue-200/80 hover:border-blue-400',
    labelCls:  'text-blue-600/80',
  },
  indigo: {
    bg:        'bg-gradient-to-br from-indigo-50 to-indigo-100/60',
    bar:       'bg-indigo-500',
    border:    'border-indigo-200',
    valueCls:  'text-indigo-700',
    iconBg:    'bg-indigo-500/10',
    iconText:  'text-indigo-600',
    watermark: 'text-indigo-400/[0.12]',
    subCls:    'text-indigo-500/80',
    glow:      'hover:shadow-indigo-200/80 hover:border-indigo-400',
    labelCls:  'text-indigo-600/80',
  },
  emerald: {
    bg:        'bg-gradient-to-br from-emerald-50 to-emerald-100/60',
    bar:       'bg-emerald-500',
    border:    'border-emerald-200',
    valueCls:  'text-emerald-700',
    iconBg:    'bg-emerald-500/10',
    iconText:  'text-emerald-600',
    watermark: 'text-emerald-400/[0.12]',
    subCls:    'text-emerald-500/80',
    glow:      'hover:shadow-emerald-200/80 hover:border-emerald-400',
    labelCls:  'text-emerald-600/80',
  },
  rose: {
    bg:        'bg-gradient-to-br from-rose-50 to-rose-100/60',
    bar:       'bg-rose-500',
    border:    'border-rose-200',
    valueCls:  'text-rose-700',
    iconBg:    'bg-rose-500/10',
    iconText:  'text-rose-600',
    watermark: 'text-rose-400/[0.12]',
    subCls:    'text-rose-500/80',
    glow:      'hover:shadow-rose-200/80 hover:border-rose-400',
    labelCls:  'text-rose-600/80',
  },
  violet: {
    bg:        'bg-gradient-to-br from-violet-50 to-violet-100/60',
    bar:       'bg-violet-500',
    border:    'border-violet-200',
    valueCls:  'text-violet-700',
    iconBg:    'bg-violet-500/10',
    iconText:  'text-violet-600',
    watermark: 'text-violet-400/[0.12]',
    subCls:    'text-violet-500/80',
    glow:      'hover:shadow-violet-200/80 hover:border-violet-400',
    labelCls:  'text-violet-600/80',
  },
  cyan: {
    bg:        'bg-gradient-to-br from-cyan-50 to-cyan-100/60',
    bar:       'bg-cyan-500',
    border:    'border-cyan-200',
    valueCls:  'text-cyan-700',
    iconBg:    'bg-cyan-500/10',
    iconText:  'text-cyan-600',
    watermark: 'text-cyan-400/[0.12]',
    subCls:    'text-cyan-500/80',
    glow:      'hover:shadow-cyan-200/80 hover:border-cyan-400',
    labelCls:  'text-cyan-600/80',
  },
  fuchsia: {
    bg:        'bg-gradient-to-br from-fuchsia-50 to-fuchsia-100/60',
    bar:       'bg-fuchsia-500',
    border:    'border-fuchsia-200',
    valueCls:  'text-fuchsia-700',
    iconBg:    'bg-fuchsia-500/10',
    iconText:  'text-fuchsia-600',
    watermark: 'text-fuchsia-400/[0.12]',
    subCls:    'text-fuchsia-500/80',
    glow:      'hover:shadow-fuchsia-200/80 hover:border-fuchsia-400',
    labelCls:  'text-fuchsia-600/80',
  },
  amber: {
    bg:        'bg-gradient-to-br from-amber-50 to-amber-100/60',
    bar:       'bg-amber-500',
    border:    'border-amber-200',
    valueCls:  'text-amber-700',
    iconBg:    'bg-amber-500/10',
    iconText:  'text-amber-600',
    watermark: 'text-amber-400/[0.12]',
    subCls:    'text-amber-500/80',
    glow:      'hover:shadow-amber-200/80 hover:border-amber-400',
    labelCls:  'text-amber-600/80',
  },
  purple: {
    bg:        'bg-gradient-to-br from-purple-50 to-purple-100/60',
    bar:       'bg-purple-500',
    border:    'border-purple-200',
    valueCls:  'text-purple-700',
    iconBg:    'bg-purple-500/10',
    iconText:  'text-purple-600',
    watermark: 'text-purple-400/[0.12]',
    subCls:    'text-purple-500/80',
    glow:      'hover:shadow-purple-200/80 hover:border-purple-400',
    labelCls:  'text-purple-600/80',
  },
  teal: {
    bg:        'bg-gradient-to-br from-teal-50 to-teal-100/60',
    bar:       'bg-teal-500',
    border:    'border-teal-200',
    valueCls:  'text-teal-700',
    iconBg:    'bg-teal-500/10',
    iconText:  'text-teal-600',
    watermark: 'text-teal-400/[0.12]',
    subCls:    'text-teal-500/80',
    glow:      'hover:shadow-teal-200/80 hover:border-teal-400',
    labelCls:  'text-teal-600/80',
  },
};

const DARK_FALLBACK: ColorConfig = {
  bg:        'bg-gradient-to-br from-slate-900 to-slate-950',
  bar:       'bg-slate-500',
  border:    'border-slate-700/30',
  valueCls:  'text-slate-300',
  iconBg:    'bg-slate-500/15',
  iconText:  'text-slate-400',
  watermark: 'text-slate-400/[0.07]',
  subCls:    'text-slate-400/70',
  glow:      'hover:shadow-slate-900/60 hover:border-slate-600/50',
  labelCls:  'text-slate-400/80',
};

const LIGHT_FALLBACK: ColorConfig = {
  bg:        'bg-gradient-to-br from-slate-50 to-slate-100/60',
  bar:       'bg-slate-400',
  border:    'border-slate-200',
  valueCls:  'text-slate-700',
  iconBg:    'bg-slate-400/10',
  iconText:  'text-slate-500',
  watermark: 'text-slate-400/[0.12]',
  subCls:    'text-slate-500/80',
  glow:      'hover:shadow-slate-200/80 hover:border-slate-400',
  labelCls:  'text-slate-500/80',
};

export const MetricsGrid: React.FC<MetricsGridProps> = ({ metrics, onMetricClick, theme = 'dark' }) => {
  if (!metrics || metrics.length === 0) return null;

  const palette = theme === 'light' ? LIGHT : DARK;
  const fallback = theme === 'light' ? LIGHT_FALLBACK : DARK_FALLBACK;

  return (
    <section className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3">
      {metrics.map(m => {
        const IconComp = m.icon || ICON_MAP[m.type] || BarChart3;
        const cfg = palette[m.color] ?? fallback;

        return (
          <div
            key={m.label}
            onClick={() => onMetricClick(m.type)}
            className={`
              relative overflow-hidden rounded-2xl border ${cfg.border} ${cfg.bg}
              p-4 shadow-sm transition-all duration-200 cursor-pointer
              hover:shadow-lg hover:scale-[1.03] ${cfg.glow}
              group
            `}
          >
            {/* Colored top accent bar */}
            <div className={`absolute top-0 left-0 right-0 h-[3px] ${cfg.bar} rounded-t-2xl`} />

            {/* Giant watermark icon */}
            <div className={`absolute -bottom-3 -right-3 pointer-events-none ${cfg.watermark}`}>
              <IconComp className="w-20 h-20" />
            </div>

            {/* Content */}
            <div className="relative z-10">
              {/* Label + icon badge */}
              <div className="flex items-center justify-between mb-3">
                <span className={`text-[9px] font-mono font-bold uppercase tracking-widest leading-none ${cfg.labelCls}`}>
                  {m.label}
                </span>
                <div className={`w-6 h-6 rounded-lg flex items-center justify-center shrink-0 ${cfg.iconBg}`}>
                  <IconComp className={`w-3.5 h-3.5 ${cfg.iconText}`} />
                </div>
              </div>

              {/* Value */}
              <span className={`block text-2xl font-mono font-extrabold tracking-tight leading-none ${cfg.valueCls}`}>
                {m.value}
              </span>

              {/* Sub label */}
              <span className={`block text-[9px] font-mono font-bold uppercase tracking-wider mt-1.5 ${cfg.subCls}`}>
                {m.sub}
              </span>
            </div>
          </div>
        );
      })}
    </section>
  );
};
