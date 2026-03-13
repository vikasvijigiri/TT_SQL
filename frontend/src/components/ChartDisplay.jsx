import React from 'react';
import {
    BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
    XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';
import './ChartDisplay.css';

const COLORS = ['#2563eb', '#6366f1', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#06b6d4', '#f97316'];

const ChartDisplay = ({ chartConfig, results, columns }) => {
    if (!chartConfig || !results || results.length === 0) return null;

    const { type, xAxis, yAxis, title } = chartConfig;

    if (!type || type === 'none' || !xAxis || !yAxis) return null;

    // Ensure the requested columns exist in data
    if (!columns.includes(xAxis) || !columns.includes(yAxis)) return null;

    // Map rows to chart-friendly objects
    const data = results.map(row => ({
        label: row[xAxis] !== null ? String(row[xAxis]) : 'N/A',
        value: parseFloat(row[yAxis]) || 0,
    }));

    const renderBar = () => (
        <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 60 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#64748b' }} angle={-35} textAnchor="end" />
                <YAxis tick={{ fontSize: 11, fill: '#64748b' }} />
                <Tooltip
                    contentStyle={{ background: 'rgba(255,255,255,0.95)', border: '1px solid #e2e8f0', borderRadius: '8px', fontSize: '12px' }}
                    formatter={(val) => [val.toLocaleString(), yAxis]}
                    labelStyle={{ fontWeight: 600, color: '#1e293b' }}
                />
                <Bar dataKey="value" fill="#2563eb" radius={[4, 4, 0, 0]}>
                    {data.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                </Bar>
            </BarChart>
        </ResponsiveContainer>
    );

    const renderLine = () => (
        <ResponsiveContainer width="100%" height={300}>
            <LineChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 60 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#64748b' }} angle={-35} textAnchor="end" />
                <YAxis tick={{ fontSize: 11, fill: '#64748b' }} />
                <Tooltip
                    contentStyle={{ background: 'rgba(255,255,255,0.95)', border: '1px solid #e2e8f0', borderRadius: '8px', fontSize: '12px' }}
                    formatter={(val) => [val.toLocaleString(), yAxis]}
                    labelStyle={{ fontWeight: 600, color: '#1e293b' }}
                />
                <Line type="monotone" dataKey="value" stroke="#2563eb" strokeWidth={2.5} dot={{ r: 4, fill: '#2563eb' }} activeDot={{ r: 6 }} />
            </LineChart>
        </ResponsiveContainer>
    );

    const renderPie = () => (
        <ResponsiveContainer width="100%" height={300}>
            <PieChart>
                <Pie data={data} dataKey="value" nameKey="label" cx="50%" cy="50%" outerRadius={110} paddingAngle={2} label={({ label, percent }) => `${label} (${(percent * 100).toFixed(1)}%)`}>
                    {data.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                </Pie>
                <Tooltip formatter={(val) => val.toLocaleString()} />
                <Legend iconSize={10} wrapperStyle={{ fontSize: '12px' }} />
            </PieChart>
        </ResponsiveContainer>
    );

    return (
        <div className="chart-display">
            {title && <div className="chart-title">{title}</div>}
            {type === 'bar' && renderBar()}
            {type === 'line' && renderLine()}
            {type === 'pie' && renderPie()}
        </div>
    );
};

export default ChartDisplay;
