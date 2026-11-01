/**
 * GET /auth?provider=github&site_id=<host>&scope=<scopes>
 *
 * Sveltia CMS 登录的第一步：把这个弹窗请求转成 GitHub 授权页。
 * 生成的 state 写进 HttpOnly Cookie，回调时比对，防止有人伪造回调。
 */
import { handshakePage, type AuthEnv } from './_lib/oauth';

type Context = { request: Request; env: AuthEnv };

/** 只接受这几个 scope，避免这个端点被拿去换一个权限更大的 token */
const ALLOWED_SCOPES = ['repo', 'public_repo', 'user', 'read:user', 'user:email'];

export const onRequestGet = async ({ request, env }: Context): Promise<Response> => {
  const url = new URL(request.url);
  const provider = url.searchParams.get('provider') ?? 'github';

  if (provider !== 'github') {
    return handshakePage(
      { provider, error: '只支持 GitHub 登录', errorCode: 'UNSUPPORTED_BACKEND' },
      env,
    );
  }

  if (!env.GITHUB_CLIENT_ID || !env.GITHUB_CLIENT_SECRET) {
    return handshakePage(
      { provider, error: '服务端缺少 GitHub OAuth 配置', errorCode: 'MISSING_CONFIG' },
      env,
    );
  }

  const requested = (url.searchParams.get('scope') ?? '').split(/[\s,]+/).filter(Boolean);
  const scope =
    requested.length && requested.every((s) => ALLOWED_SCOPES.includes(s))
      ? requested.join(',')
      : 'repo,user';

  const state = crypto.randomUUID();
  const authorize = new URL('https://github.com/login/oauth/authorize');
  authorize.searchParams.set('client_id', env.GITHUB_CLIENT_ID);
  authorize.searchParams.set('redirect_uri', `${url.origin}/callback`);
  authorize.searchParams.set('scope', scope);
  authorize.searchParams.set('state', state);

  return new Response(null, {
    status: 302,
    headers: {
      location: authorize.toString(),
      'cache-control': 'no-store',
      'set-cookie': `cms_oauth_state=${state}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=600`,
    },
  });
};
