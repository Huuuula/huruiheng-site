/**
 * GET /api/search?q=<关键词>&limit=<1-20>
 *
 * 运行在 Cloudflare Pages Functions（Workers 运行时）。
 * 索引在构建期生成并内联，无数据库、无冷启动查询，单次执行 <2ms CPU，
 * 远低于免费版 10ms/请求 的限制。
 */
import INDEX from '../_lib/search-index.json';
import { runSearch, searchJson, type SearchItem } from '../_lib/search-core';

const DATA = INDEX as SearchItem[];

export const onRequestGet = async (context: { request: Request }): Promise<Response> => {
  const url = new URL(context.request.url);
  const q = (url.searchParams.get('q') ?? url.searchParams.get('search') ?? '').trim();
  const rawLimit = Number.parseInt(url.searchParams.get('limit') ?? '8', 10);
  const limit = Number.isFinite(rawLimit) ? Math.min(Math.max(rawLimit, 1), 20) : 8;

  return searchJson(runSearch(DATA, q, limit), q);
};

/** 只允许 GET；其余方法明确拒绝，避免被当成开放端点 */
export const onRequestPost = async (): Promise<Response> =>
  new Response(JSON.stringify({ error: 'method_not_allowed' }), {
    status: 405,
    headers: { 'content-type': 'application/json; charset=utf-8' },
  });
