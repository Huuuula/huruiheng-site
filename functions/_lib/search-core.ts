/**
 * 搜索核心逻辑，被两个载体共用：
 *  - functions/api/search.ts（Cloudflare Pages Functions）
 *  - worker/index.ts（Workers Static Assets，用于 --temporary 预览部署）
 * 抽出来是为了保证两种部署形态的结果完全一致。
 */

export interface SearchItem {
  id: string;
  title: string;
  url: string;
  date: string;
  subtype: 'post' | 'project' | 'page';
  excerpt: string;
  text: string;
}

export interface SearchHit {
  id: string;
  title: string;
  url: string;
  excerpt: string;
  date: string;
  subtype: string;
}

export function runSearch(index: SearchItem[], rawQuery: string, limit = 8): SearchHit[] {
  const q = rawQuery.trim();
  if (!q) return [];
  const terms = q.toLowerCase().split(/\s+/u).filter(Boolean);

  return index
    .map((item) => {
      const title = item.title.toLowerCase();
      const excerpt = item.excerpt.toLowerCase();
      const text = item.text.toLowerCase();

      let score = 0;
      for (const term of terms) {
        const inTitle = title.includes(term);
        const inExcerpt = excerpt.includes(term);
        const inText = text.includes(term);
        // AND 语义：任一关键词完全未命中则整条淘汰
        if (!inTitle && !inExcerpt && !inText) return null;
        score += inTitle ? 100 : 0;
        score += inExcerpt ? 20 : 0;
        score += inText ? 5 : 0;
        if (inTitle && title.startsWith(term)) score += 50;
      }
      return { item, score };
    })
    .filter((x): x is { item: SearchItem; score: number } => x !== null)
    .sort((a, b) => b.score - a.score || (a.item.date < b.item.date ? 1 : -1))
    .slice(0, limit)
    .map(({ item }) => ({
      id: item.id,
      title: item.title,
      url: item.url,
      excerpt: item.excerpt,
      date: item.date,
      subtype: item.subtype,
    }));
}

export function searchJson(results: SearchHit[], query: string, status = 200): Response {
  return new Response(JSON.stringify({ query, count: results.length, results }), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'public, max-age=300',
    },
  });
}
