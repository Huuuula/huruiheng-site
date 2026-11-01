/**
 * 纯文本抽取与阅读时间。原站用 wp_strip_all_tags(the_content) 计数：
 * 代码块里的字也算数，所以这里只去掉围栏行、保留代码内容。
 */
import { readingTime } from './format';

export function plainText(markdown: string): string {
  return markdown
    .replace(/^```.*$/gm, '')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/<[^>]+>/g, ' ')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/^\s*>\s?/gm, '')
    .replace(/^\s*[-*+]\s+/gm, '')
    .replace(/^\s*\d+\.\s+/gm, '')
    .replace(/[*_~|]/g, '');
}

/** 阅读时间：按纯文字字数计算，最小 1 分钟 */
export function readMinutes(markdown: string): number {
  return readingTime(plainText(markdown));
}
