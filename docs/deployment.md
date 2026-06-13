# 部署指南

本文档覆盖完整部署流程, 包括后端 (HuggingFace Spaces) + 前端 (GitHub Pages) + 持久化 (HF Dataset) 的所有配置.

## 架构

```
┌─────────────────────────┐
│  GitHub Pages (Frontend)│  React 19 + Vite
│  https://xxx.github.io  │
└────────────┬────────────┘
             │ HTTPS / SSE
             ▼
┌─────────────────────────┐
│  HF Spaces (Backend)    │  FastAPI + LangGraph
│  https://xxx.hf.space   │
│  /data (持久化卷)        │
└────────────┬────────────┘
             │ git LFS push/pull
             ▼
┌─────────────────────────┐
│  HF Dataset (Persist)   │  ChromaDB + SQLite + uploads/
│  username/chatbot-data  │
└─────────────────────────┘
```

---

## 一、部署后端到 HuggingFace Spaces

### 1.1 创建 Space

1. 打开 https://huggingface.co/new-space
2. 填入:
   - **Owner**: 你的用户名或组织
   - **Space name**: 例如 `ai-chatbot`
   - **License**: MIT
   - **SDK**: **Docker**  ← 关键
   - **Space hardware**: CPU basic (免费) / T4 small ($0.60/hr) 按需
3. 点击 **Create Space**

### 1.2 推送后端代码

```bash
# 假设你已 git clone 了 Space 仓库
cd ai-chatbot  # 你刚创建的 Space 仓库
# 把 backend/ 里的所有文件复制到这里
cp -r ../AI-Chatbot/backend/* .
git add . && git commit -m "Initial deploy" && git push
```

> 提示: 也可让 Space 直接读 GitHub 仓库, 设置 Repo → Settings → Connected repos.

### 1.3 配置 Secrets (重要! 不要把这些写到代码里)

进入 Space → **Settings** → **Variables and secrets**:

| 名称 | 类别 | 值 (示例) | 说明 |
|---|---|---|---|
| `LLM_PROVIDER` | Variable | `minimax` | 也可改 openai/qwen |
| `MINIMAX_API_KEY` | **Secret** | `<你的 MiniMax API key>` | **必须设为 Secret** |
| `MINIMAX_BASE_URL` | Variable | `https://api.MiniMax.com/v1` | OpenAI 兼容端点 |
| `MINIMAX_MODEL` | Variable | `MiniMax-M3` | |
| `HF_PERSIST_REPO` | Variable | `yourname/ai-chatbot-data` | HF Dataset repo 名 |
| `HF_TOKEN` | **Secret** | `<你的 HF write token>` | 在 https://huggingface.co/settings/tokens 申请 |
| `ALLOWED_ORIGINS` | Variable | `["https://yourname.github.io"]` | 你的 GH Pages URL |
| `LANGSMITH_TRACING` | Variable | `false` | 调试可设 true |
| `LANGCHAIN_API_KEY` | **Secret** | `<langsmith key>` | (可选) |

### 1.4 配置持久化 Dataset Repo

1. 打开 https://huggingface.co/new-dataset
2. 填入:
   - **Name**: `ai-chatbot-data` (与 `HF_PERSIST_REPO` 一致)
   - **License**: MIT
   - **Visibility**: **Private** (个人数据)
3. 创建后会自动有 git LFS, 第一次启动后端时 lifespan 会自动从空 repo 启动, 第一次写入时自动 create_repo (如果你已先在 UI 创建则更好)

### 1.5 等待构建

Space 第一次 build 大约 5-10 分钟 (要装 docling + FlagEmbedding + chromadb).

**日志关键词**:
- `Successfully built` → 构建成功
- `BGE-M3 warmed up` → 模型加载成功
- `Backend ready` → 服务可用

### 1.6 验证

```bash
# 替换为你的 Space URL
SPACE=https://yourname-ai-chatbot.hf.space

# 健康检查
curl $SPACE/api/v1/healthz
curl $SPACE/api/v1/readyz

# 上传测试
curl -F "file=@test.pdf" $SPACE/api/v1/documents/upload
```

---

## 二、部署前端到 GitHub Pages

### 2.1 准备 GitHub 仓库

1. 创建一个新 GitHub 仓库, 例如 `ai-chatbot` (可以是 `yourname/ai-chatbot` 或 `yourname/yourname.github.io`)
2. 把整个项目 (含 backend/, frontend/, .github/) 推上去

```bash
cd /path/to/AI-Chatbot
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/yourname/ai-chatbot.git
git push -u origin main
```

### 2.2 启用 GitHub Pages

仓库 → **Settings** → **Pages**:
- **Source**: **GitHub Actions** ← 关键

### 2.3 配置 Secrets

仓库 → **Settings** → **Secrets and variables** → **Actions**:

#### Secrets (私密)
| 名称 | 值 |
|---|---|
| `VITE_API_BASE` | `https://yourname-ai-chatbot.hf.space/api/v1` |

#### Variables (公开也行)
| 名称 | 值 | 说明 |
|---|---|---|
| `VITE_REPO_NAME` | `ai-chatbot` | 你的仓库名 (项目页需要, 用户页可留 `yourname.github.io`) |

### 2.4 触发部署

```bash
git commit --allow-empty -m "Trigger Pages deploy"
git push
```

进入 **Actions** 标签, 应该看到 "Deploy Frontend to GitHub Pages" workflow 正在跑. 约 2-3 分钟构建完成.

### 2.5 访问

| 场景 | URL |
|---|---|
| 用户/组织页 (`username.github.io`) | `https://yourname.github.io/` |
| 项目页 | `https://yourname.github.io/ai-chatbot/#/chat` |

---

## 三、CORS 配置

后端的 `ALLOWED_ORIGINS` 必须包含前端实际部署的域. 格式: JSON 数组字符串.

示例 (多域):
```
ALLOWED_ORIGINS=["https://yourname.github.io", "https://yourname.github.io/ai-chatbot"]
```

本地 dev 时 (`pnpm dev`), 前端在 `http://localhost:5173`, 已默认放行.

---

## 四、常见问题

### 4.1 HF Space 构建失败

查看 **Logs** 标签, 常见:
- `pip install` 超时: 检查 `requirements.txt` 是否锁了正确版本
- 镜像太大: HF Space CPU basic 限制 50GB 镜像. 我们的 ~10GB (含 docling + FlagEmbedding) 应该 OK
- 系统库缺失: 已在 Dockerfile 装 `poppler-utils` / `libgl1`

### 4.2 前端 SSE 跨域

打开浏览器 DevTools → Network → 找 `/api/v1/chat/stream`:
- 看到 CORS error → 检查 `ALLOWED_ORIGINS`
- 看到 502/504 → 后端还在启动或崩溃, 查 Space logs

### 4.3 持久化数据丢失

如果 `HF_PERSIST_REPO` 没配或 token 没权限, 数据会每次重启丢. 检查:
- `/readyz` 看 `persist.enabled` 是否为 `true`
- HF Dataset repo 是不是 private + token 有 write 权限

### 4.4 摄入卡住 (长时间 embedding)

BGE-M3 在 CPU 上 ~1-2 秒/句, 一份 50 页 PDF 大约 1-3 分钟. 耐心等. 如果超过 10 分钟没动, 查 Space logs (可能是 OOM).

### 4.5 升级 / 重新部署

后端: 推代码到 Space 仓库 → 自动重新构建
前端: 推代码到 GitHub main → Actions 自动 build + deploy

---

## 五、零成本 vs 付费升级

| 项 | 免费 (默认) | 付费选项 |
|---|---|---|
| HF Space | CPU basic, 16GB RAM, 50GB 临时磁盘 | T4 small GPU ($0.60/hr, 用于 BGE-M3 加速) |
| HF Dataset | 私有, 5GB | 付费版无限制 |
| GH Pages | 100GB 流量/月, 无限站点 | 私有 repo 需 GH Pro |
| LLM API | 按 token 计费 (MiniMax V3 ~$0.14/M) | — |

**典型个人用量月度成本**:
- 100 文档/月 (5MB 平均) 摄入
- 1000 次问答/月
- → LLM 费用约 $0.5-2
- 其它全免
