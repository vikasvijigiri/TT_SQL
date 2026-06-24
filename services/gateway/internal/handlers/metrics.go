package handlers

import (
	"fmt"
	"math"
	"net/http"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/nquire/ttsql/gateway/internal/archive"
	"github.com/nquire/ttsql/gateway/internal/config"
	"github.com/nquire/ttsql/gateway/internal/csvutil"
	"github.com/nquire/ttsql/gateway/internal/logparser"
)

type metricsCacheEntry struct {
	value      map[string]any
	computedAt time.Time
}

type metricsCache struct {
	mu  sync.RWMutex
	ttl time.Duration
	m   map[string]metricsCacheEntry
}

var globalMetricsCache = &metricsCache{ttl: 15 * time.Second, m: map[string]metricsCacheEntry{}}

// MetricsHandler handles GET /api/metrics
func MetricsHandler(cfg *config.Config) gin.HandlerFunc {
	return func(c *gin.Context) {
		date := c.DefaultQuery("date", "all")
		c.JSON(http.StatusOK, computeMetrics(cfg, date))
	}
}

func computeMetrics(cfg *config.Config, date string) map[string]any {
	globalMetricsCache.mu.RLock()
	if entry, ok := globalMetricsCache.m[date]; ok && time.Since(entry.computedAt) < globalMetricsCache.ttl {
		v := entry.value
		globalMetricsCache.mu.RUnlock()
		return v
	}
	globalMetricsCache.mu.RUnlock()

	result := buildMetrics(cfg, date)

	globalMetricsCache.mu.Lock()
	globalMetricsCache.m[date] = metricsCacheEntry{value: result, computedAt: time.Now()}
	globalMetricsCache.mu.Unlock()
	return result
}

// InvalidateMetricsCache clears all cached metrics (called after run deletion).
func InvalidateMetricsCache() {
	globalMetricsCache.mu.Lock()
	globalMetricsCache.m = map[string]metricsCacheEntry{}
	globalMetricsCache.mu.Unlock()
}

func buildMetrics(cfg *config.Config, date string) map[string]any {
	targetDirs := archive.GetTargetDirsForDate(cfg.ResultsDir, date)

	var (
		totalLatency   float64
		totalInstances int
		successCount   int
		errorCount     int
		goldPassCount  int
		totalTokens    int
		totalCost      float64
		complexity     = map[string]int{"linear_logic": 0, "relational_complexity": 0, "forensic_depth": 0, "unknown": 0}
	)

	goldExecDir := filepath.Join(cfg.GoldDir, "exec_result")

	for _, tDir := range targetDirs {
		if _, err := os.Stat(tDir); err != nil {
			continue
		}
		var mdFiles []string
		if tDir == cfg.ResultsDir {
			mdFiles = archive.WalkMDFiles(tDir, true, true)
		} else {
			mdFiles = archive.WalkMDFiles(tDir, false, true)
		}

		for _, mdFile := range mdFiles {
			instanceID := stripExt(mdFile)
			csvFile := filepath.Join(filepath.Dir(mdFile), instanceID+".csv")

			data := logparser.ParseMDLog(mdFile)
			totalInstances++

			if data.Error {
				errorCount++
			} else if _, err := os.Stat(csvFile); err == nil {
				isEmpty, _ := csvutil.GetCSVInfo(csvFile)
				if !isEmpty {
					successCount++
					if csvutil.EvaluateAgainstGold(instanceID, csvFile, goldExecDir, nil) == "gold_pass" {
						goldPassCount++
					}
				}
			}

			totalLatency += data.Latency
			totalTokens += data.TotalTokens
			totalCost += data.Cost
			c := data.Complexity
			if _, ok := complexity[c]; !ok {
				c = "unknown"
			}
			complexity[c]++
		}
	}

	avgLatency := 0.0
	if totalInstances > 0 {
		avgLatency = totalLatency / float64(totalInstances)
	}
	avgTokensPerAgent := 0
	if totalInstances > 0 {
		avgTokensPerAgent = totalTokens / (totalInstances * 5)
	}

	goldAccuracy := "0.0%"
	if totalInstances > 0 {
		goldAccuracy = fmt.Sprintf("%.1f%%", float64(goldPassCount)/float64(totalInstances)*100)
	}

	avgLatencyStr := "0.0s"
	if avgLatency > 0 {
		avgLatencyStr = fmt.Sprintf("%.1fs", avgLatency)
	}

	totalTokensStr := "0"
	if totalTokens >= 1_000_000 {
		totalTokensStr = fmt.Sprintf("%.2fM", float64(totalTokens)/1e6)
	} else if totalTokens > 0 {
		totalTokensStr = fmt.Sprintf("%.1fK", float64(totalTokens)/1e3)
	}

	avgCostPerQuery := "$0.0000"
	if totalInstances > 0 {
		avgCostPerQuery = fmt.Sprintf("$%.4f", totalCost/float64(totalInstances))
	}

	return map[string]any{
		"total_processed":      totalInstances,
		"errored_count":        errorCount,
		"succeeded_count":      successCount,
		"gold_succeeded_count": goldPassCount,
		"gold_accuracy":        goldAccuracy,
		"avg_latency":          avgLatencyStr,
		"avg_tokens_per_agent": fmt.Sprintf("%s tokens", formatInt(avgTokensPerAgent)),
		"total_tokens":         totalTokensStr,
		"total_cost":           fmt.Sprintf("$%.4f", totalCost),
		"avg_cost_per_query":   avgCostPerQuery,
		"llm_calls":            totalInstances * 5,
		"complexity_distribution": map[string]any{
			"easy":    complexity["linear_logic"],
			"medium":  complexity["relational_complexity"],
			"complex": complexity["forensic_depth"],
		},
	}
}

func stripExt(path string) string {
	base := filepath.Base(path)
	ext := filepath.Ext(base)
	return base[:len(base)-len(ext)]
}

func formatInt(n int) string {
	if n == 0 {
		return "0"
	}
	s := fmt.Sprintf("%d", n)
	result := make([]byte, 0, len(s)+len(s)/3)
	for i, ch := range s {
		if i > 0 && (len(s)-i)%3 == 0 {
			result = append(result, ',')
		}
		result = append(result, byte(ch))
	}
	return string(result)
}

// Unused but kept for reference matching Python rounding
func roundTwo(f float64) float64 {
	return math.Round(f*100) / 100
}
