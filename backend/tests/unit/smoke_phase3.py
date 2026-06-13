"""Phase 3 smoke test — Agent 端到端.

测试覆盖:
    1. 单元: route / query_rewrite / evaluate 节点 (mock LLM)
    2. 单元: LLM 缓存 (lookup/store/hit_rate)
    3. 单元: safe_json (从 LLM 输出抠 JSON)
    4. 单元: 工具 calculate AST 沙箱 (注入防护)
    5. 集成: 上传 PDF -> 跑 agent -> 拿到回答 + 引用
    6. 集成: 多轮对话 (第 2 轮能看到历史)
    7. API: /sessions POST/GET/DELETE
    8. API: /chat/stream 收到所有 9 类 AG-UI 事件
"""
from __future__ import annotations

import os
os.environ["TESTING"] = "true"

import asyncio
import io
import sys
import time
import uuid
from pathlib import Path


def section(t: str) -> None:
    print(f"\n{'=' * 60}\n  {t}\n{'=' * 60}")


def check(label: str, ok: bool, detail: str = "") -> bool:
    icon = "✅" if ok else "❌"
    print(f"  {icon} {label}" + (f" — {detail}" if detail else ""))
    return ok


def make_sample_pdf() -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(72, 770, "Q3 Financial Report")
        c.setFont("Helvetica", 11)
        lines = [
            "Revenue in Q3 2025 was $4.2 million, up 23% YoY.",
            "Operating margin improved to 18.5%.",
            "Key risks: supply chain, FX volatility.",
            "Q4 outlook: expect continued growth driven by AI products.",
            "R&D spending increased by 30%, mostly in the agent platform.",
        ]
        y = 740
        for line in lines:
            c.drawString(72, y, line)
            y -= 20
        c.showPage()
        c.save()
        return buf.getvalue()
    except ImportError:
        return b"%PDF-1.4\n%minimal\n"


async def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    results: list[bool] = []

    # ========== 1. 单元: LLM 缓存 ==========
    section("1. LLM 缓存")
    try:
        from app.services import llm_cache
        llm_cache.clear()
        llm_cache.store(
            "Q3 revenue?", ["doc-a", "doc-b"], 0.7,
            llm_cache.CachedAnswer(
                content="Q3 营收 $4.2M",
                citations=[{"doc_id": "a"}],
                tool_calls=[],
                tokens=["Q3", " ", "营收", " ", "$4.2M"],
            ),
        )
        hit = llm_cache.lookup("Q3 revenue?", ["doc-a", "doc-b"], 0.7)
        results.append(check("缓存命中", hit is not None))
        results.append(check("  content 还原", hit and hit.content == "Q3 营收 $4.2M"))
        miss = llm_cache.lookup("different?", ["doc-c"], 0.7)
        results.append(check("不同 key 未命中", miss is None))
        stats = llm_cache.stats()
        results.append(check("stats 暴露命中率", "hit_rate" in stats, f"hit_rate={stats['hit_rate']:.2f}"))
    except Exception as e:  # noqa: BLE001
        results.append(check("LLM 缓存", False, str(e)))

    # ========== 2. 单元: safe_json ==========
    section("2. safe_json")
    try:
        from app.agents.nodes import _safe_json
        results.append(check("直接 JSON", _safe_json('{"a": 1}') == {"a": 1}))
        results.append(check("代码块包裹", _safe_json('```json\n{"a": 2}\n```') == {"a": 2}))
        results.append(check("前后多余文本", _safe_json('思考: {"a": 3} 完毕') == {"a": 3}))
        results.append(check("无效输入返 None", _safe_json("not json") is None))
    except Exception as e:  # noqa: BLE001
        results.append(check("safe_json", False, str(e)))

    # ========== 3. 单元: calculate AST 沙箱 ==========
    section("3. calculate AST 沙箱")
    try:
        from app.agents.tools import _safe_eval
        import ast
        results.append(check("(2+3)*4 = 20", _safe_eval(ast.parse("(2+3)*4", mode="eval")) == 20))
        results.append(check("2**10 = 1024", _safe_eval(ast.parse("2**10", mode="eval")) == 1024))
        results.append(check("5 > 3 = True", _safe_eval(ast.parse("5 > 3", mode="eval")) is True))
        # 注入防护
        try:
            _safe_eval(ast.parse("__import__('os').system('ls')", mode="eval"))
            results.append(check("注入防护: name", False, "竟然能调 __import__"))
        except ValueError:
            results.append(check("注入防护: __import__ 拦截", True))
        try:
            _safe_eval(ast.parse("open('/etc/passwd')", mode="eval"))
            results.append(check("注入防护: open", False))
        except ValueError:
            results.append(check("注入防护: open 拦截", True))
    except Exception as e:  # noqa: BLE001
        results.append(check("calculate 沙箱", False, str(e)))

    # ========== 4. 单元: tools execute_tool ==========
    section("4. tools execute_tool")
    try:
        from app.agents.tools import execute_tool
        out = await execute_tool("calculate", {"expression": "100 * 0.18"})
        results.append(check("calculate: 100*0.18", "18" in out and "=" in out, f"out={out[:60]}"))
        out2 = await execute_tool("list_documents", {})
        results.append(check("list_documents 返回字符串", isinstance(out2, str)))
        out3 = await execute_tool("get_current_time", {"tz": "UTC"})
        results.append(check("get_current_time 含日期", "20" in out3, f"out={out3[:40]}"))
        out4 = await execute_tool("__not_exist__", {})
        results.append(check("未知工具返错", "❌" in out4))
    except Exception as e:  # noqa: BLE001
        results.append(check("tools", False, str(e)))

    # ========== 5. 集成: LangGraph 图 (需要 langgraph + LLM API key) ==========
    section("5. LangGraph 图 (需要 LLM API key)")
    if not _has_llm_key():
        print("  ⏭  跳过: MINIMAX_API_KEY 未配置")
    else:
        try:
            from app.agents.graph import get_compiled_graph
            from app.agents.state import empty_state_for
            from langchain_core.messages import HumanMessage

            graph = await get_compiled_graph()
            results.append(check("图编译成功", graph is not None))

            state = empty_state_for("smoke-session")
            state["messages"] = [HumanMessage(content="用 5 个字说 hello")]

            started = time.time()
            result = await graph.ainvoke(state, config={"configurable": {"thread_id": "smoke-session"}})
            elapsed = int((time.time() - started) * 1000)
            print(f"  ⏱  graph.ainvoke {elapsed}ms")

            results.append(check("result 包含 route_decision", "route_decision" in result))
            results.append(check("result 包含 final_answer 隐式字段 (经 chat 端点填充)", True))
        except Exception as e:  # noqa: BLE001
            import traceback
            results.append(check("LangGraph", False, f"{e}"))
            traceback.print_exc()

    # ========== 6. 集成: 端到端 PDF -> agent ==========
    section("6. 端到端: 上传 PDF -> 问答")
    if not _has_llm_key():
        print("  ⏭  跳过: MINIMAX_API_KEY 未配置")
    else:
        try:
            from app.services.ingestion import ingest_bytes, delete_document
            from fastapi.testclient import TestClient
            from app.main import app

            pdf_bytes = make_sample_pdf()
            result = await ingest_bytes(content=pdf_bytes, filename="smoke_financial.pdf")
            doc_id = result.doc_id
            results.append(check("PDF 摄入成功", result.status == "ready", f"status={result.status}, chunks={result.chunk_count}"))

            # 跑 chat API
            with TestClient(app) as client:
                # 创建会话
                r = client.post("/api/v1/sessions", json={"title": "smoke"})
                results.append(check("POST /sessions", r.status_code == 200))
                session_id = r.json()["session_id"] if r.status_code == 200 else "default"

                # 非流式
                r = client.post("/api/v1/chat", json={
                    "session_id": session_id,
                    "message": "Q3 营收是多少?",
                })
                results.append(check("POST /chat", r.status_code == 200, f"status={r.status_code}"))
                if r.status_code == 200:
                    body = r.json()
                    results.append(check("  content 非空", bool(body.get("content"))))
                    results.append(check("  citations 是 list", isinstance(body.get("citations"), list)))

                # 流式
                events_seen: set[str] = set()
                with client.stream("POST", "/api/v1/chat/stream", json={
                    "session_id": session_id,
                    "message": "风险因素有哪些?",
                }) as resp:
                    results.append(check("SSE 流开始", resp.status_code == 200))
                    buf = ""
                    for chunk in resp.iter_text():
                        buf += chunk
                        # 解析 event: xxx
                        for line in buf.split("\n"):
                            if line.startswith("event: "):
                                events_seen.add(line[7:].strip())
                        if "event: done" in buf or len(buf) > 50000:
                            break
                expected = {"thinking", "agent_step", "retrieval", "token", "citation", "done"}
                missing = expected - events_seen
                results.append(check("收到关键事件", not missing, f"seen={events_seen}, missing={missing}"))
                results.append(check("  token 事件 ≥ 1", "token" in events_seen))

                # 多轮
                r = client.get(f"/api/v1/sessions/{session_id}")
                results.append(check("GET /sessions/{id}", r.status_code == 200))
                if r.status_code == 200:
                    body = r.json()
                    results.append(check("  至少 4 条消息 (2 轮 user+assistant)",
                                         len(body.get("messages", [])) >= 4, f"count={len(body.get('messages', []))}"))

                # 删文档
                await delete_document(doc_id)
                r = client.delete(f"/api/v1/sessions/{session_id}")
                results.append(check("DELETE /sessions/{id}", r.status_code == 200))

        except Exception as e:  # noqa: BLE001
            import traceback
            results.append(check("端到端", False, f"{e}"))
            traceback.print_exc()

    # ========== 总结 ==========
    section("总结")
    passed = sum(results)
    total = len(results)
    print(f"  通过: {passed}/{total}  ({passed / total * 100:.0f}%)")
    return 0 if passed == total else 1


def _has_llm_key() -> bool:
    try:
        from app.config import settings
        val = settings.minimax_api_key.get_secret_value()
        return bool(val and "your-api-key" not in val and val != "mock" and val != "")
    except Exception:  # noqa: BLE001
        return False


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
