package config

import (
	"os"
	"path/filepath"
	"runtime"
)

type Config struct {
	// Server
	Port          string
	GinMode       string
	PythonAPIURL  string

	// Auth
	GoogleClientID string
	JWTSecret      string

	// Paths (all derived from BackendDir)
	BackendDir    string
	ResultsDir    string
	DatabasesDir  string
	GoldDir       string
	InputDir      string
	MemoryDir     string
	PromptsDir    string
	ConfigDir     string
	DABResultsDir string
	DABRepo       string

	// SQLite
	SQLiteDBPath string
}

func Load() *Config {
	backendDir := envOr("BACKEND_DATA_DIR", defaultBackendDir())

	resultsDir := filepath.Join(backendDir, "results", "evaluations")

	c := &Config{
		Port:         envOr("GO_PORT", "3030"),
		GinMode:      envOr("GIN_MODE", "release"),
		PythonAPIURL: envOr("PYTHON_API_URL", "http://localhost:8010"),

		GoogleClientID: envOr("GOOGLE_CLIENT_ID", ""),
		JWTSecret:      envOr("JWT_SECRET", "change-me-in-production"),

		BackendDir:    backendDir,
		ResultsDir:    resultsDir,
		DatabasesDir:  filepath.Join(backendDir, "resources", "databases"),
		GoldDir:       filepath.Join(backendDir, "resources", "gold"),
		InputDir:      filepath.Join(backendDir, "resources", "input_data"),
		MemoryDir:     filepath.Join(backendDir, "resources", "memory"),
		PromptsDir:    filepath.Join(backendDir, "app", "prompts"),
		ConfigDir:     filepath.Join(backendDir, "config"),
		DABResultsDir: filepath.Join(resultsDir, "dab"),
		DABRepo:       envOr("DAB_REPO", defaultDABRepo(backendDir)),

		SQLiteDBPath: filepath.Join(resultsDir, "nquire.db"),
	}
	return c
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

// defaultBackendDir resolves <this_file>/../../.. → project root → backend/agent/agent/
func defaultBackendDir() string {
	// Walk up from the executable or fall back to relative path from source
	exe, err := os.Executable()
	if err == nil {
		// When running as binary: exe is in backend/gateway/cmd/server/
		// Go up 3 levels → backend/, then descend into agent/agent
		dir := filepath.Dir(exe)
		candidate := filepath.Join(dir, "..", "..", "..", "agent", "agent")
		if abs, err := filepath.Abs(candidate); err == nil {
			if info, err := os.Stat(abs); err == nil && info.IsDir() {
				return abs
			}
		}
	}

	// Fallback: use source file location (works with `go run`)
	_, srcFile, _, _ := runtime.Caller(0)
	// srcFile is internal/config/config.go, go up 3 levels
	dir := filepath.Dir(filepath.Dir(filepath.Dir(srcFile)))
	candidate := filepath.Join(dir, "..", "agent", "agent")
	if abs, err := filepath.Abs(candidate); err == nil {
		return abs
	}
	return filepath.Join("..", "agent", "agent")
}

func defaultDABRepo(backendDir string) string {
	// Default: sibling directory of the project root named DataAgentBench
	// backendDir is backend/agent/agent. Go up 4 levels to get the sibling folder's parent.
	parent := filepath.Dir(filepath.Dir(filepath.Dir(filepath.Dir(backendDir))))
	return filepath.Join(parent, "DataAgentBench")
}
