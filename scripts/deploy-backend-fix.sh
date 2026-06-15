#!/bin/bash
# 一键把 backend-fix.tar.gz 推到 HF Space. 必须显式提供 HF_TOKEN.
#
# 用法:
#   export HF_TOKEN=<your hf write token>   # 必填
#   export HF_USER=appQQQ                    # 可选, 默认 appQQQ
#   export HF_SPACE=ai-chatbot               # 可选, 默认 ai-chatbot
#   ./scripts/deploy-backend-fix.sh
#
# ⚠️ 不会把 token 写入任何文件/历史, 仅在进程内 URL 拼一次.
set -euo pipefail

: "${HF_TOKEN:?HF_TOKEN 未设置. 用 'export HF_TOKEN=hf_xxx' 注入 (write 权限)}"
HF_USER="${HF_USER:-appQQQ}"
HF_SPACE="${HF_SPACE:-ai-chatbot}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d -t hf-deploy-XXXXXX)"
TARBALL="${SCRIPT_DIR}/backend-fix.tar.gz"

if [[ ! -f "$TARBALL" ]]; then
  echo "❌ 找不到 $TARBALL"
  exit 1
fi

echo "🚀 部署 backend/ → ${HF_USER}/${HF_SPACE} (直连 + token)"
echo "📦 工作目录: $WORK"
echo

# 1. 克隆 Space (直连 HF, 不走镜像, URL 带 token; 只在本进程 URL 拼一次, 不入文件)
echo "1/5 克隆 Space 仓库..."
git clone "https://${HF_USER}:${HF_TOKEN}@huggingface.co/spaces/${HF_USER}/${HF_SPACE}" "$WORK/space" 2>&1 | tail -3

# 2. 解压新 backend
echo "2/5 解压新 backend..."
cd "$WORK/space"
# 关键: tarball 里文件路径是 "backend/...", 用 --strip-components=1 去掉 "backend/" 前缀
# 否则会在 Space repo 根目录新建一个 backend/ 子目录, 而老的 app/... 还留着
tar -xzf "$TARBALL" --strip-components=1

# 3. 清理本地数据
echo "3/5 清理本地数据目录..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.db" -delete 2>/dev/null || true

# 4. 提交
echo "4/5 commit..."
git add -A
git -c user.name="${HF_USER}" -c user.email="${HF_USER}@local" commit -m "fix: enable marker fallback + drop artifacts_path + better parser error" 2>&1 | tail -3

# 5. 推送
echo "5/5 push..."
git push origin main 2>&1 | tail -10

echo
echo "✅ 推送完成"
echo "🌐 Space 正在 rebuild, 约 5-10 分钟"
echo "   构建日志: https://huggingface.co/spaces/${HF_USER}/${HF_SPACE}/logs"
