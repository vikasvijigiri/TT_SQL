import React, { useState, useRef } from 'react';
import { Settings, Upload, Check, AlertCircle } from 'lucide-react';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8001';

const EnvUpload = ({ onUploadSuccess, apiUrl }) => {
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(false);
    const fileInputRef = useRef(null);

    const handleFileChange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        // More lenient check for .env files
        if (!file.name.includes('env')) {
            setError('Please upload a .env file');
            return;
        }

        setUploading(true);
        setError(null);
        setSuccess(false);

        const formData = new FormData();
        formData.append('file', file);

        try {
            const url = apiUrl || `${API_BASE_URL}/api/data/upload-env`;
            await axios.post(url, formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
            });

            setSuccess(true);
            if (onUploadSuccess) onUploadSuccess();
            setTimeout(() => setSuccess(false), 3000);
        } catch (err) {
            console.error('Upload failed:', err);
            setError(err.response?.data?.detail || 'Upload failed');
        } finally {
            setUploading(false);
            if (fileInputRef.current) fileInputRef.current.value = '';
        }
    };

    return (
        <div className="env-upload-container">
            <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileChange}
                style={{ display: 'none' }}
            />
            
            <button 
                className={`icon-btn ${uploading ? 'loading' : ''} ${success ? 'success' : ''}`}
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                title="Upload .env config"
            >
                {success ? <Check size={18} color="#10b981" /> : <Settings size={18} />}
            </button>

            {error && (
                <div className="upload-error-tooltip">
                    <AlertCircle size={12} />
                    <span>{error}</span>
                </div>
            )}

            <style jsx>{`
                .env-upload-container {
                    position: relative;
                    display: flex;
                    align-items: center;
                }
                .upload-error-tooltip {
                    position: absolute;
                    top: 100%;
                    right: 0;
                    margin-top: 8px;
                    background: #fee2e2;
                    color: #ef4444;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 10px;
                    white-space: nowrap;
                    z-index: 1000;
                    display: flex;
                    align-items: center;
                    gap: 4px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                    border: 1px solid #fecaca;
                }
                @keyframes spin {
                    to { transform: rotate(360deg); }
                }
                .loading svg {
                    animation: spin 1s linear infinite;
                }
            `}</style>
        </div>
    );
};

export default EnvUpload;
