#!/usr/bin/env bash
# 一条命令部署到 Cloudflare Pages（免费版）
#
# 前置（二选一）：
#   A. 本地已登录：npx wrangler login
#   B. 使用 API Token：
#        export CLOUDFLARE_API_TOKEN=...        # 权限：Cloudflare Pages:Edit
#        export CLOUDFLARE_ACCOUNT_ID=...       # 控制台右下角 / URL 里可见
#
# 用法：
#   ./scripts/deploy.sh                    # 部署到 huruiheng.pages.dev
#   ./scripts/deploy.sh my-site            # 自定义项目名
#   ./scripts/deploy.sh my-site example.com # 同时绑定自定义域名（需域名已在该账号下）
set -euo pipefail

cd "$(dirname "$0")/.."

PROJECT="${1:-huruiheng}"
DOMAIN="${2:-}"

# canonical / OG / sitemap 用的站点地址：外部显式指定 > 自定义域名 > pages.dev
if [[ -z "${SITE_URL:-}" ]]; then
  if [[ -n "$DOMAIN" ]]; then
    export SITE_URL="https://${DOMAIN}"
  else
    export SITE_URL="https://${PROJECT}.pages.dev"
  fi
fi

log() { printf '\033[36m›\033[0m %s\n' "$*"; }
die() { printf '\033[31m✗\033[0m %s\n' "$*" >&2; exit 1; }

command -v node >/dev/null || die "未找到 node，请先安装 Node 18+"

# ---------- 1. 构建 ----------
log "生成搜索索引与 sitemap（SITE_URL=$SITE_URL）"
node scripts/build-index.mjs
node scripts/build-sitemap.mjs

log "构建静态站"
npx astro build

[[ -f dist/index.html ]] || die "构建失败：dist/index.html 不存在"

# ---------- 2. 校验认证 ----------
if [[ -n "${CLOUDFLARE_API_TOKEN:-}" ]]; then
  log "使用 API Token 认证"
  [[ -n "${CLOUDFLARE_ACCOUNT_ID:-}" ]] || die "使用 Token 时必须同时设置 CLOUDFLARE_ACCOUNT_ID"
else
  if ! npx wrangler whoami 2>&1 | grep -qi "You are not authenticated"; then
    log "使用已登录的 Wrangler 会话"
  else
    die "未认证。请先运行 npx wrangler login，或设置 CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID"
  fi
fi

# ---------- 3. 创建项目（幂等） ----------
if npx wrangler pages project list 2>/dev/null | grep -qw "$PROJECT"; then
  log "项目 $PROJECT 已存在，直接部署"
else
  log "创建 Pages 项目 $PROJECT"
  npx wrangler pages project create "$PROJECT" --production-branch main
fi

# ---------- 4. 部署 ----------
log "上传 dist/（$(find dist -type f | wc -l) 个文件，$(du -sh dist | cut -f1)）"
npx wrangler pages deploy dist --project-name "$PROJECT" --branch main --commit-dirty=true

URL="https://${PROJECT}.pages.dev"
echo
printf '\033[32m✓ 部署完成\033[0m\n'
printf '  前台  %s\n' "$URL"
printf '  搜索  %s/api/search?q=DNS\n' "$URL"
printf '  后台  %s/admin/（Git CMS，需另配 GitHub OAuth，见 docs/CMS.md）\n' "$URL"

# ---------- 5. 自定义域名（可选） ----------
if [[ -n "$DOMAIN" ]]; then
  log "绑定自定义域名 $DOMAIN"
  npx wrangler pages domain add "$DOMAIN" --project-name "$PROJECT" || \
    printf '\033[33m!\033[0m 绑定失败，请确认域名已托管在同一 Cloudflare 账号下\n'
  printf '  绑定后请到 DNS 面板确认 CNAME 记录，证书签发通常 1-3 分钟\n'
fi

# ---------- 6. 线上复检 ----------
log "线上复检（等待边缘生效，最多 60 秒）"
for i in {1..12}; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$URL/" || true)
  [[ "$code" == "200" ]] && break
  sleep 5
done
bash scripts/healthcheck.sh "$URL" || {
  printf '\033[33m!\033[0m 线上检查未全部通过，请查看上方失败项\n'
  exit 1
}
