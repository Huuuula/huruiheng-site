/**
 * Workers Static Assets 版本入口。
 * 用途：在没有 Cloudflare 账号的情况下，用 `wrangler deploy --temporary`
 * 部署到临时预览账号，拿到一个可公开访问的 URL 做验收。
 * 正式部署仍走 Pages（functions/ 目录），两者共用 search-core，结果一致。
 */
import INDEX from '../functions/_lib/search-index.json';
import { runSearch, searchJson, type SearchItem } from '../functions/_lib/search-core';

interface Env {
  ASSETS: { fetch(request: Request): Promise<Response> };
}

const DATA = INDEX as SearchItem[];

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === '/api/search') {
      if (request.method !== 'GET') {
        return new Response(JSON.stringify({ error: 'method_not_allowed' }), {
          status: 405,
          headers: { 'content-type': 'application/json; charset=utf-8' },
        });
      }
      const q = (url.searchParams.get('q') ?? url.searchParams.get('search') ?? '').trim();
      const rawLimit = Number.parseInt(url.searchParams.get('limit') ?? '8', 10);
      const limit = Number.isFinite(rawLimit) ? Math.min(Math.max(rawLimit, 1), 20) : 8;
      return searchJson(runSearch(DATA, q, limit), q);
    }

    return env.ASSETS.fetch(request);
  },
};
