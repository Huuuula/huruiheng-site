/**
 * GET /callback?code=<临时码>&state=<防伪随机数>
 *
 * 登录第二步：拿 code 去 GitHub 换 access token，再通过 postMessage 交回后台。
 * token 只在这一次响应里出现，不落日志、不进 Cookie、不写仓库。
 */
import { handshakePage, readCookie, type AuthEnv } from './_lib/oauth';

type Context = { request: Request; env: AuthEnv };

export const onRequestGet = async ({ request, env }: Context): Promise<Response> => {
  const url = new URL(request.url);
  const code = url.searchParams.get('code');
  const state = url.searchParams.get('state');
  const expected = readCookie(request.headers.get('cookie'), 'cms_oauth_state');

  // 没有 code：多半是用户在 GitHub 上点了「取消」
  if (!code) {
    return handshakePage(
      { provider: 'github', error: '授权被取消', errorCode: 'AUTH_CANCELLED' },
      env,
    );
  }

  // state 必须与发起时一致，否则可能是别人构造的回调
  if (!state || !expected || state !== expected) {
    return handshakePage(
      { provider: 'github', error: '登录状态已失效，请重新登录', errorCode: 'STATE_MISMATCH' },
      env,
    );
  }

  const tokenResponse = await fetch('https://github.com/login/oauth/access_token', {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      accept: 'application/json',
      'user-agent': 'huruiheng-cms',
    },
    body: JSON.stringify({
      client_id: env.GITHUB_CLIENT_ID,
      client_secret: env.GITHUB_CLIENT_SECRET,
      code,
      redirect_uri: `${url.origin}/callback`,
    }),
  });

  const payload = (await tokenResponse.json()) as {
    access_token?: string;
    error?: string;
    error_description?: string;
  };

  if (!payload.access_token) {
    return handshakePage(
      {
        provider: 'github',
        error: payload.error_description || payload.error || '换取访问令牌失败',
        errorCode: 'TOKEN_EXCHANGE_FAILED',
      },
      env,
    );
  }

  return handshakePage({ provider: 'github', token: payload.access_token }, env);
};
