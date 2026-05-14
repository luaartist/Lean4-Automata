# Lean4-Automata Forum — Integration Guide

## Quick Start

### 1. Prerequisites

Ensure you have:
- Go 1.21+ installed
- SQLite 3.35+ with WAL support
- Python 3.11+ with venv
- Lean4-Automata DB running on `localhost:8000`
- TPH GPU server running on `localhost:5000`

### 2. Install Go Dependencies

```bash
cd /mnt/doscratch/Work/AMD_COMPETITION_MVP/vessel-production/Go_Red

# Add required dependencies to go.mod
go get github.com/mattn/go-sqlite3
go get github.com/oklog/ulid/v2
```

### 3. Integrate Go_Red Extension

**Option A: Merge into existing main.go**

Add the following to your existing `main.go` AFTER the QMCP consent handler setup:

```go
import (
    // ... existing imports ...
    "database/sql"
    "context"
    "bufio"
    "os/exec"
    
    _ "github.com/mattn/go-sqlite3"
    "github.com/oklog/ulid/v2"
)

func main() {
    // Existing QMCP routes
    http.HandleFunc("/qmcp/v1/consent", handleConsentGate)
    http.HandleFunc("/api/regulator", handleConsentGate)
    
    // NEW: Register forum routes
    registerForumRoutes()
    
    // Serve HTML UI
    http.HandleFunc("/forum", serveForumHTML)
    
    log.Println("🚀 Starting QMCP Server (Go Orchestrator) on :8443...")
    go startBPF()
    
    if err := http.ListenAndServe(":8443", nil); err != nil {
        log.Fatalf("Server failed: %v", err)
    }
}

func serveForumHTML(w http.ResponseWriter, r *http.Request) {
    http.ServeFile(w, r, "/path/to/lean4a_forum.html")
}
```

**Option B: Copy entire go_red_extension.go into your project**

```bash
# Copy the extension file
cp go_red_extension.go /mnt/doscratch/Work/AMD_COMPETITION_MVP/vessel-production/Go_Red/forum.go

# Then add to main.go:
# func main() {
#     http.HandleFunc("/qmcp/v1/consent", handleConsentGate)
#     registerForumRoutes()  // NEW LINE
#     ...
# }
```

### 4. Setup SQLite Database

The database is automatically created on first startup, but you can pre-initialize:

```bash
export LEAN4A_FORUM_DB="$HOME/.lean4a/forum.db"
mkdir -p "$HOME/.lean4a"

# Optional: Pre-create with schema
sqlite3 "$LEAN4A_FORUM_DB" < forum_schema.sql
```

### 5. Deploy HTML Interface

```bash
# Copy HTML to web-accessible location
cp lean4a_forum.html /mnt/doscratch/Work/AMD_COMPETITION_MVP/vessel-production/Go_Red/static/

# Or serve directly from Go (add route in main.go):
# http.HandleFunc("/forum", func(w http.ResponseWriter, r *http.Request) {
#     http.ServeFile(w, r, "lean4a_forum.html")
# })
```

### 6. Start the Server

```bash
cd /mnt/doscratch/Work/AMD_COMPETITION_MVP/vessel-production/Go_Red

# Set environment variables
export LEAN4A_FORUM_DB="$HOME/.lean4a/forum.db"
export LEAN_DB_URL="http://localhost:8000"
export TPH_SERVER_URL="http://localhost:5000"
export FLOW_TIMEOUT_SEC=30
export MAX_CONCURRENT_FLOWS=5

# Build and run
go build -o go_red
sudo ./go_red  # sudo needed for BPF
```

### 7. Access the UI

Open browser to: `http://localhost:8443/forum`

---

## Architecture Integration Points

### A. Existing Go_Red Components

The extension **does not modify** existing functionality:
- ✅ BPF F-Regulator kernel map remains unchanged
- ✅ QMCP consent gate `/qmcp/v1/consent` still works
- ✅ Existing `internal/registry/detachable_bridge.go` pattern reused

### B. New Components Added

1. **Flow Execution Engine**
   - Spawns subprocesses with timeout
   - Streams output via Server-Sent Events (SSE)
   - Limits concurrent executions via semaphore

2. **Ticket Storage**
   - SQLite database in WAL mode (same pattern as bridge.go)
   - Local-first: findings never leave machine
   - ULID-based IDs for chronological sorting

3. **Proxy Handlers**
   - `/lean/query` → Lean4-Automata DB
   - `/tph/inference` → TPH GPU server
   - Results stored as tickets

4. **HTML Forum Interface**
   - Single-file, no build step
   - Bootstrap 5 + Font Awesome (matches existing TPH UIs)
   - Real-time SSE log streaming

---

## Flow Definitions

Flows are stored in `flow_definitions` table and loaded at startup. To add a custom flow:

### Via SQL

```sql
INSERT INTO flow_definitions (name, description, params_schema, handler_type, command_template, enabled, tags)
VALUES (
    'my_custom_flow',
    'My custom analysis flow',
    '{"type":"object","properties":{"input":{"type":"string"}}}',
    'subprocess',
    'python3 /path/to/my_script.py',
    1,
    '["custom", "analysis"]'
);
```

### Via JSON (for bulk loading)

Edit `flow_definitions.json` and reload:

```bash
sqlite3 "$LEAN4A_FORUM_DB" <<EOF
DELETE FROM flow_definitions;
.mode json
.import flow_definitions.json flow_definitions
EOF
```

---

## Connecting to Lean4-Automata DB

The forum expects Lean4-Automata Postgres DB to expose these views:

### Required Views

1. **v_proof_status** — File-level proof completion metrics
   ```sql
   CREATE VIEW v_proof_status AS
   SELECT 
       file_path,
       COUNT(*) as total_declarations,
       SUM(CASE WHEN has_sorry THEN 1 ELSE 0 END) as sorry_count,
       ROUND(100.0 * SUM(CASE WHEN NOT has_sorry THEN 1 ELSE 0 END) / COUNT(*), 2) as completion_pct
   FROM lean_symbols
   GROUP BY file_path;
   ```

2. **v_floating_symbols** — Definitions without proofs
   ```sql
   CREATE VIEW v_floating_symbols AS
   SELECT symbol_name, file_path, definition_type
   FROM lean_symbols
   WHERE definition_type IN ('def', 'theorem', 'lemma')
     AND NOT has_proof;
   ```

3. **v_file_interconnect** — Import dependencies
   ```sql
   CREATE VIEW v_file_interconnect AS
   SELECT 
       file_path,
       COUNT(DISTINCT imported_from) as import_count,
       json_agg(DISTINCT exported_symbol) as exported_symbols
   FROM lean_imports
   GROUP BY file_path;
   ```

### API Endpoints Expected

```
GET http://localhost:8000/query
POST body: {"query": "SELECT * FROM v_proof_status"}

GET http://localhost:8000/health
Response: {"status": "ok"}
```

---

## Connecting to TPH GPU Server

The forum expects TPH GPU server (tph_gpu_server.py) at `localhost:5000`:

### Required Endpoints

```python
@app.route('/status', methods=['GET'])
def status():
    return jsonify({
        'device': DEVICE,
        'model_loaded': model is not None,
        'param_count': model_info.get('param_count'),
        'vocab_size': 1000,
        'hidden_dim': 256
    })

@app.route('/inference', methods=['POST'])
def inference():
    data = request.json
    tokens = data.get('tokens', [42])
    max_length = data.get('max_length', 50)
    
    # Run inference...
    
    return jsonify({
        'logits': logits_list,
        'speech_output': speech_dict,
        'inference_time_ms': elapsed_ms
    })
```

---

## Python Environment Integration

The forum's `env_check` flow validates Python dependencies. Ensure your venv has:

```bash
source /root/workspace/.venv/bin/activate

pip install torch requests flask flask-cors numpy psycopg2-binary
```

The `GET /env/status` endpoint checks:
- ✅ `.venv` directory exists
- ✅ Python version
- ✅ Required packages installed
- ✅ GPU availability (via `rocm-smi`)

---

## Security Considerations

### 1. Command Injection Prevention

Flow command templates use Go's `exec.CommandContext` with shell isolation:

```go
cmd := exec.CommandContext(ctx, "bash", "-c", command)
```

**Best Practice:** Never interpolate user input directly into commands. Use parameterized substitution:

```go
// BAD:
command := fmt.Sprintf("python3 -c '%s'", userInput)

// GOOD:
command := flow.CommandTemplate
// Use environment variables or stdin for user input
```

### 2. Local-First Privacy

All ticket data stored in `~/.lean4a/forum.db`:
- ✅ Never transmitted over network
- ✅ User controls export
- ✅ Configurable path via `LEAN4A_FORUM_DB`

### 3. Rate Limiting

Flow executions limited by semaphore:

```go
flowSemaphore = make(chan struct{}, maxConcurrentFlows)
```

Default: 5 concurrent flows. Adjust via `MAX_CONCURRENT_FLOWS`.

### 4. Timeout Protection

All flows have configurable timeouts:

```go
ctx, cancel := context.WithTimeout(context.Background(), time.Duration(flowTimeoutSec)*time.Second)
defer cancel()
```

Default: 30 seconds. Adjust via `FLOW_TIMEOUT_SEC`.

---

## Observability

### Logging

Structured logs to stdout:

```
2025-05-07T12:34:56Z INFO Flow execution started flow_name=lean_sorry_scan ticket_id=tk_abc123
2025-05-07T12:34:58Z INFO Flow completed flow_name=lean_sorry_scan duration_ms=2340 status=success
```

### Metrics Endpoint (Future Enhancement)

Add to `main.go`:

```go
import "github.com/prometheus/client_golang/prometheus/promhttp"

http.Handle("/metrics", promhttp.Handler())
```

Track:
- `flow_executions_total{flow_name, status}`
- `flow_duration_seconds{flow_name}`
- `tickets_created_total`
- `sse_connections_active`

### Health Check

```bash
curl http://localhost:8443/health
```

Response:
```json
{
  "status": "healthy",
  "checks": {
    "database": "ok",
    "lean_db": "ok",
    "tph_server": "ok",
    "bpf": "ok"
  }
}
```

---

## Troubleshooting

### Issue: Database locked

**Symptom:** `database is locked` errors

**Solution:** WAL mode should prevent this, but if it persists:

```bash
# Check if WAL mode enabled
sqlite3 "$LEAN4A_FORUM_DB" "PRAGMA journal_mode;"
# Should output: wal

# If not, enable it:
sqlite3 "$LEAN4A_FORUM_DB" "PRAGMA journal_mode=WAL;"
```

### Issue: Flow timeout

**Symptom:** Flows marked as "timeout" in UI

**Solution:** Increase timeout:

```bash
export FLOW_TIMEOUT_SEC=60  # 60 seconds
```

### Issue: SSE connection drops

**Symptom:** Log panel stops updating mid-flow

**Solution:** Browser closes SSE after 5min by default. Client auto-reconnects on `onerror`.

### Issue: Python venv not detected

**Symptom:** Python badge shows "offline"

**Solution:** Check venv path in `handleEnvStatus`:

```go
venvPath := filepath.Join(homeDir, "workspace", ".venv")
```

Adjust to your actual venv location.

### Issue: BPF conflicts with forum routes

**Symptom:** Server fails to start

**Solution:** Ensure forum routes registered AFTER BPF initialization:

```go
func main() {
    http.HandleFunc("/qmcp/v1/consent", handleConsentGate)
    
    go startBPF()  // BPF in goroutine
    
    registerForumRoutes()  // AFTER startBPF
    
    http.ListenAndServe(":8443", nil)
}
```

---

## Testing

### Unit Tests

```go
// forum_test.go
package main

import (
    "testing"
    "net/http/httptest"
)

func TestGetFlows(t *testing.T) {
    req := httptest.NewRequest("GET", "/flows", nil)
    w := httptest.NewRecorder()
    
    handleGetFlows(w, req)
    
    if w.Code != 200 {
        t.Errorf("Expected 200, got %d", w.Code)
    }
}
```

### Integration Tests

```bash
# Start server
./go_red &
SERVER_PID=$!

# Test flow execution
curl -X POST http://localhost:8443/run/flow/env_check

# Test ticket retrieval
TICKET_ID=$(curl -s http://localhost:8443/tickets | jq -r '.tickets[0].id')
curl http://localhost:8443/ticket/$TICKET_ID

# Cleanup
kill $SERVER_PID
```

### UI Tests (Playwright)

```javascript
// test_forum_ui.js
const { test, expect } = require('@playwright/test');

test('should load flows', async ({ page }) => {
    await page.goto('http://localhost:8443/forum');
    await expect(page.locator('.flow-btn')).toHaveCount(5);
});

test('should execute flow and show log', async ({ page }) => {
    await page.goto('http://localhost:8443/forum');
    await page.click('text=Validate Python environment');
    await expect(page.locator('.log-entry')).toContainText('Starting flow');
});
```

---

## Future Enhancements

### 1. Flow Chaining

Execute flows in sequence:

```json
{
  "chain": [
    {"flow": "lean_sorry_scan"},
    {"flow": "tph_inference", "input_from": "previous.output.sorries[0]"}
  ]
}
```

### 2. Formula Library

Searchable index of DynamicFlux formulas:

```sql
CREATE TABLE formulas (
    id TEXT PRIMARY KEY,
    name TEXT,
    python_code TEXT,
    lean_equivalent TEXT,
    tags TEXT
);
```

### 3. Export Formats

Export tickets as PDF/Markdown:

```go
GET /ticket/{id}/export?format=pdf
```

### 4. Collaboration

Share sessions via encrypted links:

```go
POST /session/{id}/share
Response: {"share_link": "https://forum.local/s/abc123"}
```

---

## File Locations Summary

```
/mnt/doscratch/Work/AMD_COMPETITION_MVP/vessel-production/Go_Red/
├── main.go                      # Original Go_Red server
├── forum.go                     # NEW: Extension code (copy of go_red_extension.go)
├── internal/
│   └── registry/
│       └── detachable_bridge.go # Existing SQLite bridge pattern
└── static/
    └── lean4a_forum.html        # NEW: Forum UI

~/.lean4a/
└── forum.db                     # NEW: Local SQLite database (auto-created)

/path/to/deliverables/
├── LEAN4A_FORUM_ARCHITECTURE.md # Architecture design doc
├── go_red_extension.go          # Complete Go extension code
├── forum_schema.sql             # SQLite database schema
├── lean4a_forum.html            # Complete HTML interface
└── flow_definitions.json        # Flow configuration
```

---

## Contact & Support

For issues or questions about this integration:
1. Check logs: `journalctl -u go_red -f`
2. Verify database: `sqlite3 ~/.lean4a/forum.db ".tables"`
3. Test endpoints: `curl http://localhost:8443/health`

---

**End of Integration Guide**
