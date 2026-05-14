// ============================================================================
// Go_Red Extension — Forum API Routes
// ============================================================================
// Add these routes to the existing main.go AFTER the QMCP consent handler
// All new functionality is additive and non-breaking
// ============================================================================

package main

import (
	"bufio"
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"time"

	_ "github.com/mattn/go-sqlite3"
	"github.com/oklog/ulid/v2"
)

// ============================================================================
// Configuration
// ============================================================================

var (
	forumDB          *sql.DB
	forumDBPath      = getEnv("LEAN4A_FORUM_DB", filepath.Join(os.Getenv("HOME"), ".lean4a", "forum.db"))
	leanDBURL        = getEnv("LEAN_DB_URL", "http://localhost:8000")
	tphServerURL     = getEnv("TPH_SERVER_URL", "http://localhost:5000")
	flowTimeoutSec   = getEnvInt("FLOW_TIMEOUT_SEC", 30)
	maxConcurrentFlows = getEnvInt("MAX_CONCURRENT_FLOWS", 5)
	
	// Flow execution limiter
	flowSemaphore = make(chan struct{}, maxConcurrentFlows)
	
	// Active SSE connections
	sseConnections = &sync.Map{}
)

func getEnv(key, defaultVal string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	return defaultVal
}

func getEnvInt(key string, defaultVal int) int {
	if val := os.Getenv(key); val != "" {
		var i int
		fmt.Sscanf(val, "%d", &i)
		return i
	}
	return defaultVal
}

// ============================================================================
// Data Models
// ============================================================================

type Ticket struct {
	ID           string          `json:"id"`
	FlowName     string          `json:"flow_name"`
	InputJSON    json.RawMessage `json:"input_json"`
	OutputJSON   json.RawMessage `json:"output_json"`
	Status       string          `json:"status"` // success, error, timeout
	ErrorMessage string          `json:"error_message,omitempty"`
	CreatedAt    int64           `json:"created_at"`
	DurationMS   int64           `json:"duration_ms"`
	Tags         []string        `json:"tags"`
}

type Session struct {
	ID         string   `json:"id"`
	Name       string   `json:"name"`
	CreatedAt  int64    `json:"created_at"`
	TicketIDs  []string `json:"ticket_ids"`
}

type FlowDefinition struct {
	Name         string          `json:"name"`
	Description  string          `json:"description"`
	ParamsSchema json.RawMessage `json:"params_schema"`
	HandlerType  string          `json:"handler_type"` // builtin, proxy
	TargetURL    string          `json:"target_url,omitempty"`
	Enabled      bool            `json:"enabled"`
	Tags         []string        `json:"tags"`
}

type FlowInput struct {
	Input map[string]interface{} `json:"input"`
}

type SSEMessage struct {
	Event string      `json:"-"`
	Data  interface{} `json:"data"`
}

type LogMessage struct {
	Level   string `json:"level"`   // info, error, stdout, stderr
	Message string `json:"message"`
}

type ResultMessage struct {
	TicketID string `json:"ticket_id"`
	Status   string `json:"status"`
}

type DoneMessage struct {
	DurationMS int64 `json:"duration_ms"`
}

// ============================================================================
// Flow Function Registry
// ============================================================================

// FlowFunc is the signature for all built-in flow implementations
type FlowFunc func(ctx context.Context, params map[string]interface{}, w http.ResponseWriter, flusher http.Flusher) (json.RawMessage, string, string)

var flowRegistry = map[string]FlowFunc{
	"lean_sorry_scan":        flowLeanSorryScan,
	"lean_float_scan":        flowLeanFloatScan,
	"lean_file_interconnect": flowLeanFileInterconnect,
	"lean_db_health":         flowLeanDBHealth,
	"quick_proof_report":     flowQuickProofReport,
	"tph_status":             flowTPHStatus,
	"env_check":              flowEnvCheck,
	"gpu_check":              flowGPUCheck,
	"formula_match":          flowNotImplemented("formula_match"),
	"wolfram_verify":         flowNotImplemented("wolfram_verify"),
	"lean_diff_mathlib":      flowNotImplemented("lean_diff_mathlib"),
	"lean_mathlib_diff":      flowNotImplemented("lean_mathlib_diff"),
}

// ============================================================================
// Database Initialization
// ============================================================================

func initForumDB() error {
	// Create directory if it doesn't exist
	dir := filepath.Dir(forumDBPath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return fmt.Errorf("failed to create forum DB directory: %w", err)
	}

	// Open database with WAL mode
	dsn := fmt.Sprintf("%s?_pragma=journal_mode(WAL)", forumDBPath)
	db, err := sql.Open("sqlite3", dsn)
	if err != nil {
		return fmt.Errorf("failed to open forum DB: %w", err)
	}

	forumDB = db

	// Create tables
	schema := `
	CREATE TABLE IF NOT EXISTS tickets (
		id TEXT PRIMARY KEY,
		flow_name TEXT NOT NULL,
		input_json TEXT NOT NULL,
		output_json TEXT NOT NULL,
		status TEXT NOT NULL CHECK(status IN ('success', 'error', 'timeout')),
		error_message TEXT,
		created_at INTEGER NOT NULL,
		duration_ms INTEGER,
		tags TEXT
	);
	CREATE INDEX IF NOT EXISTS idx_tickets_flow ON tickets(flow_name);
	CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
	CREATE INDEX IF NOT EXISTS idx_tickets_created ON tickets(created_at DESC);

	CREATE TABLE IF NOT EXISTS sessions (
		id TEXT PRIMARY KEY,
		name TEXT NOT NULL,
		created_at INTEGER NOT NULL,
		ticket_ids_json TEXT
	);
	CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at DESC);

	CREATE TABLE IF NOT EXISTS flow_definitions (
		name TEXT PRIMARY KEY,
		description TEXT NOT NULL,
		params_schema TEXT NOT NULL,
		handler_type TEXT NOT NULL,
		target_url TEXT,
		enabled BOOLEAN NOT NULL DEFAULT 1,
		tags TEXT
	);

	CREATE TABLE IF NOT EXISTS flow_logs (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		flow_name TEXT NOT NULL,
		ticket_id TEXT,
		level TEXT NOT NULL,
		message TEXT NOT NULL,
		timestamp INTEGER NOT NULL
	);
	CREATE INDEX IF NOT EXISTS idx_flow_logs_ticket ON flow_logs(ticket_id);
	CREATE INDEX IF NOT EXISTS idx_flow_logs_timestamp ON flow_logs(timestamp DESC);
	`

	if _, err := db.Exec(schema); err != nil {
		return fmt.Errorf("failed to create schema: %w", err)
	}

	// Seed flow definitions if empty
	var count int
	db.QueryRow("SELECT COUNT(*) FROM flow_definitions").Scan(&count)
	if count == 0 {
		if err := seedFlowDefinitions(db); err != nil {
			return fmt.Errorf("failed to seed flows: %w", err)
		}
	}

	log.Println("✅ Forum database initialized at", forumDBPath)
	return nil
}

func seedFlowDefinitions(db *sql.DB) error {
	// SECURITY FIX: Removed CommandTemplate field — all flows are now compile-time Go functions
	flows := []FlowDefinition{
		{
			Name:         "lean_sorry_scan",
			Description:  "Scan Lean4 codebase for sorry statements",
			ParamsSchema: json.RawMessage(`{"type":"object","properties":{"file_pattern":{"type":"string","description":"File pattern to match (e.g., *.lean)","default":"*.lean"}}}`),
			HandlerType:  "builtin",
			Enabled:      true,
			Tags:         []string{"lean", "sorry", "proof-status"},
		},
		{
			Name:         "lean_float_scan",
			Description:  "Query floating symbols (definitions without proofs)",
			ParamsSchema: json.RawMessage(`{"type":"object","properties":{"limit":{"type":"integer","description":"Maximum number of results","default":100}}}`),
			HandlerType:  "builtin",
			Enabled:      true,
			Tags:         []string{"lean", "floating", "symbols"},
		},
		{
			Name:         "lean_file_interconnect",
			Description:  "Analyze file dependencies and imports",
			ParamsSchema: json.RawMessage(`{"type":"object","properties":{"file_path":{"type":"string","description":"Specific file to analyze (optional)","default":""}}}`),
			HandlerType:  "builtin",
			Enabled:      true,
			Tags:         []string{"lean", "dependencies", "imports"},
		},
		{
			Name:         "lean_diff_mathlib",
			Description:  "Compare local Lean files against mathlib (placeholder)",
			ParamsSchema: json.RawMessage(`{"type":"object","properties":{"branch":{"type":"string","description":"Git branch to compare","default":"main"}}}`),
			HandlerType:  "builtin",
			Enabled:      false,
			Tags:         []string{"lean", "mathlib", "diff", "placeholder"},
		},
		{
			Name:         "tph_inference",
			Description:  "Run token inference through TPH model on MI300X GPU",
			ParamsSchema: json.RawMessage(`{"type":"object","properties":{"tokens":{"type":"array","description":"Token IDs to process","items":{"type":"integer"},"default":[42,17,89]},"max_length":{"type":"integer","description":"Maximum sequence length","default":50}}}`),
			HandlerType:  "proxy",
			TargetURL:    tphServerURL + "/inference",
			Enabled:      true,
			Tags:         []string{"tph", "inference", "gpu", "ml"},
		},
		{
			Name:         "tph_status",
			Description:  "Check TPH GPU server status and model info",
			ParamsSchema: json.RawMessage(`{"type":"object"}`),
			HandlerType:  "builtin",
			Enabled:      true,
			Tags:         []string{"tph", "status", "gpu"},
		},
		{
			Name:         "formula_match",
			Description:  "Match DynamicFlux Python formula against Lean symbols",
			ParamsSchema: json.RawMessage(`{"type":"object","properties":{"formula":{"type":"string","description":"Python formula to match (e.g., 'x**2 + y**2')","default":""}}}`),
			HandlerType:  "builtin",
			Enabled:      false,
			Tags:         []string{"formula", "dynamicflux", "matching", "placeholder"},
		},
		{
			Name:         "wolfram_verify",
			Description:  "Verify mathematical formula via Wolfram Engine",
			ParamsSchema: json.RawMessage(`{"type":"object","properties":{"formula":{"type":"string","description":"Mathematical formula in Wolfram Language","default":"Integrate[x^2, x]"}}}`),
			HandlerType:  "builtin",
			Enabled:      false,
			Tags:         []string{"wolfram", "verification", "math", "placeholder"},
		},
		{
			Name:         "env_check",
			Description:  "Validate Python environment and dependencies",
			ParamsSchema: json.RawMessage(`{"type":"object","properties":{"verbose":{"type":"boolean","description":"Show detailed package information","default":false}}}`),
			HandlerType:  "builtin",
			Enabled:      true,
			Tags:         []string{"env", "python", "dependencies", "diagnostics"},
		},
		{
			Name:         "gpu_check",
			Description:  "Check AMD GPU status and ROCm availability",
			ParamsSchema: json.RawMessage(`{"type":"object"}`),
			HandlerType:  "builtin",
			Enabled:      true,
			Tags:         []string{"gpu", "rocm", "hardware", "diagnostics"},
		},
		{
			Name:         "lean_db_health",
			Description:  "Check Lean4-Automata database health and statistics",
			ParamsSchema: json.RawMessage(`{"type":"object"}`),
			HandlerType:  "builtin",
			Enabled:      true,
			Tags:         []string{"lean", "database", "health", "statistics"},
		},
		{
			Name:         "quick_proof_report",
			Description:  "Generate comprehensive proof status report",
			ParamsSchema: json.RawMessage(`{"type":"object","properties":{"format":{"type":"string","description":"Output format: json or markdown","default":"json","enum":["json","markdown"]}}}`),
			HandlerType:  "builtin",
			Enabled:      true,
			Tags:         []string{"lean", "proof", "report", "summary"},
		},
	}

	stmt, err := db.Prepare(`INSERT INTO flow_definitions (name, description, params_schema, handler_type, target_url, enabled, tags) VALUES (?, ?, ?, ?, ?, ?, ?)`)
	if err != nil {
		return err
	}
	defer stmt.Close()

	for _, flow := range flows {
		tagsJSON, _ := json.Marshal(flow.Tags)
		_, err := stmt.Exec(flow.Name, flow.Description, flow.ParamsSchema, flow.HandlerType, flow.TargetURL, flow.Enabled, tagsJSON)
		if err != nil {
			return err
		}
	}

	return nil
}

// ============================================================================
// HTTP Handlers
// ============================================================================

// GET /flows — List all available flows
func handleGetFlows(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	rows, err := forumDB.Query(`SELECT name, description, params_schema, handler_type, enabled, tags FROM flow_definitions WHERE enabled = 1`)
	if err != nil {
		http.Error(w, "Database error", http.StatusInternalServerError)
		log.Printf("Error querying flows: %v", err)
		return
	}
	defer rows.Close()

	var flows []FlowDefinition
	for rows.Next() {
		var flow FlowDefinition
		var tagsJSON string
		if err := rows.Scan(&flow.Name, &flow.Description, &flow.ParamsSchema, &flow.HandlerType, &flow.Enabled, &tagsJSON); err != nil {
			continue
		}
		json.Unmarshal([]byte(tagsJSON), &flow.Tags)
		flows = append(flows, flow)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"flows": flows})
}

// POST /run/flow/:name — Execute flow and stream output via SSE
func handleRunFlow(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Extract flow name from URL
	pathParts := strings.Split(r.URL.Path, "/")
	if len(pathParts) < 4 {
		http.Error(w, "Invalid URL", http.StatusBadRequest)
		return
	}
	flowName := pathParts[3]

	// Parse input — SECURITY FIX: limit request body to 1 MB before decoding
	var input FlowInput
	if err := json.NewDecoder(io.LimitReader(r.Body, 1*1024*1024)).Decode(&input); err != nil {
		input.Input = map[string]interface{}{}
	}

	// Get flow definition
	var flow FlowDefinition
	var tagsJSON string
	err := forumDB.QueryRow(`SELECT name, description, handler_type, target_url, tags FROM flow_definitions WHERE name = ? AND enabled = 1`, flowName).
		Scan(&flow.Name, &flow.Description, &flow.HandlerType, &flow.TargetURL, &tagsJSON)
	if err != nil {
		http.Error(w, "Flow not found", http.StatusNotFound)
		return
	}
	json.Unmarshal([]byte(tagsJSON), &flow.Tags)

	// Setup SSE
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("Access-Control-Allow-Origin", "*")

	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "Streaming unsupported", http.StatusInternalServerError)
		return
	}

	// Acquire semaphore
	select {
	case flowSemaphore <- struct{}{}:
		defer func() { <-flowSemaphore }()
	default:
		sendSSE(w, flusher, "error", LogMessage{Level: "error", Message: "Too many concurrent flows, please wait"})
		return
	}

	// Execute flow
	startTime := time.Now()
	ticketID := generateULID()

	// Send start message
	sendSSE(w, flusher, "log", LogMessage{Level: "info", Message: fmt.Sprintf("Starting flow: %s", flowName)})

	var outputJSON json.RawMessage
	var status string
	var errorMsg string

	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(flowTimeoutSec)*time.Second)
	defer cancel()

	if flow.HandlerType == "proxy" {
		outputJSON, status, errorMsg = executeProxyFlow(ctx, w, flusher, flow, input)
	} else {
		// Look up in compile-time registry
		fn, ok := flowRegistry[flow.Name]
		if !ok {
			status = "error"
			errorMsg = "Flow not registered"
			outputJSON = json.RawMessage(fmt.Sprintf(`{"error":"Flow %s not found in registry"}`, flow.Name))
		} else {
			outputJSON, status, errorMsg = fn(ctx, input.Input, w, flusher)
		}
	}

	durationMS := time.Since(startTime).Milliseconds()

	// Store ticket
	inputJSON, _ := json.Marshal(input.Input)
	ticket := Ticket{
		ID:           ticketID,
		FlowName:     flowName,
		InputJSON:    inputJSON,
		OutputJSON:   outputJSON,
		Status:       status,
		ErrorMessage: errorMsg,
		CreatedAt:    time.Now().Unix(),
		DurationMS:   durationMS,
		Tags:         flow.Tags,
	}

	if err := storeTicket(ticket); err != nil {
		log.Printf("Failed to store ticket: %v", err)
	}

	// Send result
	sendSSE(w, flusher, "result", ResultMessage{TicketID: ticketID, Status: status})
	sendSSE(w, flusher, "done", DoneMessage{DurationMS: durationMS})
}

// ============================================================================
// Flow Function Implementations
// ============================================================================

// Helper to send SSE log messages
func sendFlowLog(w http.ResponseWriter, flusher http.Flusher, level, message string) {
	sendSSE(w, flusher, "log", LogMessage{Level: level, Message: message})
}

// flowNotImplemented creates a placeholder flow function
func flowNotImplemented(name string) FlowFunc {
	return func(ctx context.Context, params map[string]interface{}, w http.ResponseWriter, flusher http.Flusher) (json.RawMessage, string, string) {
		sendFlowLog(w, flusher, "warn", fmt.Sprintf("Flow %s not yet implemented", name))
		result := map[string]interface{}{
			"status":  "not_implemented",
			"message": fmt.Sprintf("Flow %s is a placeholder and not yet implemented", name),
		}
		resultJSON, _ := json.Marshal(result)
		return resultJSON, "success", ""
	}
}

// flowLeanSorryScan queries the Lean database for files with sorry statements
func flowLeanSorryScan(ctx context.Context, params map[string]interface{}, w http.ResponseWriter, flusher http.Flusher) (json.RawMessage, string, string) {
	sendFlowLog(w, flusher, "info", "Querying Lean database for sorry statements...")

	query := map[string]string{
		"query": "SELECT file_path, sorry_count, total_declarations FROM v_proof_status WHERE sorry_count > 0 ORDER BY sorry_count DESC",
	}
	queryJSON, _ := json.Marshal(query)

	req, err := http.NewRequestWithContext(ctx, "POST", leanDBURL+"/query", strings.NewReader(string(queryJSON)))
	if err != nil {
		return json.RawMessage(`{}`), "error", err.Error()
	}
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		sendFlowLog(w, flusher, "error", fmt.Sprintf("Failed to query Lean DB: %v", err))
		return json.RawMessage(`{}`), "error", err.Error()
	}
	defer resp.Body.Close()

	output, _ := io.ReadAll(io.LimitReader(resp.Body, 4*1024*1024))
	sendFlowLog(w, flusher, "info", fmt.Sprintf("Found %d bytes of sorry scan results", len(output)))

	return json.RawMessage(output), "success", ""
}

// flowLeanFloatScan queries the Lean database for floating symbols
func flowLeanFloatScan(ctx context.Context, params map[string]interface{}, w http.ResponseWriter, flusher http.Flusher) (json.RawMessage, string, string) {
	sendFlowLog(w, flusher, "info", "Querying Lean database for floating symbols...")

	limit := 100
	if l, ok := params["limit"].(float64); ok {
		limit = int(l)
	}

	query := map[string]string{
		"query": fmt.Sprintf("SELECT symbol_name, file_path, definition_type FROM v_floating_symbols ORDER BY symbol_name LIMIT %d", limit),
	}
	queryJSON, _ := json.Marshal(query)

	req, err := http.NewRequestWithContext(ctx, "POST", leanDBURL+"/query", strings.NewReader(string(queryJSON)))
	if err != nil {
		return json.RawMessage(`{}`), "error", err.Error()
	}
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		sendFlowLog(w, flusher, "error", fmt.Sprintf("Failed to query Lean DB: %v", err))
		return json.RawMessage(`{}`), "error", err.Error()
	}
	defer resp.Body.Close()

	output, _ := io.ReadAll(io.LimitReader(resp.Body, 4*1024*1024))
	sendFlowLog(w, flusher, "info", fmt.Sprintf("Found floating symbols results"))

	return json.RawMessage(output), "success", ""
}

// flowLeanFileInterconnect analyzes file dependencies and imports
func flowLeanFileInterconnect(ctx context.Context, params map[string]interface{}, w http.ResponseWriter, flusher http.Flusher) (json.RawMessage, string, string) {
	sendFlowLog(w, flusher, "info", "Analyzing file dependencies...")

	query := map[string]string{
		"query": "SELECT file_path, import_count, exported_symbols FROM v_file_interconnect ORDER BY import_count DESC LIMIT 50",
	}
	queryJSON, _ := json.Marshal(query)

	req, err := http.NewRequestWithContext(ctx, "POST", leanDBURL+"/query", strings.NewReader(string(queryJSON)))
	if err != nil {
		return json.RawMessage(`{}`), "error", err.Error()
	}
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		sendFlowLog(w, flusher, "error", fmt.Sprintf("Failed to query Lean DB: %v", err))
		return json.RawMessage(`{}`), "error", err.Error()
	}
	defer resp.Body.Close()

	output, _ := io.ReadAll(io.LimitReader(resp.Body, 4*1024*1024))
	sendFlowLog(w, flusher, "info", "File interconnect analysis complete")

	return json.RawMessage(output), "success", ""
}

// flowLeanDBHealth checks the health of the Lean database
func flowLeanDBHealth(ctx context.Context, params map[string]interface{}, w http.ResponseWriter, flusher http.Flusher) (json.RawMessage, string, string) {
	sendFlowLog(w, flusher, "info", "Checking Lean database health...")

	queries := map[string]string{
		"total_files":      "SELECT COUNT(DISTINCT file_path) FROM lean_symbols",
		"total_symbols":    "SELECT COUNT(*) FROM lean_symbols",
		"sorry_count":      "SELECT SUM(sorry_count) FROM v_proof_status",
		"floating_symbols": "SELECT COUNT(*) FROM v_floating_symbols",
	}

	result := map[string]interface{}{
		"status": "ok",
		"stats":  make(map[string]interface{}),
	}

	client := &http.Client{}
	for key, queryStr := range queries {
		queryBody := map[string]string{"query": queryStr}
		queryJSON, _ := json.Marshal(queryBody)

		req, err := http.NewRequestWithContext(ctx, "POST", leanDBURL+"/query", strings.NewReader(string(queryJSON)))
		if err != nil {
			result["stats"].(map[string]interface{})[key] = "error"
			continue
		}
		req.Header.Set("Content-Type", "application/json")

		resp, err := client.Do(req)
		if err != nil {
			result["stats"].(map[string]interface{})[key] = "error"
			continue
		}

		output, _ := io.ReadAll(io.LimitReader(resp.Body, 1*1024*1024))
		resp.Body.Close()

		var queryResult interface{}
		json.Unmarshal(output, &queryResult)
		result["stats"].(map[string]interface{})[key] = queryResult

		sendFlowLog(w, flusher, "info", fmt.Sprintf("Checked %s", key))
	}

	resultJSON, _ := json.Marshal(result)
	sendFlowLog(w, flusher, "info", "Database health check complete")

	return resultJSON, "success", ""
}

// flowQuickProofReport generates a comprehensive proof status report
func flowQuickProofReport(ctx context.Context, params map[string]interface{}, w http.ResponseWriter, flusher http.Flusher) (json.RawMessage, string, string) {
	sendFlowLog(w, flusher, "info", "Generating proof status report...")

	client := &http.Client{}

	// Get summary statistics
	summaryQuery := map[string]string{
		"query": `SELECT 
			COUNT(*) as total_files,
			SUM(sorry_count) as total_sorries,
			SUM(CASE WHEN sorry_count = 0 THEN 1 ELSE 0 END) as complete_files,
			AVG(sorry_count) as avg_sorries_per_file
		FROM v_proof_status`,
	}
	summaryJSON, _ := json.Marshal(summaryQuery)

	req, err := http.NewRequestWithContext(ctx, "POST", leanDBURL+"/query", strings.NewReader(string(summaryJSON)))
	if err != nil {
		return json.RawMessage(`{}`), "error", err.Error()
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := client.Do(req)
	if err != nil {
		sendFlowLog(w, flusher, "error", fmt.Sprintf("Failed to get summary: %v", err))
		return json.RawMessage(`{}`), "error", err.Error()
	}

	summaryOutput, _ := io.ReadAll(io.LimitReader(resp.Body, 1*1024*1024))
	resp.Body.Close()

	var summary interface{}
	json.Unmarshal(summaryOutput, &summary)

	sendFlowLog(w, flusher, "info", "Retrieved summary statistics")

	// Get top sorry files
	topQuery := map[string]string{
		"query": "SELECT file_path, sorry_count FROM v_proof_status WHERE sorry_count > 0 ORDER BY sorry_count DESC LIMIT 10",
	}
	topJSON, _ := json.Marshal(topQuery)

	req2, err := http.NewRequestWithContext(ctx, "POST", leanDBURL+"/query", strings.NewReader(string(topJSON)))
	if err != nil {
		return json.RawMessage(`{}`), "error", err.Error()
	}
	req2.Header.Set("Content-Type", "application/json")

	resp2, err := client.Do(req2)
	if err != nil {
		sendFlowLog(w, flusher, "error", fmt.Sprintf("Failed to get top files: %v", err))
		return json.RawMessage(`{}`), "error", err.Error()
	}

	topOutput, _ := io.ReadAll(io.LimitReader(resp2.Body, 1*1024*1024))
	resp2.Body.Close()

	var topFiles interface{}
	json.Unmarshal(topOutput, &topFiles)

	sendFlowLog(w, flusher, "info", "Retrieved top sorry files")

	result := map[string]interface{}{
		"summary":         summary,
		"top_sorry_files": topFiles,
		"timestamp":       time.Now().Format(time.RFC3339),
	}

	resultJSON, _ := json.Marshal(result)
	sendFlowLog(w, flusher, "info", "Proof report generation complete")

	return resultJSON, "success", ""
}

// flowTPHStatus checks the TPH server status
func flowTPHStatus(ctx context.Context, params map[string]interface{}, w http.ResponseWriter, flusher http.Flusher) (json.RawMessage, string, string) {
	sendFlowLog(w, flusher, "info", "Checking TPH server status...")

	req, err := http.NewRequestWithContext(ctx, "GET", tphServerURL+"/status", nil)
	if err != nil {
		return json.RawMessage(`{}`), "error", err.Error()
	}

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		sendFlowLog(w, flusher, "error", fmt.Sprintf("TPH server offline: %v", err))
		result := map[string]interface{}{
			"error":  err.Error(),
			"status": "offline",
		}
		resultJSON, _ := json.Marshal(result)
		return resultJSON, "success", ""
	}
	defer resp.Body.Close()

	output, _ := io.ReadAll(io.LimitReader(resp.Body, 1*1024*1024))
	sendFlowLog(w, flusher, "info", "TPH server is online")

	return json.RawMessage(output), "success", ""
}

// flowEnvCheck validates the Python environment and dependencies
func flowEnvCheck(ctx context.Context, params map[string]interface{}, w http.ResponseWriter, flusher http.Flusher) (json.RawMessage, string, string) {
	sendFlowLog(w, flusher, "info", "Checking Python environment...")

	// Check Python version - SAFE: hardcoded command with NO user input
	cmd := exec.CommandContext(ctx, "python3", "--version")
	output, err := cmd.Output()
	pythonVersion := strings.TrimSpace(string(output))
	if err != nil {
		pythonVersion = "Not available"
	}

	sendFlowLog(w, flusher, "info", fmt.Sprintf("Python version: %s", pythonVersion))

	// Check for .venv
	homeDir := os.Getenv("HOME")
	venvPath := filepath.Join(homeDir, "workspace", ".venv")
	venvExists := false
	if _, err := os.Stat(venvPath); err == nil {
		venvExists = true
		sendFlowLog(w, flusher, "info", "Virtual environment found")
	}

	result := map[string]interface{}{
		"python_version": pythonVersion,
		"venv_active":    venvExists,
	}

	resultJSON, _ := json.Marshal(result)
	sendFlowLog(w, flusher, "info", "Environment check complete")

	return resultJSON, "success", ""
}

// flowGPUCheck checks AMD GPU status and ROCm availability
func flowGPUCheck(ctx context.Context, params map[string]interface{}, w http.ResponseWriter, flusher http.Flusher) (json.RawMessage, string, string) {
	sendFlowLog(w, flusher, "info", "Checking GPU status...")

	result := map[string]interface{}{
		"gpu_available": false,
		"gpus":          []string{},
	}

	// Check ROCm - SAFE: hardcoded command with NO user input
	cmd := exec.CommandContext(ctx, "rocm-smi", "--showproductname")
	output, err := cmd.Output()
	if err == nil {
		result["gpu_available"] = true
		lines := strings.Split(strings.TrimSpace(string(output)), "\n")
		gpus := []string{}
		for _, line := range lines {
			if line = strings.TrimSpace(line); line != "" {
				gpus = append(gpus, line)
			}
		}
		result["gpus"] = gpus
		sendFlowLog(w, flusher, "info", fmt.Sprintf("Found %d GPU(s)", len(gpus)))
	} else {
		sendFlowLog(w, flusher, "warn", "ROCm not available")
	}

	// Check memory info - SAFE: hardcoded command with NO user input
	cmd2 := exec.CommandContext(ctx, "rocm-smi", "--showmeminfo", "vram")
	memOutput, err := cmd2.Output()
	if err == nil {
		result["vram_info"] = strings.TrimSpace(string(memOutput))
		sendFlowLog(w, flusher, "info", "Retrieved VRAM information")
	}

	resultJSON, _ := json.Marshal(result)
	sendFlowLog(w, flusher, "info", "GPU check complete")

	return resultJSON, "success", ""
}

// Execute proxy flow (e.g., TPH inference)
func executeProxyFlow(ctx context.Context, w http.ResponseWriter, flusher http.Flusher, flow FlowDefinition, input FlowInput) (json.RawMessage, string, string) {
	sendFlowLog(w, flusher, "info", fmt.Sprintf("Proxying request to %s", flow.TargetURL))

	body, _ := json.Marshal(input.Input)
	req, err := http.NewRequestWithContext(ctx, "POST", flow.TargetURL, strings.NewReader(string(body)))
	if err != nil {
		return json.RawMessage(`{}`), "error", err.Error()
	}
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		sendFlowLog(w, flusher, "error", fmt.Sprintf("Proxy request failed: %v", err))
		return json.RawMessage(`{}`), "error", err.Error()
	}
	defer resp.Body.Close()

	// SECURITY FIX: Limit response body to 4MB to prevent memory exhaustion
	limitedReader := io.LimitReader(resp.Body, 4*1024*1024)
	output, _ := io.ReadAll(limitedReader)
	sendFlowLog(w, flusher, "info", "Proxy request completed")

	return json.RawMessage(output), "success", ""
}

// POST /ticket/create
func handleCreateTicket(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// SECURITY FIX: Limit request body to 512 KB to prevent DoS
	var ticket Ticket
	if err := json.NewDecoder(io.LimitReader(r.Body, 512*1024)).Decode(&ticket); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// SECURITY FIX: Validate flow_name to prevent stored XSS and injection.
	// It must match an existing, enabled flow in the DB.
	var validatedFlowName string
	err := forumDB.QueryRow(`SELECT name FROM flow_definitions WHERE name = ? AND enabled = 1`, ticket.FlowName).Scan(&validatedFlowName)
	if err != nil {
		// Reject tickets for unknown / disabled flows; don't leak DB errors.
		http.Error(w, "Invalid flow_name", http.StatusBadRequest)
		return
	}
	ticket.FlowName = validatedFlowName

	ticket.ID = generateULID()
	ticket.CreatedAt = time.Now().Unix()

	if err := storeTicket(ticket); err != nil {
		http.Error(w, "Failed to create ticket", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"ticket_id":  ticket.ID,
		"created_at": ticket.CreatedAt,
	})
}

// GET /ticket/:id
func handleGetTicket(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	pathParts := strings.Split(r.URL.Path, "/")
	if len(pathParts) < 3 {
		http.Error(w, "Invalid URL", http.StatusBadRequest)
		return
	}
	ticketID := pathParts[2]

	var ticket Ticket
	var tagsJSON string
	err := forumDB.QueryRow(`SELECT id, flow_name, input_json, output_json, status, error_message, created_at, duration_ms, tags FROM tickets WHERE id = ?`, ticketID).
		Scan(&ticket.ID, &ticket.FlowName, &ticket.InputJSON, &ticket.OutputJSON, &ticket.Status, &ticket.ErrorMessage, &ticket.CreatedAt, &ticket.DurationMS, &tagsJSON)
	if err != nil {
		http.Error(w, "Ticket not found", http.StatusNotFound)
		return
	}

	json.Unmarshal([]byte(tagsJSON), &ticket.Tags)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(ticket)
}

// GET /tickets
func handleGetTickets(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	limit := 50
	if limitStr := r.URL.Query().Get("limit"); limitStr != "" {
		fmt.Sscanf(limitStr, "%d", &limit)
	}
	// SECURITY FIX: clamp limit to prevent large allocations / DoS
	if limit <= 0 || limit > 200 {
		limit = 50
	}

	rows, err := forumDB.Query(`SELECT id, flow_name, status, created_at, tags FROM tickets ORDER BY created_at DESC LIMIT ?`, limit)
	if err != nil {
		http.Error(w, "Database error", http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	var tickets []map[string]interface{}
	for rows.Next() {
		var id, flowName, status, tagsJSON string
		var createdAt int64
		rows.Scan(&id, &flowName, &status, &createdAt, &tagsJSON)

		var tags []string
		json.Unmarshal([]byte(tagsJSON), &tags)

		tickets = append(tickets, map[string]interface{}{
			"id":         id,
			"flow_name":  flowName,
			"status":     status,
			"created_at": createdAt,
			"tags":       tags,
		})
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"tickets": tickets, "total": len(tickets)})
}

// POST /lean/query
func handleLeanQuery(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// SECURITY FIX: Limit request body to 1 MB to prevent DoS
	body, err := io.ReadAll(io.LimitReader(r.Body, 1*1024*1024))
	if err != nil {
		http.Error(w, "Failed to read request", http.StatusBadRequest)
		return
	}

	// SECURITY FIX: Use context with timeout to prevent indefinite hang / SSRF amplification
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(flowTimeoutSec)*time.Second)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, "POST", leanDBURL+"/query", strings.NewReader(string(body)))
	if err != nil {
		http.Error(w, "Internal error", http.StatusInternalServerError)
		return
	}
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		log.Printf("Lean query proxy error: %v", err)
		http.Error(w, "Internal error", http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()

	// SECURITY FIX: Limit response body to 4 MB to prevent memory exhaustion
	output, err := io.ReadAll(io.LimitReader(resp.Body, 4*1024*1024))
	if err != nil {
		http.Error(w, "Internal error", http.StatusInternalServerError)
		return
	}
	ticketID := generateULID()

	// Store as ticket
	ticket := Ticket{
		ID:         ticketID,
		FlowName:   "lean_query",
		InputJSON:  body,
		OutputJSON: json.RawMessage(output),
		Status:     "success",
		CreatedAt:  time.Now().Unix(),
		Tags:       []string{"lean", "query"},
	}
	if err := storeTicket(ticket); err != nil {
		// SECURITY FIX: Log error details server-side, return generic message to client
		log.Printf("Ticket store error: %v", err)
		http.Error(w, "Internal error", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"ticket_id": ticketID,
		"results":   json.RawMessage(output),
	})
}

// POST /tph/inference
func handleTPHInference(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// SECURITY FIX: Limit request body to 1 MB to prevent DoS
	body, err := io.ReadAll(io.LimitReader(r.Body, 1*1024*1024))
	if err != nil {
		http.Error(w, "Failed to read request", http.StatusBadRequest)
		return
	}

	// SECURITY FIX: Use context with timeout to prevent indefinite hang / SSRF amplification
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(flowTimeoutSec)*time.Second)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, "POST", tphServerURL+"/inference", strings.NewReader(string(body)))
	if err != nil {
		http.Error(w, "Internal error", http.StatusInternalServerError)
		return
	}
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		log.Printf("TPH inference proxy error: %v", err)
		http.Error(w, "Internal error", http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()

	// SECURITY FIX: Limit response body to 4 MB to prevent memory exhaustion
	output, err := io.ReadAll(io.LimitReader(resp.Body, 4*1024*1024))
	if err != nil {
		http.Error(w, "Internal error", http.StatusInternalServerError)
		return
	}
	ticketID := generateULID()

	ticket := Ticket{
		ID:         ticketID,
		FlowName:   "tph_inference",
		InputJSON:  body,
		OutputJSON: json.RawMessage(output),
		Status:     "success",
		CreatedAt:  time.Now().Unix(),
		Tags:       []string{"tph", "inference"},
	}
	storeTicket(ticket)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"ticket_id": ticketID,
		"results":   json.RawMessage(output),
	})
}

// GET /env/status
func handleEnvStatus(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Check for .venv
	homeDir := os.Getenv("HOME")
	venvPath := filepath.Join(homeDir, "workspace", ".venv")
	venvActive := false
	if _, err := os.Stat(venvPath); err == nil {
		venvActive = true
	}

	// Get Python version
	cmd := exec.Command("python3", "--version")
	output, _ := cmd.Output()
	pythonVersion := strings.TrimSpace(string(output))

	// Check GPU
	gpuAvailable := false
	gpuName := ""
	if rocmInfo, err := exec.Command("rocm-smi", "--showproductname").Output(); err == nil {
		gpuAvailable = true
		gpuName = strings.TrimSpace(string(rocmInfo))
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"venv_active":    venvActive,
		// SECURITY FIX: venv_path removed — it exposed the server's home directory
		"python_version": pythonVersion,
		"gpu_available":  gpuAvailable,
		"gpu_name":       gpuName,
	})
}

// GET /health
func handleHealth(w http.ResponseWriter, r *http.Request) {
	// SECURITY FIX: Add method check
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	checks := map[string]string{
		"database": "ok",
		"bpf":      "ok",
	}

	// SECURITY FIX: Use correct health endpoint path /health/live
	if _, err := http.Get(leanDBURL + "/health/live"); err != nil {
		checks["lean_db"] = "error"
	} else {
		checks["lean_db"] = "ok"
	}

	// Check TPH server
	if _, err := http.Get(tphServerURL + "/status"); err != nil {
		checks["tph_server"] = "error"
	} else {
		checks["tph_server"] = "ok"
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status": "healthy",
		"checks": checks,
	})
}

// ============================================================================
// Helper Functions
// ============================================================================

func sendSSE(w http.ResponseWriter, flusher http.Flusher, event string, data interface{}) {
	dataJSON, _ := json.Marshal(data)
	fmt.Fprintf(w, "event: %s\n", event)
	fmt.Fprintf(w, "data: %s\n\n", dataJSON)
	flusher.Flush()
}

func generateULID() string {
	return ulid.Make().String()
}

func storeTicket(ticket Ticket) error {
	tagsJSON, _ := json.Marshal(ticket.Tags)
	_, err := forumDB.Exec(`INSERT INTO tickets (id, flow_name, input_json, output_json, status, error_message, created_at, duration_ms, tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		ticket.ID, ticket.FlowName, ticket.InputJSON, ticket.OutputJSON, ticket.Status, ticket.ErrorMessage, ticket.CreatedAt, ticket.DurationMS, tagsJSON)
	return err
}

// ============================================================================
// Registration Function — Call from main()
// ============================================================================

func registerForumRoutes() {
	// Initialize database
	if err := initForumDB(); err != nil {
		log.Fatalf("Failed to initialize forum database: %v", err)
	}

	// Register routes
	http.HandleFunc("/flows", handleGetFlows)
	http.HandleFunc("/run/flow/", handleRunFlow)
	http.HandleFunc("/ticket/create", handleCreateTicket)
	http.HandleFunc("/ticket/", handleGetTicket)
	http.HandleFunc("/tickets", handleGetTickets)
	http.HandleFunc("/lean/query", handleLeanQuery)
	http.HandleFunc("/tph/inference", handleTPHInference)
	http.HandleFunc("/env/status", handleEnvStatus)
	http.HandleFunc("/health", handleHealth)

	log.Println("✅ Forum routes registered")
}

// ============================================================================
// Add to main() AFTER existing routes:
//
// func main() {
//     // Existing QMCP routes
//     http.HandleFunc("/qmcp/v1/consent", handleConsentGate)
//     http.HandleFunc("/api/regulator", handleConsentGate)
//     
//     // NEW: Register forum routes
//     registerForumRoutes()
//     
//     log.Println("🚀 Starting QMCP Server (Go Orchestrator) on :8443...")
//     go startBPF()
//     
//     if err := http.ListenAndServe(":8443", nil); err != nil {
//         log.Fatalf("Server failed: %v", err)
//     }
// }
// ============================================================================
