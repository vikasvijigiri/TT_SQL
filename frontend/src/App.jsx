import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Zap, RefreshCw, Send, Search, Terminal, Brain, Trash2 } from 'lucide-react';
import QueryInput from './components/QueryInput';
import AgentLogs from './components/AgentLogs';
import ResultDisplay from './components/ResultDisplay';
import DatasetUpload from './components/DatasetUpload';
import EnvUpload from './components/EnvUpload';
import DatasetView from './components/DatasetView';
import './App.css';

const API_BASE_URL = 'http://localhost:8000';

function App() {
  const [loading, setLoading] = useState(false);
  const [dbConnected, setDbConnected] = useState(null);
  const [currentStage, setCurrentStage] = useState('');
  const [messages, setMessages] = useState([]);
  const [selectedDataset, setSelectedDataset] = useState('sample.jsonl');
  const [isPrepping, setIsPrepping] = useState(false);
  const [prepStatus, setPrepStatus] = useState('Ready');
  const [currentView, setCurrentView] = useState('chat'); // 'chat' or 'dataset'
  const [showRawLogs, setShowRawLogs] = useState({}); // Tracking per messageId

  const chatEndRef = useRef(null);

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, currentStage]);

  const checkDbStatus = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/health/db`);
      setDbConnected(response.data.connected);
    } catch (err) {
      console.error('Failed to check DB status:', err);
      setDbConnected(false);
    }
  };

  useEffect(() => {
    checkDbStatus();
  }, []);

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

    // Add User Message
    const userMessage = { id: Date.now(), role: 'user', content: query };
    setMessages(prev => [...prev, userMessage]);

    // Add Placeholder Assistant Message
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
      console.log("nQuire: Starting stream fetch for", `${API_BASE_URL}/api/stream`);
      const response = await fetch(`${API_BASE_URL}/api/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: query,
          db_name: 'acme-chatbot',
          dataset_name: selectedDataset,
          use_rag: true
        }),
      });

      console.log("nQuire: Fetch response status:", response.status);
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

      const reader = response.body.getReader();
      console.log("nQuire: Reader obtained, protocol check complete.");
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
                const stage = data.message.replace('💠', '').trim();
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
                      payload: {
                        ...newMessages[idx].payload,
                        instance_id: data.instance_id
                      }
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

  return (
    <div className={`app-container ${messages.length === 0 ? 'empty-state' : 'chat-state'}`}>
      <header className="app-header glass-panel">
        <div className="header-left">
          <div className="logo-icon">
            <Zap size={24} color="var(--accent-blue)" />
          </div>
          <div className="logo-text">
            <h1>nQuire</h1>
            <span className="subtitle">AI Business Intelligence</span>
          </div>
        </div>

        <div className="header-right">
          <EnvUpload onUploadSuccess={checkDbStatus} apiUrl={`${API_BASE_URL}/api/data/upload-env`} />
          <DatasetUpload 
            currentDataset={selectedDataset} 
            onUploadSuccess={(name) => setSelectedDataset(name)} 
            onViewDataset={() => setCurrentView('dataset')}
            apiUrl={`${API_BASE_URL}/api/data/upload-dataset`}
          />
          <div className={`status-badge ${dbConnected === true ? 'online' : dbConnected === false ? 'offline' : ''}`}>
            <span className="status-dot"></span>
            <span className="status-text">{dbConnected === true ? 'DB Connected' : dbConnected === false ? 'DB Offline' : 'Checking DB...'}</span>
          </div>
          <button 
            className={`icon-btn ${loading && currentStage === 'Checking Health' ? 'loading' : ''}`} 
            title="Check DB Health" 
            onClick={checkDbStatus}
          >
            <RefreshCw size={18} className={loading && currentStage === 'Checking Health' ? 'spin' : ''} />
          </button>
          
          <div className="status-separator"></div>

          <div className={`status-pill ${isPrepping ? 'active' : ''} ${prepStatus.toLowerCase()} ${prepStatus === 'Ready' ? 'hidden' : ''}`}>
            <span className="pulse-dot"></span>
            <span className="status-label">{prepStatus}</span>
          </div>
          
          <button 
            className={`icon-btn ${isPrepping ? 'loading' : ''}`} 
            title="Inject Knowledge (RAG)" 
            onClick={() => handleConnectDB(false)}
            disabled={isPrepping}
          >
            <Brain size={18} className={isPrepping ? 'pulse-glow' : ''} />
            <span style={{ marginLeft: '6px', fontSize: '12px', fontWeight: '600' }}>Inject</span>
          </button>

          <button 
            className={`icon-btn delete-btn ${isPrepping ? 'loading' : ''}`} 
            title="Delete Vector Collection" 
            onClick={handleDeleteCollection}
            disabled={isPrepping}
            style={{ color: 'var(--accent-red, #ff4d4f)' }}
          >
            <Trash2 size={18} />
          </button>
        </div>
      </header>

      <main className="chat-area">
        <div className="message-list">
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
                  <span onClick={() => handleSendQuery("How many batches had OTIF issues last month?")}>"How many batches had OTIF issues last month?"</span>
                  <span onClick={() => handleSendQuery("Show me the top 5 products by delay")}>"Show me the top 5 products by delay"</span>
                </div>
              </div>
            </div>
          ) : (
            // Chat History
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

                      {/* Per-message Toggle Switch */}
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
      </main>

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
      {currentView === 'dataset' && (
        <DatasetView onBack={() => setCurrentView('chat')} />
      )}
    </div>
  );
}

export default App;
