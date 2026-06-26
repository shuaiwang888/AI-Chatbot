# AGENTS.md — 私人 Agent 智能客服 知识库

> 写给"接手这个项目的人 / agent", 记录**踩过的所有坑**与**已建立的方案**.
> 包含: 项目架构、部署链路、本 session 修过的 bug、未解决的限制.

---

## 1. 项目一句话

**HF Spaces (FastAPI + LangGraph + ChromaDB) + GH Pages (React 19) + MiniMax-M3 LLM 的私人 Agent 智能客服.**

- 单用户, 无鉴权
- RAG + 工具调用 + 多轮对话
- 文档摄入 (PDF / Word / PPT / Excel / **Markdown** / 图片) → 解析 → BGE-M3 → Chroma
- HF Dataset 持久化 (冷启动从 Dataset restore 到 `/data`)

---

## 2. 仓库结构 (关键目录)

```
.
├── AGENTS.md                   ← 你正在读
├── backend/                    ← HF Space 根 (HF 期望平铺结构)
│   ├── Dockerfile
│   ├── README.md               ← HF 元数据头 (sdk: docker, pinned: true)
│   ├── requirements.txt
│   └── app/
│       ├── main.py             ← FastAPI 入口 (port 7860)
│       ├── config.py           ← pydantic-settings, 全部 env 变量
│       ├── api/                ← documents / chat / sessions / health
│       ├── services/
│       │   ├── ingestion.py    ← 摄入管线 (parse → chunk → embed → upsert)
│       │   ├── persist.py      ← HF Dataset 持久化 (push / restore)
│       │   └── parsers/        ← docling / simple / markdown
│       ├── agents/             ← LangGraph StateGraph
│       ├── llm/                ← LLM 抽象 + minimax
│       └── core/               ← paths / errors / logging
├── frontend/                   ← React 19 + Vite + Tailwind v4
│   ├── src/
│   │   ├── components/
│   │   │   ├── chat/           ← ChatArea / MessageList / ChatInput
│   │   │   ├── documents/      ← DocumentList / UploadPanel
│   │   │   ├── sessions/       ← SessionHistoryPanel / SessionListItem
│   │   │   ├── layout/         ← Sidebar / TopBar
│   │   │   └── effects/        ← LightRays (WebGL ogl 背景)
│   │   ├── stores/             ← Zustand (chat / ui)
│   │   ├── hooks/              ← useChatStream / useDocuments / useSessions
│   │   └── styles/globals.css  ← 主题色 (深紫蓝)
│   └── vite.config.ts          ← base: '/AI-Chatbot/'
├── scripts/
│   ├── deploy-via-api.py       ← 全量推 backend/ 到 Space repo (走 HF HTTP API)
│   ├── deploy-backend-fix.sh   ← tar 推 backend/ 到 Space
│   └── push-single-file.py     ← 单文件推 Space repo (mirror 卡死时用)
├── docs/
│   ├── architecture.md
│   └── deployment.md
└── .github/workflows/
    └── deploy-frontend.yml     ← push → npm build → GH Pages
```

---

## 3. 部署链路 (两套, 互不影响)

```
┌─────────────────────────────────────────────┐
│            推 GitHub (origin/main)          │
│  - 触发 .github/workflows/deploy-frontend   │  →  GH Pages (5 min)
│  - HF git mirror 自动同步 Space repo        │  →  HF Space rebuild (5-15 min)
└─────────────────────────────────────────────┘
        ↑                    ↑
        │ 失败时备用:          │ mirror 卡死时备用:
   git push origin      python3 scripts/push-single-file.py
```

**两个产物**:
- **GH Pages** → `https://<user>.github.io/AI-Chatbot/`
- **HF Space** → `https://<user>-<space>.hf.space/api/v1/...`

---

## 4. 本 session 踩过的所有坑 + 修复

> 严格按"问题 → 根因 → 修复 → 验证"格式, 方便以后排查时对照.

### 4.1 [后端] RAG 检索全部返回 "未在知识库中找到相关信息"

**症状**: 上传了 PDF, 问问题时永远返回 "未在知识库中找到相关信息".

**根因**:
1. **ChromaDB 持久化路径不一致** — `Dockerfile` 没设 `CHROMA_PERSIST_DIR` 环境变量, Chroma 默认写到 `/app/.chroma` 或 working dir. 重启后数据丢失或路径解析失败.
2. **`/chat` 没触发 `schedule_push`** — chat.py 写入消息后没调 `schedule_push`, 持久化层永远不 push 新数据到 HF Dataset.
3. **restore_from_hf 漏了 `colbert/`** — `persist.py` 的 `target_subdirs` 列表少了 `colbert/`, cold_restore 时 BGE-M3 colbert 向量缺失 → 检索时该路全 0 分, 触发兜底分支 → 看起来像"全空".

**修复**:
- `backend/Dockerfile` 加 `ENV CHROMA_PERSIST_DIR=/data/chroma` + `UPLOAD_DIR=/data/uploads` + `SQLITE_DIR=/data/sqlite`
- `backend/app/api/chat.py` 在写完消息后 `await schedule_push()` (用 try/except 包住, push 失败不影响 chat)
- `backend/app/services/persist.py` `target_subdirs = ["chroma", "colbert", "sqlite", "uploads"]`

**验证**: 上传 PDF → chat 问问题 → 拿到引用源; Space 重启后从 Dataset 恢复 → /readyz `persist.last_verify.has_colbert = true`.

---

### 4.2 [前端] 点击历史对话的某条记录没有反应, 或者出来很慢

**症状**: 右栏点历史 session, 主区不切 / 切得很慢 (1-3 秒空白).

**根因**: 用 `useEffect` 桥接 `currentDetail.data → chatStore.messages`, 但 React 18 不会因为 `data` 引用变化重跑 effect (deps 只看 `sessionId`), 等于 listener 死了.

**修复** (frontend/src/hooks/useSessions.ts):
- 新增 `useSelectSession()` mutation
- 点击时立即 `setSessionId(id) + loadSessionMessages([]) + setLoadingSession(id)` (视觉反馈: spinner)
- `selectMut.mutate(id, { onSuccess: detail => loadSessionMessages(detail.messages) })`
- 加 race 保护: onSuccess 时检查 `useChatStore.getState().sessionId === id` 仍然成立才写 store

**验证**: 连续点 5 个不同 session, 每个立即切, 不残留上个 session 的消息.

---

### 4.3 [前端] 在新建新对话时, 马上出现加载对话历史

**症状**: 点 "+" 新建, 立刻显示 "加载对话历史..." spinner 一闪而过.

**根因**: `MessageList` 用 `!!sessionId` 判断 loading, 但 `handleNew()` 调 `setSessionId(newId)` 也会让 `!!sessionId` 从 false 变 true → 触发了 loading 分支.

**修复** (frontend/src/stores/chatStore.ts + MessageList):
- 新增 `loadingSessionId: string | null` 字段
- 只有 "点击历史" 才设这个 flag, "新建" 不设
- MessageList 改用 `!!loadingSessionId` 判断 loading

**验证**: 新建对话无闪烁, 历史点击仍正常显示 spinner.

---

### 4.4 [后端] HF Space rebuild 后, 文档看不见, 查询不到, 历史丢失

**症状**: merge 代码后, 之前的 PDF 列表消失, 聊天也拿不到引用.

**根因**: persist restore 不全 + 路径不一致 (见 4.1, 三个问题叠加).

**修复**: 同 4.1, 加上新增的 admin 端点做手动补救:

```python
# backend/app/api/admin.py
@router.post("/push")
async def trigger_push():
    # 强制清 stuck flag + 跑一次 push
```

**验证**: rebuild 后调用 `POST /api/v1/admin/push` → Dataset 拿到完整 4 个目录 → 文档/历史都恢复.

---

### 4.5 [前端] 第一次打开项目, 期望自动新建对话, 但显示了最近的历史对话

**症状**: 刷新页面后, 自动进入最近的那条 session, 期望是新建.

**根因**: `ChatArea` mount 时从 localStorage 读上次的 `sessionId` 写回 store, 等于 "刷新 = 自动恢复上次".

**修复** (frontend/src/components/sessions/SessionHistoryPanel.tsx + ChatArea.tsx):
- ChatArea 删掉 localStorage fallback, store 初始就是空
- SessionHistoryPanel mount 时如果 `sessionId === ''` → 调 `handleNew()` 自动建新对话
- 用 `useRef` 防 React 18 strict mode 双重 mount 导致的两次 create

**验证**: 第一次打开 → 自动建 1 个空 session; 之后刷新 → 看到刚才那个空 session (不重复建).

---

### 4.6 [前端] 每次刷新页面都新建一堆 "Untitled chat"

**症状**: 多次刷新, 右栏堆了一堆空 session (都是 0 消息).

**根因**: SessionHistoryPanel 的 auto-create effect 只看 `sessionId === ''`, 不看后端 sessions 列表里有没有已存在的空 session.

**修复** (frontend/src/components/sessions/SessionHistoryPanel.tsx):
```ts
// 自动进入对话前先查列表
const list = sortSessions(sessionsQ.data?.sessions);
const newest = list[0];
if (newest && newest.message_count === 0) {
  // 重用最新空 session, 不新建
  setSessionId(newest.id);
  loadSessionMessages([]);
  return;
}
handleNew();  // 否则才新建
```

**验证**: 多次刷新 → 永远只有 1 个空 Untitled; 在空 session 发消息后再刷新 → 新建 (因为最新一条有消息).

---

### 4.7 [前端] 背景效果: Ferrofluid 替换为 LightRays

**症状**: Ferrofluid (流体磁性凸起) 视觉上跟深色主题不太搭.

**根因**: 设计选择.

**修复** (frontend/src/components/effects/ + ChatArea.tsx + globals.css):
- 删除 `Ferrofluid.tsx` + `Ferrofluid.css`
- 新建 `LightRays.tsx` (ogl WebGL, 默认导出) + `LightRays.css`
- ChatArea 改用 LightRays, 参数: `raysOrigin=top-center, raysColor=#8b9eff, mix-blend-screen, opacity=0.6`
- globals.css 改为深紫蓝主题 (`:root` 直接套深色, 不再走 system → light 默认)
  - `--background: hsl(232 35% 11%)` (≈ #0f0f23)
  - `--card: hsl(232 30% 14%)`
  - `--primary: hsl(217 91% 60%)` (AI 气泡蓝)
- TopBar 加 Sparkles 图标 toggle 按钮, 控制 `uiStore.showFluidBackground` (持久化)

**验证**: 硬刷新 GH Pages → 顶部中央散出淡蓝紫光束, 鼠标移动时偏转; 顶栏 ⚡ 可关闭.

---

### 4.8 [后端] 新增 Markdown (.md / .markdown) 文件支持

**症状**: 需求 — 允许上传 .md 文件并被 RAG 检索.

**根因**: 后端 MIME 嗅探 + parser 注册都没有 .md 入口.

**修复** (4 个文件):
- **新建** `backend/app/services/parsers/markdown_parser.py` — 零依赖, `read_text(encoding='utf-8', errors='replace')` 全文 → `ParsedDocument(markdown=全文, pages=[单页], meta=...)`. 内部 5MB 保险, 防 OOM.
- `backend/app/services/parsers/__init__.py`:
  - 注册到 `_REGISTRY["markdown"]`
  - **`get_parser_chain()` 末尾始终追加 markdown parser** — 这样生产配置 `[docling, simple]` 不需要改 env, 上传 .md 也能被接管
- `backend/app/services/ingestion.py` `_sniff_mime` 加 `.md`/`.markdown` → `text/markdown`
- `backend/app/config.py` `parser_primary/fallback` Literal 加 `'simple'` 和 `'markdown'` (顺带修了 pre-existing bug: 原 Literal 漏了 `'simple'`, 但 .env 里 `PARSER_FALLBACK=simple` 一直在用)
- `frontend/src/components/documents/UploadPanel.tsx`: `ALLOWED` + `accept` + 提示文案都加 `.md`/`.markdown`

**设计亮点**:
- Markdown 文件本身就是 LLM 友好的纯文本 + 标记, 不需要 OCR / 表格识别
- `chunking._split_by_headings` 按 H1/H2/H3 拆 section, 天然适配 MD
- 5MB 保险防 OOM (上传入口 50MB cap 之外)

**验证**: 上传 `/tmp/test.md` → `{"doc_id":"...","chunk_count":4,"status":"ready"}` → 聊天能引用.

---

### 4.9 [部署] HF git mirror 同步卡死 (>2 小时)

**症状**: push GitHub 后, HF Space 没 rebuild, 一直跑旧 commit. `/readyz` `version` 字段不变.

**诊断**:
```bash
python3 -c "from huggingface_hub import HfApi; print(HfApi().repo_info('appQQQ/ai-chatbot', repo_type='space').last_modified)"
# 卡死前: 2026-06-23 06:29:10+00:00  (3 天前)
# 我们手动推后: 2026-06-25 06:11:31+00:00
```

**根因**: HF 的 GitHub → Space repo 镜像同步服务异常. Restart 没用 (Space 拉的还是旧 commit).

**解决**:
- 用 `huggingface_hub.upload_file` 走 HF **HTTP API** 直接推 Space repo, 绕开 git 协议
- 写了一个临时脚本 `scripts/push-single-file.py` (token 走 env, 单文件推)
- 推完后 HF Space 几秒内自动 rebuild

**注意**:
- 不能用 `HF_TOKEN=xxx python3 ...` 形式 (token 进 shell history), 改成 `export HF_TOKEN=xxx` 然后再跑
- push 完一定要轮询 `/readyz` 等 rebuild 完, 看到行为正常才算成功 (version 字段可能没改, 看实际行为)

**教训**:
- HF mirror 经常抽风, 任何"push 完看不到效果"先看 `repo_info().last_modified` 时间戳
- 如果时间戳没动, 别等, 直接 `upload_file` 推
- `deploy-via-api.py` 是已建立的备选方案, 但走全量 push, mirror 健康时优先用 git

---

### 4.10 [后端] ingest_failed 后, /data/uploads/ 累积孤儿文件

**症状**: 上传不识别的格式, /readyz `persist.last_error`: `"push: ValueError: Provided path: '/data/uploads/xxx/bad.xyz' is not a file on the local file system"`.

**根因**: `_ingest_locked` 在 `_save_upload` (line 65-78) 把文件写到 `/data/uploads/{doc_id}/{filename}`, 后续 parse / chunk / embed 失败抛异常, 但**没有任何清理**. 文件残留在磁盘, persist 推送时扫到这些孤儿, 报 "is not a file".

**修复** (backend/app/services/ingestion.py `_ingest_locked` 的 except 分支):
```python
except Exception as e:
    # ⚡ 清理孤儿文件: 解析/分块/向量化失败时, /data/uploads/{doc_id}/{filename}
    # 已经写盘. 不删会累加, 而且触发 persist push 的 "is not a file" 错误.
    try:
        file_path.unlink(missing_ok=True)
    except Exception as cleanup_err:
        logger.warning("Failed to cleanup orphan file %s: %s", file_path, cleanup_err)
    # SQLite 标 failed 保留审计
    try:
        db.doc_update_status(doc_id, "failed", error=str(e)[:500])
    except Exception:
        pass
    raise IngestionFailedError(...)
```

**注意**:
- SHA256 重复分支 (line 116-125) 走 `if existing is not None`, 已经有自己的 unlink, 不进 try/except, 不影响.
- 不删 SQLite row, 保留 "failed" 状态方便审计.

**验证**: 上传 `.xyz` 触发 ingest_failed → `/readyz` `persist.last_error = none` (不再有 "is not a file").

---

### 4.11 [后端+前端] 删除文档/会话后, 后端"假删除" + HF Dataset 远端残留

**症状**: 前端点删除按钮 → 列表消失 → 用户以为删干净. 实际:
1. 本地 ChromaDB 删失败时只 warn, SQLite 行已删 → 用户看到虚假"删除成功" toast
2. 本地 SQLite 删干净, 但 HF Dataset 远端 `chroma/*` / `sqlite/*` / `uploads/*` **永远保留**
3. 下次冷启动 `snapshot_download` 把幽灵拉回 → "明明删了, 数据又冒出来"
4. session 删除连 `schedule_push` 都没调, 远端 `langgraph.db` 完全不更新
5. 失败时前端只转圈, 用户看不到原因

**根因 (5 个独立 bug)**:

| # | 位置 | 根因 |
|---|---|---|
| A | [backend/app/services/persist.py:155-163](backend/app/services/persist.py#L155-L163) | `upload_folder` 默认行为是 *"Files with the same name already present will be overwritten. **Others will be left untouched.**"*  — 必须显式传 `delete_patterns` 才会清远端. 我们的代码**没传** |
| B | [backend/app/api/sessions.py:67-79](backend/app/api/sessions.py#L67-L79) (旧版) | 整段没有 `schedule_push()`, 远端 sqlite 永久不更新 |
| C | [backend/app/api/sessions.py:70-78](backend/app/api/sessions.py#L70-L78) (旧版) | 先 `db.session_delete` 后 `adelete_thread`, checkpoint 失败仅 warn, 元数据已删 → "删了但聊天记录还在" |
| D | [backend/app/services/ingestion.py:306-335](backend/app/services/ingestion.py#L306-L335) (旧版) | `delete_document` 顺序是 SQLite → ChromaDB(warn) → uploads, ChromaDB 失败仅 warn, 但前端 toast 仍弹 "已删除" → 虚假成功. `schedule_push` 走 5s debounce, 期间崩了留幽灵 |
| E | [frontend/src/hooks/useDocuments.ts:47-55](frontend/src/hooks/useDocuments.ts#L47-L55) / [useSessions.ts:65-74](frontend/src/hooks/useSessions.ts#L65-L74) (旧版) | `useMutation` 只有 `onSuccess`, 没有 `onError`, 失败时只 `isPending` 转圈, 用户看不到原因 |

**修复 (一次性 5 处, 见 commit `2184b13`)**:

**A. persist.py** — `upload_folder` 加 `delete_patterns`:
```python
upload_folder(
    folder_path=str(local_root),
    repo_id=repo_id,
    repo_type="dataset",
    token=token,
    commit_message=f"sync {started:.0f}",
    ignore_patterns=[".cache/*", "*.tmp", "*.lock"],
    delete_patterns=[
        "chroma/*",
        "colbert/*",
        "sqlite/*",
        "uploads/*",
    ],
)
```
⚠️ 需 `huggingface_hub>=0.20` (我们 0.30 满足). 用通配而不是 `delete_patterns="*"` 避免误伤 `.gitattributes` / 模型缓存.

**B+C. sessions.py** — DELETE 端点重写:
```python
# 1) LangGraph checkpoint 先删 (失败抛 500, 元数据保留, 用户能重试)
try:
    graph = await get_compiled_graph()
    checkpointer = graph.checkpointer
    if hasattr(checkpointer, "adelete_thread"):
        await checkpointer.adelete_thread(session_id)
    else:
        raise RuntimeError("Checkpointer missing adelete_thread; langgraph too old")
except Exception as e:
    raise HTTPException(500, detail=f"Checkpoint delete failed: {e}") from e

# 2) SQLite session 行 (FK CASCADE 自动删 messages)
db.session_delete(session_id)

# 3) 同步推 HF Dataset (与 ingestion 一致, 不走 debounce)
push_ok = await push_to_hf()
if not push_ok:
    logger.warning("Delete ok locally but persist push failed for session %s", session_id)
```

**D. ingestion.py** — `delete_document` 顺序调整 + 同步 push:
```python
# 1) ChromaDB / sparse 旁路先删 (失败抛错, 阻止后续破坏性操作)
from app.services.vector_store import delete_by_doc
delete_by_doc(doc_id)  # 失败抛错, 不再 warn

# 2) SQLite chunks + document
db.chunk_delete_by_doc(doc_id)
db.doc_delete(doc_id)

# 3) uploads/ 原文件
if doc.get("sha256"):
    up_dir = upload_dir() / doc_id
    if up_dir.exists():
        shutil.rmtree(up_dir, ignore_errors=True)

# 4) 同步推 HF Dataset (A 改良版: 阻塞 + verify)
push_ok = await push_to_hf()
```
关键点: **ChromaDB 删除失败必须立即抛错**, 不能 warn. 因为 SQLite 元数据已删的情况下, warn 等于"用户看到虚假成功, 实际残留".

**E. 前端** — 装 sonner, hooks 加 onError, App.tsx 加 Toaster:
```bash
npm install sonner
```
```ts
// useDocuments.ts
import { toast } from 'sonner';
import { ApiError } from '@/lib/api';

export function useDeleteDocument() {
  return useMutation({
    mutationFn: (docId) => documentsApi.delete(docId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEY });
      toast.success('文档已删除');
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : String(err);
      toast.error(`删除失败: ${msg}`);
    },
  });
}
```
```tsx
// App.tsx
import { Toaster } from 'sonner';
<Toaster theme="dark" position="bottom-right" richColors closeButton />
```

**验证**:
- ✓ TypeScript `tsc -b --noEmit` 0 错误
- ✓ Python `ast.parse` 0 错误
- ✓ Vite build 成功 (806 kB main, gzip 245 kB)
- ✓ 对抗性 7 场景全绿 (含 blocker 1 + nice-to-have 1 二次修复)
- ⏳ **生产验证** (待 HF Space rebuild): 删一个 doc → `curl https://huggingface.co/api/datasets/appQQQ/ai-chatbot-data/tree/main` 看到 `chroma/` 下该 doc 的 `.bin` / `sqlite/chunks` 表里该 doc_id 行 / `uploads/<doc_id>/` 目录同步消失

**已部署**: commit `2184b13` 已推 GitHub (`main`). 后端部署到 HF Space 状态待用户确认 (见 §3 部署链路).

---

### 4.12 [后端+前端] Chat 首字慢 + 流式渲染掉帧 — 5 项高 ROI 优化

**症状**: 用户输入问句后, agent 反应慢 (TTFT ~4-6s, p95 ~8-12s), 长回答末段"打字掉帧".

**调研方法**: 跑一个 explore 子代理, 调查从"前端 dispatch"到"首字可见"全链路的每环节耗时, 引用具体 file_path:line.

**找到的瓶颈 (按绝对延迟值排序)**:

| 环节 | 位置 | 耗时 | 是否优化 |
|---|---|---|---|
| `_auto_title` 隐藏同步 | `chat.py:175-177` | 0 (实际是字符串函数) | ✅ #2 (防御性) |
| `route_node` LLM | `nodes.py:78-112` | 0.5-1.5s | ✅ #3 (合并) |
| `query_rewrite_node` LLM | `nodes.py:116-157` | 0.5-1.5s | ✅ #3 (合并) |
| BGE-M3 encode query | `embedding.py:113-120` | 0.1-0.4s | ❌ CPU fp32 限制 |
| `hybrid_query` ColBERT 30 .npy | `vector_store.py:309-333` | 0.3-1.5s | ✅ #1 (关) |
| BGE-reranker over 20 | `reranker.py:62-87` | 0.3-1.5s | ❌ CPU 限制 |
| 前端每 token 全量重渲 | `chatStore.ts:149-203` + `MessageBubble.tsx:19` + `MessageList.tsx:56-88` | 累积 0.1-0.5s | ✅ #4 + #5 |

**修复 (commit `53abc24`)**:

**#1 关 ColBERT** — [backend/app/config.py:81](backend/app/config.py#L81):
```python
# ⚡ A 改良版: 默认关闭 ColBERT. 三路融合每次查询多扫 30 个 .npy 文件 + matmul,
# 0.3-1.5s 开销. 召回率轻微降, reranker 兜底.
enable_colbert: bool = False
```
⚠️ **改默认值, 不改 .env**: `.env` 被 `.gitignore` 排除, HF Space 读不到. 改 `config.py` 默认值才生效. 想恢复设 `ENABLE_COLBERT=true` 环境变量.

**#2 _auto_title 后台化** — [backend/app/api/chat.py:178-198](backend/app/api/chat.py#L178-L198):
```python
# 持引用防 GC
_deferred_tasks: set[asyncio.Task] = set()

# 首次消息: 先空 title 写一行占位, 后台异步算 title 后再 upsert 更新
async def _deferred_title() -> None:
    try:
        from app.api.sessions import _auto_title
        title = _auto_title(req.message)
        db.session_upsert(req.session_id, title=title)
    except Exception as e:
        logger.warning("Deferred auto_title failed: %s", e)

task = asyncio.create_task(_deferred_title())
_deferred_tasks.add(task)
task.add_done_callback(_deferred_tasks.discard)
```
**注**: 调研子代理误判 `_auto_title` 是 LLM 调用. 实际 `sessions.py:20-27` 是纯字符串截断. 真实节省 <1ms, 仅作防御性编程.

**#3 合并 route + query_rewrite** — [backend/app/agents/prompts.py](backend/app/agents/prompts.py) + [nodes.py:78-167](backend/app/agents/nodes.py#L78-L167) + [graph.py](backend/app/agents/graph.py):
```python
# 新 prompts.py
ROUTE_AND_REWRITE_PROMPT = """你是 query 路由器 + 改写器. 单次输出三件事:
1. "route": "direct" | "retrieve" | "multi_step"
2. "query": 改写后的检索串 (direct 原样)
3. "steps": 子问题列表 (仅 multi_step 填 2-4 个)

仅输出一个 JSON: {{"route": "...", "query": "...", "steps": []}}
"""

# nodes.py: route_node 一次 LLM 调用同时拿三个字段
async def route_node(state):
    # ... 启发式快路 (短问候跳过 LLM)
    resp = await llm.chat(messages=[...ROUTE_AND_REWRITE_PROMPT, query], ...)
    return {"route_decision": ..., "query_rewritten": ..., "plan": [...]}

# graph.py: 删 query_rewrite 节点, route 直接接 retrieve
g.add_edge(START, "route")
g.add_conditional_edges("route", _after_route, {END: END, "retrieve": "retrieve"})
g.add_edge("retrieve", "rerank")
```
旧 `query_rewrite_node` 保留为 deprecated fallback (不再被 graph 调用).

**#4 rAF 帧合并** — [frontend/src/stores/chatStore.ts](frontend/src/stores/chatStore.ts):
```ts
// 模块级 buffer (跨 token 累积)
const _tokenBuf: string[] = [];
let _rafScheduled: number | null = null;
const _rafImpl = typeof requestAnimationFrame === 'function'
  ? requestAnimationFrame
  : ((cb) => setTimeout(cb, 16));  // SSR 兜底

function _flushTokenBuffer() {
  if (_rafScheduled !== null) { _cancelRaf(_rafScheduled); _rafScheduled = null; }
  _tokenBuf.length = 0;
}

appendToken: (content) => {
  _tokenBuf.push(content);
  if (_rafScheduled !== null) return;
  _rafScheduled = _rafImpl(() => {
    _rafScheduled = null;
    const batched = _tokenBuf.join('');
    _tokenBuf.length = 0;
    set((s) => ({ messages: s.messages.map(...) }));  // 一次性 set
  });
}

// 兜底: 流结束必须 flush, 防止最后一帧 token 没渲
finishAssistant: () => { _flushTokenBuffer(); set(...); }
failAssistant: (err) => { _flushTokenBuffer(); set(...); }
reset: () => { _flushTokenBuffer(); set(...); }
loadSessionMessages: (msgs) => { _flushTokenBuffer(); set(...); }
```

**#5 React.memo + Virtuoso computeItemKey** — [MessageBubble.tsx](frontend/src/components/chat/MessageBubble.tsx) + [MessageList.tsx:56-60](frontend/src/components/chat/MessageList.tsx#L56-L60):
```tsx
// MessageBubble.tsx
function MessageBubbleInner({ message }: { message: ChatMessage }) { ... }
export const MessageBubble = memo(MessageBubbleInner);  // 浅比较 props

// MessageList.tsx
<Virtuoso
  data={messages}
  computeItemKey={(_, msg) => msg.id}  // 稳定 id 跟踪 row, 避免重建引用
  itemContent={(_, msg) => <MessageBubble message={msg} />}
/>
```

**未优化的 (HF free tier 限制, 收益 > 改动成本比不够)**:
- BGE-M3 + reranker CPU fp32: HF free tier 没 GPU, fp16 自动降级 fp32. 升级到 GPU Space 才能根治
- 模型预下载 (Dockerfile 注释掉): 容器首次启动慢, 但跟"日常问答慢"无关
- 同步 sqlite (`db.py:10` 没 aiosqlite): 并发下会阻塞 event loop, 单请求影响小

**验证**:
- ✓ TypeScript `tsc -b --noEmit` 0 错误
- ✓ Python `ast.parse` 0 错误
- ✓ Vite build 成功 (806 kB → 245 kB gzip)
- ⏳ **生产验证** (待 HF Space rebuild): 提问 → 观察 TTFT 从 ~4-6s 降到 ~1.5-2.5s; 长回答末段不再掉帧

**已部署**: commit `53abc24` 推 GitHub + 5 后端文件 (`config.py` / `chat.py` / `nodes.py` / `graph.py` / `prompts.py`) 推 HF Space (Space rebuild 5-10 min).

---

### 4.12.1 [前端] rAF flush bug — 助手消息永远 "(无回答)"

**症状**: 4.12 部署后用户截图反馈: 助手气泡永远显示 "(无回答)", 但 agent trace 正常 (命中 N chunk, 来自 M 文档, 100% 完成, 引用源也正常). 重启浏览器 / 换问题都一样.

**根因**: 4.12 #4 rAF 重构时, `_flushTokenBuffer` 函数 (模块顶层) 只清空 buffer 不应用 tokens:
```ts
// ❌ 错误实现 — 只清不应用
function _flushTokenBuffer() {
  if (_rafScheduled !== null) { _cancelRaf(_rafScheduled); _rafScheduled = null; }
  _tokenBuf.length = 0;  // 末批 token 静默丢失!
}
```

`finishAssistant` (SSE 'done' 触发) 调用 flush 试图"兜底"最后一帧 token, 但因为 flush 不调 set, 末批 token 永久丢失 → assistant message.content 永远 `""` → `MessageBubble.tsx:55-68` 渲染 `_(无回答)_`.

**修复** (commit `99e6c63`): 重构为闭包内 3 个函数, 解决"flush 必须能 set"的问题:
```ts
// 闭包内, 能直接调 set/get
function _applyTokenBatch(batched: string) {
  if (!batched) return;
  set((s) => ({ messages: s.messages.map((m) => { ... 剥离 think, 累加 content ... }) }));
}
function _flushTokenBufferNow() {
  if (_rafScheduled !== null) { _cancelRaf(_rafScheduled); _rafScheduled = null; }
  if (_tokenBuf.length === 0) return;
  const batched = _tokenBuf.join('');
  _tokenBuf.length = 0;
  _applyTokenBatch(batched);  // ✅ 真的应用
}
function _clearTokenBuffer() {  // 单纯清 (切 session / reset 时用, 不需要应用)
  if (_rafScheduled !== null) { _cancelRaf(_rafScheduled); _rafScheduled = null; }
  _tokenBuf.length = 0;
}
```

**调用约定 (重要!)**:
- `finishAssistant` / `failAssistant` → `_flushTokenBufferNow()` (必须应用最后一帧)
- `loadSessionMessages` / `reset` → `_clearTokenBuffer()` (要清的是错的 state, 不能应用)
- `appendToken` 内 rAF 触发 → `_applyTokenBatch(batched)` (直接调, 不走 flush)

**教训**:
- 性能优化**不能破坏正确性**. 重构时只想到"清 buffer"忘了"应用 buffer"是典型错误.
- 模块顶层函数 (如 `_flushTokenBuffer`) 无法 set state, 应放进 create() 闭包内.
- 任何 flush 类操作都要明确: **应用** vs **丢弃**. 这是两个不同的语义, 不能用同一个函数.

**验证**:
- ✓ TypeScript tsc -b --noEmit 0 错
- ✓ Vite build 成功
- ⏳ **生产验证**: GitHub 已推, GH Pages 部署后提问, 助手消息应正常显示

**已部署**: commit `99e6c63` 推 GitHub (`main`). 等 GH Pages 部署即可生效 (后端未变, 不需 HF rebuild).

---

## 5. 已建立的工具脚本 (遇到问题先看这里)

| 脚本 | 用途 | 何时用 |
|---|---|---|
| `scripts/deploy-via-api.py` | 全量推 `backend/` 到 Space repo (单次 `upload_folder`, 绕开 git mirror) | mirror 卡死, 想推全量 |
| `scripts/deploy-backend-fix.sh` | tar + scp 推 backend (旧脚本) | 已弃用, 别用 |
| `scripts/push-single-file.py` | **单文件**推 Space repo (token 走 env) | mirror 卡死, 只想改 1-2 个文件 |
| `scripts/deploy-now.sh` | 老脚本 | 已弃用 |
| `scripts/deploy-to-hf-space.sh` | 老脚本 | 已弃用 |

**用法**:
```bash
# 单文件推 (推荐 mirror 卡时用)
export HF_TOKEN=hf_xxxxxx
python3 scripts/push-single-file.py <local_relpath> <path_in_repo> [commit_msg]
# 例: 推 backend/app/services/ingestion.py 修复
python3 scripts/push-single-file.py backend/app/services/ingestion.py app/services/ingestion.py "fix: cleanup orphan file"

# 全量推
export HF_TOKEN=hf_xxxxxx
python3 scripts/deploy-via-api.py
```

---

## 6. 安全 / 密钥管理 (⚠️ 重要)

**所有 token / secret 必须走环境变量, 绝不入仓:**

- `HF_TOKEN` — 写权限 HF token, 推 Space / Dataset 用
- `backend/.env` — 在 `.gitignore` 里, 不入仓
- HF Space 端: Settings → Secrets 设 `HF_TOKEN`, `MINIMAX_API_KEY` 等
- GH Actions 端: Settings → Secrets → Actions 设 `VITE_API_BASE` 等
- 部署时绝对不要 `echo $HF_TOKEN > file` 或粘到 chat 记录

**本地调试**:
```bash
# 写到 .env (gitignored)
echo "HF_TOKEN=hf_xxx" >> backend/.env

# 临时一次性
export HF_TOKEN=hf_xxx  # 只在当前 shell 进程有效
unset HF_TOKEN           # 用完清掉
```

---

## 7. 调试 checklist (出问题时按这个走)

### 前端看不到改动
1. 硬刷新 (Ctrl+Shift+R) — 清 GH Pages CDN 缓存
2. `curl -s https://<user>.github.io/AI-Chatbot/ | grep -oE 'index-[A-Za-z0-9_-]+\.js'` — 确认 bundle hash 更新
3. 如果还是旧的 → 看 GH Actions 跑成功没

### 后端看不到改动
1. `curl https://<space>.hf.space/api/v1/readyz` → 看 `version` 字段
2. 如果 version 不对 → `python3 -c "from huggingface_hub import HfApi; print(HfApi().repo_info('<space>').last_modified)"` → 看 Space repo 真的更新了没
3. 如果 repo time 卡住 → mirror 卡, 用 `push-single-file.py` 推
4. 如果 repo time 动了但 version 不对 → Space rebuild 没完, 等 5-10 分钟再试

### 上传失败
1. 看后端日志 (HF Space → Logs 标签)
2. 看 `/readyz` `persist.last_error` 字段
3. 看 SQLite `documents` 表 status 字段 (`failed` 有 error 详情)
4. 看 `/data/uploads/` 有没有累积孤儿文件 (应该没有, 见 4.10)

### Chroma 检索不到
1. `/readyz` `chroma: true`?
2. `persist.last_verify.has_chroma` + `has_colbert` 都 true?
3. 文档 status = "ready" + chunk_count > 0?
4. 试问个明显在文档里的关键词

---

## 8. 仍未解决 / 已知限制

| 项 | 描述 | 建议处理 |
|---|---|---|
| HF git mirror 不稳定 | push 完偶尔不自动 rebuild, 需手动推 | 已有 workaround (push-single-file.py); 可考虑把 deploy 自动化加到 GH Actions |
| 没 light mode toggle | 当前 `:root` 直接是深紫蓝, 没法切回 light | 加 toggle: `uiStore.theme` 已有, 补上 `document.documentElement.classList.toggle('dark')` 即可 |
| 单用户, 无鉴权 | CORS 任何人能调 | 项目定位是个人用, 暂不处理 |
| `_push_chroma_fallback` | 用 upload_file 单文件推, 当 upload_folder 撞 LFS 限速时用 | 已就绪, 不需修 |
| `marker` parser 引用但未注册 | Literal 里写了 marker, _REGISTRY 没注册 | 不影响 (生产用 docling + simple), 但代码上是个小坑 |
| `feishu/lark 文档` 摄入 | docling 应该能解析, 没单独测试 | 按需扩展 |

---

## 9. 相关文档

- [docs/architecture.md](docs/architecture.md) — 架构总览
- [docs/deployment.md](docs/deployment.md) — 部署细节
- [backend/README.md](backend/README.md) — HF Space 元数据

---

## 10. 修改 AGENTS.md 的规则

1. **每修一个 bug, 就在第 4 节加一条** (症状 → 根因 → 修复 → 验证)
2. **新工具脚本在第 5 节登记**
3. **新限制 / 已知问题在第 8 节登记**
4. **不要写代码到 AGENTS.md** — 只写位置引用, 例如 "见 `backend/app/services/ingestion.py:285-294`"
5. **commit 时在 message 末尾加 `docs: update AGENTS.md`**

---

> 最后更新: 本 session (2026-06-25)
> 维护者: shuaiwang
