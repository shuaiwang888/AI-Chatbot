# 部署指南（实战版）

> 本文档基于 **2026-06-13 首次成功部署**的实战过程整理, 记录了所有踩过的坑. 后续改完功能重部署时, 按本文档**顺序**操作即可.
>
> 实际部署的服务:
> - 前端: https://shuaiwang888.github.io/AI-Chatbot/
> - 后端: https://appQQQ-ai-chatbot.hf.space/api/v1/
> - 代码仓库: https://github.com/shuaiwang888/AI-Chatbot
> - HF Space: https://huggingface.co/spaces/appQQQ/ai-chatbot

---

## 0. 架构总览

```
┌──────────────────────────────────────┐
│  GitHub Pages (Frontend, 静态)        │  React 19 + Vite
│  https://shuaiwang888.github.io      │  base=/AI-Chatbot/
│  /AI-Chatbot/                        │
└──────────────┬───────────────────────┘
               │ HTTPS + SSE (跨域)
               ▼
┌──────────────────────────────────────┐
│  HF Space (Backend, Docker)           │  FastAPI + LangGraph
│  https://appQQQ-ai-chatbot.hf.space  │  端口 7860
│  /data (持久卷, 50GB)                 │  → /data/chroma + /data/sqlite
└──────────────────────────────────────┘
```

**总成本 ≈ $0/月**(HF Space 免费 16GB + GH Pages 免费; 只付 LLM token 费, 实测每条对话约 $0.001-0.005).

---

## 1. 一次性准备

### 1.1 项目目录结构 (已经组织好)

```
ai-chatbot/
├── backend/                   # → 推到 HF Space
│   ├── Dockerfile
│   ├── app/
│   ├── requirements.txt
│   └── ...
├── frontend/                  # → GH Actions 自动 build
│   ├── package.json
│   ├── package-lock.json      # ← 用 npm, 不是 pnpm
│   └── ...
├── .github/workflows/
│   └── deploy-frontend.yml    # GH Pages 部署
├── scripts/
│   └── deploy-to-hf-space.sh  # 一键推 Space 脚本
└── docs/
    └── deployment.md          # ← 你正在读的文件
```

### 1.2 GitHub 仓库

```bash
cd /Users/appstore/AI-Code/提升项目/AI-Chatbot
git init
git add .
git commit -m "init: ai-chatbot"
git branch -M main
git remote add origin git@github.com:shuaiwang888/AI-Chatbot.git
git push -u origin main
```

`.gitignore` 已经排除了 `backend/data/` 和 `backend/.env`, **不会泄露密钥和本地数据**.

---

## 2. 部署后端 → HuggingFace Space

### 2.1 创建 Space

打开 https://huggingface.co/new-space:

| 字段 | 值 |
|---|---|
| Space name | `ai-chatbot` |
| License | MIT |
| **SDK** | **Docker** ← 必须选这个 |
| Hardware | **CPU basic (free)** ← 16GB RAM 够用 |
| Storage | 默认即可 (免费 20GB 持久卷) |
| Visibility | Public 或 Private |

创建后记录:
- 仓库 URL: `https://huggingface.co/spaces/appQQQ/ai-chatbot`
- **运行时 URL**: `https://appQQQ-ai-chatbot.hf.space` (注意是用户名-空格名连写, 全小写)

### 2.2 推送 backend/ 到 Space

有 3 种方式, **按场景选**:

#### 方式 A: 一键脚本 (推荐, 本地 macOS)

```bash
./scripts/deploy-to-hf-space.sh appQQQ ai-chatbot
```

脚本自动: 克隆空 Space → 复制 `backend/` → 清理 `data/`/`.venv`/`__pycache__` → commit → push.

#### 方式 B: 手动 SSH (本机有 HF SSH key)

```bash
# 在项目根目录
WORK=/tmp/hf-space-deploy
mkdir -p $WORK && cd $WORK
git clone git@hf.co:spaces/appQQQ/ai-chatbot
cd ai-chatbot
cp -R /path/to/AI-Chatbot/backend/. .   # 注意末尾的 .
rm -rf data __pycache__ tests
find . -name "*.db" -delete
git add -A
git -c user.name=deploy -c user.email=d@l commit -m "deploy backend"
git push origin main
```

#### 方式 C: HTTPS + Token (本机没 SSH key, 或 SSH 22 端口被封)

```bash
# 1. 在 https://huggingface.co/settings/tokens 生成 write token
# 2. 用 token 克隆 (避开 SSH)
git clone https://appQQQ:<TOKEN>@huggingface.co/spaces/appQQQ/ai-chatbot
# 或走国内镜像
git clone https://appQQQ:<TOKEN>@hf-mirror.com/spaces/appQQQ/ai-chatbot

# 3. 复制 backend/, 清理, commit, push (同上)
```

### 2.3 配置 Space Secrets

进入 https://huggingface.co/spaces/appQQQ/ai-chatbot/settings → **Variables and secrets**:

| Name | Type | Value | 说明 |
|---|---|---|---|
| `MINIMAX_API_KEY` | **secret** | `sk-cp-...` | LLM API key (敏感) |
| `MINIMAX_BASE_URL` | variable | `https://api.minimaxi.com/v1` | OpenAI 兼容端点 |
| `MINIMAX_MODEL` | variable | `MiniMax-M3` | 模型名 |
| `EMBEDDING_MODEL` | variable | `BAAI/bge-m3` | Embedding |
| `RERANKER_MODEL` | variable | `BAAI/bge-reranker-v2-m3` | Reranker |
| `ALLOWED_ORIGINS` | variable | `["https://shuaiwang888.github.io"]` | CORS 白名单 (**必须精确匹配前端域**) |
| `LLM_CACHE_ENABLED` | variable | `true` | 重复问题走缓存省钱 |
| `HF_PERSIST_REPO` | secret (可选) | `appQQQ/ai-chatbot-data` | 备份数据到 HF Dataset |
| `HF_TOKEN` | secret (可选) | `<write token>` | HF 写权限 |

> ⚠️ **Pydantic Settings 大小写敏感**, 名称必须**完全一致** (上面表格里复制).

### 2.4 重启 + 验证

配完 secrets 后, 在 Space 主页右上角 **⋮** → **Restart this Space**.

第一次构建 8-15 分钟 (要装 FlagEmbedding + 拉 BGE-M3 2.3GB).

**Logs 标签页关键节点**:
```
pip install -r requirements.txt ...    # 3-5 分钟
=== Loading BGE-M3: model=BAAI/bge-m3 ===
=== BGE-M3 warmed up ===                # ← 看到这行说明 embedding OK
=== Reranker warmed up ===              # ← 看到这行说明 rerank OK
INFO  Backend ready
INFO  Uvicorn running on http://0.0.0.0:7860  ← 服务可用
```

验证:
```bash
curl https://appQQQ-ai-chatbot.hf.space/api/v1/healthz
# 期望: {"status":"ok","llm":true,...}

curl -X POST https://appQQQ-ai-chatbot.hf.space/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"v1","message":"ping","locale":"zh"}'
# 期望: 返回中文回答 (3-5 秒)
```

---

## 3. 部署前端 → GitHub Pages

### 3.1 启用 Pages

打开 https://github.com/shuaiwang888/AI-Chatbot/settings/pages:

- **Source**: 选 **GitHub Actions** (不是 "Deploy from a branch")

### 3.2 配置 Secret

打开 https://github.com/shuaiwang888/AI-Chatbot/settings/secrets/actions → **New repository secret**:

| Name | Secret |
|---|---|
| `VITE_API_BASE` | `https://appQQQ-ai-chatbot.hf.space/api/v1` |

(可选) **Variables** 标签页:
| Name | Value |
|---|---|
| `VITE_REPO_NAME` | `AI-Chatbot` ← **你的仓库实际名 (大小写匹配!)** |

### 3.3 触发部署

任选一种:
```bash
# A. 命令行
git commit --allow-empty -m "ci: trigger Pages deploy"
git push origin main

# B. 网页: Actions → Deploy Frontend to GitHub Pages → Run workflow
```

约 2-3 分钟构建完. 去 Actions 看状态.

### 3.4 访问

```
https://<用户名>.github.io/<仓库名>/
# 例: https://shuaiwang888.github.io/AI-Chatbot/
```

---

## 4. 端到端验证 checklist

部署完后**按顺序**跑一遍:

```bash
# 1. 前端可达
curl -I https://shuaiwang888.github.io/AI-Chatbot/
# 期望: HTTP 200

# 2. 后端可达
curl https://appQQQ-ai-chatbot.hf.space/api/v1/healthz
# 期望: {"status":"ok","llm":true,...}

# 3. CORS 配置正确 (前端域被白名单)
curl -I -H "Origin: https://shuaiwang888.github.io" \
  https://appQQQ-ai-chatbot.hf.space/api/v1/documents
# 期望: 响应头有 access-control-allow-origin: https://shuaiwang888.github.io

# 4. E2E 对话
curl -X POST https://appQQQ-ai-chatbot.hf.space/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"e2e","message":"hi","locale":"zh"}'
# 期望: 3-5 秒返回中文回答
```

最后, 在浏览器打开前端 URL, 实际发一条消息, 看是否流式出现 token.

---

## 5. 重新部署 (日常流程)

### 5.1 仅前端改动

```bash
# 改 frontend/src/... 然后:
git add . && git commit -m "feat: xxx" && git push origin main
# GH Actions 自动 build + 部署 (2-3 分钟)
```

### 5.2 仅后端改动

```bash
# 改 backend/app/... 然后:
./scripts/deploy-to-hf-space.sh appQQQ ai-chatbot
# 或手动 push (见 2.2)
# HF Space 自动重新构建 (3-5 分钟, 用缓存)
```

### 5.3 同时改前后端

```bash
git add . && git commit -m "feat: both" && git push origin main
./scripts/deploy-to-hf-space.sh appQQQ ai-chatbot
# 两边并行部署, 互不阻塞
```

---

## 6. ⚠️ 踩过的坑 (本节必看!)

### 坑 1: HF Space Dockerfile 必须 COPY 完整 backend

**症状**: Space 启动后 502, Logs 报 `ModuleNotFoundError: No module named 'app'`

**原因**: HF Space 期望**根目录**有 `Dockerfile` 和 `app/` 等文件. 不能只 push `backend/` 目录.

**解决**: 把 `backend/` 里的所有内容 (含 `Dockerfile`) 提到 Space 仓库的根. 参见 2.2 的 `cp -R backend/. .` (注意末尾的 `.`).

---

### 坑 2: macOS / 沙箱网络封锁 huggingface.co 主域

**症状**:
```bash
curl https://huggingface.co  # Connection timed out
# 但
curl https://api.hf.co       # 200 OK
curl https://hf-mirror.com   # 200 OK (国内镜像)
```

**原因**:
- `huggingface.co` 解析到 `104.244.43.208`, 国内网络封了
- `api.hf.co` 走不同 IP, 通常能通
- `hf-mirror.com` 是 HF 的国内镜像, 完整可用

**解决** (按优先级尝试):
1. **SSH via `git@hf.co:`** (推荐, 走 22 端口, 通常不被封):
   ```bash
   git clone git@hf.co:spaces/appQQQ/ai-chatbot
   # 或 push 时:
   git remote set-url origin git@hf.co:spaces/appQQQ/ai-chatbot
   ```
2. **HTTPS 走 hf-mirror.com**:
   ```bash
   git remote set-url origin https://USER:TOKEN@hf-mirror.com/spaces/appQQQ/ai-chatbot
   git push
   ```
3. **本机有 HTTP 代理** (ClashX / Surge):
   ```bash
   export https_proxy=http://127.0.0.1:7890
   git push
   ```
4. **最后手段: 复制仓库到本地其他机器 push**.

---

### 坑 3: GH Actions `environment` 写在顶层 → 报错

**症状**:
```
Invalid workflow file: .github/workflows/deploy-frontend.yml#L1
(Line: 22, Col: 1): Unexpected value 'environment'
```

**原因**: `environment` 写在 workflow 顶层是 **Beta 功能**, 很多 org 没开. 应该挪到具体 job 里.

**修法** (已修, 不要再回退):
```yaml
# ❌ 错误 (top-level)
environment:
  name: github-pages
  url: ${{ steps.deployment.outputs.page_url }}
jobs:
  build: ...

# ✅ 正确 (在 deploy job 里)
jobs:
  build: ...
  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
```

---

### 坑 4: GH Actions `Setup Node` 缓存配置成 pnpm 但项目用 npm

**症状**:
```
build
Setup Node: Unable to locate executable file: pnpm
```

**原因**: 项目 `frontend/` 下只有 `package-lock.json`, 没有 `pnpm-lock.yaml`. 但 workflow 配了 `cache: 'pnpm'`, 导致 `cache-dependency-path` 找不到文件.

**修法** (已修): 改成 npm:
```yaml
- name: Setup Node
  uses: actions/setup-node@v4
  with:
    node-version: 20
    cache: 'npm'                                          # ← 改这里
    cache-dependency-path: frontend/package-lock.json    # ← 改这里
- name: Install dependencies
  working-directory: frontend
  run: npm ci                                            # ← 改这里
- name: Build
  working-directory: frontend
  run: npm run build                                     # ← 改这里
```

---

### 坑 5: HF Space `ALLOWED_ORIGINS` 没设或设错 → 跨域失败

**症状**: 浏览器 Network 里 `(blocked: cors)` 或 `405 Method Not Allowed`.

**原因**:
1. 没设 `ALLOWED_ORIGINS` → 后端用默认 `["http://localhost:5173", "http://localhost:3000"]`
2. 大小写不匹配 / 带斜杠 / 协议不对

**正确格式** (Pydantic 解析 JSON 数组):
```
ALLOWED_ORIGINS=["https://shuaiwang888.github.io"]
# 注意: 
#   - 必须有 https:// (不能是 // 或 *)
#   - 末尾**不能**有斜杠
#   - 多域用逗号分隔
#   - 字符串必须用双引号 (JSON 规范)
```

---

### 坑 6: 推 backend 时把 `.venv` / `data/` / `.env` 也带上去

**症状**:
- push 几小时都传不完 (1.7GB .venv)
- HF Space 起来后挂载了 100GB 别人的测试数据
- API key 泄露

**原因**: `cp -R backend/. .` 会把 backend 下的 `data/` `.venv/` `.env` 也带过去.

**修法** (已修, 见 `scripts/deploy-to-hf-space.sh`):

Space 仓库根目录创建 `.gitignore`:
```gitignore
# HF Space build context .gitignore
data/
.venv/
__pycache__/
tests/
.env
*.db
*.sqlite
backend/data/
```

**或者**手动删:
```bash
cd /path/to/space-clone
rm -rf data __pycache__ tests .pytest_cache
find . -name "*.db" -delete
```

---

### 坑 7: `httpx` 走系统代理导致 LLM 调用超时

**症状**:
- 本地能调通 LLM (curl 直连 OK)
- 部署到 HF Space 后 `readyz` 返回 `llm: false`
- Logs 看不到 LLM 调用, 像什么都没发生

**原因** (本项目特有): `httpx` 默认读 `urllib.getproxies()`, macOS 的 `127.0.0.1:7897` 系统代理被读走. 如果代理服务挂了, LLM 请求会卡住.

**修法** (已修, 见 `backend/app/llm/minimax.py`):
```python
import httpx as _httpx
_http_client = _httpx.AsyncClient(
    trust_env=False,         # ← 关键: 强制不走系统代理
    timeout=timeout,
)
self.client = AsyncOpenAI(
    api_key=api_key or "EMPTY",
    base_url=base_url,
    timeout=timeout,
    max_retries=0,
    http_client=_http_client,    # ← 传入
)
```

---

### 坑 8: BGE-M3 启动报 `Cannot copy out of meta tensor`

**症状**:
- HF Space 启动后首次上传 PDF 时 `RuntimeError: Cannot copy out of meta tensor; no data!`
- 第二次重启会好 (因为模型已经在内存)

**原因**: FlagEmbedding 在 PyTorch 2.2 + transformers 4.57 组合下, 异步 `run_in_executor` 触发的首次 `.to(device)` 在 worker 线程里跑, 没正确完成 meta → cpu 转移.

**修法** (已修):
1. `backend/app/main.py`: lifespan 里的 warmup 改成**同步**调用 (不要 `run_in_executor`)
2. `backend/app/services/embedding.py`: 加载后立刻跑一次空 encode, 强制 device 转移
3. `backend/app/services/reranker.py`: 同样模式

---

### 坑 9: GH Pages base path 大小写不匹配 → 空白页面

**症状**:
- 部署到 GH Pages 后页面**完全空白**
- HTML 正常返回 200, 但 bundle 404
- 浏览器 DevTools → Network: `index-XXX.js` 报 404

**原因**: GH Pages 对路径**大小写敏感** (虽然 Server 端有 fallback, 但 asset 路径不会). 如果 Vite 用了小写 `ai-chatbot` 作为 base, 但 GitHub 仓库是 `AI-Chatbot`, bundle 找不到.

**验证**:
```bash
# 仓库是大写
curl -I https://USER.github.io/AI-Chatbot/                     # 200 ✓
curl -I https://USER.github.io/AI-Chatbot/assets/index-X.js     # 200 ✓

# Vite 默认用了小写 (会 404)
curl -I https://USER.github.io/ai-chatbot/                      # 404
curl -I https://USER.github.io/ai-chatbot/assets/index-X.js      # 404
```

**修法** (已修, `frontend/vite.config.ts`):
```typescript
function resolveRepoName(): string {
  // 1. 显式 VITE_REPO_NAME (最高优先级, 手动 override)
  const explicit = process.env.VITE_REPO_NAME;
  if (explicit) return explicit;

  // 2. GH Actions 自动注入, 形如 "owner/Repo-Name", 提取大小写正确的仓库名
  const ghRepo = process.env.GITHUB_REPOSITORY;
  if (ghRepo) {
    const parts = ghRepo.split('/');
    if (parts.length === 2 && parts[1]) return parts[1];
  }

  // 3. 兜底 (本地 dev)
  return 'ai-chatbot';
}

const REPO_NAME = resolveRepoName();
// ...
base: mode === 'production' ? `/${REPO_NAME}/` : '/',
```

**关键**: GH Actions 里**不要**硬编码 `VITE_REPO_NAME: ${{ vars.VITE_REPO_NAME || 'ai-chatbot' }}`, 让 `GITHUB_REPOSITORY` 自动接管. 如果用户仓库名带大小写 (如 `AI-Chatbot`), 手动设的小写默认值会把构建搞坏.

---

## 7. 升级到付费版 (按需)

| 项 | 免费 (当前) | 付费选项 | 升级理由 |
|---|---|---|---|
| HF Space CPU basic | 16GB RAM, 免费 | T4 small GPU $0.60/hr | BGE-M3 加速 5-10 倍 |
| HF Space Storage | 20GB 持久卷 | 更大 | 文档库超过 20GB 时 |
| GH Pages | 100GB 流量/月 | — | 个人用够, 不会超 |
| LLM API | 按 token | — | 用 `LLM_CACHE_ENABLED` 省 50%+ |

**建议**: 个人项目免费版**完全够用**, 升级 GPU 不划算 (BGE-M3 fp16 在 CPU 上 5-10 秒/页, 可接受).

---

## 8. 数据备份 (可选, 强烈推荐)

HF Space 持久卷**理论上是持久的**, 但实际有丢失风险 (HF 维护 / 你的 token 失效). 建议加 HF Dataset 备份:

1. 创建私有 Dataset: https://huggingface.co/new-dataset → name: `ai-chatbot-data`
2. Space secrets 加:
   - `HF_PERSIST_REPO` = `appQQQ/ai-chatbot-data`
   - `HF_TOKEN` = `<write token>` (https://huggingface.co/settings/tokens)
3. 后端每次写入会自动 push 到 Dataset repo (异步, 不阻塞请求)
4. Space 重启 / 重建后, lifespan 会从 Dataset 自动拉回数据

---

## 9. 排障速查

| 现象 | 看哪里 | 修复 |
|---|---|---|
| Space 启动后 502 | Space → Logs | 通常是 pip install 失败, 检查 requirements.txt |
| `BGE-M3 warmed up` 没出现 | Space → Logs | 镜像下载卡了, 重启 Space |
| 前端打开空白 | 浏览器 DevTools → Console | 通常是 base path 不对, 看 `VITE_REPO_NAME` |
| 跨域失败 | DevTools → Network | 检查 `ALLOWED_ORIGINS` secret (精确匹配) |
| `readyz` 报 `llm: false` | Space → Logs | LLM 健康检查失败, 检查 `MINIMAX_API_KEY` |
| 上传 PDF 卡死 | Space → Logs → OOM | 单 PDF 超过 50MB 或 RAM 爆了, 改小文件 |
| Chroma 锁文件 | Space → Logs | 已有单 worker, 不会出. 重启 Space |
| SSE 中断 | DevTools → Network | 后端 502/504, 看 Space Logs |

---

## 10. 关键文件 / 命令速查

```bash
# 推后端
./scripts/deploy-to-hf-space.sh appQQQ ai-chatbot

# 推前端 (commit 即触发)
git add . && git commit -m "msg" && git push origin main

# 看 Space 日志
open "https://huggingface.co/spaces/appQQQ/ai-chatbot/logs"

# 看 GH Actions
open "https://github.com/shuaiwang888/AI-Chatbot/actions"

# 验证 E2E
curl https://appQQQ-ai-chatbot.hf.space/api/v1/healthz
curl https://shuaiwang888.github.io/AI-Chatbot/ -I
```
