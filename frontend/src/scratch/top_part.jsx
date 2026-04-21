import React, { useState, useEffect, useRef } from 'react';
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
import { API_BASE_URL } from './config';
import './App.css';

function App() {
  const [loading, setLoading] = useState(false);
  const [isCheckingDb, setIsCheckingDb] = useState(false);
  const [dbConnected, setDbConnected] = useState(null);
  const [executionHistory, setExecutionHistory] = useState("");
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [currentStage, setCurrentStage] = useState('');
  const [messages, setMessages] = useState([]);
  const [selectedDataset, setSelectedDataset] = useState('sample.jsonl');
  const [isPrepping, setIsPrepping] = useState(false);
  const [prepStatus, setPrepStatus] = useState('Ready');
  const [currentView, setCurrentView] = useState('projects');
  const [showRawLogs, setShowRawLogs] = useState({});
  const [lastInstanceId, setLastInstanceId] = useState(null);
  const [activeProject, setActiveProject] = useState(null);
  const [sampleQuestions, setSampleQuestions] = useState([]);
  const [isLoadingSamples, setIsLoadingSamples] = useState(false);
  const [storageStats, setStorageStats] = useState(null);

  const get_active_project_slug_js = (project) => {
    if (!project) return 'default_project';
    return project.name.toLowerCase().replace(/[^a-z0-9]/g, '_');
  };

  const chatEndRef = useRef(null);

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, currentStage]);

  useEffect(() => {
    checkDbStatus();
    fetchActiveProject();
  }, []);

  useEffect(() => {
    if (activeProject?.id) {
      fetchSampleQuestions(activeProject.id);
    } else {
      setSampleQuestions([
        "How many batches had OTIF issues last month?",
        "Show me the top 5 products by delay"
      ]);
    }
  }, [activeProject]);

  useEffect(() => {
    if (currentView === 'maintenance') {
      fetchStorageStats();
    }
  }, [currentView, activeProject]);

  const fetchStorageStats = async () => {
    try {
      const res = await axios.get(`${API_BASE_URL}/api/data/storage/workspaces`);
      setStorageStats(res.data);
    } catch (err) {
      console.error("Failed to fetch storage stats", err);
    }
  };

  const handleWipeWorkspace = async (slug, projectName) => {
    if (!window.confirm(`CRITICAL: This will permanently delete ALL results (SQL, CSV, logs) for the workspace "${projectName || slug}". This action cannot be undone. Proceed?`)) return;

    try {
      setLoading(true);
      await axios.delete(`${API_BASE_URL}/api/data/cleanup/workspace/${slug}`);
      if (activeProject && get_active_project_slug_js(activeProject) === slug) {
        setExecutionHistory("");
        setMessages([]);
        setLastInstanceId(null);
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
      const res = await axios.get(`${API_BASE_URL}/api/projects/active`);
      if (res.data.project) {
        setActiveProject(res.data.project);
      } else {
        setActiveProject(null);
      }
    } catch (err) {
      console.error("Failed to fetch active project", err);
    }
  };

  const fetchSampleQuestions = async (projectId) => {
    setIsLoadingSamples(true);
    try {
      const res = await axios.get(`${API_BASE_URL}/api/projects/${projectId}/samples`);
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
      const response = await axios.get(`${API_BASE_URL}/api/health/db`);
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
      const response = await fetch(`${API_BASE_URL}/api/prep/run?force=${force}`, {
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

  const fetchExecutionHistory = async () => {
    setLoadingHistory(true);
    try {
      const response = await axios.get(`${API_BASE_URL}/api/data/logs/history`);
      setExecutionHistory(response.data.content);
    } catch (err) {
      console.error("Failed to fetch execution history:", err);
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleClearCache = async () => {
    if (!lastInstanceId) {
      alert("No active query to clear from cache.");
      return;
    }

    if (!window.confirm(`Are you sure you want to clear the cache for query ${lastInstanceId}?`)) return;

    try {
      const response = await axios.delete(`${API_BASE_URL}/api/data/cache/${lastInstanceId}`);
      if (response.data.status === 'success') {
        alert(`Cache cleared successfully for ${lastInstanceId}.`);
        fetchExecutionHistory();
      }
    } catch (err) {
      console.error("Failed to clear cache:", err);
      alert("Error clearing cache: " + err.message);
    }
  };

  const handlePurgeProject = async () => {
    if (!activeProject) return;
    if (!window.confirm(`WARNING: This will permanently delete ALL analytical results (SQL, CSV, logs) for the project "${activeProject.name}". This action cannot be undone. Proceed?`)) return;

    try {
      setLoading(true);
      await axios.delete(`${API_BASE_URL}/api/data/cleanup/project`);
      setExecutionHistory("");
      setMessages([]);
      setLastInstanceId(null);
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
    const periodLabels = { hour: 'Last Hour', today: 'Today', yesterday: 'Yesterday' };
    if (!window.confirm(`Clear session results for: ${periodLabels[period]}?`)) return;

    try {
      setLoading(true);
      const res = await axios.delete(`${API_BASE_URL}/api/data/cleanup/session?period=${period}`);
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

  // Real-time log polling while query is active
  useEffect(() => {
    let interval;
    if (loading) {
      interval = setInterval(() => {
        fetchExecutionHistory();
      }, 3000); // Poll every 3 seconds
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [loading]);

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

    try {
      const response = await fetch(`${API_BASE_URL}/api/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query,
          db_name: '',
          dataset_name: selectedDataset,
          use_rag: true
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
                setLastInstanceId(data.instance_id);
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
      console.error(err);
      setMessages(prev => prev.map(m =>
        m.id === assistantMessageId ? { ...m, type: 'error', content: err.message, status: null } : m
      ));
      setLoading(false);
      setCurrentStage('');
    }
  };

  const navItems = [
    { id: 'projects', icon: FolderKanban, label: 'Projects' },
    { id: 'chat', icon: MessageSquare, label: 'Ask Data' },
    { id: 'database', icon: Database, label: 'Data Explorer' },
    { id: 'maintenance', icon: HardDrive, label: 'Storage' },
  ];

  return (
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
              onClick={() => setCurrentView(item.id)}
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
