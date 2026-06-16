package handlers

import (
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/nquire/ttsql/gateway/internal/config"
)

type checkResult struct {
	Name   string `json:"name"`
	Status string `json:"status"`
	Detail any    `json:"detail"`
}

// HealthHandler handles GET /api/health
func HealthHandler(cfg *config.Config) gin.HandlerFunc {
	return func(c *gin.Context) {
		var checks []checkResult

		check := func(name string, fn func() any) {
			defer func() {
				if r := recover(); r != nil {
					checks = append(checks, checkResult{name, "fail", r})
				}
			}()
			detail := fn()
			checks = append(checks, checkResult{name, "ok", detail})
		}

		check("results_dir", func() any {
			_, err := os.Stat(cfg.ResultsDir)
			writable := false
			if err == nil {
				writable = checkWritable(cfg.ResultsDir)
			}
			return map[string]any{"path": cfg.ResultsDir, "exists": err == nil, "writable": writable}
		})

		check("databases_dir", func() any {
			sqliteCount := countGlob(cfg.DatabasesDir, "**/*.sqlite")
			duckdbCount := countGlob(cfg.DatabasesDir, "**/*.duckdb")
			_, err := os.Stat(cfg.DatabasesDir)
			return map[string]any{
				"path": cfg.DatabasesDir, "exists": err == nil,
				"sqlite_count": sqliteCount, "duckdb_count": duckdbCount,
			}
		})

		check("dynamic_lessons", func() any {
			p := filepath.Join(cfg.MemoryDir, "dynamic_lessons.json")
			_, err := os.Stat(p)
			return map[string]any{"path": p, "exists": err == nil}
		})

		check("improvement_log", func() any {
			p := filepath.Join(cfg.MemoryDir, "improvement_log.json")
			_, err := os.Stat(p)
			return map[string]any{"initialized": err == nil}
		})

		check("llm_config", func() any {
			cfgFile := filepath.Join(cfg.ConfigDir, "system_params.yaml")
			_, err := os.Stat(cfgFile)
			return map[string]any{
				"config_file":     err == nil,
				"bedrock_key_set": os.Getenv("BEDROCK_SECRET_ACCESS_KEY") != "",
				"bedrock_region":  envOr("BEDROCK_REGION", "us-east-1"),
			}
		})

		check("prompts_dir", func() any {
			_, err := os.Stat(cfg.PromptsDir)
			count := countGlob(cfg.PromptsDir, "*.yaml")
			return map[string]any{"exists": err == nil, "yaml_count": count}
		})

		check("dab_repo", func() any {
			info, err := os.Stat(cfg.DABRepo)
			datasets := 0
			if err == nil && info.IsDir() {
				entries, _ := os.ReadDir(cfg.DABRepo)
				for _, e := range entries {
					if e.IsDir() && len(e.Name()) > 6 && e.Name()[:6] == "query_" {
						datasets++
					}
				}
			}
			return map[string]any{"path": cfg.DABRepo, "exists": err == nil, "dataset_dirs": datasets}
		})

		check("dab_results", func() any {
			_, err := os.Stat(cfg.DABResultsDir)
			count := countGlob(cfg.DABResultsDir, "**/*_eval.json")
			return map[string]any{"dir": cfg.DABResultsDir, "exists": err == nil, "eval_count": count}
		})

		check("gold_standards", func() any {
			p := filepath.Join(cfg.GoldDir, "spider2lite_eval.jsonl")
			_, err := os.Stat(p)
			return map[string]any{"exists": err == nil}
		})

		check("api_self", func() any {
			return map[string]any{"status": "serving", "service": "go-gateway"}
		})

		critical := map[string]bool{"results_dir": true, "databases_dir": true, "llm_config": true, "gold_standards": true}
		var failed []checkResult
		for _, ch := range checks {
			if ch.Status == "fail" {
				failed = append(failed, ch)
			}
		}

		var degraded []checkResult
		for _, ch := range checks {
			if ch.Status == "ok" && critical[ch.Name] {
				if d, ok := ch.Detail.(map[string]any); ok {
					if exists, ok := d["exists"].(bool); ok && !exists {
						degraded = append(degraded, ch)
					}
				}
			}
		}

		overall := "healthy"
		if len(failed) > 0 {
			overall = "unhealthy"
		} else if len(degraded) > 0 {
			overall = "degraded"
		}

		ok := 0
		for _, ch := range checks {
			if ch.Status == "ok" {
				ok++
			}
		}

		c.JSON(http.StatusOK, gin.H{
			"overall":   overall,
			"timestamp": time.Now().UTC().Format(time.RFC3339),
			"checks":    checks,
			"summary": gin.H{
				"total":   len(checks),
				"ok":      ok,
				"fail":    len(failed),
				"degraded": len(degraded),
			},
		})
	}
}

func checkWritable(dir string) bool {
	tmp := filepath.Join(dir, ".write_test")
	f, err := os.Create(tmp)
	if err != nil {
		return false
	}
	f.Close()
	os.Remove(tmp)
	return true
}

func countGlob(base, pattern string) int {
	if !strings.Contains(pattern, "**") {
		matches, _ := filepath.Glob(filepath.Join(base, pattern))
		return len(matches)
	}

	suffix := pattern
	if idx := strings.LastIndex(pattern, "**/"); idx != -1 {
		suffix = pattern[idx+3:]
	}
	suffix = strings.TrimPrefix(suffix, "*")

	count := 0
	_ = filepath.WalkDir(base, func(path string, d os.DirEntry, err error) error {
		if err != nil {
			return nil
		}
		if d.IsDir() {
			return nil
		}
		if strings.HasSuffix(strings.ToLower(path), strings.ToLower(suffix)) {
			count++
		}
		return nil
	})
	return count
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
