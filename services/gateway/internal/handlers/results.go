package handlers

import (
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/nquire/ttsql/gateway/internal/archive"
	"github.com/nquire/ttsql/gateway/internal/config"
	"github.com/nquire/ttsql/gateway/internal/csvutil"
	"github.com/nquire/ttsql/gateway/internal/db"
	"github.com/nquire/ttsql/gateway/internal/logparser"
)

// ResultsRecentHandler handles GET /api/results/recent
func ResultsRecentHandler(cfg *config.Config) gin.HandlerFunc {
	return func(c *gin.Context) {
		limit := 10
		if l := c.Query("limit"); l != "" {
			if n, err := strconv.Atoi(l); err == nil && n > 0 {
				limit = n
			}
		}
		date := c.DefaultQuery("date", "all")
		c.JSON(http.StatusOK, getRecentResults(cfg, limit, date))
	}
}

func getRecentResults(cfg *config.Config, limit int, date string) []map[string]any {
	targetDirs := archive.GetTargetDirsForDate(cfg.ResultsDir, date)

	var allMD []string
	for _, tDir := range targetDirs {
		if _, err := os.Stat(tDir); err != nil {
			continue
		}
		var files []string
		if tDir == cfg.ResultsDir {
			files = archive.WalkMDFiles(tDir, true, true)
		} else {
			files = archive.WalkMDFiles(tDir, false, true)
		}
		allMD = append(allMD, files...)
	}

	sort.Slice(allMD, func(i, j int) bool {
		si, _ := os.Stat(allMD[i])
		sj, _ := os.Stat(allMD[j])
		if si == nil || sj == nil {
			return false
		}
		return si.ModTime().After(sj.ModTime())
	})

	var runs []map[string]any
	for _, mdFile := range allMD {
		if len(runs) >= limit {
			break
		}
		instanceID := stripExt(mdFile)
		dbName := filepath.Base(filepath.Dir(mdFile))
		csvFile := filepath.Join(filepath.Dir(mdFile), instanceID+".csv")

		logData := logparser.ParseMDLog(mdFile)
		status := "pending"
		if logData.Error {
			status = "error"
		}
		rowCount := 0
		if _, err := os.Stat(csvFile); err == nil {
			isEmpty, rows := csvutil.GetCSVInfo(csvFile)
			if !isEmpty {
				status = "success"
			} else {
				status = "empty"
			}
			rowCount = rows
		} else if logData.Success {
			status = "empty"
		}

		ts := ""
		if fi, err := os.Stat(mdFile); err == nil {
			ts = fi.ModTime().Format(time.RFC3339)
		}

		runs = append(runs, map[string]any{
			"id":               instanceID,
			"db":               dbName,
			"status":           status,
			"gold_status":      nil,
			"latency":          logData.Latency,
			"complexity":       logData.Complexity,
			"complexity_type":  logData.ComplexityType,
			"complexity_score": logData.ComplexityScore,
			"corrections":      logData.Corrections,
			"critic_rounds":    logData.CriticRounds,
			"rows":             rowCount,
			"timestamp":        ts,
			"total_tokens":     logData.TotalTokens,
			"cost":             logData.Cost,
		})
	}
	if runs == nil {
		runs = []map[string]any{}
	}
	return runs
}

// ResultsDatesHandler handles GET /api/results/dates
func ResultsDatesHandler(cfg *config.Config, sqlDB *db.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		spiderDates := getSpiderDates(cfg)
		dabDates := getDABDates(cfg, sqlDB)
		c.JSON(http.StatusOK, gin.H{"spider": spiderDates, "dab": dabDates})
	}
}

func getSpiderDates(cfg *config.Config) []string {
	dates := map[string]bool{}
	archiveBase := filepath.Join(cfg.ResultsDir, "_archive")
	if entries, err := os.ReadDir(archiveBase); err == nil {
		for _, e := range entries {
			if !e.IsDir() {
				continue
			}
			parts := strings.SplitN(e.Name(), "_", 2)
			if len(parts) < 2 || len(parts[1]) < 8 {
				continue
			}
			ds := parts[1]
			dates[ds[:4]+"-"+ds[4:6]+"-"+ds[6:8]] = true
		}
	}
	// Check for live results
	hasLive := false
	_ = filepath.Walk(cfg.ResultsDir, func(p string, fi os.FileInfo, err error) error {
		if hasLive || err != nil {
			return nil
		}
		if fi.IsDir() && (fi.Name() == "_archive" || strings.EqualFold(fi.Name(), "dab")) {
			return filepath.SkipDir
		}
		if !fi.IsDir() && filepath.Ext(p) == ".md" {
			hasLive = true
		}
		return nil
	})
	if hasLive {
		dates[time.Now().Format("2006-01-02")] = true
	}
	return sortedDescKeys(dates)
}

func getDABDates(cfg *config.Config, sqlDB *db.DB) []string {
	dates := map[string]bool{}
	if sqlDB != nil {
		if dbDates, err := sqlDB.GetDistinctEvalDates(); err == nil {
			for _, d := range dbDates {
				dates[d] = true
			}
		}
	}
	// DAB archive
	archiveBase := filepath.Join(cfg.DABResultsDir, "_archive")
	if entries, err := os.ReadDir(archiveBase); err == nil {
		for _, e := range entries {
			if !e.IsDir() {
				continue
			}
			parts := strings.SplitN(e.Name(), "_", 2)
			if len(parts) < 2 || len(parts[1]) < 8 {
				continue
			}
			ds := parts[1]
			dates[ds[:4]+"-"+ds[4:6]+"-"+ds[6:8]] = true
		}
	}
	// Check for live DAB results
	hasLive := false
	_ = filepath.Walk(cfg.DABResultsDir, func(p string, fi os.FileInfo, err error) error {
		if hasLive || err != nil {
			return nil
		}
		if fi.IsDir() && fi.Name() == "_archive" {
			return filepath.SkipDir
		}
		if !fi.IsDir() && strings.HasSuffix(p, "_eval.json") {
			hasLive = true
		}
		return nil
	})
	if hasLive {
		dates[time.Now().Format("2006-01-02")] = true
	}
	return sortedDescKeys(dates)
}

func sortedDescKeys(m map[string]bool) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Sort(sort.Reverse(sort.StringSlice(keys)))
	return keys
}

// AllResultsHandler handles GET /api/results/all
func AllResultsHandler(cfg *config.Config) gin.HandlerFunc {
	return func(c *gin.Context) {
		date := c.DefaultQuery("date", "all")
		c.JSON(http.StatusOK, getAllResults(cfg, date))
	}
}

func getAllResults(cfg *config.Config, date string) []map[string]any {
	targetDirs := archive.GetTargetDirsForDate(cfg.ResultsDir, date)
	if len(targetDirs) == 0 {
		return []map[string]any{}
	}

	var allRuns []map[string]any
	for _, tDir := range targetDirs {
		if _, err := os.Stat(tDir); err != nil {
			continue
		}
		var mdFiles []string
		if tDir == cfg.ResultsDir {
			mdFiles = archive.WalkMDFiles(tDir, true, false)
		} else {
			mdFiles = archive.WalkMDFiles(tDir, false, false)
		}
		for _, mdFile := range mdFiles {
			if archive.IsDabPath(mdFile) {
				continue
			}
			instanceID := stripExt(mdFile)
			dbName := filepath.Base(filepath.Dir(mdFile))
			csvFile := filepath.Join(filepath.Dir(mdFile), instanceID+".csv")

			logData := logparser.ParseMDLog(mdFile)
			status := "pending"
			if logData.Error {
				status = "error"
			}
			rowCount := 0
			if _, err := os.Stat(csvFile); err == nil {
				isEmpty, rows := csvutil.GetCSVInfo(csvFile)
				if !isEmpty {
					status = "success"
				} else {
					status = "empty"
				}
				rowCount = rows
			} else if logData.Success {
				status = "empty"
			}

			ts := ""
			if fi, err := os.Stat(mdFile); err == nil {
				ts = fi.ModTime().Format(time.RFC3339)
			}

			allRuns = append(allRuns, map[string]any{
				"id":             instanceID,
				"db":             dbName,
				"status":         status,
				"gold_status":    nil,
				"latency":        logData.Latency,
				"complexity":     logData.Complexity,
				"corrections":    logData.Corrections,
				"critic_rounds":  logData.CriticRounds,
				"rows":           rowCount,
				"timestamp":      ts,
			})
		}
	}

	sort.Slice(allRuns, func(i, j int) bool {
		return allRuns[i]["timestamp"].(string) > allRuns[j]["timestamp"].(string)
	})
	if allRuns == nil {
		return []map[string]any{}
	}
	return allRuns
}

// DBResultsHandler handles GET /api/results/{db_name}
func DBResultsHandler(cfg *config.Config) gin.HandlerFunc {
	return func(c *gin.Context) {
		dbName := strings.TrimSpace(c.Param("db_name"))
		date := c.DefaultQuery("date", "all")
		goldExecDir := filepath.Join(cfg.GoldDir, "exec_result")
		c.JSON(http.StatusOK, getDBResults(cfg, dbName, date, goldExecDir))
	}
}

func getDBResults(cfg *config.Config, dbName, date, goldExecDir string) []map[string]any {
	dbNameUpper := strings.ToUpper(strings.TrimSpace(dbName))
	examples := getAllExamples(cfg.InputDir)
	targetDirs := archive.GetTargetDirsForDate(cfg.ResultsDir, date)

	var results []map[string]any
	for instanceID, data := range examples {
		if dbVal, ok := data["db"].(string); !ok || strings.ToUpper(strings.TrimSpace(dbVal)) != dbNameUpper {
			continue
		}
		question := ""
		if q, ok := data["question"].(string); ok {
			question = q
		}

		cleanID := strings.TrimSpace(instanceID)
		status := "pending"
		rowCount := 0
		complexity := "unclassified"
		complexityType := "Unclassified"
		complexityScore := 0.0
		latency := 0.0
		corrections := 0
		criticRounds := 0
		logPath := ""
		totalTokens := 0
		cost := 0.0
		var goldStatus *string

		var mdFile, csvFile string
		for _, tDir := range targetDirs {
			candidate := filepath.Join(tDir, dbNameUpper, cleanID+".md")
			if _, err := os.Stat(candidate); err == nil {
				mdFile = candidate
				csvFile = filepath.Join(tDir, dbNameUpper, cleanID+".csv")
				break
			}
		}
		if mdFile == "" {
			mdFile = filepath.Join(cfg.ResultsDir, dbNameUpper, cleanID+".md")
			csvFile = filepath.Join(cfg.ResultsDir, dbNameUpper, cleanID+".csv")
		}

		if _, err := os.Stat(mdFile); err == nil {
			logPath = mdFile
			logData := logparser.ParseMDLog(mdFile)
			complexity = logData.Complexity
			complexityType = logData.ComplexityType
			complexityScore = logData.ComplexityScore
			latency = logData.Latency
			corrections = logData.Corrections
			criticRounds = logData.CriticRounds
			totalTokens = logData.TotalTokens
			cost = logData.Cost

			if _, err := os.Stat(csvFile); err == nil {
				isEmpty, rows := csvutil.GetCSVInfo(csvFile)
				rowCount = rows
				if !isEmpty {
					status = "success"
					gs := csvutil.EvaluateAgainstGold(cleanID, csvFile, goldExecDir, nil)
					if gs != "" {
						goldStatus = &gs
					}
				} else {
					status = "empty"
				}
			} else if logData.Error {
				status = "error"
			} else if logData.Success {
				status = "empty"
			}
		}

		results = append(results, map[string]any{
			"id":               instanceID,
			"question":         question,
			"status":           status,
			"gold_status":      goldStatus,
			"complexity":       complexity,
			"complexity_type":  complexityType,
			"complexity_score": complexityScore,
			"latency":          latency,
			"corrections":      corrections,
			"critic_rounds":    criticRounds,
			"rows":             rowCount,
			"log_path":         logPath,
			"total_tokens":     totalTokens,
			"cost":             cost,
		})
	}
	if results == nil {
		return []map[string]any{}
	}
	return results
}

// DeleteRunHandler handles DELETE /api/runs/{date}
func DeleteRunHandler(cfg *config.Config) gin.HandlerFunc {
	return func(c *gin.Context) {
		date := strings.TrimSpace(c.Param("date"))
		if date == "all" {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Cannot delete 'all' dates."})
			return
		}

		today := time.Now().Format("2006-01-02")
		if date == today {
			if err := clearLiveResults(cfg.ResultsDir); err != nil {
				c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
				return
			}
			c.JSON(http.StatusOK, gin.H{"message": "Cleared live results for " + date})
			return
		}

		archiveBase := filepath.Join(cfg.ResultsDir, "_archive")
		entries, _ := os.ReadDir(archiveBase)
		for _, e := range entries {
			if !e.IsDir() {
				continue
			}
			parts := strings.SplitN(e.Name(), "_", 2)
			if len(parts) < 2 || len(parts[1]) < 8 {
				continue
			}
			ds := parts[1]
			runDate := ds[:4] + "-" + ds[4:6] + "-" + ds[6:8]
			if runDate == date {
				_ = os.RemoveAll(filepath.Join(archiveBase, e.Name()))
			}
		}
		// Clear the metrics cache so next request recomputes
		InvalidateMetricsCache()

		c.JSON(http.StatusOK, gin.H{"message": "Run " + date + " deleted."})
	}
}

func clearLiveResults(resultsDir string) error {
	entries, err := os.ReadDir(resultsDir)
	if err != nil {
		return err
	}
	for _, e := range entries {
		if e.Name() == "_archive" || strings.EqualFold(e.Name(), "dab") {
			continue
		}
		_ = os.RemoveAll(filepath.Join(resultsDir, e.Name()))
	}
	return nil
}

