#!/usr/bin/env python3
"""临时脚本: 推单个文件到 HF Space repo, 走 HF HTTP API 绕开 git mirror.
用法: HF_TOKEN=xxx python3 scripts/push-single-file.py <local_relpath> <path_in_repo> [commit_msg]
"""
import os
import sys
from pathlib import Path
from huggingface_hub import HfApi, upload_file

TOKEN = os.environ.get("HF_TOKEN")
if not TOKEN:
    print("❌ HF_TOKEN env var required", file=sys.stderr)
    sys.exit(1)

api = HfApi(token=TOKEN)
me = api.whoami()
print(f"✓ Auth: {me.get('name', '?')}")

local = Path(sys.argv[1])
path_in_repo = sys.argv[2]
msg = sys.argv[3] if len(sys.argv) > 3 else f"push {path_in_repo}"

if not local.exists():
    print(f"❌ {local} not found", file=sys.stderr)
    sys.exit(1)

print(f"  {local} → appQQQ/ai-chatbot/{path_in_repo} ({local.stat().st_size} bytes)")
try:
    upload_file(
        path_or_fileobj=str(local),
        path_in_repo=path_in_repo,
        repo_id="appQQQ/ai-chatbot",
        repo_type="space",
        token=TOKEN,
        commit_message=msg,
    )
    print("  ✓ Done")
except Exception as e:
    print(f"  ✗ {type(e).__name__}: {e}", file=sys.stderr)
    sys.exit(1)
