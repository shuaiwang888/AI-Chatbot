# HuggingFace Spaces Docker image
# python:3.12-slim 是 2026-06 推荐基础镜像
FROM python:3.12-slim

# HF Spaces 元数据
LABEL org.opencontainers.image.title="ai-chatbot"
LABEL org.opencontainers.image.description="Agentic multimodal RAG customer service"
LABEL org.opencontainers.image.source="https://github.com/yourname/ai-chatbot"
LABEL org.opencontainers.image.licenses="MIT"

# 环境
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DATA_DIR=/data \
    HF_HOME=/data/.cache/huggingface \
    TRANSFORMERS_CACHE=/data/.cache/huggingface \
    TOKENIZERS_PARALLELISM=false

# 系统依赖 (Poppler for PDF, GL libs for OpenCV/PaddleOCR)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
        libgl1 \
        libglib2.0-0 \
        poppler-utils \
        curl \
    && rm -rf /var/lib/apt/lists/*

# 工作目录
WORKDIR /app

# 先复制 requirements 利用 Docker 层缓存
COPY requirements.txt .

# 安装 Python 依赖
# 单独 install FlagEmbedding 比较慢, 但因为在 requirements.txt 里只装一次
RUN pip install -r requirements.txt

# 可选: 预热模型 (避免 Space 启动超时). 如果镜像太大, 可注释掉, 运行时再下载
# RUN python -c "from FlagEmbedding import BGEM3FlagModel, FlagReranker; \
#     BGEM3FlagModel('BAAI/bge-m3', use_fp16=True); \
#     FlagReranker('BAAI/bge-reranker-v2-m3')" \
#     || echo "Model pre-warm skipped (will download on first startup)"

# 复制应用代码
COPY app ./app
COPY pyproject.toml ./pyproject.toml

# 数据目录 (HF Space 持久卷挂载点)
RUN mkdir -p /data/chroma /data/sqlite /data/uploads /data/.cache/huggingface

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:7860/api/v1/healthz || exit 1

# 暴露端口 (HF Spaces 约定 7860)
EXPOSE 7860

# 启动命令
# --workers 1: 避免 BGE-M3 / ChromaDB 在多 worker 下重复加载模型
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
