# 私人 Agent 智能客服 — 实施方案

## Context

需要从零打造一个**以 Agent 模式工作的私人智能客服**：用户上传多模态文档（PDF / Word / 图片，含跨页文字、表格、公式、扫描件等），系统通过 RAG + 工具调用 + 多轮对话，**高准确度、带引用源**地回答问题。

**关键决策（已与用户确认）**

| 维度 | 决策 | 原因 |
|---|---|---|
| LLM | **MiniMax-M3（默认），可配置切换** | 用户要求初始为 MiniMax；通过 OpenAI 兼容协议接入，未来可无缝切到 Claude / GPT / Qwen |
| 后端部署 | **HuggingFace Spaces（Docker）** 而非 Render | 免费版 Render 有 512MB RAM + 30-60s 冷启动 + 无持久磁盘。HF Spaces 给 16GB RAM + 50GB 临时磁盘 + 2 vCPU，零成本。**注意：免费版磁盘非持久化**，需外部持久化策略（见下方持久化章节） |
| 前端部署 | **GitHub Pages** | 静态站点 + HashRouter 兼容 |
| 文档 | PDF + Word(DOCX) + 图片（PNG/JPG），**中英双语** | 需 OCR + 多语言 embedding |
| 功能 | 多轮对话 + 引用源 + 工具调用 | LangGraph 工具节点 + LangChain citation 模式 |
| 使用规模 | **纯个人使用**（单用户） | 无需多租户 / 鉴权 |

**目标产出**：一个可部署的、agentic 的、端到端的私人 AI 客服系统，整体成本 ≈ $1/月（仅 LLM 推理费）。

---

## 架构总览

```
┌──────────────────────────────────────────────────────────────┐
│  React 19.2 + Vite 8 + TypeScript + shadcn/ui (CLI v4)      │
│  (GitHub Pages 静态部署，HashRouter)                         │
│  ─ SSE 消费者 ─ TanStack Query ─ Zustand ─                   │
└────────────────────────┬─────────────────────────────────────┘
                         │ HTTPS / SSE
                         ▼
┌──────────────────────────────────────────────────────────────┐
│  FastAPI on HuggingFace Spaces (Docker, port 7860)           │
│  ─ CORS ─ Lifespan warm-up ─ Routers ─                       │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ LangGraph v1.2 Agent (StateGraph + SQLite Checkpoint) │  │
│  │   route → rewrite → retrieve → rerank → answer        │  │
│  │   → CRAG evaluate → (loop / done)                     │  │
│  │   astream_events v2 → SSE                             │  │
│  └────────────────────────────────────────────────────────┘  │
│  ┌──────────────┐ ┌──────────────┐ ┌─────────────────────┐  │
│  │ Docling 解析 │ │ ChromaDB     │ │ BGE-M3 + Reranker   │  │
│  │ + Marker 兜底 │ │ v1.0 (Rust)  │ │ FlagEmbedding       │  │
│  └──────────────┘ └──────────────┘ └─────────────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ LLM 抽象层 (AbstractLLM) → MiniMax-M3 (默认, 可切换) │  │
│  └────────────────────────────────────────────────────────┘  │
│  临时磁盘 /data + HF Dataset repo 持久化同步                  │
└──────────────────────────────────────────────────────────────┘
```

---

## 项目结构（Monorepo）

```
ai-chatbot/
├── README.md
├── .env.example
├── .gitignore
├── docs/
│   ├── architecture.md
│   └── deployment.md
│
├── backend/                        # HF Space 根目录
│   ├── Dockerfile
│   ├── README.md                   # HF 元数据头
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py                 # FastAPI 入口 (port 7860)
│   │   ├── config.py               # Pydantic Settings
│   │   ├── deps.py                 # 单例依赖（LLM / embedder / chroma）
│   │   ├── api/
│   │   │   ├── documents.py        # 上传 / 列表 / 删除
│   │   │   ├── chat.py             # /chat + /chat/stream (SSE)
│   │   │   ├── sessions.py         # 会话历史
│   │   │   └── health.py           # /healthz + /readyz
│   │   ├── services/
│   │   │   ├── ingestion.py        # 上传→解析→分块→向量化→入库
│   │   │   ├── chunking.py         # 结构感知 + 语义分块 + 上下文预置
│   │   │   ├── embedding.py        # BGE-M3 封装
│   │   │   ├── vector_store.py     # ChromaDB 适配
│   │   │   ├── reranker.py         # BGE-reranker-v2-m3 / Qwen3-Reranker
│   │   │   ├── document_store.py   # SQLite 元数据
│   │   │   ├── persist.py          # HF Dataset repo 持久化同步
│   │   │   └── parsers/
│   │   │       ├── base_parser.py       # 解析器抽象基类
│   │   │       ├── docling_parser.py    # 主力：结构感知 + 跨页表 + OCR
│   │   │       ├── marker_parser.py     # 兜底：文字密集型 PDF
│   │   │       ├── mineru_parser.py     # 可选：学术/复杂双栏布局
│   │   │       └── vlm_parser.py        # 远期：多模态 LLM 直接理解图表
│   │   ├── agents/
│   │   │   ├── state.py            # AgentState
│   │   │   ├── graph.py            # StateGraph 装配
│   │   │   ├── nodes.py            # route / query_rewrite / retrieve / rerank / answer / evaluate
│   │   │   ├── tools.py            # Pydantic AI 工具
│   │   │   └── prompts.py          # 中英系统提示
│   │   ├── llm/
│   │   │   ├── base.py             # AbstractLLM
│   │   │   ├── minimax.py          # MiniMax-M3 (OpenAI 兼容)
│   │   │   └── factory.py          # 工厂选择
│   │   ├── models/
│   │   │   ├── schemas.py          # Pydantic IO 模型
│   │   │   └── db.py               # SQLModel 表
│   │   ├── streaming/
│   │   │   ├── sse.py              # SSE 格式化
│   │   │   └── events.py           # 事件类型
│   │   └── core/
│   │       ├── logging.py
│   │       ├── paths.py
│   │       └── errors.py
│   └── tests/
│       ├── unit/                    # 单元测试
│       └── eval/                    # RAG 质量评估
│           ├── test_ragas.py        # RAGAS 离线评估
│           └── test_quality_gate.py # DeepEval CI/CD 质量门禁
│
├── frontend/                       # React 19 + Vite 8
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── components.json
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── router.tsx              # HashRouter
│   │   ├── env.ts
│   │   ├── components/
│   │   │   ├── ui/                 # shadcn/ui 原语
│   │   │   ├── chat/               # ChatArea / MessageList / CitationPanel / AgentStepTrace
│   │   │   ├── documents/          # DocumentList / UploadPanel
│   │   │   └── layout/             # Sidebar / TopBar
│   │   ├── hooks/
│   │   │   ├── useChatStream.ts    # SSE 消费
│   │   │   └── useDocuments.ts
│   │   ├── stores/                 # Zustand
│   │   ├── lib/                    # api / sse / utils
│   │   └── styles/globals.css
│
└── .github/workflows/
    ├── deploy-frontend.yml         # 构建并部署到 GitHub Pages
    └── test-backend.yml            # 后端 lint + pytest + DeepEval 质量门禁
```

---

## 后端设计要点

### 1. FastAPI 入口 [backend/app/main.py](backend/app/main.py)

- 监听 `0.0.0.0:7860`（HF Spaces 约定端口）
- CORS 白名单 = `settings.allowed_origins`（含 GH Pages 域 + 本地 dev）
- `lifespan` 在启动时预热单例：LLM client / BGE-M3 / reranker / Chroma client
- `lifespan` 启动时从 HF Dataset repo 恢复持久化数据，关闭时同步回推
- 挂载 `/api/v1/{health,documents,chat,sessions}`

### 2. 配置 [backend/app/config.py](backend/app/config.py)

`pydantic-settings` 读取环境变量，关键字段：

```python
llm_provider: str = "minimax"            # 切换: "openai" / "anthropic" / "qwen"
minimax_api_key: SecretStr
minimax_base_url: str = "https://api.MiniMax.com/v1"
minimax_model: str = "MiniMax-M3"
embedding_model: str = "BAAI/bge-m3"
reranker_model: str = "BAAI/bge-reranker-v2-m3"  # 可选 "Qwen/Qwen3-Reranker-0.6B"
data_dir: Path = Path("/data")
allowed_origins: list[str] = ["http://localhost:5173"]
chunk_size: int = 512
chunk_overlap: int = 64
semantic_chunking: bool = True           # 启用语义分块
contextual_retrieval: bool = True        # 启用 Anthropic-style 上下文预置（需消耗少量 LLM token）
retrieval_k: int = 20
rerank_top_n: int = 5
crag_max_iterations: int = 2             # CRAG 最大循环次数
crag_relevance_threshold: float = 0.7    # CRAG 相关性阈值
langsmith_tracing: bool = False          # LangSmith 追踪开关（开发环境启用）
hf_persist_repo: str = ""               # HF Dataset repo ID 用于持久化同步
```

### 3. LLM 抽象 [backend/app/llm/](backend/app/llm/)

`AbstractLLM` 接口：
- `async stream_chat(messages, tools=None) -> AsyncIterator[Chunk]`
- `async chat(messages, tools=None) -> Message`

`minimax.py` 用 `openai.AsyncOpenAI(base_url=settings.minimax_base_url)` 直接调 MiniMax-M3（OpenAI 兼容）。**未来切 Claude / GPT 仅需新增一个 provider 文件 + factory 一行分支。**

### 4. 文档摄入管道 [backend/app/services/ingestion.py](backend/app/services/ingestion.py)

```
upload → 保存到 /data/uploads/{uuid}/{filename}
     → 智能路由解析：
       1. Docling（默认，结构感知 + 跨页表 + OCR）
       2. 降级 Marker（Docling 失败时）
       3. MinerU（可选，学术论文/复杂双栏布局）
       4. VLM 解析（远期，图表/流程图等视觉内容 → 调用多模态 LLM 生成描述）
     → 结构感知分块 + 语义断句
       (parent 1500-2000t / child 400-512t, 按标题/段落/语义边界)
     → Anthropic-style 上下文预置：LLM 为每个 chunk 生成简短上下文摘要前缀
     → BGE-M3 编码 ("上下文+chunk" 拼接后送入, dense + sparse + colbert)
     → **SHA256 幂等性检查**：上传前计算文件 hash，SQLite 已有同 hash 文档则直接返回 doc_id（避免重复摄入）
     → 写入 ChromaDB + 元数据入 SQLite
     → 返回 doc_id + chunk_count
```

`docling_parser.py` 关键配置：`do_ocr=True, do_table_structure=True, images_scale=2.0`（PaddleOCR 内置支持中英）。失败时降级到 `marker`。

### 5. 向量存储 [backend/app/services/vector_store.py](backend/app/services/vector_store.py)

`chromadb.PersistentClient(path="/data/chroma")` (v1.0, Rust core)：
- 单一 collection `docs`，`embedding_function=None`（我们自己 embed）
- **三路混合检索**：BGE-M3 原生 dense + sparse + ColBERT → RRF 三路融合
  - 无需额外 `rank_bm25` 库，BGE-M3 一次编码同时产出三种向量
  - **dense + ColBERT** 存 ChromaDB v1.0 multi-vector collection（ChromaDB v1.0 原生支持多向量集合）
  - **sparse（lexical weights）** 存旁路 SQLite 表，检索时反序列化后做 SPLADE-style 稀疏打分
  - 三路结果 RRF（Reciprocal Rank Fusion）融合 → top-K
- 个人规模 10K-100K chunks 完全够用
- **未来可降级**：若 BGE-M3 ColBERT 在 16GB RAM 下 OOM，提供 `enable_colbert=False` 配置项，仅用 dense + sparse 两路

### 6. 持久化策略 [backend/app/services/persist.py](backend/app/services/persist.py)

由于 HF Spaces 免费版磁盘是**临时的**（容器重启后数据丢失），需要外部持久化机制：

| 数据类型 | 持久化方案 | 说明 |
|---------|-----------|------|
| 向量数据 (ChromaDB) | HF Dataset repo (Git LFS) | 启动时 `snapshot_download`，定期 `upload_folder` |
| SQLite checkpoint + 元数据 | HF Dataset repo | 同上，与 ChromaDB 一起同步 |
| 上传文件 | HF Dataset repo | 一并持久化，避免重传 |
| 模型权重 | Dockerfile 预下载（镜像层缓存） | 已有，不受重启影响 |

**冷启动处理**（首次部署时 `hf_persist_repo` 还不存在）：
```python
# app/services/persist.py
async def restore_from_hf():
    if not settings.hf_persist_repo:
        return  # 未配置则跳过持久化
    try:
        snapshot_download(
            repo_id=settings.hf_persist_repo,
            repo_type="dataset",
            local_dir=str(settings.data_dir),
        )
    except RepositoryNotFoundError:
        # 首次部署：repo 不存在是正常情况
        logger.info("First deploy: persist repo not found, starting fresh")
        # 写入时再 create_repo
    except Exception as e:
        logger.error(f"Persist restore failed: {e}")
        # 不阻塞启动，提示用户在 /readyz 看到降级状态
```

**写入端**：`huggingface_hub.create_repo(repo_type="dataset", exist_ok=True)` + `upload_folder(...)`，在每个写操作后异步触发（不阻塞用户请求）。

**替代方案**：升级 HF Pro ($9/月) 获取持久化存储，可彻底避免此问题。

### 7. LangGraph Agent [backend/app/agents/](backend/app/agents/)

**State**：
```python
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    session_id: str
    query_rewritten: str              # 改写后的查询
    route_decision: str               # "direct" | "single_retrieve" | "multi_step"
    retrieved: list[Document]
    reranked: list[Document]
    citations: list[dict]              # {doc_id, page, snippet, score}
    plan: list[str]
    iteration: int
    max_iterations: int               # CRAG 最大循环次数（默认 2）
    relevance_score: float            # CRAG 相关性评分
```

**节点**：
1. `route` — **Adaptive RAG 路由**：分析查询复杂度，决定走向
   - 直接回答（闲聊/通用知识）→ 跳过检索直达 answer
   - 单次检索 → query_rewrite → retrieve
   - 多步检索 → 拆分子问题 → 多次 retrieve + 合并
2. `query_rewrite` — **查询改写**：HyDE / 多查询扩展 / step-back prompting，提高召回率
3. `retrieve` — 三路混合检索 top-20（BGE-M3 dense + sparse + ColBERT → RRF）
4. `rerank` — BGE-reranker-v2-m3 选 top-5（可选升级 Qwen3-Reranker-0.6B）
5. `tool_executor` — Pydantic AI 工具（doc_summary / compare_docs / calc）
6. `answer` — 流式生成 + 注入内联引用 [1][2]（结构化 citation JSON 并行输出）
7. `evaluate` — **CRAG 评估**：两阶段判断，避免循环依赖
   - **阶段 1（必走，快）**：直接读 reranker 输出的 top-1 score
     - score ≥ `crag_relevance_threshold` (0.7) → 高置信，跳 LLM judge
     - score < 0.3 → 全部不相关，直接告知用户未找到相关信息并结束
     - 0.3 ≤ score < 0.7 → 进入阶段 2
   - **阶段 2（仅在模糊区间触发）**：用 LLM judge 判断检索质量 + 答案忠实度
     - 高置信 → done
     - 低置信 → query_rewrite 重新检索（最多 `crag_max_iterations` 轮，默认 2）
   - 这样大多数查询不需要走 LLM judge，省时省钱

**Checkpoint**：`AsyncSqliteSaver`（`langgraph-checkpoint-sqlite`）写到 `/data/sqlite/langgraph.db`，实现多轮会话持久化。⚠️ 实施前需到 [GitHub Advisory](https://github.com/advisories) + PyPI 核对当前最新稳定版本与已知漏洞。

### 8. 流式输出 [backend/app/api/chat.py](backend/app/api/chat.py)

`POST /api/v1/chat/stream` 返回 `text/event-stream`
（基于 LangGraph `astream_events` v2 → `asyncio.Queue` → FastAPI `StreamingResponse`）：

**AG-UI 兼容事件 schema**（`app/streaming/events.py` 中用 Pydantic 定义 + 常量导出）：

| event 名 | payload 字段 | 触发节点 | 说明 |
|---|---|---|---|
| `thinking` | `{content: str}` | route, query_rewrite | Agent 推理过程 / 决策说明 |
| `agent_step` | `{node: str, status: "running"\|"done"\|"error"}` | 所有节点 | 节点生命周期 |
| `retrieval` | `{doc_ids: list[str], scores: list[float]}` | retrieve | 命中文档 ID + 分数 |
| `tool_call` | `{name: str, args: dict, result_summary: str}` | tool_executor | 工具调用详情 |
| `token` | `{content: str}` | answer | LLM delta token |
| `citation` | `{doc_id, page, snippet, score}` | answer | 引用片段 |
| `progress` | `{pct: int, label: str}` | 全局 | 整体进度 0-100 |
| `done` | `{message_id, usage, total_ms}` | END | 结束 |
| `error` | `{code, message, retryable: bool}` | 任意 | 错误 |

**实现**：使用 LangGraph `astream_events(version="v2")` 获取细粒度事件 → 业务侧映射为 AG-UI 事件 → `asyncio.Queue` 桥接到 FastAPI `StreamingResponse`，格式化为标准 SSE 双行格式 (`event: xxx\ndata: {...}\n\n`)。

**LLM 响应缓存**（`app/services/llm_cache.py`，中优改进）：
- 内存级 LRU 缓存：key = `sha256(query + top_docs_ids)`，value = 完整回答
- 命中时跳过 LLM 调用直接流式回放（节省 API 费用）
- 默认关闭，可通过 `LLM_CACHE_ENABLED=true` 启用
- 用 `cachetools.LRUCache(maxsize=200)` 实现

---

## 前端设计要点

### 1. 栈
- **React 19.2** + **Vite 8**（Rolldown 构建器）+ TypeScript strict
- **Tailwind v4** + **shadcn/ui CLI v4**（Radix 原语 + GitHub Registry 支持）
- **Zustand**（聊天/UI 状态）+ **TanStack Query v5**（文档/会话列表）
- **HashRouter**（react-router-dom v7）兼容 GH Pages
- **react-virtuoso** 虚拟化长消息列表

### 2. 组件树
```
App
├── Sidebar
│   ├── DocumentList (含状态 chip)
│   └── UploadPanel (拖拽多文件)
└── ChatArea
    ├── MessageList
    │   ├── MessageBubble
    │   ├── CitationPanel (可折叠右栏，doc_id + 页码 + 片段)
    │   └── AgentStepTrace (调试视图，节点进度)
    └── ChatInput (含 Stop 按钮)
```

### 3. SSE 消费 [frontend/src/hooks/useChatStream.ts](frontend/src/hooks/useChatStream.ts)

`fetch` + `ReadableStream` 解析（**不用** `EventSource`，因为需要 POST JSON）：
- 解析 `event:` + `data:` 双行
- 分发到 Zustand store：`appendToken` / `setCitations` / `setStep` / `setThinking` / `setProgress` / `finalize`
- 暴露 `send / stop / isStreaming`

### 4. 环境变量
- `.env.production`：`VITE_API_BASE=https://<user>-<space>.hf.space/api/v1`
- `src/env.ts` 校验并导出

---

## 部署

### 后端 — HF Spaces Dockerfile [backend/Dockerfile](backend/Dockerfile)

```dockerfile
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 DATA_DIR=/data
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libgl1 libglib2.0-0 poppler-utils && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
# 预热模型，避免 Space 启动超时
RUN python -c "from FlagEmbedding import BGEM3FlagModel, FlagReranker; \
    BGEM3FlagModel('BAAI/bge-m3', use_fp16=True); \
    FlagReranker('BAAI/bge-reranker-v2-m3')"
COPY app ./app
RUN mkdir -p /data/chroma /data/sqlite /data/uploads
EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
```

`backend/README.md` 顶部 HF 元数据：`sdk: docker, pinned: true`

**HF Space Secrets**：在 Web UI 设置 `MINIMAX_API_KEY` / `ALLOWED_ORIGINS` / `LLM_PROVIDER` / `HF_PERSIST_REPO` / `HF_TOKEN`（持久化同步用）。

### 前端 — GitHub Actions [.github/workflows/deploy-frontend.yml](.github/workflows/deploy-frontend.yml)

- 触发：push 到 main 改动 `frontend/**`
- 步骤：`npm ci && npm run build` → `actions/upload-pages-artifact@v3` → `actions/deploy-pages@v4`
- Pages 设置：Source = GitHub Actions
- 自定义 base：`vite.config.ts` 中 `base: '/<repo-name>/'`

---

## 关键库版本（2026-06）

| 类别 | 库 | 版本 |
|---|---|---|
| 后端框架 | fastapi / uvicorn | ≥0.136 / ≥0.34 |
| Agent | langgraph / langgraph-checkpoint-sqlite | ≥1.2 / ≥2.0（⚠️ checkpoint ≥1.0.10 修复 CVE-2026-28277） |
| 数据 | pydantic / pydantic-settings / pydantic-ai | ≥2.9 / ≥0.2 |
| 解析 | docling / marker-pdf / mineru（可选） | ≥2.98 / ≥1.10 / ≥0.22 |
| Embedding | FlagEmbedding (BGE-M3) | ≥1.3 |
| 向量库 | chromadb | ≥1.0（Rust 核心重写） |
| LLM SDK | openai (兼容 MiniMax) | ≥1.60 |
| 前端 | react / vite / react-router-dom | 19.2+ / 8（Rolldown 构建）/ 7 |
| 状态 | zustand / @tanstack/react-query | 5 / 5 |
| UI | tailwindcss / shadcn/ui | v4 / CLI v4 |
| 评估 | ragas / deepeval | ≥0.2 / ≥1.0 |
| 追踪 | langsmith | ≥0.2 |
| 持久化 | huggingface_hub | ≥0.30 |

---

## 实施阶段

| 阶段 | 范围 | 产出 | 天数 |
|---|---|---|---|
| **1. 后端骨架** | FastAPI / healthz / LLM 抽象 / MiniMax provider / 简单 `/chat`（无 RAG）/ 持久化同步 | 后端可独立部署到 HF Space | 1-2 |
| **2. 文档摄入** | Docling + Marker 兜底 / 语义分块 + 上下文预置 / BGE-M3 三路向量 / Chroma / upload-list-delete | 上传 PDF → 看到 chunks | 2-3 |
| **3. RAG + Agent** | 三路混合检索 / BGE-reranker / LangGraph 状态图（route→rewrite→retrieve→rerank→answer→evaluate）/ 引用 / SQLite checkpoint | 问答带引用 | 2-3 |
| **4. 前端 UI** | React 19 + Vite 8 + shadcn / ChatArea / SSE 流式 (astream_events) / 文档管理 | 本地 dev 可用 | 1-2 |
| **5. 部署** | HF Dockerfile + 持久化同步 / GH Actions / CORS / 环境变量 | 两侧同时上线 | 0.5-1 |
| **6. 打磨** | 引用片段含页码 / Agent trace UI / 错误边界 / 重试 / 中英提示 / RAGAS 评估 | 生产可用 | 1-2 |

**总计 8-13 个工作日。**

---

## 验证方案（端到端）

### 本地 smoke
```bash
cd backend && uvicorn app.main:app --reload --port 7860
curl http://localhost:7860/api/v1/healthz

# 1) 上传
curl -F "file=@sample.pdf" http://localhost:7860/api/v1/documents/upload
# → {"doc_id":"abc123","chunk_count":42,"status":"ready"}

# 2) 流式问答
curl -N -X POST http://localhost:7860/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"session_id":"t1","message":"第三季度的营收是多少？"}'

# 预期 SSE：
#   event: thinking data: {"content":"用户在询问财务数据，需要检索..."}
#   event: agent_step data: {"node":"query_rewrite","status":"running"}
#   event: retrieval data: {"doc_ids":["abc123"],"scores":[0.92]}
#   event: token data: {"content":"第三"}
#   event: citation data: {"doc_id":"abc123","page":12,"snippet":"Q3 营收 $4.2M...","score":0.95}
#   event: done
```

### RAG 质量评估（RAGAS + DeepEval）
```bash
# 离线评估：RAGAS 评估 RAG 质量
cd backend && python -m pytest tests/eval/test_ragas.py -v

# 评估指标：
# - Faithfulness（忠实度）：答案是否仅基于检索到的上下文
# - Answer Relevancy（答案相关性）：答案是否回答了用户的问题
# - Context Precision（上下文精度）：检索到的文档是否相关
# - Context Recall（上下文召回）：是否检索到了所有相关文档

# CI/CD 质量门禁：DeepEval（pytest 风格断言）
cd backend && deepeval test run tests/eval/test_quality_gate.py
```

### LangSmith 可观测性（开发/调试环境）
- 设置 `LANGCHAIN_TRACING_V2=true` + `LANGCHAIN_API_KEY`
- Dashboard 查看每次查询的完整 trace（节点耗时、token 用量、检索质量）
- 监控 latency breakdown / token usage / retrieval hit rate

### 前端 E2E
1. `cd frontend && npm run dev`
2. 拖一份中英混合 PDF 到 UploadPanel → 列表显示带 status
3. ChatInput 输入问题 → 流式出现 token
4. 验证：
   - [ ] token-by-token 流畅
   - [ ] CitationPanel 显示 doc_id + 页码 + 片段
   - [ ] AgentStepTrace（开发开关）显示 route→rewrite→retrieve→rerank→answer→evaluate
   - [ ] Stop 按钮中断流
   - [ ] 刷新页面 → 会话历史恢复（SQLite checkpoint）
   - [ ] thinking 事件在 UI 中正确显示 Agent 推理过程

### 部署验证
1. push backend → HF Space 构建成功（日志看到 `BGE-M3 loaded`）
2. HF Space secret 设 `ALLOWED_ORIGINS=["https://<user>.github.io"]`
3. push frontend → GH Pages 部署成功
4. 打开 `https://<user>.github.io/<repo>/#/chat` → 跨域 SSE 无 CORS 错误
5. **持久化验证**：重启 HF Space → 数据从 HF Dataset repo 自动恢复

### 失败模式清单
- [ ] Docling 大 PDF OOM → 降级 Marker → 分页处理
- [ ] Chroma 损坏 → admin 端点从 `/data/uploads` 重建
- [ ] LLM 限流 → `minimax.py` 指数退避
- [ ] 临时磁盘数据丢失 → lifespan 自动从 HF Dataset repo 恢复
- [ ] 流中断 → 客户端用 `last-event-id` 自动重连
- [ ] CRAG 循环超时 → max_iterations=2 硬限制 + 超时降级直接回答

---

## 关键文件清单

| 文件 | 职责 |
|---|---|
| [backend/app/main.py](backend/app/main.py) | FastAPI 入口 / CORS / lifespan / 路由挂载 / 持久化恢复 |
| [backend/app/config.py](backend/app/config.py) | 全量环境变量配置（含 CRAG / LangSmith / 持久化参数） |
| [backend/app/llm/minimax.py](backend/app/llm/minimax.py) | MiniMax-M3 流式客户端（OpenAI 兼容） |
| [backend/app/services/ingestion.py](backend/app/services/ingestion.py) | 上传→解析→分块→向量化→入库编排 |
| [backend/app/services/chunking.py](backend/app/services/chunking.py) | 结构感知 + 语义分块 + Anthropic-style 上下文预置 |
| [backend/app/services/parsers/base_parser.py](backend/app/services/parsers/base_parser.py) | 解析器抽象基类 |
| [backend/app/services/parsers/docling_parser.py](backend/app/services/parsers/docling_parser.py) | Docling 解析（PDF/Word/图片） |
| [backend/app/services/parsers/mineru_parser.py](backend/app/services/parsers/mineru_parser.py) | MinerU 学术文档解析（可选） |
| [backend/app/services/parsers/vlm_parser.py](backend/app/services/parsers/vlm_parser.py) | 多模态 LLM 视觉文档解析（远期） |
| [backend/app/services/embedding.py](backend/app/services/embedding.py) | BGE-M3 dense+sparse+colbert 封装 |
| [backend/app/services/vector_store.py](backend/app/services/vector_store.py) | ChromaDB v1.0 持久化适配 + 三路检索 |
| [backend/app/services/persist.py](backend/app/services/persist.py) | HF Dataset repo 持久化同步（冷启动容错） |
| [backend/app/services/llm_cache.py](backend/app/services/llm_cache.py) | LLM 响应 LRU 缓存 |
| [backend/app/streaming/events.py](backend/app/streaming/events.py) | AG-UI 兼容事件 schema（Pydantic + 常量） |
| [backend/app/agents/graph.py](backend/app/agents/graph.py) | LangGraph v1.2 StateGraph 装配 |
| [backend/app/agents/nodes.py](backend/app/agents/nodes.py) | route / query_rewrite / retrieve / rerank / answer / evaluate 节点 |
| [backend/app/api/chat.py](backend/app/api/chat.py) | `/chat/stream` SSE 端点（astream_events v2） |
| [backend/Dockerfile](backend/Dockerfile) | HF Spaces 构建（Python 3.12 + 模型预热） |
| [backend/tests/eval/test_ragas.py](backend/tests/eval/test_ragas.py) | RAGAS 离线质量评估 |
| [backend/tests/eval/test_quality_gate.py](backend/tests/eval/test_quality_gate.py) | DeepEval CI/CD 质量门禁 |
| [frontend/src/hooks/useChatStream.ts](frontend/src/hooks/useChatStream.ts) | SSE 消费驱动 Zustand |
| [frontend/src/components/chat/CitationPanel.tsx](frontend/src/components/chat/CitationPanel.tsx) | 引用卡片（页码 + 片段） |
| [frontend/src/lib/api.ts](frontend/src/lib/api.ts) | 带 baseURL 的 fetch 客户端 |
| [.github/workflows/deploy-frontend.yml](.github/workflows/deploy-frontend.yml) | 构建并部署 React 到 Pages |
| [.github/workflows/test-backend.yml](.github/workflows/test-backend.yml) | 后端 lint + pytest + DeepEval 质量门禁 |

---

## 风险与权衡

| 风险 | 缓解 |
|---|---|
| HF Space 16GB RAM 仍可能不够并发处理大 PDF | 摄入异步队列（asyncio）+ 单并发 + 分页处理 |
| HF Spaces 临时磁盘数据丢失 | lifespan 启停时自动同步到 HF Dataset repo；冷启动有 try/except 兜底 |
| 首次部署 HF Dataset repo 不存在 | persist.py 用 RepositoryNotFoundError 捕获 → 正常启动 + 首次写入时 create_repo |
| MiniMax-M3 推理质量 | 关键查询可配置回退到 Claude Sonnet（已留 provider 抽象） |
| CRAG 自评循环依赖风险 | evaluate 阶段 1 直接读 reranker score，0.3-0.7 模糊区间才调 LLM judge |
| 跨页表格被 Docling 拆散 | 用 `do_table_structure=True` + 自定义 chunk 合并规则 |
| ColBERT 索引膨胀 | 存 ChromaDB v1.0 multi-vector collection；提供 `enable_colbert` 配置项可降级 |
| 冷启动模型加载慢 | Dockerfile 中预下载 + HF Space 镜像层缓存 |
| 私钥泄露 | 所有 key 走 HF Space Secrets / GitHub Secrets，不入仓 |
| BGE-M3 1GB+ 镜像大小 | 用 `use_fp16=True` + HF Space GPU 选项（按需） |
| 语义分块 + 上下文预置增加摄入时间 | 仅首次摄入执行；可通过配置项关闭 `contextual_retrieval` |
| CRAG 循环增加响应延迟 | 设 `max_iterations=2`；大多数查询一次即命中 |
| LangGraph v1.2 与旧教程不兼容 | 使用官方 v1 迁移指南；实施前核对 GitHub Advisory 最新漏洞 |
| MinerU 依赖较重 | 作为可选解析器，不强制安装；按需启用 |
| 重复上传浪费摄入时间 | SHA256 哈希去重，命中直接返回已有 doc_id |
