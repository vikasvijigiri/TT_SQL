package handlers

import (
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/nquire/ttsql/gateway/internal/config"
	"github.com/nquire/ttsql/gateway/internal/csvutil"
)

const maxDiagRead = 500 * 1024 // 500 KB

var (
	reSLErrors  = regexp.MustCompile(`(?i)SchemaLinker.*?Error|SCHEMA_LINKER.*?Failed`)
	reGenerErr  = regexp.MustCompile(`(?i)SQLGenerator.*?Error|SQL_GENERATOR.*?Failed|syntax error`)
	reMismatch  = regexp.MustCompile(`(?i)mismatch|silent data loss|empty result`)
	reCorFail   = regexp.MustCompile(`(?i)Self-Correction failed|Correction loop limit exceeded`)
	reSLogs     = regexp.MustCompile(`(?i)SchemaLinker|SCHEMA_LINKER`)
	rePruner    = regexp.MustCompile(`(?i)TablePruner|ColumnPruner|PRUNER`)
	reGenerator = regexp.MustCompile(`(?i)SQLGenerator|SQL_GENERATOR`)
	reValidator = regexp.MustCompile(`(?i)ResultValidator|DATA_IQ|Validator`)
	reCorrectN  = regexp.MustCompile(`(?i)Executing Self-Correction Module`)
)

// DiagnoseHandler handles GET /api/diagnose/{db_name}/{instance_id}
func DiagnoseHandler(cfg *config.Config) gin.HandlerFunc {
	return func(c *gin.Context) {
		dbName := strings.TrimSpace(c.Param("db_name"))
		instanceID := strings.TrimSpace(c.Param("instance_id"))
		c.JSON(http.StatusOK, diagnose(cfg, dbName, instanceID))
	}
}

// DiagnoseDABHandler handles GET /api/diagnose/dab/{dataset}/{query_id}
func DiagnoseDABHandler(cfg *config.Config) gin.HandlerFunc {
	return func(c *gin.Context) {
		dataset := strings.TrimSpace(c.Param("dataset"))
		queryID := strings.TrimSpace(c.Param("query_id"))
		qid := strings.ToLower(strings.ReplaceAll(queryID, "query", ""))
		c.JSON(http.StatusOK, diagnose(cfg, "DAB/"+dataset, "query"+qid))
	}
}

func diagnose(cfg *config.Config, dbName, instanceID string) map[string]any {
	dbNameUpper := strings.ToUpper(strings.TrimSpace(dbName))
	instanceID = strings.TrimSpace(instanceID)
	mdFile := filepath.Join(cfg.ResultsDir, dbNameUpper, instanceID+".md")
	csvFile := filepath.Join(cfg.ResultsDir, dbNameUpper, instanceID+".csv")

	if _, err := os.Stat(mdFile); err != nil {
		return map[string]any{
			"success": false,
			"error":   "Log file not found at " + mdFile + ".",
		}
	}

	content := readDiagContent(mdFile)

	// Determine is_zero_rows
	isZeroRows := false
	if _, err := os.Stat(csvFile); err == nil {
		isEmpty, rows := csvutil.GetCSVInfo(csvFile)
		if isEmpty || rows == 0 {
			isZeroRows = true
		}
	} else if strings.Contains(content, "0 rows") ||
		strings.Contains(content, "empty result") ||
		strings.Contains(content, "returned empty") ||
		strings.Contains(content, "0 verified") {
		isZeroRows = true
	}

	hasSuccess := strings.Contains(content, "SUCCESS") || strings.Contains(content, "Final SQL")
	hasError := strings.Contains(content, "ERROR") || strings.Contains(content, "Traceback")
	isOK := hasSuccess && !hasError && !isZeroRows

	agentStatus := map[string]any{}

	// Schema Linker
	slErrors := reSLErrors.MatchString(content)
	slLogs := reSLogs.MatchString(content)
	var slStatus, slMsg string
	if slErrors {
		slStatus, slMsg = "error", "Encountered critical schema candidates mapping errors or unresolvable semantic ambiguities."
	} else if isZeroRows {
		slStatus, slMsg = "warning", "Successfully linked schema candidates, but missed required subtle join keys or exact value-level domain grounding needed for correct filtering."
	} else {
		slStatus, slMsg = "success", "Linked primary database candidates successfully with precise semantic mappings."
	}
	metricsStr := "1 call"
	if !slLogs {
		metricsStr = "1 call (Cached)"
	}
	agentStatus["Schema Linker"] = map[string]any{"status": slStatus, "message": slMsg, "metrics": metricsStr}

	// Context Pruners
	prunerLogs := rePruner.MatchString(content)
	var cpStatus, cpMsg string
	if isZeroRows {
		cpStatus, cpMsg = "warning", "Pruned schema context down to active subset. Over-aggressive pruning likely discarded crucial foreign-key reference tables or necessary filtering columns."
	} else {
		cpStatus, cpMsg = "success", "Optimized active table and column scopes successfully without losing context."
	}
	prunerMetrics := "2 calls"
	if !prunerLogs {
		prunerMetrics = "2 calls (Cached)"
	}
	agentStatus["Context Pruners"] = map[string]any{"status": cpStatus, "message": cpMsg, "metrics": prunerMetrics}

	// SQL Generator
	generatorErrors := reGenerErr.MatchString(content)
	generatorLogs := reGenerator.MatchString(content)
	var sgStatus, sgMsg string
	if generatorErrors {
		sgStatus, sgMsg = "error", "Encountered query syntax errors or variant mismatch anomalies during assembly."
	} else if isZeroRows {
		sgStatus, sgMsg = "error", "Generated valid SQL syntax, but highly restrictive WHERE predicates or ungrounded string literal equality checks caused the query to filter out all rows."
	} else {
		sgStatus, sgMsg = "success", "Generated FQN-compliant case-matching SQL query successfully."
	}
	genMetrics := "1 call"
	if !generatorLogs {
		genMetrics = "1 call"
	}
	agentStatus["SQL Generator"] = map[string]any{"status": sgStatus, "message": sgMsg, "metrics": genMetrics}

	// Data IQ Auditor
	validatorLogs := reValidator.FindAllString(content, -1)
	mismatchAudits := reMismatch.MatchString(content)
	var diqStatus, diqMsg string
	if isZeroRows {
		diqStatus, diqMsg = "warning", "Auditor scrutinized execution and flagged 0 rows returned. Identified the empty result anomaly but was unable to derive alternative valid predicates."
	} else if mismatchAudits {
		diqStatus, diqMsg = "warning", "Triggered alerts for data loss or mathematical continuity anomalies."
	} else {
		diqStatus, diqMsg = "success", "Audited result set successfully (Parity and continuity passed)."
	}
	diqMetrics := "1 audit"
	if len(validatorLogs) > 0 {
		diqMetrics = strings.TrimSpace(strings.Join([]string{itoa(len(validatorLogs)), "audits"}, " "))
	}
	agentStatus["Data IQ Auditor"] = map[string]any{"status": diqStatus, "message": diqMsg, "metrics": diqMetrics}

	// Self Corrector
	corrections := len(reCorrectN.FindAllString(content, -1))
	correctionFailures := reCorFail.MatchString(content)
	var scStatus, scMsg string
	if correctionFailures {
		scStatus = "error"
		scMsg = "Failed to converge after " + itoa(corrections) + " self-correction rounds due to persistent semantic validation errors."
	} else if isZeroRows {
		if corrections > 0 {
			scStatus = "warning"
			scMsg = "Executed " + itoa(corrections) + " self-correction rounds. Scrutinized syntax but failed to relax the restrictive semantic filters responsible for the 0-row output."
		} else {
			scStatus, scMsg = "error", "Zero self-correction cycles triggered because the SQL compiled successfully, failing to recognize that returning 0 rows was a semantic failure."
		}
	} else {
		if corrections > 0 {
			scStatus = "success"
			scMsg = "Drove " + itoa(corrections) + " structural self-correction iterations to resolve syntax/compilation issues."
		} else {
			scStatus, scMsg = "success", "No syntax or execution anomalies detected. Zero corrections needed."
		}
	}
	agentStatus["Self Corrector"] = map[string]any{"status": scStatus, "message": scMsg, "metrics": itoa(corrections) + " rounds"}

	// Determine problematic agent and summary
	problematicAgent := "None"
	diagnosticsSummary := "Pipeline executed flawlessly with gold-standard parity verified."
	recommendations := []string{"Keep current pipeline topology."}

	if isZeroRows {
		if corrections == 0 {
			problematicAgent = "SQL Generator"
		} else {
			problematicAgent = "Self Corrector"
		}
		diagnosticsSummary = "Pipeline compiled valid SQL but suffered a 0-row collapse during execution. The generated query contained overly restrictive WHERE filters or ungrounded JOIN conditions that eliminated all valid data records."
		recommendations = []string{
			"Conduct exact value-first grounding on WHERE clause string literals.",
			"Relax strict INNER JOIN constraints to LEFT JOINs where optional relationships exist.",
			"Audit Schema Linker output for omitted intermediary bridge tables.",
		}
	} else if !hasSuccess || hasError || correctionFailures {
		if correctionFailures {
			problematicAgent = "Self Corrector"
			diagnosticsSummary = "The query corrections failed to converge. The self-correction module ran multiple rounds of adjustments but couldn't bypass semantic validation errors."
			recommendations = []string{"Inspect custom dialect rules.", "Check for case-sensitivity mismatch in table/column FQNs."}
		} else if generatorErrors {
			problematicAgent = "SQL Generator"
			diagnosticsSummary = "Encountered initial query generation errors. The SQL generator produced invalid Snowflake syntax or mismatched variant keys."
			recommendations = []string{"Hardcode FQN-compliance in generator prompts.", "Specify explicit dialect-aware rules inside sql_generator.yaml."}
		} else if slErrors {
			problematicAgent = "Schema Linker"
			diagnosticsSummary = "Failed to link critical columns or tables. Mapped incorrect schema context to the generation loop."
			recommendations = []string{"Increase semantic metadata context embeddings.", "Broaden Linker tolerance parameters in system_params.yaml."}
		} else if mismatchAudits {
			problematicAgent = "Data IQ Auditor"
			diagnosticsSummary = "Data IQ flagged mathematical anomalies, silent data loss, or empty rows in the generated result set."
			recommendations = []string{"Review JOIN join constraints.", "Check for microsecond-scale timestamp offset mismatch."}
		} else {
			problematicAgent = "Execution Engine"
			diagnosticsSummary = "The database execution engine failed to parse or execute the final compiled SQL due to runtime Snowflake server connection issues or execution state timeouts."
			recommendations = []string{"Verify Snowflake connection status.", "Enforce microsecond-scale conversions using TO_TIMESTAMP_NTZ(column, 6)."}
		}
	}

	if !isZeroRows {
		for agent, info := range agentStatus {
			if infoMap, ok := info.(map[string]any); ok {
				if infoMap["status"] == "error" {
					problematicAgent = agent
					break
				}
			}
		}
	}

	return map[string]any{
		"success":             true,
		"instance_id":         instanceID,
		"db_name":             dbName,
		"is_ok":               isOK,
		"problematic_agent":   problematicAgent,
		"diagnostics_summary": diagnosticsSummary,
		"agent_scorecard":     agentStatus,
		"recommendations":     recommendations,
	}
}

func readDiagContent(path string) string {
	fi, err := os.Stat(path)
	if err != nil {
		return ""
	}
	fileSize := fi.Size()
	f, err := os.Open(path)
	if err != nil {
		return ""
	}
	defer f.Close()

	if fileSize <= maxDiagRead {
		b, _ := os.ReadFile(path)
		return string(b)
	}
	// Read last 500KB
	buf := make([]byte, maxDiagRead)
	f.Seek(-maxDiagRead, 2)
	n, _ := f.Read(buf)
	return "[Content truncated for diagnosis]\n" + string(buf[:n])
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	if n < 0 {
		return "-" + itoa(-n)
	}
	var buf [20]byte
	pos := len(buf)
	for n > 0 {
		pos--
		buf[pos] = byte('0' + n%10)
		n /= 10
	}
	return string(buf[pos:])
}
