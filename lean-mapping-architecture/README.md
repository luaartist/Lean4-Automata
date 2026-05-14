# Lean Mapping Architecture

> Comprehensive architecture documentation for the Lean 4 source-code dependency
> mapping system integrated with Serena.

## Reading Guide

| Audience | Start with |
|----------|-----------|
| Executives / PMs | [00 – Executive Summary](sections/00-executive-summary.md) |
| Backend engineers | [03 – API Specification](sections/03-api-specification.md), [08 – Backend Services](sections/08-backend-services.md) |
| Frontend engineers | [06 – Frontend Architecture](sections/06-frontend-architecture.md), [07 – UI Patterns](sections/07-frontend-ui-patterns.md) |
| SREs / DevOps | [13 – Deployment](sections/13-deployment.md), [15 – Operational Runbook](sections/15-operational-runbook.md) |
| Security reviewers | [10 – Security Model](sections/10-security-model.md) |
| New contributors | [14 – Development Workflow](sections/14-development-workflow.md), [17 – Glossary](sections/17-glossary.md) |

## Section Index

| # | Section | Purpose |
|---|---------|---------|
| 00 | [Executive Summary](sections/00-executive-summary.md) | Business context, goals, constraints |
| 01 | [System Architecture](sections/01-system-architecture.md) | Component map, boundaries, data flows |
| 02 | [Technology Stack](sections/02-technology-stack.md) | Chosen technologies and rationale |
| 03 | [API Specification](sections/03-api-specification.md) | REST contract catalogue |
| 04 | [Data Model](sections/04-data-model.md) | PostgreSQL schema, indexes, migrations |
| 05 | [Data Freshness Model](sections/05-data-freshness-model.md) | Cache-control, SSE invalidation, TTLs |
| 06 | [Frontend Architecture](sections/06-frontend-architecture.md) | Next.js app structure, component tree |
| 07 | [Frontend UI Patterns](sections/07-frontend-ui-patterns.md) | Three-layer exploration, accessibility |
| 08 | [Backend Services](sections/08-backend-services.md) | Service decomposition, worker pool |
| 09 | [Backend Performance](sections/09-backend-performance.md) | Connection pooling, query optimisation |
| 10 | [Security Model](sections/10-security-model.md) | Auth context, RBAC, input validation |
| 11 | [Resilience Patterns](sections/11-resilience-patterns.md) | Retries, circuit breakers, back-pressure |
| 12 | [Observability](sections/12-observability.md) | Metrics, traces, correlation IDs |
| 13 | [Deployment](sections/13-deployment.md) | Docker, Kubernetes, zero-downtime |
| 14 | [Development Workflow](sections/14-development-workflow.md) | Local setup, branching, CI gates |
| 15 | [Operational Runbook](sections/15-operational-runbook.md) | Incident playbooks, reindexing |
| 16 | [Decision Records](sections/16-decision-records.md) | ADRs for major architecture choices |
| 17 | [Glossary](sections/17-glossary.md) | Domain terms, abbreviations |

## Building the LaTeX Report

```bash
cd latex/
latexmk -pdf main.tex   # or: pdflatex main.tex && pdflatex main.tex
```

## Conventions

- **Heading hierarchy**: `#` per-document title, `##` sections, `###` subsections.
- **Code blocks** use language tags (`sql`, `python`, `typescript`, `bash`).
- **ADR format**: Status → Context → Decision → Consequences.
- **Wolfram references** are always marked `[Optional – non-core]`.
