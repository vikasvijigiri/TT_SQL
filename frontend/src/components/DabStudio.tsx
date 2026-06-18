import { MetricsGrid } from './common/MetricsGrid';
import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts';
import {
  BarChart3,
  Database,
  Activity,
  Cpu,
  CheckCircle2,
  XCircle,
  Play,
  Search,
  ChevronRight,
  Zap,
  Clock,
  Layers,
  ArrowLeft,
  Copy,
  Check,
  Filter,
  RefreshCw,
  Sliders,
  Terminal,
  FileSpreadsheet,
  FileCode,
  AlertTriangle,
  DollarSign,
  TrendingUp,
  X,
  Sparkles,
  Trophy,
  TerminalSquare,
  ShieldAlert,
  Link2,
  Microscope,
  ShieldCheck,
  Lightbulb,
  Download,
  MessageSquare,
  LogOut,
  ChevronDown,
  Info,
  User
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import NQuireLogo from './NQuireLogo';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

const generateInsights = (headers, data) => {
  if (!headers?.length || !data?.length) return [];
  const insights = [];
  insights.push(`Query returned ${data.length} row${data.length !== 1 ? 's' : ''} across ${headers.length} column${headers.length !== 1 ? 's' : ''}.`);
  const numericCols = headers.filter(h => data.some(r => r[h] !== null && r[h] !== '' && !isNaN(Number(r[h]))));
  const labelCol = headers.find(h => !numericCols.includes(h));
  numericCols.slice(0, 2).forEach(col => {
    const vals = data.map(r => Number(r[col])).filter(v => !isNaN(v));
    if (!vals.length) return;
    const max = Math.max(...vals), min = Math.min(...vals);
    const avg = (vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1);
    const maxRow = data.find(r => Number(r[col]) === max);
    if (labelCol && maxRow) insights.push(`Highest ${col}: ${max} — "${maxRow[labelCol]}". Average: ${avg}.`);
    else insights.push(`${col} spans ${min}–${max} with average ${avg}.`);
  });
  if (numericCols.length > 0) {
    const col = numericCols[0];
    const sorted = [...data].sort((a, b) => Number(b[col]) - Number(a[col]));
    const top = sorted.slice(0, Math.min(3, sorted.length));
    if (labelCol && top.length > 1) insights.push(`Top ${top.length} by ${col}: ${top.map(r => `${r[labelCol]} (${r[col]})`).join(', ')}.`);
  }
  const nullCols = headers.filter(h => data.some(r => r[h] === null || r[h] === '' || r[h] === 'NULL'));
  if (nullCols.length) insights.push(`Missing/null values in: ${nullCols.slice(0, 3).join(', ')}.`);
  return insights.slice(0, 5);
};

const InsightsChart = ({ headers, data }) => {
  const numericCols = headers?.filter(h => data?.some(r => r[h] !== null && !isNaN(Number(r[h])))) || [];
  const labelCol = headers?.find(h => !numericCols.includes(h));
  const valCol = numericCols.find(c => !c.toLowerCase().endsWith('_id') && c.toLowerCase() !== 'id') || numericCols[0];
  if (!valCol || !data?.length) return (
    <div className="flex items-center justify-center h-36 text-slate-600 text-[11px] font-mono">No numeric column to chart.</div>
  );
  const rows = data.map((r, i) => ({ label: labelCol ? String(r[labelCol] ?? `Row ${i+1}`).slice(0, 14) : `Row ${i+1}`, val: Number(r[valCol]) || 0 }));
  const maxVal = Math.max(...rows.map(r => r.val), 1);
  const W = 480, H = 160, ml = 40, mb = 32, mt = 12, mr = 12;
  const iw = W - ml - mr, ih = H - mt - mb;
  const bw = Math.max(8, Math.min(36, (iw / rows.length) * 0.55));
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" preserveAspectRatio="xMidYMid meet">
      <defs>
        <linearGradient id="dab-ig" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#a78bfa" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#6366f1" stopOpacity="0.3" />
        </linearGradient>
      </defs>
      {[0, 0.5, 1].map((r, i) => {
        const y = mt + ih - r * ih;
        return (<g key={i} opacity="0.35">
          <line x1={ml} y1={y} x2={ml+iw} y2={y} stroke="#a78bfa" strokeWidth="0.5" strokeDasharray="3,3" />
          <text x={ml-4} y={y+3} textAnchor="end" fill="#64748b" fontSize="8" fontFamily="monospace">{Math.round(r*maxVal)}</text>
        </g>);
      })}
      {rows.map((r, i) => {
        const x = ml + (i * iw / rows.length) + (iw / rows.length - bw) / 2;
        const bh = (r.val / maxVal) * ih;
        return (<g key={i}>
          <rect x={x} y={mt+ih-bh} width={bw} height={bh} fill="url(#dab-ig)" rx="2" />
          <text x={x+bw/2} y={mt+ih+14} textAnchor="middle" fill="#64748b" fontSize="8" fontFamily="monospace">
            {r.label.length > 10 ? r.label.slice(0,9)+'…' : r.label}
          </text>
        </g>);
      })}
      <line x1={ml} y1={mt} x2={ml} y2={mt+ih} stroke="#2c3e55" strokeWidth="1" />
      <line x1={ml} y1={mt+ih} x2={ml+iw} y2={mt+ih} stroke="#2c3e55" strokeWidth="1" />
    </svg>
  );
};

const C = {
  bg:       '#050508',
  surface1: 'rgba(12,10,24,0.7)',
  surface2: 'rgba(18,15,38,0.5)',
  sky:      '#38bdf8',
  indigo:   '#818cf8',
  violet:   '#a78bfa',
  teal:     '#2dd4bf',
  pink:     '#f472b6',
  mint:     '#34d399',
  text1:    '#e8eef8',
  text2:    '#94a3b8',
  text3:    '#475569',
  border:   'rgba(148,163,184,0.07)',
};

const getComplexityBadge = (complexity, type, score) => {
  const displayScore = score > 0 ? score.toFixed(2) : null;
  const displayType = type || (complexity ? String(complexity).toUpperCase() : 'STANDARD');

  let colorClass = "text-slate-400 bg-slate-800/80 border border-slate-700/30";
  if (score >= 0.75 || complexity === 'complex' || (complexity && complexity.includes('nested') && !complexity.includes('non_nested'))) {
    colorClass = "text-pink-400 bg-pink-500/10 border border-pink-500/20";
  } else if (score >= 0.45 || complexity === 'medium' || (complexity && complexity.includes('non_nested'))) {
    colorClass = "text-purple-400 bg-purple-500/10 border border-purple-500/20";
  } else if (score > 0 || complexity === 'easy') {
    colorClass = "text-blue-400 bg-blue-500/10 border border-blue-500/20";
  }

  return (
    <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded flex items-center gap-1.5 shrink-0 ${colorClass}`} title={`Complexity Type: ${displayType}`}>
      <span>{displayType}</span>
      {displayScore && (
        <span className="opacity-90 px-1 rounded bg-black/40 text-[8px] font-black text-white border border-white/10">
          {displayScore}
        </span>
      )}
    </span>
  );
};

// Telemetry Status Styling Configuration
const TELEMETRY_STATUS_STYLE = {
  pending:  { ring: 'border-slate-800', bg: 'bg-[#101014]', text: 'text-slate-600', dot: 'bg-slate-700' },
  running:  { ring: 'border-purple-400 shadow-[0_0_12px_rgba(167,139,250,0.3)]', bg: 'bg-purple-500/10', text: 'text-purple-400', dot: 'bg-purple-400 animate-pulse' },
  success:  { ring: 'border-emerald-500/50', bg: 'bg-emerald-500/10 border border-emerald-500/20', text: 'text-emerald-400', dot: 'bg-emerald-400' },
  warning:  { ring: 'border-amber-500/50', bg: 'bg-amber-500/10 border border-amber-500/20', text: 'text-amber-400', dot: 'bg-amber-400' },
  error:    { ring: 'border-rose-500/50', bg: 'bg-rose-500/10 border border-rose-500/20', text: 'text-rose-500', dot: 'bg-rose-500' }
};

const FlowParticle = ({ active, themeColor = 'violet' }) => (
  <AnimatePresence>
    {active && (
      <motion.div
        className={`absolute left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full ${themeColor === 'blue' ? 'bg-blue-400 shadow-[0_0_6px_rgba(59,130,246,0.8)]' : 'bg-purple-400 shadow-[0_0_6px_rgba(167,139,250,0.8)]'}`}
        initial={{ top: 0, opacity: 0 }}
        animate={{ top: '100%', opacity: [0, 1, 1, 0] }}
        exit={{ opacity: 0 }}
        transition={{ duration: 1.2, ease: 'linear', repeat: Infinity }}
      />
    )}
  </AnimatePresence>
);

const Connector = ({ active, themeColor = 'violet' }) => (
  <div className="relative w-8 flex justify-center animate-fadeIn" style={{ height: 24 }}>
    <div
      className={`w-0.5 h-full ${active ? (themeColor === 'blue' ? 'bg-blue-500/20' : 'bg-purple-500/20') : 'bg-slate-800/40'}`}
    />
    <FlowParticle active={active} themeColor={themeColor} />
  </div>
);

const getActiveStepIndex = (phase) => {
  if (!phase) return 0;
  const p = phase.toLowerCase();
  if (p.includes("complete") || p.includes("finish") || p.includes("success") || p.includes("pipeline complete")) return 6;
  if (p.includes("audit") || p.includes("validator") || p.includes("auditor") || p.includes("execution auditor")) return 5;
  if (p.includes("correct") || p.includes("repair") || p.includes("corrector") || p.includes("correction")) return 4;
  if (p.includes("generation") || p.includes("synthesis") || p.includes("sql") || p.includes("sql synthesis")) return 3;
  if (p.includes("route") || p.includes("strategy") || p.includes("dialect") || p.includes("router")) return 2;
  // Distinguish schema linking from context pruning
  if (p.includes("contextpruner") || p.includes("context pruning") || p.includes("token budget") || p.includes("budget")) return 1;
  if (p.includes("schemalinker") || p.includes("schema linker") || p.includes("schema linking") || p.includes("surgical schema") || p.includes("database grounding")) return 0;
  if (p.includes("initialize") || p.includes("initializing")) return 0;
  return 0;
};

const ArchitectureFlow = ({ diagnoseData, currentStatus, themeColor = 'violet' }) => {
  const [expandedNode, setExpandedNode] = useState(null);
  const consoleBodyRef = useRef(null);
  const liveSteps = diagnoseData?.live_steps || [];

  useEffect(() => {
    if (consoleBodyRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = consoleBodyRef.current;
      const isNearBottom = scrollHeight - scrollTop - clientHeight < 60;
      if (liveSteps.length <= 1 || isNearBottom) {
        consoleBodyRef.current.scrollTop = scrollHeight;
      }
    }
  }, [liveSteps]);

  const steps = [
    {
      id: 'schema_linking',
      label: 'Schema Linker & Database Grounding',
      desc: 'Surgically maps question elements to target database schemas, resolving table joins and identifying columns.',
      icon: Link2,
      scorecardKey: 'Schema Linker'
    },
    {
      id: 'context_pruning',
      label: 'Context Pruners & Token Budgets',
      desc: 'Filters down schema structures to a minimal active context, keeping within LLM context tokens limit.',
      icon: Layers,
      scorecardKey: 'Context Pruners'
    },
    {
      id: 'strategy_routing',
      label: 'Strategy Router & Dialect Planner',
      desc: 'Dynamically routes execution plans and adapts SQL structures based on the target database engine.',
      icon: Cpu,
      scorecardKey: null
    },
    {
      id: 'sql_generation',
      label: 'SQL Synthesis & Agent Generator',
      desc: 'Drafts candidate SQL queries, validating casing, names, and table qualifiers.',
      icon: FileCode,
      scorecardKey: 'SQL Generator'
    },
    {
      id: 'self_correction',
      label: 'Self-Correction & Syntax Validator',
      desc: 'Executes candidate SQL against the target database, trapping errors, and running repair iterations.',
      icon: RefreshCw,
      scorecardKey: 'Self Corrector'
    },
    {
      id: 'result_auditing',
      label: 'Result Auditor & Accuracy Validator',
      desc: 'Compares resulting output row-counts and cell contents against gold-standard evaluation bounds.',
      icon: ShieldCheck,
      scorecardKey: 'Data IQ Auditor'
    }
  ];

  const isRunning = currentStatus === 'running';
  const hasData = diagnoseData && (diagnoseData.agent_scorecard || (diagnoseData.live_steps && diagnoseData.live_steps.length > 0));

  return (
    <div className="space-y-4 select-text animate-fadeIn">
      <div className="flex items-center gap-2 mb-2 pb-2 border-b border-[#1b1b26]/50">
        <Sparkles className={`w-4 h-4 ${themeColor === 'blue' ? 'text-blue-400' : 'text-purple-400'} animate-pulse`} />
        <span className="text-[11px] font-bold text-slate-400 uppercase tracking-widest font-mono">
          Agent Pipeline Telemetry
        </span>
      </div>

      {!hasData && !isRunning ? (
        <div className="bg-[#0e0e14] border border-[#20202d]/50 p-6 rounded-xl text-center space-y-2">
          <Sliders className="w-8 h-8 text-slate-500 mx-auto opacity-40 animate-pulse" />
          <p className="text-xs font-mono text-slate-400 font-bold">No Telemetry Logs Recorded Yet</p>
          <p className="text-[10px] text-slate-600 font-sans leading-normal">
            This query hasn't been executed in the active session. Run the query probe to capture multi-agent traces and view the live architecture flow.
          </p>
        </div>
      ) : (
        <div className="relative pl-2 space-y-0">
          {steps.map((step, idx) => {
            let status = 'pending';
            let message = step.desc;
            let metrics = '';

            if (isRunning) {
              const activeIndex = getActiveStepIndex(diagnoseData?.current_phase);
              if (idx < activeIndex) {
                status = 'success';
              } else if (idx === activeIndex) {
                status = 'running';
              } else {
                status = 'pending';
              }
            } else if (hasData) {
              if (diagnoseData.agent_scorecard) {
                if (step.scorecardKey) {
                  const card = diagnoseData.agent_scorecard[step.scorecardKey];
                  if (card) {
                    status = card.status;
                    message = card.message || step.desc;
                    metrics = card.metrics || '';
                  }
                } else if (step.id === 'strategy_routing') {
                  const sqlCard = diagnoseData.agent_scorecard['SQL Generator'];
                  status = sqlCard ? (sqlCard.status === 'error' ? 'warning' : 'success') : 'success';
                  message = 'Engine-level SQL grammar and execution plans verified successfully.';
                  metrics = '1 plan';
                }
              } else {
                const activeIndex = getActiveStepIndex(diagnoseData?.current_phase);
                const isErr = currentStatus === 'error' || (diagnoseData?.current_phase && diagnoseData.current_phase.toLowerCase().includes('error'));
                if (idx < activeIndex) {
                  status = 'success';
                } else if (idx === activeIndex) {
                  status = isErr ? 'error' : 'success';
                } else {
                  status = isErr ? 'pending' : 'success';
                }
              }
            }

            const IconComp = step.icon;
            const style = TELEMETRY_STATUS_STYLE[status] || TELEMETRY_STATUS_STYLE.pending;
            const isExpanded = expandedNode === step.id;

            return (
              <div key={step.id} className="flex flex-col">
                <div className="flex items-start gap-4">
                  <div className="flex flex-col items-center shrink-0">
                    <motion.div
                      whileHover={{ scale: 1.05 }}
                      onClick={() => setExpandedNode(isExpanded ? null : step.id)}
                      className={`w-9 h-9 rounded-xl border-2 flex items-center justify-center cursor-pointer transition-all duration-300 ${style.ring} ${style.bg}`}
                    >
                      <IconComp
                        className={`w-4 h-4 transition-colors duration-300 ${style.text} ${status === 'running' ? 'animate-spin' : ''}`}
                      />
                    </motion.div>
                  </div>

                  <div
                    onClick={() => setExpandedNode(isExpanded ? null : step.id)}
                    className={`flex-1 bg-[#0f0f15]/80 border text-left ${isExpanded ? (themeColor === 'blue' ? 'border-blue-500/30' : 'border-purple-500/30') : 'border-[#1b1b26]/50'} hover:border-slate-700/60 p-3 rounded-xl cursor-pointer transition-all duration-200`}
                  >
                    <div className="flex justify-between items-center gap-2">
                      <h4 className="text-xs font-bold font-sans text-slate-200 tracking-tight">
                        {step.label}
                      </h4>
                      <div className="flex items-center gap-1.5 shrink-0">
                        {metrics && (
                          <span className="text-[9px] font-mono font-bold px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 border border-slate-700/30 uppercase shrink-0">
                            {metrics}
                          </span>
                        )}
                        <span className={`text-[9px] font-mono font-extrabold uppercase shrink-0 px-1 py-0.1 rounded ${
                          status === 'success' ? 'bg-emerald-500/10 text-emerald-400' :
                          status === 'warning' ? 'bg-amber-500/10 text-amber-400' :
                          status === 'error' ? 'bg-rose-500/10 text-rose-500' :
                          status === 'running' ? 'bg-blue-500/10 text-blue-400' : 'bg-slate-800 text-slate-500'
                        }`}>
                          {status}
                        </span>
                      </div>
                    </div>

                    <p className="text-[10px] text-slate-400 leading-relaxed font-sans mt-1.5 line-clamp-2 hover:line-clamp-none transition-all font-medium font-sans mt-1.5">
                      {message}
                    </p>

                    <AnimatePresence>
                      {isExpanded && (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: 'auto' }}
                          exit={{ opacity: 0, height: 0 }}
                          className="mt-3 pt-3 border-t border-[#1b1b26]/50 space-y-2 text-[10px]"
                        >
                          <div className="text-slate-500 uppercase tracking-widest font-mono text-[8px]">Agent Trace Analysis</div>
                          <div className="text-slate-300 font-sans leading-normal whitespace-pre-wrap">
                            {step.scorecardKey && diagnoseData?.agent_scorecard ? (
                              `Subsystem Evaluation Scorecard:\n • Status Verification: ${status.toUpperCase()}\n • Metrics Checked: ${metrics || 'None'}\n • Trace Message: ${message}`
                            ) : (
                              `Details:\n • Status Verification: ${status.toUpperCase()}\n • Operational Mode: Dialect Adaptor Active\n • Description: Matches SQL dialects and structural guidelines against targeted schema context mappings.`
                            )}
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </div>

                {idx < steps.length - 1 && (
                  <div className="pl-[18px]">
                    <Connector active={status === 'success' || status === 'warning' || status === 'running'} themeColor={themeColor} />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Live Terminal Console Logs */}
      {liveSteps && liveSteps.length > 0 && (
        <div className="mt-6 space-y-2.5">
          <div className="flex items-center justify-between px-1">
            <span className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-wider">
              Real-time Console Output
            </span>
            {currentStatus === 'running' && (
              <span className="text-[9px] font-mono text-purple-400 animate-pulse flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-ping" />
                Live streaming logs...
              </span>
            )}
          </div>
          <div className="bg-[#040406] border border-[#171722] rounded-xl overflow-hidden shadow-inner flex flex-col font-mono text-[11px] h-60">
            {/* Terminal Top Window Frame */}
            <div className="flex items-center justify-between px-3 py-2 bg-[#0c0c12]/80 border-b border-[#171722]/80 shrink-0">
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-rose-500/80" />
                <div className="w-2.5 h-2.5 rounded-full bg-amber-500/80" />
                <div className="w-2.5 h-2.5 rounded-full bg-emerald-500/80" />
              </div>
              <span className="text-[9px] font-semibold text-slate-500">orchestrator@nquire-agent:~</span>
              <div className="w-12" />
            </div>
            {/* Terminal Body */}
            <div ref={consoleBodyRef} className="flex-1 overflow-y-auto p-4 space-y-2 scrollbar-thin scrollbar-thumb-slate-800 scrollbar-track-transparent">
              {liveSteps.map((st, idx) => {
                let textColor = 'text-slate-300';
                if (st.type === 'success') textColor = 'text-emerald-400';
                else if (st.type === 'warn' || st.type === 'warning') textColor = 'text-amber-400';
                else if (st.type === 'error') textColor = 'text-rose-400';
                else if (st.type === 'start') textColor = 'text-purple-400 font-bold';

                return (
                  <div key={idx} className="flex items-start gap-2 leading-relaxed select-text font-mono text-[10.5px] text-left">
                    <span className="text-slate-600 shrink-0 select-none">[{st.time}]</span>
                    <span className={textColor}>{st.text}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const parseLiveStepsFromMd = (content) => {
  if (!content) return { currentPhase: 'Initializing Agent Orchestrator...', steps: [] };
  const lines = content.split('\n');
  const steps = [];
  let currentPhase = 'Initializing Agent Orchestrator...';
  let corrections = 0;

  // Add the start step
  steps.push({
    time: "00:01",
    type: 'start',
    text: 'Initializing autonomous pipeline container...'
  });

  for (const line of lines) {
    const l_s = line.trim();
    if (l_s.includes("Executing SchemaLinker Module") || l_s.includes("SchemaLinker")) {
      currentPhase = "Surgical Schema Pruning & Column Linker";
      if (!steps.some(s => s.text.includes("SchemaLinker:"))) {
        steps.push({
          time: "00:02",
          type: 'step',
          text: "SchemaLinker: Pruning full schema down to surgical candidate subset."
        });
      }
    } else if (l_s.includes("Executing SQL Generator Module")) {
      currentPhase = "Adaptive FQN SQL Generation";
      if (!steps.some(s => s.text.includes("SQL Generator:"))) {
        steps.push({
          time: "00:03",
          type: 'step',
          text: "SQL Generator: Assembling deterministic joins."
        });
      }
    } else if (l_s.includes("Executing Self-Correction Module") || l_s.includes("Self-Correction")) {
      currentPhase = "Closed-Loop Execution Corrector";
      corrections += 1;
      steps.push({
        time: "00:05",
        type: 'warn',
        text: `Self-Correction: Triggered automated SQL repair loop #${corrections}.`
      });
    } else if (l_s.includes("Executing ResultValidator") || l_s.includes("Data IQ")) {
      currentPhase = "Data IQ Execution Auditor";
      if (!steps.some(s => s.text.includes("Data IQ Auditor:"))) {
        steps.push({
          time: "00:06",
          type: 'step',
          text: "Data IQ Auditor: Probing result grain, NULL density, and unit scale."
        });
      }
    }
  }

  const cleanSteps = [];
  const seenTexts = new Set();
  for (const st of steps) {
    if (!seenTexts.has(st.text)) {
      seenTexts.add(st.text);
      cleanSteps.push(st);
    }
  }

  return { currentPhase, steps: cleanSteps };
};

const DabStudio = ({ onBack, onHome, autoOpenDetails, clearAutoOpenDetails, user, onLogout }) => {
  const [selectedModel, setSelectedModel] = useState(() => localStorage.getItem('dab_settings_model') || 'bedrock/openai.gpt-oss-safeguard-120b');
  const [temperature, setTemperature] = useState(() => Number(localStorage.getItem('dab_settings_temp') || '0.0'));
  const [workers, setWorkers] = useState(() => Number(localStorage.getItem('dab_settings_workers') || '3'));

  useEffect(() => {
    localStorage.setItem('dab_settings_model', selectedModel);
  }, [selectedModel]);

  useEffect(() => {
    localStorage.setItem('dab_settings_temp', String(temperature));
  }, [temperature]);

  useEffect(() => {
    localStorage.setItem('dab_settings_workers', String(workers));
  }, [workers]);

  const [currentView, setCurrentView] = useState(() => {
    return localStorage.getItem('dab_current_view') || 'dashboard';
  });
  const [metrics, setMetrics] = useState(null);
  const [agentAnalytics, setAgentAnalytics] = useState(null);
  const [loadingAgentAnalytics, setLoadingAgentAnalytics] = useState(false);
  const [analyticsSearchQuery, setAnalyticsSearchQuery] = useState('');
  const [databases, setDatabases] = useState([]);
  const [selectedDb, setSelectedDb] = useState(() => {
    return localStorage.getItem('dab_selected_db') || null;
  });
  const [dbResults, setDbResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [dateFilter, setDateFilter] = useState<string>(''); // Default to empty, wait for dates to load
  const [allDates, setAllDates] = useState<{ id: string; label: string; date: string; is_active: boolean }[]>([]);
  const [recentRuns, setRecentRuns] = useState([]);
  const [runningInstances, setRunningInstances] = useState({});
  const [runningDbs, setRunningDbs] = useState({});
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showDateDropdown, setShowDateDropdown] = useState(false);
  const dateDropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dateDropdownRef.current && !dateDropdownRef.current.contains(event.target as Node)) {
        setShowDateDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  // Modals & Drawers
  const [selectedDetails, setSelectedDetails] = useState(null);
  const [detailsTab, setDetailsTab] = useState('sql');
  const [copiedType, setCopiedType] = useState(null);
  const [showMetricModal, setShowMetricModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showRunOptionsModal, setShowRunOptionsModal] = useState(false);
  const [completedSlots, setCompletedSlots] = useState(0);
  const [showSchemaModal, setShowSchemaModal] = useState(false);
  const [schemaLoading, setSchemaLoading] = useState(false);
  const [schemaData, setSchemaData] = useState(null);
  const [selectedSchemaTab, setSelectedSchemaTab] = useState("");
  const [activeMetricFilter, setActiveMetricFilter] = useState('total');
  const [allInstanceResults, setAllInstanceResults] = useState([]);
  const [loadingMetricInstances, setLoadingMetricInstances] = useState(false);
  const [metricSearchQuery, setMetricSearchQuery] = useState('');
  const [showDiagnoseDrawer, setShowDiagnoseDrawer] = useState(false);
  const [diagnoseData, setDiagnoseData] = useState(null);
  const [loadingDiagnose, setLoadingDiagnose] = useState(false);
  const [fixResult, setFixResult] = useState(null);
  const [applyingFix, setApplyingFix] = useState(false);
  const [fixFeedback, setFixFeedback] = useState('');

  // Tickers
  const [isGlobalRunning, setIsGlobalRunning] = useState(false);
  const [globalProgress, setGlobalProgress] = useState({ total: 0, completed: 0 });
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [dabQuip, setDabQuip] = useState("Resolving DBMS environments... 🔬");

  const liveEsRef = useRef(null);
  const animTimerRef = useRef(null);
  const safetyTimeoutRef = useRef(null);
  const logPollRef = useRef(null);
  const logPreRef = useRef(null);
  const selectedDbRef = useRef(selectedDb);
  const rtPollRef = useRef(null);

  const dabMascotQuotes = [
    "Spinning up localized DuckDB nodes... 🦆",
    "Running multi-step logical operations... 🧩",
    "Verifying results with dynamic grading... 🎓",
    "Trapping PostgreSQL connection loops... 🔗",
    "Self-correction repairing query traces... 🛠️",
    "Calculating exact token efficiency indexes... 📊",
    "DBMS dialect alignment complete! 🚀"
  ];

  // Fetch dates on mount — with a 7s global safety net so spinner never gets stuck
  useEffect(() => {
    // Safety: if fetchDates hangs beyond 7s, force dateFilter='all' so the page unblocks
    const safetyFallback = setTimeout(() => {
      setLoading(false);
      setDateFilter(prev => prev || 'all');
    }, 7000);

    fetchDates().finally(() => clearTimeout(safetyFallback));
    fetchDabSubmissions();
    const ticker = setInterval(() => {
      setDabQuip(dabMascotQuotes[Math.floor(Math.random() * dabMascotQuotes.length)]);
    }, 9000);
    return () => { clearInterval(ticker); clearTimeout(safetyFallback); };
  }, []);

  const handleOpenSchemaModal = async (e, dbName) => {
    e.stopPropagation(); // Avoid selecting/navigating the DB list row
    setSchemaLoading(true);
    setShowSchemaModal(true);
    setSchemaData(null);
    setSelectedSchemaTab("");
    try {
      const res = await axios.get(`${API_BASE}/dab/schema/${dbName}`);
      setSchemaData(res.data);
      if (res.data?.schema) {
        const clients = Object.keys(res.data.schema);
        if (clients.length > 0) {
          setSelectedSchemaTab(clients[0]);
        }
      }
    } catch (err) {
      console.error("Failed to load schema info", err);
    } finally {
      setSchemaLoading(false);
    }
  };

  // Sync state changes with localStorage
  useEffect(() => {
    localStorage.setItem('dab_current_view', currentView);
  }, [currentView]);

  useEffect(() => {
    if (selectedDb) {
      localStorage.setItem('dab_selected_db', selectedDb);
    } else {
      localStorage.removeItem('dab_selected_db');
    }
  }, [selectedDb]);

  // Fetch metrics and databases when date filter changes
  useEffect(() => {
    fetchInitialData();
    if (selectedDbRef.current) {
      handleRefresh(selectedDbRef.current);
    }
  }, [dateFilter]);

  // Sync run/evaluate tickers — runs every 5 s to keep frontend in sync with backend
  useEffect(() => {
    let isMounted = true;
    let timer: any;
    const loop = async () => {
      if (!isMounted) return;
      await checkGlobalRunStatus();
      if (isMounted && currentView === 'agents') {
        await fetchAgentAnalytics(false);
      }
      if (isMounted) timer = setTimeout(loop, 5000);
    };
    loop();
    return () => { isMounted = false; clearTimeout(timer); };
  }, [dateFilter, currentView]);

  // Auto-open details when navigated deep-link from global tasks panel
  useEffect(() => {
    if (autoOpenDetails && autoOpenDetails.project === 'dab') {
      const { db, id } = autoOpenDetails;
      setSelectedDb(db);
      setCurrentView('database');
      const qId = id.split('_q')[1] || id.replace(/\D/g, '');
      fetchInstanceDetails(db, qId);
      clearAutoOpenDetails();
    }
  }, [autoOpenDetails]);

  useEffect(() => {
    return () => {
      liveEsRef.current?.close();
      clearInterval(animTimerRef.current);
      clearTimeout(safetyTimeoutRef.current);
      clearTimeout(logPollRef.current);
      clearTimeout(rtPollRef.current);
    };
  }, []);

  // Keep ref in sync so closures always see the latest selectedDb
  useEffect(() => {
    selectedDbRef.current = selectedDb;
  }, [selectedDb]);

  // Real-time probe card + metrics refresh while any instance is running
  useEffect(() => {
    clearTimeout(rtPollRef.current);
    const hasRunning = Object.keys(runningInstances).length > 0 || isGlobalRunning;
    if (!hasRunning) return;
    
    let isMounted = true;
    const tick = async () => {
      if (!isMounted) return;
      const db = selectedDbRef.current;
      if (db) {
        try {
          const res = await axios.get(`${API_BASE}/dab/queries/db/${db}?run_id=${dateFilter}`, { timeout: 5000 });
          setDbResults(res.data);
        } catch (_) {}
      }
      try {
        const [m, dbs, recent] = await Promise.all([
          axios.get(`${API_BASE}/dab/metrics?run_id=${dateFilter}`, { timeout: 15000 }),
          axios.get(`${API_BASE}/dab/databases?run_id=${dateFilter}`, { timeout: 15000 }),
          axios.get(`${API_BASE}/dab/results/recent?limit=12&run_id=${dateFilter}`, { timeout: 15000 }),
        ]);
        setMetrics(m.data);
        setDatabases(dbs.data);
        setRecentRuns(recent.data);
      } catch (_) {}
      
      if (isMounted) rtPollRef.current = setTimeout(tick, 3000) as any;
    };
    tick();
    return () => { isMounted = false; clearTimeout(rtPollRef.current); };
  }, [Object.keys(runningInstances).length, isGlobalRunning, dateFilter]);

  // Poll /dab/results for live log content when the log tab is open during a run
  useEffect(() => {
    clearTimeout(logPollRef.current);
    if (detailsTab !== 'log' || !selectedDetails || selectedDetails.status !== 'running') return;
    const { db, id } = selectedDetails;
    const qNum = id.replace(/\D/g, '');
    
    let isMounted = true;
    const poll = async () => {
      if (!isMounted) return;
      try {
        const res = await axios.get(`${API_BASE}/dab/results/${db}/${qNum}?run_id=${dateFilter}`);
        if (res.data?.log_content) {
          setSelectedDetails(prev => {
            if (!prev || prev.id !== id) return prev;
            return { ...prev, logContent: res.data.log_content };
          });
        }
      } catch (_) {}
      if (isMounted) logPollRef.current = setTimeout(poll, 2500) as any;
    };
    poll();
    return () => { isMounted = false; clearTimeout(logPollRef.current); };
  }, [detailsTab, selectedDetails?.id, selectedDetails?.status, dateFilter]);

  // Auto-scroll log to bottom when content updates during a run
  useEffect(() => {
    if (logPreRef.current && selectedDetails?.status === 'running') {
      logPreRef.current.scrollTop = logPreRef.current.scrollHeight;
    }
  }, [selectedDetails?.logContent]);

  // SSE for instances opened via DIAGNOSE (not via handleRunSingle which manages its own stream)
  useEffect(() => {
    if (!selectedDetails || selectedDetails.status !== 'running') return;
    // handleRunSingle already opened liveEsRef — don't double-connect
    if (liveEsRef.current && liveEsRef.current.readyState !== EventSource.CLOSED) return;

    const db = selectedDetails.db;
    const id = selectedDetails.id;
    const qId = id.replace(/\D/g, '');
    const es = new EventSource(`${API_BASE}/dab/stream/${db}/${qId}`);

    es.onmessage = (e) => {
      const data = JSON.parse(e.data);
      setSelectedDetails(prev => {
        if (!prev || prev.id !== id) return prev;
        return {
          ...prev,
          diagnoseData: {
            ...prev.diagnoseData,
            live_steps: data.live_steps,
            current_phase: data.current_phase,
          }
        };
      });
    };

    es.addEventListener('done', () => {
      es.close();
      setRunningInstances(prev => { const next = { ...prev }; delete next[`${db}_q${qId}`]; return next; });
      setTimeout(() => {
        fetchInstanceDetails(db, qId);
        handleRefresh(db);
      }, 500);
    });

    es.onerror = () => es.close();
    return () => es.close();
  }, [selectedDetails?.id, selectedDetails?.status]);

  const fetchDates = async () => {
    try {
      // 6s timeout so a hung backend doesn't freeze the UI forever
      const res = await axios.get(`${API_BASE}/dab/runs`, { timeout: 6000 });
      const dates = res.data || [];

      // Always inject a "Live" option at position 1 so active runs are always visible
      const liveEntry = { id: 'live', label: '⚡ Live View', date: '', is_active: true };
      const withLive = [
        dates[0] || { id: 'all', label: 'All Runs', date: 'All', is_active: false },
        liveEntry,
        ...dates.slice(1),
      ];
      setAllDates(withLive);

      if (dateFilter === '') {
        // Check if backend flagged an actively running archived run
        const activeRun = dates.find(r => r.is_active && r.id !== 'all');
        if (activeRun) {
          setDateFilter(activeRun.id);
        } else {
          // Default to Live — always shows whatever is currently being written
          setDateFilter('live');
        }
      }
    } catch (err) {
      console.error("Failed to load execution dates", err);
      // On failure, still inject Live option so user can try
      const liveEntry = { id: 'live', label: '⚡ Live View', date: '', is_active: true };
      setAllDates([
        { id: 'all', label: 'All Runs', date: 'All', is_active: false },
        liveEntry,
      ]);
      if (dateFilter === '') setDateFilter('live');
    }
  };

  const fetchDabSubmissions = async () => { /* leaderboard removed */ };

  const fetchInitialData = async (showSpinner = true, force = false, forceDate?: string) => {
    const activeDate = forceDate || dateFilter;
    if (!activeDate) return; // Don't fetch until date filter is determined
    
    if (showSpinner) setLoading(true);
    // Hard timeout — if any call hangs longer than 10 s, clear the spinner anyway
    const safetyTimer = showSpinner ? setTimeout(() => setLoading(false), 10000) : null;
    try {
      const OPT = { timeout: 12000 };
      const [metricsRes, dbsRes, recentRes] = await Promise.all([
        axios.get(`${API_BASE}/dab/metrics?run_id=${activeDate}${force ? '&force=true' : ''}`, OPT).catch(() => ({ data: null })),
        axios.get(`${API_BASE}/dab/databases?run_id=${activeDate}${force ? '&force=true' : ''}`, OPT).catch(() => ({ data: [] })),
        axios.get(`${API_BASE}/dab/results/recent?limit=12&run_id=${activeDate}${force ? '&force=true' : ''}`, OPT).catch(() => ({ data: [] })),
      ]);
      if (metricsRes.data) setMetrics(metricsRes.data);
      if (dbsRes.data) setDatabases(dbsRes.data);
      if (recentRes.data) setRecentRuns(recentRes.data);
      fetchAgentAnalytics(false, activeDate);
    } catch (err) {
      console.error("Failed to load initial DAB metrics", err);
    } finally {
      clearTimeout(safetyTimer);
      if (showSpinner) setLoading(false);
    }
  };

  const fetchAgentAnalytics = async (showSpinner = true, forceDate?: string) => {
    const activeDate = forceDate || dateFilter;
    if (!activeDate) return;
    if (showSpinner) setLoadingAgentAnalytics(true);
    try {
      const res = await axios.get(`${API_BASE}/dab/agent_analytics?run_id=${activeDate}`);
      if (res.data) setAgentAnalytics(res.data);
    } catch (err) {
      console.error("Failed to load agent analytics", err);
    } finally {
      if (showSpinner) setLoadingAgentAnalytics(false);
    }
  };

  const checkGlobalRunStatus = async () => {
    // If looking at a historical run, it should be completely static (no active polling)
    const today = new Date().toISOString().split('T')[0];
    // Don't early exit if dateFilter is still loading (empty string)
    if (dateFilter && dateFilter.startsWith('run_')) {
        setIsGlobalRunning(false);
        setRunningInstances({});
        return;
    }

    try {
      const res = await axios.get(`${API_BASE}/dab/status`, { timeout: 4000 });
      const backendRunning = res.data.running || []; // e.g. ["deps_dev_v1_q1"]
      const count = res.data.count || 0;

      // Reconcile runningInstances with backend truth
      setRunningInstances(prev => {
        const next = { ...prev };
        // Add any that backend says are running but frontend doesn't know about
        backendRunning.forEach(key => { next[key] = true; });
        // Remove any that backend says are finished
        Object.keys(next).forEach(key => {
          if (!backendRunning.includes(key)) delete next[key];
        });
        return next;
      });

      setIsGlobalRunning(prev => {
        if (prev && count === 0) {
          // Tasks just completed — give eval files 2 s to flush, then full refresh
          setTimeout(() => handleRefresh(selectedDbRef.current), 2000);
        }
        return count > 0;
      });
      setGlobalProgress({ total: res.data.total || 0, completed: res.data.completed || 0 });
    } catch (_) {}
  };

  const fetchResults = async (dbName) => {
    setSelectedDb(dbName);
    setCurrentView('database');
    try {
      const res = await axios.get(`${API_BASE}/dab/queries/db/${dbName}?run_id=${dateFilter}`, { timeout: 8000 });
      setDbResults(res.data);
      
      // Auto-populate and sync runningInstances from backend statuses
      setRunningInstances(prev => {
        const next = { ...prev };
        res.data.forEach(q => {
          if (q.status === 'running') {
            next[q.id] = true;
          } else {
            delete next[q.id];
          }
        });
        return next;
      });
    } catch (err) {
      console.error(`Failed to load results for dataset ${dbName}`, err);
    }
  };

  const handleRefresh = async (db?: any, forceDate?: string) => {
    const target = typeof db === 'string' ? db : selectedDbRef.current;
    const activeDate = forceDate || dateFilter;
    setIsRefreshing(true);
    try {
    await checkGlobalRunStatus();
    await fetchDates();
    await fetchInitialData(false, true, forceDate);
    await fetchAgentAnalytics(false, activeDate);
    if (target) {
      try {
        const res = await axios.get(`${API_BASE}/dab/queries/db/${target}?run_id=${activeDate}`);
        setDbResults(res.data);
        setRunningInstances(prev => {
          const next = { ...prev };
          res.data.forEach(q => {
            if (q.status === 'running') next[q.id] = true;
            else delete next[q.id];
          });
          return next;
        });
      } catch (_) {}
    }
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleDeleteRun = () => {
    setShowDeleteModal(true);
  };

  const confirmDeleteRun = async () => {
    setIsDeleting(true);
    try {
      const currentRunLabel = allDates.find(r => r.id === dateFilter)?.label || dateFilter;
      await axios.delete(`${API_BASE}/dab/runs/${dateFilter}`);
      
      const res = await axios.get(`${API_BASE}/dab/runs`);
      const newDates = res.data || [];
      setAllDates(newDates);
      
      let fallbackDate = 'all';
      if (newDates.length > 0) {
        const hasLive = newDates.some(r => r.id === 'live');
        fallbackDate = hasLive ? 'live' : newDates[0].id;
      }
      
      // Optimistically clear current state to prevent flashing stale data
      setMetrics(null);
      setDbResults([]);
      setRecentRuns([]);
      
      setDateFilter(fallbackDate);
      setShowDeleteModal(false);
      
      // Manually trigger handleRefresh with the explicit new date
      await handleRefresh(selectedDbRef.current, fallbackDate);
      setToast({ message: `Run "${currentRunLabel}" deleted successfully.`, type: 'success' });
    } catch (err: any) {
      console.error("Failed to delete DAB run", err);
      const errMsg = err.response?.data?.detail || err.message || 'Failed to delete DAB run';
      setToast({ message: `Failed to delete run: ${errMsg}`, type: 'error' });
    } finally {
      setIsDeleting(false);
    }
  };

  const handleRunSingle = async (dataset, instanceId) => {
    const qkey = `${dataset}_q${instanceId}`;
    setRunningInstances(prev => ({ ...prev, [qkey]: true }));
    setSelectedDetails({
      id: `query${instanceId}`,
      db: dataset,
      status: 'running',
      diagnoseData: {
        current_phase: 'Initializing Agent Orchestrator...',
        live_steps: []
      }
    });
    setDetailsTab('flow');

    // Fire the run — backend returns immediately (async thread pool)
    const runStart = Date.now();
    axios.post(`${API_BASE}/dab/run/${dataset}/${instanceId}`, {
      model: selectedModel,
      temperature: temperature
    })
      .catch(err => {
        console.error("Failed to trigger single DAB run", err);
        setRunningInstances(prev => { const next = { ...prev }; delete next[qkey]; return next; });
        setSelectedDetails(prev => prev && prev.id === `query${instanceId}` ? { ...prev, status: 'error' } : prev);
      });

    // Animated progress steps shown before log file appears
    const ANIM_STEPS = [
      { time: "00:01", type: "start", text: "Initializing autonomous pipeline container..." },
      { time: "00:02", type: "step",  text: "SchemaLinker: Pruning full schema to surgical candidate subset." },
      { time: "00:03", type: "step",  text: "ContextPruner: Eliminating unrelated schema structures." },
      { time: "00:04", type: "step",  text: "SQLGenerator: Assembling deterministic joins and clauses." },
    ];
    let animIdx = 0;
    animTimerRef.current = setInterval(() => {
      animIdx++;
      if (animIdx < ANIM_STEPS.length) {
        setSelectedDetails(prev => {
          if (!prev || prev.id !== `query${instanceId}`) return prev;
          const existingSteps = prev.diagnoseData?.live_steps || [];
          if (existingSteps.length <= animIdx) {
            return {
              ...prev,
              diagnoseData: {
                ...prev.diagnoseData,
                current_phase: ANIM_STEPS[animIdx].text,
                live_steps: ANIM_STEPS.slice(0, animIdx + 1),
              }
            };
          }
          return prev;
        });
      } else {
        clearInterval(animTimerRef.current);
      }
    }, 3500);

    // SSE stream replaces the 2 s double-poll (livelog + results simultaneously).
    // The backend pushes each new step the moment it appears in the log file (~800 ms
    // server-side check interval), so perceived latency drops from 2 s → <1 s.
    // Results are fetched exactly once, on completion — not on every tick.
    liveEsRef.current = new EventSource(`${API_BASE}/dab/stream/${dataset}/${instanceId}`);

    liveEsRef.current.onmessage = (e) => {
      const liveData = JSON.parse(e.data);
      clearInterval(animTimerRef.current);
      setSelectedDetails(prev => {
        if (!prev || prev.id !== `query${instanceId}`) return prev;
        return {
          ...prev,
          diagnoseData: {
            ...prev.diagnoseData,
            live_steps: liveData.live_steps,
            current_phase: liveData.current_phase,
          }
        };
      });
    };

    liveEsRef.current.addEventListener('done', async () => {
      liveEsRef.current?.close();
      liveEsRef.current = null;
      clearInterval(animTimerRef.current);
      clearTimeout(safetyTimeoutRef.current);
      setRunningInstances(prev => { const next = { ...prev }; delete next[qkey]; return next; });

      try {
        const [finalDiag, finalResult] = await Promise.all([
          axios.get(`${API_BASE}/diagnose/dab/${dataset}/query${instanceId}`).catch(() => ({ data: null })),
          axios.get(`${API_BASE}/dab/results/${dataset}/${instanceId}?run_id=${dateFilter}`).catch(() => ({ data: null })),
        ]);
        setSelectedDetails(prev => prev && prev.id === `query${instanceId}`
          ? {
              ...prev,
              status: finalResult.data?.status || 'done',
              diagnoseData: finalDiag.data || prev.diagnoseData,
              logContent: finalResult.data?.log_content || prev.logContent,
              sqlContent: finalResult.data?.sql_content || prev.sqlContent,
              csvHeaders: finalResult.data?.csv_headers || prev.csvHeaders,
              csvData: finalResult.data?.csv_data || prev.csvData,
              agentAnswer: finalResult.data?.agent_answer || prev.agentAnswer,
            }
          : prev
        );
      } catch (_) {}
      handleRefresh(dataset);
    });

    liveEsRef.current.onerror = () => {
      liveEsRef.current?.close();
      liveEsRef.current = null;
      clearInterval(animTimerRef.current);
      clearTimeout(safetyTimeoutRef.current);
    };

    safetyTimeoutRef.current = setTimeout(() => {
      liveEsRef.current?.close();
      liveEsRef.current = null;
      clearInterval(animTimerRef.current);
      setRunningInstances(prev => { const next = { ...prev }; delete next[qkey]; return next; });
      handleRefresh(dataset);
    }, 30 * 60 * 1000);
  };

  const handleRunDb = async (dbName) => {
    setRunningDbs(prev => ({ ...prev, [dbName]: true }));
    try {
      await axios.post(`${API_BASE}/dab/run_all`, {
        dataset_scope: dbName
      });
      setTimeout(handleRefresh, 1500);
    } catch (err) {
      console.error(`Failed to run pipeline for dataset ${dbName}`, err);
    } finally {
      setRunningDbs(prev => ({ ...prev, [dbName]: false }));
    }
  };

  const triggerGlobalRun = async (mode: 'fresh' | 'continue' = 'fresh') => {
    try {
      setIsGlobalRunning(true);
      if (mode === 'fresh') {
        // Optimistically wipe dashboard metrics and database progress
        setMetrics({ total_queries: 0, evaluated: 0, passed: 0, failed: 0, pass_at_1_pct: '0.0%', avg_latency: '0.0s', avg_tokens_per_agent: '0 tokens', total_cost: '$0.0000' });
        setDbResults([]);
        setAllInstanceResults([]);
        setDatabases(prev => prev.map(db => ({ ...db, results_count: 0, error_count: 0, status: 'pending' })));
      }
      
      const today = new Date().toISOString().split('T')[0];
      const getRunDateStr = (f) => {
        if (f && f.startsWith('run_')) {
          const parts = f.split('_')[1];
          return `${parts.slice(0, 4)}-${parts.slice(4, 6)}-${parts.slice(6, 8)}`;
        }
        return today;
      };
      const targetDate = getRunDateStr(dateFilter);
      
      const runIdToPass = dateFilter && dateFilter.startsWith('run_') ? dateFilter : undefined;
      const payload = { 
        force_rerun: true, 
        workers: workers, 
        mode, 
        date: targetDate,
        run_id: runIdToPass,
        model: selectedModel,
        temperature: temperature
      };
      await axios.post(`${API_BASE}/dab/run_all`, payload);
      
      if (mode === 'fresh') {
        setDateFilter('live');
        fetchDates();
      }
      
      setTimeout(handleRefresh, 1500);
    } catch (err) {
      console.error("Failed to trigger global DAB run", err);
    }
  };

  const handleRunAllClick = async () => {
    try {
      const res = await axios.get(`${API_BASE}/dab/metrics?run_id=live`);
      const completedSlotsCount = res.data?.total_run_slots || 0;
      if (completedSlotsCount > 0) {
        setCompletedSlots(completedSlotsCount);
        setShowRunOptionsModal(true);
      } else {
        triggerGlobalRun('fresh');
      }
    } catch (err) {
      console.error("Failed to check existing runs", err);
      triggerGlobalRun('fresh');
    }
  };

  const handleStopGlobalRun = async () => {
    try {
      await axios.post(`${API_BASE}/dab/stop`);
      setTimeout(handleRefresh, 1000);
    } catch (err) {
      console.error("Failed to stop DAB run", err);
    }
  };


  const handleOpenMetricModal = async (filter) => {
    setActiveMetricFilter(filter);
    setShowMetricModal(true);
    setLoadingMetricInstances(true);
    try {
      const res = await axios.get(`${API_BASE}/dab/queries?run_id=${dateFilter}`);
      setAllInstanceResults(res.data.map(inst => ({
        id: inst.instance_id,
        db: inst.dataset,
        status: inst.status,
        gold_status: inst.status === 'passed' ? 'gold_pass' : 'gold_fail',
        latency: inst.latency || 0,
        corrections: 0
      })));
    } catch (err) {
      console.error("Failed to load instance list", err);
    } finally {
      setLoadingMetricInstances(false);
    }
  };

  const fetchInstanceDetailsFromModal = async (dbName, instanceId) => {
    setShowMetricModal(false);
    const qId = instanceId.split('_q')[1] || instanceId.replace(/\D/g, '');
    fetchInstanceDetails(dbName, qId);
  };

  const fetchInstanceDetails = async (dbName, queryId, question = null) => {
    const qkey = `${dbName}_q${queryId}`;
    const isCurrentlyRunning = runningInstances[qkey];
    setSelectedDetails({
      id: `query${queryId}`,
      db: dbName,
      question,
      status: isCurrentlyRunning ? 'running' : 'idle',
      diagnoseData: isCurrentlyRunning ? { current_phase: 'Initializing Agent Orchestrator...', live_steps: [] } : null
    });
    setDetailsTab('flow');

    if (isCurrentlyRunning) {
      setLoadingDetails(false);
      return;
    }

    setLoadingDetails(true);
    try {
      const [detailsRes, diagnoseRes] = await Promise.all([
        axios.get(`${API_BASE}/dab/results/${dbName}/${queryId}?run_id=${dateFilter}`),
        axios.get(`${API_BASE}/diagnose/dab/${dbName}/query${queryId}?run_id=${dateFilter}`).catch(err => {
          console.error("Failed to fetch diagnostics for details", err);
          return { data: null };
        })
      ]);
      
      const backendStatus = detailsRes.data?.status;
      const isBackendRunning = backendStatus === 'running' || backendStatus === 'pending';

      if (isBackendRunning) {
        setRunningInstances(prev => ({ ...prev, [qkey]: true }));
      }

      setSelectedDetails(prev => ({
        ...prev,
        status: isBackendRunning ? 'running' : 'idle',
        question: prev.question || detailsRes.data.question || null,
        logContent: detailsRes.data.log_content,
        sqlContent: detailsRes.data.sql_content,
        csvHeaders: detailsRes.data.csv_headers,
        csvData: detailsRes.data.csv_data,
        agentAnswer: detailsRes.data.agent_answer,
        complexity: "Standard",
        complexity_type: "Standard",
        complexity_score: 0.2,
        diagnoseData: isBackendRunning 
          ? { current_phase: 'Resuming live telemetry...', live_steps: [] } 
          : diagnoseRes.data
      }));
    } catch (err) {
      console.error("Failed to load run details", err);
    } finally {
      setLoadingDetails(false);
    }
  };

  const handleCardClick = (dbName, queryId) => {
    if (window.getSelection() && window.getSelection().toString().trim() !== '') {
      return; // Ignore click if user is selecting text
    }
    fetchInstanceDetails(dbName, queryId);
  };

  const handleCopy = (text, type) => {
    navigator.clipboard.writeText(text);
    setCopiedType(type);
    setTimeout(() => setCopiedType(null), 2000);
  };

  const handleDiagnose = async (dbName, queryId) => {
    setLoadingDiagnose(true);
    setShowDiagnoseDrawer(true);
    setDiagnoseData(null);
    setFixResult(null);
    setFixFeedback('');
    try {
      const res = await axios.get(`${API_BASE}/diagnose/dab/${dbName}/query${queryId}?run_id=${dateFilter}`);
      setDiagnoseData(res.data);
    } catch (err) {
      console.error("Failed to run diagnosis", err);
    } finally {
      setLoadingDiagnose(false);
    }
  };

  const triggerFixIssues = async () => {
    if (!diagnoseData) return;
    setApplyingFix(true);
    setFixResult(null);
    setFixFeedback('');
    try {
      const dataset = selectedDb;
      const qId = diagnoseData.instance_id.replace('query', '');
      const res = await axios.post(`${API_BASE}/fix_issues/dab/${dataset}/query${qId}`);
      setFixResult(res.data);
    } catch (err) {
      console.error("AI correction failed", err);
      setFixFeedback('Correction error occurred.');
    } finally {
      setApplyingFix(false);
    }
  };

  const acceptFix = async () => {
    if (!fixResult || !diagnoseData) return;
    setApplyingFix(true);
    try {
      const dataset = selectedDb;
      const qId = diagnoseData.instance_id.replace('query', '');
      const res = await axios.post(`${API_BASE}/accept_fix/dab/${dataset}/query${qId}`, {
        corrected_sql: fixResult.corrected_sql,
        reasoning: fixResult.reasoning,
        verification: fixResult.verification,
        temp_id: fixResult.temp_id,
        modifications: fixResult.modifications,
      });
      if (res.data.success) {
        setFixFeedback("Success: Correction accepted and written to database results.");
        setTimeout(() => {
          setShowDiagnoseDrawer(false);
          handleRefresh();
        }, 1500);
      }
    } catch (err) {
      console.error("Failed to accept fix", err);
      setFixFeedback("Failed to save correction.");
    } finally {
      setApplyingFix(false);
    }
  };

  const rejectFix = async () => {
    if (!fixResult || !diagnoseData) return;
    setApplyingFix(true);
    try {
      const dataset = selectedDb;
      const qId = diagnoseData.instance_id.replace('query', '');
      await axios.post(`${API_BASE}/reject_fix/dab/${dataset}/query${qId}`, {
        temp_id: fixResult.temp_id,
      });
      setFixFeedback("Fix rejected. Speculative sandbox cleared.");
      setFixResult(null);
    } catch (err) {
      console.error("Failed to reject fix", err);
    } finally {
      setApplyingFix(false);
    }
  };

  const getStatusIcon = (status) => {
    if (status === 'passed' || status === 'success') return <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />;
    if (status === 'empty') return <Activity className="w-4 h-4 text-amber-400 shrink-0" />;
    if (status === 'failed' || status === 'error') return <XCircle className="w-4 h-4 text-rose-500 shrink-0" />;
    if (status === 'running') return <Activity className="w-4 h-4 text-blue-400 animate-spin shrink-0" />;
    return <Layers className="w-4 h-4 text-slate-500 shrink-0" />;
  };

  const filteredDatabases = databases.filter(db =>
    db.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const renderAgentAnalytics = () => {
    if (loadingAgentAnalytics && !agentAnalytics) {
      return (
        <div className="h-[50vh] flex flex-col items-center justify-center gap-3 text-purple-400 font-mono animate-pulse">
          <Activity className="w-10 h-10 animate-spin" />
          <p className="text-sm font-black">Compiling Agent performance scores from logs...</p>
        </div>
      );
    }

    if (!agentAnalytics || agentAnalytics.queries.length === 0) {
      return (
        <div className="py-24 text-center border border-dashed border-[#231d36] rounded-2xl bg-[#090812] max-w-2xl mx-auto flex flex-col items-center gap-4 animate-fadeIn">
          <Cpu className="w-12 h-12 text-slate-500 stroke-1" />
          <p className="text-sm text-slate-400 font-mono font-bold uppercase tracking-wider">No Analytics Data Available</p>
          <p className="text-xs text-slate-500 font-mono max-w-sm">
            Ensure you have run evaluations for the selected date filter. The agent analytics are parsed live from execution logs.
          </p>
          <button
            onClick={() => handleRefresh()}
            className="mt-2 px-4 py-2 rounded-lg font-mono font-bold text-xs bg-purple-600/20 hover:bg-purple-600/30 text-purple-400 border border-purple-500/20 shadow-md transition-all flex items-center gap-1.5"
          >
            <RefreshCw className="w-3.5 h-3.5" /> REFRESH
          </button>
        </div>
      );
    }

    const { avg_scores, difficulty_metrics, queries } = agentAnalytics;
    
    // Calculate global average score
    const totalScores: number = (Object.values(avg_scores) as number[]).reduce((acc: number, val: number) => acc + val, 0);
    const globalAvgScore = Math.round(totalScores / Object.keys(avg_scores).length);

    // Filtered queries
    const filteredQueries = queries.filter(q => 
      q.id.toLowerCase().includes(analyticsSearchQuery.toLowerCase()) ||
      q.dataset.toLowerCase().includes(analyticsSearchQuery.toLowerCase()) ||
      q.question.toLowerCase().includes(analyticsSearchQuery.toLowerCase())
    );

    const agentScoresData = [
      { name: 'Schema Linker', score: avg_scores.schema_linker, color: '#3b82f6' },
      { name: 'SQL Generator', score: avg_scores.sql_generator, color: '#a855f7' },
      { name: 'Critic', score: avg_scores.critic, color: '#ec4899' },
      { name: 'Self Corrector', score: avg_scores.self_corrector, color: '#eab308' },
      { name: 'Data IQ', score: avg_scores.data_iq, color: '#10b981' }
    ];

    const difficultyData = [
      { name: 'Easy', failedPct: difficulty_metrics.easy.pct_failed, total: difficulty_metrics.easy.total, color: '#10b981' },
      { name: 'Medium', failedPct: difficulty_metrics.medium.pct_failed, total: difficulty_metrics.medium.total, color: '#f59e0b' },
      { name: 'Tough', failedPct: difficulty_metrics.tough.pct_failed, total: difficulty_metrics.tough.total, color: '#ef4444' }
    ];

    const CustomTooltip = ({ active, payload, label }: any) => {
      if (active && payload && payload.length) {
        return (
          <div className="bg-[#0b0a12] border border-[#231d36] rounded-xl p-3 shadow-2xl font-mono text-xs text-slate-300">
            <p className="font-bold text-white mb-1">{label}</p>
            <p className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: payload[0].payload.color || '#a855f7' }} />
              <span>{payload[0].name}: <strong className="text-white">{payload[0].value}%</strong></span>
            </p>
            {payload[0].payload.total !== undefined && (
              <p className="text-[10px] text-slate-500 mt-1">Total Evaluated: {payload[0].payload.total}</p>
            )}
          </div>
        );
      }
      return null;
    };

    return (
      <div className="space-y-6 animate-fadeIn pb-12">
        {/* Top level stats */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl border border-[#1e1932] bg-gradient-to-br from-[#0c0a15] to-[#08070e] shadow-lg flex flex-col gap-1 select-none">
            <span className="text-[9px] font-mono font-bold text-slate-500 uppercase tracking-widest">Global Agent Rating</span>
            <div className="flex items-baseline gap-1.5 mt-1">
              <span className="text-2xl font-mono font-black text-purple-400">{globalAvgScore}%</span>
              <span className="text-[10px] font-mono text-slate-600">Avg Score</span>
            </div>
            <div className="mt-2 text-[10px] font-mono text-slate-400 flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5 text-purple-500" />
              Comprehensive rating based on logs
            </div>
          </div>

          <div className="p-4 rounded-xl border border-[#1e1932] bg-gradient-to-br from-[#0c0a15] to-[#08070e] shadow-lg flex flex-col gap-1 select-none">
            <span className="text-[9px] font-mono font-bold text-slate-500 uppercase tracking-widest">Easy Failure Rate</span>
            <div className="flex items-baseline gap-1.5 mt-1">
              <span className="text-2xl font-mono font-black text-emerald-400">{difficulty_metrics.easy.pct_failed}%</span>
              <span className="text-[10px] font-mono text-slate-600">Failed</span>
            </div>
            <div className="mt-2 text-[10px] font-mono text-slate-400">
              Passed: {difficulty_metrics.easy.passed} / {difficulty_metrics.easy.total}
            </div>
          </div>

          <div className="p-4 rounded-xl border border-[#1e1932] bg-gradient-to-br from-[#0c0a15] to-[#08070e] shadow-lg flex flex-col gap-1 select-none">
            <span className="text-[9px] font-mono font-bold text-slate-500 uppercase tracking-widest">Medium Failure Rate</span>
            <div className="flex items-baseline gap-1.5 mt-1">
              <span className="text-2xl font-mono font-black text-amber-500">{difficulty_metrics.medium.pct_failed}%</span>
              <span className="text-[10px] font-mono text-slate-600">Failed</span>
            </div>
            <div className="mt-2 text-[10px] font-mono text-slate-400">
              Passed: {difficulty_metrics.medium.passed} / {difficulty_metrics.medium.total}
            </div>
          </div>

          <div className="p-4 rounded-xl border border-[#1e1932] bg-gradient-to-br from-[#0c0a15] to-[#08070e] shadow-lg flex flex-col gap-1 select-none">
            <span className="text-[9px] font-mono font-bold text-slate-500 uppercase tracking-widest">Tough Failure Rate</span>
            <div className="flex items-baseline gap-1.5 mt-1">
              <span className="text-2xl font-mono font-black text-rose-500">{difficulty_metrics.tough.pct_failed}%</span>
              <span className="text-[10px] font-mono text-slate-600">Failed</span>
            </div>
            <div className="mt-2 text-[10px] font-mono text-slate-400">
              Passed: {difficulty_metrics.tough.passed} / {difficulty_metrics.tough.total}
            </div>
          </div>
        </div>

        {/* Charts Section */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-[#0b0a12] border border-[#1e1933] rounded-xl p-4.5 flex flex-col shadow-lg">
            <h2 className="text-xs font-mono font-bold pb-3 mb-3 border-b border-[#1e1933] uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <Activity className="w-3.5 h-3.5 text-purple-400" />
              Agent Tools Performance Scores (%)
            </h2>
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={agentScoresData} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
                  <XAxis dataKey="name" stroke="#64748b" fontSize={9} tickLine={false} />
                  <YAxis domain={[0, 100]} stroke="#64748b" fontSize={9} tickLine={false} />
                  <CartesianGrid stroke="#1c1833" vertical={false} strokeDasharray="3 3" />
                  <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
                  <Bar dataKey="score" radius={[4, 4, 0, 0]} name="Performance Score">
                    {agentScoresData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="bg-[#0b0a12] border border-[#1e1933] rounded-xl p-4.5 flex flex-col shadow-lg">
            <h2 className="text-xs font-mono font-bold pb-3 mb-3 border-b border-[#1e1933] uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <BarChart3 className="w-3.5 h-3.5 text-purple-400" />
              Failure Rate by Query Complexity (%)
            </h2>
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={difficultyData} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
                  <XAxis dataKey="name" stroke="#64748b" fontSize={9} tickLine={false} />
                  <YAxis domain={[0, 100]} stroke="#64748b" fontSize={9} tickLine={false} />
                  <CartesianGrid stroke="#1c1833" vertical={false} strokeDasharray="3 3" />
                  <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
                  <Bar dataKey="failedPct" radius={[4, 4, 0, 0]} name="Failure Rate">
                    {difficultyData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Live Ratings Feed Table */}
        <div className="bg-[#0b0a12] border border-[#1e1933] rounded-xl p-4 flex flex-col shadow-lg">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-3 mb-3 border-b border-[#1e1933]">
            <h2 className="text-xs font-mono font-bold flex items-center gap-2 uppercase tracking-wider text-slate-400">
              <Cpu className="w-3.5 h-3.5 text-purple-400" />
              Live Query Performance Ratings
            </h2>
            <div className="flex items-center gap-2 max-w-sm w-full">
              <div className="relative flex-1">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
                <input
                  type="text"
                  placeholder="Search queries, questions or datasets..."
                  value={analyticsSearchQuery}
                  onChange={(e) => setAnalyticsSearchQuery(e.target.value)}
                  className="w-full bg-[#050508] border border-[#231d36] hover:border-purple-500/40 rounded px-2.5 py-1.5 pl-8 text-xs font-mono text-slate-200 placeholder-slate-500 focus:outline-none focus:border-purple-500 transition-all"
                />
              </div>
            </div>
          </div>

          <div className="overflow-x-auto rounded-lg border border-[#1c1833] bg-[#050508]/40">
            <table className="w-full font-mono text-left border-collapse text-xs">
              <thead>
                <tr className="bg-[#0e0c1b] text-slate-400 uppercase tracking-widest text-[9px] border-b border-[#1c1833]">
                  <th className="p-3">Query ID</th>
                  <th className="p-3">Question</th>
                  <th className="p-3">Difficulty</th>
                  <th className="p-3">Status</th>
                  <th className="p-3 text-center">Schema Linker</th>
                  <th className="p-3 text-center">SQL Gen</th>
                  <th className="p-3 text-center">Critic</th>
                  <th className="p-3 text-center">Self Corrector</th>
                  <th className="p-3 text-center">Data IQ</th>
                  <th className="p-3 text-center">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1b1730]">
                {filteredQueries.length > 0 ? (
                  filteredQueries.map(q => {
                    const getScoreColor = (score: number) => {
                      if (score >= 80) return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20';
                      if (score >= 50) return 'text-amber-400 bg-amber-500/10 border-amber-500/20';
                      return 'text-rose-500 bg-rose-500/10 border-rose-500/20';
                    };
                    
                    const getDifficultyBadge = (diff: string) => {
                      if (diff === 'easy') return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20';
                      if (diff === 'medium') return 'text-amber-400 bg-amber-500/10 border-amber-500/20';
                      return 'text-rose-500 bg-rose-500/10 border-rose-500/20';
                    };

                    return (
                      <tr key={q.id} className="hover:bg-[#1a1532]/10 transition-colors">
                        <td className="p-3 font-bold text-white whitespace-nowrap">
                          {q.id.replace("_q", " q")}
                        </td>
                        <td className="p-3 max-w-[200px] truncate" title={q.question}>
                          {q.question}
                        </td>
                        <td className="p-3 uppercase whitespace-nowrap">
                          <span className={`px-2 py-0.5 rounded border text-[9px] font-bold ${getDifficultyBadge(q.difficulty)}`}>
                            {q.difficulty}
                          </span>
                        </td>
                        <td className="p-3 whitespace-nowrap">
                          <span className="flex items-center gap-1.5">
                            {getStatusIcon(q.passed ? 'passed' : 'failed')}
                            {q.passed ? 'PASSED' : 'FAILED'}
                          </span>
                        </td>
                        <td className="p-3 text-center">
                          <span className={`px-2 py-1 rounded-md border font-bold ${getScoreColor(q.scores.schema_linker)}`}>
                            {q.scores.schema_linker}%
                          </span>
                        </td>
                        <td className="p-3 text-center">
                          <span className={`px-2 py-1 rounded-md border font-bold ${getScoreColor(q.scores.sql_generator)}`}>
                            {q.scores.sql_generator}%
                          </span>
                        </td>
                        <td className="p-3 text-center">
                          <span className={`px-2 py-1 rounded-md border font-bold ${getScoreColor(q.scores.critic)}`}>
                            {q.scores.critic}%
                          </span>
                        </td>
                        <td className="p-3 text-center">
                          <span className={`px-2 py-1 rounded-md border font-bold ${getScoreColor(q.scores.self_corrector)}`}>
                            {q.scores.self_corrector}%
                          </span>
                        </td>
                        <td className="p-3 text-center">
                          <span className={`px-2 py-1 rounded-md border font-bold ${getScoreColor(q.scores.data_iq)}`}>
                            {q.scores.data_iq}%
                          </span>
                        </td>
                        <td className="p-3 text-center whitespace-nowrap">
                          <button
                            onClick={() => {
                              setSelectedDb(q.dataset);
                              fetchInstanceDetails(q.dataset, q.query_id, q.question);
                            }}
                            className="px-2.5 py-1 rounded bg-[#131126] border border-[#231d3d] hover:border-purple-500/40 hover:bg-purple-500/10 text-purple-400 hover:text-purple-300 font-bold transition-all cursor-pointer shadow-sm text-[10px]"
                          >
                            INSPECT LOG
                          </button>
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan={10} className="p-12 text-center text-slate-500 italic">
                      No query results match the search filter.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  };

  const filteredMetricInstances = allInstanceResults.filter(inst => {
    if (activeMetricFilter === 'succeeded' && inst.status !== 'passed') return false;
    if (activeMetricFilter === 'errored' && inst.status !== 'failed') return false;
    if (activeMetricFilter === 'gold' && inst.gold_status !== 'gold_pass') return false;
    if (metricSearchQuery) {
      return inst.id.toLowerCase().includes(metricSearchQuery.toLowerCase()) ||
             inst.db.toLowerCase().includes(metricSearchQuery.toLowerCase());
    }
    return true;
  });

  return (
    <div className="flex h-screen w-full overflow-hidden bg-[#050508] text-slate-200 font-sans selection:bg-purple-500/30 selection:text-white">
      {/* Toast Notification System */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: -20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -20, scale: 0.95 }}
            className="fixed top-6 right-6 z-[999] pointer-events-none"
          >
            <div className={`flex items-center gap-2.5 px-4.5 py-3 rounded-xl border shadow-2xl font-mono text-xs font-bold ${
              toast.type === 'success' 
                ? 'bg-emerald-950/95 text-emerald-400 border-emerald-500/35 shadow-emerald-950/30' 
                : 'bg-rose-950/95 text-rose-400 border-rose-500/35 shadow-rose-950/30'
            }`}>
              {toast.type === 'success' ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              ) : (
                <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
              )}
              <span>{toast.message}</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Sidebar Navigation */}
      <aside className="w-16 lg:w-56 border-r border-[#1a1a22] bg-[#090812] flex flex-col p-4 gap-6 shrink-0 z-20 shadow-2xl animate-fadeIn">
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-3 px-1">
            <NQuireLogo size={32} showName nameSize="text-xs" onClick={onHome} />
          </div>

          <button
            onClick={onBack}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#110f1c] border border-[#231d36] hover:border-amber-500/50 hover:bg-[#19152a] text-slate-400 hover:text-amber-400 transition-all font-bold text-[11px] font-mono justify-center w-full shadow-md shrink-0"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span className="hidden lg:inline">Switch Project</span>
          </button>
        </div>

        <nav className="flex flex-col gap-1 flex-1">
          <button
            onClick={() => setCurrentView('dashboard')}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all font-bold text-xs tracking-tight ${currentView === 'dashboard' ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20 shadow-inner' : 'hover:bg-white/[0.04] text-slate-400 hover:text-slate-200'}`}
          >
            <BarChart3 className="w-4 h-4 shrink-0" />
            <span className="hidden lg:block truncate">Audit Dashboard</span>
          </button>
          <button
            onClick={() => {
              if (databases.length > 0) fetchResults(selectedDb || databases[0].name);
              else setCurrentView('database');
            }}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all font-bold text-xs tracking-tight ${currentView === 'database' ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20 shadow-inner' : 'hover:bg-white/[0.04] text-slate-400 hover:text-slate-200'}`}
          >
            <Terminal className="w-4 h-4 shrink-0" />
            <span className="hidden lg:block truncate">Execution Probes</span>
          </button>
          <button
            onClick={() => {
              setCurrentView('agents');
              fetchAgentAnalytics(true);
            }}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all font-bold text-xs tracking-tight ${currentView === 'agents' ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20 shadow-inner' : 'hover:bg-white/[0.04] text-slate-400 hover:text-slate-200'}`}
          >
            <Cpu className="w-4 h-4 shrink-0" />
            <span className="hidden lg:block truncate">Agent Analytics</span>
          </button>


        </nav>

        {/* Mascot Card */}
        <div className="hidden lg:flex flex-col my-auto p-3.5 bg-[#0b0a14] rounded-2xl border border-[#1d1933] shadow-md relative overflow-hidden group select-none transition-all hover:border-purple-500/40">
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-purple-500 via-indigo-500 to-pink-500 animate-pulse" />
          <div className="relative mb-3 bg-[#110e1e] border border-[#231c36] p-2.5 rounded-xl rounded-bl-none shadow-lg">
            <div className="text-[11px] font-mono text-slate-300 leading-tight min-h-[28px] flex items-center">
              {dabQuip}
            </div>
            <div className="absolute -bottom-2 left-3 w-0 h-0 border-t-8 border-t-[#110e1e] border-r-8 border-r-transparent border-l-0" />
          </div>
          <div className="flex items-center justify-center py-2">
            <Sparkles className="w-6 h-6 text-purple-400 animate-pulse" />
          </div>
        </div>

        {/* DIN Pipeline Settings */}
        <div className="hidden lg:flex flex-col p-3.5 bg-[#0b0a14] rounded-2xl border border-[#1d1933] shadow-md relative overflow-hidden group select-none transition-all hover:border-purple-500/40 mt-4">
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-purple-500 to-indigo-500" />
          <div className="flex items-center gap-2 mb-3">
            <Sliders className="w-3.5 h-3.5 text-purple-400" />
            <span className="text-[10px] font-mono font-bold text-slate-300 uppercase tracking-widest">Pipeline Settings</span>
          </div>
          
          <div className="space-y-2.5">
            {/* Model selection */}
            <div className="flex flex-col gap-1">
              <label className="text-[8px] font-mono font-bold text-slate-500 uppercase tracking-wider">Model</label>
              <select
                value={selectedModel}
                onChange={e => setSelectedModel(e.target.value)}
                className="w-full bg-[#121020] border border-[#231d36] rounded px-2 py-1 text-[11px] font-mono text-slate-200 focus:outline-none focus:border-purple-500 cursor-pointer"
              >
                <option value="bedrock/openai.gpt-oss-safeguard-120b">GPT-OSS Safeguard 120B</option>
                <option value="bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0">Claude 3.5 Sonnet v2</option>
                <option value="bedrock/anthropic.claude-3-5-haiku-20241022-v1:0">Claude 3.5 Haiku</option>
                <option value="bedrock/meta.llama3-1-70b-instruct-v1:0">Llama 3.1 70B</option>
                <option value="bedrock/meta.llama3-1-405b-instruct-v1:0">Llama 3.1 405B</option>
              </select>
            </div>

            {/* Temperature selection */}
            <div className="flex flex-col gap-1">
              <div className="flex justify-between items-center">
                <label className="text-[8px] font-mono font-bold text-slate-500 uppercase tracking-wider">Temperature</label>
                <span className="text-[9px] font-mono text-purple-400 font-bold">{temperature.toFixed(1)}</span>
              </div>
              <input
                type="range"
                min="0.0"
                max="1.0"
                step="0.1"
                value={temperature}
                onChange={e => setTemperature(Number(e.target.value))}
                className="w-full h-1 bg-[#121020] rounded-lg appearance-none cursor-pointer accent-purple-500"
              />
            </div>

            {/* Workers selection */}
            <div className="flex flex-col gap-1">
              <div className="flex justify-between items-center">
                <label className="text-[8px] font-mono font-bold text-slate-500 uppercase tracking-wider">Workers</label>
                <span className="text-[9px] font-mono text-purple-400 font-bold">{workers} Parallel</span>
              </div>
              <input
                type="range"
                min="1"
                max="5"
                step="1"
                value={workers}
                onChange={e => setWorkers(Number(e.target.value))}
                className="w-full h-1 bg-[#121020] rounded-lg appearance-none cursor-pointer accent-purple-500"
              />
            </div>
          </div>
        </div>

        {/* User Profile */}
        <div className="mt-auto pt-3 border-t border-[#1a1a22]">
          <div className="flex items-center gap-2.5 px-1 py-2 rounded-xl hover:bg-white/[0.04] transition-all group">
            {user && user.picture ? (
              <img src={user.picture} alt={user.name} className="w-7 h-7 rounded-full shrink-0 ring-1 ring-purple-500/40" referrerPolicy="no-referrer" />
            ) : (
              <div className="w-7 h-7 rounded-full bg-gradient-to-br from-purple-500/20 to-indigo-500/20 border border-purple-500/30 shrink-0 flex items-center justify-center shadow-inner">
                <User className="w-4 h-4 text-purple-300" />
              </div>
            )}
            <div className="hidden lg:flex flex-col min-w-0 flex-1">
              <span className="text-[11px] font-bold text-slate-200 truncate leading-tight">
                {user ? (user.name || 'User') : 'User (Guest)'}
              </span>
              <span className="text-[10px] text-slate-500 truncate leading-tight">
                {user ? user.email : 'guest@nquire.ai'}
              </span>
            </div>
            {user && onLogout && (
              <button
                onClick={onLogout}
                title="Sign out"
                className="hidden lg:flex shrink-0 p-1 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-400/10 transition-all"
              >
                <LogOut className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>
      </aside>

      {/* Main Panel */}
      <main className="flex-1 flex flex-col min-w-0 bg-[#050508] relative overflow-hidden">
        {/* Header Bar */}
        <header className="h-16 border-b border-[#14141c] bg-[#08070e]/80 backdrop-blur-lg flex items-center justify-between px-6 z-10 shrink-0 gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <span className="text-sm font-mono font-bold text-white tracking-tight truncate">
              {currentView === 'dashboard' && 'DataAgentBench · Forensic Telemetry & Audit Matrix'}
              {currentView === 'agents' && 'DataAgentBench · Live Agent rating & complexity matrix'}
              {currentView === 'database' && `DataAgentBench · Dataset: ${selectedDb}`}
            </span>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {/* Custom High-Contrast Date Filter Dropdown */}
            <div className="relative" ref={dateDropdownRef}>
              <button
                onClick={() => setShowDateDropdown(!showDateDropdown)}
                className="flex items-center gap-2 bg-[#0d0c15] border border-[#2c2748] hover:border-purple-500/50 rounded-lg px-3 py-1.5 text-xs font-mono text-slate-200 hover:text-white font-bold transition-all shadow-md cursor-pointer select-none"
              >
                <Filter className="w-3.5 h-3.5 text-purple-400 shrink-0" />
                {(() => {
                  const selectedRun = allDates.find(r => r.id === dateFilter);
                  const isActive = selectedRun?.is_active;
                  return (
                    <span className="flex items-center gap-2">
                      {isActive && <span className="pulsing-dot-green" title="Active Run" />}
                      <span>{selectedRun?.label || (dateFilter === 'all' ? 'All Runs' : dateFilter)}</span>
                    </span>
                  );
                })()}
                <ChevronDown className="w-3.5 h-3.5 text-slate-400 shrink-0 ml-1" />
              </button>

              <AnimatePresence>
                {showDateDropdown && (
                  <motion.div
                    initial={{ opacity: 0, y: 8, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 8, scale: 0.95 }}
                    transition={{ duration: 0.15 }}
                    className="absolute right-0 mt-1.5 w-60 rounded-xl bg-[#0b0a12] border border-[#231d36] shadow-2xl p-1 z-50 overflow-hidden font-mono"
                  >
                    <div className="text-[9px] font-bold text-slate-500 px-3 py-1.5 uppercase tracking-widest border-b border-[#1b172a] mb-1">
                      Select Benchmark Run
                    </div>
                    <div className="space-y-0.5 max-h-60 overflow-y-auto no-scrollbar">
                      {allDates.map(run => {
                        const isSelected = dateFilter === run.id;
                        return (
                          <button
                            key={run.id}
                            onClick={() => {
                              setDateFilter(run.id);
                              setShowDateDropdown(false);
                            }}
                            className={`w-full flex items-center justify-between px-3 py-2 text-left text-xs font-mono rounded-lg transition-all ${
                              isSelected 
                                ? 'bg-purple-500/10 text-purple-300 font-bold border border-purple-500/20' 
                                : 'hover:bg-white/[0.04] text-slate-400 hover:text-slate-200'
                            }`}
                          >
                            <span className="truncate">{run.label}</span>
                            {run.is_active && (
                              <span className="pulsing-dot-green ml-2" title="Active Run" />
                            )}
                          </button>
                        );
                      })}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <button
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="p-1.5 rounded-lg bg-[#0a0914] border border-[#1e1932] hover:bg-[#131024] text-slate-400 hover:text-white transition-all shadow-sm disabled:opacity-60"
              title="Refresh Current Dashboard"
            >
              <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            </button>

            {currentView === 'dashboard' && dateFilter !== 'all' && (
              <button
                onClick={handleDeleteRun}
                className="px-3 py-1.5 rounded-lg font-mono font-bold text-xs shadow-lg transition-all border flex items-center gap-1.5 bg-rose-600/10 text-rose-400 border-rose-500/30 hover:bg-rose-600/20"
                title="Delete this historical run"
              >
                <X className="w-3.5 h-3.5" />
                DELETE RUN
              </button>
            )}

            {currentView === 'dashboard' && (
              isGlobalRunning ? (
                <button
                  onClick={handleStopGlobalRun}
                  className="px-3 py-1.5 rounded-lg font-mono font-bold text-xs shadow-lg transition-all border flex items-center gap-1.5 bg-rose-600/20 text-rose-400 border-rose-500/40 hover:bg-rose-600/30"
                >
                  <XCircle className="w-3.5 h-3.5 animate-pulse" />
                  STOP
                </button>
              ) : (
                <button
                  onClick={handleRunAllClick}
                  className="px-3 py-1.5 rounded-lg font-mono font-bold text-xs shadow-lg transition-all border flex items-center gap-1.5 bg-purple-600/10 text-purple-400 border-purple-500/30 hover:bg-purple-600/20"
                >
                  <Trophy size={14} className="mr-2" />
                  RUN ALL
                </button>
              )
            )}
          </div>
        </header>

        {/* ── Run Progress Bar instead of News Ticker ─────────────────────────────── */}
        {currentView === 'dashboard' && metrics && !isGlobalRunning && (
          <div className="shrink-0 border-b border-purple-500/20 bg-gradient-to-r from-[#0d0b18] via-purple-950/20 to-[#0d0b18] px-6 py-2.5 flex items-center justify-between select-none gap-6 animate-fadeIn">
            <div className="flex items-center gap-2 text-xs font-mono font-bold text-slate-300">
              <span className="text-purple-500">◈</span>
              <span className="text-purple-400 uppercase tracking-widest text-[10px]">Active Run</span>
              <span className="text-slate-200">
                {allDates.find(r => r.id === dateFilter)?.label || (dateFilter === 'all' ? 'All Runs' : dateFilter)}
              </span>
            </div>
            
            {(() => {
              const totalQueries = metrics.total_queries || 54;
              const totalSlots = totalQueries * 5;
              const completedSlots = metrics.total_run_slots || 0;
              const pct = totalSlots > 0 ? Math.round((completedSlots / totalSlots) * 100) : 0;
              
              return (
                <div className="flex-1 max-w-xl flex items-center gap-3">
                  <div className="flex-1 h-2 bg-[#050508] rounded-full overflow-hidden border border-purple-950/50 relative">
                    <div 
                      className="h-full bg-gradient-to-r from-purple-500 to-indigo-500 shadow-[0_0_8px_rgba(167,139,250,0.4)] transition-all duration-700 ease-out"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="text-xs font-mono font-black text-purple-300 min-w-[36px] text-right">{pct}%</span>
                </div>
              );
            })()}

            <div className="flex items-center gap-3 text-xs font-mono text-slate-400">
              <span>
                <span className="text-purple-200 font-bold">{metrics.total_run_slots || 0}</span>
                <span className="text-slate-500"> / </span>
                <span className="text-purple-400 font-bold">{(metrics.total_queries || 54) * 5}</span> evaluations done
              </span>
            </div>
          </div>
        )}

        {/* Global Progress Bar */}
        {isGlobalRunning && globalProgress.total > 0 && currentView === 'dashboard' && (
          <div className="bg-[#0b0a12] border-b border-[#1e1933] px-6 py-3 flex flex-col gap-2 shadow-lg animate-fadeIn shrink-0">
            <div className="flex items-center justify-between text-xs font-mono font-bold">
              <span className="text-purple-400 flex items-center gap-2">
                <Activity className="w-4 h-4 animate-spin" />
                Executing Benchmark Batch...
              </span>
              <span className="text-slate-400">
                {Math.round((globalProgress.completed / globalProgress.total) * 100)}% Completed ({globalProgress.completed}/{globalProgress.total})
              </span>
            </div>
            <div className="w-full h-2 bg-[#050508] rounded-full overflow-hidden border border-[#1e1933]">
              <div 
                className="h-full bg-gradient-to-r from-purple-500 to-indigo-500 shadow-[0_0_10px_rgba(167,139,250,0.5)] transition-all duration-500"
                style={{ width: `${(globalProgress.completed / globalProgress.total) * 100}%` }}
              />
            </div>
          </div>
        )}



        {/* Scrollable View Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 no-scrollbar">
          {loading ? (
            <div className="h-full flex flex-col items-center justify-center gap-3 text-purple-400 font-mono animate-pulse">
              <Activity className="w-10 h-10 animate-spin" />
              <p className="text-sm font-black">Syncing DAB telemetry standards...</p>
            </div>
          ) : (
            currentView === 'dashboard' ? (
              <>
                {/* Metrics Grid */}
                {/* Metrics Grid */}
                {metrics && (
                  <MetricsGrid 
                    metrics={[
                        { label: 'TOTAL QUERIES', value: metrics.total_queries || 0, color: 'blue', type: 'total', sub: 'QUERIES' },
                        { label: 'EVALUATED', value: metrics.evaluated || 0, color: 'indigo', type: 'total', sub: 'RUNS' },
                        { label: 'PASSED', value: metrics.passed || 0, color: 'emerald', type: 'succeeded', sub: 'PASS' },
                        { label: 'FAILED', value: metrics.failed || 0, color: 'rose', type: 'errored', sub: 'FAIL' },
                        { label: 'PASS@1 ACCURACY (%)', value: String(metrics.pass_at_1_pct || metrics.gold_accuracy || '0.0%').replace('%', ''), color: 'violet', type: 'gold', sub: 'ACCURACY' },
                        { label: 'AVG LATENCY (s)', value: String(metrics.avg_latency || '0.0s').replace('s', ''), color: 'cyan', type: 'total', sub: 'PER RUN' },
                        { label: 'AVG TOKENS', value: String(metrics.avg_tokens_per_agent || '0 tokens').replace(' tokens', ''), color: 'fuchsia', type: 'total', sub: 'PER AGENT' },
                        { label: 'TOTAL COST ($)', value: String(metrics.total_cost || '$0.0000').replace('$', ''), color: 'amber', type: 'total', sub: 'ESTIMATED' }
                    ]}
                    onMetricClick={handleOpenMetricModal}
                  />
                )}

                {/* Databases and Recent Runs */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                  {/* Left Column: Target Repositories Matrix */}
                  <section className="lg:col-span-7 bg-[#0b0a12] border border-[#1e1933] rounded-xl p-4 flex flex-col shadow-lg">
                    <div className="flex items-center justify-between pb-3 mb-3 border-b border-[#1e1933]">
                      <h2 className="text-xs font-mono font-bold flex items-center gap-2 uppercase tracking-wider text-slate-400">
                        <Database className="w-3.5 h-3.5 text-purple-400" />
                        Target Benchmarks Matrix
                      </h2>
                      <span className="text-[10px] font-mono font-bold text-slate-500 bg-[#12101e] px-2 py-0.5 rounded border border-white/5">
                        {filteredDatabases.length} DATASETS
                      </span>
                    </div>

                    <div className="space-y-2 max-h-[460px] overflow-y-auto pr-1 no-scrollbar">
                      {filteredDatabases.map((db) => {
                        const totalTargetRuns = db.total_questions * 5;
                        const totalProcessed = db.run_slots || 0;
                        
                        const passK = db.results_count;
                        const failK = db.error_count;
                        const passKPct = db.total_questions ? (passK / db.total_questions) * 100 : 0;
                        const failKPct = db.total_questions ? (failK / db.total_questions) * 100 : 0;
                        
                        const executionPct = totalTargetRuns ? (totalProcessed / totalTargetRuns) * 100 : 0;

                        return (
                          <div
                            key={db.name}
                            onClick={() => fetchResults(db.name)}
                            className={`group p-3.5 rounded-lg bg-[#0e0c1b] border border-[#1c1833] hover:border-purple-500/40 hover:bg-[#141224] transition-all cursor-pointer flex items-center justify-between ${selectedDb === db.name ? 'border-purple-500 bg-purple-500/5 shadow-[0_0_15px_rgba(167,139,250,0.15)]' : ''}`}
                          >
                            <div className="flex items-center gap-3 w-full pr-4">
                              <div className={`w-8 h-8 shrink-0 rounded-md flex items-center justify-center font-bold text-xs ${db.status === 'completed' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-slate-800 text-slate-400 border border-slate-700/20'}`}>
                                {db.status === 'completed' ? <CheckCircle2 className="w-4 h-4" /> : <Database className="w-4 h-4" />}
                              </div>

                              <div className="flex-1 min-w-0">
                                <div className="flex items-center justify-between gap-2">
                                  <h3 className="font-mono font-bold text-xs truncate text-white group-hover:text-purple-400 transition-colors">
                                    {db.name}
                                  </h3>
                                  <div className="flex items-center gap-1.5 shrink-0">
                                    {db.tables_count > 0 && (
                                      <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded text-purple-400 bg-purple-500/10 border border-purple-500/20 flex items-center gap-1">
                                        <Layers className="w-2.5 h-2.5 shrink-0" />
                                        {db.tables_count} Tbls
                                      </span>
                                    )}
                                    {db.tokens > 0 && (
                                      <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded text-amber-400 bg-amber-500/10 border border-amber-500/20 flex items-center gap-1">
                                        <Zap className="w-2.5 h-2.5 shrink-0" />
                                        {db.tokens > 1000 ? `${(db.tokens / 1000).toFixed(1)}K` : db.tokens} Tokens
                                      </span>
                                    )}
                                    <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded text-blue-400 bg-blue-500/10 border border-blue-500/20">
                                      {db.total_questions} Qs
                                    </span>
                                  </div>
                                </div>

                                <div className="mt-2 w-full h-1 bg-[#090812] rounded-full overflow-hidden flex mb-1.5 relative border border-[#1e1933]">
                                  <div style={{ width: `${executionPct}%` }} className="h-full bg-gradient-to-r from-purple-500 to-indigo-500 shadow-[0_0_8px_rgba(167,139,250,0.5)] transition-all"></div>
                                </div>

                                <div className="flex items-center justify-between text-[10px] font-mono text-slate-400">
                                  <span className="text-slate-500">Done: {totalProcessed}/{totalTargetRuns} Runs</span>
                                  <div className="flex items-center gap-2 font-bold" title="Pass@K (At least 1 pass per query)">
                                    <span className="text-emerald-400">{passKPct.toFixed(0)}% P@K</span>
                                    <span className="text-rose-500">{failKPct.toFixed(0)}% Fail</span>
                                  </div>
                                </div>
                              </div>
                            </div>

                            <div className="flex items-center gap-1.5 shrink-0">
                              <button
                                className="p-2 rounded-md bg-[#131126] border border-[#231d3d] hover:border-purple-500/40 hover:bg-purple-500/10 text-purple-400 hover:text-purple-300 transition-all cursor-pointer shadow-sm shrink-0"
                                onClick={(e) => handleOpenSchemaModal(e, db.name)}
                                title="View Database Schema"
                              >
                                <Info size={14} className="animate-pulse" />
                              </button>

                              {dateFilter === 'live' && (
                                <button
                                  className={`p-2 rounded-md bg-[#1d1b32] border border-[#2d284a] hover:bg-purple-600 hover:text-white transition-all cursor-pointer shrink-0 ${runningDbs[db.name] ? 'animate-spin bg-purple-500 text-white' : 'text-slate-300'}`}
                                  onClick={(e) => { e.stopPropagation(); handleRunDb(db.name); }}
                                  title="Execute Batch Run"
                                >
                                  {runningDbs[db.name] ? <Activity className="w-3.5 h-3.5 animate-pulse" /> : <Play className="w-3.5 h-3.5" />}
                                </button>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </section>

                  {/* Right Column: Recent Executions */}
                  <section className="lg:col-span-5 bg-[#0b0a12] border border-[#1e1933] rounded-xl p-4 flex flex-col shadow-lg">
                    <div className="flex items-center justify-between pb-3 mb-3 border-b border-[#1e1933]">
                      <div className="flex items-center gap-2">
                        <Clock className="w-5 h-5 text-purple-400" />
                        <h2 className="text-sm font-mono font-bold text-white uppercase tracking-wider">Recent Executions</h2>
                      </div>
                    </div>

                    <div className="bg-[#0e0c1b]/80 border border-[#1c1833] rounded-xl overflow-hidden shadow-2xl">
                      <div className="max-h-[360px] overflow-y-auto divide-y divide-[#1b1730] no-scrollbar">
                        {recentRuns.length > 0 ? (
                          recentRuns.map(run => (
                            <div
                              key={run.id}
                              onClick={() => handleCardClick(run.db, run.id.split('_q')[1] || run.id.replace(/\D/g, ''))}
                              className="p-3.5 flex items-center justify-between gap-4 hover:bg-[#1a1532]/30 cursor-pointer transition-colors"
                            >
                              <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-2 mb-1">
                                  <span className="font-mono font-extrabold text-xs text-white">{run.id}</span>
                                  <span className="text-[9px] font-mono text-slate-500 bg-slate-800 px-1.5 py-0.2 rounded uppercase">{run.db}</span>
                                </div>
                                <div className="flex items-center gap-3 font-mono text-[9px] text-slate-500">
                                  <span>{run.latency}s</span>
                                  <span>{run.total_tokens ? `${(run.total_tokens / 1000).toFixed(1)}k tokens` : ''}</span>
                                  <span>{new Date(run.timestamp).toLocaleTimeString()}</span>
                                </div>
                              </div>

                              <div className="flex items-center gap-2.5">
                                {getStatusIcon(run.status)}
                                <ChevronRight className="w-4 h-4 text-slate-600" />
                              </div>
                            </div>
                          ))
                        ) : (
                          <div className="py-16 text-center text-slate-600 font-mono text-xs italic">
                            No recent evaluation runs found for this filter.
                          </div>
                        )}
                      </div>
                    </div>
                  </section>
                </div>
              </>
            ) : currentView === 'agents' ? (
              renderAgentAnalytics()
            ) : currentView === 'database' ? (
              /* Database Detail View */
              <div className="space-y-4 animate-fadeIn">
                <header className="bg-[#101014] border border-[#1f1f27] p-4 rounded-xl flex items-center justify-between shadow-lg flex-wrap gap-3">
                  <div className="flex items-center gap-3 flex-wrap min-w-0">
                    <button
                      onClick={() => setCurrentView('dashboard')}
                      className="p-2 rounded-lg bg-[#181820] border border-[#262632] hover:bg-white/10 hover:text-white transition-all text-slate-400 font-mono text-xs flex items-center gap-1.5 font-bold shrink-0"
                    >
                      <ArrowLeft className="w-4 h-4" /> BACK
                    </button>
                    <div className="h-4 w-px bg-[#262632]" />
                    <Database className="w-5 h-5 text-purple-400 shrink-0" />
                    <h1 className="text-base font-mono font-black tracking-tight text-white flex items-center gap-2 flex-wrap min-w-0">
                      <span className="truncate">{selectedDb}</span>
                    </h1>
                  </div>

                  {dateFilter === 'live' && (
                    <div className="flex items-center gap-2 font-mono text-xs shrink-0">
                      <button
                        onClick={() => handleRunDb(selectedDb)}
                        disabled={runningDbs[selectedDb]}
                        className="px-3 py-1.5 rounded-lg bg-purple-600/10 text-purple-400 border border-purple-500/20 hover:bg-purple-600/20 font-bold transition-all shadow"
                      >
                        {runningDbs[selectedDb] ? 'RUNNING...' : 'RUN ALL PROBES'}
                      </button>
                    </div>
                  )}
                </header>

                {/* Probe List Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
                  {dbResults.map(res => {
                    let statusColor = 'border-slate-800 text-slate-500';
                    if (res.status === 'passed' || res.status === 'success') statusColor = 'border-emerald-500 text-emerald-400';
                    else if (res.status === 'failed' || res.status === 'error') statusColor = 'border-rose-500 text-rose-500';

                    return (
                      <div
                        key={res.id}
                        onClick={() => handleCardClick(selectedDb, res.id.split('_q')[1])}
                        className={`bg-[#101014] border border-[#1f1f27] hover:border-purple-500/60 hover:bg-[#151224] rounded-xl p-3.5 flex flex-col justify-between group cursor-pointer transition-all shadow-md relative overflow-hidden ${runningInstances[res.id] ? 'border-purple-500 shadow-[0_0_20px_rgba(167,139,250,0.2)]' : ''}`}
                      >
                        <div className="flex items-center justify-between pb-2 mb-2 border-b border-[#1b1b22]">
                          <div className="flex items-center gap-1.5 flex-wrap min-w-0 pr-1">
                            {getStatusIcon(res.status)}
                            <span className="font-mono font-black text-xs text-white truncate tracking-tight">{res.id}</span>
                            {getComplexityBadge(res.complexity, res.complexity_type, res.complexity_score)}
                            {res.latency > 0 ? (
                              <>
                                <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded text-amber-400 bg-amber-500/10 border border-amber-500/20 flex items-center gap-1 shrink-0" title="Execution Time (Latency)">
                                  <Zap className="w-2.5 h-2.5 shrink-0 text-amber-400" />
                                  {res.latency}s
                                </span>
                                {res.cost > 0 && (
                                  <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded text-violet-400 bg-violet-500/10 border border-violet-500/20 flex items-center gap-1 shrink-0" title={`Cost Incurred`}>
                                    <DollarSign className="w-2.5 h-2.5 shrink-0 text-violet-400" />
                                    ${res.cost.toFixed(4)}
                                  </span>
                                )}
                              </>
                            ) : (
                              <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded text-slate-400 bg-slate-500/10 border border-slate-500/20 flex items-center gap-1 shrink-0" title="Execution Time (Latency)">
                                <Clock className="w-2.5 h-2.5 shrink-0 text-slate-400" />
                                {res.status === 'running' ? 'Executing...' : 'Unrun'}
                              </span>
                            )}
                            {res.status === 'passed' || res.status === 'success' ? (
                              <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded flex items-center gap-1 shrink-0 ${res.rows > 0 ? 'text-emerald-400 bg-emerald-500/10 border border-emerald-500/20' : 'text-amber-400 bg-amber-500/10 border border-amber-500/20'}`} title="Result Set Row Count">
                                <Database className="w-2.5 h-2.5 shrink-0" />
                                {res.rows} {res.rows === 1 ? 'Row' : 'Rows'}
                              </span>
                            ) : res.status === 'failed' || res.status === 'error' ? (
                              <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded text-rose-400 bg-rose-500/10 border border-rose-500/20 flex items-center gap-1 shrink-0" title="Execution Failed">
                                <AlertTriangle className="w-2.5 h-2.5 shrink-0 text-rose-400" />
                                Failed
                              </span>
                            ) : null}
                            {res.corrections > 0 && (
                              <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded text-cyan-400 bg-cyan-500/10 border border-cyan-500/20 flex items-center gap-1 shrink-0" title="Self-Correction Rounds Triggered">
                                <RefreshCw className={`w-2.5 h-2.5 shrink-0 text-cyan-400 ${res.status === 'running' ? 'animate-spin' : ''}`} />
                                {res.corrections} {res.corrections === 1 ? 'Fix' : 'Fixes'}
                              </span>
                            )}
                          </div>

                          <div className="flex items-center gap-1.5 shrink-0">
                            <button
                              onClick={(e) => { e.stopPropagation(); fetchInstanceDetails(res.db_id, res.id.split('_q')[1], res.question || null); }}
                              className="p-1.5 rounded bg-[#181820] border border-[#262632] hover:bg-purple-600 hover:text-white transition-all text-slate-400"
                              title="Live Execution Audit Drawer"
                            >
                              <Activity className="w-3.5 h-3.5 text-purple-400 animate-pulse" />
                            </button>
                            {dateFilter === 'live' && (
                              <button
                                className={`p-1.5 rounded bg-[#181820] border border-[#262632] hover:bg-emerald-600 hover:text-white transition-all ${runningInstances[res.id] ? 'animate-spin bg-purple-500 text-white' : 'text-slate-300'}`}
                                onClick={(e) => { e.stopPropagation(); handleRunSingle(res.db_id, res.id.split('_q')[1]); }}
                                disabled={runningInstances[res.id]}
                                title="Execute Single Instance"
                              >
                                {runningInstances[res.id] ? <Activity className="w-3.5 h-3.5 animate-pulse" /> : <Play className="w-3.5 h-3.5" />}
                              </button>
                            )}
                          </div>
                        </div>

                        <div className="bg-[#141419] p-2.5 rounded-lg border border-[#1c1c24] mb-3 flex-1 font-sans">
                          <p className="text-[11px] text-slate-300 leading-normal font-sans line-clamp-3 hover:line-clamp-none transition-all font-medium">
                            {res.question || <span className="italic text-slate-600 font-mono">Question data unavailable.</span>}
                          </p>
                        </div>

                        <div className="flex items-center justify-between pt-2 border-t border-[#1b1b22] font-mono text-[10px]">
                          <div className="flex items-center gap-1.5 font-bold uppercase tracking-wider">
                            <span className="text-slate-500">VERDICT:</span>
                            <span className={statusColor.split(' ')[1]}>{res.status.toUpperCase()}</span>
                            {res.gold_status === 'gold_pass' && (
                              <span className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-1.5 py-0.2 rounded font-black ml-1">
                                GOLD ✓
                              </span>
                            )}
                            {res.gold_status === 'gold_fail' && (
                              <span className="bg-rose-500/10 text-rose-400 border border-rose-500/20 px-1.5 py-0.2 rounded font-black ml-1">
                                GOLD ✗
                              </span>
                            )}
                          </div>

                          {res.status !== 'pending' && (
                            <div className="flex items-center gap-1.5 shrink-0">
                              <button
                                className="font-bold flex items-center gap-1 text-indigo-400 hover:text-white bg-indigo-500/10 hover:bg-indigo-500 border border-indigo-500/20 hover:border-indigo-500 px-2 py-1 rounded transition-all"
                                onClick={(e) => { e.stopPropagation(); handleDiagnose(selectedDb, res.id.split('_q')[1]); }}
                              >
                                <ShieldAlert className="w-3 h-3 shrink-0" />
                                DIAGNOSE
                              </button>
                              <button
                                className="font-bold flex items-center gap-1 text-blue-400 hover:text-white bg-blue-500/10 hover:bg-blue-500 border border-blue-500/20 hover:border-blue-500 px-2 py-1 rounded transition-all"
                                onClick={(e) => { e.stopPropagation(); fetchInstanceDetails(selectedDb, res.id.split('_q')[1], res.question || null); }}
                              >
                                <TerminalSquare className="w-3 h-3 shrink-0" />
                                ARTIFACTS
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : null
          )}
        </div>
      </main>

      {/* Metric Detail Modal */}
      <AnimatePresence>
        {showMetricModal && (
          <motion.div
            initial="hidden"
            animate="visible"
            exit="hidden"
            className="fixed inset-0 z-50 flex items-center justify-center p-6 select-none"
          >
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="absolute inset-0 bg-black/60 backdrop-blur-sm"
              onClick={() => setShowMetricModal(false)}
            />
            {/* Modal Box */}
            <motion.div
              variants={{
                hidden: { scale: 0.95, opacity: 0 },
                visible: { scale: 1, opacity: 1 }
              }}
              transition={{ duration: 0.2, ease: 'easeOut' }}
              className="bg-[#0b0b0e] border border-[#1a1a24] rounded-2xl w-full max-w-4xl h-[80vh] flex flex-col overflow-hidden shadow-2xl relative z-10"
            >
              <header className="p-4 border-b border-[#1f1f2a] flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="font-mono font-bold text-sm text-white uppercase tracking-wider">
                    Metrics Inspector: {activeMetricFilter}
                  </span>
                </div>
                <button onClick={() => setShowMetricModal(false)} className="p-1.5 rounded-lg bg-[#181822] hover:bg-white/5 text-slate-400 hover:text-white transition-colors">
                  <X className="w-4 h-4" />
                </button>
              </header>

              {/* Filter controls */}
              <div className="p-4 bg-[#0d0d12] border-b border-[#1a1a24] flex items-center justify-between gap-4 flex-wrap">
                <div className="relative w-64">
                  <Search className="absolute left-3 top-2 w-3.5 h-3.5 text-slate-500" />
                  <input
                    type="text"
                    placeholder="Search ID or DB..."
                    value={metricSearchQuery}
                    onChange={e => setMetricSearchQuery(e.target.value)}
                    className="w-full pl-9 pr-4 py-1.5 bg-[#0e0e14] border border-[#282838] rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
                  />
                </div>
              </div>

              {/* Instance List */}
              <div className="flex-1 overflow-y-auto p-4 no-scrollbar">
                {loadingMetricInstances ? (
                  <div className="h-full flex flex-col items-center justify-center text-purple-400 font-mono animate-pulse">
                    <Activity className="w-8 h-8 animate-spin" />
                    <p className="text-xs font-bold mt-2">Aggregating benchmark forensic execution logs...</p>
                  </div>
                ) : filteredMetricInstances.length > 0 ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {filteredMetricInstances.map(inst => (
                      <div
                        key={inst.id}
                        onClick={() => fetchInstanceDetailsFromModal(inst.db, inst.id)}
                        className="bg-[#121217] border border-[#22222c] hover:border-purple-500/50 p-4 rounded-xl cursor-pointer transition-all hover:scale-[1.02] shadow-lg flex flex-col justify-between font-mono"
                      >
                        <div>
                          <div className="flex items-center justify-between mb-2">
                            <span className="font-extrabold text-xs text-white truncate">{inst.id}</span>
                            {getStatusIcon(inst.status)}
                          </div>
                          <div className="text-[10px] text-slate-500 uppercase tracking-widest mb-3">{inst.db}</div>
                        </div>

                        <div className="pt-2 border-t border-[#1e1e2c] flex justify-between text-[10px] text-slate-400">
                          <span>{inst.latency}s</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="h-full flex items-center justify-center text-slate-600 font-mono text-xs italic">
                    No instances match the current filters.
                  </div>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Forensic Diagnostics Drawer */}
      <AnimatePresence>
        {selectedDetails && (
          <motion.div
            initial="hidden"
            animate="visible"
            exit="hidden"
            className="fixed inset-0 z-50 flex justify-end select-none"
          >
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="absolute inset-0 bg-black/60 backdrop-blur-sm"
              onClick={() => setSelectedDetails(null)}
            />
            <motion.div
              variants={{
                hidden: { x: '100%' },
                visible: { x: 0 }
              }}
              transition={{ type: 'spring', damping: 28, stiffness: 240 }}
              className="relative w-full max-w-4xl bg-[#09090c] border-l border-[#1a1a24] h-full flex flex-col shadow-2xl z-10"
            >
              <header className="p-4 border-b border-[#1b1b26] bg-[#0c0c11] flex justify-between items-start shrink-0">
                <div className="flex items-start gap-3 flex-1 min-w-0">
                  <Database className="w-5 h-5 text-purple-400 mt-0.5 shrink-0" />
                  <div className="min-w-0">
                    <h2 className="font-mono font-black text-sm text-white">{selectedDetails.id}</h2>
                    <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">{selectedDetails.db}</span>
                    {selectedDetails.question && (
                      <div className="flex items-start gap-1.5 mt-2">
                        <MessageSquare className="w-3.5 h-3.5 text-purple-400 shrink-0 mt-0.5" />
                        <p className="text-[11px] text-slate-300 font-sans leading-snug">{selectedDetails.question}</p>
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0 ml-3">
                  <button onClick={() => setSelectedDetails(null)} className="p-1.5 rounded-lg bg-[#14141c] border border-[#252538] text-slate-400 hover:text-white transition-colors">
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </header>

              {/* Sub-tabs */}
              <div className="flex border-b border-[#1f1f2e] bg-[#0c0c11] px-4 shrink-0">
                {[
                  { id: 'flow', icon: <Sparkles className="w-3.5 h-3.5 inline mr-1" /> },
                  { id: 'sql', icon: <FileCode className="w-3.5 h-3.5 inline mr-1" /> },
                  { id: 'log', icon: <Activity className="w-3.5 h-3.5 inline mr-1" /> },
                  { id: 'csv', icon: <FileSpreadsheet className="w-3.5 h-3.5 inline mr-1" /> },
                  { id: 'insights', icon: <Lightbulb className="w-3.5 h-3.5 inline mr-1" /> },
                ].map(({ id, icon }) => (
                  <button
                    key={id}
                    onClick={() => setDetailsTab(id)}
                    className={`px-4 py-2 font-mono font-bold text-xs uppercase border-b-2 tracking-wider transition-all ${detailsTab === id ? 'border-purple-500 text-purple-400 font-extrabold' : 'border-transparent text-slate-500 hover:text-slate-300'}`}
                  >
                    {icon}{id}
                  </button>
                ))}
              </div>

              {/* Drawer Content */}
              <div className="flex-1 overflow-auto p-6 no-scrollbar bg-[#07070a]">
                {loadingDetails ? (
                  <div className="h-full flex flex-col items-center justify-center text-purple-400 animate-pulse font-mono">
                    <Activity className="w-8 h-8 animate-spin" />
                    <p className="text-xs font-bold mt-2">Loading logs & database schemas...</p>
                  </div>
                ) : (
                  <>
                    {detailsTab === 'flow' && (
                      <ArchitectureFlow
                        diagnoseData={{
                          ...selectedDetails.diagnoseData,
                          live_steps: (selectedDetails.diagnoseData?.live_steps && selectedDetails.diagnoseData.live_steps.length > 0)
                            ? selectedDetails.diagnoseData.live_steps
                            : (selectedDetails.logContent ? parseLiveStepsFromMd(selectedDetails.logContent).steps : [])
                        }}
                        currentStatus={selectedDetails.status}
                        themeColor="violet"
                      />
                    )}
                    {detailsTab === 'sql' && (
                      <div className="space-y-4 h-full flex flex-col">
                        <div className="flex justify-between items-center">
                          <span className="text-[10px] font-mono text-slate-500 uppercase tracking-widest">Compiled SQL Query / Program</span>
                          <button
                            onClick={() => handleCopy(selectedDetails.sqlContent, 'sql')}
                            className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#101017] border border-[#262638] text-slate-400 hover:text-white transition-colors text-[10px] font-mono font-bold"
                          >
                            {copiedType === 'sql' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                            {copiedType === 'sql' ? 'COPIED' : 'COPY'}
                          </button>
                        </div>
                        <pre className="flex-1 bg-black/40 border border-[#1a1a24] p-4 rounded-xl font-mono text-xs text-purple-300 overflow-auto whitespace-pre-wrap select-text selection:bg-purple-600/30">
                          {selectedDetails.sqlContent || 'No SQL generated for this run.'}
                        </pre>
                      </div>
                    )}

                    {detailsTab === 'log' && (
                      <div className="space-y-4 h-full flex flex-col">
                        <div className="flex justify-between items-center">
                          <span className="text-[10px] font-mono text-slate-500 uppercase tracking-widest flex items-center gap-2">
                            Execution Reasoning Logs
                            {selectedDetails.status === 'running' && (
                              <span className="flex items-center gap-1 text-purple-400">
                                <span className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-ping inline-block" />
                                live
                              </span>
                            )}
                          </span>
                          <button
                            onClick={() => handleCopy(selectedDetails.logContent, 'log')}
                            className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#101017] border border-[#262638] text-slate-400 hover:text-white transition-colors text-[10px] font-mono font-bold"
                          >
                            {copiedType === 'log' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                            {copiedType === 'log' ? 'COPIED' : 'COPY'}
                          </button>
                        </div>
                        <pre ref={logPreRef} className="flex-1 bg-black/40 border border-[#1a1a24] p-4 rounded-xl font-mono text-[11px] text-slate-300 overflow-auto whitespace-pre-wrap select-text selection:bg-purple-600/30">
                          {selectedDetails.logContent || 'No execution logs available.'}
                        </pre>
                      </div>
                    )}

                    {detailsTab === 'csv' && (
                      <div className="space-y-4 h-full flex flex-col">
                        <div className="flex justify-between items-center shrink-0">
                          <span className="text-[10px] font-mono text-slate-500 uppercase tracking-widest">Query Result Dataset</span>
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => {
                                if (!selectedDetails.csvHeaders?.length) return;
                                const rows = [selectedDetails.csvHeaders.join(','), ...(selectedDetails.csvData || []).map(r => selectedDetails.csvHeaders.map(h => `"${String(r[h] ?? '').replace(/"/g, '""')}"`).join(','))].join('\n');
                                handleCopy(rows, 'csv');
                              }}
                              className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#101017] border border-[#262638] text-slate-400 hover:text-white transition-colors text-[10px] font-mono font-bold"
                            >
                              {copiedType === 'csv' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                              {copiedType === 'csv' ? 'COPIED' : 'COPY CSV'}
                            </button>
                            <button
                              onClick={() => {
                                if (!selectedDetails.csvHeaders?.length) return;
                                const rows = [selectedDetails.csvHeaders.join(','), ...(selectedDetails.csvData || []).map(r => selectedDetails.csvHeaders.map(h => `"${String(r[h] ?? '').replace(/"/g, '""')}"`).join(','))].join('\n');
                                const blob = new Blob([rows], { type: 'text/csv' });
                                const url = URL.createObjectURL(blob);
                                const a = document.createElement('a');
                                a.href = url; a.download = `${selectedDetails.id}_results.csv`; a.click();
                                URL.revokeObjectURL(url);
                              }}
                              className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#101017] border border-[#262638] text-slate-400 hover:text-emerald-400 transition-colors text-[10px] font-mono font-bold"
                            >
                              <Download className="w-3 h-3" />
                              DOWNLOAD
                            </button>
                          </div>
                        </div>
                        <div className="flex-1 border border-[#1e1e2d] bg-[#0c0c11]/50 rounded-xl overflow-auto select-text">
                          {selectedDetails.csvHeaders && selectedDetails.csvHeaders.length > 0 ? (
                            <table className="w-full text-left font-mono text-xs border-collapse">
                              <thead className="sticky top-0 z-10">
                                <tr className="bg-[#12121c] border-b border-[#20202d] text-slate-400 uppercase text-[10px]">
                                  {selectedDetails.csvHeaders.map(h => (
                                    <th key={h} className="p-3 font-extrabold">{h}</th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {selectedDetails.csvData && selectedDetails.csvData.map((row, idx) => (
                                  <tr key={idx} className="border-b border-[#181822] hover:bg-white/5 transition-colors">
                                    {selectedDetails.csvHeaders.map(h => (
                                      <td key={h} className="p-3 text-slate-300 truncate max-w-[200px]">{String(row[h] ?? 'NULL')}</td>
                                    ))}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          ) : (
                            <div className="h-full flex items-center justify-center text-slate-600 font-mono text-xs italic py-16">
                              No result set returned or empty table.
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {detailsTab === 'insights' && (() => {
                      const insights = generateInsights(selectedDetails.csvHeaders, selectedDetails.csvData);
                      const dotColors = ['#a78bfa','#6366f1','#38bdf8','#34d399','#fb923c'];
                      return (
                        <div className="space-y-5 h-full flex flex-col">
                          {selectedDetails.question && (
                            <div className="flex items-start gap-2 p-3 rounded-xl bg-purple-500/10 border border-purple-500/20 shrink-0">
                              <MessageSquare className="w-3.5 h-3.5 text-purple-400 mt-0.5 shrink-0" />
                              <p className="text-[12px] text-slate-200 font-sans leading-snug">{selectedDetails.question}</p>
                            </div>
                          )}
                          {insights.length > 0 ? (
                            <>
                              <div className="space-y-2.5 shrink-0">
                                {insights.map((bullet, i) => (
                                  <div key={i} className="flex items-start gap-2.5">
                                    <span className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-black shrink-0 mt-0.5" style={{ background: dotColors[i] + '22', color: dotColors[i], border: `1px solid ${dotColors[i]}44` }}>{i+1}</span>
                                    <p className="text-[12px] text-slate-300 leading-snug font-sans">{bullet}</p>
                                  </div>
                                ))}
                              </div>
                              <div className="flex items-center gap-3 shrink-0">
                                <span className="text-[10px] font-mono text-slate-600 uppercase tracking-widest">{selectedDetails.csvData?.length || 0} rows</span>
                                <span className="w-1 h-1 rounded-full bg-slate-700" />
                                <span className="text-[10px] font-mono text-slate-600 uppercase tracking-widest">{selectedDetails.csvHeaders?.length || 0} cols</span>
                              </div>
                              <div className="flex-1 bg-[#0c0c11] border border-[#1e1e2d] rounded-xl p-4 overflow-hidden">
                                <InsightsChart headers={selectedDetails.csvHeaders} data={selectedDetails.csvData} />
                              </div>
                            </>
                          ) : (
                            <div className="flex-1 flex items-center justify-center text-slate-600 font-mono text-xs italic">
                              Run the query to generate insights.
                            </div>
                          )}
                        </div>
                      );
                    })()}
                  </>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>



      {/* Forensic Diagnostics & Repair Drawer */}
      <AnimatePresence>
        {showDiagnoseDrawer && (
          <motion.div
            initial="hidden"
            animate="visible"
            exit="hidden"
            className="fixed inset-0 z-50 flex justify-end select-none"
          >
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="absolute inset-0 bg-black/60 backdrop-blur-sm"
              onClick={() => setShowDiagnoseDrawer(false)}
            />
            <motion.div
              variants={{
                hidden: { x: '100%' },
                visible: { x: 0 }
              }}
              transition={{ type: 'spring', damping: 28, stiffness: 240 }}
              className="relative w-full max-w-2xl bg-[#09090c] border-l border-[#1a1a24] h-full flex flex-col shadow-2xl z-10"
            >
              <header className="p-4 border-b border-[#1b1b26] bg-[#0c0c11] flex justify-between items-center shrink-0">
                <div className="flex items-center gap-3">
                  <Activity className="w-5 h-5 text-amber-500 animate-pulse" />
                  <div>
                    <h2 className="font-mono font-black text-sm text-white">Forensic Diagnostics</h2>
                    <span className="text-[10px] font-mono text-slate-500 uppercase">{diagnoseData ? diagnoseData.instance_id : 'Loading...'}</span>
                  </div>
                </div>
                <button onClick={() => setShowDiagnoseDrawer(false)} className="p-1.5 rounded-lg bg-[#14141c] border border-[#252538] text-slate-400 hover:text-white transition-colors">
                  <X className="w-4 h-4" />
                </button>
              </header>

              <div className="flex-1 overflow-y-auto p-6 bg-[#07070a] space-y-6 no-scrollbar">
                {loadingDiagnose || !diagnoseData ? (
                  <div className="h-full flex flex-col items-center justify-center text-amber-500 animate-pulse font-mono">
                    <Activity className="w-8 h-8 animate-spin" />
                    <p className="text-xs font-bold mt-2">Running diagnostic assertions...</p>
                  </div>
                ) : (
                  <>
                    {/* Problematic Agent Card */}
                    <div className="p-4 rounded-xl bg-[#0e0e14] border border-[#20202d] font-mono text-xs space-y-3">
                      <div className="flex justify-between items-center">
                        <span className="text-slate-500">Problematic Module:</span>
                        <span className={`px-2 py-0.5 rounded font-extrabold text-[10px] uppercase border ${diagnoseData.problematic_agent === 'None' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border-rose-500/20 animate-pulse'}`}>
                          {diagnoseData.problematic_agent}
                        </span>
                      </div>
                      <p className="text-slate-300 leading-relaxed text-[11px]">
                        {diagnoseData.diagnostics_summary}
                      </p>
                    </div>

                    {/* Scorecard table */}
                    <div className="space-y-2">
                      <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">Agent Evaluation Scores</span>
                      <div className="bg-[#0e0e14] border border-[#1a1a24] rounded-xl overflow-hidden font-mono text-xs">
                        <div className="divide-y divide-[#1e1e2c]">
                          {Object.entries(diagnoseData.agent_scorecard || {}).map(([agent, card]: [string, any]) => (
                            <div key={agent} className="p-3 flex items-center justify-between">
                              <span className="text-slate-300 font-medium">{agent}</span>
                              <div className="flex items-center gap-3">
                                <span className="text-[10px] text-slate-500">{card.metrics}</span>
                                {card.status === 'success' ? (
                                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                                ) : card.status === 'warning' ? (
                                  <AlertTriangle className="w-4 h-4 text-amber-500" />
                                ) : (
                                  <XCircle className="w-4 h-4 text-rose-500" />
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>

                    {/* Recommendations */}
                    <div className="space-y-2 font-mono text-xs">
                      <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">Recommendations</span>
                      <ul className="list-disc list-inside p-4 rounded-xl bg-[#0e0e14] border border-[#20202d] text-slate-300 space-y-2">
                        {diagnoseData.recommendations && diagnoseData.recommendations.map((r, i) => (
                          <li key={i}>{r}</li>
                        ))}
                      </ul>
                    </div>

                    {/* Repair Sandbox */}
                    {dateFilter === 'live' && (
                      <div className="pt-4 border-t border-[#1a1a24] space-y-4 font-mono text-xs">
                        <div className="flex justify-between items-center">
                          <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">Autonomous Repair Sandbox</span>
                          <button
                            onClick={triggerFixIssues}
                            disabled={applyingFix}
                            className="px-3 py-1.5 rounded-lg bg-amber-600/10 text-amber-400 border border-amber-500/20 hover:bg-amber-600/20 font-bold transition-all shadow"
                          >
                            {applyingFix ? 'COMPUTING REPAIR...' : 'TRIGGER AUTO-REPAIR'}
                          </button>
                        </div>

                        {fixFeedback && (
                          <div className="p-3.5 rounded-lg bg-emerald-950/20 text-emerald-400 border border-emerald-500/20 leading-relaxed text-[11px]">
                            {fixFeedback}
                          </div>
                        )}

                        {fixResult && (
                          <div className="space-y-4 p-4 bg-black/40 border border-[#1b1b26] rounded-xl relative">
                            <div>
                              <span className="text-slate-500 text-[10px] uppercase">Reasoning Steps:</span>
                              <div className="text-slate-400 text-[11px] leading-relaxed mt-1 space-y-1">
                                {fixResult.reasoning.map((r, i) => <div key={i}>• {r}</div>)}
                              </div>
                            </div>

                            <div className="border-t border-[#1b1b26] pt-3">
                              <span className="text-slate-500 text-[10px] uppercase block mb-1">Proposed corrected SQL:</span>
                              <pre className="p-3 bg-black/50 border border-[#1f1f2d] text-purple-300 text-xs overflow-x-auto rounded-lg">
                                {fixResult.corrected_sql}
                              </pre>
                            </div>

                            <div className="flex items-center gap-3 justify-end pt-2">
                              <button
                                onClick={rejectFix}
                                className="px-3 py-1.5 rounded bg-rose-600/10 border border-rose-500/20 text-rose-500 hover:bg-rose-600/20 text-xs font-bold"
                              >
                                REJECT
                              </button>
                              <button
                                onClick={acceptFix}
                                className="px-3 py-1.5 rounded bg-emerald-600/15 border border-emerald-500/20 text-emerald-400 hover:bg-emerald-600/30 text-xs font-bold"
                              >
                                ACCEPT & WRITE
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
      {/* Delete Confirmation Modal */}
      {showDeleteModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fadeIn">
          <div className="bg-[#0b0a14] border border-purple-500/30 rounded-2xl w-full max-w-md shadow-2xl shadow-purple-900/20 overflow-hidden flex flex-col relative animate-slideUp">
            <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-purple-600 to-rose-400" />
            <div className="p-6">
              <div className="flex items-center gap-4 mb-4">
                <div className="w-12 h-12 rounded-full bg-rose-500/10 border border-rose-500/20 flex items-center justify-center shrink-0">
                  <X className="w-6 h-6 text-rose-500" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-slate-100 font-mono">Delete Forensic Data</h3>
                  <p className="text-sm text-slate-400 font-mono mt-1">
                    Target: <span className="text-rose-400">{allDates.find(r => r.id === dateFilter)?.label || dateFilter}</span>
                  </p>
                </div>
              </div>
              <p className="text-sm text-slate-300 leading-relaxed">
                You are about to permanently delete all archived DAB metrics, baseline benchmark evaluations, and execution logs for this specific date/run.
                <br /><br />
                <span className="font-bold text-rose-400">This action is completely irreversible.</span> Do you wish to proceed?
              </p>
            </div>
            <div className="flex items-center justify-end gap-3 px-6 py-4 bg-[#0e0d18] border-t border-[#1c1a2d]">
              <button
                onClick={() => setShowDeleteModal(false)}
                disabled={isDeleting}
                className="px-4 py-2 rounded-lg font-mono text-xs font-bold text-slate-400 hover:text-slate-200 hover:bg-white/5 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                CANCEL
              </button>
              <button
                onClick={confirmDeleteRun}
                disabled={isDeleting}
                className="px-4 py-2 rounded-lg font-mono text-xs font-bold text-white bg-rose-600 hover:bg-rose-500 transition-all shadow-lg shadow-rose-600/20 flex items-center gap-2 disabled:bg-rose-800 disabled:cursor-not-allowed"
              >
                {isDeleting ? (
                  <>
                    <Activity className="w-4 h-4 animate-spin" />
                    DELETING RUN...
                  </>
                ) : (
                  <>
                    <X className="w-4 h-4" />
                    CONFIRM DELETION
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Run Options Confirmation Modal */}
      {showRunOptionsModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fadeIn">
          <div className="bg-[#0b0a14] border border-purple-500/30 rounded-2xl w-full max-w-lg shadow-2xl shadow-purple-900/20 overflow-hidden flex flex-col relative animate-slideUp">
            <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-purple-600 to-indigo-400" />
            <div className="p-6">
              <div className="flex items-center gap-4 mb-4">
                <div className="w-12 h-12 rounded-full bg-purple-500/10 border border-purple-500/20 flex items-center justify-center shrink-0">
                  <Play className="w-6 h-6 text-purple-400" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-slate-100 font-mono">DAB Execution Setup</h3>
                  <p className="text-sm text-slate-400 font-mono mt-1">
                    Today's Run Status: <span className="text-purple-400">{completedSlots} / 270 evaluations completed</span>
                  </p>
                </div>
              </div>
              
              <div className="space-y-4 my-4">
                <button
                  onClick={() => {
                    setShowRunOptionsModal(false);
                    triggerGlobalRun('continue');
                  }}
                  className="w-full p-4 rounded-xl border border-purple-500/20 bg-[#121020] hover:bg-[#1a1730] transition-all text-left flex flex-col gap-1 cursor-pointer group"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-purple-400 text-sm group-hover:text-purple-300">CONTINUE INCOMPLETE RUN</span>
                    <ChevronRight className="w-4 h-4 text-purple-500 transition-transform group-hover:translate-x-1" />
                  </div>
                  <p className="text-xs text-slate-400 font-mono">
                    Resume the existing run, executing only the remaining {270 - completedSlots} pending queries. This preserves your completed evaluations and metrics.
                  </p>
                </button>

                <button
                  onClick={() => {
                    setShowRunOptionsModal(false);
                    triggerGlobalRun('fresh');
                  }}
                  className="w-full p-4 rounded-xl border border-rose-500/20 bg-[#171015] hover:bg-[#251820] transition-all text-left flex flex-col gap-1 cursor-pointer group"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-rose-400 text-sm group-hover:text-rose-300">START A FRESH RUN</span>
                    <ChevronRight className="w-4 h-4 text-rose-500 transition-transform group-hover:translate-x-1" />
                  </div>
                  <p className="text-xs text-slate-400 font-mono">
                    Archive all of today's evaluations to the disk log history, clear the database, and start a completely new evaluation process from scratch.
                  </p>
                </button>
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 px-6 py-4 bg-[#0e0d18] border-t border-[#1c1a2d]">
              <button
                onClick={() => setShowRunOptionsModal(false)}
                className="px-4 py-2 rounded-lg font-mono text-xs font-bold text-slate-400 hover:text-slate-200 hover:bg-white/5 transition-all"
              >
                CANCEL
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Database Schema Modal */}
      <AnimatePresence>
        {showSchemaModal && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fadeIn font-sans select-text">
            <motion.div
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              transition={{ type: 'spring', damping: 25, stiffness: 200 }}
              className="bg-[#0b0a14] border border-purple-500/30 rounded-2xl w-full max-w-3xl h-[80vh] shadow-2xl overflow-hidden flex flex-col relative"
            >
              <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-purple-600 via-indigo-500 to-cyan-500" />
              
              {/* Header */}
              <header className="p-5 border-b border-[#1b1730] flex justify-between items-center bg-[#0d0c1b]/80 shrink-0">
                <div className="flex items-center gap-3">
                  <Database className="w-5 h-5 text-purple-400" />
                  <div className="text-left">
                    <h3 className="text-sm font-mono font-bold text-white uppercase tracking-wider">
                      Database Schema Explorer
                    </h3>
                    <span className="text-[10px] font-mono text-slate-500 uppercase">
                      Dataset: {schemaData?.dataset || 'Loading...'}
                    </span>
                  </div>
                </div>
                <button 
                  onClick={() => { setShowSchemaModal(false); setSchemaData(null); }}
                  className="p-1.5 rounded-lg bg-[#141224] border border-[#25203c] text-slate-400 hover:text-white transition-colors cursor-pointer"
                >
                  <X className="w-4 h-4" />
                </button>
              </header>

              {/* Content Body */}
              <div className="flex-1 overflow-y-auto p-6 bg-[#07070a] space-y-6 no-scrollbar text-left">
                {schemaLoading || !schemaData ? (
                  <div className="h-full flex flex-col items-center justify-center text-purple-400 animate-pulse font-mono py-20">
                    <Activity className="w-8 h-8 animate-spin" />
                    <p className="text-xs font-bold mt-2">Connecting to local database node...</p>
                  </div>
                ) : schemaData.error ? (
                  <div className="text-rose-400 bg-rose-950/20 border border-rose-900/30 rounded-xl p-4 flex gap-2.5 text-xs font-mono">
                    <AlertTriangle className="w-4 h-4 shrink-0" />
                    <div>{schemaData.error}</div>
                  </div>
                ) : (
                  <>
                    {/* DB Description if available */}
                    {schemaData.description && (
                      <div className="p-4 rounded-xl bg-[#0e0c1b] border border-[#1e1735] text-slate-300 font-sans leading-relaxed text-xs">
                        <div className="text-[9px] font-mono font-bold text-purple-400 uppercase tracking-wider mb-1">Description</div>
                        {schemaData.description}
                      </div>
                    )}

                    {/* Schema Tabs if multiple database clients */}
                    {Object.keys(schemaData.schema || {}).length > 1 && (
                      <div className="flex border-b border-[#1b1730] gap-1 shrink-0">
                        {Object.keys(schemaData.schema).map(clientName => (
                          <button
                            key={clientName}
                            onClick={() => setSelectedSchemaTab(clientName)}
                            className={`px-4 py-2 text-xs font-mono font-bold transition-all border-b-2 cursor-pointer ${
                              selectedSchemaTab === clientName
                                ? 'border-purple-500 text-purple-400 bg-purple-500/5'
                                : 'border-transparent text-slate-500 hover:text-slate-300'
                            }`}
                          >
                            {clientName.toUpperCase()} ({schemaData.schema[clientName].db_type})
                          </button>
                        ))}
                      </div>
                    )}

                    {/* Schema Display for Selected Client */}
                    {(() => {
                      const clientName = selectedSchemaTab || Object.keys(schemaData.schema || {})[0];
                      const clientData = schemaData.schema?.[clientName];
                      if (!clientData || !clientData.tables || Object.keys(clientData.tables).length === 0) {
                        return (
                          <div className="text-slate-500 font-mono text-xs italic text-center py-10">
                            No tables found in this database schema.
                          </div>
                        );
                      }

                      return (
                        <div className="space-y-6">
                          {Object.entries(clientData.tables).map(([tableName, columns]: [string, any]) => (
                            <div key={tableName} className="border border-[#1e1735] bg-[#0c0a18] rounded-xl overflow-hidden shadow-inner">
                              {/* Table Header */}
                              <div className="px-4 py-3 bg-[#110e24] border-b border-[#1e1735] flex items-center justify-between">
                                <span className="font-mono font-black text-xs text-white">
                                  📁 {tableName}
                                </span>
                                <span className="text-[9px] font-mono text-purple-400 font-bold bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20">
                                  {columns.length} Columns
                                </span>
                              </div>
                              
                              {/* Table Columns List */}
                              <div className="divide-y divide-[#16122d]">
                                {columns.map(col => (
                                  <div key={col.name} className="px-4 py-3 flex items-center justify-between hover:bg-white/[0.02] transition-colors text-xs font-mono">
                                    <div className="flex items-center gap-3">
                                      <span className="font-bold text-slate-200">{col.name}</span>
                                      <span className="text-[9.5px] text-slate-500 bg-[#121020] px-1.5 py-0.2 rounded border border-white/5">{col.type}</span>
                                    </div>
                                    
                                    <div className="flex items-center gap-2">
                                      {col.pk && (
                                        <span className="text-[8px] font-black text-amber-400 bg-amber-500/10 px-1 rounded border border-amber-500/30">
                                          PK
                                        </span>
                                      )}
                                      {col.notnull && (
                                        <span className="text-[8px] font-black text-purple-400 bg-purple-500/10 px-1 rounded border border-purple-500/30">
                                          NOT NULL
                                        </span>
                                      )}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                      );
                    })()}
                  </>
                )}
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default DabStudio;
