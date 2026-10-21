#!/usr/bin/env bash
# 启用 docs 仓的 git 钩子（每个克隆执行一次）
#
#   cd docs && bash script/setup-hooks.sh
#
# 做的事：git config core.hooksPath .githooks —— 这是**仓库本地配置**，不改全局、不影响其它仓；
# 取消：git config --unset core.hooksPath
set -euo pipefail

cd "$(dirname "$0")/.."
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit 2>/dev/null || true
echo "已启用：core.hooksPath = $(git config core.hooksPath)"
echo "验证：修改任一 .md 后 git add && git commit，会先跑 script/doc_audit.py"
