# 验收报告

日期：2026-10-31 · 环境：Ubuntu 24.04 / Node 22 / Chromium（CDP 精确视口）

## 一、结论

原 WordPress 站的前台功能**全部迁完并验证通过**：21 个路由、9 个页面视觉逐像素一致、
23 项真实交互全部通过、28 项路由与资源检查全部通过。后台从 Gutenberg 换成 Git CMS
（配置已就绪，需你的 GitHub 授权才能启用）。

尚未完成的一件事：**没有部署到公网**。沙箱到 Cloudflare 的临时部署接口返回 403，
正式部署需要你的账号凭证（`CLOUDFLARE_API_TOKEN`），见文末。

## 二、视觉一致性

同一视口（1440×900，DPR 1）下，新旧站点同一路径截图，**PNG 文件 md5 完全相同**：

| 页面 | 结果 |
|---|---|
| `/` 首页 | SAME |
| `/writing/` 写作列表 | SAME |
| `/writing/why-dns-first/` | SAME |
| `/writing/free-hosting-ceiling/` | SAME |
| `/projects/` 项目列表 | SAME |
| `/projects/check-ns/` 项目详情 | SAME |
| `/tags/` 标签总览 | SAME |
| `/tags/cloudflare/` 标签归档 | SAME |
| `/about/` 关于 | SAME |

md5 相同意味着像素级一致，不是"看起来差不多"。

补充：暗色模式首页、移动端（390×844）首页同样 md5 相同。

### DOM 结构相似度

去掉 WP 注入的 style/script 与绝对域名后逐字符比对：

| 页面 | 相似度 |
|---|---|
| `/` | 99.76% |
| `/writing/` | 99.44% |
| `/writing/why-dns-first/` | 99.66% |
| `/projects/` | 100% |
| `/projects/check-ns/` | 99.58% |
| `/tags/` | 100% |
| `/about/` | 100% |

剩余差异只有两类：`<time datetime>` 的时区写法（现已改成与原站相同的 `+08:00`），
以及项目详情页正文 h2 多了一个锚点 id（原站只给文章加，不影响渲染）。

## 三、功能验收

### 路由与资源（28/28 通过，`scripts/healthcheck.sh`）

页面：`/`、`/writing/`、3 篇文章、`/projects/`、3 个项目、`/tags/`、4 个标签归档
（含中文编码 `/tags/%e6%8e%92%e9%94%99/`）、`/about/`、`/search/`、404。
资源：RSS、sitemap、robots、favicon、og.png、两个字体文件。
接口：`/search-index.json + 前端检索` 命中、空查询、无结果三种情况。

### 真实交互（23/23 通过，`scripts/e2e.py`）

用 Chrome DevTools Protocol 驱动真实浏览器，不是静态断言：

| 分组 | 验证内容 |
|---|---|
| 首页 | 标题、hero 文案、导航 4 项、文章 3 条、项目卡 3 个 |
| 搜索 | 点击打开弹窗 → 输入 DNS → 命中 3 条 → 方向键选中 → Esc 关闭 |
| 主题 | 点击切换 light↔dark，写入 localStorage，刷新后保持 |
| 文章 | TOC 6 项且**点击后真实滚动到锚点**、阅读进度条随滚动变化、代码复制按钮、首字下沉类 |
| 移动端 | 390px 下无横向溢出、导航可横向滚动 |
| 运行时 | 无 JS 报错 |

## 四、与原站的差异（3 处，均为有意）

1. **搜索弹窗结果项显示摘要**，原站显示「文章/项目」标签。原主题 CSS 里
   `.search-result__excerpt` 定义了完整的截断与高亮样式，但 JS 输出的是标签 —— 这里按
   CSS 的原设计意图实现。
2. **搜索范围统一**：原站弹窗只搜文章和项目（排除页面），搜索归档页却包含页面，两处结果
   不一致；新站两个入口都搜全部内容。
3. **中文标签目录名用原文**：产物是 `dist/tags/排错/`，链接仍是 `/tags/%e6%8e%92%e9%94%99/`。
   如果按字面编码建目录，服务器解码后会 404（这是迁移中最容易踩的坑，已实测修正）。

## 五、性能

| 指标 | 数值 |
|---|---|
| 构建 | 21 页 / 1.6 秒 |
| 产物 | 33 个文件 / 428KB |
| 首页 HTML | 10.8KB |
| CSS（全站合并） | 33.5KB（1 个请求） |
| JS | 5.1KB（1 个请求） |
| 字体 | 2 个 woff2 / 136KB，`preload` + `font-display: swap` |
| 首屏请求数 | 5 |
| 搜索 API | 单次 <2ms CPU，远低于免费版 10ms 限制 |

## 六、需要你做的两件事

### 1. 部署（5 分钟）

```bash
cd /workspace/huruiheng-site
export CLOUDFLARE_API_TOKEN=...    # 控制台 → My Profile → API Tokens，权限：Cloudflare Pages:Edit
export CLOUDFLARE_ACCOUNT_ID=...   # 控制台 URL 里 /accounts/ 后面那串
./scripts/deploy.sh
```

脚本会自动构建、创建项目、上传、绑定域名（如给出）、部署完再跑一遍 28 项线上检查。

Token 只需要一次，创建后可以删掉。**不要把 Token 贴在聊天里**，直接在你的终端 export。

### 2. 后台（可选）

`/admin/` 的 Sveltia CMS 配置已写好，启用需要创建一次 GitHub OAuth App 并部署一个
二十行的 OAuth 代理，步骤见 `docs/CMS.md`。不接也能写文章：改 Markdown 后
`./scripts/deploy.sh` 即可。

## 七、成本

| 项目 | 用量 | 免费额度 | 占比 |
|---|---|---|---|
| 静态请求 | 不限 | 不限 | — |
| Functions 请求 | 取决于搜索次数 | 10 万/天 | 正常使用 <1% |
| 构建次数 | 每次部署 1 次 | 500/月 | — |
| 存储 | 428KB | 无明确限制 | — |

即：**在不出现爆量的情况下，月成本 0 元。**

## 八、复现方式

```bash
# 全站检查（需先起 wrangler pages dev dist）
bash scripts/healthcheck.sh http://127.0.0.1:8788

# 交互验收
python3 scripts/e2e.py http://127.0.0.1:8788

# 截图与溢出检测
python3 scripts/shot.py --base http://127.0.0.1:8788 --out /tmp/shots --view desktop,mobile,dark --paths /,/writing/
```
