package handlers

import (
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/nquire/ttsql/gateway/internal/archive"
	"github.com/nquire/ttsql/gateway/internal/config"
	"github.com/nquire/ttsql/gateway/internal/csvutil"
	"github.com/nquire/ttsql/gateway/internal/logparser"
)

type dbListCache struct {
	mu        sync.RWMutex
	value     any
	computedAt time.Time
	ttl       time.Duration
}

var globalDBCache = &dbListCache{ttl: 15 * time.Second}

// DatabasesHandler handles GET /api/databases
func DatabasesHandler(cfg *config.Config) gin.HandlerFunc {
	return func(c *gin.Context) {
		date := c.DefaultQuery("date", "all")
		c.JSON(http.StatusOK, getDatabases(cfg, date))
	}
}

func getDatabases(cfg *config.Config, date string) []map[string]any {
	globalDBCache.mu.RLock()
	if time.Since(globalDBCache.computedAt) < globalDBCache.ttl && globalDBCache.value != nil {
		v := globalDBCache.value
		globalDBCache.mu.RUnlock()
		return v.([]map[string]any)
	}
	globalDBCache.mu.RUnlock()

	result := buildDatabaseList(cfg, date)

	globalDBCache.mu.Lock()
	globalDBCache.value = result
	globalDBCache.computedAt = time.Now()
	globalDBCache.mu.Unlock()
	return result
}

func buildDatabaseList(cfg *config.Config, date string) []map[string]any {
	inputCounts := getInputCounts(cfg)
	targetDirs := archive.GetTargetDirsForDate(cfg.ResultsDir, date)

	sfDir := filepath.Join(cfg.DatabasesDir, "snowflake")
	entries, err := os.ReadDir(sfDir)
	if err != nil {
		return []map[string]any{}
	}

	var databases []map[string]any
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		dbName := e.Name()
		var successCount, errorCount, emptyCount int

		for _, tDir := range targetDirs {
			resDir := filepath.Join(tDir, dbName)
			if _, err := os.Stat(resDir); err != nil {
				continue
			}
			mdFiles := listFiles(resDir, ".md")
			for _, mdFile := range mdFiles {
				instanceID := stripExt(mdFile)
				csvFile := filepath.Join(resDir, instanceID+".csv")
				logData := logparser.ParseMDLog(mdFile)
				if logData.Error {
					errorCount++
				} else if _, err := os.Stat(csvFile); err == nil {
					isEmpty, _ := csvutil.GetCSVInfo(csvFile)
					if isEmpty {
						emptyCount++
					} else {
						successCount++
					}
				} else {
					emptyCount++
				}
			}
		}

		totalQuestions := inputCounts[strings.ToUpper(dbName)]
		processed := successCount + errorCount + emptyCount
		status := "pending"
		if processed >= totalQuestions && totalQuestions > 0 {
			status = "completed"
		}

		databases = append(databases, map[string]any{
			"name":            dbName,
			"status":          status,
			"results_count":   successCount,
			"error_count":     errorCount,
			"empty_count":     emptyCount,
			"total_questions": totalQuestions,
			"tokens":          0,
			"tables_count":    0,
		})
	}

	sort.Slice(databases, func(i, j int) bool {
		ri := databases[i]["results_count"].(int) + databases[i]["error_count"].(int)
		rj := databases[j]["results_count"].(int) + databases[j]["error_count"].(int)
		return ri > rj
	})
	return databases
}

var (
	inputCountsOnce  sync.Once
	inputCountsCache map[string]int
)

// getInputCounts reads spider2-lite-snowflake.jsonl and counts questions per DB.
func getInputCounts(cfg *config.Config) map[string]int {
	inputCountsOnce.Do(func() {
		inputCountsCache = buildInputCounts(cfg)
	})
	return inputCountsCache
}

func buildInputCounts(cfg *config.Config) map[string]int {
	counts := map[string]int{}
	path := filepath.Join(cfg.InputDir, "spider2-lite-snowflake.jsonl")
	for _, item := range readJSONL(path) {
		if db, ok := item["db"].(string); ok {
			counts[strings.ToUpper(strings.TrimSpace(db))]++
		}
	}
	return counts
}

// listFiles returns all files with a given extension in dir (non-recursive).
func listFiles(dir, ext string) []string {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil
	}
	var files []string
	for _, e := range entries {
		if !e.IsDir() && filepath.Ext(e.Name()) == ext {
			files = append(files, filepath.Join(dir, e.Name()))
		}
	}
	return files
}
