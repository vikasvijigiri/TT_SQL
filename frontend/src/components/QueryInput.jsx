import React, { useState } from 'react';
import { Send, Search, Square } from 'lucide-react';
import './QueryInput.css';

const QueryInput = ({ onSend, onStop, loading }) => {
  const [query, setQuery] = useState('');
  const inputRef = React.useRef(null);

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

  return (
    <div className="query-input-container">
      <form onSubmit={handleSubmit} className="query-form glass-panel">
        <div className="input-icon">
          <Search size={20} color="var(--text-secondary)" />
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
