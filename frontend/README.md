# AI Chatbot · Frontend

React 19 + Vite + TypeScript + shadcn/ui · 部署到 GitHub Pages.

## 本地开发

```bash
# 1. 安装依赖
pnpm install          # 或 npm install

# 2. 复制环境变量
cp .env.example .env
# 编辑 .env, 设置 VITE_API_BASE (生产) / VITE_DEV_API_BASE (本地 dev)

# 3. 启 dev server
pnpm dev
# → http://localhost:5173
```

Vite dev server 走 proxy, `/api/*` 自动转发到 `VITE_DEV_API_BASE` (默认 `http://localhost:7860`),
所以本地不需要处理 CORS.

## 构建

```bash
pnpm build
# → frontend/dist/  (静态资源, 直接放到任何静态托管)
```

## 部署到 GitHub Pages

### 一次性配置
1. GitHub repo → Settings → Pages → Source = **GitHub Actions**
2. Settings → Secrets and variables → Actions:
   - **Secret** `VITE_API_BASE` = `https://yourname-ai-chatbot.hf.space/api/v1`
   - **Variable** `VITE_REPO_NAME` = `ai-chatbot` (你的仓库名, 用于 base path)
3. 推 `main` 分支, GitHub Actions 自动 build + deploy

### 访问
- 用户/组织页: `https://<username>.github.io/`
- 项目页: `https://<username>.github.io/<repo-name>/`

## 目录结构

```
frontend/
├── package.json              # 依赖
├── vite.config.ts            # Vite + React + base path + dev proxy
├── tsconfig*.json            # TS strict 模式
├── index.html
├── .env.example
└── src/
    ├── main.tsx              # React 19 createRoot
    ├── App.tsx               # QueryClient + HashRouter
    ├── router.tsx            # 路由表 (/chat, /documents)
    ├── env.ts                # import.meta.env 集中校验
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
