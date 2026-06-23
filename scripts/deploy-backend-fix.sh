#!/bin/bash
# 一键把 backend-fix.tar.gz 推到 HF Space. 自动探测网络环境:
#  - huggingface.co 可达 → 走直连 (避免镜像 ref tracking 问题)
#  - 仅 hf-mirror.com 可达 → 走镜像 (国内沙箱/被封环境)
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

# 探测网络: 直连 HF 主域 or 镜像
echo "🔍 探测网络环境..."
if curl -sS --max-time 8 -o /dev/null "https://huggingface.co/api/spaces/${HF_USER}/${HF_SPACE}" 2>/dev/null; then
  HF_HOST="huggingface.co"
  echo "✅ 直连 huggingface.co 可达"
else
  HF_HOST="hf-mirror.com"
  echo "⚠️  huggingface.co 不可达, 切换到 hf-mirror.com"
fi

SPACE_URL="https://${HF_HOST}/spaces/${HF_USER}/${HF_SPACE}"
echo "🚀 部署 backend/ → ${HF_USER}/${HF_SPACE} (via ${HF_HOST})"
echo "📦 工作目录: $WORK"
echo

# 1. 克隆 Space (URL 带 token)
echo "1/5 克隆 Space 仓库..."
CLONE_URL="https://${HF_USER}:${HF_TOKEN}@${HF_HOST}/spaces/${HF_USER}/${HF_SPACE}"
git clone "$CLONE_URL" "$WORK/space" 2>&1 | tail -3

# 2. 解压新 backend
# ⚠️ 不要带 --strip-components. tarball 路径是 app/__init__.py / app/config.py,
#    去掉 strip 后 tar 按原路径解开, 直接覆盖 app/ 里的对应文件.
#    带 --strip-components=1 会把路径变成裸 __init__.py / config.py,
#    落到工作目录根, **不会**覆盖 app/ 下的同名文件, push 上去会变成根目录新建文件.
echo "2/5 解压新 backend..."
cd "$WORK/space"
tar -xzf "$TARBALL"

# 3. 清理本地数据
echo "3/5 清理本地数据目录..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.db" -delete 2>/dev/null || true

# 4. 提交
echo "4/5 commit..."
git add -A
# 避免镜像 ref tracking: 设一个非默认 branch 推, 然后同步回去
# (镜像 commit ref 跟主站不一致, 直 push main 会被拒)
if [[ "$HF_HOST" == "hf-mirror.com" ]]; then
  # 镜像分支命名: hf-mirror-push-{timestamp}
  BR="hf-mirror-push-$(date +%s)"
  git checkout -b "$BR"
  git -c user.name="${HF_USER}" -c user.email="${HF_USER}@local" commit -m "fix: persist sync verify + 5s debounce (A 改良版)" 2>&1 | tail -3
  # push 到镜像分支
  git push origin "$BR" 2>&1 | tail -10
  echo
  echo "⚠️  镜像 push 完成, 但镜像的 ref tracking 跟主站不同步"
  echo "    HF 主站会在 5-30 分钟内自动从镜像 sync 过去"
  echo "    或你也可以手动在 hf.co 上 sync 该 branch"
  echo "    查看: https://huggingface.co/spaces/${HF_USER}/${HF_SPACE}/tree/${BR}"
else
  git -c user.name="${HF_USER}" -c user.email="${HF_USER}@local" commit -m "fix: persist sync verify + 5s debounce (A 改良版)" 2>&1 | tail -3
  git push origin main 2>&1 | tail -10
fi

echo
echo "✅ 推送完成"
echo "🌐 Space 正在 rebuild, 约 5-10 分钟"
echo "   构建日志: https://huggingface.co/spaces/${HF_USER}/${HF_SPACE}/logs"