package handlers

import (
	"encoding/csv"
	"math"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/nquire/ttsql/gateway/internal/archive"
	"github.com/nquire/ttsql/gateway/internal/config"
	"github.com/nquire/ttsql/gateway/internal/logparser"
)

var reSSQLBlock = regexp.MustCompile("(?s)```sql\n(.*?)\n```")
var reExecStart = regexp.MustCompile(`--- EXECUTION STARTED AT`)

// DetailsHandler handles GET /api/details/{db_name}/{instance_id}
func DetailsHandler(cfg *config.Config) gin.HandlerFunc {
	return func(c *gin.Context) {
		dbName := strings.ToUpper(strings.TrimSpace(c.Param("db_name")))
		instanceID := strings.TrimSpace(c.Param("instance_id"))
		date := c.DefaultQuery("date", "all")

		resDir := filepath.Join(cfg.ResultsDir, dbName)
		targetDirs := archive.GetTargetDirsForDate(cfg.ResultsDir, date)
		for _, tDir := range targetDirs {
			candidate := filepath.Join(tDir, dbName)
			if _, err := os.Stat(candidate); err == nil {
				resDir = candidate
				break
			}
		}

		mdFile := filepath.Join(resDir, instanceID+".md")
		csvFile := filepath.Join(resDir, instanceID+".csv")
		sqlFile := filepath.Join(resDir, instanceID+".sql")

		logContent := "Log file not found."
		sqlContent := "SQL file not found."
		var csvHeaders []string
		var csvData []map[string]any
		var executedAt *string
		totalTokens := 0
		cost := 0.0
		complexityType := "Unclassified"
		complexityScore := 0.0

		if sqlBytes, err := os.ReadFile(sqlFile); err == nil {
			sqlContent = strings.TrimSpace(string(sqlBytes))
		}

		if _, err := os.Stat(mdFile); err == nil {
			if fi, err := os.Stat(mdFile); err == nil {
				ts := fi.ModTime().Format(time.RFC3339)
				executedAt = &ts
			}
			logData := logparser.ParseMDLog(mdFile)
			totalTokens = logData.TotalTokens
			cost = logData.Cost
			complexityType = logData.ComplexityType
			complexityScore = logData.ComplexityScore

			if raw, err := os.ReadFile(mdFile); err == nil {
				content := string(raw)
				// Trim to last execution block
				if m := reExecStart.FindStringIndex(content); m != nil {
					parts := strings.SplitN(content, "--- EXECUTION STARTED AT", -1)
					if len(parts) > 1 {
						content = "--- EXECUTION STARTED AT" + parts[len(parts)-1]
					}
				}
				logContent = content

				if sqlContent == "SQL file not found." {
					if m := reSSQLBlock.FindStringSubmatch(content); len(m) > 1 {
						sqlContent = strings.TrimSpace(m[1])
					}
				}
			}
		}

		if _, err := os.Stat(csvFile); err == nil {
			csvHeaders, csvData = readCSVForDisplay(csvFile, 100)
		}

		c.JSON(http.StatusOK, gin.H{
			"log_content":      logContent,
			"sql_content":      sqlContent,
			"csv_headers":      csvHeaders,
			"csv_data":         csvData,
			"executed_at":      executedAt,
			"total_tokens":     totalTokens,
			"cost":             cost,
			"complexity_type":  complexityType,
			"complexity_score": complexityScore,
		})
	}
}

func readCSVForDisplay(path string, maxRows int) ([]string, []map[string]any) {
	f, err := os.Open(path)
	if err != nil {
		return nil, nil
	}
	defer f.Close()

	r := csv.NewReader(f)
	r.LazyQuotes = true
	records, err := r.ReadAll()
	if err != nil || len(records) == 0 {
		return nil, nil
	}

	headers := records[0]
	var data []map[string]any
	limit := len(records) - 1
	if limit > maxRows {
		limit = maxRows
	}
	for i := 1; i <= limit; i++ {
		row := map[string]any{}
		for j, h := range headers {
			if j < len(records[i]) {
				row[h] = sanitizeCSVValue(records[i][j])
			} else {
				row[h] = nil
			}
		}
		data = append(data, row)
	}
	if data == nil {
		data = []map[string]any{}
	}
	return headers, data
}

func sanitizeCSVValue(s string) any {
	// Try float
	if s == "" || strings.EqualFold(s, "nan") || strings.EqualFold(s, "inf") ||
		strings.EqualFold(s, "-inf") || strings.EqualFold(s, "null") || strings.EqualFold(s, "none") {
		return nil
	}
	if f, err := parseFloat(s); err == nil {
		if math.IsNaN(f) || math.IsInf(f, 0) {
			return nil
		}
		return f
	}
	return s
}

func parseFloat(s string) (float64, error) {
	return strconv.ParseFloat(strings.TrimSpace(s), 64)
}
