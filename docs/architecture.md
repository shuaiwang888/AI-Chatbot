# 架构总览

## 数据流

### 文档摄入路径
```
用户上传 PDF
   │
   ▼
[FastAPI] /documents/upload
   │
   ├─ 1. SHA256 哈希 (幂等)
   │
   ├─ 2. Docling 解析 (结构感知 + 跨页表 + OCR)
   │      ↓ markdown + pages
   │
   ├─ 3. 层次化分块 (parent 2000t / child 512t, 标题/段落边界)
   │
   ├─ 4. Anthropic-style 上下文预置 (LLM 给每 chunk 加 1-2 句描述)
   │
   ├─ 5. BGE-M3 三路编码 (dense 1024d + sparse + colbert 多向量)
   │
   ├─ 6. 入库
   │      ├─ ChromaDB: dense + (colbert) multi-vector
   │      ├─ 旁路 SQLite: sparse lexical weights
   │      └─ SQLite: document + chunk 元数据
   │
   └─ 7. 调度 HF Dataset 同步 (后台)
```

### 问答路径
```
用户问: "Q3 营收是多少?"
   │
   ▼
[FastAPI] /chat/stream (SSE)
   │
   ├─ 1. LangGraph 检索循环
   │    ├─ route: LLM 决定 direct/retrieve/multi_step
   │    ├─ query_rewrite: 改写 (HyDE / 多查询 / 多步拆解)
   │    ├─ retrieve: 三路混合 (dense + sparse + colbert) → RRF 融合 → top-20
   │    ├─ rerank: BGE-reranker-v2-m3 → top-5
   │    └─ evaluate (CRAG): 读 top-1 score
   │       ├─ ≥ 0.7 → done
   │       ├─ < 0.3 → done (无相关)
   │       └─ 0.3-0.7 → LLM judge → 可能重写 + 再检索 (≤2 轮)
   │
   ├─ 2. Answer 流式生成 (直接调 LLM, 不走 graph)
   │    ├─ 拼 context (citations)
   │    ├─ 查 LLM 缓存 (LRU 200)
   │    ├─ 命中 → 回放 tokens
   │    └─ 未命中 → 流式 + 缓存
   │
   └─ 3. 推送 SSE 事件 (9 类 AG-UI)
        ├─ thinking / agent_step / retrieval / tool_call
        ├─ token (多次, 流式)
        ├─ citation (5 个, 含 page+snippet+score)
        ├─ progress / done / error
```

## 模块依赖

```
Frontend (React 19)
  └─ fetch / SSE → Backend

Backend (FastAPI)
  ├─ api/  (HTTP routes)
  │   ├─ chat (agent + SSE)
  │   ├─ documents (upload / list / delete)
  │   ├─ sessions (CRUD + checkpoint)
  │   └─ health
  │
  ├─ agents/ (LangGraph)
  │   ├─ state: AgentState
  │   ├─ nodes: route / rewrite / retrieve / rerank / answer / evaluate / tool
  │   ├─ graph: StateGraph 装配 + AsyncSqliteSaver
  │   ├─ tools: 5 个 Pydantic AI 工具
  │   └─ prompts: 中英 system prompts
  │
  ├─ services/  (业务编排)
  │   ├─ ingestion: 文档摄入流水线
  │   ├─ chunking: 层次化分块
  │   ├─ embedding: BGE-M3 编码
  │   ├─ vector_store: ChromaDB + RRF + 旁路 sparse
  │   ├─ reranker: BGE-reranker-v2-m3
  │   ├─ llm_cache: LRU 200
  │   └─ persist: HF Dataset 同步
  │
  ├─ parsers/  (文档解析)
  │   ├─ docling: 主力 (结构 + OCR + 跨页表)
  │   ├─ marker: 兜底
  │   └─ (mineru / vlm: 远期可选)
  │
  ├─ llm/  (LLM 抽象)
  │   ├─ base: AbstractLLM
  │   ├─ minimax: OpenAI 兼容客户端
  │   └─ factory: provider 切换
  │
  ├─ models/  (Pydantic + SQLite)
  │   ├─ schemas: API IO models
  │   └─ db: SQLite CRUD
  │
  ├─ streaming/  (SSE)
  │   ├─ events: AG-UI 9 类事件常量
  │   └─ sse: 格式化 helper
  │
  └─ core/  (横切)
      ├─ paths: 持久盘路径
      ├─ logging: JSON 结构化
      └─ errors: 异常体系
```

## 关键设计决策

| 决策 | 原因 |
|---|---|
| **HuggingFace Spaces 而非 Render** | 免费版 Render 仅 512MB RAM + 30s 冷启动 + 无持久磁盘; HF 给 16GB + 50GB + 零冷启动 |
| **HF Dataset 持久化** | HF Spaces 临时磁盘重启即丢, Dataset 是唯一免费持久化 |
| **Chromadb + 旁路 sparse** | ChromaDB v1.0 multi-vector 存 dense + colbert, sparse 因量大走旁路 SQLite |
| **RRF 融合** | 三路 (dense/sparse/colbert) 简单融合, 不调权重, 行业标配 |
| **层次化分块 (parent/child)** | child 用于精确检索, parent 用于提供 LLM 上下文, 召回率↑ |
| **Anthropic 上下文预置** | 每 chunk 加 LLM 生成的 1-2 句描述, 召回率实测↑35% |
| **CRAG 二阶段评估** | 阶段 1 读 rerank score 省 LLM judge; 阶段 2 仅在模糊区间触发 |
| **LangGraph async SQLite** | 持久 checkpoint + 与摄入共享 SQLite, 减少组件数 |
| **AG-UI 9 类事件** | 标准化 agent UI 事件, 调试体验与生产可观测性双赢 |
| **LLM 缓存 (LRU 200)** | 个人项目, 同一问题反复问常见, 省 API 费 |
| **AST 沙箱 (calculate 工具)** | 防 prompt injection, 不让 LLM 调危险函数 |
| **SHA256 幂等** | 重传不重复摄入 |
| **多模态解析路由** | Docling 主 + Marker 兜底, 失败自动降级 |

## 性能 / 成本预算

| 指标 | 数值 | 备注 |
|---|---|---|
| 文档摄入 (50 页 PDF) | 1-3 分钟 | Docling 30s + BGE-M3 1-2 分钟 |
| 检索延迟 (无 LLM judge) | < 500ms | dense HNSW + rerank |
| 检索延迟 (有 LLM judge) | 1-3s | 多一次 LLM 调用 |
| Token 流式 | 实时 | 与 LLM provider 速率一致 |
| LLM 月费 (个人) | $0.5-2 | 1000 次/月, MiniMax V3 |
| HF Space 资源 | 16GB RAM, 50GB 磁盘 | 免费 |
| GH Pages 流量 | 100GB/月 | 免费 |
| ChromaDB 容量 | 100K-1M chunks | 取决于 RAM |
| LRU 缓存命中 | ~20% | 节省 token |
