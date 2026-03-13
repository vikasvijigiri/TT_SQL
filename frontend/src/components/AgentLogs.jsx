import React, { useEffect, useRef } from 'react';
import './AgentLogs.css';

const AgentLogs = ({ logs }) => {
    const scrollRef = useRef(null);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [logs]);

    return (
        <div className="agent-logs glass-panel">
            <div className="logs-header">
                <h3>Pipeline Trace</h3>
            </div>
            <div className="logs-container" ref={scrollRef}>
                {logs.map((log, index) => (
                    <div key={index} className="log-entry">
                        {/* Using dangerouslySetInnerHTML to support rich formatting and colors in the trace */}
                        <span className="log-text" dangerouslySetInnerHTML={{ __html: log }} />
                    </div>
                ))}
                {logs.length === 0 && (
                    <div className="empty-logs">Waiting for query...</div>
                )}
            </div>
        </div>
    );
};

export default React.memo(AgentLogs);
