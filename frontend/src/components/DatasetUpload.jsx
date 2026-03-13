import React, { useState, useRef } from 'react';
import { Upload, FileText, Check, AlertCircle } from 'lucide-react';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

const DatasetUpload = ({ onUploadSuccess, currentDataset }) => {
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState(null);
    const fileInputRef = useRef(null);

    const handleFileChange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        if (!file.name.endsWith('.jsonl') && !file.name.endsWith('.json')) {
            setError('Please upload a .jsonl or .json file');
            return;
        }

        setUploading(true);
        setError(null);

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await axios.post(`${API_BASE_URL}/api/upload-dataset`, formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
            });

            if (response.data.status === 'success') {
                onUploadSuccess(response.data.filename);
            }
        } catch (err) {
            console.error('Upload failed:', err);
            setError(err.response?.data?.detail || 'Upload failed. Please try again.');
        } finally {
            setUploading(false);
            // Reset input
            if (fileInputRef.current) fileInputRef.current.value = '';
        }
    };

    return (
        <div className="dataset-upload-container">
            <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileChange}
                accept=".jsonl,.json"
                style={{ display: 'none' }}
            />
            
            <div className="dataset-controls">
                <button 
                    className={`upload-trigger-btn ${uploading ? 'loading' : ''}`}
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploading}
                    title="Upload new dataset"
                >
                    {uploading ? (
                        <div className="spinner-tiny"></div>
                    ) : (
                        <Upload size={18} />
                    )}
                    <span>{uploading ? 'Uploading...' : 'Upload Dataset'}</span>
                </button>

                {currentDataset && (
                    <div className="current-dataset-status glass-panel">
                        <FileText size={14} color="var(--accent-blue)" />
                        <span className="dataset-name">{currentDataset}</span>
                        <Check size={14} color="#10b981" />
                    </div>
                )}
            </div>

            {error && (
                <div className="upload-error-msg">
                    <AlertCircle size={14} />
                    <span>{error}</span>
                </div>
            )}

            <style jsx>{`
                .dataset-upload-container {
                    display: flex;
                    flex-direction: column;
                    gap: 8px;
                }
                .dataset-controls {
                    display: flex;
                    align-items: center;
                    gap: 12px;
                }
                .upload-trigger-btn {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    padding: 8px 16px;
                    background: rgba(var(--accent-blue-rgb), 0.1);
                    border: 1px solid rgba(var(--accent-blue-rgb), 0.2);
                    border-radius: 8px;
                    color: var(--accent-blue);
                    font-size: 13px;
                    font-weight: 500;
                    cursor: pointer;
                    transition: all 0.2s ease;
                }
                .upload-trigger-btn:hover:not(:disabled) {
                    background: rgba(var(--accent-blue-rgb), 0.15);
                    transform: translateY(-1px);
                }
                .upload-trigger-btn:active:not(:disabled) {
                    transform: translateY(0);
                }
                .upload-trigger-btn:disabled {
                    opacity: 0.6;
                    cursor: not-allowed;
                }
                .current-dataset-status {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    padding: 8px 12px;
                    border-radius: 8px;
                    font-size: 12px;
                    color: var(--text-secondary);
                    background: rgba(255, 255, 255, 0.03);
                }
                .dataset-name {
                    max-width: 150px;
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }
                .upload-error-msg {
                    display: flex;
                    align-items: center;
                    gap: 6px;
                    color: #ef4444;
                    font-size: 11px;
                    padding: 4px 8px;
                }
                .spinner-tiny {
                    width: 14px;
                    height: 14px;
                    border: 2px solid rgba(var(--accent-blue-rgb), 0.3);
                    border-top-color: var(--accent-blue);
                    border-radius: 50%;
                    animation: spin 0.8s linear infinite;
                }
                @keyframes spin {
                    to { transform: rotate(360deg); }
                }
            `}</style>
        </div>
    );
};

export default DatasetUpload;
