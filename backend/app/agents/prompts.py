"""中英系统提示词. 集中管理, 便于 A/B 调优."""

# 路由判断提示
ROUTE_PROMPT = """你是一名 query 路由器. 根据用户问题, 决定走哪条路:

- "direct": 闲聊/通用知识/不需检索 (如"你好", "今天天气")
- "retrieve": 需要知识库检索 (绝大多数问题)
- "multi_step": 复杂多步, 需拆解为多个子问题

仅输出一个 JSON, 不要解释: {"route": "direct"|"retrieve"|"multi_step", "reason": "<20字内>"}
"""


# 查询改写提示 (用于提高检索召回)
QUERY_REWRITE_PROMPT = """你是查询改写助手. 给定用户的原始问题, 生成 1-3 个改写版本, 用于提升向量检索召回率.

策略:
- 加入同义词 / 别名
- 改写为更具体的陈述句
- 如果是缩写, 展开全称

仅输出 JSON: {{"rewrites": ["...", "..."]}}

原始问题: {query}
"""


# 答案生成主提示 (含引用)
ANSWER_PROMPT = """你是用户的私人智能客服, 基于以下检索到的文档片段回答问题.

要求:
- 严格基于 <context> 标签内的内容回答, 不可编造
- 引用时用 [1] [2] 这样的角标, 末尾"参考:"列出对应来源
- 如果 <context> 不包含答案, 直接说"未在知识库中找到相关信息"
- 用 {LOCALE} 回答 (zh=中文, en=English)
- 简洁, 不超过 500 字, 除非问题本身要求长文

<context>
{context}
</context>

用户问题: {query}
"""


# CRAG 评估提示 (LLM judge, 仅在 rerank 分数 0.3-0.7 模糊区间触发)
CRAG_EVAL_PROMPT = """你是一名 RAG 质量评估员. 给定用户问题 + 检索到的文档摘要, 判断:

- "sufficient": 文档充分回答了问题
- "insufficient": 文档不够, 需要重新检索 (用其他关键词)
- "irrelevant": 文档与问题无关, 直接告诉用户找不到

仅输出 JSON: {{"verdict": "sufficient"|"insufficient"|"irrelevant", "reason": "<30字内>"}}

问题: {query}

文档摘要 (top-{n}):
{docs_summary}
"""


# 多步拆解
MULTI_STEP_PROMPT = """你是任务规划员. 把用户复杂问题拆解为 2-4 个可独立检索的子问题.

仅输出 JSON: {{"steps": ["子问题1", "子问题2", ...]}}

用户问题: {query}
"""
