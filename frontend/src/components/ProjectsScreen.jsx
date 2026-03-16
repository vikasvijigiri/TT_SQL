import { useState, useEffect } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Database, Plus, ChevronRight, Server, HardDrive, Play, Trash2,
    Home, LayoutGrid, CheckCircle2, Layers, Globe, FlaskConical,
    Plug, ArrowRight, Pencil, Shield, X, Zap
} from 'lucide-react';

const API_BASE_URL = 'http://localhost:8000';

const ProjectsScreen = ({ onProjectConnected, onStartChat }) => {
    const [projects, setProjects] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedTab, setSelectedTab] = useState('Home');
    const [activeProjectId, setActiveProjectId] = useState(null);

    // Project Creation
    const [isCreatingProject, setIsCreatingProject] = useState(false);
    const [projectName, setProjectName] = useState('');

    // Connection Form
    const [selectedProjectId, setSelectedProjectId] = useState(null);
    const [testResult, setTestResult] = useState({ id: null, status: null, message: '', tables: [] });
    const [dbType, setDbType] = useState('postgres');
    const [dbName, setDbName] = useState('');
    const [database, setDatabase] = useState('postgres');
    const [host, setHost] = useState('');
    const [port, setPort] = useState('5432');
    const [user, setUser] = useState('');
    const [password, setPassword] = useState('');
    const [sqlitePath, setSqlitePath] = useState('');
    const [qdrantCollection, setQdrantCollection] = useState('');

    const [saving, setSaving] = useState(false);
    const [activationData, setActivationData] = useState({ id: null, status: null });
    const [justActivated, setJustActivated] = useState(null);

    useEffect(() => {
        fetchProjects();
        fetchActiveProject();
    }, []);

    const fetchProjects = async () => {
        setLoading(true);
        try {
            const res = await axios.get(`${API_BASE_URL}/api/projects`);
            setProjects(res.data);
        } catch (err) {
            console.error("Failed to fetch projects", err);
        } finally {
            setLoading(false);
        }
    };

    const fetchActiveProject = async () => {
        try {
            const res = await axios.get(`${API_BASE_URL}/api/projects/active`);
            setActiveProjectId(res.data.active_project_id);
        } catch (err) {
            console.error("Failed to fetch active project", err);
        }
    };

    const handleCreateProject = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            await axios.post(`${API_BASE_URL}/api/projects`, { name: projectName });
            setProjectName('');
            setIsCreatingProject(false);
            fetchProjects();
        } catch (err) {
            console.error("Failed to create project", err);
            alert("Failed to create project.");
        } finally {
            setSaving(false);
        }
    };

    const resetForm = () => {
        setDbName(''); setDatabase('postgres'); setHost(''); setPort('5432');
        setUser(''); setPassword('');
        setSqlitePath(''); setQdrantCollection('');
    };

    const handleEditConnection = (project) => {
        setSelectedProjectId(project.id);
        const conn = project.connection || {};
        setDbType(conn.db_type || 'postgres');
        setDbName(conn.db_name || '');
        setDatabase(conn.database || 'postgres');
        setHost(conn.host || '');
        setPort(conn.port || '5432');
        setUser(conn.user || '');
        setPassword(conn.password || '');
        setSqlitePath(conn.sqlite_path || '');
        setQdrantCollection(conn.qdrant_collection || '');
        setSelectedTab(conn.db_type === 'sqlite' ? 'sqlite' : 'postgres');
    };

    const handleSaveConnection = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            const payload = {
                db_type: dbType, db_name: dbName, database, host, port,
                user, password, sqlite_path: sqlitePath,
                qdrant_collection: qdrantCollection
            };
            await axios.put(`${API_BASE_URL}/api/projects/${selectedProjectId}/connection`, payload);
            resetForm();
            setSelectedTab('Home');
            setSelectedProjectId(null);
            fetchProjects();
        } catch (err) {
            console.error("Failed to save connection", err);
            alert("Failed to save connection.");
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async (id, e) => {
        e.stopPropagation();
        if (!window.confirm("Delete this project and its connection?")) return;
        try {
            await axios.delete(`${API_BASE_URL}/api/projects/${id}`);
            if (activeProjectId === id) setActiveProjectId(null);
            fetchProjects();
        } catch (err) {
            console.error("Failed to delete", err);
        }
    };

    const handleActivate = async (id) => {
        setActivationData({ id, status: 'loading' });
        try {
            const res = await axios.post(`${API_BASE_URL}/api/projects/${id}/activate`);
            setActivationData({ id, status: 'success' });
            setActiveProjectId(id);
            setJustActivated(id);
            if (onProjectConnected && res.data.project) {
                onProjectConnected(res.data.project);
            }
        } catch (err) {
            console.error("Activation failed", err);
            setActivationData({ id, status: 'error' });
            alert("Failed to activate project.");
        }
    };

    const handleTestConnection = async (id) => {
        setTestResult({ id, status: 'loading', message: '', tables: [] });
        try {
            const res = await axios.post(`${API_BASE_URL}/api/projects/${id}/test`);
            if (res.data.status === 'success') {
                setTestResult({ id, status: 'success', message: res.data.message, tables: res.data.tables });
            } else {
                setTestResult({ id, status: 'error', message: res.data.message || "Connection failed.", tables: [] });
            }
        } catch (err) {
            console.error("Test connection failed", err);
            setTestResult({
                id, status: 'error',
                message: err.response?.data?.detail || "Failed to reach server.",
                tables: []
            });
        }
    };

    // Styles
    const labelStyle = { fontSize: '11px', fontWeight: '600', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '2px' };
    const valueStyle = { fontSize: '13px', fontWeight: '500', color: '#334155' };
    const inputStyle = {
        padding: '10px 14px', borderRadius: '8px', border: '1px solid #e2e8f0',
        outline: 'none', fontSize: '14px', transition: 'border-color 0.2s, box-shadow 0.2s',
        width: '100%', boxSizing: 'border-box', background: '#fafbfc'
    };
    const inputFocusHandler = (e) => {
        e.target.style.borderColor = '#2563eb';
        e.target.style.boxShadow = '0 0 0 3px rgba(37, 99, 235, 0.08)';
    };
    const inputBlurHandler = (e) => {
        e.target.style.borderColor = '#e2e8f0';
        e.target.style.boxShadow = 'none';
    };

    return (
        <div style={{ display: 'flex', height: '100%', width: '100%', backgroundColor: '#f8fafc' }}>

            {/* ===== SIDEBAR ===== */}
            <div style={{
                width: '240px', backgroundColor: '#ffffff', borderRight: '1px solid #e2e8f0',
                display: 'flex', flexDirection: 'column', flexShrink: 0
            }}>
                {/* Header */}
                <div style={{ padding: '20px 18px', borderBottom: '1px solid #e2e8f0' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#2563eb' }}>
                        <Plug size={20} />
                        <h1 style={{ fontSize: '16px', fontWeight: '700', margin: 0, fontFamily: "'Outfit', sans-serif" }}>
                            Data Sources
                        </h1>
                    </div>
                    <p style={{ fontSize: '11px', color: '#94a3b8', margin: '4px 0 0 0', letterSpacing: '0.02em' }}>
                        Manage your connections
                    </p>
                </div>

                {/* DB Type Buttons */}
                <div style={{ padding: '12px 0', flex: 1 }}>
                    <div style={{
                        padding: '0 18px', marginBottom: '8px', fontSize: '10px', fontWeight: '700',
                        color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.1em'
                    }}>
                        Connect to
                    </div>

                    {[
                        { key: 'postgres', label: 'PostgreSQL', icon: <Server size={16} />, color: '#2563eb' },
                        { key: 'sqlite', label: 'SQLite', icon: <HardDrive size={16} />, color: '#7c3aed' },
                    ].map(item => (
                        <button
                            key={item.key}
                            onClick={() => { setSelectedTab(item.key); setDbType(item.key); }}
                            style={{
                                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                width: '100%', padding: '10px 18px',
                                backgroundColor: selectedTab === item.key ? '#eff6ff' : 'transparent',
                                border: 'none', cursor: 'pointer', textAlign: 'left',
                                transition: 'all 0.15s',
                                borderLeft: selectedTab === item.key ? `3px solid ${item.color}` : '3px solid transparent'
                            }}
                        >
                            <div style={{
                                display: 'flex', alignItems: 'center', gap: '10px',
                                color: selectedTab === item.key ? item.color : '#475569',
                                fontSize: '13px', fontWeight: '500'
                            }}>
                                {item.icon} {item.label}
                            </div>
                            <ChevronRight size={14} color="#94a3b8" />
                        </button>
                    ))}
                </div>

                {/* Saved Projects Button */}
                <div style={{ padding: '12px 18px', borderTop: '1px solid #e2e8f0' }}>
                    <button
                        onClick={() => { setSelectedTab('Home'); resetForm(); setSelectedProjectId(null); }}
                        style={{
                            display: 'flex', alignItems: 'center', gap: '10px', width: '100%',
                            padding: '10px 12px',
                            backgroundColor: selectedTab === 'Home' ? '#eff6ff' : 'transparent',
                            border: 'none', borderRadius: '8px', cursor: 'pointer',
                            color: selectedTab === 'Home' ? '#2563eb' : '#475569',
                            fontWeight: '500', fontSize: '13px', transition: 'all 0.15s'
                        }}
                    >
                        <LayoutGrid size={16} /> Saved Projects
                    </button>
                </div>
            </div>

            {/* ===== MAIN CONTENT ===== */}
            <div style={{ flex: 1, padding: '28px 40px', overflowY: 'auto' }}>

                {/* ----- HOME TAB ----- */}
                {selectedTab === 'Home' && (
                    <div className="animation-fade-in">
                        {/* Header Row */}
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                <LayoutGrid size={22} color="#334155" />
                                <h2 style={{ fontSize: '22px', color: '#0f172a', margin: 0, fontWeight: '600', fontFamily: "'Outfit', sans-serif" }}>
                                    Projects
                                </h2>
                                <span style={{
                                    fontSize: '12px', color: '#94a3b8', fontWeight: '600',
                                    background: '#f1f5f9', padding: '2px 8px', borderRadius: '10px'
                                }}>
                                    {projects.length}
                                </span>
                            </div>
                            <button
                                onClick={() => setIsCreatingProject(true)}
                                style={{
                                    display: 'flex', alignItems: 'center', gap: '6px',
                                    backgroundColor: '#2563eb', color: 'white',
                                    border: 'none', borderRadius: '8px', padding: '9px 18px',
                                    fontSize: '13px', fontWeight: '600', cursor: 'pointer',
                                    transition: 'all 0.2s', boxShadow: '0 2px 8px rgba(37, 99, 235, 0.2)'
                                }}
                                onMouseEnter={e => e.currentTarget.style.boxShadow = '0 4px 16px rgba(37, 99, 235, 0.3)'}
                                onMouseLeave={e => e.currentTarget.style.boxShadow = '0 2px 8px rgba(37, 99, 235, 0.2)'}
                            >
                                <Plus size={16} /> New Project
                            </button>
                        </div>

                        {/* Just-Activated Success Banner */}
                        <AnimatePresence>
                            {justActivated && (
                                <motion.div
                                    initial={{ opacity: 0, y: -10, height: 0 }}
                                    animate={{ opacity: 1, y: 0, height: 'auto' }}
                                    exit={{ opacity: 0, y: -10, height: 0 }}
                                    style={{
                                        background: 'linear-gradient(135deg, #f0fdf4, #ecfdf5)',
                                        border: '1px solid #86efac',
                                        borderRadius: '12px', padding: '16px 20px', marginBottom: '20px',
                                        display: 'flex', alignItems: 'center', justifyContent: 'space-between'
                                    }}
                                >
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                        <CheckCircle2 size={22} color="#16a34a" />
                                        <div>
                                            <div style={{ fontSize: '14px', fontWeight: '600', color: '#166534' }}>
                                                Project Connected Successfully
                                            </div>
                                            <div style={{ fontSize: '12px', color: '#15803d', marginTop: '2px' }}>
                                                Your data source is ready. Start asking questions about your data.
                                            </div>
                                        </div>
                                    </div>
                                    <div style={{ display: 'flex', gap: '8px' }}>
                                        <button
                                            onClick={() => { setJustActivated(null); onStartChat && onStartChat(); }}
                                            style={{
                                                display: 'flex', alignItems: 'center', gap: '6px',
                                                background: '#16a34a', color: 'white', border: 'none',
                                                borderRadius: '8px', padding: '8px 18px', fontSize: '13px',
                                                fontWeight: '600', cursor: 'pointer', transition: 'all 0.2s',
                                                boxShadow: '0 2px 8px rgba(22, 163, 74, 0.3)'
                                            }}
                                        >
                                            <Zap size={14} /> Start Chatting <ArrowRight size={14} />
                                        </button>
                                        <button
                                            onClick={() => setJustActivated(null)}
                                            style={{
                                                background: 'transparent', border: 'none', color: '#6b7280',
                                                cursor: 'pointer', padding: '4px', borderRadius: '6px'
                                            }}
                                        >
                                            <X size={16} />
                                        </button>
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        {/* Create Project Inline Form */}
                        <AnimatePresence>
                            {isCreatingProject && (
                                <motion.div
                                    initial={{ opacity: 0, y: -10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    exit={{ opacity: 0, y: -10 }}
                                    style={{
                                        backgroundColor: 'white', padding: '18px 22px', borderRadius: '10px',
                                        border: '2px solid #2563eb',
                                        boxShadow: '0 4px 16px rgba(37, 99, 235, 0.1)',
                                        marginBottom: '20px', maxWidth: '480px'
                                    }}
                                >
                                    <h3 style={{ margin: '0 0 12px 0', fontSize: '14px', fontWeight: '600', color: '#0f172a' }}>
                                        Create New Project
                                    </h3>
                                    <form onSubmit={handleCreateProject} style={{ display: 'flex', gap: '10px' }}>
                                        <input
                                            type="text" required autoFocus value={projectName}
                                            onChange={e => setProjectName(e.target.value)}
                                            placeholder="Project name..."
                                            style={{ ...inputStyle, flex: 1 }}
                                            onFocus={inputFocusHandler} onBlur={inputBlurHandler}
                                        />
                                        <button type="submit" disabled={saving} style={{
                                            backgroundColor: '#2563eb', color: 'white', border: 'none',
                                            borderRadius: '8px', padding: '10px 20px', fontSize: '13px',
                                            fontWeight: '600', cursor: 'pointer', whiteSpace: 'nowrap'
                                        }}>
                                            Create
                                        </button>
                                        <button type="button" onClick={() => { setIsCreatingProject(false); setProjectName(''); }} style={{
                                            backgroundColor: '#f1f5f9', color: '#475569', border: 'none',
                                            borderRadius: '8px', padding: '10px 16px', fontSize: '13px',
                                            fontWeight: '500', cursor: 'pointer'
                                        }}>
                                            Cancel
                                        </button>
                                    </form>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        {/* Project Cards */}
                        {loading ? (
                            <div style={{ display: 'flex', justifyContent: 'center', padding: '60px' }}>
                                <div className="spinner-mini" />
                            </div>
                        ) : projects.length === 0 && !isCreatingProject ? (
                            <motion.div
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                style={{
                                    backgroundColor: 'white', padding: '60px 40px', borderRadius: '16px',
                                    border: '2px dashed #cbd5e1', textAlign: 'center'
                                }}
                            >
                                <Database size={48} color="#cbd5e1" style={{ marginBottom: '16px' }} />
                                <h3 style={{ color: '#475569', fontSize: '18px', margin: '0 0 6px 0', fontWeight: '600' }}>
                                    No Projects Yet
                                </h3>
                                <p style={{ color: '#94a3b8', fontSize: '14px', margin: '0 0 20px 0' }}>
                                    Create your first project to connect a database and start asking questions.
                                </p>
                                <button onClick={() => setIsCreatingProject(true)} style={{
                                    backgroundColor: '#2563eb', color: 'white', border: 'none',
                                    borderRadius: '8px', padding: '10px 24px', fontSize: '14px',
                                    fontWeight: '600', cursor: 'pointer',
                                    boxShadow: '0 2px 8px rgba(37, 99, 235, 0.2)'
                                }}>
                                    <Plus size={16} style={{ verticalAlign: 'middle', marginRight: '6px', marginTop: '-2px' }} />
                                    Get Started
                                </button>
                            </motion.div>
                        ) : (
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '16px' }}>
                                {projects.map((p, index) => {
                                    const isActive = p.id === activeProjectId;
                                    const isActivating = activationData.id === p.id && activationData.status === 'loading';

                                    return (
                                        <motion.div
                                            key={p.id}
                                            initial={{ opacity: 0, y: 20 }}
                                            animate={{ opacity: 1, y: 0 }}
                                            transition={{ delay: index * 0.06, duration: 0.3 }}
                                            style={{
                                                backgroundColor: 'white',
                                                borderRadius: '12px',
                                                border: isActive ? '2px solid #10b981' : '1px solid #e2e8f0',
                                                boxShadow: isActive
                                                    ? '0 0 0 3px rgba(16, 185, 129, 0.08), 0 4px 12px rgba(0, 0, 0, 0.04)'
                                                    : '0 1px 4px rgba(0, 0, 0, 0.04)',
                                                transition: 'all 0.2s',
                                                overflow: 'hidden'
                                            }}
                                            whileHover={{ boxShadow: '0 8px 24px rgba(0, 0, 0, 0.08)' }}
                                        >
                                            {/* Card Header */}
                                            <div style={{
                                                padding: '14px 18px', borderBottom: '1px solid #f1f5f9',
                                                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                                backgroundColor: isActive ? '#f0fdf4' : '#fafbfc'
                                            }}>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                                    {p.connection?.db_type === 'sqlite'
                                                        ? <HardDrive size={17} color="#7c3aed" />
                                                        : <Server size={17} color="#2563eb" />}
                                                    <span style={{ fontSize: '15px', fontWeight: '600', color: '#0f172a' }}>
                                                        {p.name}
                                                    </span>
                                                </div>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                    {isActive && (
                                                        <span style={{
                                                            display: 'flex', alignItems: 'center', gap: '4px',
                                                            backgroundColor: '#dcfce7', color: '#15803d',
                                                            padding: '3px 10px', borderRadius: '9999px',
                                                            fontSize: '10px', fontWeight: '700',
                                                            letterSpacing: '0.03em', textTransform: 'uppercase'
                                                        }}>
                                                            <CheckCircle2 size={11} /> Active
                                                        </span>
                                                    )}
                                                    <button
                                                        onClick={(e) => handleDelete(p.id, e)}
                                                        style={{
                                                            background: 'none', border: 'none', color: '#d1d5db',
                                                            cursor: 'pointer', padding: '4px', borderRadius: '6px',
                                                            transition: 'all 0.15s', display: 'flex'
                                                        }}
                                                        onMouseEnter={e => { e.currentTarget.style.color = '#ef4444'; e.currentTarget.style.background = '#fef2f2'; }}
                                                        onMouseLeave={e => { e.currentTarget.style.color = '#d1d5db'; e.currentTarget.style.background = 'none'; }}
                                                    >
                                                        <Trash2 size={14} />
                                                    </button>
                                                </div>
                                            </div>

                                            {/* Card Body */}
                                            {p.connection ? (
                                                <div style={{ padding: '16px 18px' }}>
                                                    {/* Metadata Grid */}
                                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px 20px', marginBottom: '16px' }}>
                                                        <div>
                                                            <div style={labelStyle}>
                                                                <Database size={10} style={{ verticalAlign: 'middle', marginRight: '3px' }} />
                                                                Type
                                                            </div>
                                                            <div style={valueStyle}>
                                                                {p.connection.db_type === 'sqlite' ? 'SQLite' : 'PostgreSQL'}
                                                            </div>
                                                        </div>
                                                        <div>
                                                            <div style={labelStyle}>
                                                                <Shield size={10} style={{ verticalAlign: 'middle', marginRight: '3px' }} />
                                                                Schema
                                                            </div>
                                                            <div style={valueStyle}>{p.connection.db_name || '--'}</div>
                                                        </div>
                                                        <div>
                                                            <div style={labelStyle}>
                                                                <Globe size={10} style={{ verticalAlign: 'middle', marginRight: '3px' }} />
                                                                Host
                                                            </div>
                                                            <div style={{ ...valueStyle, fontSize: '12px', wordBreak: 'break-all' }}>
                                                                {p.connection.db_type === 'sqlite'
                                                                    ? 'Local File'
                                                                    : (p.connection.host ? `${p.connection.host}:${p.connection.port || '5432'}` : '--')}
                                                            </div>
                                                        </div>
                                                        <div>
                                                            <div style={labelStyle}>
                                                                <Layers size={10} style={{ verticalAlign: 'middle', marginRight: '3px' }} />
                                                                Collection
                                                            </div>
                                                            <div style={valueStyle}>
                                                                {p.connection.qdrant_collection || p.connection.db_name || '--'}
                                                            </div>
                                                        </div>
                                                    </div>

                                                    {/* Action Bar */}
                                                    <div style={{
                                                        paddingTop: '14px', borderTop: '1px solid #f1f5f9',
                                                        display: 'flex', justifyContent: 'space-between', alignItems: 'center'
                                                    }}>
                                                        <button
                                                            onClick={() => handleEditConnection(p)}
                                                            style={{
                                                                background: 'none', border: 'none', color: '#64748b',
                                                                fontSize: '12px', cursor: 'pointer', fontWeight: '500',
                                                                padding: '4px 0', transition: 'color 0.15s',
                                                                display: 'flex', alignItems: 'center', gap: '4px'
                                                            }}
                                                            onMouseEnter={e => e.currentTarget.style.color = '#2563eb'}
                                                            onMouseLeave={e => e.currentTarget.style.color = '#64748b'}
                                                        >
                                                            <Pencil size={12} /> Edit
                                                        </button>
                                                        <div style={{ display: 'flex', gap: '8px' }}>
                                                            <button
                                                                onClick={() => handleTestConnection(p.id)}
                                                                disabled={testResult.id === p.id && testResult.status === 'loading'}
                                                                style={{
                                                                    backgroundColor: 'white', color: '#475569',
                                                                    border: '1px solid #e2e8f0', borderRadius: '7px',
                                                                    padding: '6px 14px', fontSize: '12px', fontWeight: '600',
                                                                    cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px',
                                                                    transition: 'all 0.15s'
                                                                }}
                                                                onMouseEnter={e => { e.currentTarget.style.borderColor = '#2563eb'; e.currentTarget.style.color = '#2563eb'; }}
                                                                onMouseLeave={e => { e.currentTarget.style.borderColor = '#e2e8f0'; e.currentTarget.style.color = '#475569'; }}
                                                            >
                                                                {testResult.id === p.id && testResult.status === 'loading'
                                                                    ? <div className="spinner-tiny" style={{ borderColor: 'rgba(0,0,0,0.1)', borderTopColor: '#475569' }} />
                                                                    : <FlaskConical size={12} />}
                                                                Test
                                                            </button>
                                                            <button
                                                                onClick={() => handleActivate(p.id)}
                                                                disabled={isActivating || isActive}
                                                                style={{
                                                                    backgroundColor: isActive ? '#10b981' : '#2563eb',
                                                                    color: 'white', border: 'none', borderRadius: '7px',
                                                                    padding: '6px 16px', fontSize: '12px', fontWeight: '600',
                                                                    cursor: isActive ? 'default' : 'pointer',
                                                                    opacity: isActive ? 0.85 : 1,
                                                                    display: 'flex', alignItems: 'center', gap: '5px',
                                                                    transition: 'all 0.15s',
                                                                    boxShadow: isActive ? 'none' : '0 2px 6px rgba(37, 99, 235, 0.2)'
                                                                }}
                                                            >
                                                                {isActivating
                                                                    ? <div className="spinner-tiny" style={{ borderColor: 'rgba(255,255,255,0.3)', borderTopColor: 'white' }} />
                                                                    : isActive
                                                                        ? <CheckCircle2 size={12} />
                                                                        : <Play size={12} fill="white" />}
                                                                {isActive ? 'Connected' : 'Activate'}
                                                            </button>
                                                        </div>
                                                    </div>

                                                    {/* Test Result */}
                                                    <AnimatePresence>
                                                        {testResult.id === p.id && testResult.status !== 'loading' && (
                                                            <motion.div
                                                                initial={{ opacity: 0, height: 0 }}
                                                                animate={{ opacity: 1, height: 'auto' }}
                                                                exit={{ opacity: 0, height: 0 }}
                                                                style={{
                                                                    marginTop: '12px', padding: '10px 12px', borderRadius: '8px', fontSize: '12px',
                                                                    backgroundColor: testResult.status === 'success' ? '#f0fdf4' : '#fef2f2',
                                                                    color: testResult.status === 'success' ? '#047857' : '#b91c1c',
                                                                    border: `1px solid ${testResult.status === 'success' ? '#bbf7d0' : '#fecaca'}`
                                                                }}
                                                            >
                                                                <div style={{ fontWeight: '600', marginBottom: '3px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                                                    {testResult.status === 'success'
                                                                        ? <><CheckCircle2 size={13} /> Connection Successful</>
                                                                        : <><X size={13} /> Connection Failed</>}
                                                                </div>
                                                                <div>{testResult.message}</div>
                                                                {testResult.status === 'success' && testResult.tables?.length > 0 && (
                                                                    <div style={{ marginTop: '6px', fontSize: '11px', color: '#065f46' }}>
                                                                        <strong>{testResult.tables.length} tables:</strong>{' '}
                                                                        {testResult.tables.length <= 6
                                                                            ? testResult.tables.join(', ')
                                                                            : `${testResult.tables.slice(0, 6).join(', ')}...`}
                                                                    </div>
                                                                )}
                                                            </motion.div>
                                                        )}
                                                    </AnimatePresence>
                                                </div>
                                            ) : (
                                                <div style={{
                                                    padding: '28px 18px', display: 'flex', flexDirection: 'column',
                                                    alignItems: 'center', backgroundColor: '#fafbfc'
                                                }}>
                                                    <Plug size={28} color="#d1d5db" style={{ marginBottom: '10px' }} />
                                                    <span style={{ fontSize: '13px', color: '#94a3b8', marginBottom: '14px' }}>
                                                        No connection configured
                                                    </span>
                                                    <button
                                                        onClick={() => handleEditConnection(p)}
                                                        style={{
                                                            backgroundColor: 'white', border: '1px solid #e2e8f0',
                                                            borderRadius: '7px', padding: '7px 16px', fontSize: '12px',
                                                            fontWeight: '600', color: '#475569', cursor: 'pointer',
                                                            transition: 'all 0.15s', display: 'flex', alignItems: 'center', gap: '6px'
                                                        }}
                                                        onMouseEnter={e => { e.currentTarget.style.borderColor = '#2563eb'; e.currentTarget.style.color = '#2563eb'; }}
                                                        onMouseLeave={e => { e.currentTarget.style.borderColor = '#e2e8f0'; e.currentTarget.style.color = '#475569'; }}
                                                    >
                                                        <Plug size={13} /> Add Connection
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

                {/* ----- CONNECTION FORM TAB ----- */}
                {(selectedTab === 'postgres' || selectedTab === 'sqlite') && (
                    <div className="animation-fade-in" style={{ maxWidth: '560px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '6px' }}>
                            {selectedTab === 'postgres'
                                ? <Server size={22} color="#2563eb" />
                                : <HardDrive size={22} color="#7c3aed" />}
                            <h2 style={{ fontSize: '22px', color: '#0f172a', margin: 0, fontWeight: '600', fontFamily: "'Outfit', sans-serif" }}>
                                {selectedTab === 'postgres' ? 'PostgreSQL' : 'SQLite'} Connection
                            </h2>
                        </div>
                        <p style={{ color: '#94a3b8', fontSize: '13px', marginBottom: '24px' }}>
                            Configure database credentials and vector store settings.
                        </p>

                        {!selectedProjectId ? (
                            <div style={{
                                backgroundColor: '#fffbeb', color: '#92400e', padding: '14px 18px',
                                borderRadius: '10px', border: '1px solid #fde68a', fontSize: '13px',
                                display: 'flex', alignItems: 'center', gap: '10px'
                            }}>
                                <Database size={18} color="#f59e0b" />
                                <div>
                                    <strong>Select a project first.</strong> Go to Saved Projects and click
                                    "Add Connection" or "Edit" on a project card.
                                </div>
                            </div>
                        ) : (
                            <form onSubmit={handleSaveConnection} style={{
                                display: 'flex', flexDirection: 'column', gap: '16px',
                                backgroundColor: 'white', padding: '24px',
                                borderRadius: '12px', border: '1px solid #e2e8f0',
                                boxShadow: '0 2px 8px rgba(0, 0, 0, 0.03)'
                            }}>
                                {/* Project Context Banner */}
                                <div style={{
                                    padding: '10px 14px', backgroundColor: '#f0f9ff', borderRadius: '8px',
                                    border: '1px solid #bae6fd', fontSize: '13px', color: '#0369a1',
                                    fontWeight: '500', display: 'flex', alignItems: 'center', gap: '8px'
                                }}>
                                    <Server size={14} />
                                    Project: <strong>{projects.find(p => p.id === selectedProjectId)?.name || 'Unknown'}</strong>
                                </div>

                                {/* Database + Schema row */}
                                {selectedTab === 'postgres' && (
                                    <div style={{ display: 'flex', gap: '12px' }}>
                                        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                            <label style={{ fontSize: '13px', fontWeight: '600', color: '#334155', display: 'flex', alignItems: 'center', gap: '5px' }}>
                                                <Database size={13} color="#64748b" /> Database
                                            </label>
                                            <input
                                                type="text" required value={database}
                                                onChange={e => setDatabase(e.target.value)}
                                                placeholder="e.g., postgres or alfred-backend"
                                                style={inputStyle}
                                                onFocus={inputFocusHandler} onBlur={inputBlurHandler}
                                            />
                                            <span style={{ fontSize: '10px', color: '#94a3b8' }}>
                                                The PostgreSQL database name to connect to
                                            </span>
                                        </div>
                                        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                            <label style={{ fontSize: '13px', fontWeight: '600', color: '#334155' }}>
                                                Schema
                                            </label>
                                            <input
                                                type="text" required value={dbName}
                                                onChange={e => setDbName(e.target.value)}
                                                placeholder="e.g., public"
                                                style={inputStyle}
                                                onFocus={inputFocusHandler} onBlur={inputBlurHandler}
                                            />
                                            <span style={{ fontSize: '10px', color: '#94a3b8' }}>
                                                Schema for search_path and Qdrant collection
                                            </span>
                                        </div>
                                    </div>
                                )}

                                {/* SQLite schema name */}
                                {selectedTab === 'sqlite' && (
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                        <label style={{ fontSize: '13px', fontWeight: '600', color: '#334155' }}>
                                            Schema / Database Name
                                        </label>
                                        <input
                                            type="text" required value={dbName}
                                            onChange={e => setDbName(e.target.value)}
                                            placeholder="e.g., my_database"
                                            style={inputStyle}
                                            onFocus={inputFocusHandler} onBlur={inputBlurHandler}
                                        />
                                    </div>
                                )}

                                {/* DB-specific fields */}
                                {selectedTab === 'postgres' ? (
                                    <>
                                        <div style={{ display: 'flex', gap: '12px' }}>
                                            <div style={{ flex: 2, display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                                <label style={{ fontSize: '13px', fontWeight: '600', color: '#334155', display: 'flex', alignItems: 'center', gap: '5px' }}>
                                                    <Globe size={13} color="#64748b" /> Host
                                                </label>
                                                <input
                                                    type="text" required value={host}
                                                    onChange={e => setHost(e.target.value)}
                                                    placeholder="db.example.com"
                                                    style={inputStyle}
                                                    onFocus={inputFocusHandler} onBlur={inputBlurHandler}
                                                />
                                            </div>
                                            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                                <label style={{ fontSize: '13px', fontWeight: '600', color: '#334155' }}>Port</label>
                                                <input
                                                    type="text" required value={port}
                                                    onChange={e => setPort(e.target.value)}
                                                    placeholder="5432"
                                                    style={inputStyle}
                                                    onFocus={inputFocusHandler} onBlur={inputBlurHandler}
                                                />
                                            </div>
                                        </div>
                                        <div style={{ display: 'flex', gap: '12px' }}>
                                            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                                <label style={{ fontSize: '13px', fontWeight: '600', color: '#334155' }}>Username</label>
                                                <input
                                                    type="text" value={user}
                                                    onChange={e => setUser(e.target.value)}
                                                    placeholder="postgres"
                                                    style={inputStyle}
                                                    onFocus={inputFocusHandler} onBlur={inputBlurHandler}
                                                />
                                            </div>
                                            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                                <label style={{ fontSize: '13px', fontWeight: '600', color: '#334155', display: 'flex', alignItems: 'center', gap: '5px' }}>
                                                    <Shield size={13} color="#64748b" /> Password
                                                </label>
                                                <input
                                                    type="password" value={password}
                                                    onChange={e => setPassword(e.target.value)}
                                                    placeholder="Enter password"
                                                    style={inputStyle}
                                                    onFocus={inputFocusHandler} onBlur={inputBlurHandler}
                                                />
                                            </div>
                                        </div>
                                    </>
                                ) : (
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                        <label style={{ fontSize: '13px', fontWeight: '600', color: '#334155', display: 'flex', alignItems: 'center', gap: '5px' }}>
                                            <HardDrive size={13} color="#64748b" /> SQLite File Path
                                        </label>
                                        <input
                                            type="text" required value={sqlitePath}
                                            onChange={e => setSqlitePath(e.target.value)}
                                            placeholder="resources/mydb.sqlite"
                                            style={inputStyle}
                                            onFocus={inputFocusHandler} onBlur={inputBlurHandler}
                                        />
                                    </div>
                                )}

                                {/* Divider */}
                                <div style={{ height: '1px', backgroundColor: '#f1f5f9', margin: '2px 0' }} />

                                {/* Qdrant Collection */}
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                    <label style={{ fontSize: '13px', fontWeight: '600', color: '#334155', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                        <Layers size={14} color="#7c3aed" /> Qdrant Collection Name
                                    </label>
                                    <input
                                        type="text" value={qdrantCollection}
                                        onChange={e => setQdrantCollection(e.target.value)}
                                        placeholder={dbName ? `Defaults to "${dbName}"` : 'Defaults to schema name'}
                                        style={inputStyle}
                                        onFocus={inputFocusHandler} onBlur={inputBlurHandler}
                                    />
                                    <span style={{ fontSize: '11px', color: '#94a3b8' }}>
                                        Leave blank to use the schema name as the vector collection.
                                    </span>
                                </div>

                                {/* Actions */}
                                <div style={{ marginTop: '4px', display: 'flex', gap: '10px' }}>
                                    <button type="submit" disabled={saving} style={{
                                        backgroundColor: '#2563eb', color: 'white',
                                        border: 'none', borderRadius: '8px', padding: '11px 24px',
                                        fontSize: '14px', fontWeight: '600', cursor: 'pointer',
                                        display: 'flex', alignItems: 'center', gap: '8px',
                                        transition: 'all 0.2s',
                                        boxShadow: '0 2px 8px rgba(37, 99, 235, 0.2)'
                                    }}>
                                        {saving
                                            ? <div className="spinner-tiny" style={{ borderColor: 'rgba(255,255,255,0.3)', borderTopColor: 'white' }} />
                                            : <Database size={16} />}
                                        Save Connection
                                    </button>
                                    <button type="button" onClick={() => { setSelectedTab('Home'); resetForm(); setSelectedProjectId(null); }} style={{
                                        backgroundColor: '#f8fafc', color: '#475569',
                                        border: '1px solid #e2e8f0', borderRadius: '8px', padding: '11px 20px',
                                        fontSize: '14px', fontWeight: '600', cursor: 'pointer'
                                    }}>
                                        Cancel
                                    </button>
                                </div>
                            </form>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};

export default ProjectsScreen;
