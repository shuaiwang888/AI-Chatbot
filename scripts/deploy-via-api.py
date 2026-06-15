#!/usr/bin/env python3
"""用 huggingface_hub API 推 backend/ 到 HF Space, 单次 upload_folder 提交.

不走 git, 不走每文件 commit (会撞 128 commits/hour 限速).

用法:
  1. export HF_TOKEN=<你的 write token>
  2. python3 scripts/deploy-via-api.py
"""
import os
import sys
import shutil
import tempfile
from pathlib import Path

REPO_ID = os.environ.get("HF_SPACE_REPO", "appQQQ/ai-chatbot")
TOKEN = os.environ.get("HF_TOKEN")
if not TOKEN:
    print("❌ 请先设环境变量:  export HF_TOKEN=<your write token>")
    sys.exit(1)

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent / "backend"

# 复制到一个临时目录再打包 (避免把 backend 整个 push 上去, Space 期望平铺结构)
print(f"🚀 用 HF Hub API 单次 upload_folder 部署 → {REPO_ID}")

try:
    from huggingface_hub import HfApi
except ImportError:
    print("❌ 缺 huggingface_hub. 装:  pip install huggingface_hub")
    sys.exit(1)

api = HfApi(token=TOKEN)

# 1. 准备 staging 目录: 拷 backend/ 进去, 排除 data/.venv/__pycache__/tests/.env 等
STAGE = Path(tempfile.mkdtemp(prefix="hf-stage-"))
print(f"📦 staging 目录: {STAGE}")

SKIP_NAMES = {
    "__pycache__", "data", ".venv", "venv", ".pytest_cache",
    "tests", ".env", ".env.local", ".mypy_cache", ".ruff_cache",
}
SKIP_EXTS = {".pyc", ".db", ".sqlite", ".sqlite3"}

for src in BACKEND_DIR.rglob("*"):
    if src.is_dir():
        continue
    rel = src.relative_to(BACKEND_DIR)
    # 跳过的目录/扩展名
    if any(p.name in SKIP_NAMES for p in [rel, *rel.parents]):
        continue
    if src.suffix in SKIP_EXTS:
        continue
    dst = STAGE / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)

file_count = sum(1 for _ in STAGE.rglob("*") if _.is_file())
print(f"   共 {file_count} 个文件待上传 (单次 commit)")

# 2. 一次 commit 全推上去
print()
print("📤 upload_folder (单 commit, 不会撞 128/hr 限速)...")
try:
    api.upload_folder(
        folder_path=str(STAGE),
        repo_id=REPO_ID,
        repo_type="space",
        token=TOKEN,
        commit_message="fix: independent persist executor + reset pending_push on failure",
        ignore_patterns=["__pycache__/*", "*.pyc", ".cache/*"],
    )
    print("✅ 上传完成")
except Exception as e:
    print(f"❌ 上传失败: {type(e).__name__}: {e}")
    sys.exit(1)
finally:
    shutil.rmtree(STAGE, ignore_errors=True)

print()
print("🌐 Space 正在 rebuild, 约 5-10 分钟")
print("   构建日志: https://huggingface.co/spaces/appQQQ/ai-chatbot/logs")
