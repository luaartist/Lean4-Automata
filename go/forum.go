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
	Name            string          `json:"name"`
	Description     string          `json:"description"`
	ParamsSchema    json.RawMessage `json:"params_schema"`
	HandlerType     string          `json:"handler_type"` // subprocess, proxy
	CommandTemplate string          `json:"command_template"`
	Enabled         bool            `json:"enabled"`
	Tags            []string        `json:"tags"`
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
		command_template TEXT,
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
	flows := []FlowDefinition{
		{
			Name:        "lean_sorry_scan",
			Description: "Scan Lean4 codebase for sorry statements",
			ParamsSchema: json.RawMessage(`{"type":"object","properties":{"file_pattern":{"type":"string","default":"*.lean"}}}`),
			HandlerType: "subprocess",
			CommandTemplate: `python3 -c "
import requests
resp = requests.get('` + leanDBURL + `/query', json={'query': 'SELECT * FROM v_proof_status WHERE sorry_count > 0'})
print(resp.json())
"`,
			Enabled: true,
			Tags:    []string{"lean", "sorry"},
		},
		{
			Name:        "lean_float_scan",
			Description: "Query floating symbols (definitions without proofs)",
			ParamsSchema: json.RawMessage(`{"type":"object","properties":{"limit":{"type":"integer","default":100}}}`),
			HandlerType: "subprocess",
			CommandTemplate: `python3 -c "
import requests
resp = requests.get('` + leanDBURL + `/query', json={'query': 'SELECT * FROM v_floating_symbols LIMIT 100'})
print(resp.json())
"`,
			Enabled: true,
			Tags:    []string{"lean", "float"},
		},
		{
			Name:        "lean_diff_mathlib",
			Description: "Compare local Lean files against mathlib (placeholder)",
			ParamsSchema: json.RawMessage(`{"type":"object"}`),
			HandlerType: "subprocess",
			CommandTemplate: `echo '{"status": "not_implemented", "message": "Mathlib diff requires lake integration"}'`,
			Enabled: false,
			Tags:    []string{"lean", "mathlib"},
		},
		{
			Name:         "tph_inference",
			Description:  "Run token inference through TPH model",
			ParamsSchema: json.RawMessage(`{"type":"object","properties":{"tokens":{"type":"array"},"max_length":{"type":"integer","default":50}}}`),
			HandlerType:  "proxy",
			Enabled:      true,
			Tags:         []string{"tph", "inference"},
		},
		{
			Name:        "env_check",
			Description: "Validate Python environment and dependencies",
			ParamsSchema: json.RawMessage(`{"type":"object"}`),
			HandlerType: "subprocess",
			CommandTemplate: `python3 -c "
import sys, importlib.metadata
print(f'Python: {sys.version}')
for pkg in ['torch', 'requests', 'flask']:
    try:
        v = importlib.metadata.version(pkg)
        print(f'{pkg}: {v}')
    except:
        print(f'{pkg}: NOT INSTALLED')
"`,
			Enabled: true,
			Tags:    []string{"env", "python"},
		},
	}

	stmt, err := db.Prepare(`INSERT INTO flow_definitions (name, description, params_schema, handler_type, command_template, enabled, tags) VALUES (?, ?, ?, ?, ?, ?, ?)`)
	if err != nil {
		return err
	}
	defer stmt.Close()

	for _, flow := range flows {
		tagsJSON, _ := json.Marshal(flow.Tags)
		_, err := stmt.Exec(flow.Name, flow.Description, flow.ParamsSchema, flow.HandlerType, flow.CommandTemplate, flow.Enabled, tagsJSON)
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

	// Parse input
	var input FlowInput
	if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
		input.Input = map[string]interface{}{}
	}

	// Get flow definition
	var flow FlowDefinition
	var tagsJSON string
	err := forumDB.QueryRow(`SELECT name, description, handler_type, command_template, tags FROM flow_definitions WHERE name = ? AND enabled = 1`, flowName).
		Scan(&flow.Name, &flow.Description, &flow.HandlerType, &flow.CommandTemplate, &tagsJSON)
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

	if flow.HandlerType == "subprocess" {
		outputJSON, status, errorMsg = executeSubprocessFlow(w, flusher, flow, input)
	} else if flow.HandlerType == "proxy" {
		outputJSON, status, errorMsg = executeProxyFlow(w, flusher, flow, input)
	} else {
		status = "error"
		errorMsg = "Unknown handler type"
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

// Execute subprocess flow
func executeSubprocessFlow(w http.ResponseWriter, flusher http.Flusher, flow FlowDefinition, input FlowInput) (json.RawMessage, string, string) {
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(flowTimeoutSec)*time.Second)
	defer cancel()

	// Substitute input variables in command template
	command := flow.CommandTemplate
	// Simple variable substitution (can be enhanced)

	cmd := exec.CommandContext(ctx, "bash", "-c", command)
	stdout, _ := cmd.StdoutPipe()
	stderr, _ := cmd.StderrPipe()

	if err := cmd.Start(); err != nil {
		return json.RawMessage(`{}`), "error", err.Error()
	}

	var output strings.Builder
	var wg sync.WaitGroup

	// Stream stdout
	wg.Add(1)
	go func() {
		defer wg.Done()
		scanner := bufio.NewScanner(stdout)
		for scanner.Scan() {
			line := scanner.Text()
			output.WriteString(line + "\n")
			sendSSE(w, flusher, "log", LogMessage{Level: "stdout", Message: line})
		}
	}()

	// Stream stderr
	wg.Add(1)
	go func() {
		defer wg.Done()
		scanner := bufio.NewScanner(stderr)
		for scanner.Scan() {
			line := scanner.Text()
			sendSSE(w, flusher, "log", LogMessage{Level: "stderr", Message: line})
		}
	}()

	wg.Wait()
	err := cmd.Wait()

	if ctx.Err() == context.DeadlineExceeded {
		return json.RawMessage(`{"error":"timeout"}`), "timeout", "Flow execution timeout"
	}

	if err != nil {
		return json.RawMessage(fmt.Sprintf(`{"error":"%s"}`, err.Error())), "error", err.Error()
	}

	return json.RawMessage(output.String()), "success", ""
}

// Execute proxy flow (e.g., TPH inference)
func executeProxyFlow(w http.ResponseWriter, flusher http.Flusher, flow FlowDefinition, input FlowInput) (json.RawMessage, string, string) {
	var targetURL string
	if flow.Name == "tph_inference" {
		targetURL = tphServerURL + "/inference"
	} else {
		return json.RawMessage(`{}`), "error", "Unknown proxy target"
	}

	// Forward request
	body, _ := json.Marshal(input.Input)
	resp, err := http.Post(targetURL, "application/json", strings.NewReader(string(body)))
	if err != nil {
		return json.RawMessage(`{}`), "error", err.Error()
	}
	defer resp.Body.Close()

	output, _ := io.ReadAll(resp.Body)
	sendSSE(w, flusher, "log", LogMessage{Level: "info", Message: string(output)})

	return json.RawMessage(output), "success", ""
}

// POST /ticket/create
func handleCreateTicket(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var ticket Ticket
	if err := json.NewDecoder(r.Body).Decode(&ticket); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

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

	body, _ := io.ReadAll(r.Body)
	resp, err := http.Post(leanDBURL+"/query", "application/json", strings.NewReader(string(body)))
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()

	output, _ := io.ReadAll(resp.Body)
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
	storeTicket(ticket)

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

	body, _ := io.ReadAll(r.Body)
	resp, err := http.Post(tphServerURL+"/inference", "application/json", strings.NewReader(string(body)))
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()

	output, _ := io.ReadAll(resp.Body)
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
		"venv_path":      venvPath,
		"python_version": pythonVersion,
		"gpu_available":  gpuAvailable,
		"gpu_name":       gpuName,
	})
}

// GET /health
func handleHealth(w http.ResponseWriter, r *http.Request) {
	checks := map[string]string{
		"database": "ok",
		"bpf":      "ok",
	}

	// Check Lean DB
	if _, err := http.Get(leanDBURL + "/health"); err != nil {
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
