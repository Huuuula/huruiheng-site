#!/usr/bin/env node
/**
 * 构建期生成 sitemap.xml。
 * 不引入额外依赖：内容来自 src/content，静态路由在此显式登记。
 */
import { writeFileSync, readdirSync, existsSync, readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const SITE = process.env.SITE_URL || 'https://huruiheng.pages.dev';
const BASE = SITE.replace(/\/$/, '');

const slugs = (dir) =>
  existsSync(dir)
    ? readdirSync(dir)
        .filter((f) => f.endsWith('.md'))
        .map((f) => f.replace(/\.md$/, ''))
    : [];

// 中文标签按小写百分号编码，与页面产物目录一致
const tags = new Set();
for (const sub of ['posts', 'projects']) {
  for (const file of readdirSync(join(root, 'src/content', sub)).filter((f) => f.endsWith('.md'))) {
    const raw = readFileSync(join(root, 'src/content', sub, file), 'utf8');
    const m = raw.match(/^tags:\s*\[(.*?)\]/m);
    if (!m) continue;
    for (const t of m[1].split(',')) {
      const name = t.trim().replace(/^["']|["']$/g, '');
      if (name) tags.add(name);
    }
  }
}

const paths = [
  '/',
  '/writing/',
  '/projects/',
  '/tags/',
  '/about/',
  '/search/',
  ...slugs(join(root, 'src/content/posts')).map((s) => `/writing/${s}/`),
  ...slugs(join(root, 'src/content/projects')).map((s) => `/projects/${s}/`),
  ...[...tags].map((t) => `/tags/${encodeURIComponent(t).toLowerCase()}/`),
];

const today = new Date().toISOString().slice(0, 10);
const urls = paths
  .map(
    (p) =>
      `  <url>\n    <loc>${BASE}${p}</loc>\n    <lastmod>${today}</lastmod>\n` +
      `    <changefreq>${p === '/' ? 'daily' : 'weekly'}</changefreq>\n` +
      `    <priority>${p === '/' ? '1.0' : p.split('/').length > 3 ? '0.7' : '0.8'}</priority>\n  </url>`
  )
  .join('\n');

const xml = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`;

writeFileSync(join(root, 'public/sitemap.xml'), xml);

// robots 与 sitemap 同源生成，域名只在一处维护
const robots = `User-agent: *\nAllow: /\n\nSitemap: ${BASE}/sitemap.xml\n`;
writeFileSync(join(root, 'public/robots.txt'), robots);

console.log(`[sitemap] ${paths.length} 条 · robots 已更新`);
