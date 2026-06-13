#!/usr/bin/env python3
"""用 huggingface_hub API 推 backend/ 到 HF Space. 走 API 不走 git push,
适用于 huggingface.co 主域被封但 API 端点可达的情况.

用法:
  1. 装 huggingface_hub:  pip install huggingface_hub
  2. export HF_TOKEN=<你的 write token>
  3. python3 scripts/deploy-via-api.py
"""
import os
import sys
from pathlib import Path

# 1. 解析参数
REPO_ID = os.environ.get("HF_SPACE_REPO", "appQQQ/ai-chatbot")
TOKEN = os.environ.get("HF_TOKEN")
if not TOKEN:
    print("❌ 请先设环境变量:  export HF_TOKEN=<your write token>")
    sys.exit(1)

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent / "backend"

# 2. 跳过本地数据 / cache / venv
SKIP_PATTERNS = [
    "__pycache__",
    "data",
    ".venv",
    "venv",
    ".pytest_cache",
    "tests",
    ".env",
    ".env.local",
    "*.db",
    "*.sqlite",
    "*.pyc",
    ".mypy_cache",
    ".ruff_cache",
]


def should_skip(path: Path) -> bool:
    name = path.name
    for p in SKIP_PATTERNS:
        if p.startswith("*"):
            if name.endswith(p[1:]):
                return True
        elif name == p:
            return True
    return False


# 3. 上传
print(f"🚀 用 HF Hub API 部署 → {REPO_ID}")
print(f"📦 上传目录: {BACKEND_DIR}")
print()

try:
    from huggingface_hub import HfApi
except ImportError:
    print("❌ 缺 huggingface_hub. 装:  pip install huggingface_hub")
    sys.exit(1)

api = HfApi(token=TOKEN)

# 4. 列出现在 Space 的所有文件 (除了 README + .gitattributes)
print("🔍 检查 Space 当前内容...")
try:
    files = api.list_repo_files(repo_id=REPO_ID, repo_type="space")
    # 不删 .gitattributes (HF Space 元数据)
    # 不删 README.md (用户可能改了)
    keep = {".gitattributes", "README.md"}
    to_delete = [f for f in files if f not in keep]
    if to_delete:
        print(f"🗑  准备删 {len(to_delete)} 个旧文件 (保留 .gitattributes + README.md)")
        for f in to_delete:
            try:
                api.delete_file(
                    path_in_repo=f,
                    repo_id=REPO_ID,
                    repo_type="space",
                    token=TOKEN,
                    commit_message="chore: clear old backend before redeploy",
                )
                print(f"   - {f}")
            except Exception as e:
                print(f"   ! {f}: {e}")
    else:
        print("   (无旧文件)")
except Exception as e:
    print(f"⚠️  列文件失败 (可能 Space 还没初始化): {e}")


# 5. 上传整个 backend 目录
print()
print("📤 上传 backend/ → Space...")
uploaded = 0
for src in BACKEND_DIR.rglob("*"):
    if src.is_dir():
        continue
    rel = src.relative_to(BACKEND_DIR)
    if should_skip(rel) or any(should_skip(p) for p in rel.parents):
        continue
    try:
        api.upload_file(
            path_or_fileobj=str(src),
            path_in_repo=str(rel),
            repo_id=REPO_ID,
            repo_type="space",
            token=TOKEN,
            commit_message=f"chore: upload {rel}",
        )
        uploaded += 1
        print(f"   ✓ {rel}")
    except Exception as e:
        print(f"   ✗ {rel}: {e}")

print()
print(f"✅ 上传 {uploaded} 个文件")
print()
print("🌐 Space 正在自动 rebuild, 约 5-10 分钟")
print("   构建日志: https://huggingface.co/spaces/appQQQ/ai-chatbot/logs")
