/**
 * 与 WordPress 主题保持完全一致的格式化规则。
 * 任何改动都会导致与原站出现可见差异，改动前先对照 _baseline。
 */

/** 2026.10.31 —— 原站用点分隔，UTC 取值避免时区漂移 */
export function formatDate(d: Date): string {
  const y = d.getUTCFullYear();
  const m = String(d.getUTCMonth() + 1).padStart(2, '0');
  const day = String(d.getUTCDate()).padStart(2, '0');
  return `${y}.${m}.${day}`;
}

/** 归档页用的年份 */
export function yearOf(d: Date): string {
  return String(d.getUTCFullYear());
}

/**
 * <time datetime> 用的 ISO 串。
 * 原站输出 2026-10-31T08:00:00+08:00（WP 按 UTC 零点存、+08:00 显示），
 * 这里保持逐字一致，避免结构化数据出现时区漂移。
 */
export function isoDateTime(d: Date): string {
  return `${d.toISOString().slice(0, 10)}T08:00:00+08:00`;
}

/** 去掉空白后按 350 字/分钟向上取整，最小 1 —— 对应 hrh_reading_time() */
export function readingTime(plain: string): number {
  const chars = plain.replace(/\s+/gu, '').length;
  return Math.max(1, Math.ceil(chars / 350));
}

/**
 * 标题锚点：h-<小写 urlencode>，空格转连字符。
 * 对应 WP sanitize_title()，例如「提交时它查了 12 个地址」
 * → h-%e6%8f%90%e4%ba%a4%e6%97%b6%e5%ae%83%e6%9f%a5%e4%ba%86-12-%e4%b8%aa%e5%9c%b0%e5%9d%80
 */
export function headingId(text: string): string {
  return 'h-' + encodeURIComponent(text.trim().replace(/\s+/gu, '-')).toLowerCase();
}

/** 标签路由片段：中文按小写百分号编码，与 WP 输出一致 */
export function tagSlug(tag: string): string {
  return encodeURIComponent(tag).toLowerCase();
}

/** 中文数字：文章编号 No. 003 */
export function padNo(no: string | undefined, fallback: number): string {
  if (no && no.trim() !== '') return no.trim();
  return String(fallback).padStart(3, '0');
}

/** 从 markdown 里粗略抽纯文本，用于阅读时间 */
export function stripMarkdown(md: string): string {
  return md
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`[^`]*`/g, ' ')
    .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/[*_>~|-]/g, ' ');
}
