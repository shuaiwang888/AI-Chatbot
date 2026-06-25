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
