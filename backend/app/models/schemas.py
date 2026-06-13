"""Pydantic IO schemas (API 请求/响应/事件)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ========== Chat ==========
class ChatRequest(BaseModel):
    """非流式 / 流式聊天共用请求体."""

    session_id: str = Field(default="default", description="会话 ID, 用于 LangGraph checkpoint 隔离")
    message: str = Field(..., min_length=1, max_length=8000)
    # 预留: 未来可加 doc_id 白名单 / 工具开关
    doc_ids: list[str] | None = None
    locale: Literal["zh", "en"] = "zh"


class ChatResponse(BaseModel):
    """非流式响应."""

    session_id: str
    message_id: str
    content: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    agent_steps: list[dict[str, Any]] = Field(default_factory=list)
    usage: dict[str, int] = Field(default_factory=dict)
    total_ms: int = 0


# ========== Documents ==========
class DocumentMeta(BaseModel):
    id: str
    filename: str
    mime: str
    size: int
    page_count: int | None = None
    chunk_count: int = 0
    status: Literal["uploading", "parsing", "embedding", "ready", "failed"] = "uploading"
    progress: int = 0
    progress_label: str | None = None
    error: str | None = None
    created_at: float
    sha256: str | None = None
    parser: str | None = None
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    semantic_chunking: bool = False
    contextual_retrieval: bool = False
    meta: dict[str, Any] = Field(default_factory=dict)


class DocumentChunk(BaseModel):
    id: str
    doc_id: str
    parent_id: str | None = None
    chunk_index: int
    text: str
    token_count: int | None = None
    page_no: int | None = None
    heading: str | None = None
    context_prefix: str | None = None
    created_at: float


class IngestResult(BaseModel):
    doc_id: str
    chunk_count: int
    status: Literal["ready", "duplicate"] = "ready"


# ========== Sessions ==========
class SessionMeta(BaseModel):
    id: str
    title: str | None = None
    message_count: int = 0
    created_at: float
    updated_at: float


# ========== Health ==========
class HealthStatus(BaseModel):
    status: Literal["ok", "degraded"]
    llm: bool
    persist: dict[str, Any]
    chroma: bool = False
    version: str


# ========== Streaming events (AG-UI 兼容) ==========
class StreamEvent(BaseModel):
    """统一的 SSE 事件 envelope. 序列化为 `event: <type>\\ndata: <json>\\n\\n`."""

    type: Literal[
        "thinking", "agent_step", "retrieval", "tool_call",
        "token", "citation", "progress", "done", "error",
    ]
    data: dict[str, Any] = Field(default_factory=dict)
    ts: float = Field(default_factory=lambda: __import__("time").time())
