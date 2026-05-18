# Hugging Face Requirements Boundary

This document lists what Lean4-Automata can and cannot expect from a Hugging Face Spaces deployment. The Hugging Face surface is a public preview and artifact reader, not the full local proof infrastructure.

## Production Target

The Hugging Face repo should run a small read-only application:

- `app.py` as the Gradio entrypoint.
- `requirements.txt` for lightweight Python dependencies.
- Small committed static artifacts, generated summaries, SVGs, JSON files, or Markdown.
- No dependency on local Postgres, Docker Compose, Go services, Wolfram Engine, or private operator dashboards.

## Possible On Hugging Face

| Requirement Type | Status | Notes |
| --- | --- | --- |
| Gradio UI | Allowed | Declared in top-level `requirements.txt`. |
| Pure Python parsing and rendering | Allowed | Keep imports small and deterministic. |
| Static HTML, CSS, SVG, Markdown, JSON | Allowed | Best fit for public proof-map summaries and evidence tables. |
| Small precomputed Lean/Wolfram summaries | Allowed | Commit generated data or ship a small artifact bundle. |
| Public read-only artifact tables | Allowed | Avoid mutating audit tickets or badges from the Space. |
| OS packages from `packages.txt` | Possible | Keep them minimal and compatible with the Space base image. |
| Linux-native compiled Python wheels | Possible | Build for Linux, preferably manylinux-compatible or in a Docker Space. |
| Small C/C++ helper modules | Possible | Compile as Linux-native modules; document source, build flags, and licenses. |

## Not For Hugging Face Production

| Requirement Type | Status | Reason |
| --- | --- | --- |
| Wolfram Engine | Not allowed for this production target | Local development may use it, but the public Space must not require a proprietary Wolfram runtime or license. |
| Wolfram LLMSynthesize | Not allowed for this production target | Treat generated outputs as precomputed artifacts, not live HF dependencies. |
| Cygwin binaries or DLLs | Not deployable directly | Hugging Face Spaces run Linux containers, not a Windows Cygwin runtime. |
| A 200 GB local Cygwin/library tree | Not suitable | Too large and too environment-specific for the Space. Inventory exact needs instead. |
| Local Postgres, Go forum service, Docker Compose | Not part of the preview | These belong to local/operator deployments. |
| Live L2BL4 badge issuance | Not part of the preview | Public badge issuing requires the local evidence contract and OTS policy. |
| Private keys, tokens, admin endpoints | Never ship | Keep secrets and mutable operator controls outside the public repo. |

## Wolfram Development Boundary

Wolfram Engine can remain useful in this local development workspace for symbolic checks, formula exploration, and companion-map generation. Hugging Face should receive only the resulting public-safe artifacts:

- Markdown summaries.
- JSON or CSV graph data.
- SVG or PNG visualizations.
- Precomputed tables with timestamps and provenance notes.

Do not present Wolfram outputs as formal proof. Lean remains the proof authority.

## Cygwin Module Strategy

If Cygwin-hosted libraries are needed during development, treat that folder as a source and discovery environment, not as the Hugging Face runtime target.

For production packaging:

1. Inventory the exact library names, functions, headers, and data files that are actually needed.
2. Separate source code from Windows/Cygwin-built binaries.
3. Prefer PyPI, apt, or small source builds when Linux equivalents exist.
4. Compile any custom helper as a Linux-native wheel or shared object.
5. Record build commands, checksums, and licenses.
6. Ship only the minimal runtime artifact, not the full Cygwin tree.

If the old 200 GB library archive is missing, do not redownload it blindly for Hugging Face. Start with a manifest-driven search for the minimal libraries required by the preview or helper module.

The inventory manifest should record library name, purpose, exact symbols or functions used, headers, data files, source provenance, license, Linux package or PyPI equivalent, build flags, checksum, and expected runtime artifact.

## Acceptance Checklist

Before publishing the Hugging Face repo:

- `python3 -m py_compile app.py` passes.
- `requirements.txt` installs in a clean Linux environment.
- The Space starts without Wolfram, Postgres, Docker, Go, or Cygwin.
- Public copy states that the Space is read-only.
- All large generated data is either omitted, summarized, or moved to a deliberate artifact store.
- Any native module is Linux-native and has documented provenance.
