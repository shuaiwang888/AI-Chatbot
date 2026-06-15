# AI Chatbot · 私人 Agent 智能客服

> 基于多模态文档 (PDF / Word / 图片) 的 RAG + Agent 问答系统.
> 多轮对话 · 引用源追踪 · 工具调用 · 零成本部署.

![demo](https://img.shields.io/badge/status-MVP-blue)
![python](https://img.shields.io/badge/python-3.11%2B-blue)
![react](https://img.shields.io/badge/react-19-61dafb)
![langgraph](https://img.shields.io/badge/langgraph-0.3%2B-orange)
![deploy](https://img.shields.io/badge/deploy-HF%20Spaces%20%2B%20GH%20Pages-brightgreen)

## ⚠️ 部署方式

**本项目只支持线上部署，不提供本机本地启动。**

| 角色 | 平台 | 地址 |
|---|---|---|
| 后端 | HuggingFace Spaces (Docker) | `https://<user>-<space>.hf.space` |
| 前端 | GitHub Pages (静态) | `https://<user>.github.io/<repo>/` |
| 持久化 | HuggingFace Dataset (Git LFS) | `https://huggingface.co/datasets/<user>/<data>` |

部署步骤见 [docs/deployment.md](docs/deployment.md)。代码改动通过：
- **前端** → `git push main` → GH Actions 自动 build & deploy
- **后端** → `./scripts/deploy-backend-fix.sh` → 推到 HF Space 仓库

## ✨ 功能

- 📄 **多格式文档摄入**: PDF / Word / PPT / Excel / 图片 (中英 OCR)
- 🧠 **混合检索**: BGE-M3 dense + sparse + ColBERT 三路 → RRF 融合
- 🎯 **精排 + CRAG 自校正**: BGE-reranker-v2-m3 + 二阶段评估, 拒答有度
- 💬 **多轮对话**: LangGraph SQLite checkpoint, 持久化
- 📚 **引用源**: 每次回答附 page + heading + snippet + score
- 🛠️ **工具调用**: 5 个工具 (doc_summary / compare / calc / list / time)
- 🚀 **零成本部署**: HF Spaces + GH Pages + HF Dataset 持久化

## 🏗️ 架构

```
React 19 + Vite + shadcn/ui  →  GitHub Pages (静态)
                                ↓ SSE
FastAPI + LangGraph + Docling  →  HuggingFace Spaces (Docker)
   BGE-M3 + BGE-Reranker + ChromaDB
   LLM (MiniMax-M3 / OpenAI / Qwen)   ↓ git LFS
   HF Dataset Repo (持久化)
```

详见 [docs/architecture.md](docs/architecture.md)

## 📁 项目结构

```
ai-chatbot/
├── PLAN.md                       # 完整方案 (557 行, 4 处高优修复)
├── README.md                     # ← 你在这里
├── docs/
│   ├── architecture.md
│   └── deployment.md             # 部署指南 (HF Space + GH Pages)
│
├── backend/                      # FastAPI + LangGraph (线上后端)
│   ├── Dockerfile                # HF Space 构建
│   ├── README.md                 # HF Space 元数据
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── app/                      # 源码 (同步推 HF Space)
│   └── tests/unit/               # 3 个 smoke 脚本 (线上跑)
│
├── frontend/                     # React 19 + Vite (线上前端)
│   ├── package.json
│   ├── vite.config.ts            # GH Pages base path
│   ├── tsconfig.json
│   ├── README.md
│   └── src/                      # 源码 (GH Actions 自动 build)
│
├── scripts/                      # 部署脚本
│   ├── deploy-to-hf-space.sh     # 完整后端打包 + 推送
│   ├── deploy-backend-fix.sh     # 增量修复 (tarball + strip-components)
│   └── deploy-via-api.py         # hf-mirror 不可用时的 API 直推
│
└── .github/workflows/
    └── deploy-frontend.yml       # GH Pages 自动部署
```

## 📁 项目结构

```
ai-chatbot/
├── PLAN.md                       # 完整方案 (557 行, 4 处高优修复)
├── README.md                     # ← 你在这里
├── docs/
│   ├── architecture.md
│   └── deployment.md
│
├── backend/                      # FastAPI + LangGraph
│   ├── Dockerfile
│   ├── README.md                 # HF Space 元数据
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py               # 入口
│   │   ├── config.py             # 全量配置
│   │   ├── api/                  # 4 个 router
│   │   ├── services/             # ingestion / chunking / embedding / vector_store / reranker / llm_cache / persist
│   │   ├── agents/               # LangGraph (state / nodes / graph / tools / prompts)
│   │   ├── llm/                  # LLM 抽象 (base / minimax / factory)
│   │   ├── parsers/              # docling / marker
│   │   ├── models/               # Pydantic + SQLite
│   │   ├── streaming/            # AG-UI 9 类 SSE 事件
│   │   └── core/                 # paths / logging / errors
│   └── tests/unit/               # 3 个 smoke 脚本
│
├── frontend/                     # React 19 + Vite
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── README.md
│   └── src/
│       ├── App.tsx
│       ├── main.tsx
│       ├── router.tsx
│       ├── env.ts
│       ├── types.ts
│       ├── styles/globals.css
│       ├── lib/                  # api / sse / utils
│       ├── stores/               # Zustand
│       ├── hooks/                # useChatStream / useDocuments
│       └── components/
│           ├── ui/               # shadcn primitives
│           ├── chat/             # 7 个组件
│           ├── documents/        # 3 个组件
│           └── layout/           # Sidebar / TopBar
│
└── .github/workflows/
    ├── deploy-frontend.yml       # GH Pages 自动部署
    └── test-backend.yml          # 后端 lint + smoke
```

## 🧪 测试 (在线上 HF Space 跑)

HF Space 网页 → **Shell** 标签页内:

```bash
cd /app && python tests/unit/smoke_phase1.py   # 基础 LLM + API
cd /app && python tests/unit/smoke_phase2.py   # 文档摄入
cd /app && python tests/unit/smoke_phase3.py   # Agent 端到端
```

## 🛠️ 技术栈

### 后端
- **Web**: FastAPI 0.115+, Uvicorn
- **Agent**: LangGraph 0.3+ (StateGraph + AsyncSqliteSaver)
- **LLM**: MiniMax-M3 (默认) / OpenAI / Anthropic / Qwen (统一 OpenAI 兼容协议)
- **解析**: Docling 2.30+ (结构感知 + 跨页表 + OCR)
- **Embedding**: BGE-M3 (FlagEmbedding 1.2+)
- **Reranker**: BGE-reranker-v2-m3
- **向量库**: ChromaDB 1.0+ (multi-vector)
- **元数据**: SQLite (WAL 模式)
- **持久化**: HuggingFace Dataset (Git LFS)

### 前端
- **框架**: React 19 + TypeScript strict
- **构建**: Vite 6+
- **样式**: Tailwind v4 + shadcn/ui (Radix 原语)
- **状态**: Zustand 5 (聊天 / UI)
- **数据**: TanStack Query 5 (文档 / 健康)
- **路由**: HashRouter (兼容 GH Pages)
- **虚拟化**: react-virtuoso
- **图标**: lucide-react

## 📊 性能

| 指标 | 数值 |
|---|---|
| 50 页 PDF 摄入 | 1-3 分钟 |
| 检索延迟 (无 LLM judge) | < 500ms |
| 检索延迟 (有 LLM judge) | 1-3s |
| 月成本 (个人) | $0.5-2 LLM |

## 🔒 安全

- ✅ `calculate` 工具用 AST 沙箱, 防 prompt injection
- ✅ 路径穿越防护 (`Path(name).name`)
- ✅ MIME 嗅探, 50MB 上限
- ✅ CORS 白名单 (非 `*`)
- ✅ 异常统一处理 (AppError + 全局 handler)
- ✅ 所有 API key 走 Secrets, 不入仓

## 📜 License

MIT
