import React, { useState, useRef } from 'react';
import { Upload, FileText, Check, AlertCircle } from 'lucide-react';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

const DatasetUpload = ({ onUploadSuccess, currentDataset, onViewDataset }) => {
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
                        <button 
                            className="dataset-name-btn" 
                            onClick={onViewDataset}
                            title="View dataset format"
                        >
                            <span className="dataset-name">{currentDataset}</span>
                        </button>
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

        </div>
    );
};

export default DatasetUpload;
