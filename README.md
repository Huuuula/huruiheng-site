# huruiheng.eu.org · Astro + Cloudflare Pages

WordPress 站点（Hu 的个人站）迁移到静态生成 + 边缘函数的完整实现。
前台视觉与交互与原站逐像素一致（已用 DOM diff 与截图比对验证），后台由 WordPress 换成
Markdown + Git，运行成本为 Cloudflare 免费额度内的 0 元。

## 技术构成

| 层 | 实现 | 说明 |
|---|---|---|
| 页面 | Astro 5 静态生成 | 21 个路由，构建约 1.6 秒，产物 428KB |
| 样式 | 直接复用原主题 CSS | tokens / base / components 共 2274 行，未改写 |
| 交互 | 原生 JS（原 main.js 移植） | 主题切换、搜索弹窗、进度条、目录、代码复制 |
| 搜索 | Pages Functions + 构建期索引 | 索引 9.5KB 内联进函数，单次执行 <2ms CPU |
| 托管 | Cloudflare Pages（免费） | 静态请求不限量，Functions 10 万次/天 |
| 内容 | Markdown + Git | 可选的 Sveltia CMS，见 `docs/CMS.md` |

> 为什么不用 WordPress 运行时：Cloudflare 免费版没有 PHP，Workers 单请求 CPU 上限 10ms，
> 跑不动 WP 启动。前台全部功能都能静态化保留，只有 Gutenberg 后台无法原样迁移。

## 本地运行

```bash
pnpm install
pnpm dev                 # 开发服务器 http://localhost:4321
pnpm build               # 构建到 dist/（含 prebuild 生成索引与 sitemap）
npx wrangler pages dev dist   # 本地跑 Pages Functions，测试 /api/search
```

## 部署

站点是**动静混合**：页面全部预渲染为静态 HTML，搜索走 Pages Functions（`/api/search`）。
前端带自动降级——部署环境没有运行时时自动改用浏览器本地索引，功能不缺失，但失去服务端扩展能力。

| 部署方式 | 页面 | 搜索 | 说明 |
|---|---|---|---|
| B 命令行 `wrangler pages deploy` | 静态 | **Functions 动态** | 当前线上采用，推荐 |
| C Git 自动构建 | 静态 | **Functions 动态** | 可网页改稿，长期推荐 |
| A 网页拖拽上传 | 静态 | 前端本地索引（降级） | 仅在无法用命令行时使用 |

> 线上实例：<https://huruiheng.pages.dev>（方式 B 部署，`/api/search` 为真实动态接口）。

### 方式 A：网页拖拽上传（会降级为纯静态）

```bash
npm run build        # 产出 dist/
```

1. 打开 https://dash.cloudflare.com → **Workers & Pages** → **Create** → **Pages** → **Upload assets**
2. 项目名随意，把 `dist` 目录里的内容（不是 dist 文件夹本身）拖进去
3. Deploy，得到 `https://<project>.pages.dev`

> 注意：不要把 `wrangler.toml`、`_worker.js`、`functions/` 放进上传内容。
> Cloudflare 的上传器见到它们会要求改用 `wrangler deploy`。

### 方式 B：命令行部署（可自动化、可绑域名）

```bash
pnpm install
npx wrangler login                       # 或 export CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID
./scripts/deploy.sh                      # 构建 + 创建项目 + 部署 + 线上复检
```

自定义项目名与域名：

```bash
./scripts/deploy.sh my-site example.com
```

### 方式 C：接 Git 自动部署

把仓库连到 Cloudflare Pages，构建命令 `npm run build`，输出目录 `dist`。
之后每次 push 自动重建，改 Markdown 就等于发布。

部署完成后：

| 入口 | 地址 |
|---|---|
| 前台 | `https://<project>.pages.dev` |
| 搜索 | 页面右上角「搜索」或 `⌘K`（也可直达 `/search/?q=DNS`） |
| RSS | `https://<project>.pages.dev/feed/` |
| 站点地图 | `https://<project>.pages.dev/sitemap.xml` |

绑定自定义域名后，在 Cloudflare Pages 项目 → Settings → Environment variables 添加
`SITE_URL=https://你的域名`，重新构建一次，canonical / OG / sitemap 会自动切换到正式域名。

## 内容编辑

```
src/content/
├── posts/       # 文章 → /writing/<文件名>/
├── projects/    # 项目 → /projects/<文件名>/
└── pages/       # 关于 → /about/
```

新增一篇文章：在 `src/content/posts/` 建 `my-post.md`，

```markdown
---
title: "标题"
date: "2026-11-01"
no: "004"
tags: ["cloudflare", "dns"]
excerpt: "列表页显示的摘要，控制在一行半以内。"
---

正文用 Markdown。`##` 和 `###` 会自动生成目录与锚点，锚点规则与原站一致。
```

文件名即 URL，改文件名等于改链接，**已发布的文件名不要改**。

## 目录结构

```
├── functions/api/search.ts      # Pages Functions：搜索接口
├── functions/_lib/
│   ├── search-core.ts           # 搜索打分逻辑（Pages 与 Worker 共用）
│   └── search-index.json        # 构建期生成的索引（勿手改）
├── src/
│   ├── components/              # Header / Footer / SearchDialog / PostRow / ProjectCard
│   ├── layouts/Base.astro       # head、主题初始化、全站骨架
│   ├── pages/                   # 21 个路由
│   ├── content/                 # Markdown 内容
│   ├── lib/                     # 日期、阅读时间、锚点等与原站一致的格式化规则
│   └── styles/                  # 原主题 CSS，原样复用
├── scripts/
│   ├── build-index.mjs          # 生成搜索索引
│   ├── build-sitemap.mjs        # 生成 sitemap + robots
│   ├── healthcheck.sh           # 28 项路由/资源/API 检查
│   ├── e2e.py                   # 23 项真实交互测试（CDP）
│   ├── shot.py                  # 精确视口截图 + 溢出检测
│   └── deploy.sh                # 一键部署
└── wrangler.toml                # Pages 配置
```

## 与原站的一致性

| 项目 | 状态 |
|---|---|
| 页面结构（DOM） | 7 个页面相似度 99.4%–100%，差异仅为 `<time datetime>` 时区写法 |
| 视觉 | 桌面/暗色/移动端截图与原站逐像素一致（PNG md5 相同） |
| 固定链接 | `/writing/<slug>/`、`/projects/<slug>/`、`/tags/<中文编码>/` 全部保持 |
| 文章锚点 | `h-<小写 urlencode>` 规则与 WP `sanitize_title()` 完全一致，目录可跳转 |
| 搜索 | 关键词「DNS」返回 3 条，顺序与原站一致 |
| RSS | `/feed/` 兼容，另生成 `/feed.xml` |
| 阅读时间 | 350 字/分钟向上取整，与原文数字一致（6/5/7 分钟） |

唯一有意的偏差：搜索弹窗的结果项显示摘要，原站显示「文章/项目」标签。CSS 里
`.search-result__excerpt` 有完整的截断与高亮样式，但原主题 JS 输出的是标签 —— 这里按
CSS 的原设计意图实现，信息量更大。

## 常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| 内页 404 | 构建产物没带尾斜杠 | 确认 `trailingSlash: 'always'`，访问 `/writing/xxx/` 而非 `/writing/xxx` |
| 中文标签页 404 | 产物目录名被写成 `%e6...` | 目录必须是中文原文，链接才用编码（本项目已按此实现） |
| 搜索 500 | Functions 未随静态资源部署 | 确认 `functions/` 在项目根目录，重新 `wrangler pages deploy dist` |
| 样式全丢 | `SITE_URL` 与实际域名不一致 | 样式用的是绝对根路径 `/fonts/...`，域名变化不影响；检查 `_astro/` 是否上传 |
| 部署报 403 | Token 权限不足 | Token 需要 `Cloudflare Pages:Edit` + `Account:Read` |
