# Grafana + Loki UX Spec — Lean4-Automata

> **Phase:** Log aggregation only. No metrics, traces, or OpenTelemetry.

---

## 1  Scope Boundaries

| In scope | Explicitly out of scope |
|---|---|
| Loki log collection via Docker log driver | Prometheus metrics collection |
| Grafana dashboards for log exploration | Tempo / distributed tracing |
| Provisioned datasource + dashboards-as-code | OpenTelemetry SDK instrumentation |
| Alerting on log patterns (error spikes) | Custom application metrics endpoints |

The only new containers are **loki** and **grafana**.
Logs flow from Docker → Loki log driver → Grafana. No sidecar or agent needed.

---

## 2  Log Labels Taxonomy

Every log line ingested by Loki carries these labels (set by the Docker log driver):

| Label | Source | Example values |
|---|---|---|
| `compose_project` | Docker Compose project name | `lean4-automata` |
| `compose_service` | Compose service key | `worker`, `watcher`, `web`, `nginx`, `postgres`, `redis`, `flower` |
| `container_name` | Running container name | `lean4-automata-worker-1` |

**Extracted at query-time** (Loki pipeline stages, not stored as index labels):

| Parsed field | Extraction method | Notes |
|---|---|---|
| `level` | JSON key or regex `(?P<level>DEBUG\|INFO\|WARN\|ERROR\|CRITICAL)` | Celery & Python emit structured levels |
| `request_id` | JSON key `request_id` / regex | Present in web & API logs when middleware injects it |
| `task_name` | Regex from Celery log format | e.g. `workers.tasks.parse_lean_file` |

> **Design rule:** keep indexed labels low-cardinality (≤ 7 services).
> High-cardinality fields (`request_id`, `task_name`) are parsed, never indexed.

---

## 3  Grafana Information Architecture

```
Grafana
└── Folder: "Lean4-Automata"
    ├── Dashboard: "Logs Overview"       ← single primary dashboard (see §4)
    └── Dashboard: "Nginx Access Logs"   ← optional future; not in this phase
```

One folder, one dashboard. Resist adding more until the team asks for them.

### Datasource provisioning

A single Loki datasource named **Lean4-Loki**, auto-provisioned at container
start via `grafana/provisioning/datasources/loki.yaml`.

---

## 4  Dashboard Layout — "Logs Overview"

### 4.1 Template variables (top bar)

| Variable | Type | Query / Values | Default |
|---|---|---|---|
| `$service` | Query | `label_values(compose_service)` | `All` (multi + include-all) |
| `$level` | Custom | `DEBUG, INFO, WARN, ERROR, CRITICAL` | `All` |
| `$search` | Text box | Free text | *(empty)* |

### 4.2 Row & panel layout

Dashboard uses a **single-column layout** (full-width 24-col spans) for
readability at any viewport width.

```
╔══════════════════════════════════════════════════════════════╗
║  Row 1 — Health at a glance                                  ║
║  ┌────────────────────┐ ┌────────────────────┐               ║
║  │ Log Volume (bar)   │ │ Error Rate (bar)   │               ║
║  │ 12 col             │ │ 12 col             │               ║
║  └────────────────────┘ └────────────────────┘               ║
╠══════════════════════════════════════════════════════════════╣
║  Row 2 — Log stream                                          ║
║  ┌──────────────────────────────────────────────────────────┐║
║  │ Logs panel (full width, 24 col)                          │║
║  │ Shows raw log lines; filterable by $service, $level,     │║
║  │ $search. Default sort: newest first.                     │║
║  └──────────────────────────────────────────────────────────┘║
╠══════════════════════════════════════════════════════════════╣
║  Row 3 — Per-service breakdown (collapsed by default)        ║
║  ┌──────────────────────────────────────────────────────────┐║
║  │ Table panel: service × log-level counts (24 col)         │║
║  └──────────────────────────────────────────────────────────┘║
╚══════════════════════════════════════════════════════════════╝
```

### 4.3 Panel details

#### P1 — Log Volume (time series bar chart)

- **LogQL:** `sum by (compose_service) (count_over_time({compose_project="lean4-automata", compose_service=~"$service"} | $level != "" [$__auto]))`
- **Visualization:** stacked bar chart, one series per service.
- **Purpose:** spot traffic spikes at a glance.

#### P2 — Error Rate (time series bar chart)

- **LogQL:** `count_over_time({compose_project="lean4-automata", compose_service=~"$service"} |~ "(?i)error|critical" [$__auto])`
- **Visualization:** single-series bar chart, red fill.
- **Purpose:** surface error bursts without needing a metrics pipeline.

#### P3 — Log Stream (Logs panel)

- **LogQL:** `{compose_project="lean4-automata", compose_service=~"$service"} |~ "$search" | logfmt or json | level=~"$level"`
- **Deduplication:** off (show every line).
- **Wrap lines:** on.
- **Show time:** on, relative.
- **Drilldown:** clicking a log line opens the side detail pane (Grafana built-in); no external links needed.

#### P4 — Service × Level Matrix (table)

- **LogQL:** one instant query per level using `count_over_time` over `$__range`, grouped by `compose_service`.
- **Purpose:** quick "which service is noisiest?" view.
- **Cell coloring:** background tint by value (see §5 color rules).

---

## 5  Accessibility & Visual Guidance

### 5.1 Color palette for log levels

| Level | Hex | Role | WCAG contrast on #181B1F bg |
|---|---|---|---|
| `DEBUG` | `#8AB4F8` (light blue) | Neutral info | 7.4 : 1 ✅ AAA |
| `INFO` | `#A8DAB5` (soft green) | Normal ops | 8.1 : 1 ✅ AAA |
| `WARN` | `#FDD663` (amber) | Attention | 11.2 : 1 ✅ AAA |
| `ERROR` | `#F28B82` (salmon) | Problem | 6.5 : 1 ✅ AA+ |
| `CRITICAL` | `#FF6D6D` (bright red) | Severe | 5.6 : 1 ✅ AA |

> Use **both color and a text badge** for level—never color alone.
> All hex values verified against Grafana Dark theme background `#181B1F`.

### 5.2 Table readability

- Alternate row shading with ≥ 3 : 1 contrast difference.
- Monospace font (`Roboto Mono`) for log content columns.
- Minimum row height: 36 px (touch target ≥ 44 px on interactive rows).
- Truncate long lines with ellipsis; full text visible on row expand.

### 5.3 Keyboard-oriented exploration

Grafana's built-in keyboard shortcuts apply:

| Action | Key |
|---|---|
| Open command palette | `Cmd/Ctrl + K` |
| Toggle variable dropdown | `Tab` into var → `Enter` |
| Time range zoom | `Ctrl + Z` (zoom out) |
| Expand log line | `Enter` on focused row |

> **Spec requirement:** Do not use custom JS panels or plugins that break
> keyboard focus order. Stick to native Grafana panel types.

### 5.4 Responsive behavior

- At < 1200 px, the two bar charts in Row 1 stack vertically (Grafana default repeat behavior with `min-width` on panels).
- Logs panel remains full-width at all sizes; horizontal scroll is acceptable for very wide structured fields.

---

## 6  Provisioning File Map

```
observability/
├── GRAFANA_LOKI_UX.md              ← this file
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/
│   │   │   └── loki.yaml           ← Lean4-Loki datasource
│   │   └── dashboards/
│   │       └── default.yaml        ← dashboard provider config
│   └── dashboards/
│       └── logs-overview.json      ← "Logs Overview" dashboard JSON
└── loki/
    └── loki-config.yaml            ← Loki local config (filesystem store)
```

All provisioning is file-based, committed to the repo, and mounted into
containers. No manual Grafana UI setup required.

---

## 7  Validation Checklist

Before merging, verify each item on a running `docker compose up` stack:

- [ ] **Datasource:** Grafana → Connections → Lean4-Loki shows "Data source is working."
- [ ] **Variables:** `$service` dropdown lists all 7 services; `$level` dropdown lists 5 levels.
- [ ] **P1 (Volume):** bars appear within 60 s of container start; one color per service.
- [ ] **P2 (Errors):** intentionally log an error (`docker exec ... python -c "import logging; logging.error('test')"`) and confirm it renders within 15 s.
- [ ] **P3 (Log stream):** filtering by single service shows only that service's lines.
- [ ] **P3 (Search):** typing a `$search` term filters lines correctly.
- [ ] **P4 (Matrix):** table populates with non-zero counts for active services.
- [ ] **Color/contrast:** visually verify level badges are distinguishable; no color-only encoding.
- [ ] **Keyboard nav:** Tab through variable dropdowns, press Enter to select, verify focus is visible.
- [ ] **Collapsed row:** Row 3 is collapsed on load; clicking the header expands it.
- [ ] **Dark theme default:** dashboard ships with Grafana dark theme; light theme is not broken.
- [ ] **No metrics/traces:** confirm no Prometheus or Tempo datasources exist; Grafana has only the Loki datasource.
- [ ] **Fresh-start provisioning:** `docker compose down -v && docker compose up -d` results in a working dashboard with zero manual steps.
