import React from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeRaw from 'rehype-raw';
import ChartDisplay from './ChartDisplay';
import './ResultDisplay.css';

const ResultDisplay = ({ sql, results, columns, total_count, business_summary, chart_config, error, total_time }) => {
    if (error) {
        return (
            <div className="result-display glass-panel error">
                <div className="error-header">Error</div>
                <div className="error-message">{error}</div>
            </div>
        );
    }

    if (!sql && (!results || results.length === 0) && !business_summary) {
        return null;
    }

    // Backend now caps the 'results' array at 100 for network performance.
    // 'total_count' tells us the true size of the result set on the database.
    const displayResults = results || [];
    const totalRecords = total_count || results?.length || 0;
    const hasMore = totalRecords > displayResults.length;

    return (
        <div className="result-display-nested">
            {business_summary && (
                <div className="result-section insights-section">
                    <div className="business-summary">
                        {/* Hybrid Markdown + HTML Rendering for premium AI components */}
                        <ReactMarkdown rehypePlugins={[rehypeRaw]}>{business_summary}</ReactMarkdown>
                    </div>
                </div>
            )}

            {/* AI-Driven Chart */}
            {chart_config && displayResults.length > 0 && (
                <ChartDisplay chartConfig={chart_config} results={displayResults} columns={columns} />
            )}

            {displayResults.length > 0 && (
                <div className="result-section">
                    <div className="table-wrapper">
                        <table className="result-table">
                            <thead>
                                <tr>
                                    {columns.map((col) => (
                                        <th key={col}>{col}</th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {displayResults.map((row, idx) => (
                                    <tr key={idx}>
                                        {columns.map((col) => (
                                            <td key={col}>{row[col] === null ? 'NULL' : String(row[col])}</td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                        {totalRecords > 0 && (
                            <div className="table-footer">
                                Showing {displayResults.length} of {totalRecords} records retrieved.
                                {hasMore && " Use the CSV download for the full dataset."}
                            </div>
                        )}
                    </div>
                </div>
            )}

            {total_time && (
                <div className="execution-meta">
                    <span className="time-metric">Analysis completed in <strong>{total_time.toFixed(2)}s</strong></span>
                </div>
            )}
        </div>
    );
};

export default React.memo(ResultDisplay);
