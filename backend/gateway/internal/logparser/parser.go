// Package logparser ports the Python _cached_parse_md_log logic to Go.
// It extracts execution metadata (latency, tokens, cost, complexity) from .md log files.
package logparser

import (
	"io"
	"math"
	"os"
	"regexp"
	"strconv"
	"strings"
	"time"
)

const (
	headRead = 32 * 1024 // 32 KB
	tailRead = 8 * 1024  // 8 KB
)

// LogData mirrors the dict returned by parse_md_log in Python.
type LogData struct {
	Latency         float64 `json:"latency"`
	Complexity      string  `json:"complexity"`
	ComplexityType  string  `json:"complexity_type"`
	ComplexityScore float64 `json:"complexity_score"`
	Corrections     int     `json:"corrections"`
	CriticRounds    int     `json:"critic_rounds"`
	Success         bool    `json:"success"`
	Error           bool    `json:"error"`
	TotalTokens     int     `json:"total_tokens"`
	Cost            float64 `json:"cost"`
}

var (
	reStart      = regexp.MustCompile(`--- EXECUTION STARTED AT (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ---`)
	reEnd        = regexp.MustCompile(`--- EXECUTION FINISHED AT (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ---`)
	reLatency    = regexp.MustCompile(`Latency:\s*(\d+\.\d+)s`)
	reComplexity = regexp.MustCompile(`"complexity":\s*"(\w+)"`)
	reCorrection = regexp.MustCompile(`Executing Self-Correction Module`)
	reCritic     = regexp.MustCompile(`Executing adversarial Planner-Critic`)
	reInputTok   = regexp.MustCompile(`(?:Final Sent Tokens|Total Tokens):\s*(\d+)`)
	reResponseBk = regexp.MustCompile(`(?m)^v RESPONSE\s*\n([\s\S]*?)(?:\n\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} -|$)`)
	reLogPrefix  = regexp.MustCompile(`^(?:\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} - [^ -]+ - [^ -]+ - )?\s*\|\s*`)
	reSQL        = regexp.MustCompile("(?s)```sql\n(.*?)\n```")
	reJoins      = regexp.MustCompile(`(?i)\bjoin\b`)
	reCTEs       = regexp.MustCompile(`(?i)\bwith\b`)
	reWindowFn   = regexp.MustCompile(`(?i)\bover\s*\(`)
	reAggs       = regexp.MustCompile(`(?i)\b(sum|avg|count|max|min|group by|having)\b`)
	reQuestion   = regexp.MustCompile(`(?is)(?:###\s*Question:|Question\s*:\s*)(.*?)(?:\n\n|\n\d{4}-\d{2}-\d{2}|$)`)
	tsFormat     = "2006-01-02 15:04:05"
)

// readLogSample reads the first headRead bytes + last tailRead bytes of a file,
// matching the Python _read_log_sample behaviour.
func readLogSample(path string) string {
	f, err := os.Open(path)
	if err != nil {
		return ""
	}
	defer f.Close()

	size, err := f.Seek(0, io.SeekEnd)
	if err != nil {
		return ""
	}

	if size <= int64(headRead+tailRead) {
		f.Seek(0, io.SeekStart)
		buf, _ := io.ReadAll(f)
		return string(buf)
	}

	f.Seek(0, io.SeekStart)
	head := make([]byte, headRead)
	headN, _ := f.Read(head)

	f.Seek(-int64(tailRead), io.SeekEnd)
	tail := make([]byte, tailRead)
	tailN, _ := f.Read(tail)

	return string(head[:headN]) + "\n" + string(tail[:tailN])
}

// ParseMDLog extracts execution metadata from a .md log file.
// Returns an empty LogData (not nil) if the file doesn't exist or can't be parsed.
func ParseMDLog(filePath string) LogData {
	content := readLogSample(filePath)
	if content == "" {
		return LogData{}
	}

	var latency float64
	if m := reStart.FindStringSubmatch(content); len(m) > 1 {
		if m2 := reEnd.FindStringSubmatch(content); len(m2) > 1 {
			t1, err1 := time.Parse(tsFormat, m[1])
			t2, err2 := time.Parse(tsFormat, m2[1])
			if err1 == nil && err2 == nil {
				latency = math.Round(t2.Sub(t1).Seconds()*10) / 10
			}
		}
	}
	if latency <= 0 {
		if m := reLatency.FindStringSubmatch(content); len(m) > 1 {
			if v, err := strconv.ParseFloat(m[1], 64); err == nil {
				latency = v
			}
		}
	}

	complexityClass := "linear_logic"
	if m := reComplexity.FindStringSubmatch(content); len(m) > 1 {
		complexityClass = strings.TrimSpace(m[1])
	}

	corrections := len(reCorrection.FindAllString(content, -1))
	criticRounds := len(reCritic.FindAllString(content, -1))

	hasError := strings.Contains(content, "ERROR") || strings.Contains(content, "Traceback")
	hasSuccess := strings.Contains(content, "SUCCESS") || strings.Contains(content, "Final SQL")

	// Parse input tokens
	var totalInputTokens int
	for _, m := range reInputTok.FindAllStringSubmatch(content, -1) {
		if v, err := strconv.Atoi(m[1]); err == nil {
			totalInputTokens += v
		}
	}

	// Parse output tokens from RESPONSE blocks
	var totalOutputTokens int
	for _, m := range reResponseBk.FindAllStringSubmatch(content, -1) {
		block := m[1]
		var cleanLines []string
		for _, line := range strings.Split(block, "\n") {
			cleaned := reLogPrefix.ReplaceAllString(line, "")
			cleanLines = append(cleanLines, cleaned)
		}
		blockText := strings.TrimSpace(strings.Join(cleanLines, "\n"))
		tokens := len(blockText) / 4
		if tokens < 1 {
			tokens = 1
		}
		totalOutputTokens += tokens
	}

	totalTokens := totalInputTokens + totalOutputTokens
	// Bedrock pricing for bedrock/openai.gpt-oss-safeguard-120b
	cost := float64(totalInputTokens)*0.15/1e6 + float64(totalOutputTokens)*0.60/1e6

	// Complexity scoring
	var complexityType string
	var baseScore float64
	switch complexityClass {
	case "linear_logic":
		baseScore, complexityType = 0.25, "Linear Logic (Easy)"
	case "relational_complexity":
		baseScore, complexityType = 0.55, "Relational Complexity (Medium)"
	case "forensic_depth":
		baseScore, complexityType = 0.85, "Forensic Depth (Complex)"
	default:
		baseScore, complexityType = 0.40, "Unclassified"
	}

	// Question factor
	var questionWords int
	if m := reQuestion.FindStringSubmatch(content); len(m) > 1 {
		questionWords = len(strings.Fields(strings.TrimSpace(m[1])))
	}
	if questionWords == 0 {
		questionWords = 20
	}
	qFactor := math.Min(0.12, float64(questionWords)/180.0)

	// SQL complexity factor
	var sqlText string
	if mAll := reSQL.FindAllStringSubmatch(content, -1); len(mAll) > 0 {
		sqlText = strings.ToLower(mAll[len(mAll)-1][1])
	}
	joins := float64(len(reJoins.FindAllString(sqlText, -1)))
	ctes := float64(len(reCTEs.FindAllString(sqlText, -1)))
	windowFns := float64(len(reWindowFn.FindAllString(sqlText, -1)))
	aggs := float64(len(reAggs.FindAllString(sqlText, -1)))
	sqlFactor := math.Min(0.18, joins*0.04+ctes*0.06+windowFns*0.06+aggs*0.015)

	var schemaFactor float64
	if totalInputTokens > 0 {
		schemaFactor = math.Min(0.10, float64(totalInputTokens)/60000.0)
	} else {
		schemaFactor = 0.03
	}

	var latencyFactor float64
	if latency > 0 {
		latencyFactor = math.Min(0.15, latency/1500.0)
	}

	complexityScore := math.Round(math.Min(1.0, math.Max(0.1,
		baseScore+qFactor+sqlFactor+schemaFactor+latencyFactor))*100) / 100

	return LogData{
		Latency:         latency,
		Complexity:      complexityClass,
		ComplexityType:  complexityType,
		ComplexityScore: complexityScore,
		Corrections:     corrections,
		CriticRounds:    criticRounds,
		Success:         hasSuccess,
		Error:           hasError && !hasSuccess,
		TotalTokens:     totalTokens,
		Cost:            cost,
	}
}
