import React, { useState } from 'react';
import { Send, Search } from 'lucide-react';
import './QueryInput.css';

const QueryInput = ({ onSend, loading }) => {
  const [query, setQuery] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim() && !loading) {
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
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask a question about your data..."
          className="main-input"
          disabled={loading}
        />
        <button type="submit" className={`send-btn ${loading ? 'loading' : ''}`} disabled={loading}>
          {loading ? <div className="spinner" /> : <Send size={18} />}
        </button>
      </form>
    </div>
  );
};

export default React.memo(QueryInput);
