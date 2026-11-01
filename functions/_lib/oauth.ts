/**
 * OAuth 回调页的公共部分。
 *
 * 为什么不用 Sveltia 官方的 workers.dev 代理：
 * `*.workers.dev` 在境内被 DNS 污染（解析到无关的境外 IP），浏览器到不了，
 * 登录弹窗会一直白屏。把 /auth 与 /callback 放在站点同域下，
 * 走的是 pages.dev 这条已经能通的链路。
 *
 * 协议照抄官方的握手方式：弹窗先发 `authorizing:github`，
 * 父窗口收到后回一个来源，弹窗再用这个来源把 token 发回去。
 * 父窗口的来源由浏览器填写、无法伪造，所以用它判断该不该交出 token。
 */

export type AuthEnv = {
  GITHUB_CLIENT_ID: string;
  GITHUB_CLIENT_SECRET: string;
  /** 允许接收 token 的站点，逗号分隔。留空表示不校验（不建议） */
  ALLOWED_DOMAINS?: string;
};

/** 把域名清单转成精确匹配 / 通配匹配的判断表 */
const toPatterns = (raw?: string): string[] =>
  (raw ?? '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);

/**
 * 生成与父窗口握手的页面。
 * @param content 成功时带 token，失败时带 error 与 errorCode
 * @param env 环境变量，用于读取域名白名单
 */
export const handshakePage = (
  content: { provider: string; token?: string; error?: string; errorCode?: string },
  env: AuthEnv,
): Response => {
  const state = content.token ? 'success' : 'error';
  const html = `<!doctype html>
<html lang="zh-Hans">
<head><meta charset="utf-8"><title>登录中…</title></head>
<body>
<script>
(() => {
  const PROVIDER = 'github';
  const CONTENT = ${JSON.stringify(content).replace(/</g, '\\u003c')};
  const TRUSTED = ${JSON.stringify(toPatterns(env.ALLOWED_DOMAINS)).replace(/</g, '\\u003c')};

  const isTrusted = (origin) => {
    try {
      const host = new URL(origin).hostname;
      return TRUSTED.some((p) =>
        p.startsWith('*.') ? host.endsWith(p.slice(1)) : host === p
      );
    } catch {
      return false;
    }
  };

  window.addEventListener('message', (event) => {
    if (event.data !== 'authorizing:' + PROVIDER) return;
    // 出错时没有秘密可泄露，直接回，方便页面显示原因
    if (CONTENT.token && TRUSTED.length && !isTrusted(event.origin)) return;
    window.opener?.postMessage(
      'authorization:' + PROVIDER + ':${state}:' + JSON.stringify(CONTENT),
      event.origin
    );
  });

  window.opener?.postMessage('authorizing:' + PROVIDER, '*');
})();
</script>
</body>
</html>`;

  return new Response(html, {
    status: 200,
    headers: {
      'content-type': 'text/html; charset=utf-8',
      'cache-control': 'no-store',
      // state 用完即弃
      'set-cookie': 'cms_oauth_state=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0',
    },
  });
};

/** 从 Cookie 头里取单个值 */
export const readCookie = (header: string | null, name: string): string => {
  for (const part of (header ?? '').split(';')) {
    const [k, ...rest] = part.trim().split('=');
    if (k === name) return rest.join('=');
  }
  return '';
};
