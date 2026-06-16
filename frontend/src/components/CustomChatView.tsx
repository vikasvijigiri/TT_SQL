import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Send, Square, Search, Database, MessageSquare,
  Sparkles, Copy, Check, ChevronDown, ChevronUp, AlertCircle
} from 'lucide-react';
import PipelineFlow from './PipelineFlow';

const CUSTOM_STREAM = `${import.meta.env.VITE_API_BASE_URL || '/api'}/custom/stream`;

const SAMPLE_QUESTIONS = [
  'Show me the top 10 records from the main table',
  'What are the column names and types in this database?',
  'Give me a summary of the data',
  'How many total rows are in the database?',
];

const CustomChatView = ({ activeProject, onGoToProjects }) => {
  const [messages, setMessages] = useState([]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId] = useState(() => crypto.randomUUID?.() || Math.random().toString(36).slice(2));
  const abortRef = useRef(null);
  const chatEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (!loading) inputRef.current?.focus();
  }, [loading]);

  const handleStop = useCallback(() => {
    abortRef.current?.abort();
    setLoading(false);
  }, []);

  const handleSend = useCallback(async (q) => {
    if (!q.trim() || loading) return;

    const userMsg = { id: Date.now(), role: 'user', content: q };
    const asstId = Date.now() + 1;
    const asstMsg = {
      id: asstId, role: 'assistant', status: 'Connecting…',
      stageStatuses: {},
      payload: { sql: '', results: [], columns: [], logs: [], business_summary: '' }
    };

    setMessages(prev => [...prev, userMsg, asstMsg]);
    setLoading(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const resp = await fetch(CUSTOM_STREAM, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
        body: JSON.stringify({
          query: q,
          project_id: activeProject?.id || '',
          session_id: sessionId,
          use_rag: true,
        }),
      });

      if (!resp.ok) throw new Error(`Server error ${resp.status}`);

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop();

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const json = line.replace('data: ', '').trim();
          if (!json) continue;
          try {
            const data = JSON.parse(json);
            setMessages(prev => {
              const msgs = [...prev];
              const idx = msgs.findIndex(m => m.id === asstId);
              if (idx === -1) return prev;
              const cur = msgs[idx];
              if (data.type === 'stage') {
                msgs[idx] = {
                  ...cur,
                  stageStatuses: { ...(cur.stageStatuses || {}), [data.stage]: data.status },
                  status: data.status === 'running' ? data.stage.replace(/_/g, ' ') : cur.status,
                };
              } else if (data.type === 'section') {
                msgs[idx] = { ...cur, status: data.message, payload: { ...cur.payload, logs: [...(cur.payload.logs || []), data.message] } };
              } else if (data.type === 'token') {
                msgs[idx] = { ...cur, status: 'Streaming…', payload: { ...cur.payload, business_summary: (cur.payload.business_summary || '') + data.token } };
              } else if (data.type === 'result') {
                msgs[idx] = { ...cur, status: 'Done', payload: { ...cur.payload, sql: data.sql || cur.payload.sql, results: data.results || [], columns: data.columns || [], total_count: data.total_count } };
              } else if (data.type === 'sql') {
                msgs[idx] = { ...cur, payload: { ...cur.payload, sql: data.sql } };
              } else if (data.type === 'error') {
                msgs[idx] = { ...cur, status: 'Error', error: data.message };
              } else if (data.type === 'done') {
                msgs[idx] = { ...cur, status: 'Done' };
              }
              return msgs;
            });
          } catch { /* ignore parse errors */ }
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        setMessages(prev => {
          const msgs = [...prev];
          const idx = msgs.findIndex(m => m.id === asstId);
          if (idx !== -1) msgs[idx] = { ...msgs[idx], status: 'Error', error: err.message };
          return msgs;
        });
      }
    } finally {
      setLoading(false);
    }
  }, [activeProject, loading, sessionId]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (loading) { handleStop(); return; }
    if (query.trim()) { handleSend(query); setQuery(''); }
  };

  return (
    <div className="flex flex-col h-full bg-[#070709]">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3.5 border-b border-[#1a1a22] bg-[#0c0c10] shrink-0">
        <div className="flex items-center gap-3">
          <MessageSquare className="w-4 h-4 text-emerald-400" />
          <span className="text-sm font-bold text-slate-200">Ask Data</span>
          {activeProject && (
            <span className="flex items-center gap-1.5 text-[11px] font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-0.5 rounded-full">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              {activeProject.name}
            </span>
          )}
        </div>
        {!activeProject && (
          <button
            onClick={onGoToProjects}
            className="flex items-center gap-1.5 text-xs text-amber-400 hover:text-amber-300 bg-amber-500/10 border border-amber-500/20 px-3 py-1.5 rounded-lg transition-all font-semibold"
          >
            <Database size={12} /> Connect a Database
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full min-h-[400px] text-center select-none">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-emerald-600/20 to-teal-500/10 border border-emerald-500/20 flex items-center justify-center mb-5 shadow-lg">
              <Sparkles className="w-7 h-7 text-emerald-400" />
            </div>
            <h3 className="text-xl font-bold text-slate-200 mb-2">Ask Anything About Your Data</h3>
            <p className="text-slate-500 text-sm max-w-sm mb-8 leading-relaxed">
              {activeProject
                ? `Connected to "${activeProject.name}". Ask a question in plain English.`
                : 'Connect a database first, then come back to ask questions.'}
            </p>
            {activeProject && (
              <div className="flex flex-col gap-2 w-full max-w-sm">
                {SAMPLE_QUESTIONS.map((q, i) => (
                  <button
                    key={i}
                    onClick={() => { handleSend(q); }}
                    className="px-4 py-2.5 text-left rounded-xl bg-[#0e0e14] border border-[#1e1e2c] hover:border-emerald-500/30 hover:bg-emerald-500/5 text-slate-400 hover:text-slate-200 text-sm transition-all"
                  >
                    {q}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          messages.map(msg => (
            msg.role === 'user' ? (
              <UserMessage key={msg.id} content={msg.content} />
            ) : (
              <AssistantMessage key={msg.id} message={msg} />
            )
          ))
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Input Bar */}
      <div className="px-6 py-4 border-t border-[#1a1a22] bg-[#0c0c10] shrink-0">
        <form onSubmit={handleSubmit} className="flex items-center gap-3 px-4 py-3 rounded-2xl bg-[#12121a] border border-[#1e1e2c] focus-within:border-emerald-500/40 transition-all shadow-lg">
          <Search className="w-4 h-4 text-slate-600 shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder={activeProject ? 'Ask a question about your data…' : 'Connect a database to start asking questions'}
            disabled={!activeProject || (loading)}
            className="flex-1 bg-transparent text-slate-200 text-sm placeholder-slate-600 outline-none disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!activeProject}
            className={`flex items-center justify-center w-8 h-8 rounded-xl transition-all shrink-0 ${loading ? 'bg-rose-600/80 hover:bg-rose-500 text-white' : query.trim() && activeProject ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-md' : 'bg-[#1a1a22] text-slate-600 cursor-not-allowed'}`}
          >
            {loading ? <Square size={14} fill="currentColor" strokeWidth={0} /> : <Send size={14} />}
          </button>
        </form>
        <p className="text-center text-[10px] text-slate-700 mt-2 font-mono">CustomSQL · NL-to-SQL Engine</p>
      </div>
    </div>
  );
};

const UserMessage = ({ content }) => (
  <div className="flex justify-end">
    <div className="max-w-[75%] px-4 py-3 rounded-2xl rounded-tr-sm bg-emerald-600/20 border border-emerald-500/20 text-slate-200 text-sm leading-relaxed">
      {content}
    </div>
  </div>
);

const AssistantMessage = ({ message }) => {
  const { status, error, payload, stageStatuses } = message;
  const [showSql, setShowSql] = useState(false);
  const [showLogs, setShowLogs] = useState(false);
  const [copied, setCopied] = useState(false);
  const isDone = status === 'Done';
  const isError = status === 'Error' || !!error;
  const isThinking = !isDone && !isError;
  const hasPipeline = stageStatuses && Object.keys(stageStatuses).length > 0;

  const copySql = () => {
    if (!payload?.sql) return;
    navigator.clipboard.writeText(payload.sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex justify-start">
      <div className="max-w-[90%] w-full space-y-3">
        {/* Status indicator */}
        {isThinking && (
          <div className="flex items-center gap-2 text-xs text-slate-500 font-mono">
            <div className="flex gap-0.5">
              {[0, 0.1, 0.2].map(d => (
                <span key={d} className="w-1.5 h-1.5 rounded-full bg-emerald-400/60 animate-bounce" style={{ animationDelay: `${d}s` }} />
              ))}
            </div>
            <span>{status}</span>
          </div>
        )}

        {/* Error */}
        {isError && (
          <div className="flex items-start gap-2 px-4 py-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-sm">
            <AlertCircle size={15} className="shrink-0 mt-0.5" />
            <span>{error || 'An error occurred.'}</span>
          </div>
        )}

        {/* Business Summary */}
        {payload?.business_summary && (
          <div className="px-4 py-3 rounded-xl bg-[#0e0e14] border border-[#1e1e2c] text-slate-300 text-sm leading-relaxed whitespace-pre-wrap">
            {payload.business_summary}
          </div>
        )}

        {/* SQL Block */}
        {payload?.sql && (
          <div className="rounded-xl bg-[#0a0a12] border border-[#1e1e2c] overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2 border-b border-[#1a1a22]">
              <button
                onClick={() => setShowSql(s => !s)}
                className="flex items-center gap-1.5 text-xs font-mono font-bold text-slate-400 hover:text-slate-200 transition-all"
              >
                {showSql ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                SQL Query
              </button>
              <button onClick={copySql} className="flex items-center gap-1 text-[11px] text-slate-600 hover:text-emerald-400 transition-all">
                {copied ? <><Check size={11} /> Copied</> : <><Copy size={11} /> Copy</>}
              </button>
            </div>
            {showSql && (
              <pre className="px-4 py-3 text-xs font-mono text-emerald-300/90 overflow-x-auto leading-relaxed">
                {payload.sql}
              </pre>
            )}
          </div>
        )}

        {/* Results Table */}
        {payload?.results?.length > 0 && (
          <ResultsTable
            results={payload.results}
            columns={payload.columns}
            total={payload.total_count}
          />
        )}

        {/* Execution Logs */}
        {payload?.logs?.length > 0 && (
          <div>
            <button
              onClick={() => setShowLogs(s => !s)}
              className="flex items-center gap-1.5 text-[11px] text-slate-600 hover:text-slate-400 transition-all font-mono mb-1"
            >
              {showLogs ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
              {payload.logs.length} execution step{payload.logs.length !== 1 ? 's' : ''}
            </button>
            {showLogs && (
              <div className="space-y-0.5 pl-2 border-l border-[#1e1e2c]">
                {payload.logs.map((log, i) => (
                  <div key={i} className="text-[11px] font-mono text-slate-600">{log}</div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

const ResultsTable = ({ results, columns, total }) => {
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 20;
  const totalPages = Math.ceil(results.length / PAGE_SIZE);
  const visible = results.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const hasMore = total && total > results.length;

  return (
    <div className="rounded-xl bg-[#0a0a12] border border-[#1e1e2c] overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-[#1a1a22]">
        <span className="text-xs font-mono font-bold text-slate-400">
          Results · {results.length}{hasMore ? `+ of ${total}` : ''} rows
        </span>
      </div>
      <div className="overflow-x-auto max-h-72">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-[#1a1a22]">
              {columns.map(col => (
                <th key={col} className="text-left px-3 py-2 text-[10px] font-bold text-slate-500 uppercase tracking-wider whitespace-nowrap bg-[#0c0c10]">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((row, i) => (
              <tr key={i} className="border-b border-[#131318] hover:bg-white/[0.02] transition-colors">
                {columns.map(col => (
                  <td key={col} className="px-3 py-2 text-slate-300 font-mono whitespace-nowrap max-w-[200px] truncate">
                    {row[col] === null ? <span className="text-slate-600 italic">NULL</span> : String(row[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-2 border-t border-[#1a1a22] text-[11px] text-slate-600">
          <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0} className="px-2 py-1 rounded bg-[#1a1a22] disabled:opacity-30 hover:text-slate-300 transition-all">Prev</button>
          <span>Page {page + 1} / {totalPages}</span>
          <button onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page === totalPages - 1} className="px-2 py-1 rounded bg-[#1a1a22] disabled:opacity-30 hover:text-slate-300 transition-all">Next</button>
        </div>
      )}
    </div>
  );
};

export default CustomChatView;
