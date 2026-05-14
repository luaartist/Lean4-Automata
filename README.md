# Lean4-Automata

A Lean 4 project for formal specification and verification of automata theory conceptual design and refined development.

---

## Prerequisites

Before running the stack, ensure the following are installed on your system:

| Tool | Version | Install |
|------|---------|---------|
| **Docker** | 24+ | https://docs.docker.com/engine/install/ |
| **Docker Compose** | v2 (plugin) | Included with Docker Desktop; or `apt install docker-compose-plugin` |
| **Python** | 3.11+ | https://www.python.org/downloads/ |
| **Lean 4 / elan** | latest | `curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf \| sh` |

> **Docker Compose v2** ships as a Docker CLI plugin (`docker compose`).  
> If you only have the older standalone binary (`docker-compose`), upgrade or install the plugin:
> ```bash
> # Debian/Ubuntu
> sudo apt update && sudo apt install docker-compose-plugin
> # Verify
> docker compose version
> ```

---

## Quick Start

```bash
# Clone / enter the project
cd Lean4-Automata

# Copy env template (edit values as needed)
cp .env.example .env

# Bring up the full stack
docker compose up --build

# Health check
curl http://localhost:8000/health
```

---

## Forum UI & Go CLI Harness

The `go/forum.go` binary and `ui/lean4a_forum.html` provide an **optional, local-only**
research workflow tool — not a community forum. Its purpose:

- **Flow runner**: Trigger named analysis flows (sorry scan, float scan, interconnect map)
  against the live Lean4-Automata API via a browser UI
- **Ticket log**: Store proof-audit findings locally in `~/.lean4a/forum.db` (SQLite, stays on disk)
- **AI agent interface**: Each flow corresponds to a structured JSON response that agents
  can consume directly — the UI is human-readable sugar over a machine-readable protocol

This is deliberate scope: the forum DB is SQLite and **never replicated to Postgres**.
Proof audit tickets are user-local findings, not shared state.

### Why it exists alongside the watcher
The watcher pipeline (inotify → parse → Postgres) feeds the *database* layer.
The forum harness gives a *workflow* layer: a human or AI agent can run targeted
queries and bookmark findings without writing SQL.

### Running standalone (no Docker)
```bash
cd go && go build -o lean4a_forum && ./lean4a_forum --port 8443
# Open ui/lean4a_forum.html — uses http://localhost:8443 as API_BASE
```

---

## Project Layout

| Directory | Purpose |
|-----------|---------|
| `app/` | FastAPI REST backend |
| `db/` | PostgreSQL schema |
| `alembic/` | Database migrations |
| `workers/` | Lean symbol parsing workers |
| `frontend/` | UI layer |
| `tools/` | Standalone file/search utilities (`lean4_file_tools.py`) |
| `observability/` | Grafana / Loki log stack |
| `infra/` | Infrastructure configs |
| `go/` | Go CLI forum harness (flow runner + ticket log) |
| `ui/` | Browser UI for forum harness |
| `parser/` | Lean 4 file parser and inotify watcher |
| `docs/` | Architecture anchor (LaTeX), role guides, codebase survey |

---

### Proof Completion Metric

`proof_completion` is the primary health signal per Lean file:

```
proof_completion = (theorem_count − sorry_in_proof_count) / theorem_count
```

| Value | Meaning |
|-------|---------|
| `1.0` | All theorems/lemmas have complete proofs — no sorry, admit, or native_decide |
| `0.5` | Half of theorems contain an incomplete proof marker |
| `0.0` | Every theorem is sorry-or-equivalent |

**What counts as an incomplete proof marker:**
- `sorry` — explicit placeholder, always incomplete
- `admit` — alias for sorry in some Lean 4 toolchain versions
- `native_decide` — treated as sorry-equivalent; can silently succeed on false
  propositions with incorrect typeclass instances and is fragile across Lean versions

**What is tracked but does NOT penalise proof_completion:**
- `decide_count` — legitimate tactic but worth auditing for performance
- `native_decide_count` — raw occurrence count (separate from per-theorem detection)

The `v_proof_status` view buckets files into `complete` / `partial` / `incomplete` / `empty`
and orders by `proof_completion ASC, sorry_count DESC` for audit prioritisation.
