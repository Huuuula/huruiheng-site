/**
 * 摘要与阅读时间。原主题用 wp_strip_all_tags() + 按字符截断，超出补「…」；
 * 纯文本抽取复用 reading.ts（它的字数与原站 wp_trim_words 一致）。
 */
import { readMinutes } from './reading';

/** 压成单行纯文本，给摘要 / 导语用（保留下划线，check_ns.py 这类名字不能被吃掉） */
export function plainSummary(markdown: string): string {
  return markdown
    .replace(/^```.*$/gm, ' ')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/<[^>]+>/g, ' ')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/^\s*>\s?/gm, '')
    .replace(/^\s*[-*+]\s+/gm, '')
    .replace(/\*/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

/** 按字符数截断，超出补省略号 */
export function clampChars(text: string, limit: number): string {
  const chars = Array.from(text);
  return chars.length > limit ? chars.slice(0, limit).join('') + '…' : text;
}

/** 文章摘要：优先手写 excerpt，否则从正文提炼 */
export function excerptOf(
  data: { excerpt?: string },
  body: string | undefined,
  limit: number,
): string {
  const source = data.excerpt?.trim() ? data.excerpt : plainSummary(body ?? '');
  return clampChars(source.replace(/\s+/g, ' ').trim(), limit);
}

/** 阅读时间，供列表页直接使用 */
export function minutesOf(body: string | undefined): number {
  return readMinutes(body ?? '');
}
