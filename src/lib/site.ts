/**
 * 站点常量。改域名只需改 SITE_URL 环境变量，其余引用这里。
 */
export const SITE = {
  name: 'Hu',
  brand: 'Hu',
  tagline: '写作与项目',
  desc: 'Hu 的个人站。技术笔记、排错记录，和一些做出来的东西。',
  email: 'hi@huruiheng.eu.org',
  nav: [
    { label: '写作', href: '/writing/' },
    { label: '项目', href: '/projects/' },
    { label: '标签', href: '/tags/' },
    { label: '关于', href: '/about/' },
  ],
  /** 每页最多显示的条目数 */
  perPage: 50,
} as const;

/** 绝对 URL 拼装，避免各处重复 new URL */
export function abs(path: string, base: URL | string): string {
  return new URL(path, base).href;
}
