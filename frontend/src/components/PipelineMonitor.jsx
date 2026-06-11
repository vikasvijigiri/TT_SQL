import { useState, useEffect, useRef, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  RefreshCw, Clock, CheckCircle2, Database, Code,
  Star, Activity
} from 'lucide-react';
import PipelineFlow from './PipelineFlow';
import axios from 'axios';

const API_BASE = 'http://localhost:8001/api';

// Replay sequence: [stage_id, runAt_ms, successAt_ms]
const REPLAY_SEQ = [
  ['schema_linking',  250,  1050],
  ['feasibility',    1050,  1850],
  ['exploration',    1850,  2450],
  ['routing',        2450,  2950],
  ['sql_generation', 2950,  4350],
  ['execution',      4350,  5150],
  ['validation',     5150,  5850],
  ['complete',       5850,  6100],
];

const PipelineMonitor = () => {
  const [stageStatuses, setStageStatuses] = useState({});
  const [runs, setRuns] = useState([]);
  const [loadingRuns, setLoadingRuns] = useState(true);
  const [selectedRun, setSelectedRun] = useState(null);
  const [replaying, setReplaying] = useState(false);
  const timers = useRef([]);

  const replay = useCallback(() => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
    setStageStatuses({});
    setReplaying(true);

    REPLAY_SEQ.forEach(([stage, runAt, doneAt]) => {
      timers.current.push(
        setTimeout(() => setStageStatuses(p => ({ ...p, [stage]: 'running' })), runAt),
        setTimeout(() => setStageStatuses(p => ({ ...p, [stage]: 'success' })), doneAt),
      );
    });
    timers.current.push(setTimeout(() => setReplaying(false), 6200));
  }, []);

  useEffect(() => {
    replay();
    setLoadingRuns(true);
    axios.get(`${API_BASE}/pipeline/recent_runs`)
      .then(r => setRuns(r.data || []))
      .catch(() => setRuns([]))
      .finally(() => setLoadingRuns(false));

    return () => timers.current.forEach(clearTimeout);
  }, [replay]);

  const formatAge = (ms) => {
    const diff = Date.now() - ms;
    const m = Math.floor(diff / 60000);
    if (m < 1) return 'just now';
    if (m < 60) return `${m}m ago`;
    return `${Math.floor(m / 60)}h ago`;
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-5"
    >
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-bold text-slate-200 flex items-center gap-2">
            <Activity className="w-4 h-4 text-emerald-400" />
            Pipeline Monitor
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Live replay of the SemanticDIN execution flow · cached SQL runs
          </p>
        </div>
        <button
          onClick={replay}
          disabled={replaying}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 text-xs font-bold transition-all disabled:opacity-50"
        >
          <RefreshCw size={12} className={replaying ? 'animate-spin' : ''} />
          {replaying ? 'Replaying…' : 'Replay'}
        </button>
      </div>

      {/* Two-column body */}
      <div className="flex gap-5 items-start">

        {/* ── Left: pipeline flow ─────────────────────────────── */}
        <div className="w-72 shrink-0">
          <PipelineFlow stageStatuses={stageStatuses} />
        </div>

        {/* ── Right: recent runs ──────────────────────────────── */}
        <div className="flex-1 min-w-0 bg-[#0a0a12] border border-[#1a1a28] rounded-2xl overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-[#1a1a28]">
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-widest font-mono">
              Cached SQL Runs
            </span>
            {!loadingRuns && (
              <span className="text-[10px] text-slate-600 font-mono">{runs.length} entries</span>
            )}
          </div>

          {loadingRuns ? (
            <div className="flex items-center justify-center py-16 gap-2 text-slate-600">
              <Activity className="w-4 h-4 animate-spin" />
              <span className="text-xs font-mono">Loading…</span>
            </div>
          ) : runs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 gap-3 text-slate-600">
              <Database size={28} className="opacity-40" />
              <p className="text-xs font-mono">No runs cached yet. Ask a query first.</p>
            </div>
          ) : (
            <div className="divide-y divide-[#0f0f1a] max-h-[560px] overflow-y-auto no-scrollbar">
              {runs.map(run => {
                const expanded = selectedRun?.id === run.id;
                return (
                  <div
                    key={run.id}
                    onClick={() => setSelectedRun(expanded ? null : run)}
                    className="px-4 py-3 hover:bg-white/[0.02] cursor-pointer transition-all group"
                  >
                    {/* Row header */}
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <CheckCircle2 size={11} className="text-emerald-500 shrink-0" />
                          <span className="text-[11px] font-mono text-slate-500 truncate">
                            {run.id}
                          </span>
                          {run.curated && (
                            <span className="flex items-center gap-0.5 text-[9px] font-bold px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 uppercase tracking-wide">
                              <Star size={8} />
                              curated
                            </span>
                          )}
                        </div>
                        <pre className="text-[11px] font-mono text-slate-300 whitespace-pre-wrap leading-relaxed line-clamp-2 group-hover:text-slate-200 transition-colors">
                          {run.sql}
                        </pre>
                      </div>
                      <span className="shrink-0 text-[10px] text-slate-600 font-mono flex items-center gap-1 mt-1">
                        <Clock size={9} />
                        {formatAge(run.timestamp_ms)}
                      </span>
                    </div>

                    {/* Expanded: full SQL */}
                    {expanded && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        className="mt-2 pt-2 border-t border-[#1a1a28]"
                      >
                        <div className="flex items-center gap-1.5 mb-1.5 text-[10px] text-slate-600 font-mono">
                          <Code size={9} />
                          Full SQL
                        </div>
                        <pre className="text-[11px] font-mono text-emerald-300/80 whitespace-pre-wrap leading-relaxed overflow-x-auto rounded-lg bg-[#060608] p-3 border border-[#1a1a28]">
                          {run.sql_full || run.sql}
                        </pre>
                      </motion.div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
};

export default PipelineMonitor;
