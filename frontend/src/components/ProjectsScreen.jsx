import { useState, useEffect } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Database, Plus, ChevronRight, Server, HardDrive, Play, Trash2,
    Home, LayoutGrid, CheckCircle2, Layers, Globe, FlaskConical,
    Plug, ArrowRight, Pencil, Shield, X, Zap, Cloud, Triangle, Clock
} from 'lucide-react';

const API_BASE_URL = 'http://localhost:8001';

const ProjectsScreen = ({ onProjectConnected, onStartChat, onProjectDeleted, userEmail, userName }) => {
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
    const [qdrantUrl, setQdrantUrl] = useState('');
    const [qdrantApiKey, setQdrantApiKey] = useState('');

    // BigQuery Fields
    const [bqCredentialsPath, setBqCredentialsPath] = useState('');

    // Snowflake Fields
    const [sfWarehouse, setSfWarehouse] = useState('');
    const [sfRole, setSfRole] = useState('');

    // Discovery State
    const [isDiscoveryMode, setIsDiscoveryMode] = useState(false);
    const [discoveryStep, setDiscoveryStep] = useState(1); // 1: Creds/Path, 2: DBs/Files, 3: Schemas (Postgres only)
    const [discoveredDbs, setDiscoveredDbs] = useState([]);
    const [discoveredSchemas, setDiscoveredSchemas] = useState([]);
    const [selectedSchemas, setSelectedSchemas] = useState([]);
    const [discoveredSqliteFiles, setDiscoveredSqliteFiles] = useState([]);
    const [selectedSqliteFiles, setSelectedSqliteFiles] = useState([]);
    const [sqliteDir, setSqliteDir] = useState('');
    const [discovering, setDiscovering] = useState(false);

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
            const res = await axios.get(`${API_BASE_URL}/api/projects`, {
                params: { user_email: userEmail, user_name: userName }
            });
            setProjects(res.data);
        } catch (err) {
            console.error("Failed to fetch projects", err);
        } finally {
            setLoading(false);
        }
    };

    const fetchActiveProject = async () => {
        try {
            const res = await axios.get(`${API_BASE_URL}/api/projects/active`, {
                params: { user_email: userEmail, user_name: userName }
            });
            setActiveProjectId(res.data.active_project_id);
        } catch (err) {
            console.error("Failed to fetch active project", err);
        }
    };

    const handleCreateProject = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            await axios.post(`${API_BASE_URL}/api/projects`, { name: projectName }, {
                params: { user_email: userEmail, user_name: userName }
            });
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
        setQdrantUrl(''); setQdrantApiKey('');
        setIsDiscoveryMode(false);
        setDiscoveryStep(1);
        setDiscoveredDbs([]);
        setDiscoveredSchemas([]);
        setSelectedSchemas([]);
        setDiscoveredSqliteFiles([]);
        setSelectedSqliteFiles([]);
        setSqliteDir('');
        setBqCredentialsPath('');
        setSfWarehouse('');
        setSfRole('');
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
        setQdrantUrl(conn.qdrant_url || '');
        setQdrantApiKey(conn.qdrant_api_key || '');
        setBqCredentialsPath(conn.bq_credentials_path || '');
        setSfWarehouse(conn.sf_warehouse || '');
        setSfRole(conn.sf_role || '');

        if (conn.db_type === 'sqlite') setSelectedTab('sqlite');
        else if (conn.db_type === 'bigquery') setSelectedTab('bigquery');
        else if (conn.db_type === 'snowflake') setSelectedTab('snowflake');
        else setSelectedTab('postgres');
    };

    const handleSaveConnection = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            const payload = {
                db_type: dbType, db_name: dbName, database, host, port,
                user, password, sqlite_path: sqlitePath,
                qdrant_collection: qdrantCollection,
                qdrant_url: qdrantUrl,
                qdrant_api_key: qdrantApiKey,
                bq_credentials_path: bqCredentialsPath,
                sf_warehouse: sfWarehouse,
                sf_role: sfRole
            };
            await axios.put(`${API_BASE_URL}/api/projects/${selectedProjectId}/connection`, payload, {
                params: { user_email: userEmail, user_name: userName }
            });
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

    const handleDeleteProject = async (projectId) => {
        if (!window.confirm("Are you sure you want to delete this project?")) return;
        try {
            await axios.delete(`${API_BASE_URL}/api/projects/${projectId}`, {
                params: { user_email: userEmail, user_name: userName }
            });
            fetchProjects();
            if (projectId === activeProjectId) {
                onProjectDeleted && onProjectDeleted(projectId);
                setJustActivated(null);
            }
            if (testResult.id === projectId) {
                setTestResult({ id: null, status: null, message: '', tables: [] });
            }
        } catch (err) {
            console.error("Failed to delete project", err);
        }
    };

    const handleDeleteAllProjects = async () => {
        if (!window.confirm("CRITICAL: Are you sure you want to delete ALL projects and connections? This cannot be undone.")) return;
        try {
            await axios.delete(`${API_BASE_URL}/api/projects`, {
                params: { user_email: userEmail, user_name: userName }
            });
            fetchProjects();
            setJustActivated(null);
            setTestResult({ id: null, status: null, message: '', tables: [] });
            // Inform parent to reset all
            onProjectDeleted && onProjectDeleted('all');
        } catch (err) {
            console.error("Failed to delete all projects", err);
            alert("Failed to delete all projects.");
        }
    };

    const handleActivate = async (id) => {
        setActivationData({ id, status: 'loading' });
        try {
            const res = await axios.post(`${API_BASE_URL}/api/projects/${id}/activate`, {}, {
                params: { user_email: userEmail, user_name: userName }
            });
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


    const handleDeactivate = async () => {
        setActivationData({ id: activeProjectId, status: 'loading' });

        try {
            const res = await axios.post(
                `${API_BASE_URL}/api/projects/deactivate`,
                {},
                {
                    params: { user_email: userEmail, user_name: userName }
                }
            );

            setActivationData({ id: activeProjectId, status: 'success' });

            // ✅ clear active project
            setActiveProjectId(null);
            setJustActivated(null);

            // optional: inform parent
            if (onProjectDeleted) {
                onProjectDeleted(activeProjectId);
            }

        } catch (err) {
            console.error("Deactivation failed", err);
            setActivationData({ id: activeProjectId, status: 'error' });
            alert("Failed to deactivate project.");
        }
    };

    const handleTestConnection = async (id) => {
        setTestResult({ id, status: 'loading', message: '', tables: [] });
        try {
            const res = await axios.post(`${API_BASE_URL}/api/projects/${id}/test`, {}, {
                params: { user_email: userEmail, user_name: userName }
            });
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

    const handleDiscoverDbs = async (e) => {
        e.preventDefault();
        setDiscovering(true);
        try {
            const res = await axios.post(`${API_BASE_URL}/api/discovery/databases`, {
                host, port, user, password
            });
            setDiscoveredDbs(res.data.databases);
            setDiscoveryStep(2);
        } catch (err) {
            console.error("Discovery failed", err);
            alert("Failed to connect to server: " + (err.response?.data?.detail || err.message));
        } finally {
            setDiscovering(false);
        }
    };

    const handleDiscoverSchemas = async (db) => {
        setDatabase(db);
        setDiscovering(true);
        try {
            const res = await axios.post(`${API_BASE_URL}/api/discovery/schemas`, {
                host, port, user, password, database: db
            });
            setDiscoveredSchemas(res.data.schemas);
            setSelectedSchemas(res.data.schemas); // Select all by default
            setDiscoveryStep(3);
        } catch (err) {
            console.error("Schema discovery failed", err);
            alert("Failed to fetch schemas: " + (err.response?.data?.detail || err.message));
        } finally {
            setDiscovering(false);
        }
    };

    const handleBulkCreate = async () => {
        if (selectedSchemas.length === 0) return;
        setSaving(true);
        try {
            const promises = selectedSchemas.map(schema => {
                const projectName = `${database}_${schema}`;
                const payload = {
                    name: projectName,
                    connection: {
                        db_type: 'postgres',
                        db_name: schema,
                        database: database,
                        host, port, user, password,
                        qdrant_collection: schema
                    }
                };
                return axios.post(`${API_BASE_URL}/api/projects`, payload);
            });
            await Promise.all(promises);
            alert(`Successfully created ${selectedSchemas.length} projects!`);
            resetForm();
            setSelectedTab('Home');
            fetchProjects();
        } catch (err) {
            console.error("Bulk creation failed", err);
            alert("Failed to create projects.");
        } finally {
            setSaving(false);
        }
    };

    const handleDiscoverSqlite = async (e) => {
        e.preventDefault();
        setDiscovering(true);
        try {
            const res = await axios.post(`${API_BASE_URL}/api/discovery/sqlite`, {
                path: sqliteDir
            });
            setDiscoveredSqliteFiles(res.data.files);
            setSelectedSqliteFiles(res.data.files); // Select all by default
            setDiscoveryStep(2);
        } catch (err) {
            console.error("Discovery failed", err);
            alert("Failed to scan directory: " + (err.response?.data?.detail || err.message));
        } finally {
            setDiscovering(false);
        }
    };

    const handleBulkCreateSqlite = async () => {
        if (selectedSqliteFiles.length === 0) return;
        setSaving(true);
        try {
            const promises = selectedSqliteFiles.map(filename => {
                // Name project after filename (without extension)
                const name = filename.replace(/\.(db|sqlite|sqlite3|duckdb)$/i, '');
                const fullPath = `${sqliteDir}/${filename}`.replace(/\/+/g, '/');

                const payload = {
                    name: name,
                    connection: {
                        db_type: 'sqlite',
                        db_name: name,
                        sqlite_path: fullPath,
                        qdrant_collection: name
                    }
                };
                return axios.post(`${API_BASE_URL}/api/projects`, payload);
            });
            const results = await Promise.all(promises);

            // Activate all created projects (last one will remain active in backend)
            // but the UX will show they were all "connected"
            for (const res of results) {
                if (res.data?.id) {
                    await axios.post(`${API_BASE_URL}/api/projects/${res.data.id}/activate`);
                }
            }

            alert(`Successfully created and activated ${selectedSqliteFiles.length} projects!`);
            resetForm();
            setSelectedTab('Home');
            fetchProjects();
            if (onProjectConnected && results.length > 0) {
                // Return the last one as active
                onProjectConnected(results[results.length - 1].data);
            }
        } catch (err) {
            console.error("Bulk creation failed", err);
            alert("Failed to create projects.");
        } finally {
            setSaving(false);
        }
    };




    // Styles
    const labelStyle = { fontSize: '11px', fontWeight: '600', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '2px' };
    const valueStyle = { fontSize: '13px', fontWeight: '500', color: '#334155' };

    const formatLastActivity = (isoString) => {
        if (!isoString) return 'Never';
        try {
            const date = new Date(isoString);
            return new Intl.DateTimeFormat('en-US', {
                month: 'short',
                day: 'numeric',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            }).format(date);
        } catch (e) {
            return 'Recently';
        }
    };
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
                        { key: 'bigquery', label: 'GCP BigQuery', icon: <Cloud size={16} />, color: '#ea4335' },
                        { key: 'snowflake', label: 'Snowflake', icon: <Triangle size={16} style={{ transform: 'rotate(180deg)' }} />, color: '#29b5e8' },
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
                            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                <button
                                    onClick={() => setSelectedTab('Home')}
                                    style={{
                                        display: 'flex', alignItems: 'center', gap: '6px',
                                        backgroundColor: 'white', color: '#475569', border: '1px solid #e2e8f0',
                                        borderRadius: '8px', padding: '10px 16px', fontSize: '13px',
                                        fontWeight: '600', cursor: 'pointer', transition: 'all 0.2s'
                                    }}
                                    onMouseEnter={e => { e.currentTarget.style.borderColor = '#2563eb'; e.currentTarget.style.color = '#2563eb'; }}
                                    onMouseLeave={e => { e.currentTarget.style.borderColor = '#e2e8f0'; e.currentTarget.style.color = '#475569'; }}
                                >
                                    <LayoutGrid size={16} /> View All
                                </button>
                                {projects.length > 0 && (
                                    <button
                                        onClick={handleDeleteAllProjects}
                                        title="Delete All Connections"
                                        style={{
                                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                                            backgroundColor: '#fee2e2', color: '#dc2626', border: '1px solid #fecaca',
                                            borderRadius: '8px', padding: '10px', cursor: 'pointer', transition: 'all 0.2s'
                                        }}
                                        onMouseEnter={e => { e.currentTarget.style.backgroundColor = '#fecaca'; }}
                                        onMouseLeave={e => { e.currentTarget.style.backgroundColor = '#fee2e2'; }}
                                    >
                                        <Trash2 size={16} />
                                    </button>
                                )}
                                <button
                                    onClick={() => setIsCreatingProject(true)}
                                    style={{
                                        display: 'flex', alignItems: 'center', gap: '6px',
                                        backgroundColor: '#2563eb', color: 'white', border: 'none',
                                        borderRadius: '8px', padding: '10px 20px', fontSize: '13px',
                                        fontWeight: '600', cursor: 'pointer', transition: 'all 0.2s',
                                        boxShadow: '0 4px 12px rgba(37, 99, 235, 0.25)'
                                    }}
                                    onMouseEnter={e => e.currentTarget.style.transform = 'translateY(-1px)'}
                                    onMouseLeave={e => e.currentTarget.style.transform = 'translateY(0)'}
                                >
                                    <Plus size={16} strokeWidth={3} /> New Project
                                </button>
                            </div>
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
                                                    {p.connection?.db_type === 'sqlite' ? <HardDrive size={17} color="#7c3aed" /> :
                                                        p.connection?.db_type === 'bigquery' ? <Cloud size={17} color="#ea4335" /> :
                                                            p.connection?.db_type === 'snowflake' ? <Triangle size={17} color="#29b5e8" style={{ transform: 'rotate(180deg)' }} /> :
                                                                <Server size={17} color="#2563eb" />}
                                                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                                                        <span style={{ fontSize: '14px', fontWeight: '600', color: '#0f172a' }}>
                                                            {p.name}
                                                        </span>
                                                        <span style={{ fontSize: '10px', color: '#94a3b8' }}>
                                                            Activity: {formatLastActivity(p.last_activity)}
                                                        </span>
                                                    </div>
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
                                                        onClick={(e) => { e.stopPropagation(); handleDeleteProject(p.id); }}
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
                                                                {p.connection?.db_type === 'bigquery' ? 'Location' : 'Host'}
                                                            </div>
                                                            <div style={{ ...valueStyle, fontSize: '12px', wordBreak: 'break-all' }}>
                                                                {p.connection.db_type === 'sqlite'
                                                                    ? 'Local File'
                                                                    : (p.connection.host ? `${p.connection.host}${p.connection.port ? ':' + p.connection.port : ''}` : '--')}
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
                                                        <div>
                                                            <div style={labelStyle}>
                                                                <Clock size={10} style={{ verticalAlign: 'middle', marginRight: '3px' }} />
                                                                Last Activity
                                                            </div>
                                                            <div style={valueStyle}>
                                                                {formatLastActivity(p.last_activity)}
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

                                                            {/* 🔥 ADD THIS EXACTLY HERE */}
                                                            {isActive && (
                                                                <button
                                                                    onClick={handleDeactivate}
                                                                    style={{
                                                                        backgroundColor: '#ef4444',
                                                                        color: 'white',
                                                                        border: 'none',
                                                                        borderRadius: '7px',
                                                                        padding: '6px 16px',
                                                                        fontSize: '12px',
                                                                        fontWeight: '600',
                                                                        cursor: 'pointer'
                                                                    }}
                                                                >
                                                                    Deactivate
                                                                </button>
                                                            )}


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
                {(selectedTab === 'postgres' || selectedTab === 'sqlite' || selectedTab === 'bigquery' || selectedTab === 'snowflake') && (
                    <div className="animation-fade-in" style={{ maxWidth: '560px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '6px' }}>
                            {selectedTab === 'postgres' ? <Server size={22} color="#2563eb" /> :
                                selectedTab === 'sqlite' ? <HardDrive size={22} color="#7c3aed" /> :
                                    selectedTab === 'bigquery' ? <Cloud size={22} color="#ea4335" /> :
                                        <Triangle size={22} color="#29b5e8" style={{ transform: 'rotate(180deg)' }} />}
                            <h2 style={{ fontSize: '22px', color: '#0f172a', margin: 0, fontWeight: '600', fontFamily: "'Outfit', sans-serif" }}>
                                {selectedTab === 'postgres' ? 'PostgreSQL' :
                                    selectedTab === 'sqlite' ? 'SQLite' :
                                        selectedTab === 'bigquery' ? 'GCP BigQuery' : 'Snowflake'} Connection
                            </h2>
                        </div>
                        <p style={{ color: '#94a3b8', fontSize: '13px', marginBottom: '24px' }}>
                            Configure database credentials and vector store settings.
                        </p>

                        {(selectedTab === 'postgres' || selectedTab === 'sqlite' || selectedTab === 'bigquery' || selectedTab === 'snowflake') && (
                            <div style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
                                <button
                                    onClick={() => { setIsDiscoveryMode(false); setDiscoveryStep(1); }}
                                    style={{
                                        padding: '8px 16px', borderRadius: '8px', fontSize: '13px', fontWeight: '600',
                                        backgroundColor: !isDiscoveryMode ? '#eff6ff' : 'transparent',
                                        color: !isDiscoveryMode ? '#1e40af' : '#64748b',
                                        border: '1px solid', borderColor: !isDiscoveryMode ? '#bfdbfe' : 'transparent',
                                        cursor: 'pointer'
                                    }}
                                >
                                    Manual Setup
                                </button>
                                <button
                                    onClick={() => { setIsDiscoveryMode(true); setDiscoveryStep(1); }}
                                    style={{
                                        padding: '8px 16px', borderRadius: '8px', fontSize: '13px', fontWeight: '600',
                                        backgroundColor: isDiscoveryMode ? (selectedTab === 'sqlite' ? '#f5f3ff' : '#f5f3ff') : 'transparent',
                                        color: isDiscoveryMode ? (selectedTab === 'sqlite' ? '#5b21b6' : '#5b21b6') : '#64748b',
                                        border: '1px solid', borderColor: isDiscoveryMode ? (selectedTab === 'sqlite' ? '#ddd6fe' : '#ddd6fe') : 'transparent',
                                        cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px'
                                    }}
                                >
                                    <Zap size={14} /> Auto-Discovery
                                </button>
                            </div>
                        )}

                        {!selectedProjectId && !isDiscoveryMode ? (
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
                        ) : isDiscoveryMode ? (
                            <div style={{
                                backgroundColor: 'white', padding: '24px', borderRadius: '12px',
                                border: '1px solid #e2e8f0', boxShadow: '0 2px 8px rgba(0, 0, 0, 0.03)',
                                display: 'flex', flexDirection: 'column', gap: '20px'
                            }}>
                                {/* STEP 1: CREDENTIALS / PATH */}
                                {discoveryStep === 1 && (
                                    selectedTab === 'postgres' ? (
                                        <form onSubmit={handleDiscoverDbs} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                                            <div style={{ fontSize: '14px', fontWeight: '600', color: '#1e293b' }}>Step 1: Connect to Server</div>
                                            <div style={{ display: 'flex', gap: '12px' }}>
                                                <div style={{ flex: 2, display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                                    <label style={{ fontSize: '13px', fontWeight: '600', color: '#334155' }}>Host</label>
                                                    <input type="text" required value={host} onChange={e => setHost(e.target.value)} placeholder="localhost" style={inputStyle} />
                                                </div>
                                                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                                    <label style={{ fontSize: '13px', fontWeight: '600', color: '#334155' }}>Port</label>
                                                    <input type="text" required value={port} onChange={e => setPort(e.target.value)} placeholder="5432" style={inputStyle} />
                                                </div>
                                            </div>
                                            <div style={{ display: 'flex', gap: '12px' }}>
                                                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                                    <label style={{ fontSize: '13px', fontWeight: '600', color: '#334155' }}>User</label>
                                                    <input type="text" required value={user} onChange={e => setUser(e.target.value)} placeholder="postgres" style={inputStyle} />
                                                </div>
                                                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                                    <label style={{ fontSize: '13px', fontWeight: '600', color: '#334155' }}>Password</label>
                                                    <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="password" style={inputStyle} />
                                                </div>
                                            </div>
                                            <button type="submit" disabled={discovering} style={{
                                                backgroundColor: '#2563eb', color: 'white', border: 'none', borderRadius: '8px', padding: '12px',
                                                fontWeight: '600', cursor: 'pointer', marginTop: '10px'
                                            }}>
                                                {discovering ? 'Connecting...' : 'Fetch Databases'}
                                            </button>
                                        </form>
                                    ) : (
                                        <form onSubmit={handleDiscoverSqlite} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                                            <div style={{ fontSize: '14px', fontWeight: '600', color: '#1e293b' }}>Step 1: Scan Local Folder</div>
                                            <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                                <label style={{ fontSize: '13px', fontWeight: '600', color: '#334155' }}>Directory Path</label>
                                                <input
                                                    type="text" required value={sqliteDir}
                                                    onChange={e => setSqliteDir(e.target.value)}
                                                    placeholder="C:/Users/Documents/Databases"
                                                    style={inputStyle}
                                                />
                                                <span style={{ fontSize: '11px', color: '#94a3b8' }}>Provide the absolute path to the folder containing your .db or .sqlite files</span>
                                            </div>
                                            <button type="submit" disabled={discovering} style={{
                                                backgroundColor: '#7c3aed', color: 'white', border: 'none', borderRadius: '8px', padding: '12px',
                                                fontWeight: '600', cursor: 'pointer', marginTop: '10px'
                                            }}>
                                                {discovering ? 'Scanning...' : 'Scan Directory'}
                                            </button>
                                        </form>
                                    )
                                )}

                                {/* STEP 2: DATABASES / FILES */}
                                {discoveryStep === 2 && (
                                    selectedTab === 'postgres' ? (
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                                <div style={{ fontSize: '14px', fontWeight: '600', color: '#1e293b' }}>Step 2: Select Database</div>
                                                <button onClick={() => setDiscoveryStep(1)} style={{ fontSize: '12px', color: '#2563eb', background: 'none', border: 'none', cursor: 'pointer' }}>Change Credentials</button>
                                            </div>
                                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: '10px' }}>
                                                {discoveredDbs.map(db => (
                                                    <button
                                                        key={db} onClick={() => handleDiscoverSchemas(db)}
                                                        style={{
                                                            padding: '12px', borderRadius: '8px', border: '1px solid #e2e8f0',
                                                            backgroundColor: 'white', cursor: 'pointer', textAlign: 'left',
                                                            transition: 'all 0.2s', display: 'flex', alignItems: 'center', gap: '8px'
                                                        }}
                                                        onMouseOver={e => e.currentTarget.style.borderColor = '#2563eb'}
                                                        onMouseOut={e => e.currentTarget.style.borderColor = '#e2e8f0'}
                                                    >
                                                        <Database size={14} color="#64748b" />
                                                        <span style={{ fontSize: '13px', fontWeight: '500' }}>{db}</span>
                                                    </button>
                                                ))}
                                            </div>
                                            {discovering && <div style={{ fontSize: '13px', color: '#64748b', textAlign: 'center' }}>Fetching schemas...</div>}
                                        </div>
                                    ) : (
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                                <div style={{ fontSize: '14px', fontWeight: '600', color: '#1e293b' }}>Step 2: Select Files</div>
                                                <button onClick={() => setDiscoveryStep(1)} style={{ fontSize: '12px', color: '#7c3aed', background: 'none', border: 'none', cursor: 'pointer' }}>Change Path</button>
                                            </div>
                                            <div style={{ maxHeight: '250px', overflowY: 'auto', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '10px' }}>
                                                {discoveredSqliteFiles.length > 0 ? discoveredSqliteFiles.map(file => (
                                                    <label key={file} style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '8px', cursor: 'pointer', borderBottom: '1px solid #f8fafc' }}>
                                                        <input
                                                            type="checkbox"
                                                            checked={selectedSqliteFiles.includes(file)}
                                                            onChange={() => {
                                                                setSelectedSqliteFiles(prev =>
                                                                    prev.includes(file) ? prev.filter(f => f !== file) : [...prev, file]
                                                                )
                                                            }}
                                                        />
                                                        <HardDrive size={14} color="#64748b" />
                                                        <span style={{ fontSize: '13px' }}>{file}</span>
                                                    </label>
                                                )) : (
                                                    <div style={{ padding: '20px', textAlign: 'center', color: '#94a3b8', fontSize: '13px' }}>No SQLite files found in this directory.</div>
                                                )}
                                            </div>
                                            <button
                                                onClick={handleBulkCreateSqlite}
                                                disabled={saving || selectedSqliteFiles.length === 0}
                                                style={{
                                                    backgroundColor: '#7c3aed', color: 'white', border: 'none', borderRadius: '8px', padding: '12px',
                                                    fontWeight: '600', cursor: 'pointer', marginTop: '10px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px'
                                                }}
                                            >
                                                {saving ? 'Creating...' : `Create ${selectedSqliteFiles.length} Projects`}
                                            </button>
                                        </div>
                                    )
                                )}

                                {/* STEP 3: SCHEMAS (Postgres Only) */}
                                {discoveryStep === 3 && selectedTab === 'postgres' && (
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                            <div style={{ fontSize: '14px', fontWeight: '600', color: '#1e293b' }}>
                                                Step 3: Select Schemas for <span style={{ color: '#2563eb' }}>{database}</span>
                                            </div>
                                            <button onClick={() => setDiscoveryStep(2)} style={{ fontSize: '12px', color: '#2563eb', background: 'none', border: 'none', cursor: 'pointer' }}>Change Database</button>
                                        </div>
                                        <div style={{ maxHeight: '200px', overflowY: 'auto', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '10px' }}>
                                            {discoveredSchemas.map(schema => (
                                                <label key={schema} style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '8px', cursor: 'pointer' }}>
                                                    <input
                                                        type="checkbox"
                                                        checked={selectedSchemas.includes(schema)}
                                                        onChange={() => {
                                                            setSelectedSchemas(prev =>
                                                                prev.includes(schema) ? prev.filter(s => s !== schema) : [...prev, schema]
                                                            )
                                                        }}
                                                    />
                                                    <span style={{ fontSize: '13px' }}>{schema}</span>
                                                </label>
                                            ))}
                                        </div>
                                        <div style={{ fontSize: '12px', color: '#94a3b8' }}>
                                            Each selected schema will be created as a new project automatically.
                                        </div>
                                        <button
                                            onClick={handleBulkCreate}
                                            disabled={saving || selectedSchemas.length === 0}
                                            style={{
                                                backgroundColor: '#2563eb', color: 'white', border: 'none', borderRadius: '8px', padding: '12px',
                                                fontWeight: '600', cursor: 'pointer', marginTop: '10px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px'
                                            }}
                                        >
                                            {saving ? 'Creating...' : `Create ${selectedSchemas.length} Projects`}
                                        </button>
                                    </div>
                                )}
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

                                {/* Form Fields Selection */}
                                {selectedTab === 'bigquery' ? (
                                    <>
                                        <div style={{ display: 'flex', gap: '12px' }}>
                                            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                                <label style={{ fontSize: '13px', fontWeight: '600', color: '#334155' }}>
                                                    Project ID
                                                </label>
                                                <input
                                                    type="text" required value={database}
                                                    onChange={e => setDatabase(e.target.value)}
                                                    placeholder="e.g., my-gcp-project"
                                                    style={inputStyle}
                                                    onFocus={inputFocusHandler} onBlur={inputBlurHandler}
                                                />
                                            </div>
                                            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                                <label style={{ fontSize: '13px', fontWeight: '600', color: '#334155' }}>
                                                    Dataset ID
                                                </label>
                                                <input
                                                    type="text" required value={dbName}
                                                    onChange={e => setDbName(e.target.value)}
                                                    placeholder="e.g., analytics_dataset"
                                                    style={inputStyle}
                                                    onFocus={inputFocusHandler} onBlur={inputBlurHandler}
                                                />
                                            </div>
                                        </div>
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                            <label style={{ fontSize: '13px', fontWeight: '600', color: '#334155', display: 'flex', alignItems: 'center', gap: '5px' }}>
                                                <Shield size={13} color="#64748b" /> Service Account Key Path
                                            </label>
                                            <input
                                                type="text" required value={bqCredentialsPath}
                                                onChange={e => setBqCredentialsPath(e.target.value)}
                                                placeholder="/absolute/path/to/key.json"
                                                style={inputStyle}
                                                onFocus={inputFocusHandler} onBlur={inputBlurHandler}
                                            />
                                            <span style={{ fontSize: '10px', color: '#94a3b8' }}>
                                                Absolute path to your GCP service account JSON credentials
                                            </span>
                                        </div>
                                    </>
                                ) : selectedTab === 'snowflake' ? (
                                    <>
                                        <div style={{ display: 'flex', gap: '12px' }}>
                                            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                                <label style={{ fontSize: '13px', fontWeight: '600', color: '#334155' }}>
                                                    Account
                                                </label>
                                                <input
                                                    type="text" required value={host}
                                                    onChange={e => setHost(e.target.value)}
                                                    placeholder="xy12345.us-east-1"
                                                    style={inputStyle}
                                                    onFocus={inputFocusHandler} onBlur={inputBlurHandler}
                                                />
                                            </div>
                                            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                                <label style={{ fontSize: '13px', fontWeight: '600', color: '#334155' }}>
                                                    Warehouse
                                                </label>
                                                <input
                                                    type="text" required value={sfWarehouse}
                                                    onChange={e => setSfWarehouse(e.target.value)}
                                                    placeholder="COMPUTE_WH"
                                                    style={inputStyle}
                                                    onFocus={inputFocusHandler} onBlur={inputBlurHandler}
                                                />
                                            </div>
                                        </div>
                                        <div style={{ display: 'flex', gap: '12px' }}>
                                            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                                <label style={{ fontSize: '13px', fontWeight: '600', color: '#334155' }}>
                                                    Database
                                                </label>
                                                <input
                                                    type="text" required value={database}
                                                    onChange={e => setDatabase(e.target.value)}
                                                    placeholder="SNOWFLAKE_SAMPLE_DATA"
                                                    style={inputStyle}
                                                    onFocus={inputFocusHandler} onBlur={inputBlurHandler}
                                                />
                                            </div>
                                            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                                <label style={{ fontSize: '13px', fontWeight: '600', color: '#334155' }}>
                                                    Schema
                                                </label>
                                                <input
                                                    type="text" required value={dbName}
                                                    onChange={e => setDbName(e.target.value)}
                                                    placeholder="TPCH_SF1"
                                                    style={inputStyle}
                                                    onFocus={inputFocusHandler} onBlur={inputBlurHandler}
                                                />
                                            </div>
                                        </div>
                                        <div style={{ display: 'flex', gap: '12px' }}>
                                            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                                <label style={{ fontSize: '13px', fontWeight: '600', color: '#334155' }}>Username</label>
                                                <input
                                                    type="text" required value={user}
                                                    onChange={e => setUser(e.target.value)}
                                                    placeholder="my_user"
                                                    style={inputStyle}
                                                    onFocus={inputFocusHandler} onBlur={inputBlurHandler}
                                                />
                                            </div>
                                            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                                <label style={{ fontSize: '13px', fontWeight: '600', color: '#334155' }}>Password</label>
                                                <input
                                                    type="password" required value={password}
                                                    onChange={e => setPassword(e.target.value)}
                                                    placeholder="password"
                                                    style={inputStyle}
                                                    onFocus={inputFocusHandler} onBlur={inputBlurHandler}
                                                />
                                            </div>
                                        </div>
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                            <label style={{ fontSize: '13px', fontWeight: '600', color: '#334155' }}>
                                                Role (Optional)
                                            </label>
                                            <input
                                                type="text" value={sfRole}
                                                onChange={e => setSfRole(e.target.value)}
                                                placeholder="ACCOUNTADMIN"
                                                style={inputStyle}
                                                onFocus={inputFocusHandler} onBlur={inputBlurHandler}
                                            />
                                        </div>
                                    </>
                                ) : (
                                    <>
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
                                    </>
                                )}

                                {/* Divider */}
                                <div style={{ height: '1px', backgroundColor: '#f1f5f9', margin: '2px 0' }} />

                                {/* Qdrant Configuration */}
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', padding: '16px', backgroundColor: '#f8fafc', borderRadius: '10px', border: '1px solid #e2e8f0' }}>
                                    <h4 style={{ fontSize: '13px', fontWeight: '700', color: '#1e293b', margin: '0 0 4px 0', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                        <Globe size={14} color="#2563eb" /> RAG & Vector Store Configuration
                                    </h4>
                                    
                                    <div style={{ display: 'flex', gap: '12px' }}>
                                        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                            <label style={{ fontSize: '12px', fontWeight: '600', color: '#64748b' }}>Qdrant URL</label>
                                            <input
                                                type="text" value={qdrantUrl}
                                                onChange={e => setQdrantUrl(e.target.value)}
                                                placeholder="http://localhost:6333"
                                                style={{ ...inputStyle, padding: '8px 12px' }}
                                                onFocus={inputFocusHandler} onBlur={inputBlurHandler}
                                            />
                                        </div>
                                        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                            <label style={{ fontSize: '12px', fontWeight: '600', color: '#64748b' }}>API Key</label>
                                            <input
                                                type="password" value={qdrantApiKey}
                                                onChange={e => setPassword(e.target.value)}
                                                placeholder="optional-key"
                                                style={{ ...inputStyle, padding: '8px 12px' }}
                                                onFocus={inputFocusHandler} onBlur={inputBlurHandler}
                                            />
                                        </div>
                                    </div>

                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                        <label style={{ fontSize: '12px', fontWeight: '600', color: '#64748b', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                            <Layers size={14} color="#7c3aed" /> Collection Name
                                        </label>
                                        <input
                                            type="text" value={qdrantCollection}
                                            onChange={e => setQdrantCollection(e.target.value)}
                                            placeholder={dbName ? `Defaults to "${dbName}"` : 'Defaults to schema name'}
                                            style={{ ...inputStyle, padding: '8px 12px' }}
                                            onFocus={inputFocusHandler} onBlur={inputBlurHandler}
                                        />
                                        <span style={{ fontSize: '10px', color: '#94a3b8' }}>
                                            Leave blank to use the schema/database name as the vector collection.
                                        </span>
                                    </div>
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
