package router

import (
	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
	"github.com/nquire/ttsql/gateway/internal/config"
	"github.com/nquire/ttsql/gateway/internal/db"
	"github.com/nquire/ttsql/gateway/internal/handlers"
	"github.com/nquire/ttsql/gateway/internal/middleware"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"go.uber.org/zap"
)

// New builds and returns the configured Gin engine.
func New(cfg *config.Config, sqlDB *db.DB, log *zap.Logger) *gin.Engine {
	gin.SetMode(cfg.GinMode)

	r := gin.New()
	r.Use(middleware.Recovery(log))
	r.Use(middleware.ZapLogger(log))

	// CORS â€” allow all origins (same as Python FastAPI config)
	r.Use(cors.New(cors.Config{
		AllowAllOrigins:  true,
		AllowMethods:     []string{"GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"},
		AllowHeaders:     []string{"*"},
		ExposeHeaders:    []string{"Content-Length", "Content-Type"},
		AllowCredentials: false,
	}))

	// Prometheus metrics endpoint (native Go metrics)
	r.GET("/prometheus/metrics", gin.WrapH(promhttp.Handler()))

	// â”€â”€ Non-AI endpoints handled natively in Go â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
	api := r.Group("/api")
	{
		api.GET("/health", handlers.HealthHandler(cfg))

		// Auth — public, no JWT required
		api.POST("/auth/google", handlers.GoogleAuthHandler(cfg))

		api.GET("/metrics", handlers.MetricsHandler(cfg))
		api.GET("/databases", handlers.DatabasesHandler(cfg))

		// Results
		api.GET("/results/recent", handlers.ResultsRecentHandler(cfg))
		api.GET("/results/dates", handlers.ResultsDatesHandler(cfg, sqlDB))
		api.GET("/results/all", handlers.AllResultsHandler(cfg))
		api.GET("/results/:db_name", handlers.DBResultsHandler(cfg))
		api.DELETE("/runs/:date", handlers.DeleteRunHandler(cfg))

		// Details
		api.GET("/details/:db_name/:instance_id", handlers.DetailsHandler(cfg))

		// Diagnose (pure file regex, no LLM)
		api.GET("/diagnose/:db_name/:instance_id", handlers.DiagnoseHandler(cfg))
		api.GET("/diagnose/dab/:dataset/:query_id", handlers.DiagnoseDABHandler(cfg))

		// Accept/reject fix (pure file ops, no LLM)
		api.POST("/accept_fix/:db_name/:instance_id", handlers.AcceptFixHandler(cfg))
		api.POST("/reject_fix/:db_name/:instance_id", handlers.RejectFixHandler(cfg))
		api.POST("/accept_fix/dab/:dataset/:query_id", handlers.AcceptFixDABHandler(cfg))
		api.POST("/reject_fix/dab/:dataset/:query_id", handlers.RejectFixDABHandler(cfg))
	}

	// â”€â”€ AI/ML endpoints â€” proxy to Python FastAPI â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
	aiProxy := handlers.NewAIProxy(cfg.PythonAPIURL, log)

	// Explicit AI routes (proxied)
	api.POST("/demo/query", aiProxy)
	api.POST("/run_instance/:instance_id", aiProxy)
	api.POST("/run/:db_name", aiProxy)
	api.POST("/run_all", aiProxy)
	api.GET("/stream/:db_name/:instance_id", aiProxy)  // SSE
	api.GET("/live_execution/:db_name/:instance_id", aiProxy)
	api.GET("/status", aiProxy)
	api.GET("/evaluate/status", aiProxy)
	api.POST("/evaluate/all", aiProxy)
	api.POST("/fix_issues/:db_name/:instance_id", aiProxy)
	api.POST("/fix_issues/dab/:dataset/:query_id", aiProxy)
	api.POST("/stop", aiProxy)

	// DAB runner routes (proxied â€” they trigger AI pipeline)
	r.Any("/api/dab/*path", aiProxy)

	// Custom project routes (proxied â€” may have schema extraction with Python DB drivers)
	r.Any("/api/custom/*path", aiProxy)

	// Catch-all for any remaining /api/* routes not matched above â†’ proxy to Python
	r.NoRoute(func(c *gin.Context) {
		if len(c.Request.URL.Path) >= 4 && c.Request.URL.Path[:4] == "/api" {
			aiProxy(c)
			return
		}
		c.JSON(404, gin.H{"error": "not found"})
	})

	return r
}
