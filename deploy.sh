#!/usr/bin/env bash
# SkillBazaar 一键部署：拉代码 → 构建前端 → 重启后端
#
# 设计原则：只做能确认的事。重启前会打印识别到的进程管理方式，
# 找不到明确的 supervisor 时不盲杀进程，只输出需要人工执行的命令。
#
# 用法：bash deploy.sh [分支名]    默认分支 main
set -euo pipefail

BRANCH="${1:-main}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m!! %s\033[0m\n' "$*"; }

say "当前分支：$(git rev-parse --abbrev-ref HEAD)"
if [[ -n "$(git status --porcelain)" ]]; then
  warn "工作区有未提交改动，先提交或 stash 再部署："
  git status --short
  exit 1
fi

say "拉取 $BRANCH"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

say "构建前端"
cd "$ROOT/frontend"
if [[ -d node_modules ]]; then
  npm run build
else
  npm ci
  npm run build
fi
cd "$ROOT"

say "探测后端进程管理方式"
SYSTEMD_UNIT=""
for unit in skillbazaar bazaar skillbazaar-backend; do
  if systemctl list-unit-files 2>/dev/null | grep -q "^${unit}\.service"; then
    SYSTEMD_UNIT="$unit"; break
  fi
done

PM2_APP="$(pm2 jlist 2>/dev/null | python3 -c 'import json,sys
try:
    apps=[a["name"] for a in json.load(sys.stdin) if "uvicorn" in " ".join(a.get("pm2_env",{}).get("exec_mode","")) or "skill" in a["name"].lower() or "bazaar" in a["name"].lower()]
    print(apps[0] if apps else "")
except Exception:
    print("")' 2>/dev/null || true)"

DOCKER_CID="$(docker ps --filter "ancestor=skillbazaar" --format '{{.ID}}' 2>/dev/null | head -1 || true)"

if [[ -n "$SYSTEMD_UNIT" ]]; then
  say "重启 systemd 单元：$SYSTEMD_UNIT"
  sudo systemctl restart "$SYSTEMD_UNIT"
elif [[ -n "$PM2_APP" ]]; then
  say "重启 pm2 应用：$PM2_APP"
  pm2 restart "$PM2_APP"
elif [[ -n "$DOCKER_CID" ]]; then
  say "重启容器：$DOCKER_CID"
  docker restart "$DOCKER_CID"
else
  warn "未识别到 systemd / pm2 / docker 管理方式，未自动重启。"
  warn "请按实际方式手动重启后端，例如："
  warn "  systemctl restart <unit>         # systemd"
  warn "  pm2 restart <app>                # pm2"
  warn "  pkill -f 'uvicorn main:app' && nohup uvicorn main:app --host 0.0.0.0 --port 8000 >/var/log/skillbazaar.log 2>&1 &"
  exit 3
fi

say "健康检查"
for i in $(seq 1 20); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
    say "后端健康检查通过："
    curl -fsS http://127.0.0.1:8000/health || true
    echo
    say "部署完成 ✅  下载端点：GET /api/skills/{product_id}/download"
    exit 0
  fi
  sleep 1
done

warn "后端健康检查未通过，请查看日志："
warn "  journalctl -u ${SYSTEMD_UNIT:-<unit>} -n 100 --no-pager"
exit 4
