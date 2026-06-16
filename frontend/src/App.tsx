import React, { useState, useEffect } from 'react';
import { Database, Sparkles, FolderOpen, ChevronRight, Activity, Loader2, X, ChevronUp, ChevronDown, Play } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import axios from 'axios';
import LandingPage from './components/LandingPage';
import SpiderStudio from './components/SpiderStudio';
import DabStudio from './components/DabStudio';
import CustomWorkspace from './components/CustomWorkspace';
import NQuireLogo from './components/NQuireLogo';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

const GlobalRunningPanel = ({ runningSpiderTasks, runningDabTasks, onNavigateTask }) => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const totalTasks = runningSpiderTasks.length + runningDabTasks.length;

  if (totalTasks === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 50, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 50, scale: 0.95 }}
      className="fixed bottom-6 right-6 z-50 w-80 bg-[#1b2738]/95 backdrop-blur-md border border-[#2c3e55]/80 rounded-2xl shadow-2xl overflow-hidden font-mono text-left"
    >
      {/* Header */}
      <div 
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="px-4 py-3 bg-[#243448] border-b border-[#2c3e55]/80 flex items-center justify-between cursor-pointer select-none"
      >
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          <span className="text-[10px] font-bold text-slate-300 uppercase tracking-wider">
            Active Pipelines ({totalTasks})
          </span>
        </div>
        <div className="text-slate-400 hover:text-white transition-colors">
          {isCollapsed ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </div>
      </div>

      {/* Content */}
      <AnimatePresence>
        {!isCollapsed && (
          <motion.div
            initial={{ height: 0 }}
            animate={{ height: 'auto' }}
            exit={{ height: 0 }}
            className="overflow-hidden bg-[#1b2738]/60 max-h-60 overflow-y-auto"
          >
            <div className="p-3 space-y-2">
              {runningSpiderTasks.map(task => {
                const parts = task.split('_');
                const dbName = parts.length > 1 ? parts.slice(0, -1).join('_') : task;
                return (
                  <div
                    key={task}
                    onClick={() => onNavigateTask('spider', dbName, task)}
                    className="group p-2.5 rounded-xl bg-[#131820]/90 border border-blue-500/10 hover:border-blue-400/30 hover:bg-blue-950/10 transition-all cursor-pointer flex items-center justify-between"
                  >
                    <div className="flex flex-col gap-0.5 truncate pr-2">
                      <span className="text-[10px] text-blue-400 font-bold uppercase tracking-wide">Spider Studio</span>
                      <span className="text-[11px] text-slate-200 font-bold truncate">{task}</span>
                    </div>
                    <Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin shrink-0" />
                  </div>
                );
              })}

              {runningDabTasks.map(task => {
                const parts = task.split('_q');
                const dataset = parts[0];
                const qId = parts[1] || task;
                return (
                  <div
                    key={task}
                    onClick={() => onNavigateTask('dab', dataset, task)}
                    className="group p-2.5 rounded-xl bg-[#131820]/90 border border-violet-500/10 hover:border-violet-400/30 hover:bg-violet-950/10 transition-all cursor-pointer flex items-center justify-between"
                  >
                    <div className="flex flex-col gap-0.5 truncate pr-2">
                      <span className="text-[10px] text-purple-400 font-bold uppercase tracking-wide">DAB Studio</span>
                      <span className="text-[11px] text-slate-200 font-bold truncate">Query {qId} ({dataset})</span>
                    </div>
                    <Loader2 className="w-3.5 h-3.5 text-purple-400 animate-spin shrink-0" />
                  </div>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};

const App = () => {
  const [currentView, setCurrentView] = useState('landing'); // 'landing' | 'dashboard'
  const [selectedProject, setSelectedProject] = useState(null); // null | 'spider' | 'dab' | 'custom'
  const [runningSpiderTasks, setRunningSpiderTasks] = useState([]);
  const [runningDabTasks, setRunningDabTasks] = useState([]);
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem('nquire_user') || 'null'); } catch { return null; }
  });

  // Attach JWT to every axios request automatically.
  useEffect(() => {
    const id = axios.interceptors.request.use((config) => {
      const token = localStorage.getItem('nquire_token');
      if (token) config.headers['Authorization'] = `Bearer ${token}`;
      return config;
    });
    return () => axios.interceptors.request.eject(id);
  }, []);
  const [autoOpenDetails, setAutoOpenDetails] = useState(null); // { project: 'spider' | 'dab', db: string, id: string }

  // Sync state with URL hash (Browser back/forward history support)
  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash;
      if (hash === '#/spider') {
        setCurrentView('dashboard');
        setSelectedProject('spider');
      } else if (hash === '#/dab') {
        setCurrentView('dashboard');
        setSelectedProject('dab');
      } else if (hash === '#/custom') {
        setCurrentView('dashboard');
        setSelectedProject('custom');
      } else if (hash === '#/dashboard') {
        setCurrentView('dashboard');
        setSelectedProject(null);
      } else {
        setCurrentView('landing');
        setSelectedProject(null);
      }
    };

    if (!window.location.hash) {
      window.history.replaceState(null, '', '#/');
    }
    handleHashChange();

    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  useEffect(() => {
    let targetHash = '#/';
    if (currentView === 'landing') {
      targetHash = '#/';
    } else if (selectedProject === 'spider') {
      targetHash = '#/spider';
    } else if (selectedProject === 'dab') {
      targetHash = '#/dab';
    } else if (selectedProject === 'custom') {
      targetHash = '#/custom';
    } else if (currentView === 'dashboard') {
      targetHash = '#/dashboard';
    }

    if (window.location.hash !== targetHash) {
      window.history.pushState(null, '', targetHash);
    }
  }, [currentView, selectedProject]);

  // Poll global running tasks status
  useEffect(() => {
    const checkStatus = async () => {
      try {
        const [spiderStatus, dabStatus] = await Promise.all([
          axios.get(`${API_BASE}/run/status`).catch(() => ({ data: { tasks: [] } })),
          axios.get(`${API_BASE}/dab/status`).catch(() => ({ data: { running: [] } }))
        ]);
        setRunningSpiderTasks(spiderStatus.data?.tasks || []);
        setRunningDabTasks(dabStatus.data?.running || []);
      } catch (err) {
        console.error("Failed to query background tasks", err);
      }
    };
    checkStatus();
    const interval = setInterval(checkStatus, 8000);
    return () => clearInterval(interval);
  }, []);

  let activeScreen = null;

  const handleLogin = (userData, token?: string) => {
    setUser(userData);
    localStorage.setItem('nquire_user', JSON.stringify(userData));
    if (token) localStorage.setItem('nquire_token', token);
  };

  const handleLogout = () => {
    setUser(null);
    localStorage.removeItem('nquire_user');
    localStorage.removeItem('nquire_token');
  };

  if (currentView === 'landing') {
    activeScreen = (
      <LandingPage
        onEnter={() => { setSelectedProject(null); setCurrentView('dashboard'); }}
        user={user}
        onLogin={handleLogin}
        onLogout={handleLogout}
      />
    );
  } else if (selectedProject === 'spider') {
    activeScreen = (
      <SpiderStudio
        onBack={() => setSelectedProject(null)}
        onHome={() => { setSelectedProject(null); setCurrentView('landing'); }}
        autoOpenDetails={autoOpenDetails}
        clearAutoOpenDetails={() => setAutoOpenDetails(null)}
        user={user}
        onLogout={handleLogout}
      />
    );
  } else if (selectedProject === 'dab') {
    activeScreen = (
      <DabStudio
        onBack={() => setSelectedProject(null)}
        onHome={() => { setSelectedProject(null); setCurrentView('landing'); }}
        autoOpenDetails={autoOpenDetails}
        clearAutoOpenDetails={() => setAutoOpenDetails(null)}
        user={user}
        onLogout={handleLogout}
      />
    );
  } else if (selectedProject === 'custom') {
    activeScreen = (
      <CustomWorkspace
        onBack={() => setSelectedProject(null)}
        onHome={() => { setSelectedProject(null); setCurrentView('landing'); }}
        user={user}
        onLogout={handleLogout}
      />
    );
  }

  if (!activeScreen) {
    activeScreen = (
      <div
        className="flex flex-col items-center justify-center min-h-screen w-full bg-[#070709] text-slate-200 font-sans p-6 overflow-y-auto select-none relative animate-fadeIn"
        style={{
          backgroundImage: 'radial-gradient(circle, rgba(255,255,255,0.03) 1px, transparent 1px)',
          backgroundSize: '24px 24px',
          backgroundColor: '#07070b'
        }}
      >
        <header className="absolute top-0 left-0 right-0 px-8 py-5 flex justify-between items-center max-w-7xl mx-auto z-30">
          <NQuireLogo size={34} showName nameSize="text-sm" onClick={() => setCurrentView('landing')} />
        </header>

        <div className="max-w-5xl w-full space-y-10 text-center mt-12">
          {/* Main Title & Header */}
          <div className="space-y-4">
            <motion.div
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
              className="inline-flex items-center gap-3 bg-[#12121a] border border-[#222232] px-4 py-2 rounded-full text-xs font-mono text-cyan-400 font-bold"
            >
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
              <span>ZEN AGENTIC SQL WORKBENCH v2.0</span>
            </motion.div>

            <motion.h1
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.2, duration: 0.8 }}
              className="text-4xl sm:text-5xl font-black tracking-tight text-white leading-none bg-gradient-to-r from-white via-slate-200 to-slate-500 bg-clip-text text-transparent"
            >
              Forensic Benchmark Hub
            </motion.h1>

            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.3, duration: 0.8 }}
              className="text-sm sm:text-base text-slate-400 max-w-xl mx-auto leading-relaxed"
            >
              Select an execution workspace benchmark to inspect reasoning graphs, audit database outputs, edit prompt protocols, and execute autonomous SQL agent repairs.
            </motion.p>
          </div>

          {/* Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-4 text-left">
            {/* Spider2-Lite Card */}
            <motion.div
              initial={{ opacity: 0, x: -30 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.4, type: 'spring', stiffness: 100 }}
              whileHover={{ y: -6, borderColor: 'rgba(59, 130, 246, 0.5)' }}
              onClick={() => setSelectedProject('spider')}
              className="bg-[#0e0e14]/90 backdrop-blur border border-[#1e1e2c] p-6 rounded-2xl cursor-pointer shadow-xl relative overflow-hidden group flex flex-col justify-between min-h-[280px]"
            >
              <div className="absolute -right-12 -bottom-12 w-40 h-40 bg-blue-500/5 rounded-full blur-3xl group-hover:bg-blue-500/10 transition-all pointer-events-none" />
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="w-12 h-12 bg-blue-600/10 border border-blue-500/30 rounded-xl flex items-center justify-center text-blue-400 shadow-lg shadow-blue-500/10">
                    <Database className="w-6 h-6" />
                  </div>
                  <span className="text-[10px] font-mono font-bold tracking-wider px-2 py-0.5 rounded bg-blue-500/15 text-blue-400 border border-blue-500/20">
                    DIALECT PROBES
                  </span>
                </div>
                <div>
                  <h2 className="text-lg font-black font-mono text-white group-hover:text-blue-400 transition-colors">
                    Spider2-Lite Studio
                  </h2>
                  <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                    Evaluate agentic text-to-SQL workflows on complex databases (Snowflake, SQLite, DuckDB). Inspect schema links, bridge table queries, FQN casing resolution, and closed-loop syntax corrections.
                  </p>
                </div>
              </div>
              <div className="pt-6 flex items-center gap-1.5 text-xs text-blue-400 font-bold font-mono group-hover:gap-2.5 transition-all">
                <span>OPEN WORKSPACE</span>
                <ChevronRight className="w-4 h-4" />
              </div>
            </motion.div>

            {/* DAB Card */}
            <motion.div
              initial={{ opacity: 0, x: 30 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.4, type: 'spring', stiffness: 100 }}
              whileHover={{ y: -6, borderColor: 'rgba(139, 92, 246, 0.5)' }}
              onClick={() => setSelectedProject('dab')}
              className="bg-[#0e0e14]/90 backdrop-blur border border-[#1e1e2c] p-6 rounded-2xl cursor-pointer shadow-xl relative overflow-hidden group flex flex-col justify-between min-h-[280px]"
            >
              <div className="absolute -right-12 -bottom-12 w-40 h-40 bg-violet-500/5 rounded-full blur-3xl group-hover:bg-violet-500/10 transition-all pointer-events-none" />
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="w-12 h-12 bg-violet-600/10 border border-violet-500/30 rounded-xl flex items-center justify-center text-violet-400 shadow-lg shadow-violet-500/10">
                    <Sparkles className="w-6 h-6" />
                  </div>
                  <span className="text-[10px] font-mono font-bold tracking-wider px-2 py-0.5 rounded bg-violet-500/15 text-violet-400 border border-violet-500/20">
                    REASONING AGENTS
                  </span>
                </div>
                <div>
                  <h2 className="text-lg font-black font-mono text-white group-hover:text-violet-400 transition-colors">
                    DataAgentBench (DAB) Studio
                  </h2>
                  <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                    Evaluate data agents executing multi-step reasoning questions, interacting with complex datasets using DuckDB and SQLite, and verifying execution outputs under rigorous evaluation rules.
                  </p>
                </div>
              </div>
              <div className="pt-6 flex items-center gap-1.5 text-xs text-violet-400 font-bold font-mono group-hover:gap-2.5 transition-all">
                <span>OPEN WORKSPACE</span>
                <ChevronRight className="w-4 h-4" />
              </div>
            </motion.div>

            {/* Custom Project Card */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5, type: 'spring', stiffness: 100 }}
              whileHover={{ y: -6, borderColor: 'rgba(16, 185, 129, 0.5)' }}
              onClick={() => setSelectedProject('custom')}
              className="bg-[#0e0e14]/90 backdrop-blur border border-[#1e1e2c] p-6 rounded-2xl cursor-pointer shadow-xl relative overflow-hidden group flex flex-col justify-between min-h-[280px]"
            >
              <div className="absolute -right-12 -bottom-12 w-40 h-40 bg-emerald-500/5 rounded-full blur-3xl group-hover:bg-emerald-500/10 transition-all pointer-events-none" />
              <div className="absolute -left-6 -top-6 w-24 h-24 bg-teal-500/3 rounded-full blur-2xl pointer-events-none" />
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="w-12 h-12 bg-emerald-600/10 border border-emerald-500/30 rounded-xl flex items-center justify-center text-emerald-400 shadow-lg shadow-emerald-500/10">
                    <FolderOpen className="w-6 h-6" />
                  </div>
                  <span className="text-[10px] font-mono font-bold tracking-wider px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">
                    YOUR DATA
                  </span>
                </div>
                <div>
                  <h2 className="text-lg font-black font-mono text-white group-hover:text-emerald-400 transition-colors">
                    Custom Project
                  </h2>
                  <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                    Connect your own database — PostgreSQL, SQLite, BigQuery, or Snowflake — and explore it with AI-powered natural language queries. No benchmarks, just your data.
                  </p>
                </div>
              </div>
              <div className="pt-6 flex items-center gap-1.5 text-xs text-emerald-400 font-bold font-mono group-hover:gap-2.5 transition-all">
                <span>START PROJECT</span>
                <ChevronRight className="w-4 h-4" />
              </div>
            </motion.div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative min-h-screen w-full">
      {activeScreen}
      <AnimatePresence>
        <GlobalRunningPanel
          runningSpiderTasks={runningSpiderTasks}
          runningDabTasks={runningDabTasks}
          onNavigateTask={(project, db, id) => {
            setSelectedProject(project);
            setCurrentView('dashboard');
            setAutoOpenDetails({ project, db, id });
          }}
        />
      </AnimatePresence>
    </div>
  );
};

export default App;
