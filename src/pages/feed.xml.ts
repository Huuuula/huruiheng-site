/**
 * RSS 2.0：/feed.xml（原站地址是 /feed/，由 public/_redirects 内部转到此文件）。
 * 字段对齐 WordPress 的 feed 输出；content:encoded 用摘要包一层 <p>。
 */
import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';
import { SITE } from '../lib/site';

/** 原站 feed 的 channel description 不含「Hu 的个人站。」前缀，逐字照抄基准 */
const FEED_DESC = '技术笔记、排错记录，和一些做出来的东西。';

const xml = (s: string) =>
  s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');

const cdata = (s: string) => `<![CDATA[${s.replace(/]]>/g, ']]]]><![CDATA[>')}]]>`;

/** WP 的 pubDate 形如 Sat, 31 Oct 2026 00:00:00 +0000 */
const rfc822 = (d: Date) => d.toUTCString().replace(/GMT$/, '+0000');

export const GET: APIRoute = async ({ site }) => {
  const base = site ?? new URL('https://huruiheng.pages.dev');
  const origin = base.origin;

  const posts = (await getCollection('posts')).sort(
    (a, b) => b.data.date.getTime() - a.data.date.getTime(),
  );

  const latest = posts[0]?.data.date ?? new Date();
  const lastBuild = rfc822(latest);

  const items = posts
    .map((post) => {
      const url = new URL(`/writing/${post.id}/`, base).href;
      const summary = post.data.excerpt || post.data.title;

      return `    <item>
      <title>${xml(post.data.title)}</title>
      <link>${xml(url)}</link>
      <pubDate>${rfc822(post.data.date)}</pubDate>
      <description>${xml(summary)}</description>
      <content:encoded>${cdata(`<p>${summary}</p>`)}</content:encoded>
    </item>`;
    })
    .join('\n');

  const body = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${xml(SITE.name)}</title>
    <atom:link href="${xml(new URL('/feed.xml', base).href)}" rel="self" type="application/rss+xml" />
    <link>${xml(origin)}</link>
    <description>${xml(FEED_DESC)}</description>
    <language>zh-Hans</language>
    <pubDate>${lastBuild}</pubDate>
    <lastBuildDate>${lastBuild}</lastBuildDate>
${items}
  </channel>
</rss>
`;

  return new Response(body, {
    headers: { 'Content-Type': 'application/xml; charset=utf-8' },
  });
};
