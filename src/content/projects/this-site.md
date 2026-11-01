---
title: "本站 huruiheng.eu.org"
date: "2026-10-31"
no: "01"
summary: "Astro 静态生成，输出纯 HTML 与 CSS，无前端框架、统计脚本和第三方请求。托管 Cloudflare Pages 免费档。"
status: "维护中"
stack: ["astro", "css", "cloudflare pages"]
period: "2026"
link: "https://huruiheng.eu.org"
excerpt: "Astro 静态生成，输出纯 HTML 与 CSS，无前端框架、统计脚本和第三方请求。托管 Cloudflare Pages 免费档。"
---

这个站用 Astro 静态生成，构建产物就是纯 HTML 和一份 CSS。没有前端框架，没有统计脚本，页面加载时不发出任何第三方请求。

中文正文刻意不加载 webfont，直接用系统宋体栈，省掉字体文件那几百 KB。托管在 Cloudflare Pages 免费档，域名 huruiheng.eu.org 来自 eu.org 的免费二级域。整站没有服务端逻辑，文章和项目数据都在构建时写进页面。

视觉方向经历过一次重做。最早是杂志编辑风，细线、密排、黑白的刊物感；后来整体改成暖米白底、白色卡片、大圆角的风格，强调色换成赭橙。改版只动了样式层，页面结构和内容没有重写。

现在维护的重点是内容和细节：文章编号手工维护，补旧文时插在中间不影响已有编号；样式集中在 components.css，组件只引用类名，不写内联样式。

## 要点

- 无框架、无统计、无第三方请求
- 中文正文不加载 webfont
- Cloudflare Pages 免费档托管
- 一次视觉重做，只改样式层
