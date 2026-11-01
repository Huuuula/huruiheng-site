#!/usr/bin/env node
/**
 * 中文衬线子集化：把 Noto Serif SC 裁到「本站实际用到的字」。
 *
 * 为什么不用 Google 的 unicode-range 分片：
 *   分片是给「未知内容」准备的，代价是一篇中文文章要拉 7–10 个 60KB 的分片，
 *   光标题字体就 400KB。本站字数有限（当前全站 855 个唯一字符），
 *   按内容裁一次只要 145KB，一个请求、全站缓存。
 *
 * 为什么不担心新文章缺字：
 *   本脚本挂在 prebuild，每次构建都从 src/ 重新收集字符集，
 *   新写的字会自动进入子集；万一漏了，浏览器回落到系统宋体，不会出豆腐块。
 *
 * 源字体：assets/fonts/noto-serif-sc-400.woff2（静态 400 字重，8244 字形）
 * 产物：public/fonts/noto-serif-sc.woff2
 */
import fs from 'node:fs';
import path from 'node:path';
import subsetFont from 'subset-font';

const ROOT = path.resolve(import.meta.dirname, '..');
const SOURCE = path.join(ROOT, 'assets/fonts/noto-serif-sc-400.woff2');
const TARGET = path.join(ROOT, 'public/fonts/noto-serif-sc.woff2');

/** 需要扫描的文本来源：内容、模板、文案、后台配置 */
const SCAN_DIRS = ['src'];
const SCAN_FILES = ['public/admin/config.yml'];
const EXTS = new Set(['.md', '.astro', '.ts', '.js', '.mjs', '.yml', '.json']);

function walk(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, out);
    else if (EXTS.has(path.extname(entry.name))) out.push(full);
  }
  return out;
}

function collectChars() {
  const chars = new Set();
  const files = SCAN_DIRS.flatMap((d) => walk(path.join(ROOT, d)));
  for (const f of SCAN_FILES) {
    const full = path.join(ROOT, f);
    if (fs.existsSync(full)) files.push(full);
  }
  for (const file of files) {
    const text = fs.readFileSync(file, 'utf8');
    for (const ch of text) {
      const cp = ch.codePointAt(0);
      // 只留非 ASCII：拉丁字母由 Source Serif 4 负责，这里只收中文与全角标点
      if (cp > 0x2000) chars.add(ch);
    }
  }
  return chars;
}

async function main() {
  if (!fs.existsSync(SOURCE)) {
    console.error('[font] 缺少源字体 assets/fonts/noto-serif-sc-400.woff2，跳过子集化');
    process.exit(0);
  }

  const chars = collectChars();
  const text = [...chars].join('');
  const source = fs.readFileSync(SOURCE);
  const subset = await subsetFont(source, text, {
    targetFormat: 'woff2',
    // 不保留 hinting，屏幕渲染用不到，能再省一点
    hinting: false,
  });

  fs.mkdirSync(path.dirname(TARGET), { recursive: true });
  fs.writeFileSync(TARGET, subset);

  const kb = (n) => (n / 1024).toFixed(1);
  console.log(
    `[font] Noto Serif SC 子集：${chars.size} 字 → ${kb(subset.length)}KB（源 ${kb(source.length)}KB）`
  );
}

main().catch((err) => {
  console.error('[font] 子集化失败，回落到系统宋体：', err.message);
  process.exit(0);
});
