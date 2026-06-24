package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/joho/godotenv"
	"github.com/nquire/ttsql/gateway/internal/config"
	"github.com/nquire/ttsql/gateway/internal/db"
	"github.com/nquire/ttsql/gateway/internal/router"
	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"
)

func main() {
	// Load .env from project root (TT_SQL_V2/.env)
	_ = godotenv.Load(".env")
	_ = godotenv.Load("../.env")
	_ = godotenv.Load("../../.env")
	_ = godotenv.Load("../../../.env") // fallback when running from repo root

	cfg := config.Load()

	log := buildLogger(cfg.GinMode == "debug")
	defer log.Sync()

	log.Info("starting NQuire Go gateway",
		zap.String("port", cfg.Port),
		zap.String("python_api", cfg.PythonAPIURL),
		zap.String("results_dir", cfg.ResultsDir),
	)

	// SQLite is optional â€” metrics still work from filesystem if DB isn't present yet
	var sqlDB *db.DB
	if sdb, err := db.Open(cfg.SQLiteDBPath); err != nil {
		log.Warn("SQLite unavailable (dates endpoint will fall back to filesystem only)",
			zap.String("path", cfg.SQLiteDBPath),
			zap.Error(err),
		)
	} else {
		sqlDB = sdb
		defer sqlDB.Close()
		log.Info("SQLite connected", zap.String("path", cfg.SQLiteDBPath))
	}

	engine := router.New(cfg, sqlDB, log)

	srv := &http.Server{
		Addr:         "0.0.0.0:" + cfg.Port,
		Handler:      engine,
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 300 * time.Second, // long timeout for streaming responses
		IdleTimeout:  120 * time.Second,
	}

	// Graceful shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, os.Interrupt, syscall.SIGTERM)

	go func() {
		log.Info(fmt.Sprintf("API gateway listening on http://0.0.0.0:%s", cfg.Port))
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatal("server error", zap.Error(err))
		}
	}()

	<-quit
	log.Info("shutting down gracefullyâ€¦")

	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	if err := srv.Shutdown(ctx); err != nil {
		log.Error("forced shutdown", zap.Error(err))
	}
	log.Info("server stopped")
}

func buildLogger(debug bool) *zap.Logger {
	level := zapcore.InfoLevel
	if debug {
		level = zapcore.DebugLevel
	}
	cfg := zap.NewProductionConfig()
	cfg.Level = zap.NewAtomicLevelAt(level)
	cfg.EncoderConfig.EncodeTime = zapcore.ISO8601TimeEncoder
	log, _ := cfg.Build()
	return log
}
