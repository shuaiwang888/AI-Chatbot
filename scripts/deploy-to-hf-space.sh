#!/bin/bash
# 一键把 backend/ 推送到 HuggingFace Space.
# 用法:
#   ./scripts/deploy-to-hf-space.sh <hf-username> <space-name>
# 例:
#   ./scripts/deploy-to-hf-space.sh appQQQ ai-chatbot
set -euo pipefail

HF_USER="${1:-appQQQ}"
SPACE_NAME="${2:-ai-chatbot}"
WORK_DIR="$(mktemp -d -t hf-space-deploy-XXXXXX)"
SPACE_URL="https://huggingface.co/spaces/${HF_USER}/${SPACE_NAME}"
SPACE_SSH="git@hf.co:spaces/${HF_USER}/${SPACE_NAME}"
RUNTIME_URL="https://${HF_USER}-${SPACE_NAME}.hf.space"

echo "🚀 部署 backend/ → ${SPACE_URL}"
echo "📦 工作目录: ${WORK_DIR}"
echo

# 1. 克隆空 Space 仓库
echo "1/4 克隆 Space 仓库..."
git clone "${SPACE_SSH}" "${WORK_DIR}/space" 2>&1 | tail -3

# 2. 复制 backend 全部内容
echo "2/4 复制 backend 文件..."
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cp -R "${REPO_ROOT}/backend/." "${WORK_DIR}/space/"

# 3. 清理本地数据/缓存 (绝对不能 push 上去)
echo "3/4 清理本地数据目录..."
rm -rf "${WORK_DIR}/space/data" \
       "${WORK_DIR}/space/.cache" \
       "${WORK_DIR}/space/.pytest_cache" \
       "${WORK_DIR}/space/.venv" \
       "${WORK_DIR}/space/__pycache__" 2>/dev/null || true
find "${WORK_DIR}/space" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "${WORK_DIR}/space" -type f -name "*.db" -delete 2>/dev/null || true

# 4. 提交并推送
echo "4/4 commit + push..."
cd "${WORK_DIR}/space"
git add -A
git -c user.name="deploy-script" \
    -c user.email="deploy@local" \
    commit -m "deploy: backend for ${HF_USER}/${SPACE_NAME}" 2>&1 | tail -3
git push origin main 2>&1 | tail -5

echo
echo "✅ 推送完成"
echo
echo "⏳ 等待 HF Space 构建 (约 8-15 分钟, 看 Logs)"
echo "   构建日志: ${SPACE_URL}/logs"
echo
echo "🌐 运行时地址: ${RUNTIME_URL}"
echo "   健康检查: ${RUNTIME_URL}/api/v1/healthz"
echo
echo "📋 接下来要做:"
echo "   1. 在 HF Space → Settings → Variables and secrets 配上:"
echo "      MINIMAX_API_KEY    = sk-cp-... (你的真 key)"
echo "      MINIMAX_BASE_URL   = https://api.minimaxi.com/v1"
echo "      MINIMAX_MODEL      = MiniMax-M3"
echo "      EMBEDDING_MODEL    = BAAI/bge-m3"
echo "      RERANKER_MODEL     = BAAI/bge-reranker-v2-m3"
echo "      ALLOWED_ORIGINS    = [\"https://shuaiwang888.github.io\"]"
echo "   2. 等构建完成, 跑:"
echo "      curl ${RUNTIME_URL}/api/v1/healthz"
echo "   3. 拿到 URL 后告诉我, 我帮你配 GH Pages 的 VITE_API_BASE"
