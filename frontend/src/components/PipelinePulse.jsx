import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Link2, Microscope, Search, Cpu, Play, ShieldCheck,
  CheckCircle2, AlertTriangle, SkipForward, Clock, Activity,
  Zap, ShieldAlert, AlertCircle
} from 'lucide-react';
import axios from 'axios';

const API_BASE = 'http://localhost:8001/api';

const STAGE_META = {
  schema_linking:  { label: 'Schema Linking',       Icon: Link2,        color: '#6366f1' },
  feasibility:     { label: 'Feasibility Analysis',  Icon: Microscope,   color: '#8b5cf6' },
  exploration:     { label: 'Gap Exploration',        Icon: Search,       color: '#a78bfa' },
  routing:         { label: 'Strategy Routing',       Icon: Cpu,          color: '#ec4899' },
  sql_generation:  { label: 'SQL Generation',         Icon: Play,         color: '#f59e0b' },
  execution:       { label: 'Query Execution',        Icon: Play,         color: '#10b981' },
  validation:      { label: 'Result Audit',           Icon: ShieldCheck,  color: '#06b6d4' },
  complete:        { label: 'Complete',               Icon: CheckCircle2, color: '#10b981' },
};

const STATUS_STYLE = {
  pending:  { ring: '#2a2a3a', bg: '#12121a', icon: 'text-slate-600', label: 'text-slate-700' },
  running:  { ring: '#10b981', bg: '#10b98115', icon: 'text-emerald-400', label: 'text-emerald-400' },
  success:  { ring: '#10b981', bg: '#10b98115', icon: 'text-emerald-400', label: 'text-slate-500' },
  error:    { ring: '#ef4444', bg: '#ef444410', icon: 'text-rose-400',    label: 'text-rose-400'  },
  skipped:  { ring: '#3a3a4a', bg: '#0e0e14',   icon: 'text-slate-700',  label: 'text-slate-700' },
};

// Derive alert flags from the stage log
function deriveAlerts(stages) {
  const alerts = [];
  const errorStages = stages.filter(s => s.status === 'error');
  const skippedStages = stages.filter(s => s.status === 'skipped');

  if (errorStages.length > 0) {
    alerts.push({
      type: 'error',
      icon: AlertTriangle,
      color: '#ef4444',
      bg: '#ef444412',
      msg: `Stage failed: ${errorStages.map(s => STAGE_META[s.stage]?.label ?? s.stage).join(', ')}`,
    });
  }
  if (skippedStages.some(s => s.stage === 'exploration')) {
    alerts.push({
      type: 'info',
      icon: SkipForward,
      color: '#a78bfa',
      bg: '#a78bfa12',
      msg: 'Gap exploration skipped — schema coverage was sufficient.',
    });
  }
  return alerts;
}

// Compute duration between running → success/error for a stage
function stageDuration(stages, stageId) {
  const runEvents = stages.filter(s => s.stage === stageId);
  const running = runEvents.find(s => s.status === 'running');
  const done = runEvents.find(s => s.status === 'success' || s.status === 'error');
  if (running && done) return done.ts - running.ts;
  return null;
}

// Convert stage log to a flat status map
function buildStatusMap(stages) {
  const map = {};
  for (const entry of stages) {
    // last write wins (so 'success' overwrites 'running')
    map[entry.stage] = entry.status;
  }
  return map;
}

const PipelinePulse = ({ instanceId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!instanceId) return;
    setLoading(true);
    axios.get(`${API_BASE}/pipeline/run/${instanceId}`)
      .then(r => setData(r.data))
      .catch(() => setData({ stages: [], query: '' }))
      .finally(() => setLoading(false));
  }, [instanceId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-10 text-slate-600">
        <Activity className="w-4 h-4 animate-spin" />
        <span className="text-xs font-mono">Loading pipeline telemetry…</span>
      </div>
    );
  }

  const stages = data?.stages ?? [];
  const query = data?.query ?? '';

  if (stages.length === 0) {
    return (
      <div className="flex flex-col items-center gap-3 py-12 text-slate-600">
        <AlertCircle size={28} className="opacity-40" />
        <p className="text-xs font-mono">No telemetry recorded for this run yet.</p>
        <p className="text-[11px] text-slate-700">Run the query again to capture stage data.</p>
      </div>
    );
  }

  const statusMap = buildStatusMap(stages);
  const alerts = deriveAlerts(stages);
  const stageOrder = Object.keys(STAGE_META);

  // Total run duration
  const tsFirst = stages[0]?.ts;
  const tsLast = stages[stages.length - 1]?.ts;
  const totalMs = tsFirst && tsLast ? tsLast - tsFirst : null;

  return (
    <div className="space-y-4 p-4">
      {/* Query chip */}
      {query && (
        <div className="bg-[#0a0a10] border border-[#1a1a28] rounded-xl px-4 py-3">
          <div className="text-[10px] font-mono text-slate-600 uppercase tracking-wider mb-1">Query</div>
          <p className="text-xs text-slate-300 leading-relaxed line-clamp-3">{query}</p>
        </div>
      )}

      {/* Alerts */}
      {alerts.length > 0 && (
        <div className="space-y-2">
          {alerts.map((a, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.1 }}
              className="flex items-start gap-2.5 rounded-xl px-3 py-2.5 border"
              style={{ backgroundColor: a.bg, borderColor: `${a.color}30` }}
            >
              <a.icon size={13} style={{ color: a.color }} className="mt-0.5 shrink-0" />
              <span className="text-[11px] font-mono" style={{ color: a.color }}>{a.msg}</span>
            </motion.div>
          ))}
        </div>
      )}

      {/* Stage timeline */}
      <div className="bg-[#0a0a10] border border-[#1a1a28] rounded-2xl overflow-hidden">
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#1a1a28]">
          <span className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-widest">
            Stage Timeline
          </span>
          {totalMs != null && (
            <span className="flex items-center gap-1 text-[10px] font-mono text-slate-600">
              <Clock size={9} />
              {(totalMs / 1000).toFixed(2)}s total
            </span>
          )}
        </div>

        <div className="divide-y divide-[#0f0f18]">
          {stageOrder.map((stageId, idx) => {
            const meta = STAGE_META[stageId];
            const status = statusMap[stageId] ?? 'pending';
            const style = STATUS_STYLE[status] ?? STATUS_STYLE.pending;
            const dur = stageDuration(stages, stageId);

            const BadgeIcon = status === 'error' ? AlertTriangle
              : status === 'skipped' ? SkipForward
              : status === 'success' ? CheckCircle2
              : null;

            return (
              <motion.div
                key={stageId}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: status === 'skipped' ? 0.45 : 1, x: 0 }}
                transition={{ delay: idx * 0.04 }}
                className="flex items-center gap-3 px-4 py-3"
              >
                {/* Icon box */}
                <div className="relative shrink-0">
                  {status === 'running' && (
                    <motion.div
                      className="absolute inset-0 rounded-xl border-2 border-emerald-400"
                      animate={{ scale: [1, 1.3, 1], opacity: [0.8, 0, 0.8] }}
                      transition={{ duration: 1.4, repeat: Infinity }}
                    />
                  )}
                  <div
                    className="w-9 h-9 rounded-xl border-2 flex items-center justify-center"
                    style={{ borderColor: style.ring, backgroundColor: style.bg }}
                  >
                    <meta.Icon size={14} style={
                      status === 'running' || status === 'success'
                        ? { color: meta.color }
                        : undefined
                    } className={STATUS_STYLE[status]?.icon ?? ''} />
                  </div>
                  {BadgeIcon && (
                    <motion.div
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      className="absolute -top-1 -right-1 w-3.5 h-3.5 rounded-full flex items-center justify-center"
                      style={{
                        background: status === 'error' ? '#1a0a0a' : status === 'skipped' ? '#111' : '#0a1a0a',
                        border: `1.5px solid ${status === 'error' ? '#ef4444' : status === 'skipped' ? '#3a3a4a' : '#10b981'}`,
                      }}
                    >
                      <BadgeIcon size={8} color={status === 'error' ? '#ef4444' : status === 'skipped' ? '#4a4a5a' : '#10b981'} />
                    </motion.div>
                  )}
                </div>

                {/* Label */}
                <div className="flex-1 min-w-0">
                  <div className={`text-xs font-semibold ${
                    status === 'running' ? 'text-slate-200' :
                    status === 'success' ? 'text-slate-300' :
                    status === 'error' ? 'text-rose-300' : 'text-slate-600'
                  }`}>
                    {meta.label}
                  </div>
                  {status === 'running' && (
                    <div className="text-[10px] text-emerald-400/70 font-mono mt-0.5">● processing…</div>
                  )}
                </div>

                {/* Duration badge */}
                {dur != null && (
                  <span className="shrink-0 flex items-center gap-1 text-[10px] font-mono text-slate-600">
                    <Zap size={9} className="text-amber-500/60" />
                    {dur < 1000 ? `${dur}ms` : `${(dur / 1000).toFixed(1)}s`}
                  </span>
                )}

                {/* Status label */}
                <span className={`shrink-0 text-[10px] font-mono font-bold uppercase tracking-wide ${style.label}`}>
                  {status !== 'pending' ? status : '—'}
                </span>
              </motion.div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default PipelinePulse;
