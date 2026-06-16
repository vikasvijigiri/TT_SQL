import { useState, useEffect } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Database, Plus, ChevronRight, Server, HardDrive, Play, Trash2,
  LayoutGrid, CheckCircle2, Globe, FlaskConical, Plug, X, Zap,
  Cloud, FolderKanban, Shield, ArrowRight, Pencil, Clock,
  Lock, Unlock, RotateCcw, Triangle, Settings
} from 'lucide-react';

const CUSTOM = `${import.meta.env.VITE_API_BASE_URL || '/api'}/custom`;

const inp =
  'w-full px-3 py-2 rounded-lg bg-[#12121a] border border-[#2a2a3a] text-slate-200 text-sm placeholder-slate-600 outline-none focus:border-emerald-500/60 focus:ring-1 focus:ring-emerald-500/20 transition-all';

const DB_TYPES = [
  { key: 'postgres',   label: 'PostgreSQL',   icon: Server,        color: '#2563eb' },
  { key: 'sqlite',     label: 'SQLite',        icon: HardDrive,     color: '#7c3aed' },
  { key: 'bigquery',   label: 'GCP BigQuery',  icon: Cloud,         color: '#ea4335' },
  { key: 'snowflake',  label: 'Snowflake',     icon: Triangle,      color: '#29b5e8' },
  { key: 'bulk_sqlite',label: 'Bulk SQLite',   icon: FolderKanban,  color: '#059669' },
];

const CustomProjectsScreen = ({
  externalActiveProject,
  onProjectActivated,
  onProjectDeactivated,
  onStartChat,
}) => {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedTab, setSelectedTab] = useState('Home');
  const [activeProjectId, setActiveProjectId] = useState(externalActiveProject?.id || null);

  const [isCreatingProject, setIsCreatingProject] = useState(false);
  const [projectName, setProjectName] = useState('');
  const [saving, setSaving] = useState(false);

  const [selectedProjectId, setSelectedProjectId] = useState(null);
  const [dbType, setDbType] = useState('postgres');
  const [dbName, setDbName] = useState('');
  const [database, setDatabase] = useState('');
  const [host, setHost] = useState('');
  const [port, setPort] = useState('5432');
  const [user, setUser] = useState('');
  const [password, setPassword] = useState('');
  const [sqlitePath, setSqlitePath] = useState('');
  const [bqCredentialsPath, setBqCredentialsPath] = useState('');
  const [sfWarehouse, setSfWarehouse] = useState('');
  const [sfRole, setSfRole] = useState('');
  const [qdrantCollection, setQdrantCollection] = useState('');

  const [testResult, setTestResult] = useState({ id: null, status: null, message: '', tables: [] });
  const [activationData, setActivationData] = useState({ id: null, status: null });
  const [justActivated, setJustActivated] = useState(null);

  const [globalSettings, setGlobalSettings] = useState({
    llm_provider: 'bedrock', llm_model: '', llm_api_base: '',
    embedding_model: '', bedrock_region: '', bedrock_access_key: '',
    bedrock_secret_key: '', qdrant_url: '', qdrant_api_key: ''
  });
  const [isConfigLocked, setIsConfigLocked] = useState(true);

  useEffect(() => {
    fetchProjects();
    fetchGlobalSettings();
  }, []);

  useEffect(() => {
    if (externalActiveProject?.id) setActiveProjectId(externalActiveProject.id);
  }, [externalActiveProject]);

  const fetchProjects = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${CUSTOM}/projects`);
      setProjects((res.data || []).filter(p => p?.id));
    } catch {
      // silently fail if backend not running
    } finally {
      setLoading(false);
    }
  };

  const fetchGlobalSettings = async () => {
    try {
      const res = await axios.get(`${CUSTOM}/settings`);
      if (Object.keys(res.data).length > 0) {
        setGlobalSettings(prev => ({ ...prev, ...res.data }));
      }
    } catch { /* ignore */ }
  };

  const handleSaveGlobalSettings = async (e) => {
    if (e) e.preventDefault();
    setSaving(true);
    try {
      await axios.put(`${CUSTOM}/settings`, globalSettings);
      alert('Global settings saved!');
    } catch {
      alert('Failed to save settings.');
    } finally {
      setSaving(false);
    }
  };

  const handleResetGlobalSettings = async () => {
    if (!window.confirm('Reset global settings to defaults?')) return;
    setSaving(true);
    try {
      await axios.delete(`${CUSTOM}/settings`);
      await fetchGlobalSettings();
      setIsConfigLocked(true);
    } catch {
      alert('Failed to reset settings.');
    } finally {
      setSaving(false);
    }
  };

  const handleCreateProject = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await axios.post(`${CUSTOM}/projects`, { name: projectName });
      setProjectName('');
      setIsCreatingProject(false);
      fetchProjects();
    } catch {
      alert('Failed to create project.');
    } finally {
      setSaving(false);
    }
  };

  const resetForm = () => {
    setDbName(''); setDatabase(''); setHost(''); setPort('5432');
    setUser(''); setPassword(''); setSqlitePath('');
    setBqCredentialsPath(''); setSfWarehouse(''); setSfRole('');
    setQdrantCollection('');
  };

  const handleEditConnection = (project) => {
    setSelectedProjectId(project.id);
    const c = project.connection || {};
    setDbType(c.db_type || 'postgres');
    setDbName(c.db_name || '');
    setDatabase(c.database || '');
    setHost(c.host || '');
    setPort(c.port || '5432');
    setUser(c.user || '');
    setPassword(c.password || '');
    setSqlitePath(c.sqlite_path || c.db_root || '');
    setBqCredentialsPath(c.bq_credentials_path || '');
    setSfWarehouse(c.sf_warehouse || '');
    setSfRole(c.sf_role || '');
    setQdrantCollection(c.qdrant_collection || '');

    const tab = c.db_type === 'sqlite' ? 'sqlite'
      : c.db_type === 'bigquery' ? 'bigquery'
      : c.db_type === 'snowflake' ? 'snowflake'
      : c.db_type === 'bulk_sqlite' ? 'bulk_sqlite'
      : 'postgres';
    setSelectedTab(tab);
  };

  const handleSaveConnection = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {
        db_type: selectedTab === 'bulk_sqlite' ? 'bulk_sqlite' : dbType,
        db_name: dbName, database, host, port, user, password,
        sqlite_path: sqlitePath, qdrant_collection: qdrantCollection,
        bq_credentials_path: bqCredentialsPath,
        sf_warehouse: sfWarehouse, sf_role: sfRole,
        db_root: selectedTab === 'bulk_sqlite' ? sqlitePath : '',
      };
      await axios.put(`${CUSTOM}/projects/${selectedProjectId}/connection`, payload);
      resetForm();
      setSelectedTab('Home');
      setSelectedProjectId(null);
      fetchProjects();
    } catch {
      alert('Failed to save connection.');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteProject = async (projectId) => {
    if (!window.confirm('Delete this project?')) return;
    try {
      await axios.delete(`${CUSTOM}/projects/${projectId}`);
      fetchProjects();
      if (projectId === activeProjectId) {
        setActiveProjectId(null);
        onProjectDeactivated?.();
        setJustActivated(null);
      }
      if (testResult.id === projectId) setTestResult({ id: null, status: null, message: '', tables: [] });
    } catch { /* ignore */ }
  };

  const handleActivate = async (id) => {
    setActivationData({ id, status: 'loading' });
    try {
      const res = await axios.post(`${CUSTOM}/projects/${id}/activate`);
      setActivationData({ id, status: 'success' });
      setActiveProjectId(id);
      setJustActivated(id);
      if (res.data.project) onProjectActivated?.(res.data.project);
    } catch {
      setActivationData({ id, status: 'error' });
      alert('Failed to activate project.');
    }
  };

  const handleDeactivate = async () => {
    const id = activeProjectId;
    setActivationData({ id, status: 'loading' });
    try {
      await axios.post(`${CUSTOM}/projects/deactivate`);
      setActivationData({ id, status: 'success' });
      setActiveProjectId(null);
      setJustActivated(null);
      onProjectDeactivated?.();
    } catch {
      setActivationData({ id, status: 'error' });
      alert('Failed to deactivate project.');
    }
  };

  const handleTestConnection = async (id) => {
    setTestResult({ id, status: 'loading', message: '', tables: [] });
    try {
      const res = await axios.post(`${CUSTOM}/projects/${id}/test`);
      const d = res.data;
      if (d.status === 'success' || d.connected) {
        setTestResult({ id, status: 'success', message: d.message || 'Connection successful!', tables: d.tables || [] });
      } else {
        setTestResult({ id, status: 'error', message: d.message || d.error || 'Connection failed.', tables: [] });
      }
    } catch (err) {
      setTestResult({ id, status: 'error', message: err.response?.data?.detail || 'Failed to reach server.', tables: [] });
    }
  };

  const formatLastActivity = (iso) => {
    if (!iso) return 'Never';
    try {
      return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(iso));
    } catch { return 'Recently'; }
  };

  const DbIcon = ({ type, size = 16, style }) => {
    if (type === 'sqlite') return <HardDrive size={size} color="#7c3aed" style={style} />;
    if (type === 'bigquery') return <Cloud size={size} color="#ea4335" style={style} />;
    if (type === 'snowflake') return <Triangle size={size} color="#29b5e8" style={{ transform: 'rotate(180deg)', ...style }} />;
    if (type === 'bulk_sqlite') return <FolderKanban size={size} color="#059669" style={style} />;
    return <Server size={size} color="#2563eb" style={style} />;
  };

  return (
    <div className="flex h-full w-full overflow-hidden bg-[#070709]">
      {/* ─── Inner Sidebar ─── */}
      <div className="w-56 bg-[#0c0c10] border-r border-[#1a1a22] flex flex-col shrink-0">
        <div className="px-4 py-5 border-b border-[#1a1a22]">
          <div className="flex items-center gap-2.5 text-emerald-400">
            <Plug size={18} />
            <span className="text-sm font-bold">Data Sources</span>
          </div>
          <p className="text-[11px] text-slate-500 mt-1">Manage your connections</p>
        </div>

        <div className="flex-1 py-3">
          <p className="px-4 mb-2 text-[10px] font-bold text-slate-600 uppercase tracking-widest">Connect to</p>
          {DB_TYPES.map(({ key, label, icon: Icon, color }) => (
            <button
              key={key}
              onClick={() => { setSelectedTab(key); setDbType(key); }}
              className="flex items-center justify-between w-full px-4 py-2.5 text-left transition-all"
              style={{
                backgroundColor: selectedTab === key ? 'rgba(16,185,129,0.06)' : 'transparent',
                borderLeft: selectedTab === key ? `3px solid ${color}` : '3px solid transparent',
              }}
            >
              <div className="flex items-center gap-2.5 text-[13px] font-medium" style={{ color: selectedTab === key ? color : '#94a3b8' }}>
                <Icon size={15} style={key === 'snowflake' ? { transform: 'rotate(180deg)' } : undefined} />
                {label}
              </div>
              <ChevronRight size={13} className="text-slate-600" />
            </button>
          ))}
        </div>

        <div className="px-3 py-2">
          <button
            onClick={() => setSelectedTab('GlobalConfig')}
            className={`flex items-center gap-2.5 w-full px-3 py-2.5 rounded-lg text-[13px] font-medium transition-all ${selectedTab === 'GlobalConfig' ? 'bg-emerald-500/10 text-emerald-400' : 'text-slate-500 hover:text-slate-300 hover:bg-white/[0.04]'}`}
          >
            <Settings size={15} /> Global Config
          </button>
        </div>

        <div className="px-3 py-3 border-t border-[#1a1a22]">
          <button
            onClick={() => { setSelectedTab('Home'); resetForm(); setSelectedProjectId(null); }}
            className={`flex items-center gap-2.5 w-full px-3 py-2.5 rounded-lg text-[13px] font-medium transition-all ${selectedTab === 'Home' ? 'bg-emerald-500/10 text-emerald-400' : 'text-slate-500 hover:text-slate-300 hover:bg-white/[0.04]'}`}
          >
            <LayoutGrid size={15} /> Saved Projects
          </button>
        </div>
      </div>

      {/* ─── Main Content ─── */}
      <div className="flex-1 overflow-y-auto p-8">

        {/* ── HOME TAB ── */}
        {selectedTab === 'Home' && (
          <div>
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <LayoutGrid size={20} className="text-slate-300" />
                <h2 className="text-xl font-bold text-slate-100">Projects</h2>
                <span className="text-xs text-slate-500 font-semibold bg-[#1a1a22] px-2 py-0.5 rounded-full">{projects.length}</span>
              </div>
              <div className="flex items-center gap-2">
                {projects.length > 0 && (
                  <button
                    onClick={() => {
                      if (window.confirm('Delete ALL projects?')) {
                        axios.delete(`${CUSTOM}/projects`).then(() => {
                          fetchProjects();
                          setActiveProjectId(null);
                          onProjectDeactivated?.();
                          setJustActivated(null);
                          setTestResult({ id: null, status: null, message: '', tables: [] });
                        });
                      }
                    }}
                    className="p-2 rounded-lg bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 border border-rose-500/20 transition-all"
                  >
                    <Trash2 size={15} />
                  </button>
                )}
                <button
                  onClick={() => setIsCreatingProject(true)}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold transition-all shadow-lg shadow-emerald-500/20"
                >
                  <Plus size={15} strokeWidth={3} /> New Project
                </button>
              </div>
            </div>

            {/* Success Banner */}
            <AnimatePresence>
              {justActivated && (
                <motion.div
                  initial={{ opacity: 0, y: -8, height: 0 }}
                  animate={{ opacity: 1, y: 0, height: 'auto' }}
                  exit={{ opacity: 0, y: -8, height: 0 }}
                  className="flex items-center justify-between mb-5 px-4 py-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30"
                >
                  <div className="flex items-center gap-3">
                    <CheckCircle2 size={18} className="text-emerald-400" />
                    <div>
                      <div className="text-sm font-semibold text-emerald-300">Project Connected Successfully</div>
                      <div className="text-xs text-emerald-500 mt-0.5">Your data source is ready. Start asking questions.</div>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => { setJustActivated(null); onStartChat?.(); }}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-xs font-bold hover:bg-emerald-500 transition-all"
                    >
                      <Zap size={12} /> Start Chatting <ArrowRight size={12} />
                    </button>
                    <button onClick={() => setJustActivated(null)} className="text-slate-500 hover:text-slate-300 p-1">
                      <X size={14} />
                    </button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Create Project Form */}
            <AnimatePresence>
              {isCreatingProject && (
                <motion.div
                  initial={{ opacity: 0, y: -8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  className="mb-5 p-4 rounded-xl bg-[#0e0e14] border-2 border-emerald-500/40 max-w-md shadow-xl"
                >
                  <h3 className="text-sm font-semibold text-slate-200 mb-3">Create New Project</h3>
                  <form onSubmit={handleCreateProject} className="flex gap-2">
                    <input
                      type="text" required autoFocus value={projectName}
                      onChange={e => setProjectName(e.target.value)}
                      placeholder="Project name..."
                      className={inp + ' flex-1'}
                    />
                    <button type="submit" disabled={saving} className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold transition-all whitespace-nowrap">
                      Create
                    </button>
                    <button type="button" onClick={() => { setIsCreatingProject(false); setProjectName(''); }}
                      className="px-3 py-2 rounded-lg bg-[#1a1a22] text-slate-400 hover:text-slate-200 text-sm transition-all">
                      Cancel
                    </button>
                  </form>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Project Cards */}
            {loading ? (
              <div className="flex justify-center py-16">
                <div className="w-6 h-6 border-2 border-emerald-500/30 border-t-emerald-400 rounded-full animate-spin" />
              </div>
            ) : projects.length === 0 && !isCreatingProject ? (
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex flex-col items-center justify-center py-16 rounded-2xl border-2 border-dashed border-[#262638] bg-[#0c0c10]"
              >
                <Database size={44} className="text-slate-700 mb-4" />
                <h3 className="text-slate-300 text-lg font-semibold mb-1">No Projects Yet</h3>
                <p className="text-slate-500 text-sm mb-5 text-center max-w-xs">Create your first project to connect a database and start asking questions.</p>
                <button onClick={() => setIsCreatingProject(true)}
                  className="flex items-center gap-1.5 px-5 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold transition-all shadow-lg shadow-emerald-500/20">
                  <Plus size={15} strokeWidth={3} /> Get Started
                </button>
              </motion.div>
            ) : (
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                {projects.map((p, idx) => {
                  const isActive = p.id === activeProjectId;
                  const isActivating = activationData.id === p.id && activationData.status === 'loading';
                  return (
                    <motion.div
                      key={p.id}
                      initial={{ opacity: 0, y: 16 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: idx * 0.05 }}
                      className={`rounded-xl overflow-hidden transition-all ${isActive ? 'border-2 border-emerald-500/40 shadow-lg shadow-emerald-500/10' : 'border border-[#1e1e2c] hover:border-[#2a2a3e]'} bg-[#0e0e14]`}
                    >
                      {/* Card Header */}
                      <div className={`flex items-center justify-between px-4 py-3 border-b border-[#1a1a22] ${isActive ? 'bg-emerald-500/5' : 'bg-[#0c0c10]'}`}>
                        <div className="flex items-center gap-2.5">
                          <DbIcon type={p.connection?.db_type} size={16} />
                          <div>
                            <span className="text-sm font-semibold text-slate-100">{p.name}</span>
                            <span className="block text-[10px] text-slate-500">Activity: {formatLastActivity(p.last_activity)}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {isActive && (
                            <span className="flex items-center gap-1 text-[10px] font-bold text-emerald-400 bg-emerald-500/15 border border-emerald-500/20 px-2 py-0.5 rounded-full uppercase tracking-wide">
                              <CheckCircle2 size={10} /> Active
                            </span>
                          )}
                          <button
                            onClick={() => handleDeleteProject(p.id)}
                            className="p-1 rounded text-slate-600 hover:text-rose-400 hover:bg-rose-500/10 transition-all"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </div>

                      {/* Card Body */}
                      {p.connection ? (
                        <div className="px-4 py-3">
                          <div className="grid grid-cols-2 gap-3 mb-4 text-xs">
                            <div>
                              <div className="text-[10px] font-semibold text-slate-600 uppercase tracking-widest mb-0.5 flex items-center gap-1"><Database size={9} /> Type</div>
                              <div className="text-slate-300 font-medium">
                                {p.connection.db_type === 'sqlite' ? 'SQLite' : p.connection.db_type === 'bulk_sqlite' ? 'Bulk SQLite' : p.connection.db_type === 'snowflake' ? 'Snowflake' : p.connection.db_type === 'bigquery' ? 'BigQuery' : 'PostgreSQL'}
                              </div>
                            </div>
                            {p.connection.db_type !== 'bulk_sqlite' && (
                              <div>
                                <div className="text-[10px] font-semibold text-slate-600 uppercase tracking-widest mb-0.5 flex items-center gap-1"><Shield size={9} /> Schema</div>
                                <div className="text-slate-300 font-medium">{p.connection.db_name || '--'}</div>
                              </div>
                            )}
                            <div className={p.connection.db_type === 'bulk_sqlite' ? 'col-span-2' : ''}>
                              <div className="text-[10px] font-semibold text-slate-600 uppercase tracking-widest mb-0.5 flex items-center gap-1"><Globe size={9} /> Host</div>
                              <div className="text-slate-300 font-medium text-[11px] break-all">
                                {p.connection.db_type === 'sqlite' ? 'Local File' : p.connection.db_type === 'bulk_sqlite' ? p.connection.db_root : (p.connection.host || '--')}
                              </div>
                            </div>
                            <div>
                              <div className="text-[10px] font-semibold text-slate-600 uppercase tracking-widest mb-0.5 flex items-center gap-1"><Clock size={9} /> Last Activity</div>
                              <div className="text-slate-300 font-medium">{formatLastActivity(p.last_activity)}</div>
                            </div>
                          </div>

                          {/* Action Bar */}
                          <div className="flex items-center justify-between pt-3 border-t border-[#1a1a22]">
                            <button
                              onClick={() => handleEditConnection(p)}
                              className="flex items-center gap-1 text-xs text-slate-500 hover:text-emerald-400 transition-all font-medium"
                            >
                              <Pencil size={11} /> Edit
                            </button>
                            <div className="flex gap-2">
                              <button
                                onClick={() => handleTestConnection(p.id)}
                                disabled={testResult.id === p.id && testResult.status === 'loading'}
                                className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-[#1a1a22] text-slate-400 hover:text-slate-200 border border-[#262638] hover:border-slate-500 text-xs font-semibold transition-all"
                              >
                                {testResult.id === p.id && testResult.status === 'loading'
                                  ? <div className="w-3 h-3 border border-slate-500 border-t-slate-300 rounded-full animate-spin" />
                                  : <FlaskConical size={11} />}
                                Test
                              </button>
                              <button
                                onClick={() => handleActivate(p.id)}
                                disabled={isActivating || isActive}
                                className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${isActive ? 'bg-emerald-600/80 text-white cursor-default' : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-md shadow-emerald-500/20'}`}
                              >
                                {isActivating ? <div className="w-3 h-3 border border-white/30 border-t-white rounded-full animate-spin" />
                                  : isActive ? <CheckCircle2 size={11} />
                                  : <Play size={11} fill="currentColor" />}
                                {isActive ? 'Connected' : 'Activate'}
                              </button>
                              {isActive && (
                                <button
                                  onClick={handleDeactivate}
                                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-rose-600/80 hover:bg-rose-500 text-white text-xs font-semibold transition-all"
                                >
                                  Deactivate
                                </button>
                              )}
                            </div>
                          </div>

                          {/* Test Result */}
                          <AnimatePresence>
                            {testResult.id === p.id && testResult.status && testResult.status !== 'loading' && (
                              <motion.div
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: 'auto' }}
                                exit={{ opacity: 0, height: 0 }}
                                className={`mt-3 px-3 py-2 rounded-lg text-xs ${testResult.status === 'success' ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-300 border border-rose-500/20'}`}
                              >
                                <div className="font-semibold flex items-center gap-1.5 mb-0.5">
                                  {testResult.status === 'success' ? <><CheckCircle2 size={11} /> Connection Successful</> : <><X size={11} /> Connection Failed</>}
                                </div>
                                <div>{testResult.message}</div>
                                {testResult.status === 'success' && testResult.tables?.length > 0 && (
                                  <div className="mt-1 text-emerald-400/80">
                                    Tables: {testResult.tables.slice(0, 6).join(', ')}{testResult.tables.length > 6 ? '...' : ''}
                                  </div>
                                )}
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      ) : (
                        <div className="px-4 py-6 flex flex-col items-center bg-[#0a0a0f]">
                          <Plug size={24} className="text-slate-700 mb-2" />
                          <span className="text-xs text-slate-500 mb-3">No connection configured</span>
                          <button
                            onClick={() => handleEditConnection(p)}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#1a1a22] border border-[#262638] text-slate-400 hover:text-slate-200 hover:border-slate-500 text-xs font-semibold transition-all"
                          >
                            <Plug size={12} /> Add Connection
                          </button>
                        </div>
                      )}
                    </motion.div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ── CONNECTION FORM TAB ── */}
        {['postgres', 'sqlite', 'bigquery', 'snowflake', 'bulk_sqlite'].includes(selectedTab) && (
          <div className="max-w-lg">
            <div className="flex items-center gap-3 mb-1">
              {selectedTab === 'postgres' ? <Server size={20} color="#2563eb" />
                : selectedTab === 'sqlite' ? <HardDrive size={20} color="#7c3aed" />
                : selectedTab === 'bigquery' ? <Cloud size={20} color="#ea4335" />
                : selectedTab === 'bulk_sqlite' ? <FolderKanban size={20} color="#059669" />
                : <Triangle size={20} color="#29b5e8" style={{ transform: 'rotate(180deg)' }} />}
              <h2 className="text-xl font-bold text-slate-100">
                {selectedTab === 'postgres' ? 'PostgreSQL'
                  : selectedTab === 'sqlite' ? 'SQLite'
                  : selectedTab === 'bigquery' ? 'GCP BigQuery'
                  : selectedTab === 'bulk_sqlite' ? 'Bulk Database Folder'
                  : 'Snowflake'} Connection
              </h2>
            </div>
            <p className="text-slate-500 text-sm mb-6">Configure database credentials and vector store settings.</p>

            {!selectedProjectId ? (
              <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300 text-sm">
                <Database size={16} className="text-amber-400 shrink-0" />
                <span><strong>Select a project first.</strong> Go to Saved Projects and click "Add Connection" or "Edit".</span>
              </div>
            ) : (
              <form onSubmit={handleSaveConnection} className="flex flex-col gap-4 p-5 rounded-xl bg-[#0e0e14] border border-[#1e1e2c]">
                {/* Project context */}
                <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-sm">
                  <Server size={13} /> Project: <strong>{projects.find(p => p.id === selectedProjectId)?.name || 'Unknown'}</strong>
                </div>

                {/* Postgres Fields */}
                {selectedTab === 'postgres' && (
                  <>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="flex flex-col gap-1.5">
                        <label className="text-xs font-semibold text-slate-400">Schema / DB Name</label>
                        <input className={inp} value={dbName} onChange={e => setDbName(e.target.value)} placeholder="public" />
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <label className="text-xs font-semibold text-slate-400">Database</label>
                        <input className={inp} value={database} onChange={e => setDatabase(e.target.value)} placeholder="mydb" />
                      </div>
                    </div>
                    <div className="grid grid-cols-3 gap-3">
                      <div className="col-span-2 flex flex-col gap-1.5">
                        <label className="text-xs font-semibold text-slate-400">Host</label>
                        <input className={inp} value={host} onChange={e => setHost(e.target.value)} placeholder="localhost" />
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <label className="text-xs font-semibold text-slate-400">Port</label>
                        <input className={inp} value={port} onChange={e => setPort(e.target.value)} placeholder="5432" />
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="flex flex-col gap-1.5">
                        <label className="text-xs font-semibold text-slate-400">User</label>
                        <input className={inp} value={user} onChange={e => setUser(e.target.value)} placeholder="postgres" />
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <label className="text-xs font-semibold text-slate-400">Password</label>
                        <input type="password" className={inp} value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" />
                      </div>
                    </div>
                  </>
                )}

                {/* SQLite Fields */}
                {selectedTab === 'sqlite' && (
                  <>
                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs font-semibold text-slate-400">Database Name</label>
                      <input className={inp} value={dbName} onChange={e => setDbName(e.target.value)} placeholder="mydb" />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs font-semibold text-slate-400">File Path</label>
                      <input className={inp} value={sqlitePath} onChange={e => setSqlitePath(e.target.value)} placeholder="C:/path/to/database.sqlite" />
                    </div>
                  </>
                )}

                {/* Bulk SQLite Fields */}
                {selectedTab === 'bulk_sqlite' && (
                  <div className="flex flex-col gap-1.5">
                    <label className="text-xs font-semibold text-slate-400">Root Folder Path</label>
                    <input className={inp} value={sqlitePath} onChange={e => setSqlitePath(e.target.value)} placeholder="C:/path/to/databases/folder" />
                    <span className="text-[11px] text-slate-600">Folder containing multiple .db / .sqlite files</span>
                  </div>
                )}

                {/* BigQuery Fields */}
                {selectedTab === 'bigquery' && (
                  <>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="flex flex-col gap-1.5">
                        <label className="text-xs font-semibold text-slate-400">Project ID</label>
                        <input required className={inp} value={database} onChange={e => setDatabase(e.target.value)} placeholder="my-gcp-project" />
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <label className="text-xs font-semibold text-slate-400">Dataset ID</label>
                        <input required className={inp} value={dbName} onChange={e => setDbName(e.target.value)} placeholder="analytics_dataset" />
                      </div>
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs font-semibold text-slate-400">Service Account Key Path</label>
                      <input required className={inp} value={bqCredentialsPath} onChange={e => setBqCredentialsPath(e.target.value)} placeholder="/absolute/path/to/key.json" />
                    </div>
                  </>
                )}

                {/* Snowflake Fields */}
                {selectedTab === 'snowflake' && (
                  <>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="flex flex-col gap-1.5">
                        <label className="text-xs font-semibold text-slate-400">Account (Host)</label>
                        <input required className={inp} value={host} onChange={e => setHost(e.target.value)} placeholder="org-account.snowflakecomputing.com" />
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <label className="text-xs font-semibold text-slate-400">Database</label>
                        <input required className={inp} value={database} onChange={e => setDatabase(e.target.value)} placeholder="MY_DB" />
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="flex flex-col gap-1.5">
                        <label className="text-xs font-semibold text-slate-400">Schema</label>
                        <input required className={inp} value={dbName} onChange={e => setDbName(e.target.value)} placeholder="PUBLIC" />
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <label className="text-xs font-semibold text-slate-400">Warehouse</label>
                        <input className={inp} value={sfWarehouse} onChange={e => setSfWarehouse(e.target.value)} placeholder="COMPUTE_WH" />
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="flex flex-col gap-1.5">
                        <label className="text-xs font-semibold text-slate-400">User</label>
                        <input required className={inp} value={user} onChange={e => setUser(e.target.value)} placeholder="MY_USER" />
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <label className="text-xs font-semibold text-slate-400">Password</label>
                        <input type="password" required className={inp} value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" />
                      </div>
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs font-semibold text-slate-400">Role (optional)</label>
                      <input className={inp} value={sfRole} onChange={e => setSfRole(e.target.value)} placeholder="SYSADMIN" />
                    </div>
                  </>
                )}

                {/* Shared: Qdrant Collection */}
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-semibold text-slate-400">Qdrant Collection (vector store name)</label>
                  <input className={inp} value={qdrantCollection} onChange={e => setQdrantCollection(e.target.value)} placeholder={dbName || 'my_collection'} />
                </div>

                <div className="flex gap-2 pt-1">
                  <button type="submit" disabled={saving}
                    className="flex-1 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold transition-all shadow-lg shadow-emerald-500/15">
                    {saving ? 'Saving...' : 'Save Connection'}
                  </button>
                  <button type="button" onClick={() => { resetForm(); setSelectedTab('Home'); setSelectedProjectId(null); }}
                    className="px-4 py-2.5 rounded-lg bg-[#1a1a22] text-slate-400 hover:text-slate-200 text-sm transition-all">
                    Cancel
                  </button>
                </div>
              </form>
            )}
          </div>
        )}

        {/* ── GLOBAL CONFIG TAB ── */}
        {selectedTab === 'GlobalConfig' && (
          <div className="max-w-lg">
            <div className="flex items-center gap-3 mb-1">
              <Settings size={20} className="text-slate-400" />
              <h2 className="text-xl font-bold text-slate-100">Global Configuration</h2>
            </div>
            <p className="text-slate-500 text-sm mb-6">LLM provider and vector store settings shared across all projects.</p>

            <div className="flex items-center justify-between mb-4">
              <span className="text-sm font-semibold text-slate-300">Settings</span>
              <button
                onClick={() => setIsConfigLocked(l => !l)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all border ${isConfigLocked ? 'bg-[#1a1a22] text-slate-400 border-[#262638] hover:border-amber-500/40' : 'bg-amber-500/10 text-amber-400 border-amber-500/30'}`}
              >
                {isConfigLocked ? <><Lock size={11} /> Locked</> : <><Unlock size={11} /> Unlocked</>}
              </button>
            </div>

            <form onSubmit={handleSaveGlobalSettings} className="flex flex-col gap-4 p-5 rounded-xl bg-[#0e0e14] border border-[#1e1e2c]">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-semibold text-slate-400">LLM Provider</label>
                <select
                  disabled={isConfigLocked}
                  className={inp + ' disabled:opacity-50'}
                  value={globalSettings.llm_provider}
                  onChange={e => setGlobalSettings(s => ({ ...s, llm_provider: e.target.value }))}
                  style={{ background: '#12121a' }}
                >
                  <option value="bedrock">AWS Bedrock</option>
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="azure">Azure OpenAI</option>
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-semibold text-slate-400">LLM Model</label>
                  <input disabled={isConfigLocked} className={inp + ' disabled:opacity-50'} value={globalSettings.llm_model}
                    onChange={e => setGlobalSettings(s => ({ ...s, llm_model: e.target.value }))} placeholder="e.g. gpt-4o" />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-semibold text-slate-400">Embedding Model</label>
                  <input disabled={isConfigLocked} className={inp + ' disabled:opacity-50'} value={globalSettings.embedding_model}
                    onChange={e => setGlobalSettings(s => ({ ...s, embedding_model: e.target.value }))} placeholder="text-embedding-3-small" />
                </div>
              </div>
              {globalSettings.llm_provider !== 'bedrock' && (
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-semibold text-slate-400">API Key</label>
                  <input type="password" disabled={isConfigLocked} className={inp + ' disabled:opacity-50'} value={globalSettings.llm_api_base || ''}
                    onChange={e => setGlobalSettings(s => ({ ...s, llm_api_base: e.target.value }))} placeholder="sk-..." />
                </div>
              )}
              {globalSettings.llm_provider === 'bedrock' && (
                <div className="grid grid-cols-3 gap-3">
                  <div className="flex flex-col gap-1.5">
                    <label className="text-xs font-semibold text-slate-400">Region</label>
                    <input disabled={isConfigLocked} className={inp + ' disabled:opacity-50'} value={globalSettings.bedrock_region}
                      onChange={e => setGlobalSettings(s => ({ ...s, bedrock_region: e.target.value }))} placeholder="us-east-1" />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label className="text-xs font-semibold text-slate-400">Access Key</label>
                    <input disabled={isConfigLocked} className={inp + ' disabled:opacity-50'} value={globalSettings.bedrock_access_key}
                      onChange={e => setGlobalSettings(s => ({ ...s, bedrock_access_key: e.target.value }))} placeholder="AKIA..." />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label className="text-xs font-semibold text-slate-400">Secret Key</label>
                    <input type="password" disabled={isConfigLocked} className={inp + ' disabled:opacity-50'} value={globalSettings.bedrock_secret_key}
                      onChange={e => setGlobalSettings(s => ({ ...s, bedrock_secret_key: e.target.value }))} placeholder="••••••••" />
                  </div>
                </div>
              )}
              <div className="grid grid-cols-2 gap-3 pt-2 border-t border-[#1a1a22]">
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-semibold text-slate-400">Qdrant URL</label>
                  <input disabled={isConfigLocked} className={inp + ' disabled:opacity-50'} value={globalSettings.qdrant_url}
                    onChange={e => setGlobalSettings(s => ({ ...s, qdrant_url: e.target.value }))} placeholder="http://localhost:6333" />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-semibold text-slate-400">Qdrant API Key</label>
                  <input type="password" disabled={isConfigLocked} className={inp + ' disabled:opacity-50'} value={globalSettings.qdrant_api_key}
                    onChange={e => setGlobalSettings(s => ({ ...s, qdrant_api_key: e.target.value }))} placeholder="optional" />
                </div>
              </div>
              {!isConfigLocked && (
                <div className="flex gap-2 pt-1">
                  <button type="submit" disabled={saving}
                    className="flex-1 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold transition-all">
                    {saving ? 'Saving...' : 'Save Settings'}
                  </button>
                  <button type="button" onClick={handleResetGlobalSettings}
                    className="flex items-center gap-1.5 px-4 py-2.5 rounded-lg bg-[#1a1a22] text-slate-400 hover:text-rose-400 text-sm transition-all">
                    <RotateCcw size={13} /> Reset
                  </button>
                </div>
              )}
            </form>
          </div>
        )}
      </div>
    </div>
  );
};

export default CustomProjectsScreen;
