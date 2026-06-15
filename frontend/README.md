# AI Chatbot · Frontend

React 19 + Vite + TypeScript + shadcn/ui · 部署到 GitHub Pages.

> ⚠️ **本项目无 dev server / 无本地启动**。`npm run dev` / `vite preview` 都已删除。
> 所有前端代码改动通过 `git push main` → GH Actions 自动 build & deploy。

## 部署到 GitHub Pages

### 一次性配置
1. GitHub repo → Settings → Pages → Source = **GitHub Actions**
2. Settings → Secrets and variables → Actions:
   - **Secret** `VITE_API_BASE` = `https://<user>-<space>.hf.space/api/v1`
   - **Variable** `VITE_REPO_NAME` = `<repo-name>` (用于 base path)
3. 推 `main` 分支, GitHub Actions 自动 build + deploy

### 访问
- 项目页: `https://<username>.github.io/<repo-name>/`

### 自动构建原理
- `vite build` 直接产出 `dist/`
- `base: /<repo-name>/` 已硬编码, 适配项目页路径
- 跨域请求走 `VITE_API_BASE` 直连 HF Space, 免 CORS proxy

## 目录结构

```
frontend/
├── package.json              # 依赖 + 唯一脚本: build
├── vite.config.ts            # Vite + React + GH Pages base path
├── tsconfig*.json            # TS strict 模式
├── index.html
├── .env.example              # 仅参考, 实际值由 GH Actions 注入
└── src/
    ├── main.tsx              # React 19 createRoot
    ├── App.tsx               # QueryClient + HashRouter
    ├── router.tsx            # 路由表 (/chat, /documents)
    ├── env.ts                # import.meta.env 集中校验 (VITE_API_BASE 必填)
    ├── types.ts              # 与后端 schemas 对齐
    ├── styles/globals.css    # Tailwind v4 + 主题变量
    ├── lib/
    │   ├── api.ts            # fetch 客户端 (ApiError)
    │   ├── sse.ts            # SSE 解析器 (fetch + ReadableStream)
    │   └── utils.ts          # cn() / formatBytes / session id
    ├── stores/
    │   ├── chatStore.ts      # Zustand: messages + stream dispatch
    │   └── uiStore.ts        # Zustand: sidebar / theme
    ├── hooks/
    │   ├── useChatStream.ts  # SSE → chatStore 绑定
    │   └── useDocuments.ts   # TanStack Query
    └── components/
        ├── ui/               # shadcn 原语 (Button/Card/Input/Badge/ScrollArea)
        ├── chat/             # ChatArea / MessageList / MessageBubble /
        │                     # ChatInput / CitationPanel /
        │                     # AgentStepTrace / ThinkingPanel
        ├── documents/        # DocumentList / DocumentCard / UploadPanel
        └── layout/           # Sidebar / TopBar
```

## SSE 消费协议

后端用 AG-UI 兼容事件格式:

```
event: thinking
data: {"content": "用户在问财务数据..."}

event: agent_step
data: {"node": "route", "status": "running"}

event: retrieval
data: {"doc_ids": ["abc"], "count": 5, "scores": [0.92, 0.87, ...]}

event: token
data: {"content": "Q3"}

event: citation
data: {"doc_id": "abc", "page": 12, "snippet": "...", "score": 0.95}

event: done
data: {"usage": {...}, "total_ms": 1234}
```

`useChatStream` 自动把每类事件分发到 `chatStore` 相应 action, 组件订阅 store 即可。

## License

MIT
