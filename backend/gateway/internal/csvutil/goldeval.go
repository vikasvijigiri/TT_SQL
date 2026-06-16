// Package csvutil ports the Python gold evaluation logic (evaluate_against_gold,
// _compare_tables, _vectors_match, get_csv_info).
package csvutil

import (
	"encoding/csv"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

// GetCSVInfo returns (isEmpty bool, rowCount int) for a CSV file.
func GetCSVInfo(path string) (bool, int) {
	f, err := os.Open(path)
	if err != nil {
		return true, 0
	}
	defer f.Close()

	r := csv.NewReader(f)
	records, err := r.ReadAll()
	if err != nil || len(records) <= 1 {
		return true, 0
	}
	rows := len(records) - 1 // exclude header
	return rows == 0, rows
}

// ReadCSVColumns reads a CSV and returns a slice of columns (each column is a []string of values).
// The first record is treated as the header and excluded from data values.
func ReadCSVColumns(path string) [][]string {
	f, err := os.Open(path)
	if err != nil {
		return nil
	}
	defer f.Close()

	r := csv.NewReader(f)
	r.LazyQuotes = true
	records, err := r.ReadAll()
	if err != nil || len(records) < 2 {
		return nil
	}

	numCols := len(records[0])
	dataRows := records[1:]
	cols := make([][]string, numCols)
	for j := 0; j < numCols; j++ {
		col := make([]string, len(dataRows))
		for i, row := range dataRows {
			if j < len(row) {
				col[i] = row[j]
			}
		}
		cols[j] = col
	}
	return cols
}

// normalizeVal converts empty/null strings to "0" (matching Python's _normalize).
func normalizeVal(s string) string {
	switch strings.TrimSpace(strings.ToLower(s)) {
	case "", "nan", "none", "null", "<na>":
		return "0"
	}
	return s
}

// isNaN reports whether a string represents a NaN/null value.
func isNaN(s string) bool {
	switch strings.TrimSpace(strings.ToLower(s)) {
	case "", "nan", "none", "null", "<na>":
		return true
	}
	return false
}

// vectorsMatch ports Python _vectors_match with abs_tol=1e-2.
func vectorsMatch(v1, v2 []string, tol float64, ignoreOrder bool) bool {
	if len(v1) != len(v2) {
		return false
	}

	norm1 := make([]string, len(v1))
	norm2 := make([]string, len(v2))
	for i, s := range v1 {
		norm1[i] = normalizeVal(s)
	}
	for i, s := range v2 {
		norm2[i] = normalizeVal(s)
	}

	if ignoreOrder {
		sortStrings(norm1)
		sortStrings(norm2)
	}

	for i := range norm1 {
		a, b := norm1[i], norm2[i]
		aNaN, bNaN := isNaN(v1[i]), isNaN(v2[i])
		if aNaN && bNaN {
			continue
		}

		fa, errA := strconv.ParseFloat(a, 64)
		fb, errB := strconv.ParseFloat(b, 64)
		if errA == nil && errB == nil {
			if !closeEnough(fa, fb, tol) {
				return false
			}
		} else {
			if strings.TrimSpace(strings.ToLower(a)) != strings.TrimSpace(strings.ToLower(b)) {
				return false
			}
		}
	}
	return true
}

func closeEnough(a, b, absTol float64) bool {
	if math.IsNaN(a) && math.IsNaN(b) {
		return true
	}
	return math.Abs(a-b) <= absTol
}

// sortStrings sorts such that NaN values come first (matching Python sort key).
func sortStrings(ss []string) {
	sort.Slice(ss, func(i, j int) bool {
		ni, nj := isNaN(ss[i]), isNaN(ss[j])
		if ni != nj {
			return ni // NaN first
		}
		return ss[i] < ss[j]
	})
}

// CompareTables ports Python _compare_tables.
// predCols and goldCols are transposed: each element is one column's values.
// conditionCols is a list of column indices to restrict gold to (nil = check all).
func CompareTables(predCols, goldCols [][]string, conditionCols []int, ignoreOrder bool) bool {
	if len(conditionCols) > 0 {
		// Build gold subset from condition_cols
		var goldSubset [][]string
		for _, idx := range conditionCols {
			if idx < len(goldCols) {
				goldSubset = append(goldSubset, goldCols[idx])
			}
		}
		for _, gv := range goldSubset {
			matched := false
			for _, pv := range predCols {
				if vectorsMatch(gv, pv, 1e-2, ignoreOrder) {
					matched = true
					break
				}
			}
			if !matched {
				return false
			}
		}
		return true
	}

	for _, gv := range goldCols {
		matched := false
		for _, pv := range predCols {
			if vectorsMatch(gv, pv, 1e-2, ignoreOrder) {
				matched = true
				break
			}
		}
		if !matched {
			return false
		}
	}
	return true
}

// EvalStandard holds per-instance evaluation configuration from spider2lite_eval.jsonl.
type EvalStandard struct {
	ConditionCols []int `json:"condition_cols"`
	IgnoreOrder   bool  `json:"ignore_order"`
}

// EvaluateAgainstGold compares a predicted CSV against all gold CSVs for an instance.
// goldDir is backend/resources/gold/exec_result/
// Returns "gold_pass", "gold_fail", or "" if gold not available.
func EvaluateAgainstGold(instanceID, predCSVPath, goldDir string, std *EvalStandard) string {
	if _, err := os.Stat(predCSVPath); err != nil {
		return ""
	}

	goldFiles := findGoldFiles(instanceID, goldDir)
	if len(goldFiles) == 0 {
		return ""
	}

	predCols := ReadCSVColumns(predCSVPath)
	if predCols == nil {
		return "gold_fail"
	}

	var condCols []int
	var ignoreOrder bool
	if std != nil {
		condCols = std.ConditionCols
		ignoreOrder = std.IgnoreOrder
	}

	for _, gp := range goldFiles {
		goldCols := ReadCSVColumns(gp)
		if goldCols == nil {
			continue
		}
		if CompareTables(predCols, goldCols, condCols, ignoreOrder) {
			return "gold_pass"
		}
	}
	return "gold_fail"
}

// findGoldFiles locates gold CSVs for a given instance ID in goldDir.
// Gold files can be named {instanceID}.csv or {instanceID}_{letter}.csv.
func findGoldFiles(instanceID, goldDir string) []string {
	entries, err := os.ReadDir(goldDir)
	if err != nil {
		return nil
	}
	var found []string
	for _, e := range entries {
		if e.IsDir() || filepath.Ext(e.Name()) != ".csv" {
			continue
		}
		stem := strings.TrimSuffix(e.Name(), ".csv")
		var inst string
		if len(stem) > 2 && stem[len(stem)-2] == '_' {
			last := stem[len(stem)-1]
			if last >= 'a' && last <= 'z' || last >= 'A' && last <= 'Z' {
				inst = stem[:len(stem)-2]
			} else {
				inst = stem
			}
		} else {
			inst = stem
		}
		if inst == instanceID {
			found = append(found, filepath.Join(goldDir, e.Name()))
		}
	}
	return found
}
