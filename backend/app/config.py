"""全量环境变量配置 (Pydantic Settings).

修改默认值时, 注意区分:
- "工程常量" (代码内调用方期望) → 直接写死
- "环境变量" (部署时可调) → 字段, 通过 env 覆盖
"""
from __future__ import annotations

# Monkey patch transformers to bypass torch.load safety check on old PyTorch versions (macOS x86_64)
try:
    import transformers.utils.import_utils
    transformers.utils.import_utils.check_torch_load_is_safe = lambda *args, **kwargs: None
except ImportError:
    pass

try:
    import transformers.modeling_utils
    transformers.modeling_utils.check_torch_load_is_safe = lambda *args, **kwargs: None
except ImportError:
    pass

# Force CPU device for PyTorch MPS on Intel Macs to prevent NotImplementedError
try:
    import torch
    torch.backends.mps.is_available = lambda: False
    torch.backends.mps.is_built = lambda: False
    if hasattr(torch, "mps"):
        torch.mps.is_available = lambda: False
except ImportError:
    pass

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ========== App ==========
    app_name: str = "ai-chatbot"
    app_version: str = "1.0.0"
    app_host: str = "0.0.0.0"
    app_port: int = 7860
    log_level: str = "INFO"

    # ========== LLM Provider ==========
    llm_provider: Literal["minimax", "openai", "anthropic", "qwen"] = "minimax"

    # MiniMax-M3 (OpenAI 兼容)
    minimax_api_key: SecretStr = Field(default=SecretStr(""))
    minimax_base_url: str = "https://api.MiniMax.com/v1"
    minimax_model: str = "MiniMax-M3"

    # 其他 provider 备用 (切换 llm_provider 时生效)
    openai_api_key: SecretStr = Field(default=SecretStr(""))
    anthropic_api_key: SecretStr = Field(default=SecretStr(""))
    qwen_api_key: SecretStr = Field(default=SecretStr(""))

    # CRAG evaluate 阶段 2 用的 LLM judge (可选更小/更便宜)
    llm_judge_model: str = "MiniMax-M3"

    # ========== Embedding & Reranker ==========
    embedding_model: str = "BAAI/bge-m3"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    embedding_device: Literal["cpu", "cuda", "mps"] = "cpu"
    use_fp16: bool = True

    # ========== 向量库 / ChromaDB ==========
    chroma_persist_dir: str = "./data/chroma"
    chroma_collection: str = "docs"
    enable_colbert: bool = True  # 三路融合开关; false 则仅 dense+sparse

    # ========== 持久化 (HF Dataset repo) ==========
    hf_persist_repo: str = ""  # 形如 "username/ai-chatbot-data". 留空禁用持久化
    hf_token: SecretStr = Field(default=SecretStr(""))
    persist_on_write: bool = True

    # ========== 数据目录 ==========
    data_dir: Path = Path("./data")
    upload_dir: Path = Path("./data/uploads")

    # ========== RAG / Agent ==========
    chunk_size: int = 512
    chunk_overlap: int = 64
    semantic_chunking: bool = True
    contextual_retrieval: bool = True
    retrieval_k: int = 20
    rerank_top_n: int = 5
    crag_max_iterations: int = 2
    crag_relevance_threshold: float = 0.7

    # ========== LLM 缓存 ==========
    llm_cache_enabled: bool = True
    llm_cache_size: int = 200

    # ========== 解析器 ==========
    parser_primary: Literal["docling", "marker", "mineru", "vlm", "simple", "markdown"] = "docling"
    parser_fallback: Literal["docling", "marker", "mineru", "vlm", "simple", "markdown"] = "marker"
    parser_enable_ocr: bool = True
    parser_table_structure: bool = True

    # ========== 可观测性 ==========
    langsmith_tracing: bool = False
    langchain_api_key: SecretStr = Field(default=SecretStr(""))
    langchain_project: str = "ai-chatbot"

    # ========== CORS ==========
    # ⚠️ 在线部署专属: 此项目不再支持本机本地启动.
    # 必须通过环境变量 ALLOWED_ORIGINS 显式配置线上前端域名 (GH Pages 形如
    # "https://<user>.github.io"), 否则启动时该字段为空列表, 所有跨域请求都会被拒.
    allowed_origins: list[str] = Field(
        default_factory=lambda: []
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _parse_origins(cls, v: Any) -> list[str]:
        """支持 JSON 数组字符串 或 python list."""
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                return json.loads(v)
            return [o.strip() for o in v.split(",") if o.strip()]
        if isinstance(v, list):
            return v
        raise ValueError("allowed_origins must be a list or JSON string")

    @field_validator("data_dir", "upload_dir", mode="after")
    @classmethod
    def _abs_path(cls, v: Path) -> Path:
        return Path(v).expanduser().resolve()

    # ========== 派生 ==========
    @property
    def sqlite_dir(self) -> Path:
        p = self.data_dir / "sqlite"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def chroma_dir(self) -> Path:
        p = Path(self.chroma_persist_dir).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def hf_cache_dir(self) -> Path:
        p = self.data_dir / ".cache" / "huggingface"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def sqlite_db_path(self) -> Path:
        return self.sqlite_dir / "app.db"

    @property
    def langgraph_db_path(self) -> Path:
        return self.sqlite_dir / "langgraph.db"

    @property
    def upload_path(self) -> Path:
        p = self.upload_dir
        p.mkdir(parents=True, exist_ok=True)
        return p

    def is_persist_enabled(self) -> bool:
        return bool(self.hf_persist_repo and self.hf_token.get_secret_value())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """单例 settings (避免重复读取环境变量)."""
    return Settings()


# 全局访问点
settings = get_settings()
