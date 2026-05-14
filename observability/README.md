# Grafana + Loki log aggregation

This layer is intentionally limited to **logs only**. It adds Grafana and Loki
for the point where `docker compose logs` / stdout is no longer enough, without
adding Prometheus, Tempo, OpenTelemetry, or a log sidecar.

## Start the log stack

```bash
docker compose --profile observability up -d loki grafana
```

Grafana is available at <http://localhost:3001> by default.

| Setting | Default |
|---|---|
| `GRAFANA_PORT` | `3001` |
| `GRAFANA_ADMIN_USER` | `admin` |
| `GRAFANA_ADMIN_PASSWORD` | `admin` |
| `LOKI_PORT` | `3100` |

## Send container logs to Loki

The repo uses the Loki Docker logging driver instead of Promtail. Install the
driver once per Docker host:

```bash
docker plugin install grafana/loki-docker-driver:latest --alias loki --grant-all-permissions
```

Then start the stack with the logging override:

```bash
docker compose --profile observability up -d loki grafana
docker compose -f docker-compose.yml -f docker-compose.logging.yml up -d
```

The override keeps normal local development safe: the default compose file still
runs without requiring the Loki logging plugin.

## Provisioned UI

Grafana auto-provisions:

- datasource: `Lean4-Loki`
- folder: `Lean4-Automata`
- dashboard: `Logs Overview`

The dashboard has variables for compose project, service, log level, and free
text search. It keeps indexed Loki labels low-cardinality:

| Label | Purpose |
|---|---|
| `compose_project` | Compose project grouping |
| `compose_service` | Service-level filtering |
| `container_name` | Container drilldown |

High-cardinality values like `request_id` should be searched in the log stream,
not promoted to Loki labels.

## Fresh-start check

```bash
docker compose down -v
docker compose --profile observability up -d loki grafana
docker compose -f docker-compose.yml -f docker-compose.logging.yml up -d
```

Open <http://localhost:3001/d/lean4-logs-overview/logs-overview> and confirm:

1. `Lean4-Loki` reports as healthy.
2. `$service` lists active compose services.
3. `Log Volume by Service` receives bars within about a minute.
4. `Log Stream` filters by service, level, and search text.
5. No Prometheus, Tempo, or trace datasources are provisioned.
