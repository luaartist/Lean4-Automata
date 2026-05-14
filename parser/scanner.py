"""Full-scan worker — five-phase synchronous indexing pipeline.

This module is invoked from a Celery task body (see :mod:`workers.tasks`),
so it deliberately uses **synchronous** ``psycopg`` (psycopg3) and the
synchronous Redis client. Async drivers buy us nothing inside a
worker process and complicate transaction management.

Schema notes
------------
The Phase-1 Alembic schema (``0001_initial_schema.py``) uses ``Integer``
primary keys for ``projects``/``files``/``symbols``, not UUIDs as the
Phase-2 design doc presupposed. We honour the existing schema verbatim:

* ``files`` is keyed by ``(project_id, relative_path)``
* ``symbols`` is keyed by ``(project_id, full_name)``
* ``dependencies`` is symbol→symbol with a ``dependency_type`` enum
* ``file_dependencies`` is ``(source_file_id, target_file_id)``

The materialized views ``dependency_stats`` and ``module_metrics`` lack
unique indexes, so we refresh them **non-concurrently**.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
import redis
from psycopg.rows import dict_row

from parser.lean_parser import (
    KIND_TO_DB,
    ParsedFile,
    ParsedSymbol,
    parse_file,
)

log = logging.getLogger(__name__)

# Directories that should never appear in a Lean source index.
_EXCLUDED_DIR_NAMES: frozenset[str] = frozenset(
    {"lake-packages", ".lake", "build", ".git", "node_modules"}
)

# Cache key prefix used by the FastAPI query layer.
_CACHE_KEY_PREFIX = "lean4:cache:"


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _module_name_for(rel: Path) -> str:
    """Convert ``Foo/Bar/Baz.lean`` → ``Foo.Bar.Baz`` (Lean 4 module convention)."""
    parts = list(rel.with_suffix("").parts)
    return ".".join(parts)


def _to_db_kind(parser_kind: str) -> str | None:
    """Map a parser kind to a DB enum value, or ``None`` to drop the symbol."""
    return KIND_TO_DB.get(parser_kind)


def _normalise_psycopg_dsn(url: str) -> str:
    """psycopg3 doesn't understand SQLAlchemy's ``+asyncpg`` / ``+psycopg`` suffixes."""
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + url[len("postgresql+asyncpg://") :]
    if url.startswith("postgresql+psycopg://"):
        return "postgresql://" + url[len("postgresql+psycopg://") :]
    return url


# ─── Scanner ──────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class _FileRow:
    """Minimal in-memory record we carry between phases."""

    rel_path: str
    abs_path: Path
    parsed: ParsedFile
    file_id: int = -1


class FullScanner:
    """Run a complete index of ``root_dir`` for ``project_id`` against the DB.

    The five phases are intentionally separated so each can be retried,
    benchmarked and logged independently.
    """

    def __init__(
        self,
        project_id: int,
        root_dir: Path,
        db_url: str,
        redis_url: str,
    ) -> None:
        self.project_id = int(project_id)
        self.root_dir = Path(root_dir).resolve()
        self.db_url = _normalise_psycopg_dsn(db_url)
        self.redis_url = redis_url

    # ── Public entry-point ────────────────────────────────────────────────────

    def run(self) -> dict[str, Any]:
        run_id: int = -1
        with psycopg.connect(self.db_url, autocommit=False) as conn:
            self._conn = conn
            try:
                run_id = self._start_index_run()
                files = self._phase1_discover()
                self._phase2_imports(files)
                self._phase3_symbols(files)
                self._phase4_dependency_edges(files)
                symbols_total = sum(len(f.parsed.symbols) for f in files)
                self._phase5_finalize(run_id, len(files), symbols_total)
                return {
                    "run_id": run_id,
                    "status": "ok",
                    "files": len(files),
                    "symbols": symbols_total,
                }
            except Exception as exc:  # noqa: BLE001
                log.exception("Full scan failed for project_id=%s", self.project_id)
                if run_id != -1:
                    self._fail_index_run(run_id, str(exc))
                raise

    # ── Bookkeeping ───────────────────────────────────────────────────────────

    def _start_index_run(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO index_runs (project_id, run_type, status)
                VALUES (%s, 'full_scan', 'running')
                RETURNING id
                """,
                (self.project_id,),
            )
            row = cur.fetchone()
            assert row is not None
            run_id = int(row[0])
        self._conn.commit()
        log.info("index_run %s started for project %s", run_id, self.project_id)
        return run_id

    def _fail_index_run(self, run_id: int, message: str) -> None:
        try:
            with psycopg.connect(self.db_url, autocommit=True) as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE index_runs
                       SET status = 'failed',
                           completed_at = now(),
                           errors = errors || %s::jsonb
                     WHERE id = %s
                    """,
                    (json.dumps([{"error": message}]), run_id),
                )
        except Exception:  # noqa: BLE001
            log.exception("Failed to mark index_run=%s as failed", run_id)

    # ── Phase 1: discovery ────────────────────────────────────────────────────

    def _phase1_discover(self) -> list[_FileRow]:
        log.info("Phase 1: discovering .lean files under %s", self.root_dir)
        out: list[_FileRow] = []
        for p in sorted(self.root_dir.rglob("*.lean")):
            if any(part in _EXCLUDED_DIR_NAMES for part in p.parts):
                continue
            rel = p.relative_to(self.root_dir)
            try:
                parsed = parse_file(p)
            except (OSError, UnicodeError) as exc:
                log.warning("Skipping unreadable file %s: %s", p, exc)
                continue
            out.append(_FileRow(rel_path=str(rel), abs_path=p, parsed=parsed))
        log.info("Phase 1: %d files discovered", len(out))
        return out

    # ── Phase 2: file rows + import edges ─────────────────────────────────────

    def _phase2_imports(self, files: list[_FileRow]) -> None:
        log.info("Phase 2: upserting %d file rows", len(files))
        if not files:
            return

        with self._conn.cursor() as cur:
            for i, f in enumerate(files, 1):
                module = _module_name_for(Path(f.rel_path))
                cur.execute(
                    """
                    INSERT INTO files
                        (project_id, relative_path, absolute_path, module_name,
                         file_hash, line_count, char_count, imports, last_modified)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, now())
                    ON CONFLICT (project_id, relative_path) DO UPDATE
                       SET file_hash = EXCLUDED.file_hash,
                           line_count = EXCLUDED.line_count,
                           char_count = EXCLUDED.char_count,
                           imports = EXCLUDED.imports,
                           module_name = EXCLUDED.module_name,
                           absolute_path = EXCLUDED.absolute_path,
                           last_modified = now()
                    RETURNING id
                    """,
                    (
                        self.project_id,
                        f.rel_path,
                        str(f.abs_path),
                        module,
                        f.parsed.sha256,
                        f.parsed.line_count,
                        sum(1 for _ in open(f.abs_path, "rb")) if False else None,
                        json.dumps(f.parsed.imports),
                    ),
                )
                row = cur.fetchone()
                assert row is not None
                f.file_id = int(row[0])
                if i % 100 == 0:
                    log.info("Phase 2: %d / %d files upserted", i, len(files))
        self._conn.commit()

        # Build file_dependencies: source_file → file whose module_name matches an import.
        log.info("Phase 2: building file_dependencies edges")
        module_to_file_id: dict[str, int] = {
            _module_name_for(Path(f.rel_path)): f.file_id for f in files
        }
        with self._conn.cursor() as cur:
            cur.execute(
                "DELETE FROM file_dependencies WHERE source_file_id = ANY(%s)",
                ([f.file_id for f in files],),
            )
            edges: list[tuple[int, int, bool]] = []
            for f in files:
                seen: set[int] = set()
                for imp in f.parsed.imports:
                    target = module_to_file_id.get(imp)
                    if target is None or target == f.file_id or target in seen:
                        continue
                    seen.add(target)
                    edges.append((f.file_id, target, True))
            if edges:
                cur.executemany(
                    """
                    INSERT INTO file_dependencies
                        (source_file_id, target_file_id, is_direct_import)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (source_file_id, target_file_id) DO NOTHING
                    """,
                    edges,
                )
        self._conn.commit()
        log.info("Phase 2: complete")

    # ── Phase 3: symbol rows ──────────────────────────────────────────────────

    def _phase3_symbols(self, files: list[_FileRow]) -> None:
        log.info("Phase 3: upserting symbols")
        with self._conn.cursor() as cur:
            for i, f in enumerate(files, 1):
                # Replace-all-symbols-for-file is the simplest correct semantics.
                cur.execute("DELETE FROM symbols WHERE file_id = %s", (f.file_id,))
                rows = list(_symbol_insert_rows(self.project_id, f.file_id, f.parsed.symbols))
                if rows:
                    cur.executemany(
                        """
                        INSERT INTO symbols
                            (project_id, file_id, name, full_name, kind,
                             line_start, line_end, signature, is_public)
                        VALUES (%s, %s, %s, %s, %s::symbol_kind, %s, %s, %s, %s)
                        ON CONFLICT (project_id, full_name) DO UPDATE
                           SET file_id = EXCLUDED.file_id,
                               kind = EXCLUDED.kind,
                               line_start = EXCLUDED.line_start,
                               line_end = EXCLUDED.line_end,
                               signature = EXCLUDED.signature,
                               is_public = EXCLUDED.is_public
                        """,
                        rows,
                    )
                if i % 100 == 0:
                    log.info("Phase 3: %d / %d files indexed", i, len(files))
        self._conn.commit()

    # ── Phase 4: dependency edges ─────────────────────────────────────────────

    def _phase4_dependency_edges(self, files: list[_FileRow]) -> None:
        """Resolve symbol references → ``dependencies`` rows.

        Strategy
        ~~~~~~~~
        For each file, build the *visible* symbol set: every symbol defined
        in any of the file's transitively-imported modules **plus** the
        file's own symbols. Then word-scan the (comment-/string-stripped)
        source for occurrences of those names and attribute each match to
        the local symbol whose line range encloses the match.

        This is intentionally a textual approximation — Lean macros and
        notation cannot be resolved without the elaborator. It's accurate
        enough to populate the graph for the query API.
        """
        log.info("Phase 4: resolving dependency edges")

        module_to_file_id: dict[str, int] = {
            _module_name_for(Path(f.rel_path)): f.file_id for f in files
        }

        # ── Pull every (id, full_name, file_id) for the project once.
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, full_name, name, file_id
                  FROM symbols
                 WHERE project_id = %s
                """,
                (self.project_id,),
            )
            all_symbols = cur.fetchall()

        symbols_by_file: dict[int, list[dict[str, Any]]] = {}
        for s in all_symbols:
            symbols_by_file.setdefault(s["file_id"], []).append(s)

        # Reset edges sourced from the files we're (re-)indexing.
        local_symbol_ids = [s["id"] for f in files for s in symbols_by_file.get(f.file_id, [])]
        if local_symbol_ids:
            with self._conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM dependencies WHERE source_symbol_id = ANY(%s)",
                    (local_symbol_ids,),
                )
            self._conn.commit()

        edges: list[tuple[int, int, str]] = []
        edge_seen: set[tuple[int, int, str]] = set()

        for f in files:
            local_syms = symbols_by_file.get(f.file_id, [])
            if not local_syms:
                continue

            # Build (name → id) lookup of imported symbols.
            visible: dict[str, int] = {}
            for imp in f.parsed.imports:
                target_fid = module_to_file_id.get(imp)
                if target_fid is None:
                    continue
                for s in symbols_by_file.get(target_fid, []):
                    visible.setdefault(s["full_name"], s["id"])
                    visible.setdefault(s["name"], s["id"])
            if not visible:
                continue

            # Sort local symbols by line so we can attribute matches.
            local_sorted = sorted(local_syms, key=lambda s: s["file_id"])
            # Build (line_start, id) ordered list.
            local_lines: list[tuple[int, int]] = []
            with self._conn.cursor() as cur:
                cur.execute(
                    "SELECT id, line_start FROM symbols WHERE file_id = %s ORDER BY line_start",
                    (f.file_id,),
                )
                local_lines = [(int(line), int(sid)) for sid, line in cur.fetchall()]
            if not local_lines:
                continue

            try:
                src = f.abs_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            from parser.lean_parser import _strip_comments_and_strings  # noqa: PLC0415

            scrubbed = _strip_comments_and_strings(src)

            # Compile one big alternation of visible names (escaped, word-bounded).
            names = sorted(visible.keys(), key=len, reverse=True)
            if not names:
                continue
            pattern = re.compile(
                r"(?<![A-Za-z0-9_'\.])(" + "|".join(re.escape(n) for n in names) + r")(?![A-Za-z0-9_'])"
            )

            for m in pattern.finditer(scrubbed):
                target_id = visible[m.group(1)]
                line = scrubbed.count("\n", 0, m.start()) + 1
                # Find the local symbol whose line_start is the greatest <= line.
                src_id = -1
                for ls_line, ls_id in local_lines:
                    if ls_line <= line:
                        src_id = ls_id
                    else:
                        break
                if src_id == -1 or src_id == target_id:
                    continue
                key = (src_id, target_id, "direct")
                if key in edge_seen:
                    continue
                edge_seen.add(key)
                edges.append(key)

        if edges:
            log.info("Phase 4: inserting %d dependency edges", len(edges))
            with self._conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO dependencies
                        (source_symbol_id, target_symbol_id, dependency_type)
                    VALUES (%s, %s, %s::dependency_type)
                    ON CONFLICT (source_symbol_id, target_symbol_id, dependency_type)
                       DO NOTHING
                    """,
                    edges,
                )
            self._conn.commit()
        log.info("Phase 4: complete")

    # ── Phase 5: finalisation ─────────────────────────────────────────────────

    def _phase5_finalize(self, run_id: int, file_count: int, symbol_count: int) -> None:
        log.info("Phase 5: refreshing materialized views and invalidating cache")
        # MVs lack unique indexes — non-CONCURRENTLY refresh is required.
        with self._conn.cursor() as cur:
            cur.execute("REFRESH MATERIALIZED VIEW dependency_stats")
            cur.execute("REFRESH MATERIALIZED VIEW module_metrics")
            cur.execute(
                """
                UPDATE index_runs
                   SET status = 'completed',
                       completed_at = now(),
                       files_processed = %s,
                       symbols_indexed = %s
                 WHERE id = %s
                """,
                (file_count, symbol_count, run_id),
            )
        self._conn.commit()

        # Redis cache invalidation — SCAN, not KEYS.
        try:
            r = redis.Redis.from_url(self.redis_url)
            cursor = 0
            deleted = 0
            while True:
                cursor, keys = r.scan(cursor=cursor, match=f"{_CACHE_KEY_PREFIX}*", count=500)
                if keys:
                    deleted += r.delete(*keys)
                if cursor == 0:
                    break
            log.info("Phase 5: invalidated %d cache keys", deleted)
        except Exception:  # noqa: BLE001
            log.exception("Phase 5: redis invalidation failed (non-fatal)")


# ─── Module helpers ───────────────────────────────────────────────────────────


def _symbol_insert_rows(
    project_id: int, file_id: int, symbols: list[ParsedSymbol]
):
    """Yield positional tuples for the symbols-INSERT executemany call."""
    seen_full_names: set[str] = set()
    for s in symbols:
        db_kind = _to_db_kind(s.kind)
        if db_kind is None:  # ``example`` etc. — drop.
            continue
        full = s.full_name
        # Within a single file, a duplicate full_name should never happen, but
        # defend against it (e.g. ``private`` rebinding) to satisfy the
        # (project_id, full_name) unique constraint deterministically.
        if full in seen_full_names:
            continue
        seen_full_names.add(full)
        yield (
            project_id,
            file_id,
            s.name,
            full,
            db_kind,
            s.line_start,
            s.line_start,  # line_end ≈ line_start (single-line head)
            s.signature_text[:8000] if s.signature_text else None,
            not s.is_private,
        )


__all__ = ["FullScanner"]
