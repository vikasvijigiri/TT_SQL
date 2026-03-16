import React, { useState, useEffect } from 'react';
import { ArrowLeft, Database, Table as TableIcon, Key, Link as LinkIcon, AlertCircle } from 'lucide-react';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

const DatabaseView = ({ onBack }) => {
    const [schema, setSchema] = useState({ tables: [], columns: {}, foreign_keys: [] });
    const [loadingSchema, setLoadingSchema] = useState(true);
    const [error, setError] = useState(null);
    
    const [selectedTable, setSelectedTable] = useState(null);
    const [previewData, setPreviewData] = useState({ columns: [], rows: [] });
    const [loadingPreview, setLoadingPreview] = useState(false);

    useEffect(() => {
        fetchSchema();
    }, []);

    const fetchSchema = async () => {
        setLoadingSchema(true);
        setError(null);
        try {
            const response = await axios.get(`${API_BASE_URL}/api/data/schema`);
            setSchema(response.data);
            if (response.data.tables && response.data.tables.length > 0) {
                handleSelectTable(response.data.tables[0], response.data.foreign_keys);
            }
        } catch (err) {
            console.error('Failed to fetch schema:', err);
            setError(err.response?.data?.detail || 'Failed to load database schema.');
        } finally {
            setLoadingSchema(false);
        }
    };

    const handleSelectTable = async (tableName, fks = schema.foreign_keys) => {
        setSelectedTable(tableName);
        setLoadingPreview(true);
        setPreviewData({ columns: [], rows: [] });
        
        try {
            const response = await axios.get(`${API_BASE_URL}/api/data/preview/${tableName}`);
            setPreviewData(response.data);
        } catch (err) {
            console.error('Failed to fetch preview data:', err);
        } finally {
            setLoadingPreview(false);
        }
    };

    // Find relationships for the selected table
    const getTableRelations = (tableName) => {
        if (!tableName) return [];
        return schema.foreign_keys.filter(fk => fk.table === tableName || fk.foreign_table === tableName);
    };

    const tableColumns = selectedTable ? (schema.columns[selectedTable] || []) : [];
    const tableRelations = getTableRelations(selectedTable);

    return (
        <div className="dataset-view-page">
            <div className="view-header glass-panel">
                <button className="back-btn" onClick={onBack}>
                    <ArrowLeft size={20} />
                    <span>Back to Chat</span>
                </button>
                <div className="view-title">
                    <Database size={20} color="var(--accent-blue)" />
                    <h1>Database Schema &Preview</h1>
                </div>
                <div style={{ width: '120px' }}></div>
            </div>

            <main className="view-content" style={{ display: 'flex', gap: '1.5rem', height: 'calc(100vh - 120px)', padding: '0 2rem' }}>
                {/* Sidebar: Table List */}
                <div className="content-card glass-panel" style={{ width: '300px', flexShrink: 0, display: 'flex', flexDirection: 'column', height: '100%' }}>
                    <div className="card-header" style={{ padding: '1rem', borderBottom: '1px solid var(--glass-border)' }}>
                        <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1rem' }}>
                            <TableIcon size={18} /> Tables
                        </h3>
                    </div>
                    <div style={{ flex: 1, overflowY: 'auto', padding: '1rem' }}>
                        {loadingSchema ? (
                            <div className="spinner-mini" style={{ margin: 'auto', display: 'block' }}></div>
                        ) : error ? (
                            <div style={{ color: 'var(--accent-red)', fontSize: '0.875rem' }}><AlertCircle size={14}/> {error}</div>
                        ) : schema.tables.length === 0 ? (
                            <p style={{ color: 'var(--text-color)', opacity: 0.6 }}>No tables found.</p>
                        ) : (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                                {schema.tables.map(t => (
                                    <button 
                                        key={t}
                                        onClick={() => handleSelectTable(t)}
                                        style={{ 
                                            padding: '0.75rem 1rem', 
                                            textAlign: 'left', 
                                            background: selectedTable === t ? 'rgba(56, 189, 248, 0.15)' : 'transparent',
                                            border: `1px solid ${selectedTable === t ? 'var(--accent-blue)' : 'var(--glass-border)'}`,
                                            borderRadius: '8px',
                                            color: 'var(--text-color)',
                                            cursor: 'pointer',
                                            transition: 'all 0.2s',
                                            fontWeight: selectedTable === t ? '600' : '400'
                                        }}
                                    >
                                        {t}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                {/* Main Content: Schema Details & Data Preview */}
                <div className="content-card glass-panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
                    {selectedTable ? (
                        <>
                            <div className="card-header" style={{ padding: '1rem', borderBottom: '1px solid var(--glass-border)', display: 'flex', justifyContent: 'space-between' }}>
                                <h2 style={{ margin: 0, fontSize: '1.25rem' }}>{selectedTable}</h2>
                                <span className="format-badge" style={{ margin: 0 }}>{previewData.rows.length} Rows Snippet</span>
                            </div>
                            
                            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
                                {/* Relations & Columns Summary */}
                                <div style={{ padding: '1.5rem', display: 'flex', gap: '2rem', borderBottom: '1px solid var(--glass-border)' }}>
                                    
                                    <div style={{ flex: 1 }}>
                                        <h4 style={{ margin: '0 0 1rem 0', display: 'flex', alignItems: 'center', gap: '0.5rem', opacity: 0.8 }}><Key size={16}/> Schema Columns</h4>
                                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                                            {tableColumns.map(col => (
                                                <div key={col.name} style={{ background: 'var(--glass-bg)', padding: '0.25rem 0.5rem', borderRadius: '4px', fontSize: '0.8rem', border: '1px solid var(--glass-border)' }}>
                                                    <strong>{col.name}</strong> <span style={{ opacity: 0.6 }}>{col.type}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>

                                    {tableRelations.length > 0 && (
                                        <div style={{ flex: 1 }}>
                                            <h4 style={{ margin: '0 0 1rem 0', display: 'flex', alignItems: 'center', gap: '0.5rem', opacity: 0.8 }}><LinkIcon size={16}/> Relationships</h4>
                                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                                                {tableRelations.map((rel, i) => (
                                                    <div key={i} style={{ fontSize: '0.85rem', background: 'rgba(56, 189, 248, 0.05)', padding: '0.5rem', borderRadius: '6px', border: '1px solid rgba(56, 189, 248, 0.2)' }}>
                                                        {rel.table === selectedTable ? (
                                                            <span><strong>{rel.column}</strong> → {rel.foreign_table}.{rel.foreign_column}</span>
                                                        ) : (
                                                            <span><strong>{rel.foreign_column}</strong> ← {rel.table}.{rel.column}</span>
                                                        )}
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>

                                {/* Data Table */}
                                <div className="sql-results" style={{ flex: 1, padding: '1rem', overflowY: 'auto', margin: 0 }}>
                                    {loadingPreview ? (
                                        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
                                            <div className="spinner-mini"></div>
                                        </div>
                                    ) : previewData.rows.length === 0 ? (
                                        <div style={{ textAlign: 'center', opacity: 0.6, marginTop: '2rem' }}>No data found in {selectedTable}.</div>
                                    ) : (
                                        <table>
                                            <thead>
                                                <tr>
                                                    {previewData.columns.map((col, idx) => (
                                                        <th key={idx}>{col}</th>
                                                    ))}
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {previewData.rows.map((row, rIdx) => (
                                                    <tr key={rIdx}>
                                                        {row.map((cell, cIdx) => (
                                                            <td key={cIdx}>{cell !== null ? String(cell) : <span className="null-val">NULL</span>}</td>
                                                        ))}
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    )}
                                </div>
                            </div>
                        </>
                    ) : (
                        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', opacity: 0.6 }}>
                            <p>Select a table to view its schema and data.</p>
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
};

export default DatabaseView;
