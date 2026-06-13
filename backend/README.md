---
title: AI Chatbot
emoji: "\U0001F916"
colorFrom: blue
colorTo: purple
sdk: docker
pinned: true
license: mit
short_description: Agentic multimodal RAG customer service (private)
---

# AI Chatbot Backend

Agentic multimodal RAG customer service backend.

- FastAPI + LangGraph (StateGraph)
- Docling (PDF/Word/Image) + BGE-M3 + ChromaDB
- MiniMax-M3 (default) / switchable to OpenAI / Anthropic / Qwen
- Persistent via HF Dataset repo (free tier disk is ephemeral)

## Endpoints

- `GET  /api/v1/healthz` — liveness
- `GET  /api/v1/readyz`  — readiness (Chroma + LLM reachable)
- `POST /api/v1/chat` — non-streaming chat
- `POST /api/v1/chat/stream` — SSE stream (astream_events v2)
- `POST /api/v1/documents/upload` — upload + ingest
- `GET  /api/v1/documents` — list
- `DELETE /api/v1/documents/{id}` — remove
- `GET  /api/v1/sessions` — list sessions
- `DELETE /api/v1/sessions/{id}` — clear session

See [PLAN.md](../PLAN.md) for full design.
