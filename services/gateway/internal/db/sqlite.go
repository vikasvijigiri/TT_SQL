// Package db manages the shared SQLite database connection.
package db

import (
	"database/sql"
	"fmt"

	_ "modernc.org/sqlite"
)

// DB wraps the shared SQLite connection.
type DB struct {
	conn *sql.DB
}

// Open connects to the SQLite database at the given path.
func Open(path string) (*DB, error) {
	conn, err := sql.Open("sqlite", path)
	if err != nil {
		return nil, fmt.Errorf("open sqlite %s: %w", path, err)
	}
	conn.SetMaxOpenConns(1) // SQLite is single-writer; serialise all writes
	if err := conn.Ping(); err != nil {
		return nil, fmt.Errorf("ping sqlite %s: %w", path, err)
	}
	return &DB{conn: conn}, nil
}

// Close closes the underlying connection.
func (d *DB) Close() { _ = d.conn.Close() }

// QueryRows runs a SELECT and maps results via scanFn.
// scanFn receives a *sql.Rows positioned at the current row; it must call rows.Scan.
func (d *DB) QueryRows(query string, args []any, scanFn func(*sql.Rows) error) error {
	rows, err := d.conn.Query(query, args...)
	if err != nil {
		return err
	}
	defer rows.Close()
	for rows.Next() {
		if err := scanFn(rows); err != nil {
			return err
		}
	}
	return rows.Err()
}

// EvaluationDate holds a distinct date string from the evaluations table.
type EvaluationDate struct {
	Date string
}

// GetDistinctEvalDates returns all distinct dates (YYYY-MM-DD) in the evaluations table.
func (d *DB) GetDistinctEvalDates() ([]string, error) {
	const q = `SELECT DISTINCT date(timestamp) FROM evaluations WHERE timestamp IS NOT NULL ORDER BY 1 DESC`
	var dates []string
	err := d.QueryRows(q, nil, func(rows *sql.Rows) error {
		var s sql.NullString
		if err := rows.Scan(&s); err != nil {
			return err
		}
		if s.Valid && s.String != "" {
			dates = append(dates, s.String)
		}
		return nil
	})
	return dates, err
}
