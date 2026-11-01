/**
 * 搜索：索引在构建时生成（scripts/build-index.mjs → public/search-index.json），
 * 浏览器首次打开搜索时才拉取，之后整站本地过滤。
 *
 * 为什么不用服务端搜索：本站只有个位数内容，索引 20KB 左右，前端完全够用；
 * 而服务端搜索需要 Pages Functions / Worker，会让「拖拽上传」这种零门槛部署失效。
 */

let cache = null;
let pending = null;

/** 拉取索引，进程内只请求一次；失败后允许重试 */
export function loadIndex() {
  if (cache) return Promise.resolve(cache);
  if (!pending) {
    pending = fetch('/search-index.json', { credentials: 'same-origin' })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (data) {
        cache = Array.isArray(data) ? data : [];
        return cache;
      })
      .catch(function (err) {
        pending = null;
        throw err;
      });
  }
  return pending;
}

/**
 * 匹配规则（与服务端版本保持一致的语义）：
 * - 空格分词，词之间是 AND：任一关键词完全没命中就淘汰
 * - 标题命中权重最高，其次摘要，最后正文
 * - 标题前缀命中额外加分
 * - 同分按日期倒序
 */
export function runSearch(index, rawQuery, limit) {
  var max = limit || 8;
  var q = String(rawQuery || '').trim();
  if (!q || !Array.isArray(index)) return [];

  var terms = q.toLowerCase().split(/\s+/u).filter(Boolean);
  var hits = [];

  for (var i = 0; i < index.length; i++) {
    var item = index[i];
    var title = String(item.title || '').toLowerCase();
    var excerpt = String(item.excerpt || '').toLowerCase();
    var text = String(item.text || '').toLowerCase();

    var score = 0;
    var miss = false;

    for (var t = 0; t < terms.length; t++) {
      var term = terms[t];
      var inTitle = title.indexOf(term) !== -1;
      var inExcerpt = excerpt.indexOf(term) !== -1;
      var inText = text.indexOf(term) !== -1;
      if (!inTitle && !inExcerpt && !inText) {
        miss = true;
        break;
      }
      if (inTitle) score += 100;
      if (inExcerpt) score += 20;
      if (inText) score += 5;
      if (inTitle && title.indexOf(term) === 0) score += 50;
    }

    if (miss) continue;
    hits.push({ item: item, score: score });
  }

  hits.sort(function (a, b) {
    if (b.score !== a.score) return b.score - a.score;
    // 日期都是 YYYY-MM-DD，字符串比较即可
    return (a.item.date || '') < (b.item.date || '') ? 1 : -1;
  });

  return hits.slice(0, max).map(function (h) {
    return {
      id: h.item.id,
      title: h.item.title,
      url: h.item.url,
      excerpt: h.item.excerpt,
      date: h.item.date,
      subtype: h.item.subtype,
    };
  });
}
