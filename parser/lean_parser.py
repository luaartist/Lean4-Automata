"""Regex-based Lean 4 symbol and import extractor.

This module is intentionally I/O-light: :func:`parse_text` operates on a string
so it is trivial to unit-test, while :func:`parse_file` is the thin filesystem
wrapper used by the scanner and watcher pipelines.

Limitations
-----------
This is **not** a full Lean 4 grammar — it is a comment- and string-stripping
regex pass over the *declaration heads* of top-level symbols. It correctly
recognises the modifiers Lean 4 actually permits in front of a declaration
(``protected``, ``private``, ``noncomputable``, ``partial``, ``unsafe``) and
tracks ``namespace ... end`` blocks for fully-qualified names. Tactic-block
contents, term-mode bodies and elaborator macros are out of scope.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

# ─── Public symbol kinds emitted by the parser ────────────────────────────────
# (Superset of the database ``symbol_kind`` enum — see ``KIND_TO_DB`` for the
#  mapping into the canonical enum used in Postgres.)
PARSER_KINDS: frozenset[str] = frozenset(
    {
        "def",
        "theorem",
        "lemma",
        "instance",
        "class",
        "structure",
        "inductive",
        "abbrev",
        "axiom",
        "example",
        "opaque",
    }
)

#: Mapping from parser-level kind → DB ``symbol_kind`` enum value.
#: ``lemma`` collapses to ``theorem``; ``example`` is dropped at the DB layer.
KIND_TO_DB: dict[str, str] = {
    "def": "def",
    "theorem": "theorem",
    "lemma": "theorem",
    "instance": "instance",
    "class": "class",
    "structure": "structure",
    "inductive": "inductive",
    "abbrev": "abbrev",
    "axiom": "axiom",
    "opaque": "opaque",
    # ``example`` and ``constant`` deliberately omitted — handled by callers.
}

# Modifiers that may precede a declaration keyword.
_MODIFIERS = r"(?:@\[[^\]]*\]\s+)*(?:protected\s+|private\s+|noncomputable\s+|partial\s+|unsafe\s+)*"

# Identifier pattern — Lean allows dots in qualified names, but a *declaration*
# name is a single identifier (possibly with French quotes / Greek letters).
# Keep this conservative: ASCII + digits + underscore + apostrophe + dot.
_IDENT = r"[A-Za-z_\u00C0-\uFFFF][A-Za-z0-9_'\.\u00C0-\uFFFF]*"

# One regex per kind — anchored at line start (after stripping comments).
_DECL_RE = re.compile(
    rf"""
    ^                                 # start of line
    (?P<mods>{_MODIFIERS})            # optional modifier soup
    (?P<kind>def|theorem|lemma|instance|class|structure|inductive|abbrev|axiom|example|opaque)
    \b
    \s+
    (?P<name>{_IDENT})?               # name (optional for ``example`` / anonymous instance)
    """,
    re.MULTILINE | re.VERBOSE,
)

_IMPORT_RE = re.compile(r"^\s*import\s+([A-Za-z0-9_.]+)\s*$", re.MULTILINE)
_NAMESPACE_OPEN_RE = re.compile(r"^\s*namespace\s+(" + _IDENT + r")\s*$", re.MULTILINE)
_NAMESPACE_CLOSE_RE = re.compile(r"^\s*end\s+(" + _IDENT + r")\s*$", re.MULTILINE)


# ─── Data classes ─────────────────────────────────────────────────────────────


@dataclass(slots=True, frozen=True)
class ParsedSymbol:
    """A single top-level Lean declaration."""

    name: str
    kind: str
    line_start: int
    namespace_path: str
    is_private: bool
    signature_text: str

    @property
    def full_name(self) -> str:
        """Fully-qualified name, e.g. ``Foo.Bar.theorem_name``."""
        return f"{self.namespace_path}.{self.name}" if self.namespace_path else self.name


@dataclass(slots=True, frozen=True)
class ParsedFileContent:
    """Result of parsing in-memory source — no filesystem coupling."""

    imports: list[str] = field(default_factory=list)
    symbols: list[ParsedSymbol] = field(default_factory=list)
    line_count: int = 0


@dataclass(slots=True, frozen=True)
class ParsedFile:
    """Result of parsing a Lean file from disk."""

    path: Path
    imports: list[str]
    symbols: list[ParsedSymbol]
    sha256: str
    line_count: int


# ─── Comment / string scrubbing ───────────────────────────────────────────────


def _strip_comments_and_strings(src: str) -> str:
    """Replace comments and string literals with spaces of equal length.

    Length-preserving so that subsequent regex line numbers (computed via
    ``str.count('\\n', 0, idx)``) line up with the original source.

    Handles:
      - ``--`` line comments
      - ``/- ... -/`` block comments (single nesting level — Lean nests, but
        the false-positive cost of single-level handling is negligible for
        symbol extraction).
      - ``"..."`` string literals (with ``\\"`` escapes).
    """
    out: list[str] = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ""

        # Block comment /- ... -/  (track nesting depth)
        if c == "/" and nxt == "-":
            depth = 1
            j = i + 2
            out.append("  ")
            while j < n and depth > 0:
                cj = src[j]
                cj_next = src[j + 1] if j + 1 < n else ""
                if cj == "/" and cj_next == "-":
                    depth += 1
                    out.append("  ")
                    j += 2
                elif cj == "-" and cj_next == "/":
                    depth -= 1
                    out.append("  ")
                    j += 2
                elif cj == "\n":
                    out.append("\n")
                    j += 1
                else:
                    out.append(" ")
                    j += 1
            i = j
            continue

        # Line comment --
        if c == "-" and nxt == "-":
            j = i
            while j < n and src[j] != "\n":
                out.append(" ")
                j += 1
            i = j
            continue

        # String literal "..."
        if c == '"':
            out.append(" ")
            j = i + 1
            while j < n:
                cj = src[j]
                if cj == "\\" and j + 1 < n:
                    out.append("  ")
                    j += 2
                    continue
                if cj == '"':
                    out.append(" ")
                    j += 1
                    break
                if cj == "\n":
                    out.append("\n")
                else:
                    out.append(" ")
                j += 1
            i = j
            continue

        out.append(c)
        i += 1
    return "".join(out)


# ─── Namespace tracking ───────────────────────────────────────────────────────


def _build_namespace_intervals(scrubbed: str) -> list[tuple[int, int, str]]:
    """Return ``(line_start, line_end_exclusive, namespace_path)`` intervals.

    Implements a simple stack: every ``namespace X`` push, every matching
    ``end X`` pop. Mismatched ``end`` tokens are tolerated (Lean tolerates
    them too in the presence of ``section`` blocks).
    """
    events: list[tuple[int, str, str]] = []  # (line, "open"|"close", name)
    for m in _NAMESPACE_OPEN_RE.finditer(scrubbed):
        line = scrubbed.count("\n", 0, m.start()) + 1
        events.append((line, "open", m.group(1)))
    for m in _NAMESPACE_CLOSE_RE.finditer(scrubbed):
        line = scrubbed.count("\n", 0, m.start()) + 1
        events.append((line, "close", m.group(1)))
    events.sort(key=lambda e: e[0])

    intervals: list[tuple[int, int, str]] = []
    stack: list[tuple[str, int]] = []  # (name, opened_at_line)
    last_line = 1
    current_path = ""

    for line, kind, name in events:
        if line > last_line:
            intervals.append((last_line, line, current_path))
        if kind == "open":
            stack.append((name, line))
            current_path = ".".join(s[0] for s in stack)
        else:  # close
            # Pop until we find the matching name (handle stray ``end``s).
            for k in range(len(stack) - 1, -1, -1):
                if stack[k][0] == name:
                    del stack[k:]
                    break
            current_path = ".".join(s[0] for s in stack)
        last_line = line + 1  # the ``end``/``namespace`` line itself belongs to outer scope

    # Tail interval.
    intervals.append((last_line, 10**9, current_path))
    return intervals


def _namespace_for_line(intervals: list[tuple[int, int, str]], line: int) -> str:
    """Linear lookup — file count of namespaces is tiny in practice."""
    for start, end, path in intervals:
        if start <= line < end:
            return path
    return ""


# ─── Core parser ──────────────────────────────────────────────────────────────


def parse_text(content: str) -> ParsedFileContent:
    """Parse Lean source given as a string. No I/O; safe to unit-test."""
    scrubbed = _strip_comments_and_strings(content)

    imports: list[str] = [m.group(1) for m in _IMPORT_RE.finditer(scrubbed)]

    intervals = _build_namespace_intervals(scrubbed)
    symbols: list[ParsedSymbol] = []
    seen: set[tuple[str, int]] = set()  # de-dupe by (full_name, line)

    for m in _DECL_RE.finditer(scrubbed):
        name = m.group("name")
        if not name:
            # Anonymous declarations (``example``, anonymous ``instance``)
            # — synthesise a deterministic name so we don't lose them.
            name = f"_anon_{m.group('kind')}_{m.start()}"
        kind = m.group("kind")
        mods = m.group("mods") or ""
        is_private = "private" in mods

        # Line number (1-indexed) of the declaration head.
        line = scrubbed.count("\n", 0, m.start()) + 1
        ns_path = _namespace_for_line(intervals, line)

        # Signature text: from the keyword up to ``:=`` or end of line, whichever
        # comes first. We slice from the *original* source so the user sees the
        # real characters (with comments preserved), capped at 4 KiB.
        head_start = m.start()
        slice_end = min(head_start + 4096, len(content))
        chunk = content[head_start:slice_end]
        cut = chunk.find(":=")
        if cut == -1:
            # Take just the first non-empty line.
            nl = chunk.find("\n")
            cut = nl if nl != -1 else len(chunk)
        signature_text = chunk[:cut].strip()

        full = f"{ns_path}.{name}" if ns_path else name
        if (full, line) in seen:
            continue
        seen.add((full, line))

        symbols.append(
            ParsedSymbol(
                name=name,
                kind=kind,
                line_start=line,
                namespace_path=ns_path,
                is_private=is_private,
                signature_text=signature_text,
            )
        )

    return ParsedFileContent(
        imports=imports,
        symbols=symbols,
        line_count=(0 if not content else content.count("\n") + (0 if content.endswith("\n") else 1)),
    )


def parse_file(path: str | Path) -> ParsedFile:
    """Read and parse a Lean file from disk."""
    p = Path(path)
    raw = p.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    content = raw.decode("utf-8", errors="replace")
    parsed = parse_text(content)
    return ParsedFile(
        path=p,
        imports=parsed.imports,
        symbols=parsed.symbols,
        sha256=sha,
        line_count=parsed.line_count,
    )


__all__ = [
    "PARSER_KINDS",
    "KIND_TO_DB",
    "ParsedSymbol",
    "ParsedFile",
    "ParsedFileContent",
    "parse_text",
    "parse_file",
]
