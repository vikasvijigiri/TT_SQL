import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence, useMotionValue, useSpring } from 'framer-motion';
import {
  Zap, Shield, Brain, GitBranch, BarChart3, Globe,
  ArrowRight, Layers,
  CheckCircle2, ChevronRight, Play, Database, Search, Code, Terminal, Copy, Check, Sparkles, AlertCircle, Loader2,
  Download, Cpu, RotateCcw, Pause, Info, LogOut, X, User
} from 'lucide-react';
import { useGoogleLogin } from '@react-oauth/google';
import NQuireLogo from './NQuireLogo';

/* ─── Palette ──────────────────────────────────────────────────────────────── */
const C = {
  bg:       '#1b2738',
  surface1: 'rgba(26,38,54,0.88)',
  surface2: 'rgba(32,46,64,0.70)',
  sky:      '#5fa8d8',
  indigo:   '#7e96d0',
  violet:   '#a07ec8',
  teal:     '#3db8b0',
  pink:     '#c882a8',
  mint:     '#38b890',
  text1:    '#e2ecf5',
  text2:    '#8aaac0',
  text3:    '#4e6880',
  border:   'rgba(120,160,200,0.12)',
};

/* ─── Data ─────────────────────────────────────────────────────────────────── */


const FEATURES = [
  { icon: Brain,     col: C.sky,    title: 'Semantic Schema Linking',
    desc: 'FQN-level entity matching maps plain English to exact table.column identifiers with value-first grounding.' },
  { icon: GitBranch, col: C.indigo, title: 'Adaptive Strategy Router',
    desc: 'Capability detection auto-selects Simple, Join, Aggregation, or Nested execution strategies per query.' },
  { icon: Shield,    col: C.teal,   title: 'Data-IQ Result Auditor',
    desc: 'Variance profiling, null detection, and filter-collapse diagnosis before results reach you.' },
  { icon: Zap,       col: C.violet, title: 'Closed-Loop Self-Correction',
    desc: 'Up to 4-stage retry with inline root-cause diagnosis injected directly into the corrector context.' },
  { icon: Globe,     col: C.pink,   title: 'Cross-Dialect Rule Engine',
    desc: 'Native rule families for Snowflake, PostgreSQL, SQLite, DuckDB, BigQuery, and MySQL.' },
  { icon: BarChart3, col: C.mint,   title: 'Live Stage Telemetry',
    desc: 'Per-stage timing, token budgets, and a full pipeline trace surfaced on every single run.' },
];

const STATS = [
  { value: 8,  sfx: '',  label: 'Pipeline Stages' },
  { value: 6,  sfx: '+', label: 'SQL Dialects'     },
  { value: 4,  sfx: 'x', label: 'Self-Corrections' },
];

const BENCHMARKS = [
  { name: 'Spider2-Lite',   accuracy: '61.0', detail: '334 / 547 queries', color: '#38bdf8', desc: 'Execution Acc.' },
  { name: 'DataAgentBench', accuracy: '47.0', detail: '54 queries · 12 datasets', color: '#2dd4bf', desc: 'Pass@1' },
];

const SLOGANS = [
  "Traditional generators write SQL. We guarantee correctness.",
  "Closed-Loop self-healing repairs broken database queries automatically.",
  "FQN-grounded mappings eliminate column and table ambiguity.",
  "Semantic context pruning reduces token consumption by 80%."
];

const STRENGTHS_LIST = [
  { 
    title: "Self-Correction Loop", 
    desc: "Automated compiler debugging in a closed-loop sandbox up to 4 retries.", 
    badge: "Self-Healing",
    col: '#a78bfa'
  },
  { 
    title: "FQN Entity Mapping", 
    desc: "Precision grounding matching ambiguous search keywords to exact metadata.", 
    badge: "High Recall",
    col: '#38bdf8'
  },
  { 
    title: "Semantic Pruning", 
    desc: "Reduces latency and LLM costs by trimming out irrelevant tables.", 
    badge: "Context-Aware",
    col: '#2dd4bf'
  },
  { 
    title: "Data-IQ Audit Linting", 
    desc: "Inspects result grain, null variance, and limit bounds pre-execution.", 
    badge: "Verified Results",
    col: '#c882a8'
  }
];

const TESTIMONIALS = [
  {
    quote: "Before NQuire, I spent 80% of my day debugging syntax errors and 20% crying. Now, the self-correction loop does both for me. 10/10.",
    author: "Vikas V.",
    role: "Dean of Crying in Dark Theme",
    initials: "VV",
    col: '#5fa8d8',
  },
  {
    quote: "FQN grounding found a column named 'temp_final_v3_dont_drop' on our legacy server in 0.03 seconds. It knows our database secrets better than our security auditor does.",
    author: "Vinay N.",
    role: "Chief Coffee-to-Code Transpiler",
    initials: "VN",
    col: '#7e96d0',
  },
  {
    quote: "Our database is a 400-table labyrinth of poor life choices. NQuire's semantic context pruner sliced token costs so much our finance team asked if we closed the company.",
    author: "Vishal A.",
    role: "Guardian of the Free Tier",
    initials: "VA",
    col: '#3db8b0',
  },
];

/* ─── Testimonials strip ────────────────────────────────────────────────────── */
const TestimonialsStrip = () => (
  <section className="relative z-10 max-w-5xl mx-auto px-6 mb-14">
    <div className="text-center mb-6">
      <span className="text-[10px] font-mono font-bold px-2.5 py-1 rounded-full uppercase tracking-wider inline-block"
        style={{ background: 'rgba(95,168,216,0.12)', color: '#5fa8d8', border: '1px solid rgba(95,168,216,0.22)' }}>
        What teams are saying
      </span>
    </div>
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {TESTIMONIALS.map((t, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.45, delay: i * 0.1, ease: [0.25, 1, 0.5, 1] }}
          className="flex flex-col gap-3 rounded-2xl p-5 border"
          style={{ background: 'rgba(26,38,54,0.70)', borderColor: `${t.col}22`, backdropFilter: 'blur(10px)' }}
        >
          {/* Stars */}
          <div className="flex gap-0.5">
            {[...Array(5)].map((_, si) => (
              <svg key={si} className="w-3 h-3" fill={t.col} viewBox="0 0 20 20">
                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
              </svg>
            ))}
          </div>
          {/* Quote */}
          <p className="text-[12px] leading-relaxed flex-1" style={{ color: '#c0d0e0' }}>
            "{t.quote}"
          </p>
          {/* Author */}
          <div className="flex items-center gap-2.5 pt-1 border-t" style={{ borderColor: `${t.col}18` }}>
            <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 text-[10px] font-bold"
              style={{ background: `${t.col}22`, color: t.col, border: `1px solid ${t.col}30` }}>
              {t.initials}
            </div>
            <div>
              <div className="text-[11px] font-semibold" style={{ color: '#dce5f0' }}>{t.author}</div>
              <div className="text-[9px]" style={{ color: '#4e6880' }}>{t.role}</div>
            </div>
          </div>
        </motion.div>
      ))}
    </div>
  </section>
);

/* ─── Animated counter ─────────────────────────────────────────────────────── */
const Counter = ({ to, sfx }) => {
  const [n, setN] = useState(0);
  useEffect(() => {
    let cur = 0;
    const step = to / 40;
    const t = setInterval(() => {
      cur = Math.min(cur + step, to);
      setN(Math.round(cur));
      if (cur >= to) clearInterval(t);
    }, 28);
    return () => clearInterval(t);
  }, [to]);
  return <>{n}{sfx}</>;
};


/* ─── Rotating slogan cycle text ───────────────────────────────────────────── */
const SloganCycle = () => {
  const [idx, setIdx] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setIdx(i => (i + 1) % SLOGANS.length), 3800);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="flex items-center gap-2">
      <span className="w-px h-4 shrink-0 rounded-full" style={{ background: 'linear-gradient(to bottom, #818cf8, #2dd4bf)' }} />
      <div className="h-5 relative overflow-hidden flex-1">
        <AnimatePresence mode="wait">
          <motion.p
            key={idx}
            initial={{ y: 14, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: -14, opacity: 0 }}
            transition={{ duration: 0.45, ease: [0.25, 1, 0.5, 1] }}
            className="absolute text-[11px] font-medium text-left whitespace-nowrap"
            style={{ color: '#94a3b8' }}
          >
            {SLOGANS[idx]}
          </motion.p>
        </AnimatePresence>
      </div>
    </div>
  );
};

/* ─── Strengths Card Grid ─────────────────────────────────────────────────── */
const StrengthsGrid = () => {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-12 text-left">
      {STRENGTHS_LIST.map((item, idx) => (
        <motion.div
          key={idx}
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: idx * 0.1, ease: [0.25, 1, 0.5, 1] }}
          whileHover={{ y: -5, borderColor: `${item.col}44`, boxShadow: `0 8px 30px ${item.col}0d` }}
          className="relative rounded-2xl p-5 border border-slate-800/80 bg-slate-950/40 backdrop-blur-md transition-all duration-300 group cursor-default flex flex-col justify-between"
        >
          <div className="absolute top-3 right-3 text-[8px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border"
               style={{ borderColor: `${item.col}33`, color: item.col, background: `${item.col}08` }}>
            {item.badge}
          </div>
          <div>
            <h4 className="text-[11px] font-bold font-mono tracking-wide text-slate-200 mb-2 mt-2 group-hover:text-white transition-colors">
              {item.title}
            </h4>
            <p className="text-[10px] text-slate-400 leading-relaxed">
              {item.desc}
            </p>
          </div>
        </motion.div>
      ))}
    </div>
  );
};


/* ─── Smart SVG Plot Engine ────────────────────────────────────────────────── */
const SmartPlot = ({ results, columns }) => {
  const [chartType, setChartType] = useState('bar');
  const [hoveredIdx, setHoveredIdx] = useState(null);
  
  if (!results || results.length === 0) return null;
  
  const numericCols = columns.filter(col => {
    return results.some(r => r[col] !== null) && 
           results.every(r => r[col] === null || !isNaN(Number(r[col])));
  });
  
  let valCol = numericCols.find(col => !col.toLowerCase().endsWith('_id') && col.toLowerCase() !== 'id');
  if (!valCol && numericCols.length > 0) {
    valCol = numericCols[0];
  }
  
  const labelCol = columns.find(col => col !== valCol) || columns[0];
  
  if (!valCol) {
    return (
      <div className="flex flex-col items-center justify-center h-48 text-slate-500 font-mono text-[10px]">
        <AlertCircle className="w-5 h-5 mb-2 text-indigo-400 animate-pulse" />
        No numeric columns found to plot.
      </div>
    );
  }
  
  const data = results.map((r, i) => {
    const rawVal = r[valCol];
    const val = rawVal === null ? 0 : Number(rawVal);
    const label = r[labelCol] !== null ? String(r[labelCol]) : `Row ${i + 1}`;
    return { label, val, rawRow: r };
  });
  
  const maxVal = Math.max(...data.map(d => d.val), 1);
  const gridMax = Math.ceil(maxVal * 1.15);
  
  const svgWidth = 460;
  const svgHeight = 180;
  const margin = { top: 15, right: 15, bottom: 35, left: 45 };
  const innerWidth = svgWidth - margin.left - margin.right;
  const innerHeight = svgHeight - margin.top - margin.bottom;
  
  return (
    <div className="flex flex-col h-full select-none">
      <div className="flex items-center justify-between mb-2">
        <div className="text-[9px] font-mono text-slate-400">
          Plotting <span className="text-violet-400 font-bold">{valCol}</span> by <span className="text-sky-400 font-bold">{labelCol}</span>
        </div>
        <div className="flex gap-1 bg-slate-900/80 p-0.5 rounded-lg border border-slate-800">
          {['bar', 'line'].map(type => (
            <button
              key={type}
              onClick={() => setChartType(type)}
              className="px-2 py-0.5 rounded text-[9px] font-mono font-bold capitalize transition-colors cursor-pointer"
              style={{
                backgroundColor: chartType === type ? 'rgba(99, 102, 241, 0.2)' : 'transparent',
                color: chartType === type ? '#818cf8' : '#94a3b8'
              }}
            >
              {type}
            </button>
          ))}
        </div>
      </div>
      
      <div className="relative flex-1 bg-slate-950/40 rounded-xl border border-slate-900 p-2 flex items-center justify-center">
        <svg 
          width="100%" 
          height="100%" 
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          preserveAspectRatio="xMidYMid meet"
          className="overflow-visible"
        >
          <defs>
            <linearGradient id="barGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#818cf8" stopOpacity={0.85} />
              <stop offset="100%" stopColor="#38bdf8" stopOpacity={0.15} />
            </linearGradient>
            <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#818cf8" stopOpacity="0.35" />
              <stop offset="100%" stopColor="#818cf8" stopOpacity={0.0} />
            </linearGradient>
            <filter id="glow" x="-10%" y="-10%" width="120%" height="120%">
              <feDropShadow dx="0" dy="0" stdDeviation="4" floodColor="#818cf8" floodOpacity="0.4" />
            </filter>
          </defs>
          
          {[0, 0.25, 0.5, 0.75, 1].map((ratio, i) => {
            const y = margin.top + innerHeight - (ratio * innerHeight);
            const valLabel = Math.round(ratio * gridMax);
            return (
              <g key={i} className="opacity-40">
                <line 
                  x1={margin.left} 
                  y1={y} 
                  x2={margin.left + innerWidth} 
                  y2={y} 
                  stroke="rgba(148,163,184,0.15)" 
                  strokeWidth="1" 
                  strokeDasharray="3,3"
                />
                <text 
                  x={margin.left - 8} 
                  y={y + 3} 
                  textAnchor="end" 
                  fill="#475569" 
                  className="font-mono text-[8px]"
                >
                  {valLabel}
                </text>
              </g>
            );
          })}
          
          {chartType === 'bar' ? (
            data.map((d, idx) => {
              const numItems = data.length;
              const colWidth = innerWidth / numItems;
              const spacing = colWidth * 0.25;
              const barWidth = colWidth * 0.5;
              const barHeight = (d.val / gridMax) * innerHeight;
              const x = margin.left + (idx * colWidth) + spacing;
              const y = margin.top + innerHeight - barHeight;
              const isHovered = hoveredIdx === idx;
              
              return (
                <g 
                  key={idx}
                  onMouseEnter={() => setHoveredIdx(idx)}
                  onMouseLeave={() => setHoveredIdx(null)}
                  className="cursor-pointer"
                >
                  {isHovered && (
                    <rect 
                      x={x - spacing/2}
                      y={margin.top}
                      width={colWidth}
                      height={innerHeight}
                      fill="rgba(148,163,184,0.02)"
                      rx="4"
                    />
                  )}
                  <motion.rect
                    x={x}
                    y={margin.top + innerHeight}
                    width={barWidth}
                    animate={{ y, height: barHeight }}
                    transition={{ type: 'spring', stiffness: 100, damping: 15, delay: idx * 0.05 }}
                    fill="url(#barGrad)"
                    stroke="#818cf8"
                    strokeWidth={isHovered ? 1.5 : 1}
                    rx="3"
                    filter={isHovered ? "url(#glow)" : "none"}
                    className="transition-all"
                  />
                  {isHovered && (
                    <text
                      x={x + barWidth / 2}
                      y={y - 5}
                      textAnchor="middle"
                      fill="#e8eef8"
                      className="font-mono text-[9px] font-bold"
                    >
                      {d.val}
                    </text>
                  )}
                </g>
              );
            })
          ) : (
            (() => {
              const numItems = data.length;
              const points = data.map((d, idx) => {
                const x = margin.left + (idx * (innerWidth / (numItems - 1 || 1)));
                const y = margin.top + innerHeight - ((d.val / gridMax) * innerHeight);
                return { x, y };
              });
              
              const linePath = points.map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
              const areaPath = points.length > 0 
                ? `${linePath} L ${points[points.length - 1].x} ${margin.top + innerHeight} L ${points[0].x} ${margin.top + innerHeight} Z`
                : '';
                
              return (
                <g>
                  {areaPath && (
                    <motion.path 
                      d={areaPath} 
                      fill="url(#areaGrad)"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ duration: 0.6 }}
                    />
                  )}
                  {linePath && (
                    <motion.path
                      d={linePath}
                      fill="none"
                      stroke="#818cf8"
                      strokeWidth="2"
                      initial={{ pathLength: 0 }}
                      animate={{ pathLength: 1 }}
                      transition={{ duration: 0.8, ease: 'easeOut' }}
                      filter="url(#glow)"
                    />
                  )}
                  {points.map((p, idx) => {
                    const isHovered = hoveredIdx === idx;
                    return (
                      <g 
                        key={idx}
                        onMouseEnter={() => setHoveredIdx(idx)}
                        onMouseLeave={() => setHoveredIdx(null)}
                        className="cursor-pointer"
                      >
                        <circle 
                          cx={p.x} 
                          cy={p.y} 
                          r={isHovered ? 6 : 4} 
                          fill={isHovered ? '#818cf8' : '#05091a'} 
                          stroke={isHovered ? '#fff' : '#818cf8'}
                          strokeWidth="2"
                          className="transition-all duration-150"
                        />
                        {isHovered && (
                          <text
                            x={p.x}
                            y={p.y - 8}
                            textAnchor="middle"
                            fill="#e8eef8"
                            className="font-mono text-[9px] font-bold"
                          >
                            {data[idx].val}
                          </text>
                        )}
                      </g>
                    );
                  })}
                </g>
              );
            })()
          )}
          
          {data.map((d, idx) => {
            const numItems = data.length;
            const x = margin.left + (idx * (innerWidth / (chartType === 'bar' ? numItems : numItems - 1 || 1))) + (chartType === 'bar' ? (innerWidth/numItems * 0.5) : 0);
            const labelText = d.label.length > 12 ? `${d.label.slice(0, 10)}...` : d.label;
            
            return (
              <g key={idx} className="opacity-75">
                <text
                  x={x}
                  y={margin.top + innerHeight + 14}
                  textAnchor="middle"
                  fill="#94a3b8"
                  className="font-mono text-[8px] tracking-tighter"
                  transform={numItems > 4 ? `rotate(12, ${x}, ${margin.top + innerHeight + 14})` : ''}
                >
                  {labelText}
                </text>
              </g>
            );
          })}
          
          <line 
            x1={margin.left} 
            y1={margin.top + innerHeight} 
            x2={margin.left + innerWidth} 
            y2={margin.top + innerHeight} 
            stroke="rgba(148,163,184,0.2)" 
            strokeWidth="1"
          />
        </svg>
        
        {hoveredIdx !== null && data[hoveredIdx] && (
          <div 
            className="absolute z-30 p-2.5 rounded-xl border bg-slate-950/95 shadow-xl font-mono text-[9px] pointer-events-none flex flex-col gap-1"
            style={{
              borderColor: 'rgba(99, 102, 241, 0.4)',
              boxShadow: '0 4px 20px rgba(0,0,0,0.5), 0 0 10px rgba(99, 102, 241, 0.1)',
              right: hoveredIdx > data.length / 2 ? 'auto' : '15px',
              left: hoveredIdx > data.length / 2 ? '15px' : 'auto',
              top: '15px'
            }}
          >
            <div className="text-slate-400 font-bold border-b border-slate-800/80 pb-1 mb-1">
              {data[hoveredIdx].label}
            </div>
            {Object.entries(data[hoveredIdx].rawRow).map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4">
                <span className="text-slate-500">{k}:</span>
                <span className={k === valCol ? 'text-indigo-400 font-bold' : 'text-slate-300'}>
                  {v === null ? 'NULL' : typeof v === 'number' ? Math.round(v * 100) / 100 : String(v)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

/* ─── Agent Flow Simulation Constants ─────────────────────────────────────── */
const AGENT_DETAILS = {
  orchestrator: {
    name: "Central Orchestrator",
    role: "Workflow Coordination & Routing",
    desc: "Controls execution sequence, routes inputs to target agents, and initiates automated retry/repair loops upon error detection.",
    prompt: "You are the central system router. Interpret the request, maintain task state, dispatch schema linking, syntactic building, and results auditing. If Auditor reports failures, invoke Self-Corrector.",
    input: "Natural Language user request, Database connection metadata.",
    output: "Dialect SQL statements, Executable datasets, system logs."
  },
  linker: {
    name: "Schema Linker",
    role: "Semantic Field Grounding",
    desc: "Maps user vocabulary terms to exact catalog objects (tables, columns, and string values) using high-recall grounding algorithms.",
    prompt: "Identify and extract all schema terms (tables, columns, cell values) matching natural language terms. Output exact database object mappings.",
    input: "Raw English user question, full DB schema catalog.",
    output: "FQN column maps, schema grounding matrices."
  },
  pruner: {
    name: "Context Pruner",
    role: "Token Optimization",
    desc: "Trims ungrounded tables and structural clutter from the active prompt payload, keeping schema token size highly compressed.",
    prompt: "Discard schema definitions for tables and columns with zero match relevance scores. Minimize input size for downstream agents.",
    input: "Complete catalog schema, Schema Linker mappings.",
    output: "Pruned minimal schema mapping."
  },
  synthesizer: {
    name: "SQL Synthesizer",
    role: "Cross-Dialect SQL Generation",
    desc: "Composes target SQL statements using custom join-paths and aggregated functions optimized for the specified database engine.",
    prompt: "Given a pruned context and target question, compose a valid SQL SELECT statement. Handle table joints, column projections, and limits.",
    input: "Minimized schema, user request, SQL dialect identifier.",
    output: "Raw SQL query statement."
  },
  auditor: {
    name: "Result Auditor",
    role: "Quality Assurance & Linter",
    desc: "Conducts static SQL validation (aggregations, projections, limit sanity) and inspects output rows for data grain anomalies.",
    prompt: "Inspect generated SQL against rules: verify project items vs. Group By columns, check division-by-zero risks, inspect aggregate null-handling.",
    input: "Candidate SQL query, output dataset sample.",
    output: "Audit feedback (Pass / Fail + Warning messages)."
  },
  corrector: {
    name: "Self-Corrector",
    role: "Automated Error Healing",
    desc: "An automated repair agent that takes compiler errors or Auditor failures and rewrites query logic to heal execution faults.",
    prompt: "You are an SQL debugger. Inspect the failing SQL and diagnostic errors, then write a corrected SQL query addressing the failure.",
    input: "Failing query, error/warning logs, diagnostic context.",
    output: "Corrected SQL statement."
  },
  sandbox: {
    name: "Data Sandbox",
    role: "SQL Execution Engine",
    desc: "Executes completed SQL statements in a secure, isolated SQLite sandbox environment to yield columns and result rows.",
    prompt: "Secure execution: run SQL query, fetch column definitions and rows, enforce 20 rows limit.",
    input: "Validated SQL query statement.",
    output: "Dataset rows, columns list, execution time metadata."
  }
};

const SIM_STEPS = [
  {
    step: 1,
    title: "User Input Received",
    description: "Natural language query is processed and sent to the central orchestrator.",
    activeNodes: ['orchestrator'],
    pulse: { from: 'user', to: 'orchestrator' },
    log: "[Orchestrator] New task: 'Which bowler has lowest bowling average?'\n[Orchestrator] Initializing query workspace state..."
  },
  {
    step: 2,
    title: "Grounding Terms",
    description: "Orchestrator invokes the Schema Linker to identify tables and columns matches.",
    activeNodes: ['orchestrator', 'linker'],
    pulse: { from: 'orchestrator', to: 'linker' },
    log: "[Orchestrator] Dispatched to Schema Linker.\n[SchemaLinker] Grounding vocabulary against catalog...\n[SchemaLinker] Found strong matches for: 'bowler', 'bowling average'."
  },
  {
    step: 3,
    title: "Schema Matching Return",
    description: "Schema Linker yields the candidate columns (e.g. ball_by_ball.bowler, batsman_scored.runs_scored).",
    activeNodes: ['orchestrator', 'linker'],
    pulse: { from: 'linker', to: 'orchestrator' },
    log: "[SchemaLinker] Grounding completed. Returning exact FQNs:\n  - ball_by_ball.bowler\n  - batsman_scored.runs_scored"
  },
  {
    step: 4,
    title: "Pruning Context",
    description: "Orchestrator sends candidate schema to Context Pruner to discard irrelevant descriptions.",
    activeNodes: ['orchestrator', 'pruner'],
    pulse: { from: 'orchestrator', to: 'pruner' },
    log: "[Orchestrator] Context optimization requested from Context Pruner.\n[ContextPruner] Analyzing column dependencies...\n[ContextPruner] Excluded tables: [team, venue, season]."
  },
  {
    step: 5,
    title: "Context Optimized",
    description: "Context Pruner returns a minimized schema map, cutting down prompt tokens by 80%.",
    activeNodes: ['orchestrator', 'pruner'],
    pulse: { from: 'pruner', to: 'orchestrator' },
    log: "[ContextPruner] Pruning successful. Token budget reduced from 4,120 to 680 tokens."
  },
  {
    step: 6,
    title: "Synthesizing SQL",
    description: "Orchestrator dispatches the minimal grounded schema map to SQL Synthesizer to compose the SQL query.",
    activeNodes: ['orchestrator', 'synthesizer'],
    pulse: { from: 'orchestrator', to: 'synthesizer' },
    log: "[Orchestrator] Synthesizer invoked.\n[SQLSynthesizer] Resolving table join paths...\n[SQLSynthesizer] Synthesizing SQLite syntax SELECT-JOIN-GROUPBY..."
  },
  {
    step: 7,
    title: "SQL Generated",
    description: "SQL Synthesizer returns candidate SQL containing complex aggregation and joins.",
    activeNodes: ['orchestrator', 'synthesizer'],
    pulse: { from: 'synthesizer', to: 'orchestrator' },
    log: "[SQLSynthesizer] Query synthesis complete. Candidate SQL generated."
  },
  {
    step: 8,
    title: "Result Auditing",
    description: "Orchestrator forwards the candidate SQL to the Result Auditor to run static syntax audits.",
    activeNodes: ['orchestrator', 'auditor'],
    pulse: { from: 'orchestrator', to: 'auditor' },
    log: "[Orchestrator] Submitting query to Result Auditor.\n[ResultAuditor] Linting SQL check...\n[ResultAuditor] WARNING: Join lacks coalesce fallback for empty stats."
  },
  {
    step: 9,
    title: "Closed-Loop Correction",
    description: "Result Auditor rejects query. Orchestrator invokes Self-Corrector with error details to repair the query.",
    activeNodes: ['orchestrator', 'corrector'],
    pulse: { from: 'orchestrator', to: 'corrector' },
    log: "[ResultAuditor] Audit FAILED: null metrics returned.\n[SelfCorrector] Synthesizing retry logic...\n[SelfCorrector] Injected COALESCE(runs_scored, 0). Fixed SQL returned."
  },
  {
    step: 10,
    title: "Sandbox Execution",
    description: "The corrected query passes auditing. Orchestrator runs it inside the Data Sandbox, outputting CSV/Plot.",
    activeNodes: ['orchestrator', 'sandbox'],
    pulse: { from: 'orchestrator', to: 'sandbox' },
    log: "[Orchestrator] Auditing PASSED.\n[DataSandbox] Submitting query statement to database...\n[DataSandbox] Query executed! 5 rows returned."
  }
];

/* ─── Magnetic CTA button ──────────────────────────────────────────────────── */
const MagneticCTA = ({ onClick, children }) => {
  const ref = useRef(null);
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const sx = useSpring(x, { stiffness: 300, damping: 25 });
  const sy = useSpring(y, { stiffness: 300, damping: 25 });

  const handleMouse = (e) => {
    if (!ref.current) return;
    const r = ref.current.getBoundingClientRect();
    const cx = r.left + r.width / 2;
    const cy = r.top + r.height / 2;
    x.set((e.clientX - cx) * 0.28);
    y.set((e.clientY - cy) * 0.28);
  };
  const reset = () => { x.set(0); y.set(0); };

  return (
    <motion.button
      ref={ref}
      style={{ x: sx, y: sy }}
      onMouseMove={handleMouse}
      onMouseLeave={reset}
      onClick={onClick}
      whileHover={{ scale: 1.06 }}
      whileTap={{ scale: 0.95 }}
      className="relative overflow-hidden group cursor-pointer"
    >
      {/* Base gradient */}
      <div
        className="relative z-10 flex items-center gap-2.5 px-6 py-3 rounded-xl font-semibold text-sm"
        style={{
          background: `linear-gradient(135deg, #2a5898 0%, #3d5cb0 55%, #0d6e88 100%)`,
          color: '#fff',
          boxShadow: '0 0 28px rgba(61,92,176,0.35), 0 2px 8px rgba(0,0,0,0.3)',
        }}
      >
        {/* Shimmer sweep */}
        <motion.div
          className="absolute inset-0 rounded-xl overflow-hidden"
          style={{ background: 'linear-gradient(105deg, transparent 35%, rgba(255,255,255,0.12) 50%, transparent 65%)' }}
          animate={{ x: ['-100%', '200%'] }}
          transition={{ duration: 2.8, repeat: Infinity, repeatDelay: 1.8, ease: 'easeInOut' }}
        />
        <span className="relative z-10">{children}</span>
        <motion.div
          className="relative z-10"
          animate={{ x: [0, 3, 0] }}
          transition={{ duration: 1.4, repeat: Infinity, ease: 'easeInOut' }}
        >
          <ArrowRight className="w-4 h-4" />
        </motion.div>
      </div>
    </motion.button>
  );
};

/* ─── Feature card ─────────────────────────────────────────────────────────── */
const FeatureCard = ({ f, i }) => (
  <motion.div
    initial={{ opacity: 0, y: 24 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay: 0.6 + i * 0.06, duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
    whileHover={{ y: -4 }}
    className="group relative rounded-2xl p-[1px] cursor-default"
    style={{ background: 'rgba(148,163,184,0.07)' }}
  >
    {/* Hover border glow */}
    <motion.div
      className="absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500"
      style={{ background: `linear-gradient(135deg, ${f.col}22, transparent, ${f.col}11)` }}
    />
    <div
      className="relative rounded-2xl p-5 h-full"
      style={{ background: C.surface1, backdropFilter: 'blur(12px)' }}
    >
      {/* Top colour bar */}
      <div
        className="absolute top-0 left-6 right-6 h-[1.5px] rounded-full"
        style={{ background: `linear-gradient(90deg, transparent, ${f.col}60, transparent)` }}
      />
      <div
        className="w-10 h-10 rounded-xl flex items-center justify-center mb-4 mt-1"
        style={{
          background: `${f.col}14`,
          border: `1px solid ${f.col}28`,
          boxShadow: `0 0 20px ${f.col}18`,
        }}
      >
        <f.icon size={17} style={{ color: f.col }} />
      </div>
      <h3 className="text-[13px] font-bold mb-1.5" style={{ color: C.text1 }}>{f.title}</h3>
      <p className="text-[11px] leading-relaxed" style={{ color: C.text2 }}>{f.desc}</p>
    </div>
  </motion.div>
);

/* ─── Floating orbs ────────────────────────────────────────────────────────── */
const Orbs = () => (
  <div className="pointer-events-none fixed inset-0 overflow-hidden z-0">
    {/* Top-left blue bloom */}
    <motion.div
      animate={{ scale: [1, 1.1, 1], opacity: [0.30, 0.42, 0.30] }}
      transition={{ duration: 9, repeat: Infinity, ease: 'easeInOut' }}
      className="absolute -top-32 -left-32 w-[700px] h-[700px] rounded-full"
      style={{ background: 'radial-gradient(circle, rgba(40,80,160,0.30) 0%, transparent 68%)' }}
    />
    {/* Bottom-right teal bloom */}
    <motion.div
      animate={{ scale: [1, 1.08, 1], opacity: [0.24, 0.34, 0.24] }}
      transition={{ duration: 11, repeat: Infinity, ease: 'easeInOut', delay: 2.5 }}
      className="absolute -bottom-48 -right-32 w-[800px] h-[800px] rounded-full"
      style={{ background: 'radial-gradient(circle, rgba(14,120,140,0.28) 0%, transparent 65%)' }}
    />
    {/* Center violet accent */}
    <motion.div
      animate={{ y: [0, -24, 0], opacity: [0.14, 0.22, 0.14] }}
      transition={{ duration: 13, repeat: Infinity, ease: 'easeInOut', delay: 5 }}
      className="absolute top-[30%] left-[55%] w-[550px] h-[550px] rounded-full"
      style={{ background: 'radial-gradient(circle, rgba(100,70,180,0.18) 0%, transparent 65%)' }}
    />
    {/* Dot grid */}
    <div
      className="absolute inset-0"
      style={{
        backgroundImage: 'radial-gradient(circle, rgba(120,160,200,0.07) 1px, transparent 1px)',
        backgroundSize: '28px 28px',
      }}
    />
    {/* Vignette */}
    <div className="absolute inset-0" style={{ background: 'radial-gradient(ellipse at center, transparent 50%, rgba(27,39,56,0.55) 100%)' }} />
  </div>
);

/* ─── Google icon ──────────────────────────────────────────────────────────── */
const GoogleIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" aria-hidden="true">
    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
  </svg>
);

/* ─── Main component ───────────────────────────────────────────────────────── */
const LandingPage = ({ onEnter, user, onLogin, onLogout }) => {
  const [demoQuery, setDemoQuery] = useState("");
  const [demoLoading, setDemoLoading] = useState(false);
  const [demoResult, setDemoResult] = useState(null);
  const [demoError, setDemoError] = useState(null);
  const [demoStage, setDemoStage] = useState(0); // 0: idle, 1..5: stages, 6: completed
  const [copied, setCopied] = useState(false);
  const [placeholderText, setPlaceholderText] = useState("");
  const [sandboxTab, setSandboxTab] = useState("sql");
  const [simStep, setSimStep] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState("orchestrator");
  const [loginLoading, setLoginLoading] = useState(false);
  const loginIntentRef = useRef(false); // true = navigate to dashboard after auth
  const [showGuestModal, setShowGuestModal] = useState(false);
  const [guestName, setGuestName] = useState("");
  const [guestError, setGuestError] = useState("");

  const handleGuestLogin = (e) => {
    if (e) e.preventDefault();
    const nameTrimmed = guestName.trim();
    if (!nameTrimmed) {
      setGuestError("Please enter a valid name.");
      return;
    }
    // Clean name from forbidden characters to make it a safe slug
    const safeName = nameTrimmed.toLowerCase().replace(/[^a-z0-9_\-]/g, "");
    if (!safeName) {
      setGuestError("Name must contain alphanumeric characters, underscores, or dashes.");
      return;
    }

    const guestUser = {
      name: nameTrimmed,
      email: `${safeName}@nquire.ai`,
      picture: null
    };

    // Helper for base64url encoding
    const base64UrlEncode = (obj) => {
      const json = JSON.stringify(obj);
      const bytes = new TextEncoder().encode(json);
      let binString = "";
      bytes.forEach((b) => {
        binString += String.fromCharCode(b);
      });
      return btoa(binString)
        .replace(/=/g, "")
        .replace(/\+/g, "-")
        .replace(/\//g, "_");
    };

    const header = { alg: "none", typ: "JWT" };
    const payload = { email: guestUser.email, name: guestUser.name };
    const guestToken = `${base64UrlEncode(header)}.${base64UrlEncode(payload)}.`;

    onLogin(guestUser, guestToken);
    setShowGuestModal(false);
    setGuestName("");
    setGuestError("");
    onEnter();
  };

  const glogin = useGoogleLogin({
    onSuccess: async (tokenResponse) => {
      setLoginLoading(true);
      try {
        // Send the Google access token to our backend for verification + JWT issuance.
        const res = await fetch('/api/auth/google', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ access_token: tokenResponse.access_token }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.error || 'Auth failed');
        }
        const { token, user } = await res.json();
        onLogin(user, token);
        if (loginIntentRef.current) onEnter();
      } catch (err) {
        console.error('Google auth failed:', err);
      } finally {
        setLoginLoading(false);
        loginIntentRef.current = false;
      }
    },
    onError: () => {
      setLoginLoading(false);
      loginIntentRef.current = false;
    },
  });

  const signIn = () => { loginIntentRef.current = false; glogin(); };
  const signInAndEnter = () => { loginIntentRef.current = true; glogin(); };

  useEffect(() => {
    let t;
    if (isPlaying) {
      t = setInterval(() => {
        setSimStep(prev => {
          if (prev >= SIM_STEPS.length - 1) {
            return 0;
          }
          return prev + 1;
        });
      }, 3000);
    }
    return () => clearInterval(t);
  }, [isPlaying]);

  useEffect(() => {
    if (isPlaying && SIM_STEPS[simStep]) {
      const active = SIM_STEPS[simStep].activeNodes;
      const satellite = active.find(n => n !== 'orchestrator');
      if (satellite) {
        setSelectedAgent(satellite);
      } else {
        setSelectedAgent('orchestrator');
      }
    }
  }, [simStep, isPlaying]);

  const handleExportCSV = () => {
    if (!demoResult || !demoResult.results) return;
    const headers = demoResult.columns.join(',');
    const rows = demoResult.results.map(row => 
      demoResult.columns.map(col => {
        const val = row[col];
        if (val === null) return '';
        if (typeof val === 'string' && (val.includes(',') || val.includes('"') || val.includes('\n'))) {
          return `"${val.replace(/"/g, '""')}"`;
        }
        return val;
      }).join(',')
    );
    const csvContent = [headers, ...rows].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `nquire_sandbox_data.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const suggestions = [
    "Which bowler has the lowest average runs per wicket?",
    "Show players who scored 100+ runs in a match playing for the losing team.",
    "Find the top 3 bowlers who conceded the most runs in a single over."
  ];

  useEffect(() => {
    let currentSuggestionIdx = 0;
    let currentCharIdx = 0;
    let isDeleting = false;
    let timer;

    const tick = () => {
      const fullText = suggestions[currentSuggestionIdx];
      if (!isDeleting) {
        setPlaceholderText(fullText.substring(0, currentCharIdx + 1));
        currentCharIdx++;
        if (currentCharIdx === fullText.length) {
          isDeleting = true;
          timer = setTimeout(tick, 2000);
        } else {
          timer = setTimeout(tick, 45);
        }
      } else {
        setPlaceholderText(fullText.substring(0, currentCharIdx - 1));
        currentCharIdx--;
        if (currentCharIdx === 0) {
          isDeleting = false;
          currentSuggestionIdx = (currentSuggestionIdx + 1) % suggestions.length;
          timer = setTimeout(tick, 500);
        } else {
          timer = setTimeout(tick, 25);
        }
      }
    };

    tick();
    return () => clearTimeout(timer);
  }, []);

  const handleCopy = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleRunDemo = async (queryText) => {
    if (!queryText || !queryText.trim() || demoLoading) return;
    setDemoLoading(true);
    setDemoError(null);
    setDemoResult(null);
    setDemoStage(1);
    setSandboxTab("sql");

    let apiPromise = fetch("/api/demo/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: queryText })
    })
      .then(res => res.json())
      .catch(err => ({ success: false, error: err.message }));

    for (let stage = 1; stage <= 5; stage++) {
      setDemoStage(stage);
      await new Promise(resolve => setTimeout(resolve, 600));
    }

    const res = await apiPromise;
    if (res.success) {
      setDemoResult(res);
      setDemoStage(6);
    } else {
      setDemoError(res.error || "Failed to execute query.");
      setDemoStage(0);
    }
    setDemoLoading(false);
  };

  const handleChipClick = (text) => {
    setDemoQuery(text);
    handleRunDemo(text);
  };

  const SUGGESTED_QUERIES = [
    {
      label: "Bowler Average",
      text: "Which bowler has the lowest average runs per wicket?",
      desc: "Join & aggregator metrics",
      icon: Brain,
      col: C.sky
    },
    {
      label: "Losing Centurion",
      text: "Show players who scored 100+ runs in a match playing for the losing team.",
      desc: "Match-level analytics",
      icon: Shield,
      col: C.indigo
    },
    {
      label: "Expensive Over",
      text: "Find the top 3 bowlers who conceded the most runs in a single over.",
      desc: "Sub-query extra run checks",
      icon: Zap,
      col: C.violet
    }
  ];

  const MILESTONES = [
    { id: 1, name: "Schema Linker", desc: "Grounding semantic terms to physical tables & columns", icon: Brain, col: C.sky },
    { id: 2, name: "Context Pruner", desc: "Eliminating unrelated schema structures for tokens", icon: Layers, col: C.indigo },
    { id: 3, name: "SQL Synthesizer", desc: "Synthesizing query join paths & dialect clauses", icon: Code, col: C.violet },
    { id: 4, name: "Result Auditor", desc: "Verifying result grain, null-ratio, and filter health", icon: Shield, col: C.teal },
    { id: 5, name: "Data Sandbox", desc: "Executing query safely against sqlite engine", icon: Database, col: C.mint },
  ];

  const getStageLog = (stage) => {
    switch (stage) {
      case 1:
        return `> [AGENT] Invoking SchemaLinker...
> Grounding natural language terms against metadata catalog.
> Matching entity keywords with tables: [player, match, team, ball_by_ball, batsman_scored, wicket_taken]
> Found match candidates:
  - 'bowler' -> ball_by_ball.bowler
  - 'lowest bowling average' -> batsman_scored.runs_scored, wicket_taken.player_out`;
      case 2:
        return `> [AGENT] Invoking SchemaLinker... DONE
> [AGENT] Invoking ContextPruner...
> Pruning tables with zero grounding signal.
> Excluded schemas: [team, modern_data, ModernData]
> Token budget optimized: 4,120 input tokens pruned to 680.`;
      case 3:
        return `> [AGENT] Invoking SchemaLinker... DONE
> [AGENT] Invoking ContextPruner... DONE
> [AGENT] Invoking SQLSynthesizer...
> Resolving schema join paths:
  - ball_by_ball.bowler -> player.player_id
  - ball_by_ball.match_id -> batsman_scored.match_id
  - ball_by_ball.match_id -> wicket_taken.match_id
> Constructing intermediate representation (IR) graph...`;
      case 4:
        return `> [AGENT] Invoking SchemaLinker... DONE
> [AGENT] Invoking ContextPruner... DONE
> [AGENT] Invoking SQLSynthesizer... DONE
> [AGENT] Invoking ResultAuditor...
> Performing static analysis on synthesized SQL.
> Analyzing select column projection grain.
> Injecting COALESCE handler and checking aggregation groups.`;
      case 5:
        return `> [AGENT] Invoking SchemaLinker... DONE
> [AGENT] Invoking ContextPruner... DONE
> [AGENT] Invoking SQLSynthesizer... DONE
> [AGENT] Invoking ResultAuditor... DONE
> [AGENT] Running execution against local SQLite engine...
> Submitting connection statement...`;
      default:
        return "";
    }
  };
  return (
    <div className="relative min-h-screen overflow-x-hidden" style={{ background: C.bg, color: C.text1 }}>
      <Orbs />

      {/* ── Navbar ── */}
      <motion.header
        initial={{ opacity: 0, y: -16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="sticky top-0 z-20 flex items-center justify-between px-8 py-4 max-w-[1400px] mx-auto w-full"
        style={{ borderBottom: `1px solid rgba(120,160,200,0.12)`, backdropFilter: 'blur(20px)', background: 'rgba(24,36,52,0.92)' }}
      >
        <div className="flex items-center gap-2.5">
          <NQuireLogo size={30} showName nameSize="text-sm" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })} />
          <span
            className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded uppercase tracking-widest"
            style={{ background: `rgba(99,102,241,0.1)`, color: C.indigo, border: `1px solid rgba(99,102,241,0.2)` }}
          >
            v2
          </span>
        </div>

        <nav className="hidden md:flex items-center gap-7">
          {[['Features', 'architecture'], ['Pipeline', 'pipeline'], ['Demo', 'live-demo']].map(([label, id]) => (
            <motion.button
              key={label}
              whileHover={{ color: C.text1 }}
              className="text-[13px] font-medium cursor-pointer transition-colors bg-transparent border-0"
              style={{ color: C.text3 }}
              onClick={() => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })}
            >
              {label}
            </motion.button>
          ))}
        </nav>

        {user ? (
          <div className="flex items-center gap-2">
            {user.picture ? (
              <img
                src={user.picture}
                alt={user.name}
                referrerPolicy="no-referrer"
                className="w-8 h-8 rounded-full border border-slate-700/60 shrink-0"
              />
            ) : (
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/30 flex items-center justify-center shrink-0 shadow-inner">
                <User className="w-4.5 h-4.5 text-indigo-300" />
              </div>
            )}
            <span className="text-[12px] text-slate-300 font-medium hidden lg:block max-w-[80px] truncate">
              {user.name.split(' ')[0]}
            </span>
            <motion.button
              whileHover={{ scale: 1.03, background: 'rgba(99,102,241,0.18)' }}
              whileTap={{ scale: 0.97 }}
              onClick={onEnter}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-semibold transition-all"
              style={{ background: 'rgba(99,102,241,0.1)', color: C.indigo, border: `1px solid rgba(99,102,241,0.22)` }}
            >
              Dashboard <ArrowRight size={13} />
            </motion.button>
            <motion.button
              whileHover={{ scale: 1.05, color: '#f87171' }}
              whileTap={{ scale: 0.95 }}
              onClick={onLogout}
              className="p-1.5 rounded-lg transition-all"
              title="Sign out"
              style={{ color: '#64748b' }}
            >
              <LogOut size={14} />
            </motion.button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <motion.button
              whileHover={{ scale: 1.02, background: 'rgba(255,255,255,0.07)', borderColor: 'rgba(148,163,184,0.28)' }}
              whileTap={{ scale: 0.97 }}
              onClick={signIn}
              disabled={loginLoading}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-[13px] font-semibold transition-all cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
              style={{ background: 'rgba(255,255,255,0.04)', color: C.text1, border: '1px solid rgba(148,163,184,0.15)' }}
            >
              {loginLoading ? <Loader2 size={14} className="animate-spin" /> : <GoogleIcon />}
              Sign in with Google
            </motion.button>
            <motion.button
              whileHover={{ scale: 1.02, color: C.text1 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => setShowGuestModal(true)}
              className="px-3 py-2 rounded-lg text-[12px] font-medium transition-all cursor-pointer"
              style={{ color: C.text3 }}
            >
              Guest
            </motion.button>
          </div>
        )}
      </motion.header>

      {/* ── Hero ── */}
      <section id="live-demo" className="relative z-10 pt-5 pb-4 px-6">
        <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-[1fr_460px] gap-8 lg:gap-12 items-start">

        {/* ── Left: open editorial copy ── */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
          className="flex flex-col text-left pt-1"
        >
          {/* Eyebrow pill */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.05 }}
            className="inline-flex items-center gap-2 self-start px-3 py-1.5 rounded-full mb-4"
            style={{ background: `${C.indigo}18`, border: `1px solid ${C.indigo}30` }}
          >
            <motion.span
              animate={{ opacity: [1, 0.3, 1] }}
              transition={{ duration: 1.8, repeat: Infinity }}
              className="w-1.5 h-1.5 rounded-full"
              style={{ background: C.mint }}
            />
            <span className="text-[11px] font-semibold" style={{ color: C.indigo }}>
              Multi-Agent · Semantic Text-to-SQL
            </span>
          </motion.div>

          {/* Headline */}
          <h1 className="font-black tracking-tight leading-[1.05] mb-3">
            <span className="block text-4xl md:text-5xl lg:text-[3.2rem]" style={{ color: C.text1 }}>
              Ask your database
            </span>
            <span className="block text-4xl md:text-5xl lg:text-[3.2rem]" style={{ color: C.sky }}>
              in plain English.
            </span>
          </h1>

          {/* Subheadline */}
          <p className="text-sm leading-relaxed mb-4 max-w-md" style={{ color: C.text2 }}>
            A self-healing multi-agent pipeline that grounds schema, prunes context, synthesizes SQL, and auto-corrects errors — all before results reach you.
          </p>

          {/* Social proof / slogan */}
          <div className="mb-4">
            <SloganCycle />
          </div>

          {/* Stats + Benchmarks — unified compact row */}
          <div className="flex flex-wrap items-stretch gap-2 mb-4">
            {/* Pipeline stats */}
            {STATS.map(({ value, sfx, label }, i) => (
              <div
                key={label}
                className="flex flex-col justify-between px-3.5 py-2 rounded-xl min-w-[80px]"
                style={{ background: 'rgba(255,255,255,0.05)', border: `1px solid ${C.border}` }}
              >
                <div
                  className="text-[1.5rem] font-black tabular-nums leading-none mb-1"
                  style={{ color: [C.sky, C.indigo, C.violet][i] }}
                >
                  <Counter to={value} sfx={sfx} />
                </div>
                <div className="text-[9px] font-semibold uppercase tracking-wider leading-tight" style={{ color: C.text3 }}>{label}</div>
              </div>
            ))}

            {/* Benchmark results */}
            {BENCHMARKS.map(({ name, accuracy, detail, color, desc }, i) => (
              <motion.div
                key={name}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.45, delay: 0.2 + i * 0.08 }}
                className="flex flex-col justify-between px-3.5 py-2 rounded-xl"
                style={{ background: `${color}0a`, border: `1px solid ${color}28` }}
              >
                <div className="flex items-baseline gap-1 mb-1 leading-none">
                  <span className="text-[1.6rem] font-black tabular-nums" style={{ color }}>{accuracy}%</span>
                  <span className="text-[9px] font-medium" style={{ color: `${color}99` }}>{desc}</span>
                </div>
                <div>
                  <div className="text-[9px] font-bold uppercase tracking-wider leading-none mb-0.5" style={{ color }}>{name}</div>
                  <div className="text-[8px]" style={{ color: C.text3 }}>{detail}</div>
                </div>
              </motion.div>
            ))}
          </div>

          {/* CTA pair */}
          <div className="flex flex-row items-center gap-3 mb-3 flex-wrap">
            <MagneticCTA onClick={user ? onEnter : signInAndEnter}>
              {user ? 'Launch Dashboard' : 'Sign in & Launch'}
            </MagneticCTA>
            <motion.button
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => document.getElementById('architecture')?.scrollIntoView({ behavior: 'smooth' })}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all"
              style={{ color: C.text2, border: `1px solid ${C.border}` }}
            >
              See how it works
              <ChevronRight size={14} style={{ color: C.text3 }} />
            </motion.button>
            {/* Download setup script button */}
            <motion.a
              href="https://raw.githubusercontent.com/NG-VikasV/TT_SQL/main/setup-client.ps1"
              download="setup-client.ps1"
              target="_blank"
              rel="noopener noreferrer"
              whileHover={{ scale: 1.03, borderColor: 'rgba(61,184,176,0.45)', color: '#3db8b0' }}
              whileTap={{ scale: 0.97 }}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-[12px] font-semibold transition-all no-underline"
              style={{
                color: C.teal,
                border: `1px solid rgba(61,184,176,0.25)`,
                background: 'rgba(61,184,176,0.06)',
              }}
              title="Download the one-time client setup script for Wi-Fi access"
            >
              <Download size={13} />
              Client Setup Script
            </motion.a>
          </div>

          {/* Trust line */}
          <div className="flex items-center gap-2 flex-wrap">
            {['Spider2-Lite', 'DataAgentBench', 'SSE Streaming', '6 SQL Dialects'].map((tag, i) => (
              <span
                key={tag}
                className="text-[10px] font-mono px-2 py-0.5 rounded"
                style={{ color: C.text3, background: 'rgba(148,163,184,0.05)', border: '1px solid rgba(148,163,184,0.08)' }}
              >
                {tag}
              </span>
            ))}
          </div>
        </motion.div>{/* end left col */}

        {/* ── Right: live demo panel ── */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25, duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
          className="flex flex-col gap-3 rounded-2xl p-4"
          style={{ background: 'rgba(22,34,50,0.92)', border: '1px solid rgba(61,184,176,0.18)', backdropFilter: 'blur(20px)', boxShadow: '0 20px 50px rgba(0,0,0,0.28), 0 0 0 1px rgba(61,184,176,0.06) inset' }}
        >
          {/* Header + input */}
          <div>
            <div className="flex items-center gap-2 mb-2.5">
              <Sparkles className="w-3 h-3 text-indigo-400" />
              <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400">Live IPL Sandbox</span>
              <span className="ml-auto text-[8px] font-mono px-1.5 py-0.5 rounded-full" style={{ background: `${C.mint}14`, color: C.mint, border: `1px solid ${C.mint}22` }}>
                <motion.span animate={{ opacity: [1, 0.4, 1] }} transition={{ duration: 1.6, repeat: Infinity }} className="inline-block">●</motion.span> LIVE
              </span>
            </div>
            <div className="relative mb-2.5">
              <input
                type="text"
                value={demoQuery}
                onChange={(e) => setDemoQuery(e.target.value)}
                placeholder={placeholderText}
                onKeyDown={(e) => e.key === 'Enter' && handleRunDemo(demoQuery)}
                disabled={demoLoading}
                className="w-full text-xs bg-slate-950/60 text-slate-100 placeholder-slate-600 pl-3.5 pr-10 py-2.5 rounded-xl border focus:outline-none transition-all"
                style={{ borderColor: demoLoading ? `${C.indigo}33` : 'rgba(148,163,184,0.12)' }}
              />
              <button
                onClick={() => handleRunDemo(demoQuery)}
                disabled={demoLoading || !demoQuery.trim()}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 disabled:text-slate-600 text-white transition-all cursor-pointer"
              >
                {demoLoading
                  ? <motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}><Loader2 className="w-3 h-3" /></motion.div>
                  : <ArrowRight className="w-3 h-3" />}
              </button>
            </div>
            {/* Chips — compact inline pills */}
            <div className="flex gap-1.5 flex-wrap">
              {SUGGESTED_QUERIES.map((q) => (
                <button
                  key={q.label}
                  onClick={() => handleChipClick(q.text)}
                  disabled={demoLoading}
                  className="px-2.5 py-1 rounded-lg text-[9px] font-mono font-semibold border transition-all cursor-pointer flex items-center gap-1.5 bg-slate-900/50 hover:bg-slate-800 border-slate-800 hover:border-slate-700"
                  style={{ color: q.col }}
                >
                  <q.icon className="w-2.5 h-2.5 shrink-0" />
                  {q.label}
                </button>
              ))}
            </div>
          </div>

          {/* Terminal */}
          <div className="rounded-xl border flex flex-col bg-slate-950/70 min-h-[280px]" style={{ borderColor: 'rgba(148,163,184,0.08)' }}>
            <div className="flex items-center gap-2 px-3 py-2 border-b border-slate-800/50 shrink-0">
              <span className="w-2 h-2 rounded-full bg-rose-500/70" />
              <span className="w-2 h-2 rounded-full bg-amber-500/70" />
              <span className="w-2 h-2 rounded-full bg-emerald-500/70" />
              <span className="text-[9px] font-mono text-slate-600 ml-1">nquire-sandbox</span>
            </div>
            <div className="flex-1 font-mono text-[10px] leading-relaxed overflow-auto p-3 flex flex-col">
              {demoStage === 0 && !demoError && (
                <div className="flex flex-col items-center justify-center h-full text-center py-8 gap-2">
                  <Terminal className="w-5 h-5 text-slate-700" />
                  <p className="text-slate-500 text-[9px] font-bold">Sandbox Console</p>
                  <p className="text-[9px] text-slate-600">Type a question or pick a chip above.</p>
                </div>
              )}
              {demoError && (
                <div className="text-rose-400 bg-rose-950/20 border border-rose-900/30 rounded-lg p-2.5 flex gap-2 text-[9px]">
                  <AlertCircle className="w-3 h-3 shrink-0 mt-0.5" />
                  <pre className="whitespace-pre-wrap">{demoError}</pre>
                </div>
              )}
              {demoLoading && (
                <div className="text-slate-300 whitespace-pre-wrap flex-1 text-[9px]">
                  {getStageLog(demoStage)}
                  <motion.span animate={{ opacity: [1,0,1] }} transition={{ duration: 0.8, repeat: Infinity }} className="inline-block w-1 h-3 bg-indigo-400 ml-1 align-middle" />
                </div>
              )}
              {demoStage === 6 && demoResult && (
                <div className="flex flex-col h-full">
                  <div className="flex items-center justify-between border-b border-slate-800/50 pb-1.5 mb-2 shrink-0">
                    <div className="flex gap-1">
                      {[{id:'sql',label:'SQL',icon:Code},{id:'table',label:'Table',icon:Database},{id:'plot',label:'Plot',icon:BarChart3}].map(t => {
                        const Icon = t.icon; const isAct = sandboxTab === t.id;
                        return (
                          <button key={t.id} onClick={() => setSandboxTab(t.id)}
                            className="flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-mono font-bold transition-all cursor-pointer"
                            style={{ background: isAct ? 'rgba(99,102,241,0.12)' : 'transparent', color: isAct ? C.indigo : C.text3, border: isAct ? `1px solid rgba(99,102,241,0.2)` : '1px solid transparent' }}>
                            <Icon size={9} />{t.label}
                          </button>
                        );
                      })}
                    </div>
                    <div className="flex gap-1">
                      <button onClick={handleExportCSV} className="flex items-center gap-1 text-[9px] font-mono text-slate-500 hover:text-slate-200 bg-slate-900 border border-slate-800 px-1.5 py-0.5 rounded cursor-pointer">
                        <Download size={9} className="text-sky-400" />CSV
                      </button>
                      {sandboxTab === 'sql' && (
                        <button onClick={() => handleCopy(demoResult.sql)} className="flex items-center gap-1 text-[9px] font-mono text-slate-500 hover:text-slate-200 bg-slate-900 border border-slate-800 px-1.5 py-0.5 rounded cursor-pointer">
                          {copied ? <><Check size={9} className="text-emerald-400" />Copied</> : <><Copy size={9} />Copy</>}
                        </button>
                      )}
                    </div>
                  </div>
                  <div className="flex-1 min-h-0">
                    {sandboxTab === 'sql' && (
                      <div className="bg-slate-900/80 rounded-lg p-2.5 border border-slate-800/60 overflow-auto text-[9.5px] max-h-[210px]">
                        <span className="text-violet-400">SELECT</span>{' '}
                        {demoResult.sql.replace(/SELECT\s+/i,'').replace(/FROM\s+/i,'\n\n').split('\n').map((line,idx) => {
                          const h = line
                            .replace(/\b(\d+)\b/g,'<span class="text-sky-400">$1</span>')
                            .replace(/\b(SELECT|FROM|JOIN|LEFT JOIN|WHERE|GROUP BY|ORDER BY|LIMIT|HAVING|AND|OR|ON|AS|ROUND|CAST|SUM|COUNT|COALESCE)\b/gi,'<span class="text-violet-400 font-bold">$1</span>')
                            .replace(/\b(ASC|DESC)\b/gi,'<span class="text-amber-400 font-bold">$1</span>')
                            .replace(/('[^']*')/gi,'<span class="text-emerald-400">$1</span>');
                          return <div key={idx} dangerouslySetInnerHTML={{ __html: h }} />;
                        })}
                      </div>
                    )}
                    {sandboxTab === 'table' && (
                      <div>
                        <div className="text-[9px] text-emerald-400 mb-1.5">✓ {demoResult.results.length} rows returned</div>
                        <div className="border border-slate-800 rounded-lg overflow-auto bg-slate-950/40 max-h-[200px]">
                          {demoResult.results.length > 0 ? (
                            <table className="w-full text-[9px] border-collapse text-left">
                              <thead><tr className="border-b border-slate-800 bg-slate-900/60 sticky top-0 text-slate-400 font-bold">{demoResult.columns.map(col => <th key={col} className="px-2 py-1.5 font-mono whitespace-nowrap">{col}</th>)}</tr></thead>
                              <tbody className="divide-y divide-slate-900">
                                {demoResult.results.map((row,rIdx) => (
                                  <tr key={rIdx} className="hover:bg-slate-900/40 text-slate-300">
                                    {demoResult.columns.map(col => { const v=row[col]; return <td key={col} className="px-2 py-1.5 font-mono whitespace-nowrap">{v===null?<span className="text-slate-600 italic">NULL</span>:typeof v==='number'?<span className="text-sky-400">{v}</span>:v}</td>; })}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          ) : <div className="text-slate-600 text-center py-6 text-[9px]">No rows returned.</div>}
                        </div>
                      </div>
                    )}
                    {sandboxTab === 'plot' && (
                      <div className="min-h-[160px]"><SmartPlot results={demoResult.results} columns={demoResult.columns} /></div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Compact horizontal milestone strip */}
          <div className="flex items-center gap-0.5 pt-0.5">
            {MILESTONES.map((step, idx) => {
              const isCompleted = demoStage > step.id || demoStage === 6;
              const isActive    = demoStage === step.id;
              return (
                <div key={step.id} className="flex items-center gap-0.5 flex-1 min-w-0">
                  <motion.div
                    animate={{ borderColor: isCompleted ? step.col : isActive ? step.col : 'rgba(148,163,184,0.12)', backgroundColor: isCompleted ? `${step.col}18` : isActive ? `${step.col}0c` : 'transparent', boxShadow: isActive ? `0 0 6px ${step.col}50` : 'none' }}
                    transition={{ duration: 0.3 }}
                    className="w-5 h-5 rounded-full border flex items-center justify-center shrink-0"
                  >
                    {isCompleted
                      ? <CheckCircle2 size={8} style={{ color: step.col }} />
                      : <step.icon size={8} style={{ color: isActive ? step.col : C.text3 }} />}
                  </motion.div>
                  <span className="text-[7.5px] font-mono truncate hidden sm:block" style={{ color: isActive ? step.col : isCompleted ? C.text2 : C.text3 }}>{step.name}</span>
                  {idx < MILESTONES.length - 1 && (
                    <motion.div className="flex-1 h-px mx-0.5" animate={{ backgroundColor: isCompleted ? `${step.col}80` : 'rgba(148,163,184,0.08)' }} transition={{ duration: 0.3 }} />
                  )}
                </div>
              );
            })}
          </div>
        </motion.div>

        </div>{/* end two-col grid */}
      </section>

      {/* ── Scrolling strength highlights ticker ── */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.8, duration: 0.6 }}
        className="relative z-10 overflow-hidden py-3 mb-12"
        style={{ borderTop: `1px solid ${C.border}`, borderBottom: `1px solid ${C.border}`, background: `${C.surface1}` }}
      >
        <style>{`
          @keyframes marquee { 0% { transform: translateX(0); } 100% { transform: translateX(-50%); } }
          .marquee-track { animation: marquee 28s linear infinite; }
          .marquee-track:hover { animation-play-state: paused; }
        `}</style>
        <div className="flex marquee-track" style={{ width: 'max-content' }}>
          {[...STRENGTHS_LIST, ...STRENGTHS_LIST].map((item, idx) => (
            <div
              key={idx}
              className="flex items-center gap-2 px-6 shrink-0"
            >
              <span
                className="w-1.5 h-1.5 rounded-full shrink-0"
                style={{ background: item.col, boxShadow: `0 0 6px ${item.col}` }}
              />
              <span
                className="text-[10px] font-mono font-bold uppercase tracking-wider whitespace-nowrap"
                style={{ color: item.col }}
              >
                {item.title}
              </span>
              <span className="text-slate-700 text-xs mx-1">·</span>
            </div>
          ))}
        </div>
      </motion.div>

      {/* ── Testimonials ── */}
      <TestimonialsStrip />

      {/* ── Agent Architecture Flow ── */}
      <section id="architecture" className="relative z-10 max-w-5xl mx-auto px-6 mb-24 scroll-mt-24 text-center">
        {/* Shimmering Slogan / Intro Block */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="mb-10 animate-fade-in"
        >
          <span
            className="text-[10px] font-mono font-bold px-2.5 py-1 rounded-full uppercase tracking-wider mb-4 inline-block"
            style={{ background: `${C.violet}14`, color: C.violet, border: `1px solid ${C.violet}22` }}
          >
            Agentic System Orchestration
          </span>
          
          <h2 className="text-3xl md:text-4xl font-extrabold tracking-tight mb-2" style={{ color: C.text1 }}>
            Multi-Agent Architecture Flow
          </h2>
          
          <div className="mb-4">
            <SloganCycle />
          </div>

          <p className="text-xs max-w-2xl mx-auto text-slate-400 leading-relaxed">
            nQuire v2 is engineered with a self-healing agentic pipeline that grounds ambiguous terms, prunes schema payload token bloat, lints syntax, and repairs database execution errors automatically before results are finalized.
          </p>
        </motion.div>

        {/* Strengths Card Grid */}
        <StrengthsGrid />

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 rounded-3xl p-6 md:p-8"
             style={{
               background: C.surface1,
               border: `1px solid ${C.border}`,
               backdropFilter: 'blur(16px)',
             }}
        >
          {/* Left Column: Interactive Diagram (7 cols) */}
          <div className="lg:col-span-7 flex flex-col items-center justify-center bg-slate-950/40 rounded-2xl border border-slate-900/50 p-4 relative overflow-hidden min-h-[420px]">
            <svg 
              width="100%" 
              height="100%" 
              viewBox="0 0 600 450" 
              className="overflow-visible max-w-[500px]"
            >
              <defs>
                <filter id="nodeGlow" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="8" result="blur" />
                  <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
                <filter id="pulseGlow" x="-50%" y="-50%" width="200%" height="200%">
                  <feDropShadow dx="0" dy="0" stdDeviation="5" floodColor={C.indigo} />
                </filter>
              </defs>

              {/* Connector Wires */}
              {[
                { id: 'linker', name: 'Schema Linker', col: C.sky, cx: 300, cy: 65, icon: Brain },
                { id: 'pruner', name: 'Context Pruner', col: C.indigo, cx: 438, cy: 145, icon: Layers },
                { id: 'synthesizer', name: 'SQL Synthesizer', col: C.violet, cx: 438, cy: 305, icon: Code },
                { id: 'auditor', name: 'Result Auditor', col: C.teal, cx: 300, cy: 385, icon: Shield },
                { id: 'corrector', name: 'Self-Corrector', col: C.pink, cx: 162, cy: 305, icon: RotateCcw },
                { id: 'sandbox', name: 'Data Sandbox', col: C.mint, cx: 162, cy: 145, icon: Database },
              ].map(agent => {
                const isActive = isPlaying && SIM_STEPS[simStep]?.activeNodes.includes(agent.id);
                return (
                  <g key={agent.id}>
                    <line 
                      x1={300} 
                      y1={225} 
                      x2={agent.cx} 
                      y2={agent.cy} 
                      stroke={isActive ? `${agent.col}44` : 'rgba(148,163,184,0.08)'} 
                      strokeWidth={isActive ? 2 : 1}
                      className="transition-colors duration-300"
                    />
                  </g>
                );
              })}

              {/* Animated pulses */}
              {isPlaying && SIM_STEPS[simStep]?.pulse && (() => {
                const pulse = SIM_STEPS[simStep].pulse;
                const agentsList = [
                  { id: 'linker', cx: 300, cy: 65 },
                  { id: 'pruner', cx: 438, cy: 145 },
                  { id: 'synthesizer', cx: 438, cy: 305 },
                  { id: 'auditor', cx: 300, cy: 385 },
                  { id: 'corrector', cx: 162, cy: 305 },
                  { id: 'sandbox', cx: 162, cy: 145 }
                ];
                let startCoords = { x: 300, y: 225 };
                let endCoords = { x: 300, y: 225 };
                
                if (pulse.from !== 'orchestrator' && pulse.from !== 'user') {
                  const sAgent = agentsList.find(a => a.id === pulse.from);
                  if (sAgent) startCoords = { x: sAgent.cx, y: sAgent.cy };
                }
                if (pulse.to !== 'orchestrator') {
                  const eAgent = agentsList.find(a => a.id === pulse.to);
                  if (eAgent) endCoords = { x: eAgent.cx, y: eAgent.cy };
                }
                
                if (pulse.from === 'user') {
                  startCoords = { x: 50, y: 225 };
                }

                return (
                  <motion.circle
                    key={simStep}
                    r="5"
                    fill={C.sky}
                    filter="url(#pulseGlow)"
                    animate={{
                      cx: [startCoords.x, endCoords.x],
                      cy: [startCoords.y, endCoords.y]
                    }}
                    transition={{
                      duration: 1.5,
                      repeat: Infinity,
                      ease: 'easeInOut'
                    }}
                  />
                );
              })()}

              {/* Central Orchestrator Node */}
              {(() => {
                const isNodeActive = isPlaying && SIM_STEPS[simStep]?.activeNodes.includes('orchestrator');
                const isSelected = selectedAgent === 'orchestrator';
                return (
                  <g 
                    className="cursor-pointer"
                    onClick={() => setSelectedAgent('orchestrator')}
                  >
                    <motion.circle 
                      cx={300} 
                      cy={225} 
                      r={36} 
                      fill="#090d22" 
                      stroke={isSelected ? '#fff' : isNodeActive ? C.indigo : 'rgba(148,163,184,0.2)'}
                      strokeWidth={isSelected ? 3 : 2}
                      filter={isNodeActive || isSelected ? 'url(#nodeGlow)' : ''}
                      style={{ filter: isNodeActive ? `drop-shadow(0 0 12px ${C.indigo}88)` : '' }}
                    />
                    <Cpu x={285} y={210} className="w-7 h-7 text-indigo-400" />
                    <text x={300} y={276} textAnchor="middle" fill={C.text1} className="font-mono text-[9px] font-bold">Orchestrator</text>
                  </g>
                );
              })()}

              {/* Satellite Agent Nodes */}
              {[
                { id: 'linker', name: 'Schema Linker', col: C.sky, cx: 300, cy: 65, icon: Brain },
                { id: 'pruner', name: 'Context Pruner', col: C.indigo, cx: 438, cy: 145, icon: Layers },
                { id: 'synthesizer', name: 'SQL Synthesizer', col: C.violet, cx: 438, cy: 305, icon: Code },
                { id: 'auditor', name: 'Result Auditor', col: C.teal, cx: 300, cy: 385, icon: Shield },
                { id: 'corrector', name: 'Self-Corrector', col: C.pink, cx: 162, cy: 305, icon: RotateCcw },
                { id: 'sandbox', name: 'Data Sandbox', col: C.mint, cx: 162, cy: 145, icon: Database },
              ].map(agent => {
                const isNodeActive = isPlaying && SIM_STEPS[simStep]?.activeNodes.includes(agent.id);
                const isSelected = selectedAgent === agent.id;
                const Icon = agent.icon;
                
                return (
                  <g 
                    key={agent.id}
                    className="cursor-pointer"
                    onClick={() => setSelectedAgent(agent.id)}
                  >
                    <motion.circle 
                      cx={agent.cx} 
                      cy={agent.cy} 
                      r={26} 
                      fill="#090d22" 
                      stroke={isSelected ? '#fff' : isNodeActive ? agent.col : 'rgba(148,163,184,0.15)'}
                      strokeWidth={isSelected ? 2.5 : 1.5}
                      style={{ filter: isNodeActive || isSelected ? `drop-shadow(0 0 10px ${agent.col}aa)` : '' }}
                    />
                    <Icon x={agent.cx - 9} y={agent.cy - 9} className="w-4 h-4" style={{ color: isNodeActive || isSelected ? agent.col : C.text2 }} />
                    <text 
                      x={agent.cx} 
                      y={agent.cy > 225 ? agent.cy + 38 : agent.cy - 34} 
                      textAnchor="middle" 
                      fill={isNodeActive || isSelected ? C.text1 : C.text3} 
                      className="font-mono text-[8.5px] font-bold"
                    >
                      {agent.name}
                    </text>
                  </g>
                );
              })}
            </svg>
            
            {/* Simulation Steps Controller */}
            <div className="w-full flex items-center justify-between mt-4 border-t border-slate-900 pt-4 bg-slate-950/20 px-4 py-2 rounded-xl">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    setIsPlaying(!isPlaying);
                    if (!isPlaying && simStep === SIM_STEPS.length - 1) {
                      setSimStep(0);
                    }
                  }}
                  className="p-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-colors cursor-pointer"
                >
                  {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5 fill-current" />}
                </button>
                <button
                  onClick={() => {
                    setIsPlaying(false);
                    setSimStep(0);
                  }}
                  className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
                  title="Reset"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                </button>
              </div>

              <div className="flex-1 mx-4">
                <div className="flex justify-between text-[8px] font-mono text-slate-500 mb-1">
                  <span>Simulation Progress</span>
                  <span>Step {isPlaying ? simStep + 1 : 0} of {SIM_STEPS.length}</span>
                </div>
                <div className="w-full h-1 bg-slate-900 rounded-full overflow-hidden">
                  <motion.div 
                    className="h-full bg-indigo-500"
                    animate={{ width: isPlaying ? `${((simStep + 1) / SIM_STEPS.length) * 100}%` : '0%' }}
                    transition={{ duration: 0.3 }}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: Console Mind & Details Panel (5 cols) */}
          <div className="lg:col-span-5 flex flex-col gap-4">
            <div className="flex-1 rounded-2xl border border-slate-900/60 bg-slate-950/60 p-4 flex flex-col h-48 max-h-48 overflow-hidden font-mono text-left">
              <div className="flex items-center justify-between border-b border-slate-900 pb-2 mb-2">
                <span className="text-[9px] text-indigo-400 font-bold uppercase tracking-wider flex items-center gap-1.5">
                  <Terminal className="w-3 h-3 text-indigo-400" />
                  Agent Execution Mind
                </span>
                <span className="text-[8px] text-slate-500">Live Telemetry</span>
              </div>
              
              <div className="flex-1 overflow-y-auto text-[9.5px] leading-relaxed text-slate-300 whitespace-pre-wrap">
                {isPlaying ? (
                  <div>
                    <div className="text-violet-400 font-bold mb-1.5">{SIM_STEPS[simStep]?.title}</div>
                    <div className="text-slate-400 mb-2 italic text-[9px]">{SIM_STEPS[simStep]?.description}</div>
                    <div className="bg-slate-950/80 p-2 rounded-lg border border-slate-900 text-slate-200 text-[9px] font-mono">
                      {SIM_STEPS[simStep]?.log}
                    </div>
                  </div>
                ) : (
                  <div className="text-slate-500 text-center py-8">
                    Simulation paused. Click Play to watch live telemetry agent thoughts.
                  </div>
                )}
              </div>
            </div>

            <div className="flex-1 rounded-2xl border border-slate-900/60 bg-slate-950/60 p-4 flex flex-col h-56 max-h-56 overflow-y-auto text-left">
              {selectedAgent && AGENT_DETAILS[selectedAgent] ? (
                (() => {
                  const details = AGENT_DETAILS[selectedAgent];
                  return (
                    <div className="flex flex-col gap-2 font-mono text-[9.5px]">
                      <div className="flex items-center justify-between border-b border-slate-900 pb-1.5">
                        <span className="text-[10px] font-bold text-slate-200">{details.name}</span>
                        <span className="text-[8px] px-1.5 py-0.5 rounded bg-indigo-950/30 text-indigo-400 border border-indigo-900/20 uppercase font-bold tracking-wider">
                          Agent Spec
                        </span>
                      </div>
                      
                      <div>
                        <span className="text-slate-500 font-bold">Role: </span>
                        <span className="text-slate-300">{details.role}</span>
                      </div>
                      
                      <div>
                        <span className="text-slate-500 font-bold">Description: </span>
                        <span className="text-slate-400 leading-normal text-[9px]">{details.desc}</span>
                      </div>
                      
                      <div className="bg-slate-905/40 p-2 rounded border border-slate-900">
                        <span className="text-violet-400 font-bold block mb-1">System Instructions:</span>
                        <span className="text-slate-400 text-[8.5px] italic leading-tight block">"{details.prompt}"</span>
                      </div>

                      <div className="grid grid-cols-2 gap-2 mt-1 pt-1 border-t border-slate-900">
                        <div>
                          <span className="text-slate-500 font-bold block text-[8px]">Inputs:</span>
                          <span className="text-[8.5px] text-slate-400 truncate block" title={details.input}>{details.input}</span>
                        </div>
                        <div>
                          <span className="text-slate-500 font-bold block text-[8px]">Outputs:</span>
                          <span className="text-[8.5px] text-slate-400 truncate block" title={details.output}>{details.output}</span>
                        </div>
                      </div>
                    </div>
                  );
                })()
              ) : (
                <div className="text-slate-500 text-center py-12 font-mono text-[9.5px]">
                  <Info className="w-5 h-5 mx-auto mb-2 text-slate-600" />
                  Click any agent node in the radial graph to view its prompts and schema specifications.
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* ── Features ── */}
      <section id="pipeline" className="relative z-10 max-w-5xl mx-auto px-6 mb-24 scroll-mt-24">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.55, duration: 0.5 }}
          className="text-center mb-12"
        >
          <h2
            className="text-2xl md:text-3xl font-extrabold tracking-tight mb-3"
            style={{ color: C.text1 }}
          >
            Enterprise pipeline intelligence
          </h2>
          <p className="text-sm max-w-lg mx-auto" style={{ color: C.text2 }}>
            Every query passes through an 8-stage agentic system that understands schema, validates results, and heals its own mistakes.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {FEATURES.map((f, i) => <FeatureCard key={f.title} f={f} i={i} />)}
        </div>
      </section>

      {/* ── Bottom CTA ── */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.9, duration: 0.5 }}
        className="relative z-10 max-w-4xl mx-auto px-6 mb-20"
      >
        <div
          className="relative overflow-hidden rounded-3xl p-12 text-center"
          style={{
            background: 'linear-gradient(135deg, rgba(30,64,175,0.18) 0%, rgba(79,70,229,0.14) 40%, rgba(14,116,144,0.16) 100%)',
            border: `1px solid rgba(99,102,241,0.18)`,
            backdropFilter: 'blur(20px)',
          }}
        >
          {/* Decorative glow */}
          <div
            className="absolute top-0 left-1/2 -translate-x-1/2 w-64 h-1 rounded-full"
            style={{ background: `linear-gradient(90deg, transparent, ${C.indigo}80, transparent)` }}
          />

          <div className="flex items-center justify-center gap-1.5 mb-5">
            {[C.sky, C.indigo, C.violet, C.teal, C.mint].map((c, i) => (
              <motion.span
                key={i}
                animate={{ opacity: [0.4, 1, 0.4] }}
                transition={{ duration: 2, repeat: Infinity, delay: i * 0.3 }}
                className="w-1.5 h-1.5 rounded-full"
                style={{ background: c }}
              />
            ))}
          </div>

          <h2
            className="text-xl md:text-2xl font-extrabold tracking-tight mb-3"
            style={{ color: C.text1 }}
          >
            Ready to query your database in plain English?
          </h2>
          <p className="text-sm mb-8 max-w-md mx-auto" style={{ color: C.text2 }}>
            Load a Spider2-Lite or DataAgentBench project and experience the full 8-stage pipeline with live telemetry.
          </p>

          <div className="flex justify-center">
            <MagneticCTA onClick={user ? onEnter : signInAndEnter}>
              {user ? 'Enter Dashboard' : 'Sign in & Enter'}
            </MagneticCTA>
          </div>
        </div>
      </motion.section>

      {/* ── Footer ── */}
      <footer
        className="relative z-10 mt-4"
        style={{ borderTop: `1px solid ${C.border}` }}
      >
        {/* Animated top accent line */}
        <div className="relative h-px w-full overflow-hidden">
          <motion.div
            animate={{ x: ['-100%', '100%'] }}
            transition={{ duration: 4, repeat: Infinity, ease: 'linear' }}
            className="absolute inset-y-0 w-1/3"
            style={{ background: `linear-gradient(90deg, transparent, ${C.indigo}80, ${C.sky}80, transparent)` }}
          />
        </div>

        <div
          className="relative"
          style={{ background: 'rgba(5, 9, 26, 0.96)', backdropFilter: 'blur(24px)' }}
        >
          {/* Subtle background glow */}
          <div
            className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[600px] h-[200px] pointer-events-none"
            style={{ background: `radial-gradient(ellipse at 50% 100%, ${C.indigo}08 0%, transparent 70%)` }}
          />

          {/* Main footer grid */}
          <div className="relative max-w-6xl mx-auto px-8 pt-14 pb-10">
            <div className="grid grid-cols-1 md:grid-cols-12 gap-10 mb-12">

              {/* ── Brand Column ── */}
              <div className="md:col-span-4">
                {/* Ngenux logo wordmark */}
                <div className="flex items-center gap-3 mb-4">
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
                    style={{
                      background: 'linear-gradient(135deg, #0f1e5c 0%, #3730a3 55%, #1d4ed8 100%)',
                      boxShadow: `0 0 20px ${C.indigo}30`,
                      border: `1px solid ${C.indigo}30`,
                    }}
                  >
                    {/* N letterform */}
                    <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
                      <path d="M3 18V4L19 18V4" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </div>
                  <div>
                    <div
                      className="text-lg font-black tracking-tight leading-none"
                      style={{
                        background: 'linear-gradient(120deg, #e2e8f8 30%, #93c5fd 70%)',
                        WebkitBackgroundClip: 'text',
                        WebkitTextFillColor: 'transparent',
                        backgroundClip: 'text',
                      }}
                    >
                      Ngenux
                    </div>
                    <div className="text-[9px] font-mono uppercase tracking-widest mt-0.5" style={{ color: C.text3 }}>
                      Solutions LLP
                    </div>
                  </div>
                </div>

                <p className="text-[11px] leading-relaxed mb-5 max-w-xs" style={{ color: C.text2 }}>
                  Ngenux is an AI-first engineering company building intelligent, agentic systems that transform how enterprises interact with data, code, and knowledge. We design systems that think, adapt, and self-correct.
                </p>

                {/* Product badge */}
                <div
                  className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg mb-5"
                  style={{ background: `${C.sky}0c`, border: `1px solid ${C.sky}22` }}
                >
                  <NQuireLogo size={18} />
                  <span className="text-[10px] font-mono font-bold" style={{ color: C.sky }}>
                    nQuire v2 — flagship product
                  </span>
                </div>

                {/* Social links */}
                <div className="flex items-center gap-3">
                  {[
                    {
                      label: 'LinkedIn',
                      href: 'https://www.linkedin.com/company/ngenux',
                      icon: (
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                          <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6zM2 9h4v12H2z"/>
                          <circle cx="4" cy="4" r="2"/>
                        </svg>
                      )
                    },
                    {
                      label: 'GitHub',
                      href: 'https://github.com/ngenux',
                      icon: (
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                          <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/>
                        </svg>
                      )
                    },
                    {
                      label: 'Website',
                      href: 'https://www.ngenux.com',
                      icon: (
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/>
                          <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
                        </svg>
                      )
                    },
                    {
                      label: 'Email',
                      href: 'mailto:hello@ngenux.com',
                      icon: (
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
                          <polyline points="22,6 12,13 2,6"/>
                        </svg>
                      )
                    },
                  ].map(({ label, href, icon }) => (
                    <motion.a
                      key={label}
                      href={href}
                      target={label !== 'Email' ? '_blank' : undefined}
                      rel="noopener noreferrer"
                      aria-label={label}
                      whileHover={{ scale: 1.15, color: C.sky }}
                      className="w-8 h-8 rounded-lg flex items-center justify-center transition-colors cursor-pointer"
                      style={{
                        background: 'rgba(148,163,184,0.06)',
                        border: `1px solid ${C.border}`,
                        color: C.text3,
                      }}
                    >
                      {icon}
                    </motion.a>
                  ))}
                </div>
              </div>

              {/* ── Nav Columns ── */}
              <div className="md:col-span-8 grid grid-cols-2 sm:grid-cols-3 gap-8">

                {/* Product column */}
                <div>
                  <div className="text-[9px] font-mono font-bold uppercase tracking-widest mb-4" style={{ color: C.sky }}>
                    Product
                  </div>
                  <ul className="space-y-2.5">
                    {[
                      { label: 'Live Demo', id: 'live-demo' },
                      { label: 'Pipeline Architecture', id: 'architecture' },
                      { label: 'Benchmarks', id: 'live-demo' },
                      { label: 'Agent Flow Simulator', id: 'architecture' },
                      { label: 'Open Dashboard', action: 'enter' },
                    ].map(({ label, id, action }) => (
                      <li key={label}>
                        <motion.span
                          whileHover={{ color: C.text1, x: 3 }}
                          className="text-[11px] font-medium cursor-pointer inline-block transition-colors"
                          style={{ color: C.text3 }}
                          onClick={() => {
                            if (action === 'enter') { window.scrollTo({ top: 0, behavior: 'smooth' }); }
                            else document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
                          }}
                        >
                          {label}
                        </motion.span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Company column */}
                <div>
                  <div className="text-[9px] font-mono font-bold uppercase tracking-widest mb-4" style={{ color: C.violet }}>
                    Company
                  </div>
                  <ul className="space-y-2.5">
                    {[
                      { label: 'About Ngenux', href: 'https://www.ngenux.com/about' },
                      { label: 'Our Work', href: 'https://www.ngenux.com' },
                      { label: 'Careers', href: 'https://www.ngenux.com/careers' },
                      { label: 'Blog', href: 'https://www.ngenux.com/blog' },
                      { label: 'Contact Us', href: 'mailto:hello@ngenux.com' },
                    ].map(({ label, href }) => (
                      <li key={label}>
                        <motion.a
                          href={href}
                          target={!href.startsWith('mailto') ? '_blank' : undefined}
                          rel="noopener noreferrer"
                          whileHover={{ color: C.text1, x: 3 }}
                          className="text-[11px] font-medium cursor-pointer inline-block transition-colors"
                          style={{ color: C.text3, textDecoration: 'none' }}
                        >
                          {label}
                        </motion.a>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Resources column */}
                <div>
                  <div className="text-[9px] font-mono font-bold uppercase tracking-widest mb-4" style={{ color: C.teal }}>
                    Technology
                  </div>
                  <ul className="space-y-2.5">
                    {[
                      { label: 'Spider2-Lite Eval', href: '#' },
                      { label: 'DataAgentBench', href: '#' },
                      { label: 'Multi-Agent Framework', href: '#' },
                      { label: 'Self-Correction Loop', href: '#' },
                      { label: 'FQN Schema Linker', href: '#' },
                    ].map(({ label, href }) => (
                      <li key={label}>
                        <motion.a
                          href={href}
                          whileHover={{ color: C.text1, x: 3 }}
                          className="text-[11px] font-medium cursor-pointer inline-block transition-colors"
                          style={{ color: C.text3, textDecoration: 'none' }}
                        >
                          {label}
                        </motion.a>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>

            {/* ── Divider ── */}
            <div className="h-px w-full mb-6" style={{ background: C.border }} />

            {/* ── Bottom strip ── */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
              {/* Left — copyright */}
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono" style={{ color: C.text3 }}>
                  © {new Date().getFullYear()} Ngenux Solutions LLP. All rights reserved.
                </span>
              </div>

              {/* Center — built-with stack */}
              <div className="flex items-center gap-1.5 flex-wrap justify-center">
                {['React', 'FastAPI', 'SQLite', 'LLM Agents', 'SSE Streaming'].map((tech, i) => (
                  <span
                    key={tech}
                    className="text-[8px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded-full"
                    style={{
                      background: `${[C.sky,C.indigo,C.violet,C.teal,C.mint][i]}0c`,
                      color: `${[C.sky,C.indigo,C.violet,C.teal,C.mint][i]}cc`,
                      border: `1px solid ${[C.sky,C.indigo,C.violet,C.teal,C.mint][i]}18`,
                    }}
                  >
                    {tech}
                  </span>
                ))}
              </div>

              {/* Right — legal links */}
              <div className="flex items-center gap-4">
                {['Privacy Policy', 'Terms of Use'].map(label => (
                  <motion.a
                    key={label}
                    href="#"
                    whileHover={{ color: C.text2 }}
                    className="text-[10px] font-mono transition-colors"
                    style={{ color: C.text3, textDecoration: 'none' }}
                  >
                    {label}
                  </motion.a>
                ))}
              </div>
            </div>

            {/* ── Made with love strip ── */}
            <div className="flex justify-center mt-6">
              <span className="text-[9px] font-mono flex items-center gap-1.5" style={{ color: C.text3 }}>
                Crafted with
                <motion.span
                  animate={{ scale: [1, 1.3, 1] }}
                  transition={{ duration: 1.4, repeat: Infinity }}
                  style={{ color: '#f472b6' }}
                >♥</motion.span>
                by the Ngenux AI Engineering Team · Bengaluru, India
              </span>
            </div>
          </div>
        </div>
      </footer>

      {/* Guest Login Modal */}
      <AnimatePresence>
        {showGuestModal && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fadeIn font-sans">
            <motion.div
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              transition={{ type: 'spring', damping: 25, stiffness: 200 }}
              className="bg-[#121a28] border border-cyan-500/30 rounded-2xl w-full max-w-md shadow-2xl overflow-hidden flex flex-col relative"
              style={{ boxShadow: '0 20px 50px rgba(0,0,0,0.5), 0 0 0 1px rgba(61,184,176,0.1) inset' }}
            >
              <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-cyan-500 to-indigo-500" />
              
              <div className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
                      <Sparkles className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-white font-mono">Welcome, Guest!</h3>
                      <p className="text-[10px] text-slate-400 font-mono mt-0.5">Please enter a name to initialize your session.</p>
                    </div>
                  </div>
                  <button 
                    onClick={() => { setShowGuestModal(false); setGuestError(""); }}
                    className="p-1.5 rounded-lg bg-slate-900/60 border border-slate-800 text-slate-400 hover:text-white transition-colors cursor-pointer"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>

                <form onSubmit={handleGuestLogin} className="space-y-4">
                  <div className="space-y-1.5 text-left">
                    <label className="text-[10px] font-mono font-bold text-slate-400 uppercase tracking-wider">User Name</label>
                    <input
                      type="text"
                      value={guestName}
                      onChange={(e) => {
                        setGuestName(e.target.value);
                        if (guestError) setGuestError("");
                      }}
                      placeholder="e.g. Vikas"
                      autoFocus
                      className="w-full text-xs bg-slate-950/60 text-slate-100 placeholder-slate-600 px-3.5 py-2.5 rounded-xl border border-slate-800 focus:border-cyan-500/50 focus:outline-none transition-all font-mono"
                    />
                    {guestError && (
                      <p className="text-[10.5px] font-mono text-rose-400 flex items-center gap-1.5 animate-pulse mt-1">
                        <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                        {guestError}
                      </p>
                    )}
                  </div>

                  <div className="flex items-center justify-end gap-3 pt-2">
                    <button
                      type="button"
                      onClick={() => { setShowGuestModal(false); setGuestError(""); }}
                      className="px-4 py-2 rounded-lg font-mono text-xs font-bold text-slate-400 hover:text-slate-200 hover:bg-white/5 transition-all cursor-pointer"
                    >
                      CANCEL
                    </button>
                    <button
                      type="submit"
                      className="px-4 py-2 rounded-lg font-mono text-xs font-bold text-white bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 transition-all shadow-lg shadow-cyan-600/10 flex items-center gap-2 cursor-pointer"
                    >
                      <Play className="w-3.5 h-3.5" />
                      START SESSION
                    </button>
                  </div>
                </form>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default LandingPage;
