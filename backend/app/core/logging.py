"""结构化日志 (JSON 格式, 便于 LangSmith 解析)."""
from __future__ import annotations

import logging
import sys
from typing import Any

from app.config import settings


class JSONFormatter(logging.Formatter):
    """极简 JSON formatter — 生产用. 开发可切回默认."""

    def format(self, record: logging.LogRecord) -> str:
        import json

        payload: dict[str, Any] = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # 透传 extra 字段
        for k, v in record.__dict__.items():
            if k in (
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "taskName",
            ):
                continue
            try:
                json.dumps(v)
                payload[k] = v
            except (TypeError, ValueError):
                payload[k] = str(v)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging() -> None:
    """初始化根 logger. 在 lifespan 启动时调用."""
    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())

    # 避免重复 handler
    if root.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    if settings.log_level.upper() == "DEBUG":
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
                datefmt="%H:%M:%S",
            )
        )
    else:
        handler.setFormatter(JSONFormatter())
    root.addHandler(handler)

    # 降噪第三方库
    for noisy in ("httpx", "httpcore", "openai", "chromadb", "huggingface_hub"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
