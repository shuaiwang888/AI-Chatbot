#!/bin/bash
# 一键把 backend-fix.tar.gz 推到 HF Space. 用于绕过镜像的 ref tracking bug.
# 适用: 沙箱无法直连 huggingface.co 时, 由本机代推.
#
# 用法:  ./scripts/deploy-backend-fix.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d -t hf-deploy-XXXXXX)"
TARBALL="${SCRIPT_DIR}/backend-fix.tar.gz"

if [[ ! -f "$TARBALL" ]]; then
  echo "❌ 找不到 $TARBALL"
  exit 1
fi

echo "🚀 部署 backend/ → HF Space (通过直连, 绕开镜像)"
echo "📦 工作目录: $WORK"
echo

# 1. 克隆 Space (直连 HF, 不走镜像)
echo "1/5 克隆 Space 仓库..."
git clone "https://huggingface.co/spaces/appQQQ/ai-chatbot" "$WORK/space" 2>&1 | tail -3

# 2. 备份当前 Space 文件, 然后解压新版本
echo "2/5 解压新 backend..."
cd "$WORK/space"
tar -xzf "$TARBALL"

# 3. 清理绝对不能 push 的本地数据
echo "3/5 清理本地数据目录..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.db" -delete 2>/dev/null || true

# 4. 提交
echo "4/5 commit..."
git add -A
git -c user.name=appQQQ -c user.email=appQQQ@local commit -m "fix: enable marker fallback + prewarm Docling models + better parser error" 2>&1 | tail -3

# 5. 推送
echo "5/5 push..."
git push origin main 2>&1 | tail -5

echo
echo "✅ 推送完成"
echo "🌐 等待 Space 重新构建, 大约 5-10 分钟"
echo "   构建日志: https://huggingface.co/spaces/appQQQ/ai-chatbot/logs"
