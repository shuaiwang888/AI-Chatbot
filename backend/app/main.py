"""FastAPI 应用入口.

启动顺序 (lifespan):
1. setup_logging
2. restore_from_hf  (持久化恢复, 失败不阻塞)
3. (阶段 2 接入) Chroma client, BGE-M3, reranker 预热
4. (阶段 3 接入) LangGraph checkpointer 初始化

关闭顺序:
1. (阶段 3 接入) flush LangGraph checkpoint
2. push_to_hf  (持久化推送)
3. close_llm  (关闭 LLM httpx client)
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.agents.graph import close_checkpointer, get_compiled_graph
from app.api import chat, documents, health, sessions
from app.config import settings
from app.core.errors import install_exception_handlers
from app.core.logging import setup_logging
from app.deps import close_llm
from app.models import db as app_db
from app.services.embedding import warm_up as warm_embedder
from app.services.persist import push_to_hf, restore_from_hf
from app.services.reranker import warm_up as warm_reranker
from app.services.vector_store import get_chroma

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ===== Startup =====
    setup_logging()
    logger.info("=" * 60)
    logger.info("Starting %s v%s", settings.app_name, __version__)
    logger.info("LLM provider: %s | model: %s", settings.llm_provider, settings.minimax_model)
    logger.info("Data dir: %s", settings.data_dir)
    logger.info("Allowed origins: %s", settings.allowed_origins)

    # 持久化恢复 (不阻塞)
    await restore_from_hf()

    # SQLite schema (元数据 + LangGraph checkpoint 共用 db)
    app_db.init_db()

    # Chroma 客户端 (建立 collection)
    try:
        get_chroma()
        logger.info("ChromaDB ready")
    except Exception as e:  # noqa: BLE001
        logger.warning("ChromaDB init failed (will retry on first request): %s", e)

    # BGE-M3 & Reranker 预热.
    # 必须在主线程 *同步* 执行, 不能 run_in_executor 异步跑 — 因为 FlagEmbedding
    # 在 torch 2.2 + transformers 4.57 组合下, 子线程首次 .to(device) 会撞 meta tensor
    # 错 "Cannot copy out of meta tensor; no data!"; 必须等它 meta→cpu 转移完再 await
    import os
    if settings.embedding_model and not os.environ.get("TESTING"):
        try:
            warm_embedder()
            warm_reranker()
        except Exception as e:  # noqa: BLE001
            logger.warning("Embedder/reranker warm-up failed: %s", e)

    # LangGraph checkpointer 初始化 (不预热, 首次 chat 才编译)
    try:
        # 仅检查 import 路径, 不实际编译
        from app.agents.graph import _build_graph  # noqa: F401
        logger.info("LangGraph importable")
    except Exception as e:  # noqa: BLE001
        logger.warning("LangGraph import failed: %s", e)

    logger.info("Backend ready")
    yield

    # ===== Shutdown =====
    logger.info("Shutting down...")
    try:
        await push_to_hf()
    except Exception as e:  # noqa: BLE001
        logger.warning("Final persist push failed: %s", e)
    await close_checkpointer()
    await close_llm()
    logger.info("Bye")


app = FastAPI(
    title="AI Chatbot",
    version=__version__,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS (个人使用, 信任 GH Pages 域 + 本地)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# 异常处理
install_exception_handlers(app)

# 路由
app.include_router(health.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(sessions.router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
async def root() -> dict:
    return {
        "name": settings.app_name,
        "version": __version__,
        "llm_provider": settings.llm_provider,
        "docs": "/api/docs",
    }
