import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Zap, RefreshCw, Send, Search, Terminal } from 'lucide-react';
import QueryInput from './components/QueryInput';
import AgentLogs from './components/AgentLogs';
import ResultDisplay from './components/ResultDisplay';
import './App.css';

const API_BASE_URL = 'http://localhost:8000';

function App() {
  const [loading, setLoading] = useState(false);
  const [dbConnected, setDbConnected] = useState(null);
  const [currentStage, setCurrentStage] = useState('');
  const [messages, setMessages] = useState([]);

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
      const response = await fetch(`${API_BASE_URL}/api/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: query,
          db_name: 'acme-chatbot'
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
          <div className={`status-badge ${dbConnected === true ? 'online' : dbConnected === false ? 'offline' : ''}`}>
            <span className="status-dot"></span>
            <span className="status-text">{dbConnected === true ? 'DB Connected' : dbConnected === false ? 'DB Offline' : 'Checking DB...'}</span>
          </div>
          <button className="icon-btn" title="Refresh Connection" onClick={checkDbStatus}>
            <RefreshCw size={18} />
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

                      {/* Instance ID badge removed per user request */}

                      {msg.payload?.logs && msg.payload.logs.length > 0 && (
                        <div className="stages-history" style={{ marginBottom: '1.5rem' }}>
                          <AgentLogs logs={msg.payload.logs} />
                        </div>
                      )}

                      {msg.type === 'result' && (
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
    </div>
  );
}

export default App;
