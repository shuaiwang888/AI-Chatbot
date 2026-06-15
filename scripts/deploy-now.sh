#!/bin/bash
# 一键把 backend/ 推到 HF Space, 绕开 Python huggingface_hub 的 SSL bug.
# 走 git+token (macOS SecureTransport 不用 Python OpenSSL).
#
# 用法:
#   export HF_TOKEN=hf_xxx
#   ./scripts/deploy-now.sh
#
# 失败会原样退出, 看错行
set -euo pipefail

: "${HF_TOKEN:?HF_TOKEN 未设置. 用 'export HF_TOKEN=hf_xxx' 注入 (write 权限)}"

HF_USER="${HF_USER:-appQQQ}"
HF_SPACE="${HF_SPACE:-ai-chatbot}"
REPO_URL="https://${HF_USER}:${HF_TOKEN}@huggingface.co/spaces/${HF_USER}/${HF_SPACE}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"

# 临时工作区 (放 Space 仓库)
WORK="$(mktemp -d -t hf-deploy-XXXXXX)"
trap 'rm -rf "$WORK"' EXIT

echo "🚀 部署 backend/ → ${HF_USER}/${HF_SPACE}"
echo "📦 项目根: $PROJECT_ROOT"
echo "📦 backend: $BACKEND_DIR"
echo "📦 工作区: $WORK"
echo

# 1. 克隆 Space 仓库
echo "1/5 克隆 Space 仓库..."
git clone "$REPO_URL" "$WORK/space" 2>&1 | tail -3

cd "$WORK/space"

# 2. 备份 .gitattributes + README.md (HF Space 元数据, 不能丢)
echo "2/5 保留 .gitattributes + README.md..."
mkdir -p "$WORK/keep"
[[ -f .gitattributes ]] && mv .gitattributes "$WORK/keep/"
[[ -f README.md ]] && mv README.md "$WORK/keep/"

# 3. 清空根目录, 拷入新 backend (排除 data/.venv/.env/cache/test 文件)
echo "3/5 同步 backend/ 到 Space 根..."
# 清空根 (除了 .git)
find . -mindepth 1 -maxdepth 1 ! -name '.git' -exec rm -rf {} +

# 拷 backend
rsync -a \
  --exclude='data' \
  --exclude='.venv' \
  --exclude='venv' \
  --exclude='__pycache__' \
  --exclude='.pytest_cache' \
  --exclude='.mypy_cache' \
  --exclude='.ruff_cache' \
  --exclude='.cache' \
  --exclude='tests' \
  --exclude='.env' \
  --exclude='.env.local' \
  --exclude='*.db' \
  --exclude='*.sqlite' \
  --exclude='*.sqlite3' \
  --exclude='*.pyc' \
  --exclude='*.egg-info' \
  --exclude='*.tmp' \
  "$BACKEND_DIR/" ./

# 恢复元数据
[[ -f "$WORK/keep/.gitattributes" ]] && mv "$WORK/keep/.gitattributes" .
[[ -f "$WORK/keep/README.md" ]] && mv "$WORK/keep/README.md" .

file_count=$(find . -type f ! -path './.git/*' | wc -l | tr -d ' ')
echo "   共 $file_count 个文件"

# 4. 原子 commit
echo "4/5 commit..."
git -c user.name=shuaiwang -c user.email=shuaiwang@local add -A
if git diff --cached --quiet; then
  echo "   (没有改动, 跳过 commit)"
else
  git -c user.name=shuaiwang -c user.email=shuaiwang@local commit -m "fix: independent persist executor + reset pending_push on failure

- backend/app/services/persist.py: add dedicated ThreadPoolExecutor
  (so upload_folder can't starve business run_in_executor like
  ChromaDB query / BGE-M3 encode)
- push_to_hf(): reset pending_push flag on failure too
  (was getting stuck at True after first error, blocking all future
  schedule_push calls)" 2>&1 | tail -3
fi

# 5. push
echo "5/5 push..."
git push origin main 2>&1 | tail -5

echo
echo "✅ 推送完成"
echo "🌐 Space 正在 rebuild, 约 5-10 分钟"
echo "   构建日志: https://huggingface.co/spaces/${HF_USER}/${HF_SPACE}/logs"
