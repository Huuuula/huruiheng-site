#!/usr/bin/env node
/**
 * 构建期生成搜索索引，供 Pages Functions 内联使用。
 * 输出：functions/_lib/search-index.json
 * 体积控制在 100KB 以内（当前 3 篇文章 + 3 个项目约 25KB）。
 */
import { readFileSync, writeFileSync, readdirSync, mkdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

/** 解析极简 frontmatter：仅支持本项目用到的 key: value / 行内数组 */
function parseFrontmatter(raw) {
  const m = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/);
  if (!m) return { data: {}, body: raw };
  const data = {};
  for (const line of m[1].split(/\r?\n/)) {
    const kv = line.match(/^([A-Za-z_][\w-]*):\s*(.*)$/);
    if (!kv) continue;
    const key = kv[1];
    let val = kv[2].trim();
    if (val.startsWith('[') && val.endsWith(']')) {
      data[key] = val
        .slice(1, -1)
        .split(',')
        .map((s) => s.trim().replace(/^["']|["']$/g, ''))
        .filter(Boolean);
    } else {
      data[key] = val.replace(/^["']|["']$/g, '');
    }
  }
  return { data, body: m[2] };
}

/** markdown → 纯文本，尽量保留可检索内容 */
function toPlain(md) {
  return md
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/^\s*[-*+]\s+/gm, '')
    .replace(/^\s*\d+\.\s+/gm, '')
    .replace(/[*_~>]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function collect(dir, subtype) {
  const out = [];
  for (const file of readdirSync(dir).filter((f) => f.endsWith('.md'))) {
    const slug = file.replace(/\.md$/, '');
    const { data, body } = parseFrontmatter(readFileSync(join(dir, file), 'utf8'));
    if (!data.title) continue;
    const plain = toPlain(body);
    // 占位的 writing.md / tags.md 正文为空，不入索引（原站也是模板生成，无正文可搜）
    if (!plain) continue;
    const excerpt = (data.excerpt || data.summary || plain.slice(0, 90)).trim();
    out.push({
      id: slug,
      title: data.title,
      url:
        subtype === 'project' ? `/projects/${slug}/` : subtype === 'page' ? `/${slug}/` : `/writing/${slug}/`,
      date: data.date || '',
      subtype,
      excerpt,
      // 正文截断，控制索引体积；4000 字足够覆盖现有长文
      text: plain.slice(0, 4000),
    });
  }
  return out;
}

const index = [
  ...collect(join(root, 'src/content/posts'), 'post'),
  ...collect(join(root, 'src/content/projects'), 'project'),
  ...collect(join(root, 'src/content/pages'), 'page'),
];

const outDir = join(root, 'functions/_lib');
mkdirSync(outDir, { recursive: true });
writeFileSync(join(outDir, 'search-index.json'), JSON.stringify(index));

// 前端搜索用同一份索引：纯静态部署时由浏览器按需拉取，不依赖 Functions
const publicDir = join(root, 'public');
mkdirSync(publicDir, { recursive: true });
writeFileSync(join(publicDir, 'search-index.json'), JSON.stringify(index));

const bytes = JSON.stringify(index).length;
console.log(`[search-index] ${index.length} 条，${(bytes / 1024).toFixed(1)} KB（functions + public 各一份）`);
