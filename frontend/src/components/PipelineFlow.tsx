import { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Link2, Microscope, Search, Cpu, Play, ShieldCheck, CheckCircle2,
  AlertTriangle, SkipForward
} from 'lucide-react';

const STAGES = [
  { id: 'schema_linking',  label: 'Schema Linking',       sublabel: 'Mapping question to tables & columns',    Icon: Link2,        color: '#6366f1' },
  { id: 'feasibility',     label: 'Feasibility Analysis',  sublabel: 'Checking schema coverage',                Icon: Microscope,   color: '#8b5cf6' },
  { id: 'exploration',     label: 'Gap Exploration',        sublabel: 'Probing live data for missing context',   Icon: Search,       color: '#a78bfa' },
  { id: 'routing',         label: 'Strategy Routing',       sublabel: 'Choosing execution strategy',             Icon: Cpu,          color: '#ec4899' },
  { id: 'sql_generation',  label: 'SQL Generation',         sublabel: 'Synthesising and critiquing candidates',  Icon: Play,         color: '#f59e0b' },
  { id: 'execution',       label: 'Query Execution',        sublabel: 'Running against your database',           Icon: Play,         color: '#10b981' },
  { id: 'validation',      label: 'Result Audit',           sublabel: 'Data-IQ quality check',                   Icon: ShieldCheck,  color: '#06b6d4' },
  { id: 'complete',        label: 'Complete',               sublabel: 'Results ready',                           Icon: CheckCircle2, color: '#10b981' },
];

const STATUS_RING = { pending: 'border-[#2a2a3a]', running: 'border-emerald-400', success: 'border-emerald-500', error: 'border-rose-500', skipped: 'border-[#3a3a4a]' };
const STATUS_BG   = { pending: 'bg-[#12121a]', running: 'bg-emerald-500/10', success: 'bg-emerald-500/15', error: 'bg-rose-500/10', skipped: 'bg-[#0e0e14]' };
const STATUS_ICON = { pending: 'text-slate-600', running: 'text-emerald-400', success: 'text-emerald-400', error: 'text-rose-400', skipped: 'text-slate-700' };

const FlowDrop = ({ active }) => (
  <AnimatePresence>
    {active && (
      <motion.div
        key="drop"
        className="absolute left-1/2 -translate-x-1/2 w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_6px_2px_rgba(52,211,153,0.6)]"
        initial={{ top: 0, opacity: 0 }}
        animate={{ top: '100%', opacity: [0, 1, 1, 0] }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.9, ease: 'easeIn', repeat: Infinity, repeatDelay: 0.1 }}
      />
    )}
  </AnimatePresence>
);

const Connector = ({ fromStatus }) => {
  const flowing = fromStatus === 'running' || fromStatus === 'success';
  return (
    <div className="relative flex justify-center" style={{ height: 28 }}>
      <div
        className="w-px h-full"
        style={{ background: flowing ? 'linear-gradient(to bottom,rgba(52,211,153,0.4),rgba(52,211,153,0.1))' : 'rgba(42,42,58,0.8)' }}
      />
      <FlowDrop active={fromStatus === 'running'} />
    </div>
  );
};

const StageNode = ({ stage, status }) => {
  const { label, sublabel, Icon, color } = stage;
  const isRunning = status === 'running';
  const isSuccess = status === 'success';
  const isError   = status === 'error';
  const isSkipped = status === 'skipped';
  const StatusIcon = isError ? AlertTriangle : isSkipped ? SkipForward : isSuccess ? CheckCircle2 : null;

  return (
    <motion.div
      className="flex items-center gap-3"
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: isSkipped ? 0.4 : 1, x: 0 }}
      transition={{ duration: 0.25 }}
    >
      <div className="relative shrink-0">
        {isRunning && (
          <motion.div
            className="absolute inset-0 rounded-xl border-2 border-emerald-400"
            animate={{ scale: [1, 1.25, 1], opacity: [0.8, 0, 0.8] }}
            transition={{ duration: 1.4, repeat: Infinity, ease: 'easeOut' }}
          />
        )}
        <div
          className={`w-10 h-10 rounded-xl border-2 flex items-center justify-center transition-all duration-300 ${STATUS_RING[status] ?? STATUS_RING.pending} ${STATUS_BG[status] ?? STATUS_BG.pending}`}
          style={isRunning ? { boxShadow: `0 0 12px 2px ${color}44` } : undefined}
        >
          <Icon size={16} className={`transition-all duration-300 ${STATUS_ICON[status] ?? STATUS_ICON.pending}`} style={isRunning || isSuccess ? { color } : undefined} />
        </div>
        {StatusIcon && (
          <motion.div
            className="absolute -top-1 -right-1 w-4 h-4 rounded-full flex items-center justify-center"
            style={{ background: isError ? '#1a0a0a' : isSkipped ? '#111' : '#0a1a0a', border: `1.5px solid ${isError ? '#ef4444' : isSkipped ? '#3a3a4a' : '#10b981'}` }}
            initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring', stiffness: 300 }}
          >
            <StatusIcon size={9} color={isError ? '#ef4444' : isSkipped ? '#4a4a5a' : '#10b981'} />
          </motion.div>
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className={`text-xs font-semibold leading-tight transition-colors duration-200 ${isRunning ? 'text-slate-200' : isSuccess ? 'text-slate-300' : isError ? 'text-rose-300' : 'text-slate-600'}`}>
          {label}
        </div>
        <div className={`text-[10px] leading-tight mt-0.5 transition-colors duration-200 ${isRunning ? 'text-emerald-400/70 font-mono' : 'text-slate-700'}`}>
          {isRunning ? '● processing…' : sublabel}
        </div>
      </div>
      <div className={`text-[10px] font-mono font-bold uppercase tracking-wider shrink-0 ${isRunning ? 'text-emerald-400' : isSuccess ? 'text-emerald-500/70' : isError ? 'text-rose-400' : 'text-slate-700'}`}>
        {status !== 'pending' ? status : ''}
      </div>
    </motion.div>
  );
};

const PipelineFlow = ({ stageStatuses }) => {
  const statuses = stageStatuses || {};
  const activeIdx = STAGES.findIndex(s => statuses[s.id] === 'running');
  const nodeRefs = useRef([]);

  useEffect(() => {
    if (activeIdx >= 0 && nodeRefs.current[activeIdx]) {
      nodeRefs.current[activeIdx].scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [activeIdx]);

  return (
    <motion.div
      className="rounded-2xl bg-[#0a0a12] border border-[#1a1a28] p-4 overflow-hidden"
      initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
    >
      <div className="flex items-center gap-2 mb-4 pb-3 border-b border-[#1a1a28]">
        <div className="flex gap-0.5">
          {[0, 0.15, 0.3].map(d => (
            <span key={d} className="w-1.5 h-1.5 rounded-full bg-emerald-400/70 animate-bounce" style={{ animationDelay: `${d}s` }} />
          ))}
        </div>
        <span className="text-[11px] font-bold text-slate-400 uppercase tracking-widest font-mono">Pipeline Flow</span>
      </div>
      <div className="space-y-0">
        {STAGES.map((stage, i) => {
          const status = statuses[stage.id] ?? 'pending';
          const prevStatus = i > 0 ? (statuses[STAGES[i - 1].id] ?? 'pending') : null;
          return (
            <div key={stage.id} ref={el => (nodeRefs.current[i] = el)}>
              {i > 0 && <Connector fromStatus={prevStatus} />}
              <StageNode stage={stage} status={status} />
            </div>
          );
        })}
      </div>
    </motion.div>
  );
};

export default PipelineFlow;
