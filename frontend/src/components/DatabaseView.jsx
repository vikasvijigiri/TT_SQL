import React, { useState, useEffect } from 'react';
import { Database, Table as TableIcon, Key, Link as LinkIcon, AlertCircle, RefreshCw, ChevronRight } from 'lucide-react';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8001';

const DatabaseView = ({ onBack, userEmail, userName }) => {
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
            const response = await axios.get(`${API_BASE_URL}/api/data/schema`, {
                params: { user_email: userEmail, user_name: userName }
            });
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
            const response = await axios.get(`${API_BASE_URL}/api/data/preview/${tableName}`, {
                params: { user_email: userEmail, user_name: userName }
            });
            setPreviewData(response.data);
        } catch (err) {
            console.error('Failed to fetch preview data:', err);
        } finally {
            setLoadingPreview(false);
        }
    };

    const getTableRelations = (tableName) => {
        if (!tableName) return [];
        return schema.foreign_keys.filter(fk => fk.table === tableName || fk.foreign_table === tableName);
    };

    const tableColumns = selectedTable ? (schema.columns[selectedTable] || []) : [];
    const tableRelations = getTableRelations(selectedTable);

    return (
        <div className="page-layout">
            {/* ===== SIDEBAR ===== */}
            <div className="page-sidebar">
                <div className="page-sidebar-header">
                    <Database size={18} color="#2563eb" />
                    <h2>Data Explorer</h2>
                </div>

                <div className="page-sidebar-section-label">Tables</div>

                {loadingSchema ? (
                    <div style={{ display: 'flex', justifyContent: 'center', padding: '24px' }}>
                        <div className="spinner-mini" />
                    </div>
                ) : error ? (
                    <div style={{ padding: '16px 18px', color: '#dc2626', fontSize: '13px', display: 'flex', gap: '8px', alignItems: 'center' }}>
                        <AlertCircle size={14} /> {error}
                    </div>
                ) : schema.tables.length === 0 ? (
                    <div style={{ padding: '16px 18px', color: '#94a3b8', fontSize: '13px' }}>No tables found.</div>
                ) : (
                    schema.tables.map(t => (
                        <button
                            key={t}
                            className={`page-sidebar-item ${selectedTable === t ? 'active' : ''}`}
                            onClick={() => handleSelectTable(t)}
                        >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <TableIcon size={14} />
                                <span>{t}</span>
                            </div>
                            <ChevronRight size={14} color="#94a3b8" />
                        </button>
                    ))
                )}

                {/* Refresh at bottom */}
                <div style={{ marginTop: 'auto', padding: '12px 18px', borderTop: '1px solid #e2e8f0' }}>
                    <button
                        onClick={fetchSchema}
                        disabled={loadingSchema}
                        style={{
                            display: 'flex', alignItems: 'center', gap: '6px',
                            background: 'none', border: 'none', color: '#64748b',
                            fontSize: '12px', fontWeight: '500', cursor: 'pointer',
                            padding: 0, transition: 'color 0.15s'
                        }}
                        onMouseEnter={e => e.currentTarget.style.color = '#2563eb'}
                        onMouseLeave={e => e.currentTarget.style.color = '#64748b'}
                    >
                        <RefreshCw size={13} className={loadingSchema ? 'spin' : ''} /> Refresh Schema
                    </button>
                </div>
            </div>

            {/* ===== MAIN CONTENT ===== */}
            <div className="page-content" style={{ padding: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                {selectedTable ? (
                    <>
                        {/* Table Header */}
                        <div style={{
                            padding: '20px 28px', borderBottom: '1px solid #e2e8f0',
                            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                            backgroundColor: 'white', flexShrink: 0
                        }}>
                            <div>
                                <h2 style={{ margin: 0, fontSize: '18px', fontWeight: '600', color: '#0f172a', fontFamily: "'Outfit', sans-serif" }}>
                                    {selectedTable}
                                </h2>
                                <span style={{ fontSize: '12px', color: '#94a3b8', marginTop: '2px', display: 'block' }}>
                                    {tableColumns.length} columns · {previewData.rows.length} rows preview
                                </span>
                            </div>
                            <span style={{
                                fontSize: '11px', fontWeight: '700', color: '#2563eb',
                                background: '#eff6ff', padding: '4px 12px', borderRadius: '12px',
                                border: '1px solid #bfdbfe'
                            }}>
                                LIVE PREVIEW
                            </span>
                        </div>

                        <div style={{ flex: 1, overflowY: 'auto', padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
                            {/* Column Tags & Relations */}
                            <div style={{ display: 'flex', gap: '32px' }}>
                                <div style={{ flex: 1 }}>
                                    <h4 style={{ margin: '0 0 12px 0', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                                        <Key size={12} /> Columns
                                    </h4>
                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                                        {tableColumns.map(col => (
                                            <div key={col.name} style={{
                                                background: '#f8fafc', padding: '4px 10px', borderRadius: '6px',
                                                fontSize: '12px', border: '1px solid #e2e8f0',
                                                display: 'flex', gap: '6px', alignItems: 'center'
                                            }}>
                                                <strong style={{ color: '#334155' }}>{col.name}</strong>
                                                <span style={{ color: '#94a3b8' }}>{col.type}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                {tableRelations.length > 0 && (
                                    <div style={{ flex: 1 }}>
                                        <h4 style={{ margin: '0 0 12px 0', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                                            <LinkIcon size={12} /> Relationships
                                        </h4>
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                            {tableRelations.map((rel, i) => (
                                                <div key={i} style={{
                                                    fontSize: '12px', background: '#eff6ff', padding: '6px 10px',
                                                    borderRadius: '6px', border: '1px solid #bfdbfe', color: '#1d4ed8'
                                                }}>
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

                            {/* Data Preview Table */}
                            <div style={{ flex: 1, overflow: 'auto', border: '1px solid #e2e8f0', borderRadius: '10px', background: 'white' }}>
                                {loadingPreview ? (
                                    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '48px' }}>
                                        <div className="spinner-mini" />
                                    </div>
                                ) : previewData.rows.length === 0 ? (
                                    <div style={{ textAlign: 'center', padding: '48px', color: '#94a3b8', fontSize: '13px' }}>
                                        No data found in {selectedTable}.
                                    </div>
                                ) : (
                                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                                        <thead>
                                            <tr style={{ backgroundColor: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                                                {previewData.columns.map((col, idx) => (
                                                    <th key={idx} style={{ padding: '10px 14px', textAlign: 'left', fontWeight: '600', color: '#64748b', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.04em', whiteSpace: 'nowrap' }}>
                                                        {col}
                                                    </th>
                                                ))}
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {previewData.rows.map((row, rIdx) => (
                                                <tr key={rIdx} style={{ borderBottom: '1px solid #f1f5f9' }}
                                                    onMouseEnter={e => e.currentTarget.style.backgroundColor = '#f8fafc'}
                                                    onMouseLeave={e => e.currentTarget.style.backgroundColor = 'transparent'}
                                                >
                                                    {row.map((cell, cIdx) => (
                                                        <td key={cIdx} style={{ padding: '9px 14px', color: '#334155', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                                            {cell !== null ? String(cell) : <span style={{ color: '#cbd5e1', fontStyle: 'italic' }}>NULL</span>}
                                                        </td>
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
                    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', flexDirection: 'column', gap: '12px', color: '#94a3b8' }}>
                        <TableIcon size={36} />
                        <p style={{ fontSize: '14px', margin: 0 }}>Select a table to view its schema and data.</p>
                    </div>
                )}
            </div>
        </div>
    );
};

export default DatabaseView;
