import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence, useMotionValue, useSpring } from 'framer-motion';
import {
  Zap, Shield, Brain, GitBranch, BarChart3, Globe,
  ArrowRight, Activity, Database, Layers, Cpu,
  CheckCircle2, ChevronRight, Sparkles
} from 'lucide-react';

/* ─── Palette ──────────────────────────────────────────────────────────────── */
const C = {
  bg:       '#05091a',
  surface1: 'rgba(10,16,38,0.7)',
  surface2: 'rgba(15,24,54,0.5)',
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

/* ─── Data ─────────────────────────────────────────────────────────────────── */
const STRENGTHS = [
  { text: 'Zero-shot Text-to-SQL',        col: C.sky    },
  { text: 'Multi-dialect SQL generation', col: C.violet },
  { text: 'Schema-aware context linking', col: C.teal   },
  { text: 'Self-correcting query loops',  col: C.indigo },
  { text: 'Data-IQ result validation',    col: C.pink   },
  { text: 'Real-time feasibility checks', col: C.mint   },
];

const PIPELINE = [
  { label: 'Schema',      col: C.sky,    delay: 0    },
  { label: 'Feasibility', col: C.indigo, delay: 700  },
  { label: 'Routing',     col: C.violet, delay: 1300 },
  { label: 'SQL Gen',     col: '#f59e0b',delay: 2000 },
  { label: 'Execute',     col: C.mint,   delay: 2900 },
  { label: 'Audit',       col: C.teal,   delay: 3600 },
];
const PIPELINE_CYCLE = 5000;

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
  { value: 8,  sfx: '',  label: 'Pipeline Stages'  },
  { value: 6,  sfx: '+', label: 'SQL Dialects'      },
  { value: 4,  sfx: 'x', label: 'Self-Corrections'  },
  { value: 95, sfx: '%', label: 'Accuracy Target'   },
];

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

/* ─── Rotating strength text ───────────────────────────────────────────────── */
const StrengthCycle = () => {
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setI(x => (x + 1) % STRENGTHS.length), 2400);
    return () => clearInterval(t);
  }, []);
  const s = STRENGTHS[i];
  return (
    <div className="h-7 relative overflow-hidden">
      <AnimatePresence mode="wait">
        <motion.span
          key={i}
          initial={{ y: 28, opacity: 0, filter: 'blur(4px)' }}
          animate={{ y: 0, opacity: 1, filter: 'blur(0px)' }}
          exit={{ y: -28, opacity: 0, filter: 'blur(4px)' }}
          transition={{ duration: 0.38, ease: [0.22, 1, 0.36, 1] }}
          className="absolute inset-0 flex items-center justify-center text-base font-bold font-mono tracking-tight"
          style={{ color: s.col }}
        >
          {s.text}
        </motion.span>
      </AnimatePresence>
    </div>
  );
};

/* ─── Animated pipeline strip ──────────────────────────────────────────────── */
const PipelineStrip = () => {
  const [phase, setPhase] = useState(0); // 0..PIPELINE.length

  useEffect(() => {
    let frame = 0;
    const advance = () => {
      const idx = PIPELINE.findIndex(p => p.delay > frame % PIPELINE_CYCLE);
      setPhase(idx === -1 ? PIPELINE.length : idx);
    };
    const start = Date.now();
    const tick = () => {
      frame = (Date.now() - start) % PIPELINE_CYCLE;
      advance();
    };
    tick();
    const id = setInterval(tick, 60);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="flex items-center gap-0 flex-wrap justify-center">
      {PIPELINE.map((p, i) => {
        const done    = i < phase;
        const running = i === phase;
        return (
          <div key={p.label} className="flex items-center">
            <motion.div
              animate={{
                backgroundColor: done || running ? `${p.col}22` : 'rgba(15,20,40,0.6)',
                borderColor:     done || running ? p.col : 'rgba(148,163,184,0.1)',
                scale:           running ? 1.07 : 1,
                boxShadow:       running ? `0 0 16px 2px ${p.col}44` : 'none',
              }}
              transition={{ duration: 0.35, ease: 'easeOut' }}
              className="px-3 py-1.5 rounded-xl border text-[11px] font-mono font-bold transition-colors"
              style={{ color: done || running ? p.col : '#374151' }}
            >
              {running && (
                <motion.span
                  animate={{ opacity: [1, 0.3, 1] }}
                  transition={{ duration: 0.8, repeat: Infinity }}
                  className="inline-block w-1.5 h-1.5 rounded-full mr-1.5"
                  style={{ backgroundColor: p.col }}
                />
              )}
              {done && <span className="mr-1.5 text-[10px]">✓</span>}
              {p.label}
            </motion.div>
            {i < PIPELINE.length - 1 && (
              <motion.div
                animate={{ backgroundColor: done ? p.col : 'rgba(148,163,184,0.1)' }}
                transition={{ duration: 0.4 }}
                className="w-4 h-px mx-0.5"
              />
            )}
          </div>
        );
      })}
    </div>
  );
};

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
        className="relative z-10 flex items-center gap-3 px-10 py-4 rounded-2xl font-black text-sm tracking-wide"
        style={{
          background: `linear-gradient(135deg, #1e40af 0%, #4f46e5 40%, #7c3aed 70%, #0891b2 100%)`,
          color: '#fff',
          boxShadow: '0 0 40px rgba(99,102,241,0.35), 0 0 80px rgba(56,189,248,0.15)',
        }}
      >
        {/* Shimmer sweep */}
        <motion.div
          className="absolute inset-0 rounded-2xl"
          style={{
            background: 'linear-gradient(105deg, transparent 30%, rgba(255,255,255,0.15) 50%, transparent 70%)',
          }}
          animate={{ x: ['-100%', '200%'] }}
          transition={{ duration: 2.4, repeat: Infinity, repeatDelay: 1.2, ease: 'easeInOut' }}
        />
        <Activity className="w-4 h-4 shrink-0" />
        <span className="relative z-10">{children}</span>
        <motion.div
          className="relative z-10"
          animate={{ x: [0, 4, 0] }}
          transition={{ duration: 1.2, repeat: Infinity, ease: 'easeInOut' }}
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
    <motion.div
      animate={{ scale: [1, 1.08, 1], opacity: [0.18, 0.24, 0.18] }}
      transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
      className="absolute -top-40 -left-40 w-[700px] h-[700px] rounded-full"
      style={{ background: 'radial-gradient(circle, #1e40af44 0%, transparent 70%)' }}
    />
    <motion.div
      animate={{ scale: [1, 1.06, 1], opacity: [0.14, 0.2, 0.14] }}
      transition={{ duration: 10, repeat: Infinity, ease: 'easeInOut', delay: 2 }}
      className="absolute -bottom-60 -right-40 w-[800px] h-[800px] rounded-full"
      style={{ background: 'radial-gradient(circle, #0e7490 0%, transparent 60%)' }}
    />
    <motion.div
      animate={{ y: [0, -20, 0], opacity: [0.08, 0.14, 0.08] }}
      transition={{ duration: 12, repeat: Infinity, ease: 'easeInOut', delay: 4 }}
      className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] rounded-full"
      style={{ background: 'radial-gradient(circle, #4f46e530 0%, transparent 65%)' }}
    />
    {/* Noise grid */}
    <div
      className="absolute inset-0 opacity-[0.018]"
      style={{
        backgroundImage: `linear-gradient(${C.text1} 1px, transparent 1px), linear-gradient(90deg, ${C.text1} 1px, transparent 1px)`,
        backgroundSize: '52px 52px',
      }}
    />
  </div>
);

/* ─── Main component ───────────────────────────────────────────────────────── */
const LandingPage = ({ onEnter }) => {
  return (
    <div className="relative min-h-screen overflow-x-hidden" style={{ background: C.bg, color: C.text1 }}>
      <Orbs />

      {/* ── Navbar ── */}
      <motion.header
        initial={{ opacity: 0, y: -16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="relative z-20 flex items-center justify-between px-8 py-5"
        style={{ borderBottom: `1px solid ${C.border}`, backdropFilter: 'blur(16px)' }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-8 h-8 rounded-xl flex items-center justify-center"
            style={{
              background: 'linear-gradient(135deg, #1e3a8a, #4f46e5)',
              boxShadow: '0 0 20px rgba(79,70,229,0.4)',
            }}
          >
            <Database className="w-4 h-4 text-white" />
          </div>
          <span className="font-extrabold text-sm tracking-tight" style={{ color: C.text1 }}>
            Spider<span style={{ color: C.sky }}>DIN</span>
          </span>
          <span
            className="text-[9px] font-mono font-bold px-2 py-0.5 rounded-full uppercase tracking-widest"
            style={{ background: `${C.sky}14`, color: C.sky, border: `1px solid ${C.sky}22` }}
          >
            v2
          </span>
        </div>

        <nav className="hidden md:flex items-center gap-8 text-xs font-semibold" style={{ color: C.text3 }}>
          {['Pipeline', 'Benchmarks', 'Architecture'].map(n => (
            <motion.span
              key={n}
              whileHover={{ color: C.text1 }}
              className="cursor-pointer transition-colors"
            >
              {n}
            </motion.span>
          ))}
        </nav>

        <motion.button
          whileHover={{ scale: 1.04, boxShadow: `0 0 20px ${C.sky}44` }}
          whileTap={{ scale: 0.96 }}
          onClick={onEnter}
          className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all"
          style={{
            background: `${C.sky}14`,
            color: C.sky,
            border: `1px solid ${C.sky}28`,
          }}
        >
          Open App <ChevronRight size={12} />
        </motion.button>
      </motion.header>

      {/* ── Hero ── */}
      <section className="relative z-10 flex flex-col items-center text-center pt-24 pb-14 px-6">
        {/* Eyebrow */}
        <motion.div
          initial={{ opacity: 0, y: 12, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full mb-7"
          style={{
            background: `${C.indigo}12`,
            border: `1px solid ${C.indigo}30`,
          }}
        >
          <motion.span
            animate={{ scale: [1, 1.4, 1] }}
            transition={{ duration: 1.6, repeat: Infinity }}
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: C.mint }}
          />
          <span className="text-[11px] font-bold font-mono uppercase tracking-widest" style={{ color: C.indigo }}>
            Multi-Agent · Semantic Text-to-SQL
          </span>
        </motion.div>

        {/* Headline */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.18, ease: [0.22, 1, 0.36, 1] }}
        >
          <h1 className="font-black leading-[1.05] tracking-tight mb-6">
            <span
              className="block text-5xl md:text-7xl"
              style={{ color: C.text1 }}
            >
              Natural Language
            </span>
            <span
              className="block text-5xl md:text-7xl"
              style={{
                background: `linear-gradient(120deg, ${C.sky} 0%, ${C.indigo} 45%, ${C.violet} 70%, ${C.teal} 100%)`,
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
              }}
            >
              → Production SQL
            </span>
          </h1>
        </motion.div>

        {/* Rotating strength */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.35 }}
          className="mb-3"
        >
          <span className="text-xs font-mono" style={{ color: C.text3 }}>
            Powered by ·{' '}
          </span>
          <StrengthCycle />
        </motion.div>

        {/* Pipeline strip */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.45, duration: 0.5 }}
          className="mb-12 mt-4"
        >
          <PipelineStrip />
        </motion.div>

        {/* CTA pair */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.55, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          className="flex flex-col sm:flex-row items-center gap-4"
        >
          <MagneticCTA onClick={onEnter}>Launch Dashboard</MagneticCTA>

          <motion.button
            whileHover={{ scale: 1.04, borderColor: `${C.sky}40` }}
            whileTap={{ scale: 0.97 }}
            className="flex items-center gap-2 px-8 py-4 rounded-2xl text-sm font-bold transition-all"
            style={{
              background: C.surface2,
              color: C.text2,
              border: `1px solid ${C.border}`,
              backdropFilter: 'blur(8px)',
            }}
          >
            <Layers className="w-4 h-4" />
            View Architecture
          </motion.button>
        </motion.div>

        {/* Social proof micro-line */}
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.7 }}
          className="mt-6 text-[11px] font-mono flex items-center gap-2"
          style={{ color: C.text3 }}
        >
          <CheckCircle2 size={11} style={{ color: C.mint }} />
          Spider2-Lite · DataAgentBench · Custom Projects · SSE Streaming
        </motion.p>
      </section>

      {/* ── Stats strip ── */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5, duration: 0.5 }}
        className="relative z-10 max-w-3xl mx-auto px-6 mb-20"
      >
        <div
          className="grid grid-cols-2 md:grid-cols-4 rounded-2xl overflow-hidden"
          style={{ border: `1px solid ${C.border}`, background: C.surface1, backdropFilter: 'blur(16px)' }}
        >
          {STATS.map(({ value, sfx, label }, i) => (
            <div
              key={label}
              className="flex flex-col items-center py-6 px-4"
              style={{
                borderRight: i < STATS.length - 1 ? `1px solid ${C.border}` : 'none',
              }}
            >
              <div
                className="text-4xl font-black tabular-nums mb-1"
                style={{
                  background: `linear-gradient(120deg, ${C.sky}, ${C.indigo})`,
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  backgroundClip: 'text',
                }}
              >
                <Counter to={value} sfx={sfx} />
              </div>
              <div className="text-[10px] font-mono uppercase tracking-widest" style={{ color: C.text3 }}>
                {label}
              </div>
            </div>
          ))}
        </div>
      </motion.section>

      {/* ── Features ── */}
      <section className="relative z-10 max-w-5xl mx-auto px-6 mb-24">
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
            <MagneticCTA onClick={onEnter}>Enter Dashboard</MagneticCTA>
          </div>
        </div>
      </motion.section>

      {/* ── Footer ── */}
      <footer
        className="relative z-10 text-center py-8 text-[10px] font-mono"
        style={{ borderTop: `1px solid ${C.border}`, color: C.text3 }}
      >
        <span style={{ color: C.text3 }}>SpiderDIN v2</span>
        <span className="mx-2">·</span>
        <span style={{ color: C.sky + '80' }}>SemanticDIN Orchestrator</span>
        <span className="mx-2">·</span>
        <span>Multi-Agent Text-to-SQL</span>
      </footer>
    </div>
  );
};

export default LandingPage;
