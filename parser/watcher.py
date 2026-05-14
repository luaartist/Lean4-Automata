"""Lean file watcher daemon.

Watches a project root for ``.lean`` file modifications and incrementally
re-indexes affected files into Postgres + invalidates Redis cache keys.

Design
------
* Debounced per-file timer (default 500ms) collapses bursts of editor
  saves into one re-index pass.
* A SHA-256 *hash gate* short-circuits no-op events (e.g. ``mtime``-only
  touches from build systems) before any database work.
* Each re-index runs in a single explicit transaction.
* Permission errors / unreadable files are logged and skipped — the
  daemon never crashes on them.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
import redis
from psycopg.rows import dict_row
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver

from parser.lean_parser import (
    KIND_TO_DB,
    ParsedFile,
    ParsedSymbol,
    _strip_comments_and_strings,
    parse_file,
)
from parser.scanner import _module_name_for, _normalise_psycopg_dsn

log = logging.getLogger(__name__)

_CACHE_KEY_PREFIX = "lean4:cache:"
_INVALIDATE_CHANNEL = "lean4:invalidate"


# ─── Handler ──────────────────────────────────────────────────────────────────


class LeanFileHandler(FileSystemEventHandler):
    """Debounced incremental re-indexer for Lean source files."""

    def __init__(
        self,
        project_id: int,
        root_dir: Path,
        db_url: str,
        redis_url: str,
        debounce_ms: int = 500,
    ) -> None:
        super().__init__()
        self.project_id = int(project_id)
        self.root_dir = Path(root_dir).resolve()
        self.db_url = _normalise_psycopg_dsn(db_url)
        self.redis_url = redis_url
        self.debounce_ms = int(debounce_ms)

        self._pending: dict[Path, threading.Timer] = {}
        self._lock = threading.Lock()
        self._redis: redis.Redis | None = None
        self._vault_lock = threading.Lock()
        self._proof_vault_enabled = os.environ.get("LEAN_PROOF_VAULT_ENABLED", "1").lower() not in {
            "0",
            "false",
            "no",
            "off",
        }
        self._proof_vault_dir = Path(
            os.environ.get("LEAN_PROOF_VAULT_DIR", "~/.lean4a/proof_vault")
        ).expanduser()
        self._proof_vault_seed_on_start = os.environ.get("LEAN_PROOF_VAULT_SEED_ON_START", "1").lower() not in {
            "0",
            "false",
            "no",
            "off",
        }

    # ── Watchdog callbacks ────────────────────────────────────────────────────

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._schedule(Path(str(event.src_path)))

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._schedule(Path(str(event.src_path)))

    def on_deleted(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._schedule_delete(Path(str(event.src_path)))

    def on_moved(self, event: FileSystemEvent) -> None:  # type: ignore[override]
        if event.is_directory:
            return
        src = Path(str(event.src_path))
        dest = Path(str(getattr(event, "dest_path", "")))
        self._schedule_delete(src)
        if dest:
            self._schedule(dest)

    # ── Scheduling ────────────────────────────────────────────────────────────

    def _schedule(self, path: Path) -> None:
        if not str(path).endswith(".lean"):
            return
        with self._lock:
            existing = self._pending.pop(path, None)
            if existing is not None:
                existing.cancel()
            t = threading.Timer(self.debounce_ms / 1000, self._safe_process, args=(path,))
            t.daemon = True
            self._pending[path] = t
            t.start()

    def _schedule_delete(self, path: Path) -> None:
        if not str(path).endswith(".lean"):
            return
        with self._lock:
            existing = self._pending.pop(path, None)
            if existing is not None:
                existing.cancel()
            t = threading.Timer(self.debounce_ms / 1000, self._safe_delete, args=(path,))
            t.daemon = True
            self._pending[path] = t
            t.start()

    # ── Process / delete (with crash isolation) ───────────────────────────────

    def _safe_process(self, path: Path) -> None:
        try:
            self._process(path)
        except Exception:  # noqa: BLE001
            log.exception("Watcher: failed to process %s", path)
        finally:
            with self._lock:
                self._pending.pop(path, None)

    def _safe_delete(self, path: Path) -> None:
        try:
            self._delete(path)
        except Exception:  # noqa: BLE001
            log.exception("Watcher: failed to delete %s", path)
        finally:
            with self._lock:
                self._pending.pop(path, None)

    # ── Core logic ────────────────────────────────────────────────────────────

    def _rel_path(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.root_dir))
        except (ValueError, OSError):
            # Outside watch root — ignore.
            return ""

    def _process(self, path: Path) -> None:
        if not path.exists():
            log.debug("Watcher: %s vanished before processing", path)
            return
        try:
            raw = path.read_bytes()
        except (OSError, PermissionError) as exc:
            log.warning("Watcher: cannot read %s: %s", path, exc)
            return

        sha = hashlib.sha256(raw).hexdigest()
        rel = self._rel_path(path)
        if not rel:
            log.debug("Watcher: %s outside watch root, skipping", path)
            return

        with psycopg.connect(self.db_url, autocommit=False) as conn:
            # Hash gate.
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, file_hash FROM files "
                    "WHERE project_id = %s AND relative_path = %s",
                    (self.project_id, rel),
                )
                row = cur.fetchone()
            if row is not None and row[1] == sha:
                log.info("Watcher: skipped (hash match) %s", rel)
                return
            self._write_proof_snapshot(rel=rel, raw=raw, sha=sha, event="upsert")

            try:
                parsed = parse_file(path)
            except (OSError, UnicodeError) as exc:
                log.warning("Watcher: parse failed for %s: %s", path, exc)
                return

            module = _module_name_for(Path(rel))
            m = parsed.metrics  # shorthand for metric columns below

            # Single transaction: upsert file → replace symbols → rebuild edges.
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO files
                        (project_id, relative_path, absolute_path, module_name,
                         file_hash, line_count, imports, last_modified,
                         sorry_count, admit_count, sorry_lines, sorry_in_proof_count,
                         theorem_count, proof_completion,
                         native_decide_count, debug_command_count,
                         noncomputable_count, instance_count, declared_axiom_count,
                         simp_attr_count, docstring_count, todo_count,
                         mathlib_import_count)
                    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, now(),
                            %s, %s, %s::jsonb, %s,
                            %s, %s,
                            %s, %s,
                            %s, %s, %s,
                            %s, %s, %s,
                            %s)
                    ON CONFLICT (project_id, relative_path) DO UPDATE
                       SET file_hash = EXCLUDED.file_hash,
                           line_count = EXCLUDED.line_count,
                           imports = EXCLUDED.imports,
                           module_name = EXCLUDED.module_name,
                           absolute_path = EXCLUDED.absolute_path,
                           last_modified = now(),
                           sorry_count = EXCLUDED.sorry_count,
                           admit_count = EXCLUDED.admit_count,
                           sorry_lines = EXCLUDED.sorry_lines,
                           sorry_in_proof_count = EXCLUDED.sorry_in_proof_count,
                           theorem_count = EXCLUDED.theorem_count,
                           proof_completion = EXCLUDED.proof_completion,
                           native_decide_count = EXCLUDED.native_decide_count,
                           debug_command_count = EXCLUDED.debug_command_count,
                           noncomputable_count = EXCLUDED.noncomputable_count,
                           instance_count = EXCLUDED.instance_count,
                           declared_axiom_count = EXCLUDED.declared_axiom_count,
                           simp_attr_count = EXCLUDED.simp_attr_count,
                           docstring_count = EXCLUDED.docstring_count,
                           todo_count = EXCLUDED.todo_count,
                           mathlib_import_count = EXCLUDED.mathlib_import_count
                    RETURNING id
                    """,
                    (
                        self.project_id,
                        rel,
                        str(path.resolve()),
                        module,
                        sha,
                        parsed.line_count,
                        json.dumps(parsed.imports),
                        # metrics
                        m.sorry_count,
                        m.admit_count,
                        json.dumps(m.sorry_lines),
                        m.sorry_in_proof_count,
                        m.theorem_count,
                        m.proof_completion,
                        m.native_decide_count,
                        m.debug_command_count,
                        m.noncomputable_count,
                        m.instance_count,
                        m.declared_axiom_count,
                        m.simp_attr_count,
                        m.docstring_count,
                        m.todo_count,
                        m.mathlib_import_count,
                    ),
                )
                file_row = cur.fetchone()
                assert file_row is not None
                file_id = int(file_row[0])

                # Replace symbols.
                cur.execute("DELETE FROM symbols WHERE file_id = %s", (file_id,))
                rows = list(_symbol_rows(self.project_id, file_id, parsed.symbols))
                if rows:
                    cur.executemany(
                        """
                        INSERT INTO symbols
                            (project_id, file_id, name, full_name, kind,
                             line_start, line_end, signature, is_public, has_sorry)
                        VALUES (%s, %s, %s, %s, %s::symbol_kind, %s, %s, %s, %s, %s)
                        ON CONFLICT (project_id, full_name) DO UPDATE
                           SET file_id = EXCLUDED.file_id,
                               kind = EXCLUDED.kind,
                               line_start = EXCLUDED.line_start,
                               line_end = EXCLUDED.line_end,
                               signature = EXCLUDED.signature,
                               is_public = EXCLUDED.is_public,
                               has_sorry = EXCLUDED.has_sorry
                        """,
                        rows,
                    )

                # Replace dependency edges sourced from this file's symbols.
                cur.execute(
                    """
                    DELETE FROM dependencies
                     WHERE source_symbol_id IN (
                         SELECT id FROM symbols WHERE file_id = %s
                     )
                    """,
                    (file_id,),
                )
                cur.execute(
                    """
                    DELETE FROM file_dependencies WHERE source_file_id = %s
                    """,
                    (file_id,),
                )

                # Rebuild file_dependencies.
                if parsed.imports:
                    cur.execute(
                        """
                        SELECT module_name, id FROM files
                         WHERE project_id = %s AND module_name = ANY(%s)
                        """,
                        (self.project_id, list(parsed.imports)),
                    )
                    module_to_file_id: dict[str, int] = {
                        m: int(i) for m, i in cur.fetchall()
                    }
                    edges_f = [
                        (file_id, target, True)
                        for imp in parsed.imports
                        for target in (module_to_file_id.get(imp),)
                        if target is not None and target != file_id
                    ]
                    if edges_f:
                        cur.executemany(
                            """
                            INSERT INTO file_dependencies
                                (source_file_id, target_file_id, is_direct_import)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (source_file_id, target_file_id) DO NOTHING
                            """,
                            edges_f,
                        )

                # Rebuild symbol-to-symbol dependency edges (textual approximation
                # mirroring scanner phase 4).
                self._rebuild_symbol_edges(cur, file_id, parsed, raw.decode("utf-8", errors="replace"))

            conn.commit()

        log.info("Watcher: re-indexed %s (%d symbols)", rel, len(parsed.symbols))
        self._invalidate_cache(rel, [s.full_name for s in parsed.symbols], file_id=file_id)

    def _rebuild_symbol_edges(
        self,
        cur: psycopg.Cursor,
        file_id: int,
        parsed: ParsedFile,
        src: str,
    ) -> None:
        if not parsed.imports or not parsed.symbols:
            return
        cur.execute(
            """
            SELECT id, full_name, name, file_id FROM symbols
             WHERE project_id = %s
               AND file_id IN (
                   SELECT id FROM files
                    WHERE project_id = %s AND module_name = ANY(%s)
               )
            """,
            (self.project_id, self.project_id, list(parsed.imports)),
        )
        visible: dict[str, int] = {}
        for sid, full_name, name, _fid in cur.fetchall():
            visible.setdefault(full_name, int(sid))
            visible.setdefault(name, int(sid))
        if not visible:
            return

        cur.execute(
            "SELECT id, line_start FROM symbols WHERE file_id = %s ORDER BY line_start",
            (file_id,),
        )
        local_lines: list[tuple[int, int]] = [(int(line), int(sid)) for sid, line in cur.fetchall()]
        if not local_lines:
            return

        scrubbed = _strip_comments_and_strings(src)
        names = sorted(visible.keys(), key=len, reverse=True)
        pattern = re.compile(
            r"(?<![A-Za-z0-9_'\.])(" + "|".join(re.escape(n) for n in names) + r")(?![A-Za-z0-9_'])"
        )

        edges: list[tuple[int, int, str]] = []
        seen: set[tuple[int, int, str]] = set()
        for m in pattern.finditer(scrubbed):
            target_id = visible[m.group(1)]
            line = scrubbed.count("\n", 0, m.start()) + 1
            src_id = -1
            for ls_line, ls_id in local_lines:
                if ls_line <= line:
                    src_id = ls_id
                else:
                    break
            if src_id == -1 or src_id == target_id:
                continue
            key = (src_id, target_id, "direct")
            if key in seen:
                continue
            seen.add(key)
            edges.append(key)
        if edges:
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

    def _delete(self, path: Path) -> None:
        rel = self._rel_path(path)
        if not rel:
            return
        self._write_proof_tombstone(rel=rel)
        deleted_file_id: int | None = None
        with psycopg.connect(self.db_url, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM files
                 WHERE project_id = %s AND relative_path = %s
                 RETURNING id
                """,
                (self.project_id, rel),
            )
            row = cur.fetchone()
            if row is not None:
                deleted_file_id = int(row[0])
        log.info("Watcher: deleted file row for %s", rel)
        self._invalidate_cache(rel, [], file_id=deleted_file_id)

    def seed_proof_vault(self) -> None:
        """Clone all existing Lean files into the proof vault once at startup."""
        if not self._proof_vault_enabled or not self._proof_vault_seed_on_start:
            return
        count = 0
        for path in self.root_dir.rglob("*.lean"):
            try:
                raw = path.read_bytes()
            except (OSError, PermissionError) as exc:
                log.warning("Watcher: seed snapshot read failed for %s: %s", path, exc)
                continue
            rel = self._rel_path(path)
            if not rel:
                continue
            sha = hashlib.sha256(raw).hexdigest()
            self._write_proof_snapshot(rel=rel, raw=raw, sha=sha, event="seed")
            count += 1
        log.info("Watcher: proof vault seed complete (%d files)", count)

    def _write_proof_snapshot(self, rel: str, raw: bytes, sha: str, event: str) -> None:
        """Persist append-only snapshots so proof files survive accidental deletion."""
        if not self._proof_vault_enabled:
            return
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        rel_posix = rel.replace("\\", "/")

        obj_dir = self._proof_vault_dir / "objects" / sha[:2] / sha[2:4]
        obj_path = obj_dir / f"{sha}.lean"
        latest_path = self._proof_vault_dir / "latest" / rel_posix
        manifest_path = self._proof_vault_dir / "manifest.jsonl"

        try:
            obj_dir.mkdir(parents=True, exist_ok=True)
            latest_path.parent.mkdir(parents=True, exist_ok=True)

            if not obj_path.exists():
                obj_path.write_bytes(raw)
                # Read-only object copies reduce accidental mutation risk.
                obj_path.chmod(0o444)

            latest_path.write_bytes(raw)
            entry = {
                "ts": ts,
                "event": event,
                "project_id": self.project_id,
                "relative_path": rel_posix,
                "sha256": sha,
                "size_bytes": len(raw),
                "object_path": str(obj_path),
                "latest_path": str(latest_path),
            }
            with self._vault_lock:
                with manifest_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            log.info("Watcher: proof snapshot saved %s (%s)", rel_posix, sha[:12])
        except OSError as exc:
            log.warning("Watcher: proof snapshot failed for %s: %s", rel_posix, exc)

    def _write_proof_tombstone(self, rel: str) -> None:
        if not self._proof_vault_enabled:
            return
        manifest_path = self._proof_vault_dir / "manifest.jsonl"
        entry = {
            "ts": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ"),
            "event": "delete",
            "project_id": self.project_id,
            "relative_path": rel.replace("\\", "/"),
        }
        try:
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            with self._vault_lock:
                with manifest_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as exc:
            log.warning("Watcher: proof tombstone write failed for %s: %s", rel, exc)

    # ── Cache invalidation ────────────────────────────────────────────────────

    def _redis_client(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.Redis.from_url(self.redis_url)
        return self._redis

    def _invalidate_cache(
        self,
        rel: str,
        symbol_full_names: list[str],
        file_id: int | None = None,
    ) -> None:
        try:
            r = self._redis_client()
            keys_to_delete: list[bytes] = []
            cursor = 0
            while True:
                cursor, keys = r.scan(
                    cursor=cursor, match=f"{_CACHE_KEY_PREFIX}file:{rel}*", count=200
                )
                keys_to_delete.extend(keys)
                if cursor == 0:
                    break
            if file_id is not None:
                cursor = 0
                while True:
                    cursor, keys = r.scan(
                        cursor=cursor,
                        match=f"{_CACHE_KEY_PREFIX}file:{file_id}:*",
                        count=200,
                    )
                    keys_to_delete.extend(keys)
                    if cursor == 0:
                        break
            cursor = 0
            while True:
                cursor, keys = r.scan(
                    cursor=cursor,
                    match=f"{_CACHE_KEY_PREFIX}deps:*",
                    count=200,
                )
                keys_to_delete.extend(keys)
                if cursor == 0:
                    break
            for full in symbol_full_names:
                cursor = 0
                while True:
                    cursor, keys = r.scan(
                        cursor=cursor,
                        match=f"{_CACHE_KEY_PREFIX}symbol:{full}*",
                        count=200,
                    )
                    keys_to_delete.extend(keys)
                    if cursor == 0:
                        break
            if keys_to_delete:
                r.delete(*keys_to_delete)
            r.publish(
                _INVALIDATE_CHANNEL,
                json.dumps({"path": rel, "file_id": file_id, "symbols": symbol_full_names}),
            )
        except Exception:  # noqa: BLE001
            log.exception("Watcher: redis invalidation failed (non-fatal)")


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _symbol_rows(project_id: int, file_id: int, symbols: list[ParsedSymbol]):
    """Yield the positional tuples consumed by ``executemany`` for symbol upserts."""
    seen: set[str] = set()
    for s in symbols:
        db_kind = KIND_TO_DB.get(s.kind)
        if db_kind is None:
            continue
        if s.full_name in seen:
            continue
        seen.add(s.full_name)
        yield (
            project_id,
            file_id,
            s.name,
            s.full_name,
            db_kind,
            s.line_start,
            s.line_start,
            s.signature_text[:8000] if s.signature_text else None,
            not s.is_private,
            s.has_sorry,
        )


# ─── Entry point ──────────────────────────────────────────────────────────────


def main() -> None:
    """CLI entry-point invoked as ``python -m parser.watcher``."""
    logging.basicConfig(
        level=os.environ.get("LEAN_WATCH_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    # Local imports so the module remains importable for tests without the
    # full FastAPI settings stack.
    from app.core.config import settings  # noqa: PLC0415

    watch_root = Path(os.environ.get("LEAN_WATCH_ROOT", "./lean-src")).resolve()
    project_id_raw = os.environ.get("LEAN_PROJECT_ID", "1")
    try:
        project_id = int(project_id_raw)
    except ValueError:
        log.error("LEAN_PROJECT_ID must be an integer (got %r); see schema 0001.", project_id_raw)
        sys.exit(2)

    if not watch_root.exists():
        log.error("Watch root does not exist: %s", watch_root)
        sys.exit(2)

    log.info("┌─────────────────────────────────────────────────────────────")
    log.info("│ Lean4-Automata file watcher")
    log.info("│   project_id = %s", project_id)
    log.info("│   watch_root = %s", watch_root)
    log.info("│   db_url     = %s", _redact(settings.DATABASE_URL))
    log.info("│   redis_url  = %s", _redact(settings.REDIS_URL))
    log.info("│   proof_vault_enabled = %s", os.environ.get("LEAN_PROOF_VAULT_ENABLED", "1"))
    log.info("│   proof_vault_dir     = %s", os.environ.get("LEAN_PROOF_VAULT_DIR", "~/.lean4a/proof_vault"))
    log.info("└─────────────────────────────────────────────────────────────")

    handler = LeanFileHandler(
        project_id=project_id,
        root_dir=watch_root,
        db_url=settings.DATABASE_URL,
        redis_url=settings.REDIS_URL,
    )
    handler.seed_proof_vault()
    try:
        observer: Observer | PollingObserver = Observer()
        observer.schedule(handler, str(watch_root), recursive=True)
        observer.start()
        log.info("Watcher: using inotify observer")
    except OSError as exc:
        log.warning("Watcher: inotify unavailable (%s) — falling back to polling observer", exc)
        observer = PollingObserver(timeout=2)
        observer.schedule(handler, str(watch_root), recursive=True)
        observer.start()
        log.info("Watcher: using polling observer (2s interval)")

    stop_event = threading.Event()

    def _shutdown(signum: int, _frame: Any) -> None:
        log.info("Watcher: signal %s received, shutting down", signum)
        stop_event.set()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        while not stop_event.is_set():
            time.sleep(0.5)
    finally:
        observer.stop()
        observer.join(timeout=5.0)
        log.info("Watcher: stopped cleanly")


def _redact(url: str) -> str:
    """Hide passwords in connection URLs for safe logging."""
    return re.sub(r"(://[^:/@]+:)[^@]+(@)", r"\1***\2", url)


if __name__ == "__main__":
    main()
