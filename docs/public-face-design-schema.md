# Lean4-Automata Public Face Design Schema

Lean4-Automata should present itself as a local proof observatory for Lean 4 projects: a durable workbench for inspecting proof structure, tracking audit output, and preserving evidence records without overstating what the system proves.

## Surface Types

| Surface | Audience | Purpose | Internet Required |
| --- | --- | --- | --- |
| Next frontend | Users already running the stack | Live project overview, search, module metrics, and graph navigation | No, after local install |
| Static public page | Reviewers, researchers, maintainers | Portable overview of the product, trust model, and packaging paths | No |
| Hugging Face Space | Public demo viewers | Read-only preview of the same public model and artifact table | Hosted by Hugging Face |
| Offline internal dashboard | Operators and maintainers | Local artifact navigation without a backend or CDN, stored outside `public/` | No |
| FastAPI and Go services | Developers and operators | Live audit, tickets, badges, search, and ingestion | Local services only |

## Brand Centerpiece

Use the product name as the first signal:

> Lean4-Automata

Preferred category phrase:

> Local proof observatory for Lean 4 projects.

The name should not be buried in small navigation text. Every public surface should explain that Automata refers to the system around the proof work: import graph states, audit flows, evidence records, and repeatable project transitions.

## Canonical Tabs

Use the same tab model across the static page, Hugging Face preview, and internal dashboard.

| Tab | Content Contract |
| --- | --- |
| Overview | What Lean4-Automata is, who uses it, and what it does not claim |
| Foundations | Lean files, declarations, imports, proof status, and target selection |
| Lean Mapping | Import graph, symbol search, module metrics, Mathlib and external references |
| Audit Flows | Audit tickets, flow inputs, flow outputs, unresolved obligations, review notes |
| Evidence | L2BL4 keepsake, public, and sovereign badge meanings and contract boundaries |
| Packaging | Next, static HTML/CSS, Hugging Face `app.py`, Docker/API, offline internal HTML |

## Visual Rules

- Prefer restrained technical surfaces over marketing spectacle.
- Use neutral backgrounds, readable type, and one or two utility accents.
- Avoid bright gradients, decorative blobs, oversized hero sections, and vague AI claims.
- Use compact tables, segmented tabs, and status rows for operational data.
- Cards are for repeated artifacts only; do not nest cards inside cards.
- Internal pages must be clearly marked as local/operator surfaces.
- Public pages must avoid private endpoints, secrets, admin controls, and live health probes.

## Proof And Evidence Boundary

Lean remains the proof authority. Lean4-Automata records and summarizes proof-adjacent evidence.

| Artifact | What It Can Mean | What It Must Not Claim |
| --- | --- | --- |
| Lean build | Lean accepted a project under a specific toolchain | Independent peer review |
| Proof completion | No tracked incomplete proof markers were found in counted theorem bodies | Mathematical correctness beyond Lean |
| Audit ticket | A named audit flow ran and produced structured output | All findings are resolved |
| Keepsake badge | A successful local audit output was recorded | Public timestamp attestation |
| Public badge | Audit success plus confirmed OTS and matching obligation counts | Mathematical truth or authorship |
| Sovereign badge | Public badge plus composite signature hash | Legal notarization without issuer policy |
| Wolfram companion map | Optional context or symbolic assistance | Formal Lean verification |

## Content Data Contract

Every public surface should be able to render these fields without contacting a live service:

- Product name: `Lean4-Automata`
- Short description
- Current status
- Core capabilities
- Trust and evidence boundary
- Artifact table
- Packaging entrypoints
- Wolfram optional-use disclaimer
- Hugging Face production boundary: no Wolfram Engine, no Cygwin runtime, no full local library tree
- Public-root-safe anchors and visible repository paths

## Backup Discipline

Before changing public or internal HTML/CSS surfaces, create a timestamped folder under `.shipping_backups/` with:

- `manifest.txt`
- copies of any touched existing files
- notes describing the intended design change

Backups are rollback references only. They are not source-of-truth documentation.

## Agent Review Notes

The SEO review chain recommended these constraints:

- Replace the root redirect with a real public entry surface.
- Make Lean4-Automata the H1 and product centerpiece.
- Position the product as proof observability and durable evidence, not theorem automation.
- Keep Wolfram optional and clearly separate from formal proof authority.
- Use public-safe docs and static surfaces; keep debug/operator functions internal.
- Keep internal offline dashboards outside the public static web root.
- Add metadata, trust copy, and stable packaging pages before cosmetic polish.
