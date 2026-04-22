import React, { useState, useRef } from 'react';
import { Send, Search, Square, Plus } from 'lucide-react';
import './QueryInput.css';

const QueryInput = ({ onSend, onStop, onBulkUpload, loading }) => {
  const [query, setQuery] = useState('');
  const inputRef = useRef(null);
  const fileInputRef = useRef(null);

  // Auto-focus the search bar when execution finishes
  React.useEffect(() => {
    if (!loading && inputRef.current) {
      inputRef.current.focus();
    }
  }, [loading]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (loading) {
      onStop?.();
      return;
    }
    
    if (query.trim()) {
      onSend(query);
      setQuery('');
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file && onBulkUpload) {
      onBulkUpload(file);
      // Reset input so the same file can be uploaded again if needed
      e.target.value = '';
    }
  };

  return (
    <div className="query-input-container">
      <form onSubmit={handleSubmit} className="query-form glass-panel">
        <div className="input-actions-left">
          <button 
            type="button" 
            className="bulk-btn"
            onClick={() => fileInputRef.current?.click()}
            title="Bulk Processing (Upload .jsonl)"
            disabled={loading}
          >
            <Plus size={18} />
          </button>
          <input 
            type="file" 
            ref={fileInputRef} 
            onChange={handleFileChange} 
            style={{ display: 'none' }} 
            accept=".jsonl"
          />
          <div className="divider-v" />
          <div className="input-icon">
            <Search size={20} color="var(--text-secondary)" />
          </div>
        </div>
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask a question about your data..."
          className="main-input"
          disabled={loading}
        />
        <button 
          type="submit" 
          className={`send-btn ${loading ? 'stop-btn' : ''}`}
        >
          {loading ? (
            <div className="stop-icon-wrapper">
              <Square size={16} fill="currentColor" strokeWidth={0} />
            </div>
          ) : (
            <Send size={18} />
          )}
        </button>
      </form>
    </div>
  );
};

export default React.memo(QueryInput);
