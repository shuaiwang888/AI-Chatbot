"""Phase 1 smoke test — 本地手动执行.

用法:
    cd backend
    python tests/unit/smoke_phase1.py

前置:
    pip install -r requirements.txt
    复制 .env.example 为 .env, 填入 MINIMAX_API_KEY (或暂时留空, 部分用例会失败)

测试覆盖:
    1. 配置加载
    2. FastAPI app 创建
    3. /healthz 端点
    4. /readyz 端点 (无 LLM key 时返回 degraded, 不报错)
    5. /api/v1/chat 端点 (需要 API key)
    6. /api/v1/chat/stream 端点 (SSE)
    7. persist 模块冷启动处理
    8. LLM factory 错误处理
"""
from __future__ import annotations

import os
os.environ["TESTING"] = "true"

import asyncio
import json

def _has_llm_key() -> bool:
    try:
        from app.config import settings
        val = settings.minimax_api_key.get_secret_value()
        return bool(val and "your-api-key" not in val and val != "mock" and val != "")
    except Exception:  # noqa: BLE001
        return False
import sys
import time
from pathlib import Path


def section(title: str) -> None:
    print(f"\n{'=' * 60}\n  {title}\n{'=' * 60}")


def check(label: str, ok: bool, detail: str = "") -> bool:
    icon = "✅" if ok else "❌"
    print(f"  {icon} {label}" + (f" — {detail}" if detail else ""))
    return ok


async def main() -> int:
    # 强制非交互 (避免 Rich / PrettyPrint)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    results: list[bool] = []

    # ========== 1. 配置加载 ==========
    section("1. 配置加载")
    try:
        from app.config import settings  # noqa: F401
        results.append(check("settings 单例", True, f"data_dir={settings.data_dir}"))
        results.append(check(
            "LLM provider 可识别", settings.llm_provider in {"minimax", "openai", "anthropic", "qwen"},
            f"={settings.llm_provider}",
        ))
        results.append(check("数据目录可写", settings.data_dir.exists()))
    except Exception as e:  # noqa: BLE001
        results.append(check("配置加载", False, str(e)))
        return 1

    # ========== 2. FastAPI app 创建 ==========
    section("2. FastAPI app")
    try:
        from app.main import app
        routes = [r.path for r in app.routes if hasattr(r, "path")]
        results.append(check("app 创建", True, f"routes={len(routes)}"))
        for needed in ("/api/v1/healthz", "/api/v1/readyz",
                       "/api/v1/chat", "/api/v1/chat/stream",
                       "/api/v1/documents", "/api/v1/sessions"):
            results.append(check(f"  路由 {needed}", needed in routes))
    except Exception as e:  # noqa: BLE001
        results.append(check("app 创建", False, str(e)))
        return 1

    # ========== 3. /healthz via TestClient ==========
    section("3. HTTP 端点 (TestClient, 无 LLM 调用)")
    try:
        from fastapi.testclient import TestClient
        with TestClient(app) as client:
            r = client.get("/api/v1/healthz")
            results.append(check("GET /healthz", r.status_code == 200, f"status={r.status_code}"))
            if r.status_code == 200:
                body = r.json()
                results.append(check("  响应含 persist 状态", "persist" in body, f"mode={body.get('persist', {}).get('mode')}"))

            r = client.get("/api/v1/readyz")
            results.append(check("GET /readyz", r.status_code in (200, 503), f"status={r.status_code}"))
    except Exception as e:  # noqa: BLE001
        results.append(check("TestClient", False, str(e)))

    # ========== 4. /chat 非流式 (需 API key) ==========
    section("4. /chat 端点")
    if not _has_llm_key():
        print("  ⏭  跳过: MINIMAX_API_KEY 未配置")
    else:
        try:
            from fastapi.testclient import TestClient
            with TestClient(app) as client:
                r = client.post(
                    "/api/v1/chat",
                    json={"session_id": "smoke", "message": "ping (回答一个字: ok)"},
                )
                results.append(check("POST /chat", r.status_code == 200, f"status={r.status_code}"))
                if r.status_code == 200:
                    body = r.json()
                    results.append(check("  含 content", bool(body.get("content"))))
                    results.append(check("  含 usage", "usage" in body))
        except Exception as e:  # noqa: BLE001
            results.append(check("POST /chat", False, str(e)))

    # ========== 5. /chat/stream SSE ==========
    section("5. /chat/stream SSE 端点")
    if not _has_llm_key():
        print("  ⏭  跳过: MINIMAX_API_KEY 未配置")
    else:
        try:
            from fastapi.testclient import TestClient
            with TestClient(app) as client:
                with client.stream(
                    "POST",
                    "/api/v1/chat/stream",
                    json={"session_id": "smoke", "message": "用 1 个词回答: hi"},
                ) as r:
                    results.append(check("SSE 流开始", r.status_code == 200, f"status={r.status_code}"))
                    buf = ""
                    got_token = False
                    got_done = False
                    for chunk in r.iter_text():
                        buf += chunk
                        if "event: token" in buf and not got_token:
                            got_token = True
                        if "event: done" in buf:
                            got_done = True
                            break
                        if len(buf) > 5000:
                            break
                    results.append(check("  收到 token 事件", got_token))
                    results.append(check("  收到 done 事件", got_done))
        except Exception as e:  # noqa: BLE001
            results.append(check("SSE 流", False, str(e)))

    # ========== 6. persist 模块 ==========
    section("6. persist 模块冷启动")
    try:
        from app.services.persist import persist_mode, persist_status
        mode = persist_mode()
        results.append(check("persist_mode 暴露", mode in {"disabled", "cold_restore", "fresh_start"}, f"mode={mode}"))
        status = persist_status()
        results.append(check("persist_status 暴露", "enabled" in status, f"enabled={status['enabled']}"))
    except Exception as e:  # noqa: BLE001
        results.append(check("persist 模块", False, str(e)))

    # ========== 7. LLM 工厂错误处理 ==========
    section("7. LLM 工厂")
    try:
        from app.llm.factory import get_llm
        if not settings.minimax_api_key.get_secret_value():
            try:
                get_llm()
                results.append(check("无 key 应报错", False, "竟然成功了?"))
            except Exception as e:  # noqa: BLE001
                results.append(check("无 key 正确报错", "llm_api_key_missing" in str(e) or "API_KEY" in str(e)))
        else:
            llm = get_llm()
            results.append(check("LLM 实例化", llm is not None, f"type={type(llm).__name__}"))
            results.append(check("  name 字段", hasattr(llm, "name") and llm.name == "minimax"))
    except Exception as e:  # noqa: BLE001
        results.append(check("LLM 工厂", False, str(e)))

    # ========== 总结 ==========
    section("总结")
    passed = sum(results)
    total = len(results)
    print(f"  通过: {passed}/{total}  ({passed / total * 100:.0f}%)")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
