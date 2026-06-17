import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
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
  LogOut
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import PipelinePulse from './PipelinePulse';
import NQuireLogo from './NQuireLogo';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

/* ── Derive up to 5 crisp, deterministic insights from result data ── */
const generateInsights = (headers, data) => {
  if (!headers?.length || !data?.length) return [];
  const insights = [];

  insights.push(`Query returned ${data.length} row${data.length !== 1 ? 's' : ''} across ${headers.length} column${headers.length !== 1 ? 's' : ''}.`);

  const numericCols = headers.filter(h =>
    data.some(r => r[h] !== null && r[h] !== '' && !isNaN(Number(r[h])))
  );
  const labelCol = headers.find(h => !numericCols.includes(h));

  numericCols.slice(0, 2).forEach(col => {
    const vals = data.map(r => Number(r[col])).filter(v => !isNaN(v));
    if (!vals.length) return;
    const max = Math.max(...vals);
    const min = Math.min(...vals);
    const avg = (vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1);
    const maxRow = data.find(r => Number(r[col]) === max);
    if (labelCol && maxRow) {
      insights.push(`Highest ${col}: ${max} — "${maxRow[labelCol]}". Average across all: ${avg}.`);
    } else {
      insights.push(`${col} spans ${min} – ${max} with average ${avg}.`);
    }
  });

  if (numericCols.length > 0) {
    const col = numericCols[0];
    const sorted = [...data].sort((a, b) => Number(b[col]) - Number(a[col]));
    const top = sorted.slice(0, Math.min(3, sorted.length));
    if (labelCol && top.length > 1) {
      insights.push(`Top ${top.length} by ${col}: ${top.map(r => `${r[labelCol]} (${r[col]})`).join(', ')}.`);
    }
  }

  const nullCols = headers.filter(h => data.some(r => r[h] === null || r[h] === '' || r[h] === 'NULL'));
  if (nullCols.length) {
    insights.push(`Missing/null values detected in: ${nullCols.slice(0, 3).join(', ')}.`);
  }

  return insights.slice(0, 5);
};

/* ── Inline SVG bar chart for the insights panel ── */
const InsightsChart = ({ headers, data }) => {
  const numericCols = headers?.filter(h =>
    data?.some(r => r[h] !== null && !isNaN(Number(r[h])))
  ) || [];
  const labelCol = headers?.find(h => !numericCols.includes(h));
  const valCol = numericCols.find(c => !c.toLowerCase().endsWith('_id') && c.toLowerCase() !== 'id') || numericCols[0];

  if (!valCol || !data?.length) return (
    <div className="flex items-center justify-center h-36 text-slate-600 text-[11px] font-mono">
      No numeric column available to chart.
    </div>
  );

  const rows = data.map((r, i) => ({
    label: labelCol ? String(r[labelCol] ?? `Row ${i + 1}`).slice(0, 14) : `Row ${i + 1}`,
    val: Number(r[valCol]) || 0,
  }));
  const maxVal = Math.max(...rows.map(r => r.val), 1);
  const W = 480, H = 160, ml = 40, mb = 32, mt = 12, mr = 12;
  const iw = W - ml - mr, ih = H - mt - mb;
  const bw = Math.max(8, Math.min(36, (iw / rows.length) * 0.55));

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" preserveAspectRatio="xMidYMid meet">
      <defs>
        <linearGradient id="ig" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#5fa8d8" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#3db8b0" stopOpacity="0.3" />
        </linearGradient>
      </defs>
      {[0, 0.5, 1].map((r, i) => {
        const y = mt + ih - r * ih;
        return (
          <g key={i} opacity="0.35">
            <line x1={ml} y1={y} x2={ml + iw} y2={y} stroke="#5fa8d8" strokeWidth="0.5" strokeDasharray="3,3" />
            <text x={ml - 4} y={y + 3} textAnchor="end" fill="#4e6880" fontSize="8" fontFamily="monospace">
              {Math.round(r * maxVal)}
            </text>
          </g>
        );
      })}
      {rows.map((r, i) => {
        const x = ml + (i * iw / rows.length) + (iw / rows.length - bw) / 2;
        const bh = (r.val / maxVal) * ih;
        const y = mt + ih - bh;
        return (
          <g key={i}>
            <rect x={x} y={y} width={bw} height={bh} fill="url(#ig)" rx="2" />
            <text x={x + bw / 2} y={mt + ih + 14} textAnchor="middle" fill="#4e6880" fontSize="8" fontFamily="monospace">
              {r.label.length > 10 ? r.label.slice(0, 9) + '…' : r.label}
            </text>
          </g>
        );
      })}
      <line x1={ml} y1={mt} x2={ml} y2={mt + ih} stroke="#2c3e55" strokeWidth="1" />
      <line x1={ml} y1={mt + ih} x2={ml + iw} y2={mt + ih} stroke="#2c3e55" strokeWidth="1" />
    </svg>
  );
};

const getComplexityBadge = (complexity, type, score) => {
  const displayScore = score > 0 ? score.toFixed(2) : null;
  const displayType = type || (complexity ? String(complexity).toUpperCase() : 'UNCLASSIFIED');

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
  running:  { ring: 'border-blue-400 shadow-[0_0_12px_rgba(59,130,246,0.3)]', bg: 'bg-blue-500/10', text: 'text-blue-400', dot: 'bg-blue-400 animate-pulse' },
  success:  { ring: 'border-emerald-500/50', bg: 'bg-emerald-500/10 border border-emerald-500/20', text: 'text-emerald-400', dot: 'bg-emerald-400' },
  warning:  { ring: 'border-amber-500/50', bg: 'bg-amber-500/10 border border-amber-500/20', text: 'text-amber-400', dot: 'bg-amber-400' },
  error:    { ring: 'border-rose-500/50', bg: 'bg-rose-500/10 border border-rose-500/20', text: 'text-rose-500', dot: 'bg-rose-500' }
};

const FlowParticle = ({ active, themeColor = 'blue' }) => (
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

const Connector = ({ active, themeColor = 'blue' }) => (
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
  if (p.includes("initialize") || p.includes("initializing")) return 0;
  if (p.includes("pruning") || p.includes("linker") || p.includes("schema")) return 1;
  if (p.includes("route") || p.includes("strategy") || p.includes("dialect")) return 2;
  if (p.includes("generation") || p.includes("synthesis") || p.includes("sql")) return 3;
  if (p.includes("correct") || p.includes("repair") || p.includes("corrector")) return 4;
  if (p.includes("audit") || p.includes("validator") || p.includes("auditor")) return 5;
  if (p.includes("complete") || p.includes("finish") || p.includes("success")) return 6;
  return 0;
};

const ArchitectureFlow = ({ diagnoseData, currentStatus, themeColor = 'blue' }) => {
  const [expandedNode, setExpandedNode] = useState(null);
  const consoleEndRef = useRef(null);
  const liveSteps = diagnoseData?.live_steps || [];

  useEffect(() => {
    if (consoleEndRef.current) {
      consoleEndRef.current.scrollIntoView({ behavior: 'smooth' });
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
                if (idx < activeIndex) {
                  status = 'success';
                } else if (idx === activeIndex) {
                  status = 'running';
                } else {
                  status = 'pending';
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

                    <p className="text-[10px] text-slate-400 leading-relaxed font-sans mt-1.5 line-clamp-2 hover:line-clamp-none transition-all font-medium">
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
              <span className="text-[9px] font-mono text-blue-400 animate-pulse flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-ping" />
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
            <div className="flex-1 overflow-y-auto p-4 space-y-2 scrollbar-thin scrollbar-thumb-slate-800 scrollbar-track-transparent">
              {liveSteps.map((st, idx) => {
                let textColor = 'text-slate-300';
                if (st.type === 'success') textColor = 'text-emerald-400';
                else if (st.type === 'warn' || st.type === 'warning') textColor = 'text-amber-400';
                else if (st.type === 'error') textColor = 'text-rose-400';
                else if (st.type === 'start') textColor = 'text-blue-400 font-bold';

                return (
                  <div key={idx} className="flex items-start gap-2 leading-relaxed select-text font-mono text-[10.5px] text-left">
                    <span className="text-slate-600 shrink-0 select-none">[{st.time}]</span>
                    <span className={textColor}>{st.text}</span>
                  </div>
                );
              })}
              <div ref={consoleEndRef} />
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

const SpiderStudio = ({ onBack, onHome, autoOpenDetails, clearAutoOpenDetails, user, onLogout }) => {
  const [currentView, setCurrentView] = useState('dashboard'); // 'dashboard' | 'database'
  const [metrics, setMetrics] = useState(null);
  const [databases, setDatabases] = useState([]);
  const [selectedDb, setSelectedDb] = useState(null);
  const [dbResults, setDbResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [dateFilter, setDateFilter] = useState('all');
  const [allDates, setAllDates] = useState([]);
  const [recentRuns, setRecentRuns] = useState([]);
  const [runningInstances, setRunningInstances] = useState({});
  const [runningDbs, setRunningDbs] = useState({});

  // Modals & Drawers
  const [selectedDetails, setSelectedDetails] = useState(null);
  const [detailsTab, setDetailsTab] = useState('sql');
  const [copiedType, setCopiedType] = useState(null);
  const [showMetricModal, setShowMetricModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
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
  const [spideyQuip, setSpideyQuip] = useState("Crawling Snowflake schemas... 🕵️");

  // Active Runs session
  const [activeSession, setActiveSession] = useState<{
    running: boolean; total: number; completed: number;
    run_date: string; pct: number; running_tasks: string[];
  } | null>(null);
  const sessionPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const liveEsRef = useRef(null);

  const spideyMascotQuotes = [
    "Crawling Snowflake schemas... no bugs found! 🕵️",
    "Pruning 50,000 columns before breakfast! ☕",
    "Did someone say INNER JOIN? 🕷️",
    "Zero-knowledge identifier rules active! 🛡️",
    "Self-correcting your syntax errors... ✨",
    "Data IQ probe parity match 1.000! 🎯",
    "All identifiers properly FQN escaped! 🚀"
  ];

  // Fetch dates on mount
  useEffect(() => {
    fetchDates();
    const ticker = setInterval(() => {
      setSpideyQuip(spideyMascotQuotes[Math.floor(Math.random() * spideyMascotQuotes.length)]);
    }, 9000);
    return () => clearInterval(ticker);
  }, []);

  // Fetch metrics and databases when date filter changes
  useEffect(() => {
    fetchInitialData();
    if (selectedDb) {
      fetchResults(selectedDb);
    }
  }, [dateFilter]);

  // Sync run/evaluate tickers
  useEffect(() => {
    let isMounted = true;
    let timer: any;
    const loop = async () => {
      if (!isMounted) return;
      await checkGlobalRunStatus();
      if (isMounted) timer = setTimeout(loop, 5000);
    };
    loop();
    return () => { isMounted = false; clearTimeout(timer); stopSessionPoll(); };
  }, [dateFilter]);

  // Auto-open details when navigated deep-link from global tasks panel
  useEffect(() => {
    if (autoOpenDetails && autoOpenDetails.project === 'spider') {
      const { db, id } = autoOpenDetails;
      setSelectedDb(db);
      setCurrentView('database');
      fetchInstanceDetails(db, id);
      clearAutoOpenDetails();
    }
  }, [autoOpenDetails]);

  useEffect(() => {
    return () => { liveEsRef.current?.close(); };
  }, []);

  // SSE-driven live execution details (replaces 1.5 s polling)
  useEffect(() => {
    if (!selectedDetails || selectedDetails.status !== 'running') return;

    const db = selectedDetails.db;
    const id = selectedDetails.id;
    liveEsRef.current = new EventSource(`${API_BASE}/stream/${db}/${id}`);

    liveEsRef.current.onmessage = (e) => {
      const data = JSON.parse(e.data);
      setSelectedDetails(prev => {
        if (!prev || prev.id !== id) return prev;
        return {
          ...prev,
          status: data.status,
          diagnoseData: {
            ...prev.diagnoseData,
            current_phase: data.current_phase,
            live_steps: data.steps,
            elapsed_seconds: data.elapsed_seconds,
          }
        };
      });
    };

    liveEsRef.current.addEventListener('done', () => {
      liveEsRef.current?.close();
      setRunningInstances(prev => { const next = { ...prev }; delete next[id]; return next; });
      setTimeout(() => {
        fetchInstanceDetails(db, id);
        handleRefresh();
      }, 500);
    });

    liveEsRef.current.onerror = () => liveEsRef.current?.close();

    return () => liveEsRef.current?.close();
  }, [selectedDetails?.id, selectedDetails?.status]);

  const fetchDates = async () => {
    try {
      const res = await axios.get(`${API_BASE}/results/dates`);
      setAllDates(res.data.spider || []);
    } catch (err) {
      console.error("Failed to load execution dates", err);
    }
  };

  const fetchInitialData = async (force: boolean = false, forceDate?: string) => {
    const activeDate = forceDate || dateFilter;
    setLoading(true);
    try {
      const [metricsRes, dbsRes, recentRes] = await Promise.all([
        axios.get(`${API_BASE}/metrics?date=${activeDate}${force ? '&force=true' : ''}`),
        axios.get(`${API_BASE}/databases?date=${activeDate}${force ? '&force=true' : ''}`),
        axios.get(`${API_BASE}/results/recent?limit=12&date=${activeDate}${force ? '&force=true' : ''}`)
      ]);
      setMetrics(metricsRes.data);
      setDatabases(dbsRes.data);
      setRecentRuns(recentRes.data);
    } catch (err) {
      console.error("Failed to load initial Spider metrics", err);
    } finally {
      setLoading(false);
    }
  };

  const checkGlobalRunStatus = async () => {
    const today = new Date().toISOString().split('T')[0];
    if (dateFilter !== 'all' && dateFilter !== today) {
        setIsGlobalRunning(false);
        setRunningInstances({});
        setActiveSession(null);
        return;
    }

    try {
      const res = await axios.get(`${API_BASE}/status`, { timeout: 4000 });
      const count = res.data.count || 0;
      const session = res.data.session || null;
      const isRunning = count > 0 || (session && session.running);
      
      setIsGlobalRunning(isRunning);
      setActiveSession(session);
      
      // Sync running status of individual instances
      if (res.data.running) {
        const active = {};
        res.data.running.forEach(t => { active[t] = true; });
        setRunningInstances(active);
      } else {
        setRunningInstances({});
      }
    } catch (err) {
      console.error("Failed to sync global run status", err);
    }
  };

  const fetchResults = async (dbName) => {
    setSelectedDb(dbName);
    setCurrentView('database');
    try {
      const res = await axios.get(`${API_BASE}/results/${dbName}?date=${dateFilter}`);
      setDbResults(res.data);
    } catch (err) {
      console.error(`Failed to load results for ${dbName}`, err);
    }
  };

  const handleRefresh = async () => {
    await fetchDates();
    await fetchInitialData(true);
    if (selectedDb) {
      await fetchResults(selectedDb);
    }
  };

  const handleDeleteRun = () => {
    setShowDeleteModal(true);
  };

  const confirmDeleteRun = async () => {
    try {
      await axios.delete(`${API_BASE}/runs/${dateFilter}`);
      
      const res = await axios.get(`${API_BASE}/results/dates`);
      const newDates = res.data.spider || [];
      setAllDates(newDates);
      
      let fallbackDate = 'all';
      if (newDates.length > 0) {
        fallbackDate = [...newDates].sort().reverse()[0];
      }
      
      setDateFilter(fallbackDate);
      setShowDeleteModal(false);
      
      // Manually refresh data to instantly reflect the new active date since state update is asynchronous
      await fetchInitialData(true, fallbackDate);
      if (selectedDb) {
        try {
          const resDb = await axios.get(`${API_BASE}/results/${selectedDb}?date=${fallbackDate}`);
          setDbResults(resDb.data);
        } catch (_) {}
      }
    } catch (err) {
      console.error("Failed to delete run", err);
      alert(err.response?.data?.error || 'Failed to delete run');
    }
  };

  const handleRunSingle = async (instanceId) => {
    setRunningInstances(prev => ({ ...prev, [instanceId]: true }));
    setSelectedDetails({
      id: instanceId,
      db: selectedDb,
      status: 'running',
      diagnoseData: {
        current_phase: 'Initializing Agent Orchestrator...',
        live_steps: []
      }
    });
    setDetailsTab('flow');
    try {
      await axios.post(`${API_BASE}/run_instance/${instanceId}`);
    } catch (err) {
      console.error("Failed to trigger single run", err);
      setRunningInstances(prev => {
        const next = { ...prev };
        delete next[instanceId];
        return next;
      });
      setSelectedDetails(prev => prev && prev.id === instanceId ? { ...prev, status: 'error' } : prev);
    }
  };

  const handleRunDb = async (dbName) => {
    setRunningDbs(prev => ({ ...prev, [dbName]: true }));
    try {
      await axios.post(`${API_BASE}/run/${dbName}?workers=4`);
      setTimeout(handleRefresh, 1500);
    } catch (err) {
      console.error(`Failed to run pipeline for ${dbName}`, err);
    } finally {
      setRunningDbs(prev => ({ ...prev, [dbName]: false }));
    }
  };

  const stopSessionPoll = () => {
    if (sessionPollRef.current) {
      clearTimeout(sessionPollRef.current as any);
      sessionPollRef.current = null;
    }
  };

  const startSessionPoll = () => {
    stopSessionPoll();
    const poll = async () => {
      try {
        const res = await axios.get(`${API_BASE}/run/session`);
        setActiveSession(res.data);
        if (!res.data.running) {
          stopSessionPoll();
          setIsGlobalRunning(false);
          setTimeout(handleRefresh, 800);
          return;
        }
      } catch (err) {
        console.error("Session poll error", err);
      }
      sessionPollRef.current = setTimeout(poll, 2000) as any;
    };
    poll();
  };

  const triggerGlobalRun = async () => {
    try {
      // Optimistically wipe dashboard metrics and database progress
      setMetrics({ total_queries: 0, evaluated: 0, passed: 0, failed: 0, pass_at_1_pct: '0.0%', avg_latency: '0.0s', avg_tokens_per_agent: '0', total_cost: '$0.0000' });
      setDbResults([]);
      setAllInstanceResults([]);
      setDatabases(prev => prev.map(db => ({ ...db, results_count: 0, error_count: 0, status: 'pending' })));

      await axios.post(`${API_BASE}/run_all`, null, { params: { scope: 'all' } });

      const today = new Date().toISOString().split('T')[0];
      setDateFilter(today);
      if (!allDates.includes(today)) {
        setAllDates(prev => [today, ...prev]);
      }
      setTimeout(handleRefresh, 1500);
    } catch (err) {
      console.error("Failed to trigger global run", err);
    }
  };

  const handleStopGlobalRun = async () => {
    try {
      await axios.post(`${API_BASE}/stop`);
      setTimeout(handleRefresh, 1000);
    } catch (err) {
      console.error("Failed to stop Spider run", err);
    }
  };



  const triggerGlobalAudit = async () => {
    try {
      await axios.post(`${API_BASE}/evaluate/all`);
      setTimeout(handleRefresh, 1500);
    } catch (err) {
      console.error("Failed to trigger global audit", err);
    }
  };

  const handleOpenMetricModal = async (filter) => {
    setActiveMetricFilter(filter);
    setShowMetricModal(true);
    setLoadingMetricInstances(true);
    try {
      const res = await axios.get(`${API_BASE}/results/all?date=${dateFilter}`);
      setAllInstanceResults(res.data);
    } catch (err) {
      console.error("Failed to load instance list", err);
    } finally {
      setLoadingMetricInstances(false);
    }
  };

  const fetchInstanceDetailsFromModal = async (dbName, instanceId) => {
    setShowMetricModal(false);
    fetchInstanceDetails(dbName, instanceId);
  };

  const fetchInstanceDetails = async (dbName, instanceId, question = null) => {
    const isCurrentlyRunning = runningInstances[instanceId];
    setSelectedDetails({
      id: instanceId,
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
        axios.get(`${API_BASE}/details/${dbName}/${instanceId}?date=${dateFilter}`),
        axios.get(`${API_BASE}/diagnose/${dbName}/${instanceId}?date=${dateFilter}`).catch(err => {
          console.error("Failed to fetch diagnostics for details", err);
          return { data: null };
        })
      ]);
      setSelectedDetails(prev => ({
        ...prev,
        logContent: detailsRes.data.log_content,
        sqlContent: detailsRes.data.sql_content,
        csvHeaders: detailsRes.data.csv_headers,
        csvData: detailsRes.data.csv_data,
        executedAt: detailsRes.data.executed_at,
        totalTokens: detailsRes.data.total_tokens,
        cost: detailsRes.data.cost,
        complexityType: detailsRes.data.complexity_type,
        complexityScore: detailsRes.data.complexity_score,
        diagnoseData: diagnoseRes.data
      }));
    } catch (err) {
      console.error("Failed to load run details", err);
    } finally {
      setLoadingDetails(false);
    }
  };

  const handleCopy = (text, type) => {
    navigator.clipboard.writeText(text);
    setCopiedType(type);
    setTimeout(() => setCopiedType(null), 2000);
  };

  const handleDiagnose = async (dbName, instanceId) => {
    setLoadingDiagnose(true);
    setShowDiagnoseDrawer(true);
    setDiagnoseData(null);
    setFixResult(null);
    setFixFeedback('');
    try {
      const res = await axios.get(`${API_BASE}/diagnose/${dbName}/${instanceId}`);
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
      const res = await axios.post(`${API_BASE}/fix_issues/${diagnoseData.db_name}/${diagnoseData.instance_id}`);
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
      const res = await axios.post(`${API_BASE}/accept_fix/${diagnoseData.db_name}/${diagnoseData.instance_id}`, {
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
      await axios.post(`${API_BASE}/reject_fix/${diagnoseData.db_name}/${diagnoseData.instance_id}`, {
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
    if (status === 'success') return <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />;
    if (status === 'empty') return <Activity className="w-4 h-4 text-amber-400 shrink-0" />;
    if (status === 'error') return <XCircle className="w-4 h-4 text-rose-500 shrink-0" />;
    if (status === 'running') return <Activity className="w-4 h-4 text-blue-400 animate-spin shrink-0" />;
    return <Layers className="w-4 h-4 text-slate-500 shrink-0" />;
  };

  const filteredDatabases = databases.filter(db =>
    db.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredMetricInstances = allInstanceResults.filter(inst => {
    if (activeMetricFilter === 'succeeded' && inst.status !== 'success') return false;
    if (activeMetricFilter === 'errored' && inst.status !== 'error') return false;
    if (activeMetricFilter === 'gold' && inst.gold_status !== 'gold_pass') return false;
    if (metricSearchQuery) {
      return inst.id.toLowerCase().includes(metricSearchQuery.toLowerCase()) ||
             inst.db.toLowerCase().includes(metricSearchQuery.toLowerCase());
    }
    return true;
  });

  return (
    <div className="flex h-screen w-full overflow-hidden bg-[#070709] text-slate-200 font-sans selection:bg-blue-500/30 selection:text-white">
      {/* Sidebar Navigation */}
      <aside className="w-16 lg:w-56 border-r border-[#1a1a22] bg-[#0c0c10] flex flex-col p-4 gap-6 shrink-0 z-20 shadow-2xl animate-fadeIn">
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-3 px-1">
            <NQuireLogo size={32} showName nameSize="text-xs" onClick={onHome} />
          </div>

          <button
            onClick={onBack}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#14141d] border border-[#262638] hover:border-amber-500/50 hover:bg-[#1a1a26] text-slate-400 hover:text-amber-400 transition-all font-bold text-[11px] font-mono justify-center w-full shadow-md shrink-0"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span className="hidden lg:inline">Switch Project</span>
          </button>
        </div>

        <nav className="flex flex-col gap-1 flex-1">
          <button
            onClick={() => setCurrentView('dashboard')}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all font-bold text-xs tracking-tight ${currentView === 'dashboard' ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20 shadow-inner' : 'hover:bg-white/[0.04] text-slate-400 hover:text-slate-200'}`}
          >
            <BarChart3 className="w-4 h-4 shrink-0" />
            <span className="hidden lg:block truncate">Audit Dashboard</span>
          </button>
          <button
            onClick={() => {
              if (databases.length > 0) fetchResults(selectedDb || databases[0].name);
              else setCurrentView('database');
            }}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all font-bold text-xs tracking-tight ${currentView === 'database' ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20 shadow-inner' : 'hover:bg-white/[0.04] text-slate-400 hover:text-slate-200'}`}
          >
            <Terminal className="w-4 h-4 shrink-0" />
          </button>
          
          {/* Active Runs Sidebar Widget */}
          {Object.keys(runningInstances).length > 0 && (
            <div className="hidden lg:block mt-6 pt-6 border-t border-[#1a1a22] animate-fadeIn">
              <div className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-widest mb-3 px-3 flex items-center justify-between">
                <span>Active Runs</span>
                <span className="bg-blue-500/20 text-blue-400 px-1.5 py-0.5 rounded animate-pulse">{Object.keys(runningInstances).length}</span>
              </div>
              <div className="space-y-1.5 px-2 max-h-[200px] overflow-y-auto no-scrollbar">
                {Object.keys(runningInstances).map(qkey => (
                  <div key={qkey} className="flex items-center gap-2 text-[10px] font-mono text-slate-300 bg-[#12101e] border border-[#231d36] rounded p-1.5 shadow">
                    <Activity className="w-3 h-3 text-blue-400 animate-spin shrink-0" />
                    <span className="truncate" title={qkey}>{qkey}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </nav>

        {/* Spidey Mascot Quote Card */}
        <div className="hidden lg:flex flex-col my-auto p-3.5 bg-[#0e0e14] rounded-2xl border border-[#20202a] shadow-md relative overflow-hidden group select-none transition-all hover:border-blue-500/40">
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-blue-500 via-indigo-500 to-cyan-500 animate-pulse" />
          <div className="relative mb-3 bg-[#14141e] border border-[#252535] p-2.5 rounded-xl rounded-bl-none shadow-lg">
            <div className="text-[11px] font-mono text-slate-300 leading-tight min-h-[28px] flex items-center">
              {spideyQuip}
            </div>
            <div className="absolute -bottom-2 left-3 w-0 h-0 border-t-8 border-t-[#14141e] border-r-8 border-r-transparent border-l-0" />
          </div>
          <div className="flex items-center justify-center py-2">
            <Sparkles className="w-6 h-6 text-blue-400 animate-pulse" />
          </div>
        </div>

        {/* User Profile */}
        {user && (
          <div className="mt-auto pt-3 border-t border-[#1a1a22]">
            <div className="flex items-center gap-2.5 px-1 py-2 rounded-xl hover:bg-white/[0.04] transition-all group">
              {user.picture ? (
                <img src={user.picture} alt={user.name} className="w-7 h-7 rounded-full shrink-0 ring-1 ring-blue-500/40" referrerPolicy="no-referrer" />
              ) : (
                <div className="w-7 h-7 rounded-full bg-blue-500/20 border border-blue-500/30 shrink-0 flex items-center justify-center text-[11px] font-bold text-blue-400">
                  {(user.name || user.email || '?')[0].toUpperCase()}
                </div>
              )}
              <div className="hidden lg:flex flex-col min-w-0 flex-1">
                <span className="text-[11px] font-bold text-slate-200 truncate leading-tight">{user.name || 'User'}</span>
                <span className="text-[10px] text-slate-500 truncate leading-tight">{user.email}</span>
              </div>
              <button
                onClick={onLogout}
                title="Sign out"
                className="hidden lg:flex shrink-0 p-1 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-400/10 transition-all"
              >
                <LogOut className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}
      </aside>

      {/* Main Panel */}
      <main className="flex-1 flex flex-col min-w-0 bg-[#070709] relative overflow-hidden">
        {/* Header Bar */}
        <header className="h-16 border-b border-[#14141b] bg-[#09090d]/80 backdrop-blur-lg flex items-center justify-between px-6 z-10 shrink-0 gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <span className="text-sm font-mono font-bold text-white tracking-tight truncate">
              {currentView === 'dashboard' && 'Spider2-Lite · Forensic Telemetry & Audit Matrix'}
              {currentView === 'database' && `Spider2-Lite · Dataset: ${selectedDb}`}
            </span>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {/* Date filter select */}
            <div className="flex items-center gap-1.5 bg-[#0e0e14] border border-[#222232] rounded-lg px-2.5 py-1.5 text-xs font-mono">
              <Filter className="w-3.5 h-3.5 text-blue-400" />
              <select
                value={dateFilter}
                onChange={e => setDateFilter(e.target.value)}
                className="bg-transparent border-none text-slate-200 font-bold focus:outline-none cursor-pointer"
              >
                <option value="all">All Dates</option>
                {allDates.map(d => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </div>

            <button
              onClick={handleRefresh}
              className="p-1.5 rounded-lg bg-[#0e0e14] border border-[#222232] hover:bg-[#141420] text-slate-400 hover:text-white transition-all shadow-sm"
              title="Refresh Current Dashboard"
            >
              <RefreshCw className="w-4 h-4" />
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
                  onClick={() => triggerGlobalRun()}
                  className="px-3 py-1.5 rounded-lg font-mono font-bold text-xs shadow-lg transition-all border flex items-center gap-1.5 bg-emerald-600/10 text-emerald-400 border-emerald-500/30 hover:bg-emerald-600/20"
                >
                  <Play className="w-3.5 h-3.5" />
                  RUN ALL EVALS
                </button>
              )
            )}
            
            {currentView === 'dashboard' && (
              <button
                onClick={() => triggerGlobalAudit()}
                disabled={isGlobalRunning}
                className={`px-3 py-1.5 rounded-lg font-mono font-bold text-xs shadow-lg transition-all border flex items-center gap-1.5 ${isGlobalRunning ? 'bg-slate-800 border-slate-700 text-slate-500 cursor-not-allowed' : 'bg-violet-600/10 text-violet-400 border-violet-500/30 hover:bg-violet-600/20'}`}
              >
                <Trophy className="w-3.5 h-3.5" />
                AUDIT ALL
              </button>
            )}
          </div>
        </header>

        {/* Global Progress Bar */}
        {activeSession && activeSession.running && activeSession.total > 0 && (
          <div className="w-full bg-[#0a0a0f] border-b border-[#14141b] px-6 py-2 flex items-center gap-4 shrink-0 z-10 shadow-md">
            <div className="flex-1 max-w-2xl flex items-center gap-3">
              <div className="text-[10px] font-mono font-bold text-emerald-400 whitespace-nowrap bg-emerald-500/10 px-2 py-1 rounded border border-emerald-500/20 shadow-inner">
                {Math.round((activeSession.completed / activeSession.total) * 100)}% COMPLETED
              </div>
              <div className="flex-1 h-2 bg-[#1a1a24] rounded-full overflow-hidden border border-[#2a2a35]">
                <div 
                  className="h-full bg-gradient-to-r from-emerald-600 via-emerald-400 to-emerald-300 transition-all duration-1000 shadow-[0_0_12px_rgba(52,211,153,0.5)]" 
                  style={{ width: `${(activeSession.completed / activeSession.total) * 100}%` }}
                />
              </div>
              <div className="text-[10px] font-mono text-slate-400 whitespace-nowrap font-medium">
                {activeSession.completed} / {activeSession.total}
              </div>
            </div>
          </div>
        )}

        {/* Scrollable View Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 no-scrollbar">
          {loading ? (
            <div className="h-full flex flex-col items-center justify-center gap-3 text-blue-400 font-mono animate-pulse">
              <Activity className="w-10 h-10 animate-spin" />
              <p className="text-sm font-black">Syncing Spider telemetry standards...</p>
            </div>
          ) : (
            currentView === 'dashboard' ? (
              <>
                {/* Metrics Grid */}
                <section className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3.5">
                  {metrics && (
                    <>
                      {[
                        { label: 'TOTAL PROCESSED', value: metrics.total_processed, color: 'blue', type: 'total', sub: 'RUNS' },
                        { label: 'SUCCEEDED (CSV)', value: metrics.succeeded_count, color: 'emerald', type: 'succeeded', sub: 'VALID' },
                        { label: 'ERRORED', value: metrics.errored_count, color: 'rose', type: 'errored', sub: 'FAILED' },
                        { label: 'GOLD ACCURACY', value: metrics.gold_accuracy, color: 'indigo', type: 'gold', sub: `${metrics.gold_succeeded_count} PASS` },
                        { label: 'AVG LATENCY', value: metrics.avg_latency, color: 'cyan', type: 'total', sub: 'PER RUN' },
                        { label: 'AVG TOKENS', value: String(metrics.avg_tokens_per_agent || '0 tokens').replace(' tokens', ''), color: 'fuchsia', type: 'total', sub: 'PER AGENT' },
                        { label: 'TOTAL COST ($)', value: String(metrics.total_cost || '$0.0000').replace('$', ''), color: 'amber', type: 'total', sub: 'ESTIMATED' },
                        { label: 'LLM CALLS', value: metrics.llm_calls, color: 'violet', type: 'total', sub: 'TOTAL' }
                      ].map(m => (
                        <div
                          key={m.label}
                          onClick={() => handleOpenMetricModal(m.type)}
                          className="bg-[#101014] border border-[#1f1f27] hover:border-blue-500/50 p-3.5 rounded-xl shadow-sm relative overflow-hidden flex flex-col justify-between group cursor-pointer transition-all hover:scale-[1.02]"
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
                    </>
                  )}
                </section>

                {/* Databases and Recent Runs */}
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 items-start">
                  {/* Left Column: Database Cards */}
                  <section className="space-y-4">
                    <header className="flex justify-between items-center">
                      <div className="flex items-center gap-2">
                        <Database className="w-5 h-5 text-blue-400" />
                        <h2 className="text-sm font-mono font-bold text-white uppercase tracking-wider">Dialect Databases</h2>
                      </div>
                      <div className="relative w-48">
                        <Search className="absolute left-2.5 top-2 w-3.5 h-3.5 text-slate-500" />
                        <input
                          type="text"
                          placeholder="Search database..."
                          value={searchQuery}
                          onChange={e => setSearchQuery(e.target.value)}
                          className="w-full pl-8 pr-3 py-1 bg-[#101014] border border-[#222232] rounded-lg text-xs font-mono text-white focus:outline-none focus:border-blue-500"
                        />
                      </div>
                    </header>

                    <div className="space-y-2 max-h-[460px] overflow-y-auto pr-1 no-scrollbar">
                      {filteredDatabases.map((db) => {
                        const totalProcessed = db.results_count + db.empty_count + db.error_count;
                        const successPct = db.total_questions ? (db.results_count / db.total_questions) * 100 : 0;
                        const emptyPct = db.total_questions ? (db.empty_count / db.total_questions) * 100 : 0;
                        const errorPct = db.total_questions ? (db.error_count / db.total_questions) * 100 : 0;

                        return (
                          <div
                            key={db.name}
                            onClick={() => fetchResults(db.name)}
                            className={`group p-3.5 rounded-lg bg-[#0e0e14]/90 border border-[#1b1b26] hover:border-blue-500/40 hover:bg-[#121217] transition-all cursor-pointer flex items-center justify-between ${selectedDb === db.name ? 'border-blue-500 bg-blue-500/5 shadow-[0_0_15px_rgba(59,130,246,0.15)]' : ''}`}
                          >
                            <div className="flex items-center gap-3 w-full pr-4">
                              <div className={`w-8 h-8 shrink-0 rounded-md flex items-center justify-center font-bold text-xs ${db.status === 'completed' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-slate-800 text-slate-400 border border-slate-700/20'}`}>
                                {db.status === 'completed' ? <CheckCircle2 className="w-4 h-4" /> : <Database className="w-4 h-4" />}
                              </div>

                              <div className="flex-1 min-w-0">
                                <div className="flex items-center justify-between gap-2">
                                  <h3 className="font-mono font-bold text-xs truncate text-white group-hover:text-blue-400 transition-colors">
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

                                <div className="mt-2 w-full h-1 bg-[#0c0c10] rounded-full overflow-hidden flex mb-1.5">
                                  <div style={{ width: `${successPct}%` }} className="h-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)] transition-all"></div>
                                  <div style={{ width: `${emptyPct}%` }} className="h-full bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.5)] transition-all"></div>
                                  <div style={{ width: `${errorPct}%` }} className="h-full bg-rose-500 shadow-[0_0_8px_rgba(239,68,68,0.5)] transition-all"></div>
                                </div>

                                <div className="flex items-center justify-between text-[10px] font-mono text-slate-400">
                                  <span className="text-slate-500">Done: {totalProcessed}/{db.total_questions}</span>
                                  <div className="flex items-center gap-2 font-bold">
                                    <span className="text-emerald-400">{successPct.toFixed(0)}%</span>
                                    <span className="text-amber-400">{emptyPct.toFixed(0)}%</span>
                                    <span className="text-rose-500">{errorPct.toFixed(0)}%</span>
                                  </div>
                                </div>
                              </div>
                            </div>

                            <button
                              className={`p-2 shrink-0 rounded-md bg-[#181822] border border-[#262632] hover:bg-blue-600 hover:text-white transition-all ${runningDbs[db.name] ? 'animate-spin bg-blue-500 text-white' : 'text-slate-300'}`}
                              onClick={(e) => { e.stopPropagation(); handleRunDb(db.name); }}
                              title="Execute Batch Run"
                            >
                              {runningDbs[db.name] ? <Activity className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  </section>

                  {/* Right Column: Recent Runs */}
                  <section className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Clock className="w-5 h-5 text-blue-400" />
                        <h2 className="text-sm font-mono font-bold text-white uppercase tracking-wider">Recent Executions</h2>
                      </div>
                    </div>

                    <div className="bg-[#0e0e14] border border-[#1a1a24] rounded-xl overflow-hidden shadow-2xl">
                      <div className="max-h-[360px] overflow-y-auto divide-y divide-[#1e1e2c] no-scrollbar">
                        {recentRuns.length > 0 ? (
                          recentRuns.map(run => (
                            <div
                              key={run.id}
                              onClick={() => fetchInstanceDetails(run.db, run.id, run.question || null)}
                              className="p-3.5 flex items-center justify-between gap-4 hover:bg-[#141420]/30 cursor-pointer transition-colors"
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
                            No recent execution runs found for this filter.
                          </div>
                        )}
                      </div>
                    </div>
                  </section>
                </div>
              </>
            ) : (
              /* Database Detail View */
              <div className="space-y-4">
                <header className="bg-[#101014] border border-[#1f1f27] p-4 rounded-xl flex items-center justify-between shadow-lg flex-wrap gap-3">
                  <div className="flex items-center gap-3 flex-wrap min-w-0">
                    <button
                      onClick={() => setCurrentView('dashboard')}
                      className="p-2 rounded-lg bg-[#181820] border border-[#262632] hover:bg-white/10 hover:text-white transition-all text-slate-400 font-mono text-xs flex items-center gap-1.5 font-bold shrink-0"
                    >
                      <ArrowLeft className="w-4 h-4" /> BACK
                    </button>
                    <div className="h-4 w-px bg-[#262632]" />
                    <Database className="w-5 h-5 text-blue-400 shrink-0" />
                    <h1 className="text-base font-mono font-black tracking-tight text-white flex items-center gap-2 flex-wrap min-w-0">
                      <span className="truncate">{selectedDb}</span>
                    </h1>
                  </div>

                  <div className="flex items-center gap-2 font-mono text-xs shrink-0">
                    <button
                      onClick={() => handleRunDb(selectedDb)}
                      disabled={runningDbs[selectedDb]}
                      className="px-3 py-1.5 rounded-lg bg-blue-600/10 text-blue-400 border border-blue-500/20 hover:bg-blue-600/20 font-bold transition-all shadow"
                    >
                      {runningDbs[selectedDb] ? 'RUNNING...' : 'RUN ALL PROBES'}
                    </button>
                  </div>
                </header>

                {/* Probe List Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
                  {dbResults.map(res => {
                    let statusColor = 'border-slate-800 text-slate-500';
                    if (res.status === 'success') statusColor = 'border-emerald-500 text-emerald-400';
                    else if (res.status === 'empty') statusColor = 'border-amber-500 text-amber-400';
                    else if (res.status === 'error') statusColor = 'border-rose-500 text-rose-500';

                    return (
                      <div
                        key={res.id}
                        onClick={() => fetchInstanceDetails(selectedDb, res.id, res.question || null)}
                        className={`bg-[#101014] border border-[#1f1f27] hover:border-blue-500/60 hover:bg-[#13131c] rounded-xl p-3.5 flex flex-col justify-between group cursor-pointer transition-all shadow-md relative overflow-hidden ${runningInstances[res.id] ? 'border-blue-500 shadow-[0_0_20px_rgba(59,130,246,0.2)]' : ''}`}
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
                            {res.status === 'success' || res.status === 'empty' ? (
                              <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded flex items-center gap-1 shrink-0 ${res.rows > 0 ? 'text-emerald-400 bg-emerald-500/10 border border-emerald-500/20' : 'text-amber-400 bg-amber-500/10 border border-amber-500/20'}`} title="Result Set Row Count">
                                <Database className="w-2.5 h-2.5 shrink-0" />
                                {res.rows} {res.rows === 1 ? 'Row' : 'Rows'}
                              </span>
                            ) : res.status === 'error' ? (
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
                              onClick={(e) => { e.stopPropagation(); fetchInstanceDetails(selectedDb, res.id, res.question || null); }}
                              className="p-1.5 rounded bg-[#181820] border border-[#262632] hover:bg-blue-600 hover:text-white transition-all text-slate-400"
                              title="Live Execution Audit Drawer"
                            >
                              <Activity className="w-3.5 h-3.5 text-blue-400 animate-pulse" />
                            </button>
                            <button
                              className={`p-1.5 rounded bg-[#181820] border border-[#262632] hover:bg-emerald-600 hover:text-white transition-all ${runningInstances[res.id] ? 'animate-spin bg-blue-500 text-white' : 'text-slate-300'}`}
                              onClick={(e) => { e.stopPropagation(); handleRunSingle(res.id); }}
                              disabled={runningInstances[res.id]}
                              title="Execute Single Instance"
                            >
                              {runningInstances[res.id] ? <Activity className="w-3.5 h-3.5 animate-pulse" /> : <Play className="w-3.5 h-3.5" />}
                            </button>
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
                                onClick={(e) => { e.stopPropagation(); handleDiagnose(selectedDb, res.id); }}
                              >
                                <ShieldAlert className="w-3 h-3 shrink-0" />
                                DIAGNOSE
                              </button>
                              <button
                                className="font-bold flex items-center gap-1 text-blue-400 hover:text-white bg-blue-500/10 hover:bg-blue-500 border border-blue-500/20 hover:border-blue-500 px-2 py-1 rounded transition-all"
                                onClick={(e) => { e.stopPropagation(); fetchInstanceDetails(selectedDb, res.id, res.question || null); }}
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
            )
          )}
        </div>
      </main>

      {/* Metric Detail Modal */}
      <AnimatePresence>
        {showMetricModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-6 select-none bg-black/60 backdrop-blur-sm">
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-[#0b0b0e] border border-[#1a1a24] rounded-2xl w-full max-w-4xl h-[80vh] flex flex-col overflow-hidden shadow-2xl relative"
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
                    className="w-full pl-9 pr-4 py-1.5 bg-[#0e0e14] border border-[#282838] rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>

              {/* Instance List */}
              <div className="flex-1 overflow-y-auto p-4 no-scrollbar">
                {loadingMetricInstances ? (
                  <div className="h-full flex flex-col items-center justify-center text-blue-400 font-mono animate-pulse">
                    <Activity className="w-8 h-8 animate-spin" />
                    <p className="text-xs font-bold mt-2">Aggregating benchmark forensic execution logs...</p>
                  </div>
                ) : filteredMetricInstances.length > 0 ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {filteredMetricInstances.map(inst => (
                      <div
                        key={inst.id}
                        onClick={() => fetchInstanceDetailsFromModal(inst.db, inst.id)}
                        className="bg-[#121217] border border-[#22222c] hover:border-blue-500/50 p-4 rounded-xl cursor-pointer transition-all hover:scale-[1.02] shadow-lg flex flex-col justify-between font-mono"
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
                          <span>{inst.corrections || 0} corrections</span>
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
          </div>
        )}
      </AnimatePresence>

      {/* Forensic Diagnostics Drawer */}
      <AnimatePresence>
        {selectedDetails && (
          <div className="fixed inset-0 z-50 flex justify-end select-none">
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setSelectedDetails(null)} />
            <motion.div
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ type: 'spring', damping: 26, stiffness: 220 }}
              className="relative w-full max-w-4xl bg-[#09090c] border-l border-[#1a1a24] h-full flex flex-col shadow-2xl z-10"
            >
              <header className="px-4 pt-4 pb-3 border-b border-[#1b1b26] bg-[#0c0c11] shrink-0">
                <div className="flex justify-between items-start">
                  <div className="flex items-start gap-3 min-w-0">
                    <Database className="w-5 h-5 text-blue-400 mt-0.5 shrink-0" />
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h2 className="font-mono font-black text-sm text-white">{selectedDetails.id}</h2>
                        <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider bg-[#1a1a28] px-2 py-0.5 rounded">{selectedDetails.db}</span>
                      </div>
                      {selectedDetails.question && (
                        <div className="flex items-start gap-1.5 mt-1.5">
                          <MessageSquare className="w-3 h-3 text-blue-400 shrink-0 mt-0.5" />
                          <p className="text-[12px] text-slate-300 leading-snug font-medium">{selectedDetails.question}</p>
                        </div>
                      )}
                    </div>
                  </div>
                  <button onClick={() => setSelectedDetails(null)} className="ml-3 p-1.5 rounded-lg bg-[#14141c] border border-[#252538] text-slate-400 hover:text-white transition-colors shrink-0">
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </header>

              {/* Sub-tabs */}
              <div className="flex border-b border-[#1f1f2e] bg-[#0c0c11] px-4 shrink-0 overflow-x-auto no-scrollbar">
                {[
                  { id: 'flow',     icon: <Sparkles    className="w-3 h-3 inline mr-1" />, label: 'FLOW'     },
                  { id: 'sql',      icon: <FileCode     className="w-3 h-3 inline mr-1" />, label: 'SQL'      },
                  { id: 'log',      icon: <Activity     className="w-3 h-3 inline mr-1" />, label: 'LOG'      },
                  { id: 'csv',      icon: <FileSpreadsheet className="w-3 h-3 inline mr-1" />, label: 'CSV'  },
                  { id: 'insights', icon: <Lightbulb   className="w-3 h-3 inline mr-1" />, label: 'INSIGHTS' },
                ].map(tab => (
                  <button
                    key={tab.id}
                    onClick={() => setDetailsTab(tab.id)}
                    className={`px-4 py-2.5 font-mono font-bold text-xs uppercase border-b-2 tracking-wider transition-all whitespace-nowrap ${detailsTab === tab.id ? 'border-blue-500 text-blue-400' : 'border-transparent text-slate-500 hover:text-slate-300'}`}
                  >
                    {tab.icon}{tab.label}
                  </button>
                ))}
              </div>

              {/* Drawer Content */}
              <div className="flex-1 overflow-auto p-6 no-scrollbar bg-[#07070a]">
                {loadingDetails ? (
                  <div className="h-full flex flex-col items-center justify-center text-blue-400 animate-pulse font-mono">
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
                        themeColor="blue"
                      />
                    )}
                    {detailsTab === 'sql' && (
                      <div className="space-y-4 h-full flex flex-col">
                        <div className="flex justify-between items-center">
                          <span className="text-[10px] font-mono text-slate-500 uppercase tracking-widest">Compiled SQL Query</span>
                          <button
                            onClick={() => handleCopy(selectedDetails.sqlContent, 'sql')}
                            className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#101017] border border-[#262638] text-slate-400 hover:text-white transition-colors text-[10px] font-mono font-bold"
                          >
                            {copiedType === 'sql' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                            {copiedType === 'sql' ? 'COPIED' : 'COPY'}
                          </button>
                        </div>
                        <pre className="flex-1 bg-black/40 border border-[#1a1a24] p-4 rounded-xl font-mono text-xs text-blue-300 overflow-auto whitespace-pre-wrap select-text selection:bg-blue-600/30">
                          {selectedDetails.sqlContent || 'No SQL generated for this run.'}
                        </pre>
                      </div>
                    )}

                    {detailsTab === 'log' && (
                      <div className="space-y-4 h-full flex flex-col">
                        <div className="flex justify-between items-center">
                          <span className="text-[10px] font-mono text-slate-500 uppercase tracking-widest">Execution Reasoning Logs</span>
                          <button
                            onClick={() => handleCopy(selectedDetails.logContent, 'log')}
                            className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#101017] border border-[#262638] text-slate-400 hover:text-white transition-colors text-[10px] font-mono font-bold"
                          >
                            {copiedType === 'log' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                            {copiedType === 'log' ? 'COPIED' : 'COPY'}
                          </button>
                        </div>
                        <pre className="flex-1 bg-black/40 border border-[#1a1a24] p-4 rounded-xl font-mono text-[11px] text-slate-300 overflow-auto whitespace-pre-wrap select-text selection:bg-blue-600/30">
                          {selectedDetails.logContent || 'No execution logs available.'}
                        </pre>
                      </div>
                    )}

                    {detailsTab === 'csv' && (
                      <div className="space-y-3 h-full flex flex-col">
                        <div className="flex items-center justify-between shrink-0">
                          <span className="text-[10px] font-mono text-slate-500 uppercase tracking-widest">Query Result Dataset</span>
                          <div className="flex items-center gap-1.5">
                            <button
                              onClick={() => {
                                if (!selectedDetails.csvHeaders?.length) return;
                                const rows = [selectedDetails.csvHeaders.join(','), ...(selectedDetails.csvData || []).map(r => selectedDetails.csvHeaders.map(h => {
                                  const v = String(r[h] ?? '');
                                  return v.includes(',') || v.includes('"') ? `"${v.replace(/"/g, '""')}"` : v;
                                }).join(','))].join('\n');
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
                                const rows = [selectedDetails.csvHeaders.join(','), ...(selectedDetails.csvData || []).map(r => selectedDetails.csvHeaders.map(h => {
                                  const v = String(r[h] ?? '');
                                  return v.includes(',') || v.includes('"') ? `"${v.replace(/"/g, '""')}"` : v;
                                }).join(','))].join('\n');
                                const blob = new Blob([rows], { type: 'text/csv' });
                                const url = URL.createObjectURL(blob);
                                const a = document.createElement('a');
                                a.href = url; a.download = `${selectedDetails.id}.csv`; a.click();
                                URL.revokeObjectURL(url);
                              }}
                              className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#101017] border border-[#262638] text-slate-400 hover:text-white transition-colors text-[10px] font-mono font-bold"
                            >
                              <Download className="w-3 h-3" /> DOWNLOAD
                            </button>
                          </div>
                        </div>
                        <div className="flex-1 border border-[#1e1e2d] bg-[#0c0c11]/50 rounded-xl overflow-auto select-text">
                          {selectedDetails.csvHeaders && selectedDetails.csvHeaders.length > 0 ? (
                            <table className="w-full text-left font-mono text-xs border-collapse">
                              <thead>
                                <tr className="bg-[#12121c] border-b border-[#20202d] text-slate-400 uppercase text-[10px] sticky top-0">
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
                      const headers = selectedDetails.csvHeaders || [];
                      const data    = selectedDetails.csvData    || [];
                      const bullets = generateInsights(headers, data);
                      return (
                        <div className="space-y-5">
                          {/* Question recap */}
                          {selectedDetails.question && (
                            <div className="flex items-start gap-2 bg-blue-500/8 border border-blue-500/18 rounded-xl px-4 py-3">
                              <MessageSquare className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
                              <p className="text-[12px] text-slate-300 leading-snug">{selectedDetails.question}</p>
                            </div>
                          )}

                          {/* Bullet insights */}
                          <div className="bg-[#0e0e16] border border-[#1e1e2d] rounded-xl p-4 space-y-2.5">
                            <div className="flex items-center gap-2 mb-3">
                              <Lightbulb className="w-4 h-4 text-amber-400" />
                              <span className="text-[11px] font-mono font-bold text-slate-300 uppercase tracking-wider">Business Insights</span>
                            </div>
                            {bullets.length > 0 ? bullets.map((b, i) => (
                              <div key={i} className="flex items-start gap-2.5">
                                <span className="w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-black shrink-0 mt-0.5"
                                  style={{ background: ['#5fa8d8','#7e96d0','#3db8b0','#a07ec8','#38b890'][i % 5] + '22',
                                           color:      ['#5fa8d8','#7e96d0','#3db8b0','#a07ec8','#38b890'][i % 5] }}>
                                  {i + 1}
                                </span>
                                <p className="text-[12px] text-slate-300 leading-relaxed">{b}</p>
                              </div>
                            )) : (
                              <p className="text-[11px] text-slate-600 italic font-mono">Run a query to generate insights.</p>
                            )}
                          </div>

                          {/* Chart */}
                          {data.length > 0 && (
                            <div className="bg-[#0e0e16] border border-[#1e1e2d] rounded-xl p-4">
                              <div className="flex items-center gap-2 mb-3">
                                <BarChart3 className="w-4 h-4 text-blue-400" />
                                <span className="text-[11px] font-mono font-bold text-slate-300 uppercase tracking-wider">Distribution</span>
                                <span className="text-[9px] font-mono text-slate-600 ml-auto">{headers.join(' · ')}</span>
                              </div>
                              <InsightsChart headers={headers} data={data} />
                            </div>
                          )}

                          {/* Row count badge */}
                          {data.length > 0 && (
                            <div className="flex items-center gap-4 text-[10px] font-mono text-slate-500">
                              <span className="flex items-center gap-1"><TrendingUp className="w-3 h-3 text-emerald-500" />{data.length} rows</span>
                              <span className="flex items-center gap-1"><Database className="w-3 h-3 text-blue-400" />{headers.length} columns</span>
                            </div>
                          )}
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



      {/* Forensic Diagnostics & Repair Drawer */}
      <AnimatePresence>
        {showDiagnoseDrawer && (
          <div className="fixed inset-0 z-50 flex justify-end select-none">
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowDiagnoseDrawer(false)} />
            <motion.div
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
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

                    {/* Corrective Actions Recommendations */}
                    <div className="space-y-2 font-mono text-xs">
                      <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">Recommendations</span>
                      <ul className="list-disc list-inside p-4 rounded-xl bg-[#0e0e14] border border-[#20202d] text-slate-300 space-y-2">
                        {diagnoseData.recommendations && diagnoseData.recommendations.map((r, i) => (
                          <li key={i}>{r}</li>
                        ))}
                      </ul>
                    </div>

                    {/* Sandbox Correction Tool */}
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
                            <pre className="p-3 bg-black/50 border border-[#1f1f2d] text-blue-300 text-xs overflow-x-auto rounded-lg">
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
                  </>
                )}
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ── Active Runs floating panel ── */}
      <AnimatePresence>
        {activeSession && (
          <motion.div
            initial={{ opacity: 0, x: 80, y: 0 }}
            animate={{ opacity: 1, x: 0, y: 0 }}
            exit={{ opacity: 0, x: 80, y: 0 }}
            transition={{ type: 'spring', stiffness: 280, damping: 28 }}
            className="fixed bottom-6 right-6 z-50 w-72 rounded-xl border border-[#222232] bg-[#0d0d15]/95 shadow-2xl backdrop-blur-md overflow-hidden"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-2.5 bg-[#0e0e1a] border-b border-[#1c1c2a]">
              <div className="flex items-center gap-2">
                {activeSession.running ? (
                  <span className="relative flex h-2.5 w-2.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
                  </span>
                ) : (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                )}
                <span className="text-[11px] font-mono font-bold text-slate-200">
                  {activeSession.running ? 'Active Runs' : 'Run Complete'}
                </span>
              </div>
              <button
                onClick={() => { setActiveSession(null); stopSessionPoll(); }}
                className="text-slate-500 hover:text-slate-300 transition-colors"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Progress bar */}
            <div className="px-4 pt-3 pb-1">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[10px] font-mono text-slate-400">
                  {activeSession.completed} / {activeSession.total} queries
                </span>
                <span className="text-[10px] font-mono font-bold text-emerald-400">
                  {activeSession.pct}%
                </span>
              </div>
              <div className="w-full h-1.5 bg-[#1b1b2a] rounded-full overflow-hidden">
                <motion.div
                  className="h-full bg-gradient-to-r from-emerald-600 to-emerald-400 rounded-full"
                  animate={{ width: `${activeSession.pct}%` }}
                  transition={{ duration: 0.5, ease: 'easeOut' }}
                  style={{ width: `${activeSession.pct}%` }}
                />
              </div>
            </div>

            {/* Date badge */}
            <div className="px-4 py-1">
              <span className="text-[9px] font-mono text-slate-500">
                Run date: <span className="text-slate-400">{activeSession.run_date}</span>
              </span>
            </div>

            {/* Running tasks list */}
            {activeSession.running_tasks.length > 0 && (
              <div className="px-4 pb-3">
                <div className="text-[9px] font-mono text-slate-500 mb-1.5 uppercase tracking-wider">
                  Currently running ({activeSession.running_tasks.length})
                </div>
                <div className="max-h-28 overflow-y-auto space-y-1 pr-1 scrollbar-thin">
                  {activeSession.running_tasks.slice(0, 12).map(task => (
                    <div key={task} className="flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0 animate-pulse" />
                      <span className="text-[10px] font-mono text-slate-400 truncate">{task}</span>
                    </div>
                  ))}
                  {activeSession.running_tasks.length > 12 && (
                    <div className="text-[9px] font-mono text-slate-600 pl-3">
                      +{activeSession.running_tasks.length - 12} more...
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Done state */}
            {!activeSession.running && (
              <div className="px-4 pb-3 text-[10px] font-mono text-emerald-400 flex items-center gap-1.5">
                <CheckCircle2 className="w-3 h-3" />
                All {activeSession.total} queries done — results updated.
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
      {/* Delete Confirmation Modal */}
      {showDeleteModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fadeIn">
          <div className="bg-[#0b0a14] border border-rose-500/30 rounded-2xl w-full max-w-md shadow-2xl shadow-rose-900/20 overflow-hidden flex flex-col relative animate-slideUp">
            <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-rose-600 to-rose-400" />
            <div className="p-6">
              <div className="flex items-center gap-4 mb-4">
                <div className="w-12 h-12 rounded-full bg-rose-500/10 border border-rose-500/20 flex items-center justify-center shrink-0">
                  <X className="w-6 h-6 text-rose-500" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-slate-100 font-mono">Delete Forensic Data</h3>
                  <p className="text-sm text-slate-400 font-mono mt-1">
                    Date: <span className="text-rose-400">{dateFilter}</span>
                  </p>
                </div>
              </div>
              <p className="text-sm text-slate-300 leading-relaxed">
                You are about to permanently delete all archived metrics, benchmark evaluations, and execution logs for this specific date.
                <br /><br />
                <span className="font-bold text-rose-400">This action is completely irreversible.</span> Do you wish to proceed?
              </p>
            </div>
            <div className="flex items-center justify-end gap-3 px-6 py-4 bg-[#0e0d18] border-t border-[#1c1a2d]">
              <button
                onClick={() => setShowDeleteModal(false)}
                className="px-4 py-2 rounded-lg font-mono text-xs font-bold text-slate-400 hover:text-slate-200 hover:bg-white/5 transition-all"
              >
                CANCEL
              </button>
              <button
                onClick={confirmDeleteRun}
                className="px-4 py-2 rounded-lg font-mono text-xs font-bold text-white bg-rose-600 hover:bg-rose-500 transition-all shadow-lg shadow-rose-600/20 flex items-center gap-2"
              >
                <X className="w-4 h-4" />
                CONFIRM DELETION
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SpiderStudio;
