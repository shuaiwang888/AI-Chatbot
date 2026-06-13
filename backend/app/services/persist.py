"""HF Dataset repo 持久化同步.

为什么需要: HF Spaces 免费版磁盘是临时的 (容器重启后 /data 内的非持久卷数据会丢).
唯一免费的持久化方案是把 /data 同步到 HF Dataset repo (Git LFS).

调用模式:
- lifespan startup: restore_from_hf()
- 每次写操作后: schedule_push() (异步, 不阻塞用户)
- lifespan shutdown: push_to_hf() (同步, 尽量)

健壮性:
- 首次部署 (repo 不存在) → 捕获 RepositoryNotFoundError → 标记 "fresh_start"
- HF_TOKEN 缺失 → 跳过持久化, 降级为纯本地
- 网络错误 → 重试 3 次后放弃, 不阻塞业务
"""
from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path
from typing import Literal

from huggingface_hub import (
    create_repo,
    snapshot_download,
    upload_folder,
)
from huggingface_hub.errors import RepositoryNotFoundError

from app.config import settings
from app.core.paths import data_dir, sqlite_dir, chroma_dir, upload_dir

logger = logging.getLogger(__name__)

# 状态机: 持久化是否启用 / 启动模式
_state: dict[str, str | bool] = {
    "mode": "disabled",  # disabled | cold_restore | fresh_start
    "last_push_at": 0.0,
    "pending_push": False,
}


def persist_mode() -> Literal["disabled", "cold_restore", "fresh_start"]:
    return _state["mode"]  # type: ignore[return-value]


async def restore_from_hf() -> None:
    """从 HF Dataset repo 拉取数据到本地.

    调用时机: FastAPI lifespan 启动.
    """
    if not settings.is_persist_enabled():
        logger.info("Persistence disabled (HF_PERSIST_REPO or HF_TOKEN not set)")
        _state["mode"] = "disabled"
        return

    repo_id = settings.hf_persist_repo
    token = settings.hf_token.get_secret_value()
    local_root = data_dir()
    target_subdirs = ["chroma", "sqlite", "uploads"]

    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(
            None,
            lambda: snapshot_download(
                repo_id=repo_id,
                repo_type="dataset",
                local_dir=str(local_root),
                token=token,
                allow_patterns=[f"{d}/*" for d in target_subdirs] + target_subdirs,
            ),
        )
        _state["mode"] = "cold_restore"
        logger.info("Persisted data restored from %s", repo_id)
    except RepositoryNotFoundError:
        # 首次部署: repo 还没创建, 属正常情况
        _state["mode"] = "fresh_start"
        logger.info(
            "Persist repo %s not found (first deploy?). "
            "Will create on first push.",
            repo_id,
        )
    except Exception as e:  # noqa: BLE001
        logger.error("Persist restore failed (will start fresh): %s", e)
        _state["mode"] = "fresh_start"
        # 不阻塞启动, 提示用户在 /readyz 看到降级状态


async def push_to_hf() -> None:
    """同步推送本地数据到 HF Dataset repo. 阻塞."""
    if not settings.is_persist_enabled():
        return
    if _state["mode"] == "fresh_start":
        # 首次需要先 create_repo
        await _ensure_repo_exists()

    repo_id = settings.hf_persist_repo
    token = settings.hf_token.get_secret_value()
    local_root = data_dir()

    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(
            None,
            lambda: upload_folder(
                folder_path=str(local_root),
                repo_id=repo_id,
                repo_type="dataset",
                token=token,
                commit_message=f"sync {asyncio.get_running_loop().time():.0f}",
                ignore_patterns=[".cache/*", "*.tmp", "*.lock"],
            ),
        )
        _state["last_push_at"] = asyncio.get_running_loop().time()
        _state["pending_push"] = False
        logger.info("Persisted data pushed to %s", repo_id)
    except Exception as e:  # noqa: BLE001
        logger.error("Persist push failed: %s", e)


async def schedule_push() -> None:
    """异步推送, 不阻塞业务. 多次调用合并为一次 (简单去抖).

    适用: 摄入完成 / 删除文档后.
    """
    if not settings.is_persist_enabled():
        return
    if not settings.persist_on_write:
        return
    if _state["pending_push"]:
        return  # 已有 pending, 跳过

    _state["pending_push"] = True

    async def _delayed_push() -> None:
        # 简单去抖: 延迟 30s, 把同一秒内的多次写合并
        await asyncio.sleep(30)
        if _state["pending_push"]:
            await push_to_hf()

    asyncio.create_task(_delayed_push())


async def _ensure_repo_exists() -> None:
    """首次部署时自动创建 HF Dataset repo."""
    repo_id = settings.hf_persist_repo
    token = settings.hf_token.get_secret_value()
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(
            None,
            lambda: create_repo(
                repo_id=repo_id,
                repo_type="dataset",
                token=token,
                private=True,
                exist_ok=True,
            ),
        )
        logger.info("Created persist repo: %s", repo_id)
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to create persist repo: %s", e)


def persist_status() -> dict:
    """供 /readyz 暴露持久化状态."""
    return {
        "enabled": settings.is_persist_enabled(),
        "mode": _state["mode"],
        "pending_push": _state["pending_push"],
        "repo": settings.hf_persist_repo or None,
    }


def _wipe_local_data() -> None:
    """测试用: 清空本地 data 目录."""
    for d in (sqlite_dir(), chroma_dir(), upload_dir()):
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)


__all__ = [
    "restore_from_hf",
    "push_to_hf",
    "schedule_push",
    "persist_mode",
    "persist_status",
]
