"""Persistent disk path helpers.

HF Spaces 免费版 `/data` 是持久卷挂载点 (即使容器重启也保留).
在本地 dev 时, 退回到仓库内 `./data/`.
"""
from __future__ import annotations

from pathlib import Path

from app.config import settings


def data_dir() -> Path:
    """根数据目录 (确保存在)."""
    p = Path(settings.data_dir).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def upload_dir() -> Path:
    """用户上传的原始文件目录."""
    p = data_dir() / "uploads"
    p.mkdir(parents=True, exist_ok=True)
    return p


def sqlite_dir() -> Path:
    """SQLite 文件 (元数据 + LangGraph checkpoint) 目录."""
    p = data_dir() / "sqlite"
    p.mkdir(parents=True, exist_ok=True)
    return p


def chroma_dir() -> Path:
    """ChromaDB 持久化目录."""
    p = data_dir() / "chroma"
    p.mkdir(parents=True, exist_ok=True)
    return p


def hf_cache_dir() -> Path:
    """HuggingFace 模型缓存目录 (避免重复下载)."""
    p = data_dir() / ".cache" / "huggingface"
    p.mkdir(parents=True, exist_ok=True)
    return p
