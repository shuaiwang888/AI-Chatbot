"""SQLite 元数据 + LangGraph checkpoint 共享 db.

用 sqlite3 stdlib 即可, 暂不引入 SQLAlchemy (减少依赖).
WAL 模式开启, 允许 LangGraph checkpoint 与文档读并发.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from app.config import settings
from app.core.paths import sqlite_dir

logger = logging.getLogger(__name__)

_local = threading.local()


def _connect() -> sqlite3.Connection:
    """每线程一个连接 (sqlite3 本身不线程安全)."""
    conn = sqlite3.connect(
        str(settings.sqlite_db_path),
        check_same_thread=False,
        isolation_level=None,  # autocommit, 手动 BEGIN
        timeout=30.0,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_conn() -> sqlite3.Connection:
    """获取当前线程的连接."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = _connect()
        _local.conn = conn
    return conn


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """显式事务 wrapper."""
    conn = get_conn()
    conn.execute("BEGIN")
    try:
        yield conn
    except Exception:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id              TEXT PRIMARY KEY,
    filename        TEXT NOT NULL,
    mime            TEXT,
    size            INTEGER NOT NULL,
    page_count      INTEGER,
    chunk_count     INTEGER DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'uploading',
    progress        INTEGER DEFAULT 0,         -- 0-100, 用于前端进度条
    progress_label  TEXT,                       -- "正在分块 (12/48)..." 等
    error           TEXT,
    sha256          TEXT NOT NULL,
    parser          TEXT,
    chunk_size      INTEGER,
    chunk_overlap   INTEGER,
    semantic_chunking      INTEGER DEFAULT 0,
    contextual_retrieval   INTEGER DEFAULT 0,
    meta_json       TEXT,
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_documents_sha ON documents(sha256);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);

CREATE TABLE IF NOT EXISTS chunks (
    id              TEXT PRIMARY KEY,
    doc_id          TEXT NOT NULL,
    parent_id       TEXT,
    chunk_index     INTEGER NOT NULL,
    text            TEXT NOT NULL,
    token_count     INTEGER,
    page_no         INTEGER,
    heading         TEXT,
    context_prefix  TEXT,
    created_at      REAL NOT NULL,
    FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunks_parent ON chunks(parent_id);

CREATE TABLE IF NOT EXISTS sessions (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL DEFAULT 'default',
    title           TEXT,
    message_count   INTEGER DEFAULT 0,
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    citations_json  TEXT,
    tool_calls_json TEXT,
    created_at      REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, created_at);
"""


def init_db() -> None:
    """启动时调用. 幂等."""
    sqlite_dir()
    conn = get_conn()
    conn.executescript(SCHEMA)
    # 在线迁移: 给旧 documents 表加新列 (progress / parser / chunk_size 等).
    # 失败无害 (列已存在).
    _MIGRATIONS = [
        "ALTER TABLE documents ADD COLUMN progress INTEGER DEFAULT 0",
        "ALTER TABLE documents ADD COLUMN progress_label TEXT",
        "ALTER TABLE documents ADD COLUMN parser TEXT",
        "ALTER TABLE documents ADD COLUMN chunk_size INTEGER",
        "ALTER TABLE documents ADD COLUMN chunk_overlap INTEGER",
        "ALTER TABLE documents ADD COLUMN semantic_chunking INTEGER DEFAULT 0",
        "ALTER TABLE documents ADD COLUMN contextual_retrieval INTEGER DEFAULT 0",
    ]
    for sql in _MIGRATIONS:
        try:
            conn.execute(sql)
        except Exception:  # noqa: BLE001
            pass  # 列已存在, 跳过
    logger.info("DB schema ensured at %s", settings.sqlite_db_path)


# ========== Document CRUD ==========
def doc_insert(doc: dict[str, Any]) -> None:
    """doc 必须含: id, filename, size, sha256, created_at, updated_at."""
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO documents (id, filename, mime, size, page_count, chunk_count,
                               status, progress, progress_label, error, sha256,
                               parser, chunk_size, chunk_overlap,
                               semantic_chunking, contextual_retrieval,
                               meta_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            doc["id"], doc["filename"], doc.get("mime"), doc["size"],
            doc.get("page_count"), doc.get("chunk_count", 0),
            doc.get("status", "uploading"),
            doc.get("progress", 0), doc.get("progress_label"),
            doc.get("error"),
            doc["sha256"], doc.get("parser"),
            doc.get("chunk_size"), doc.get("chunk_overlap"),
            int(bool(doc.get("semantic_chunking", False))),
            int(bool(doc.get("contextual_retrieval", False))),
            json.dumps(doc.get("meta", {}), ensure_ascii=False),
            doc["created_at"], doc.get("updated_at", doc["created_at"]),
        ),
    )


def doc_update_status(
    doc_id: str,
    status: str,
    *,
    error: str | None = None,
    chunk_count: int | None = None,
    page_count: int | None = None,
    progress: int | None = None,
    progress_label: str | None = None,
) -> None:
    conn = get_conn()
    sets = ["status = ?", "updated_at = ?"]
    params: list[Any] = [status, time.time()]
    if error is not None:
        sets.append("error = ?")
        params.append(error)
    if chunk_count is not None:
        sets.append("chunk_count = ?")
        params.append(chunk_count)
    if page_count is not None:
        sets.append("page_count = ?")
        params.append(page_count)
    if progress is not None:
        sets.append("progress = ?")
        params.append(max(0, min(100, int(progress))))
    if progress_label is not None:
        sets.append("progress_label = ?")
        params.append(progress_label)
    params.append(doc_id)
    conn.execute(f"UPDATE documents SET {', '.join(sets)} WHERE id = ?", params)


def doc_get(doc_id: str) -> dict[str, Any] | None:
    row = get_conn().execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    return _row_to_doc(row) if row else None


def doc_find_by_sha256(sha: str) -> dict[str, Any] | None:
    row = get_conn().execute(
        "SELECT * FROM documents WHERE sha256 = ? AND status = 'ready' ORDER BY created_at DESC LIMIT 1",
        (sha,),
    ).fetchone()
    return _row_to_doc(row) if row else None


def doc_list(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    rows = get_conn().execute(
        "SELECT * FROM documents ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return [_row_to_doc(r) for r in rows]


def doc_delete(doc_id: str) -> bool:
    cur = get_conn().execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    return cur.rowcount > 0


def _row_to_doc(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    if d.get("meta_json"):
        try:
            d["meta"] = json.loads(d["meta_json"])
        except json.JSONDecodeError:
            d["meta"] = {}
    d.pop("meta_json", None)
    # 拆出 boolean 字段, 方便前端直接使用
    d["semantic_chunking"] = bool(d.get("semantic_chunking"))
    d["contextual_retrieval"] = bool(d.get("contextual_retrieval"))
    return d


# ========== Chunk CRUD (用于上下文回查, 实际检索走 Chroma) ==========
def chunk_insert_bulk(chunks: list[dict[str, Any]]) -> None:
    if not chunks:
        return
    conn = get_conn()
    with transaction():
        conn.executemany(
            """
            INSERT OR REPLACE INTO chunks
            (id, doc_id, parent_id, chunk_index, text, token_count, page_no, heading, context_prefix, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    c["id"], c["doc_id"], c.get("parent_id"), c["chunk_index"],
                    c["text"], c.get("token_count"), c.get("page_no"),
                    c.get("heading"), c.get("context_prefix"), c.get("created_at", time.time()),
                )
                for c in chunks
            ],
        )


def chunk_get_by_doc(doc_id: str, limit: int = 200) -> list[dict[str, Any]]:
    rows = get_conn().execute(
        "SELECT * FROM chunks WHERE doc_id = ? ORDER BY chunk_index LIMIT ?",
        (doc_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def chunk_delete_by_doc(doc_id: str) -> int:
    cur = get_conn().execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
    return cur.rowcount


# ========== Session / Message CRUD (阶段 3 实际使用) ==========
def session_upsert(session_id: str, user_id: str = "default", title: str | None = None) -> None:
    now = time.time()
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO sessions (id, user_id, title, message_count, created_at, updated_at)
        VALUES (?, ?, ?, 0, ?, ?)
        ON CONFLICT(id) DO UPDATE SET updated_at = excluded.updated_at
        """,
        (session_id, user_id, title, now, now),
    )


def session_list(limit: int = 50) -> list[dict[str, Any]]:
    rows = get_conn().execute(
        "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def session_get(session_id: str) -> dict[str, Any] | None:
    row = get_conn().execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return dict(row) if row else None


def session_delete(session_id: str) -> bool:
    cur = get_conn().execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    return cur.rowcount > 0


def message_insert(msg: dict[str, Any]) -> None:
    now = msg.get("created_at", time.time())
    conn = get_conn()
    with transaction():
        conn.execute(
            """
            INSERT INTO messages (id, session_id, role, content, citations_json, tool_calls_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                msg["id"], msg["session_id"], msg["role"], msg["content"],
                json.dumps(msg.get("citations", []), ensure_ascii=False),
                json.dumps(msg.get("tool_calls", []), ensure_ascii=False),
                now,
            ),
        )
        # 更新 session 计数
        conn.execute(
            "UPDATE sessions SET message_count = message_count + 1, updated_at = ? WHERE id = ?",
            (now, msg["session_id"]),
        )


def message_list_by_session(session_id: str, limit: int = 200) -> list[dict[str, Any]]:
    rows = get_conn().execute(
        "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at LIMIT ?",
        (session_id, limit),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("citations_json", "tool_calls_json"):
            v = d.pop(k, None)
            if v:
                try:
                    d[k.removesuffix("_json")] = json.loads(v)
                except json.JSONDecodeError:
                    d[k.removesuffix("_json")] = []
        out.append(d)
    return out
