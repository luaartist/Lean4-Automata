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
