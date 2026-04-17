import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  Zap, RefreshCw, Brain, Trash2, Database,
  FolderKanban, MessageSquare
} from 'lucide-react';
import QueryInput from './components/QueryInput';
import AgentLogs from './components/AgentLogs';
import ResultDisplay from './components/ResultDisplay';
import DatasetUpload from './components/DatasetUpload';
import EnvUpload from './components/EnvUpload';
import DatasetView from './components/DatasetView';
import DatabaseView from './components/DatabaseView';
import ProjectsScreen from './components/ProjectsScreen';
import './App.css';

const API_BASE_URL = 'http://localhost:8001';

function App() {
  const [loading, setLoading] = useState(false);
  const [isCheckingDb, setIsCheckingDb] = useState(false);
  const [dbConnected, setDbConnected] = useState(null);
  const [currentStage, setCurrentStage] = useState('');
  const [messages, setMessages] = useState([]);
  const [selectedDataset, setSelectedDataset] = useState('sample.jsonl');
  const [isPrepping, setIsPrepping] = useState(false);
  const [prepStatus, setPrepStatus] = useState('Ready');
  const [currentView, setCurrentView] = useState('projects');
  const [showRawLogs, setShowRawLogs] = useState({});
  const [activeProject, setActiveProject] = useState(null);
  const [sampleQuestions, setSampleQuestions] = useState([]);
  const [isLoadingSamples, setIsLoadingSamples] = useState(false);

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
            <EnvUpload onUploadSuccess={checkDbStatus} apiUrl={`${API_BASE_URL}/api/data/upload-env`} />
            <DatasetUpload
              currentDataset={selectedDataset}
              onUploadSuccess={(name) => setSelectedDataset(name)}
              onViewDataset={() => setCurrentView('dataset')}
              apiUrl={`${API_BASE_URL}/api/data/upload-dataset`}
            />
            <div className={`status-indicator ${dbConnected === true ? 'connected' : dbConnected === false ? 'disconnected' : ''}`} title={activeProject ? `Connected to ${activeProject.name}` : "No database connected"}>
              <span className="status-dot-sm" />
              <span>
                {isCheckingDb ? 'Checking...' : (activeProject ? activeProject.name : 'No Source')}
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
          {/* Chat View */}
          {currentView === 'chat' && (
            <div className="chat-view">
              <div className="chat-area">
                <div className="message-list">
                  {!activeProject && (
                    <div className="no-project-banner">
                      <span>No project connected. Set up a data source to start querying.</span>
                      <button onClick={() => setCurrentView('projects')}>Go to Projects</button>
                    </div>
                  )}

                  {messages.length === 0 ? (
                    <div className="hero-section">
                      <div className="hero-content">
                        <div className="pulse-icon-wrapper">
                          <Zap size={56} color="var(--accent-blue)" className="pulse" />
                        </div>
                        <h2>What would you like to know?</h2>
                        <p>Ask a question about your data to uncover insights instantly.</p>
                        <div className="centered-search-wrapper">
                          <QueryInput onSend={handleSendQuery} loading={loading} />
                        </div>
                        <div className="suggestion-chips">
                          {isLoadingSamples ? (
                            <div className="samples-loading">
                              <RefreshCw size={14} className="spin" />
                              <span>Suggesting relevant questions...</span>
                            </div>
                          ) : (
                            sampleQuestions.map((q, idx) => (
                              <span key={idx} onClick={() => handleSendQuery(q)}>"{q}"</span>
                            ))
                          )}
                        </div>
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
                                      onChange={() => setShowRawLogs(prev => ({ ...prev, [msg.id]: !prev[msg.id] }))}
                                    />
                                    <span className="premium-slider"></span>
                                  </label>
                                  <span className={`switch-label ${showRawLogs[msg.id] ? 'active' : ''}`}>Logs</span>
                                </div>
                              </div>

                              {showRawLogs[msg.id] && msg.payload?.logs && msg.payload.logs.length > 0 && (
                                <div className="stages-history" style={{ marginBottom: '1.5rem' }}>
                                  <AgentLogs logs={msg.payload.logs} />
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
                                />
                              )}

                              {msg.type === 'error' && (
                                <div className="error-display">
                                  <div className="error-header">EXECUTION FAILED</div>
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

              {messages.length > 0 && (
                <footer className="footer-bar animated-footer">
                  <div className="input-wrapper">
                    <QueryInput onSend={handleSendQuery} loading={loading} />
                    <p className="footer-disclaimer">
                      nQuire uses AI to generate queries. Always verify results for critical business decisions.
                    </p>
                  </div>
                </footer>
              )}
            </div>
          )}

          {/* Projects View */}
          {currentView === 'projects' && (
            <ProjectsScreen
              onProjectConnected={(project) => {
                setActiveProject(project);
                checkDbStatus();
              }}
              onProjectDeleted={(id) => {
                if (id === 'all' || (activeProject && activeProject.id === id)) {
                  setActiveProject(null);
                  setDbConnected(false);
                }
              }}
              onStartChat={() => setCurrentView('chat')}
            />
          )}

          {/* Database View */}
          {currentView === 'database' && (
            <DatabaseView onBack={() => setCurrentView('chat')} />
          )}

          {/* Dataset View */}
          {currentView === 'dataset' && (
            <DatasetView onBack={() => setCurrentView('chat')} />
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
