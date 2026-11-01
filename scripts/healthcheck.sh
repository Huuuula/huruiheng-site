#!/usr/bin/env bash
# 全站健康检查：路由矩阵 + 静态资源 + API + 关键内容断言
# 用法：./scripts/healthcheck.sh [base_url]
set -uo pipefail

BASE="${1:-http://127.0.0.1:8790}"
PASS=0
FAIL=0
FAILED=()

check() { # path 期望码 [关键字]
  local path="$1" want="${2:-200}" kw="${3:-}"
  local out="" code body
  if [[ -z "$kw" ]]; then
    # 二进制或不校验内容时只取状态码，避免 null 字节进入变量
    code=$(curl -s -o /dev/null -m 15 -w '%{http_code}' "${BASE}${path}")
  else
    body=$(curl -s -m 15 -w $'\n%{http_code}' "${BASE}${path}")
    code=$(printf '%s' "$body" | tail -n1)
    out=$(printf '%s' "$body" | sed '$d')
  fi
  if [[ "$code" != "$want" ]]; then
    printf '  \033[31mFAIL\033[0m %-46s %s (期望 %s)\n' "$path" "$code" "$want"
    FAIL=$((FAIL+1)); FAILED+=("$path")
    return
  fi
  if [[ -n "$kw" ]] && ! printf '%s' "$out" | grep -qF -- "$kw"; then
    printf '  \033[31mFAIL\033[0m %-46s 缺少关键字「%s」\n' "$path" "$kw"
    FAIL=$((FAIL+1)); FAILED+=("$path")
    return
  fi
  printf '  \033[32mPASS\033[0m %-46s %s\n' "$path" "$code"
  PASS=$((PASS+1))
}

echo "== 页面路由 =="
check "/" 200 "不定期更新"
check "/writing/" 200 "page-head"
check "/writing/why-dns-first/" 200 "先配好 DNS"
check "/writing/free-hosting-ceiling/" 200 "免费托管"
check "/writing/designing-as-a-journal/" 200 "把博客做成一份刊物"
check "/projects/" 200 ""
check "/projects/check-ns/" 200 "check_ns"
check "/projects/eu-org-automation/" 200 "eu.org"
check "/projects/this-site/" 200 "huruiheng.eu.org"
check "/tags/" 200 "标签"
check "/tags/cloudflare/" 200 "cloudflare"
check "/tags/dns/" 200 "dns"
check "/tags/%e6%8e%92%e9%94%99/" 200 "排错"
check "/tags/%e8%ae%be%e8%ae%a1/" 200 "设计"
check "/about/" 200 "关于"
check "/search/" 200 "搜索"
check "/no-such-page/" 404 "页面不存在"

echo "== 资源与元数据 =="
check "/feed.xml" 200 "<rss"
check "/feed/" 200 "<rss"
check "/sitemap.xml" 200 "<urlset"
check "/robots.txt" 200 "Sitemap"
check "/favicon.svg" 200 ""
check "/og.png" 200 ""
check "/fonts/inter-latin-wght-normal.woff2" 200 ""
check "/fonts/source-serif-4-latin-wght-normal.woff2" 200 ""

echo "== 搜索 API =="
check "/api/search?q=DNS" 200 '"count":3'
check "/api/search" 200 '"count":0'
check "/api/search?q=zzzz" 200 '"count":0'

echo
if [[ $FAIL -eq 0 ]]; then
  printf '\033[32m全部通过：%d 项\033[0m\n' "$PASS"
else
  printf '\033[31m通过 %d，失败 %d\033[0m\n' "$PASS" "$FAIL"
  printf '失败项：%s\n' "${FAILED[*]}"
  exit 1
fi
