import React, { useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeRaw from 'rehype-raw';
import './AgentLogs.css';

const AgentLogs = ({ historyLog, loadingHistory }) => {
    const scrollRef = useRef(null);

    // Auto-scroll to bottom of logs when content updates
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [historyLog]);

    return (
        <div className="agent-logs glass-panel">
            <div className="logs-header">
                <h3>Engine Reasoning</h3>
            </div>
            
            <div className="logs-container" ref={scrollRef}>
                {loadingHistory && !historyLog ? (
                    <div className="logs-loading">
                        <div className="spinner-mini"></div>
                        <span>Acquiring system logs...</span>
                    </div>
                ) : (
                    <div className="history-log-viewer">
                        <ReactMarkdown rehypePlugins={[rehypeRaw]}>
                            {historyLog || "No logs available. Start an analysis to see the engine reasoning."}
                        </ReactMarkdown>
                    </div>
                )}
            </div>
        </div>
    );
};

export default React.memo(AgentLogs);
