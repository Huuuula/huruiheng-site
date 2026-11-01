import { defineConfig } from 'astro/config';
import { headingId } from './src/lib/format.ts';

/**
 * 给正文 h2/h3 补 id。规则复用 headingId()，与 TOC 锚点、
 * 原主题 hrh_process_headings() 的 sanitize_title() 一致；重复标题按 -2、-3 递增。
 * 纯递归遍历，不引第三方依赖。
 */
function rehypeHeadingIds() {
  return (tree) => {
    const used = new Set();

    const textOf = (node) => {
      if (node.type === 'text') return node.value;
      if (!node.children) return '';
      return node.children.map(textOf).join('');
    };

    const walk = (node) => {
      if (node.tagName === 'h2' || node.tagName === 'h3') {
        const text = textOf(node).trim();
        if (text) {
          const existing = node.properties && node.properties.id;
          let id;
          if (existing) {
            id = String(existing);
          } else {
            const base = headingId(text);
            id = base;
            let n = 1;
            while (used.has(id)) id = `${base}-${++n}`;
            node.properties = { ...(node.properties || {}), id };
          }
          used.add(id);
        }
      }
      (node.children || []).forEach(walk);
    };

    walk(tree);
  };
}

// Cloudflare Pages 静态构建。站点地址由 SITE_URL 注入（构建时），
// 未设置时用 Pages 默认域名，保证 canonical / OG 永远绝对 URL。
export default defineConfig({
  site: process.env.SITE_URL || 'https://huruiheng.pages.dev',
  trailingSlash: 'always',
  build: {
    format: 'directory',
    inlineStylesheets: 'auto',
  },
  markdown: {
    // 原站代码块只有 <pre><code>，配色由主题 CSS 决定；Shiki 会注入深色内联背景
    syntaxHighlight: false,
    rehypePlugins: [rehypeHeadingIds],
  },
  compressHTML: true,
  devToolbar: { enabled: false },
});
