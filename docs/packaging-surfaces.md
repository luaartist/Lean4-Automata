# Lean4-Automata Packaging Surfaces

This document defines the public and internal entrypoints for packaging Lean4-Automata without mixing product presentation with operator controls.

## Entrypoints

| Entrypoint | File | Purpose | Runtime |
| --- | --- | --- | --- |
| Next public overview | `frontend/app/page.tsx` | Live app first page with product positioning and links into the workbench | Next.js |
| Static public page | `public/index.html` | Portable product and trust overview that opens from disk | Browser only |
| Static public CSS | `public/assets/styles.css` | Shared no-CDN styling for public static pages | Browser only |
| Static public JS | `public/assets/lean4-automata.js` | Accessible tabs and local page behavior | Browser only |
| Offline internal dashboard | `ui/offline_internal.html` | Local artifact and checklist navigator outside the public web root | Browser only |
| Hugging Face preview | `app.py` | Read-only Space preview using the same public model | Python + Gradio on HF |
| Operational dashboard | `ui/lean4a_forum.html` | Local flow runner, tickets, debug panel, and operator checks | Local Go service |

## Public Page Requirements

- Works without external fonts, CDNs, or remote images.
- Uses `Lean4-Automata` as the visible namesake and H1.
- Provides clear tabs for Overview, Foundations, Lean Mapping, Audit Flows, Evidence, and Packaging.
- Explains proof/evidence boundaries before badge claims.
- Uses public-root-safe anchors or visible repository paths rather than links that climb outside `public/`.
- Does not expose admin endpoints, live health checks, secrets, or mutable database controls.

## Hugging Face Requirements

- The top-level `app.py` is read-only.
- The app can render without local FastAPI, Postgres, Docker, Go, or Wolfram services.
- It should show the same tab model as the static page.
- It uses Gradio on Hugging Face; if Gradio is unavailable, `app.py` should fail with a clear Python error rather than silently degrading.
- It must not claim that badges or audit tickets prove mathematics beyond Lean verification.
- The allowed and disallowed production requirements are listed in `docs/huggingface-requirements-boundary.md`.
- Wolfram Engine and LLMSynthesize are development-only for this package and must not be required by the public Space.
- Cygwin folders are development/discovery inputs only. Hugging Face needs Linux-native wheels, small source builds, or precomputed artifacts.
- Do not publish a full Cygwin or 200 GB library tree to the Space. Inventory exact requirements and ship only the minimal runtime set.

## Offline Internal Requirements

- Opens directly as a local file.
- Uses no CDN, no external scripts, and no remote CSS.
- Shows local artifact links, status matrix, and packaging checklist.
- Clearly states that live flows require the local Go/FastAPI stack.
- Keeps operator/debug affordances separate from public copy and out of the public static web root.

## Wolfram Optional Use

Wolfram companion maps may enrich navigation, formula visualization, and symbolic review. They are optional. Do not bundle proprietary Wolfram packages or imply a Wolfram Engine license is included. If a user installs Wolfram Engine or uses commercial LLMSynthesize features, that is a separate local setup decision.

## Standard User Onboarding Prompts

Future onboarding should ask two plain questions before building a proof map:

1. What are you proving?
2. What should the main Lean target be?

The system should then register a project, target modules, expected artifacts, audit flow preferences, and evidence policy. Yang-Mills or Clay-specific defaults should only appear when explicitly selected.

## Professional Output Standard

Use sectioned output instead of visual noise:

- Short headings
- Compact tables
- Clear status labels
- Plain text fallbacks
- No emoji dependency
- No box-art output
- No bright decorative attractors masking thin functionality
