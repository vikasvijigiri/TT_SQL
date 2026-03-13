import React from 'react';
import { ArrowLeft, FileJson, Copy, Check } from 'lucide-react';
import { useState } from 'react';

const DatasetView = ({ onBack }) => {
    const [copied, setCopied] = useState(false);
    
    const sampleJson = {
        "instance_id": "q001",
        "db": "acme-chatbot",
        "question": "What is the overall performance for this month?",
        "external_knowledge": null
    };

    const handleCopy = () => {
        navigator.clipboard.writeText(JSON.stringify(sampleJson, null, 2));
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="dataset-view-page">
            <div className="view-header glass-panel">
                <button className="back-btn" onClick={onBack}>
                    <ArrowLeft size={20} />
                    <span>Back to Chat</span>
                </button>
                <div className="view-title">
                    <FileJson size={20} color="var(--accent-blue)" />
                    <h1>Dataset Format Reference</h1>
                </div>
                <div style={{ width: '120px' }}></div> {/* Spacer */}
            </div>

            <main className="view-content">
                <div className="content-card glass-panel">
                    <div className="card-header">
                        <div className="format-badge">JSONL (JSON Lines)</div>
                        <button className="copy-btn" onClick={handleCopy}>
                            {copied ? <Check size={16} color="#10b981" /> : <Copy size={16} />}
                            <span>{copied ? 'Copied!' : 'Copy Example'}</span>
                        </button>
                    </div>
                    
                    <div className="json-container">
                        <pre className="code-block">
                            <code>{JSON.stringify(sampleJson, null, 2)}</code>
                        </pre>
                    </div>

                    <div className="format-explanation">
                        <h3>Requirement Details</h3>
                        <ul>
                            <li><strong>instance_id</strong>: Unique identifier for the question (e.g., q001, q002).</li>
                            <li><strong>db</strong>: The target database/schema name (e.g., "acme-chatbot").</li>
                            <li><strong>question</strong>: The natural language question to be processed.</li>
                            <li><strong>external_knowledge</strong>: Additional context if any (set to <code>null</code> if not needed).</li>
                        </ul>
                        <div className="important-note">
                            <p><strong>Note:</strong> Your upload must be a <code>.jsonl</code> file where each line is a single JSON object like the one above.</p>
                        </div>
                    </div>
                </div>
            </main>

        </div>
    );
};

export default DatasetView;
