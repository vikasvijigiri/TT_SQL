// Package handlers – proxy.go
// Forwards AI/ML routes to the Python FastAPI service and transparently passes SSE streams.
package handlers

import (
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httputil"
	"net/url"
	"regexp"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
	"go.uber.org/zap"
)

// usernameSlugRe strips anything that isn't a lowercase letter, digit, underscore or dash.
var usernameSlugRe = regexp.MustCompile(`[^a-z0-9_\-]`)

// extractUsernameFromJWT reads the Bearer token from the Authorization header,
// parses (without verifying) the JWT claims, and returns a sanitized username slug
// derived from the email claim's local part (before @).
// Returns "" if no valid token / email is present.
func extractUsernameFromJWT(authHeader string) (username, email string) {
	if !strings.HasPrefix(authHeader, "Bearer ") {
		return "", ""
	}
	tokenStr := strings.TrimPrefix(authHeader, "Bearer ")
	// Parse without verification (gateway already validated the token earlier)
	p := jwt.NewParser()
	token, _, err := p.ParseUnverified(tokenStr, jwt.MapClaims{})
	if err != nil {
		return "", ""
	}
	claims, ok := token.Claims.(jwt.MapClaims)
	if !ok {
		return "", ""
	}
	emailRaw, _ := claims["email"].(string)
	email = emailRaw
	if emailRaw == "" {
		return "", ""
	}
	// Use the local part of the email as the username
	local := emailRaw
	if idx := strings.Index(emailRaw, "@"); idx > 0 {
		local = emailRaw[:idx]
	}
	slug := usernameSlugRe.ReplaceAllString(strings.ToLower(local), "")
	if slug == "" {
		slug = "anonymous"
	}
	return slug, emailRaw
}

// NewAIProxy returns a Gin handler that reverse-proxies every request to pythonBaseURL.
// SSE endpoints (URLs containing "/stream") are handled with a streaming-safe transport.
func NewAIProxy(pythonBaseURL string, log *zap.Logger) gin.HandlerFunc {
	target, err := url.Parse(pythonBaseURL)
	if err != nil {
		panic(fmt.Sprintf("invalid python API URL %q: %v", pythonBaseURL, err))
	}

	// Standard reverse proxy for non-streaming requests
	proxy := httputil.NewSingleHostReverseProxy(target)
	proxy.Transport = &http.Transport{
		DialContext: (&net.Dialer{
			Timeout:   10 * time.Second,
			KeepAlive: 30 * time.Second,
		}).DialContext,
		ResponseHeaderTimeout: 120 * time.Second,
		IdleConnTimeout:       90 * time.Second,
	}
	proxy.ErrorHandler = func(w http.ResponseWriter, r *http.Request, err error) {
		log.Warn("proxy error", zap.String("url", r.URL.String()), zap.Error(err))
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadGateway)
		fmt.Fprintf(w, `{"error":"Python AI service unreachable: %s"}`, err)
	}
	proxy.ModifyResponse = func(r *http.Response) error {
		// Disable gzip from upstream so Gin can re-compress if needed
		r.Header.Del("Content-Encoding")
		return nil
	}

	// SSE / streaming transport: no response timeout so connection stays open
	sseTransport := &http.Transport{
		DialContext: (&net.Dialer{
			Timeout:   10 * time.Second,
			KeepAlive: 30 * time.Second,
		}).DialContext,
		IdleConnTimeout: 0, // no idle timeout for long-lived SSE connections
	}
	sseClient := &http.Client{Transport: sseTransport, Timeout: 0}

	return func(c *gin.Context) {
		isSSE := strings.Contains(c.Request.URL.Path, "/stream")

		// Inject user identity headers so Python can scope data per user
		authHeader := c.Request.Header.Get("Authorization")
		if username, email := extractUsernameFromJWT(authHeader); username != "" {
			c.Request.Header.Set("X-Username", username)
			c.Request.Header.Set("X-User-Email", email)
		}

		if isSSE {
			handleSSE(c, target, sseClient, log)
			return
		}

		// Rewrite host to target
		c.Request.URL.Host = target.Host
		c.Request.URL.Scheme = target.Scheme
		c.Request.Header.Set("X-Forwarded-Host", c.Request.Host)
		c.Request.Header.Del("Accept-Encoding") // let proxy handle encoding
		proxy.ServeHTTP(c.Writer, c.Request)
	}
}


// handleSSE proxies a Server-Sent Events stream from Python to the client.
func handleSSE(c *gin.Context, target *url.URL, client *http.Client, log *zap.Logger) {
	upstreamURL := *target
	upstreamURL.Path = c.Request.URL.Path
	upstreamURL.RawQuery = c.Request.URL.RawQuery

	req, err := http.NewRequestWithContext(c.Request.Context(), c.Request.Method, upstreamURL.String(), c.Request.Body)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to build upstream request"})
		return
	}
	// Copy headers except hop-by-hop
	copyHeaders(req.Header, c.Request.Header)
	req.Header.Set("Accept", "text/event-stream")
	req.Header.Set("Cache-Control", "no-cache")

	resp, err := client.Do(req)
	if err != nil {
		log.Warn("SSE upstream error", zap.String("url", upstreamURL.String()), zap.Error(err))
		c.JSON(http.StatusBadGateway, gin.H{"error": "Python AI service unreachable for SSE"})
		return
	}
	defer resp.Body.Close()

	// Copy upstream response headers
	header := c.Writer.Header()
	for k, vv := range resp.Header {
		for _, v := range vv {
			header.Set(k, v)
		}
	}
	header.Set("Content-Type", "text/event-stream")
	header.Set("Cache-Control", "no-cache")
	header.Set("X-Accel-Buffering", "no")
	header.Set("Connection", "keep-alive")
	c.Writer.WriteHeader(resp.StatusCode)

	flusher, canFlush := c.Writer.(http.Flusher)
	buf := make([]byte, 4096)
	for {
		n, err := resp.Body.Read(buf)
		if n > 0 {
			c.Writer.Write(buf[:n])
			if canFlush {
				flusher.Flush()
			}
		}
		if err != nil {
			if err != io.EOF {
				log.Debug("SSE stream ended", zap.Error(err))
			}
			return
		}
	}
}

// hopByHop headers that should not be forwarded.
var hopHeaders = map[string]bool{
	"connection":          true,
	"keep-alive":          true,
	"proxy-authenticate":  true,
	"proxy-authorization": true,
	"te":                  true,
	"trailers":            true,
	"transfer-encoding":   true,
	"upgrade":             true,
}

func copyHeaders(dst, src http.Header) {
	for k, vv := range src {
		if hopHeaders[strings.ToLower(k)] {
			continue
		}
		for _, v := range vv {
			dst.Add(k, v)
		}
	}
}
