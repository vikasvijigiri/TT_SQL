import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  Zap, RefreshCw, Brain, Trash2, Database,
  FolderKanban, MessageSquare, Eraser, HardDrive,
  Clock, Calendar, ShieldAlert
} from 'lucide-react';
import QueryInput from './components/QueryInput';
import AgentLogs from './components/AgentLogs';
import ResultDisplay from './components/ResultDisplay';
import DatasetView from './components/DatasetView';
import DatabaseView from './components/DatabaseView';
import ProjectsScreen from './components/ProjectsScreen';
import LoginScreen from './components/LoginScreen';
import { GoogleOAuthProvider } from '@react-oauth/google';
import { API_BASE_URL } from './config';
import './App.css';
import React from 'react';

// Simple Error Boundary Component
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, errorInfo) {
    console.error("Uncaught error:", error, errorInfo);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '60px', textAlign: 'center', backgroundColor: '#fcfcfc', height: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ padding: '24px', borderRadius: '50%', background: '#fff', boxShadow: '0 10px 40px rgba(0,0,0,0.05)', marginBottom: '32px' }}>
            <ShieldAlert size={48} color="#ef4444" />
          </div>
          <h2 style={{ color: '#0f172a', margin: '0 0 12px', fontSize: '24px', fontWeight: '700' }}>Wait, something broke.</h2>
          <p style={{ color: '#64748b', maxWidth: '420px', lineHeight: '1.6', fontSize: '15px' }}>
            {this.state.error?.message || "An unexpected system failure occurred while rendering the interface."}
          </p>
          <div style={{ marginTop: '32px', display: 'flex', gap: '12px' }}>
            <button onClick={() => window.location.reload()} style={{ padding: '12px 24px', backgroundColor: '#2563eb', color: '#fff', border: 'none', borderRadius: '10px', cursor: 'pointer', fontWeight: '600' }}>
              Refresh Platform
            </button>
            <button onClick={() => window.location.href = "/"} style={{ padding: '12px 24px', backgroundColor: '#fff', color: '#475569', border: '1px solid #e2e8f0', borderRadius: '10px', cursor: 'pointer', fontWeight: '600' }}>
              Go to Home
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

const GOOGLE_CLIENT_ID = '55345566394-np6reosutsqplc5cv6nmkgfiktlnoev3.apps.googleusercontent.com';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [sessionId] = useState(crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2, 15));
  const [loading, setLoading] = useState(false);
  const [isCheckingDb, setIsCheckingDb] = useState(false);
  const [dbConnected, setDbConnected] = useState(null);
  const [executionHistory, setExecutionHistory] = useState("");
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [currentStage, setCurrentStage] = useState('');
  const [messages, setMessages] = useState([]);
  const [selectedDataset] = useState('');
  const [isPrepping, setIsPrepping] = useState(false);
  const [prepStatus, setPrepStatus] = useState('Ready');
  const [currentView, setCurrentView] = useState('projects');
  const [showRawLogs, setShowRawLogs] = useState({});
  const [activeProject, setActiveProject] = useState(null);
  const [sampleQuestions, setSampleQuestions] = useState([]);
  const [isLoadingSamples, setIsLoadingSamples] = useState(false);
  const [storageStats, setStorageStats] = useState(null);
  const [isRefreshingStats, setIsRefreshingStats] = useState(false);
  const [useRag, setUseRag] = useState(true);
  const [selectedModel, setSelectedModel] = useState('gpt-4-turbo');
  const [ragStatus, setRagStatus] = useState({ ready: false, status: 'checking' });

  const getUserSlug = () => {
    if (!user) return 'default_user';
    // Match stabilized backend logic: prioritize email prefix
    if (user.email) return user.email.split('@')[0].toLowerCase();
    
    const namePart = user.name || 'user';
    return namePart.toLowerCase().trim().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '');
  };

  const get_active_project_slug_js = (project) => {
    if (!project) return 'default_project';
    return project.name.toLowerCase().replace(/[^a-z0-9]/g, '_');
  };

  const chatEndRef = useRef(null);
  const abortControllerRef = useRef(null);

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, currentStage]);

  // 1. Initial Load from LocalStorage (Industry Standard persistence)
  useEffect(() => {
    const cachedUser = localStorage.getItem('nquire_user');
    if (cachedUser) {
      try {
        const userData = JSON.parse(cachedUser);
        setUser(userData);
        setIsAuthenticated(true);
        restoreUserState(userData);
      } catch (e) {
        console.error("Failed to restore cached user", e);
        localStorage.removeItem('nquire_user');
      }
    }
  }, []);

  useEffect(() => {
    if (user) {
      checkDbStatus();
      fetchActiveProject();
    }
  }, [user]);

  useEffect(() => {
    if (activeProject?.id) {
      fetchSampleQuestions(activeProject.id);
    } else {
      // Clean fallback when no project is active
      setSampleQuestions([]);
    }
  }, [activeProject]);

  useEffect(() => {
    if (currentView === 'maintenance') {
      fetchStorageStats();
    }
  }, [currentView, activeProject]);

  const fetchStorageStats = async () => {
    setIsRefreshingStats(true);
    try {
      const res = await axios.get(`${API_BASE_URL}/api/data/storage/workspaces`, {
        params: { user_email: user?.email, user_name: user?.name }
      });
      setStorageStats(res.data);
    } catch (err) {
      console.error("Failed to fetch storage stats", err);
    } finally {
      setTimeout(() => setIsRefreshingStats(false), 600); // Smooth transition back
    }
  };

  const handleWipeWorkspace = async (slug, projectName) => {
    if (!window.confirm(`CRITICAL: This will permanently delete ALL results (SQL, CSV, logs) for the workspace "${projectName || slug}". This action cannot be undone. Proceed?`)) return;

    try {
      setLoading(true);
      await axios.delete(`${API_BASE_URL}/api/data/cleanup/workspace/${slug}`, {
        params: { user_email: user?.email, user_name: user?.name }
      });
      if (activeProject && get_active_project_slug_js(activeProject) === slug) {
        setExecutionHistory("");
        setMessages([]);
      }
      fetchStorageStats();
      alert(`Workspace "${projectName || slug}" cleared.`);
    } catch (err) {
      console.error(err);
      alert("Failed to wipe workspace data");
    } finally {
      setLoading(false);
    }
  };

  const fetchActiveProject = async () => {
    try {
      const res = await axios.get(`${API_BASE_URL}/api/projects/active`, {
        params: { user_email: user?.email, user_name: user?.name }
      });
      if (res.data.project) {
        setActiveProject(res.data.project);
      } else {
        setActiveProject(null);
      }
    } catch (err) {
      console.error("Failed to fetch active project", err);
    }
  };

  const fetchRagStatus = async () => {
    if (!activeProject || !user) return;
    try {
      const res = await axios.get(`${API_BASE_URL}/api/prep/status`, {
        params: { user_email: user?.email, user_name: user?.name }
      });
      setRagStatus(res.data);
    } catch (err) {
      console.error("Failed to fetch RAG status", err);
      setRagStatus({ ready: false, status: 'Error' });
    }
  };

  useEffect(() => {
    if (activeProject) {
      fetchRagStatus();
      checkDbStatus();
    }
  }, [activeProject]);

  // Restores user state from backend on login
  const restoreUserState = async (userData) => {
    if (!userData) return;
    try {
      const response = await axios.get(`${API_BASE_URL}/user/state`, {
        params: {
          user_email: userData.email,
          user_name: userData.name
        }
      });
      const state = response.data;
      if (state.currentView) setCurrentView(state.currentView);
      if (state.activeProjectId) {
          // Triggers a fetch to get the full project details
          await fetchActiveProject();
      }
      if (state.use_rag !== undefined) setUseRag(state.use_rag);
      if (state.messages) setMessages(state.messages);
      if (state.selectedModel) setSelectedModel(state.selectedModel);
    } catch (err) {
      console.error("Failed to restore app state", err);
    }
  };

  // State Persistence Effect (Debounced)
  useEffect(() => {
    if (!isAuthenticated || !user) return;

    const timer = setTimeout(async () => {
      try {
        await axios.post(`${API_BASE_URL}/user/state`, 
          {
            currentView,
            activeProjectId: activeProject?.id,
            selectedDataset,
            use_rag: useRag,
            messages: messages.slice(-20), // Persist last 20 messages for state restoration
            selectedModel
          },
          {
            params: {
              user_email: user.email,
              user_name: user.name
            }
          }
        );
      } catch (err) {
        console.warn("Failed to persist app state", err);
      }
    }, 2000); 

    return () => clearTimeout(timer);
  }, [currentView, activeProject, selectedDataset, useRag, messages, selectedModel, isAuthenticated, user]);

  const fetchSampleQuestions = async (projectId) => {
    setIsLoadingSamples(true);
    try {
      const res = await axios.get(`${API_BASE_URL}/api/projects/${projectId}/samples`, {
        params: { user_email: user?.email, user_name: user?.name }
      });
      if (res.data.questions) {
        setSampleQuestions(res.data.questions);
      }
    } catch (err) {
      console.error("Failed to fetch sample questions", err);
    } finally {
      setIsLoadingSamples(false);
    }
  };

  const checkDbStatus = async () => {
    setIsCheckingDb(true);
    try {
      const response = await axios.get(`${API_BASE_URL}/api/health/db`, {
        params: { user_email: user?.email, user_name: user?.name }
      });
      setDbConnected(response.data.connected);
    } catch (err) {
      console.error('Failed to check DB status:', err);
      setDbConnected(false);
    } finally {
      setIsCheckingDb(false);
    }
  };

  const handleConnectDB = async (force = false) => {
    if (isPrepping) return;
    setIsPrepping(true);
    setPrepStatus('Starting');

    try {
      const response = await fetch(`${API_BASE_URL}/api/prep/run?force=${force}&user_email=${user?.email}&user_name=${user?.name}`, {
        method: 'POST'
      });
      if (!response.ok) throw new Error("Failed to start preparation");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.replace('data: ', '').trim());
              setPrepStatus(data.message);
              if (data.level === 'SUCCESS') {
                checkDbStatus();
                fetchRagStatus();
                setTimeout(() => setPrepStatus('Ready'), 5000);
              } else if (data.level === 'ERROR') {
                setTimeout(() => setPrepStatus('Ready'), 5000);
              }
            } catch (e) {
              console.error("Error parsing SSE data", e);
            }
          }
        }
      }
    } catch (err) {
      console.error(err);
      setPrepStatus('Error');
      setTimeout(() => setPrepStatus('Ready'), 5000);
    } finally {
      setIsPrepping(false);
    }
  };

  const handleDeleteCollection = async () => {
    if (isPrepping) return;
    if (!window.confirm("Are you sure you want to delete the current vector collection? This action cannot be undone.")) return;
    setIsPrepping(true);
    setPrepStatus('Deleting');

    try {
      const response = await axios.delete(`${API_BASE_URL}/api/prep/collection`);
      if (response.data.status === 'success') {
        setPrepStatus('Deleted');
        checkDbStatus();
        fetchRagStatus();
        setTimeout(() => setPrepStatus('Ready'), 3000);
      }
    } catch (err) {
      console.error('Failed to delete collection:', err);
      setPrepStatus('Error');
      setTimeout(() => setPrepStatus('Ready'), 3000);
    } finally {
      setIsPrepping(false);
    }
  };

  const fetchExecutionHistory = async (instanceId) => {
    setLoadingHistory(true);
    try {
      const response = await axios.get(`${API_BASE_URL}/api/data/logs/history`, {
        params: { 
          instance_id: instanceId,
          user_email: user?.email 
        }
      });
      setExecutionHistory(response.data.content);
    } catch (err) {
      console.error("Failed to fetch execution history:", err);
    } finally {
      setLoadingHistory(false);
    }
  };

  const handlePurgeProject = async () => {
    if (!activeProject) return;
    if (!window.confirm(`WARNING: This will permanently delete ALL analytical results (SQL, CSV, logs) for the project "${activeProject.name}". This action cannot be undone. Proceed?`)) return;

    try {
      setLoading(true);
      await axios.delete(`${API_BASE_URL}/api/data/cleanup/project`, {
        params: { user_email: user?.email, user_name: user?.name }
      });
      setExecutionHistory("");
      setMessages([]);
      fetchStorageStats();
      alert("Project results successfully purged.");
    } catch (err) {
      console.error(err);
      alert("Failed to purge project results");
    } finally {
      setLoading(false);
    }
  };

  const handlePurgeSession = async (period) => {
    const periodLabels = { hour: 'Last Hour', hour2: 'Last 2 Hours', hour4: 'Last 4 Hours', today: 'Today', yesterday: 'Yesterday' };
    if (!window.confirm(`Clear session results for: ${periodLabels[period]}?`)) return;

    try {
      setLoading(true);
      const res = await axios.delete(`${API_BASE_URL}/api/data/cleanup/session?period=${period}`, {
        params: { user_email: user?.email, user_name: user?.name }
      });
      alert(`Cleaned up ${res.data.deleted_files || 0} files from session.`);
      fetchExecutionHistory();
      fetchStorageStats();
    } catch (err) {
      console.error(err);
      alert("Failed to clear session data");
    } finally {
      setLoading(false);
    }
  };


  const handleSendQuery = async (query) => {
    if (loading) return;

    const userMessage = { id: Date.now(), role: 'user', content: query };
    setMessages(prev => [...prev, userMessage]);

    const assistantMessageId = Date.now() + 1;
    setMessages(prev => [...prev, {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      status: 'Connecting...',
      type: 'thinking',
      payload: { business_summary: '', sql: '', results: [], columns: [], logs: [] }
    }]);

    setLoading(true);
    setCurrentStage('Initializing');

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await fetch(`${API_BASE_URL}/api/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
        body: JSON.stringify({
          query: query,
          db_name: activeProject ? (activeProject.connection?.db_name || activeProject.name) : '',
          dataset_name: activeProject ? '' : selectedDataset,
          use_rag: useRag,
          user_email: user?.email,
          session_id: sessionId
        }),
      });

      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const jsonStr = line.replace('data: ', '').trim();
            if (!jsonStr) continue;

            try {
              const data = JSON.parse(jsonStr);

              if (data.type === 'section') {
                const stage = data.message.replace('\u{1F4A0}', '').trim();
                setCurrentStage(stage);
                setMessages(prev => {
                  const newMessages = [...prev];
                  const idx = newMessages.findIndex(m => m.id === assistantMessageId);
                  if (idx !== -1) {
                    newMessages[idx] = {
                      ...newMessages[idx],
                      status: stage,
                      payload: {
                        ...newMessages[idx].payload,
                        logs: [...(newMessages[idx].payload?.logs || []), stage]
                      }
                    };
                  }
                  return newMessages;
                });
              } else if (data.type === 'id') {
                setMessages(prev => {
                  const newMessages = [...prev];
                  const idx = newMessages.findIndex(m => m.id === assistantMessageId);
                  if (idx !== -1) {
                    newMessages[idx] = {
                      ...newMessages[idx],
                      instance_id: data.instance_id,
                      status: 'Initializing',
                      payload: { ...newMessages[idx].payload, instance_id: data.instance_id }
                    };
                  }
                  return newMessages;
                });
              } else if (data.type === 'token') {
                setMessages(prev => {
                  const newMessages = [...prev];
                  const idx = newMessages.findIndex(m => m.id === assistantMessageId);
                  if (idx !== -1) {
                    newMessages[idx] = {
                      ...newMessages[idx],
                      type: 'result',
                      status: 'Streaming Insights...',
                      payload: {
                        ...newMessages[idx].payload,
                        business_summary: (newMessages[idx].payload?.business_summary || '') + data.token
                      }
                    };
                  }
                  return newMessages;
                });
              } else if (data.type === 'result') {
                setMessages(prev => {
                  const newMessages = [...prev];
                  const idx = newMessages.findIndex(m => m.id === assistantMessageId);
                  if (idx !== -1) {
                    newMessages[idx] = {
                      ...newMessages[idx],
                      type: 'result',
                      status: null,
                      payload: {
                        sql: data.sql,
                        results: data.results || [],
                        columns: data.columns || [],
                        total_count: data.total_count || 0,
                        business_summary: data.business_summary,
                        chart_config: data.chart_config || null,
                        total_time: data.total_time
                      }
                    };
                  }
                  return newMessages;
                });
                setLoading(false);
                setCurrentStage('');
              } else if (data.type === 'error') {
                setMessages(prev => {
                  const newMessages = [...prev];
                  const idx = newMessages.findIndex(m => m.id === assistantMessageId);
                  if (idx !== -1) {
                    newMessages[idx] = {
                      ...newMessages[idx],
                      type: 'error',
                      content: data.message,
                      status: null
                    };
                  }
                  return newMessages;
                });
                setLoading(false);
                setCurrentStage('');
              }
            } catch (e) {
              console.error("Error parsing stream chunk:", e);
            }
          }
        }
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        console.log("Fetch aborted");
      } else {
        console.error(err);
        setMessages(prev => prev.map(m =>
          m.id === assistantMessageId ? { ...m, type: 'error', content: err.message, status: null } : m
        ));
        setLoading(false);
        setCurrentStage('');
      }
    } finally {
      abortControllerRef.current = null;
    }
  };

  const handleStopQuery = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setLoading(false);
      setCurrentStage('');

      setMessages(prev => {
        const newMessages = [...prev];
        const lastMsgIdx = newMessages.length - 1;
        if (lastMsgIdx >= 0 && newMessages[lastMsgIdx].role === 'assistant') {
          newMessages[lastMsgIdx] = {
            ...newMessages[lastMsgIdx],
            status: null,
            content: newMessages[lastMsgIdx].content || 'Query cancelled by user.',
            type: newMessages[lastMsgIdx].type === 'thinking' ? 'error' : newMessages[lastMsgIdx].type,
            payload: {
              ...newMessages[lastMsgIdx].payload,
              logs: [...(newMessages[lastMsgIdx].payload?.logs || []), 'Terminated by user']
            }
          };
        }
        return newMessages;
      });
    }
  };

  const navItems = [
    { id: 'projects', icon: FolderKanban, label: 'Projects' },
    { id: 'chat', icon: MessageSquare, label: 'Ask Data' },
    { id: 'database', icon: Database, label: 'Data Explorer' },
    { id: 'maintenance', icon: HardDrive, label: 'Storage' },
  ];

  return (
    <ErrorBoundary>
      <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      {!isAuthenticated ? (
        <LoginScreen onLogin={(userData) => {
          setIsAuthenticated(true);
          setUser(userData);
          localStorage.setItem('nquire_user', JSON.stringify(userData));
          restoreUserState(userData);
        }} />
      ) : (
        <div className="app-root">
          {/* ===== LEFT SIDEBAR ===== */}
          <nav className="nav-sidebar">
            <div className="nav-logo" onClick={() => setCurrentView('projects')}>
              <Zap size={22} />
            </div>

            <div className="nav-items">
              {navItems.map(item => (
                <button
                  key={item.id}
                  className={`nav-item ${currentView === item.id ? 'active' : ''}`}
                  onClick={() => {
                    setCurrentView(item.id);
                  }}
                >
                  <item.icon size={20} />
                  <span className="nav-tooltip">{item.label}</span>
                </button>
              ))}
            </div>

            <div className="nav-divider" />

            <div className="nav-utils">
              <button
                className={`nav-item ${isPrepping ? 'active' : ''}`}
                onClick={() => handleConnectDB(false)}
                disabled={isPrepping}
              >
                <Brain size={20} className={isPrepping ? 'pulse' : ''} />
                <span className="nav-tooltip">Inject Knowledge (RAG)</span>
              </button>
              <button
                className="nav-item"
                onClick={handleDeleteCollection}
                disabled={isPrepping}
                style={{ color: 'rgba(239, 68, 68, 0.5)' }}
              >
                <Trash2 size={18} />
                <span className="nav-tooltip">Delete Collection</span>
              </button>
              <button
                className={`nav-item ${isCheckingDb ? 'active' : ''}`}
                onClick={checkDbStatus}
                disabled={isCheckingDb}
              >
                <RefreshCw size={18} className={isCheckingDb ? 'spin' : ''} />
                <span className="nav-tooltip">Refresh Status</span>
              </button>
            </div>

            <div className="nav-footer">
              <button
                className="user-profile-btn"
                onClick={() => {
                  if (window.confirm("Logout of NextGen SQL?")) {
                    setIsAuthenticated(false);
                    setUser(null);
                    localStorage.removeItem('nquire_user');
                  }
                }}
              >
                {user?.picture ? (
                  <img src={user.picture} alt="Profile" className="user-avatar" title={user.email} />
                ) : (
                  <div className="user-avatar-initials" title={user?.email || 'User'}>
                    {user?.name?.[0] || user?.email?.[0] || 'U'}
                  </div>
                )}
                <span className="nav-tooltip">Sign Out</span>
              </button>
            </div>
          </nav>

          {/* ===== MAIN PANEL ===== */}
          <div className="main-panel">
            <header className="top-bar">
              <div className="top-bar-left">
                <h1 className="app-title">nQuire</h1>
                <span className="app-subtitle">AI Business Intelligence</span>
              </div>

              <div className="top-bar-center">
                {activeProject && (
                  <div className="active-project-badge">
                    <span className="project-dot" />
                    <span className="project-name">{activeProject.name}</span>
                    <span className="project-db-type">
                      {activeProject.connection?.db_type === 'sqlite' ? 'SQLite' : 'PostgreSQL'}
                    </span>
                  </div>
                )}
              </div>

              <div className="top-bar-right">
                {activeProject && (
                  <>
                    <div className={`status-indicator ${ragStatus.ready ? 'connected' : 'disconnected'}`} style={{ cursor: 'pointer' }} onClick={fetchRagStatus}>
                      <span className="status-dot-sm" />
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        KB: <strong>{ragStatus.ready ? `${ragStatus.status} (${ragStatus.collection || 'Active'})` : ragStatus.status}</strong>
                      </span>
                    </div>
                    <button 
                      className={`status-indicator ${useRag ? 'connected' : 'disconnected'}`} 
                      onClick={() => setUseRag(!useRag)}
                      title={useRag ? "Knowledge Base ON" : "Knowledge Base OFF"}
                      style={{ cursor: 'pointer', border: 'none', background: 'transparent' }}
                    >
                      <Brain size={14} className={useRag ? 'pulse' : ''} />
                      <span>RAG: {useRag ? 'ON' : 'OFF'}</span>
                    </button>
                  </>
                )}
                <div className={`status-indicator ${dbConnected === true ? 'connected' : dbConnected === false ? 'disconnected' : ''}`} title={activeProject ? `Connected to ${activeProject.name}` : "No database connected"}>
                  <span className="status-dot-sm" />
                  <span>
                    {isCheckingDb ? 'Checking...' : (activeProject ? (activeProject.connection?.db_name || activeProject.connection?.qdrant_collection || activeProject.name) : 'No Source')}
                  </span>
                </div>
                {isPrepping && prepStatus !== 'Ready' && (
                  <div className="prep-indicator">
                    <div className="spinner-tiny" />
                    <span>{prepStatus}</span>
                  </div>
                )}
              </div>
            </header>

            <div className="content-wrapper">
              {/* Projects View */}
              {currentView === 'projects' && (
                <ProjectsScreen
                  userEmail={user?.email}
                  userName={user?.name}
                  onProjectConnected={(project) => {
                    setActiveProject(project);
                    checkDbStatus();
                    fetchRagStatus();
                  }}
                  onProjectDeleted={(id) => {
                    if (id === 'all' || (activeProject && activeProject.id === id)) {
                      setActiveProject(null);
                      setDbConnected(false);
                      setRagStatus({ ready: false, status: 'Not Connected' });
                    }
                  }}
                  onStartChat={() => setCurrentView('chat')}
                />
              )}

              {/* Database View */}
              {currentView === 'database' && (
                <DatabaseView 
                  userEmail={user?.email}
                  userName={user?.name}
                  onBack={() => setCurrentView('chat')} 
                />
              )}

              {/* Dataset View */}
              {currentView === 'dataset' && (
                <DatasetView onBack={() => setCurrentView('chat')} />
              )}

              {/* Ask Data Chat View */}
              {currentView === 'chat' && (
                <div className="chat-view anim-fade-in">
                  <div className="chat-area">
                    <div className="message-list">
                      {!activeProject && (
                        <div className="no-project-banner">
                          <span>No project connected.</span>
                          <button onClick={() => setCurrentView('projects')}>Setup</button>
                        </div>
                      )}

                      {messages.length === 0 ? (
                        <div className="hero-section minimal">
                          <Zap size={40} color="var(--accent-blue)" className="pulse" />
                          <h2>How can I help?</h2>
                          <div className="suggestion-chips vertical">
                            {sampleQuestions.slice(0, 3).map((q, idx) => (
                              <span key={idx} onClick={() => handleSendQuery(q)}>{q}</span>
                            ))}
                          </div>
                        </div>
                      ) : (
                        messages.map((msg) => (
                          <div key={msg.id} className={`message-wrapper ${msg.role}`}>
                            <div className="message-bubble glass-panel">
                              {msg.role === 'user' ? (
                                <div className="user-text">{msg.content}</div>
                              ) : (
                                <div className="assistant-content">
                                  {msg.status && (
                                    <div className="thinking-mini">
                                      <div className="spinner-mini"></div>
                                      <span> {msg.status}...</span>
                                    </div>
                                  )}

                                  <div className="message-actions-overlay">
                                    <div className="toggle-switch-container">
                                      <span className={`switch-label ${!showRawLogs[msg.id] ? 'active' : ''}`}>Insights</span>
                                      <label className="premium-switch">
                                        <input 
                                          type="checkbox" 
                                          checked={!!showRawLogs[msg.id]}
                                          onChange={() => {
                                            const newState = !showRawLogs[msg.id];
                                            setShowRawLogs(prev => ({ ...prev, [msg.id]: newState }));
                                            if (newState) fetchExecutionHistory(msg.instance_id || msg.id);
                                          }}
                                        />
                                        <span className="premium-slider"></span>
                                      </label>
                                      <span className={`switch-label ${showRawLogs[msg.id] ? 'active' : ''}`}>Logs</span>
                                    </div>
                                  </div>

                                  {showRawLogs[msg.id] && (
                                    <div className="stages-history">
                                      <AgentLogs 
                                        historyLog={executionHistory}
                                        loadingHistory={loadingHistory}
                                      />
                                    </div>
                                  )}

                                  {msg.type === 'result' && !showRawLogs[msg.id] && (
                                    <ResultDisplay 
                                      sql={msg.payload.sql}
                                      results={msg.payload.results}
                                      columns={msg.payload.columns}
                                      total_count={msg.payload.total_count}
                                      business_summary={msg.payload.business_summary}
                                      chart_config={msg.payload.chart_config}
                                      total_time={msg.payload.total_time}
                                      token_usage={msg.payload.token_usage}
                                    />
                                  )}

                                  {msg.type === 'error' && (
                                    <div className="error-display">
                                      <div className="error-message">{msg.content}</div>
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          </div>
                        ))
                      )}
                      <div ref={chatEndRef} />
                    </div>
                  </div>
                  <footer className="footer-bar animated-footer">
                    <QueryInput
                      onSend={handleSendQuery}
                      onStop={handleStopQuery}
                      loading={loading}
                    />
                  </footer>
                </div>
              )}

              {/* Maintenance View */}
              {currentView === 'maintenance' && (
                <div className="page-layout">
                  {/* ===== SIDEBAR ===== */}
                  <div className="page-sidebar">
                    <div className="page-sidebar-header">
                      <HardDrive size={18} color="#2563eb" />
                      <h2>Storage</h2>
                    </div>

                    <div className="page-sidebar-section-label">Overview</div>
                    <div style={{ padding: '8px 18px 16px' }}>
                      <div style={{ fontSize: '12px', color: '#64748b', lineHeight: '1.6' }}>
                        Project: <strong style={{ color: '#334155' }}>{activeProject?.name || 'None'}</strong>
                      </div>
                      <div style={{ marginTop: '8px', display: 'flex', gap: '12px' }}>
                        <div style={{ textAlign: 'center' }}>
                          <div style={{ fontSize: '18px', fontWeight: '700', color: '#0f172a' }}>
                            {Array.isArray(storageStats) ? storageStats.reduce((acc, ws) => acc + (Number(ws.size_mb) || 0), 0).toFixed(1) : '0'}
                          </div>
                          <div style={{ fontSize: '10px', color: '#94a3b8', fontWeight: '600', textTransform: 'uppercase' }}>MB used</div>
                        </div>
                        <div style={{ textAlign: 'center' }}>
                          <div style={{ fontSize: '18px', fontWeight: '700', color: '#0f172a' }}>
                            {Array.isArray(storageStats) ? storageStats.reduce((acc, ws) => acc + (Number(ws.file_count) || 0), 0) : 0}
                          </div>
                          <div style={{ fontSize: '10px', color: '#94a3b8', fontWeight: '600', textTransform: 'uppercase' }}>artifacts</div>
                        </div>
                      </div>
                    </div>

                    <div className="page-sidebar-section-label">Actions</div>
                    {[
                      { key: 'registry', label: 'Workspace Registry', icon: FolderKanban },
                      { key: 'session', label: 'Context Refresh', icon: Clock },
                      { key: 'danger', label: 'Deep Wipe', icon: ShieldAlert },
                    ].map(item => (
                      <button key={item.key} className="page-sidebar-item" style={{ borderLeftColor: 'transparent' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <item.icon size={14} />
                          <span>{item.label}</span>
                        </div>
                      </button>
                    ))}

                    <div style={{ marginTop: 'auto', padding: '12px 18px', borderTop: '1px solid #e2e8f0' }}>
        <button
          className={`btn-premium-refresh ${isRefreshingStats ? 'refreshing' : ''}`}
          onClick={() => fetchStorageStats()}
          disabled={isRefreshingStats}
          style={{ width: '100%', justifyContent: 'center' }}
        >
                        <span className="btn-icon"><RefreshCw size={14} /></span>
                        <span>{isRefreshingStats ? 'Syncing...' : 'Refresh'}</span>
                      </button>
                    </div>
                  </div>

                  {/* ===== MAIN CONTENT ===== */}
                  <div className="page-content">
                    {/* Page Title */}
                    <div style={{ marginBottom: '24px' }}>
                      <h2 style={{ margin: 0, fontSize: '20px', fontWeight: '600', color: '#0f172a', fontFamily: "'Outfit', sans-serif" }}>
                        Storage Maintenance
                      </h2>
                      <p style={{ margin: '4px 0 0', fontSize: '13px', color: '#94a3b8' }}>
                        Manage analytical artifacts and workspace retention for <strong style={{ color: '#64748b' }}>{activeProject?.name || 'No Project'}</strong>
                      </p>
                    </div>

                    <div className="maintenance-grid">
                      {/* Master Overview: Registry Table */}
                      <div className="maintenance-card full-width primary-glow">
                        <div className="card-icon">
                          <FolderKanban size={24} color="var(--accent-blue)" />
                        </div>
                        <div className="card-body">
                          <div className="card-title-row">
                            <h3>Analytical Workspace Registry</h3>
                            <span className="count-badge">{Array.isArray(storageStats) ? storageStats.length : 0} Workspaces</span>
                          </div>
                          <p>Master overview of all project results. Wipe workspaces or purge orphans to reclaim disk space.</p>

                          <div className="workspace-table-container">
                            <table className="workspace-table">
                              <thead>
                                <tr>
                                  <th>Project Workspace</th>
                                  <th>Disk Usage</th>
                                  <th>Artifacts</th>
                                  <th>Status</th>
                                  <th>Action</th>
                                </tr>
                              </thead>
                              <tbody>
                                {Array.isArray(storageStats) && storageStats.map((ws) => (
                                  <tr key={ws.slug} className={ws.is_orphaned ? 'orphaned-row' : ''}>
                                    <td>
                                      <div className="ws-name-cell">
                                        <strong>{ws.name}</strong>
                                        <code className="ws-slug">{ws.slug}</code>
                                      </div>
                                    </td>
                                    <td className="ws-size">{ws.size_mb} MB</td>
                                    <td className="ws-files">{ws.file_count} files</td>
                                    <td>
                                      {ws.is_orphaned ? (
                                        <span className="status-pill warning">Orphaned</span>
                                      ) : (
                                        <span className={`status-pill ${activeProject && get_active_project_slug_js(activeProject) === ws.slug ? 'active' : 'idle'}`}>
                                          {activeProject && get_active_project_slug_js(activeProject) === ws.slug ? 'Current' : 'Cached'}
                                        </span>
                                      )}
                                    </td>
                                    <td>
                                      <button
                                        className="action-btn wipe"
                                        onClick={() => handleWipeWorkspace(ws.slug, ws.name)}
                                        title="Wipe analytical results for this workspace"
                                      >
                                        <Eraser size={14} /> Wipe
                                      </button>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      </div>

                      {/* Context Refresh */}
                      <div className="maintenance-card">
                        <div className="card-icon">
                          <Clock size={24} color="var(--accent-blue)" />
                        </div>
                        <div className="card-body">
                          <h3>Context Refresh</h3>
                          <p>Clear recent artifacts for {activeProject?.name || 'Active Workspace'}.</p>
                          <div className="purge-grid">
                            {['hour', 'hour2', 'hour4', 'today', 'yesterday'].map((period) => (
                              <div key={period} className="purge-option-card" onClick={() => handlePurgeSession(period)}>
                                <div className={`purge-card-icon ${period === 'yesterday' ? 'amber' : period === 'today' ? 'emerald' : 'blue'}`}>
                                  {period === 'yesterday' ? <Trash2 size={16} /> : period === 'today' ? <Calendar size={16} /> : <Clock size={16} />}
                                </div>
                                <div className="purge-card-info">
                                  <span className="duration">{period.replace('hour', ' Hr ').replace('2', '2').replace('4', '4').replace(' Hr  Hr ', '1 Hr ').trim()}</span>
                                  <span className="action-type">TTL</span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>

                      <div className="maintenance-card danger">
                        <div className="card-icon">
                          <ShieldAlert size={24} />
                        </div>
                        <div className="card-body">
                          <h3>Deep Wipe</h3>
                          <p>Destroy all trace data for global {activeProject?.name}.</p>
                          <button className="btn-danger" onClick={handlePurgeProject} disabled={loading || !activeProject}>
                            <Trash2 size={16} /> Purge Active Trace
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

              )}
            </div>
          </div>
        </div>
      )}
      </GoogleOAuthProvider>
    </ErrorBoundary>
  );
}

export default App;
