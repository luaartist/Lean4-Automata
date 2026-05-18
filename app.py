"""Hugging Face Spaces preview for Lean4-Automata.

This app is intentionally read-only. It presents the public proof observatory
model without requiring the local FastAPI, Go, Postgres, Docker, or Wolfram
runtime stack.
"""

from __future__ import annotations

from typing import Iterable


PROJECT_SUMMARY = """
# Lean4-Automata

Lean4-Automata is a local proof observatory for Lean 4 projects. It keeps the
Lean corpus at the center, with import graph navigation, symbol search, proof
completion tracking, audit tickets, and evidence badges for durable review.

This preview is a public, read-only packaging surface. It does not run local
audits, mutate databases, issue badges, or contact internal services.
"""

FOUNDATIONS_MD = """
## Foundations

Lean4-Automata records the basic proof infrastructure: Lean files,
declarations, imports, theorem status, and project structure. This gives the
observatory a grounded reference layer before adding audit notes, tickets,
badges, or companion maps.

Lean remains the proof authority. Dashboards, badges, timestamps, and optional
companion maps are evidence around the proof work, not replacements for Lean
verification.
"""

LEAN_MAPPING_MD = """
## Lean Mapping

Lean Mapping connects files, imports, symbols, and proof targets into a
navigable index. It supports search, dependency review, and proof completion
tracking while keeping Lean source material as the primary reference.

The intended onboarding questions are simple:

1. What are you proving?
2. What should the main Lean target be?
"""

AUDIT_FLOWS_MD = """
## Audit Flows

Audit Flows organize review work into traceable tickets. Each ticket can point
to files, symbols, proof obligations, external references, and review outcomes,
making unfinished or verified work easier to revisit.

Readable summaries should sit beside JSON output so humans and tools can
inspect the same evidence without losing structure.
"""

EVIDENCE_MD = """
## Evidence Badges

Evidence badges can serve different archival needs:

- Keepsake: successful local audit output recorded as project memory.
- Public: audit success plus confirmed OpenTimestamps evidence and matching
  obligation counts.
- Sovereign: public badge requirements plus a composite signature hash from the
  issuer process.

Time anchoring is not proof. OpenTimestamps can show when an evidence digest
existed, but it does not prove mathematical correctness, authorship, or intent.
"""

PACKAGING_MD = """
## Packaging

Lean4-Automata separates public presentation from internal operation:

- `frontend/app/page.tsx`: live Next frontend overview and workbench entry.
- `public/index.html`: no-CDN static public page.
- `ui/offline_internal.html`: local artifact navigator outside the public web
    root.
- `app.py`: this Hugging Face preview.
- `ui/lean4a_forum.html`: local operator flow dashboard.

Wolfram companion maps are optional navigation and analysis aids. A Wolfram
Engine installation or commercial LLMSynthesize setup is not bundled with this
package.
"""

HF_REQUIREMENTS_MD = """
## Hugging Face Requirements Boundary

This preview is intentionally small and read-only.

Possible in the Space:

- Gradio UI from `app.py`.
- Lightweight Python dependencies from `requirements.txt`.
- Static Markdown, JSON, SVG, and precomputed proof-map summaries.
- Small Linux-native helper modules when their build and license are
    documented.

Not part of the Space:

- Wolfram Engine or Wolfram LLMSynthesize runtime dependencies.
- Cygwin binaries, DLLs, or a Windows/Cygwin runtime tree.
- A full local library archive or 200 GB dependency folder.
- Local Postgres, Docker Compose, Go services, badge issuance, or admin flows.

Local development may use Wolfram and Cygwin-hosted libraries to generate or
check artifacts. The public Space should receive the resulting small,
public-safe artifacts or Linux-native modules only.

Before recovering or redownloading any large Cygwin archive, inventory the
minimal functions, headers, data files, licenses, and Linux-native build path
needed for the public preview.
"""

ARTIFACTS = [
    ["README", "Project overview and run notes", "README.md", "Public"],
    [
        "Design schema",
        "Public surface contract",
        "docs/public-face-design-schema.md",
        "Public",
    ],
    [
        "Packaging surfaces",
        "Entrypoint map",
        "docs/packaging-surfaces.md",
        "Public",
    ],
    [
        "HF boundary",
        "Production dependency limits",
        "docs/huggingface-requirements-boundary.md",
        "Public",
    ],
    ["Static page", "No-CDN overview", "public/index.html", "Public"],
    [
        "Offline dashboard",
        "Local artifact index outside the public web root",
        "ui/offline_internal.html",
        "Internal",
    ],
    [
        "L2BL4 contract",
        "Evidence badge rules",
        "README_DATABASE.md",
        "Public docs",
    ],
]


def _table(rows: Iterable[list[str]]) -> str:
    header = "| Name | Purpose | Path | Scope |\n| --- | --- | --- | --- |"
    body = "\n".join("| " + " | ".join(row) + " |" for row in rows)
    return f"{header}\n{body}"


def build_app():
    try:
        import gradio as gr
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Gradio is required for the Hugging Face Space preview. "
            "Install gradio or deploy this app.py on Hugging Face Spaces."
        ) from exc

    with gr.Blocks(title="Lean4-Automata") as demo:
        gr.Markdown(PROJECT_SUMMARY)
        with gr.Tabs():
            with gr.Tab("Overview"):
                gr.Markdown(PROJECT_SUMMARY)
                gr.Markdown(_table(ARTIFACTS))
            with gr.Tab("Foundations"):
                gr.Markdown(FOUNDATIONS_MD)
            with gr.Tab("Lean Mapping"):
                gr.Markdown(LEAN_MAPPING_MD)
            with gr.Tab("Audit Flows"):
                gr.Markdown(AUDIT_FLOWS_MD)
            with gr.Tab("Evidence"):
                gr.Markdown(EVIDENCE_MD)
            with gr.Tab("Packaging"):
                gr.Markdown(PACKAGING_MD)
            with gr.Tab("HF Requirements"):
                gr.Markdown(HF_REQUIREMENTS_MD)
    return demo


if __name__ == "__main__":
    app = build_app()
    app.launch()
