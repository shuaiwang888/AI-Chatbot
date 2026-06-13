"""Pydantic AI 工具集 (供 LangGraph tool_executor 节点调用).

工具列表:
- summarize_document: 总结指定文档
- compare_documents: 对比 2 个文档的某方面
- calculate: 安全数学计算 (用 AST 而不是 eval)
- list_documents: 列出已上传的文档
- get_current_time: 当前时间 (调试用)
"""
from __future__ import annotations

import ast
import datetime as _dt
import logging
import operator
from typing import Any

from pydantic import BaseModel, Field

from app.models import db
from app.services.embedding import get_embedder
from app.services.vector_store import hybrid_query

logger = logging.getLogger(__name__)


# ========== Tool schemas (OpenAI function calling 格式) ==========
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "summarize_document",
            "description": "根据 doc_id 总结指定文档的主要内容 (取前若干 chunks 拼接 + LLM 摘要).",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {
                        "type": "string",
                        "description": "要总结的文档 ID",
                    },
                    "max_chunks": {
                        "type": "integer",
                        "description": "最多取前多少个 chunk (默认 30)",
                        "default": 30,
                    },
                },
                "required": ["doc_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_documents",
            "description": "对比两个文档在某方面的异同. 返回结构化对比结果.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id_a": {"type": "string"},
                    "doc_id_b": {"type": "string"},
                    "aspect": {
                        "type": "string",
                        "description": "对比的方面, 如 '技术选型', '营收', '风险' 等",
                    },
                },
                "required": ["doc_id_a", "doc_id_b", "aspect"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "安全地计算数学表达式 (加减乘除/括号/比较), 用 AST 解析避免注入.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "数学表达式, 如 '(2+3)*4'",
                    },
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_documents",
            "description": "列出已上传的所有文档 (ID + 文件名 + 状态).",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "获取服务器当前时间 (UTC / 本地时区).",
            "parameters": {
                "type": "object",
                "properties": {
                    "tz": {
                        "type": "string",
                        "description": "时区, 如 'UTC', 'Asia/Shanghai'. 默认 UTC",
                        "default": "UTC",
                    },
                },
            },
        },
    },
]


# ========== 工具实现 ==========
async def tool_summarize_document(args: dict[str, Any]) -> str:
    doc_id = args.get("doc_id")
    if not doc_id:
        return "❌ 缺少 doc_id"
    doc = db.doc_get(doc_id)
    if doc is None:
        return f"❌ 文档 {doc_id} 不存在"

    chunks = db.chunk_get_by_doc(doc_id, limit=int(args.get("max_chunks", 30)))
    if not chunks:
        return f"❌ 文档 {doc_id} 暂无内容"

    text = "\n\n".join(c["text"] for c in chunks)
    # 简单截断前 6000 字给 LLM 摘要
    snippet = text[:6000]

    from app.llm.factory import get_llm
    llm = get_llm()
    resp = await llm.chat(
        messages=[
            {"role": "system", "content": "你是文档摘要助手. 用中文输出简洁摘要, 列出主要章节和关键事实."},
            {"role": "user", "content": f"请摘要以下内容 (来自 {doc.get('filename', doc_id)}):\n\n{snippet}"},
        ],
        temperature=0.3,
        max_tokens=600,
    )
    return resp.content or "(空)"


async def tool_compare_documents(args: dict[str, Any]) -> str:
    doc_a_id = args.get("doc_id_a")
    doc_b_id = args.get("doc_id_b")
    aspect = args.get("aspect", "整体")
    if not (doc_a_id and doc_b_id):
        return "❌ 缺少 doc_id_a 或 doc_id_b"

    chunks_a = db.chunk_get_by_doc(doc_a_id, limit=20)
    chunks_b = db.chunk_get_by_doc(doc_b_id, limit=20)
    if not chunks_a or not chunks_b:
        return f"❌ 文档 {doc_a_id if not chunks_a else doc_b_id} 无内容"

    text_a = "\n".join(c["text"] for c in chunks_a)[:3000]
    text_b = "\n".join(c["text"] for c in chunks_b)[:3000]

    from app.llm.factory import get_llm
    llm = get_llm()
    resp = await llm.chat(
        messages=[
            {"role": "system", "content": "你是文档对比助手. 输出 Markdown 表格, 列出差異与相同点."},
            {"role": "user", "content": (
                f"对比以下两份文档的「{aspect}」方面.\n\n"
                f"## 文档 A\n{text_a}\n\n## 文档 B\n{text_b}\n\n"
                f"输出: 1) 关键差异 (表格) 2) 相同点 3) 建议"
            )},
        ],
        temperature=0.3,
        max_tokens=800,
    )
    return resp.content or "(空)"


_BIN_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_CMP_OPS = {
    ast.Eq: operator.eq, ast.NotEq: operator.ne,
    ast.Lt: operator.lt, ast.LtE: operator.le,
    ast.Gt: operator.gt, ast.GtE: operator.ge,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _safe_eval(node: ast.AST) -> float | bool:
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"不支持的字面量: {node.value!r}")
    if isinstance(node, ast.BinOp):
        op = _BIN_OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"不支持的二元运算: {type(node.op).__name__}")
        return op(_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp):
        op = _UNARY_OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"不支持的一元运算: {type(node.op).__name__}")
        return op(_safe_eval(node.operand))
    if isinstance(node, ast.Compare):
        left = _safe_eval(node.left)
        for cmp_op, right_node in zip(node.ops, node.comparators):
            op = _CMP_OPS.get(type(cmp_op))
            if op is None:
                raise ValueError(f"不支持的比较: {type(cmp_op).__name__}")
            left = op(left, _safe_eval(right_node))
            if not left:
                return False
        return True
    raise ValueError(f"不支持的语法: {ast.dump(node)}")


async def tool_calculate(args: dict[str, Any]) -> str:
    expr = args.get("expression", "")
    if not expr:
        return "❌ 缺少 expression"
    try:
        tree = ast.parse(expr, mode="eval")
        result = _safe_eval(tree)
        return f"{expr} = {result}"
    except Exception as e:  # noqa: BLE001
        return f"❌ 计算失败: {e}"


async def tool_list_documents(args: dict[str, Any]) -> str:
    docs = db.doc_list(limit=200)
    if not docs:
        return "暂无已上传文档"
    lines = [f"- {d['id'][:8]}…  {d['filename']}  (chunks={d.get('chunk_count', 0)}, status={d.get('status', '?')})" for d in docs]
    return "已上传文档:\n" + "\n".join(lines)


async def tool_get_current_time(args: dict[str, Any]) -> str:
    tz = args.get("tz", "UTC")
    try:
        from zoneinfo import ZoneInfo
        now = _dt.datetime.now(ZoneInfo(tz))
    except Exception:  # noqa: BLE001
        now = _dt.datetime.utcnow()
    return now.strftime("%Y-%m-%d %H:%M:%S %Z")


# ========== 工具路由表 ==========
TOOL_FUNCS = {
    "summarize_document": tool_summarize_document,
    "compare_documents": tool_compare_documents,
    "calculate": tool_calculate,
    "list_documents": tool_list_documents,
    "get_current_time": tool_get_current_time,
}


async def execute_tool(name: str, args: dict[str, Any]) -> str:
    """统一工具执行入口."""
    fn = TOOL_FUNCS.get(name)
    if fn is None:
        return f"❌ 未知工具: {name}"
    try:
        return await fn(args)
    except Exception as e:  # noqa: BLE001
        logger.exception("Tool %s failed", name)
        return f"❌ 工具执行失败: {e}"


__all__ = ["TOOL_SCHEMAS", "TOOL_FUNCS", "execute_tool"]
