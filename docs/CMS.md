# 后台：Git CMS 接入说明

WordPress 后台无法在 Cloudflare 免费版运行（没有 PHP）。替代方案是 Git CMS：
在浏览器里写 Markdown、传图、保存，内容以 commit 形式进仓库，触发重新构建。

当前 `/admin/` 已经接好 [Sveltia CMS](https://github.com/sveltia/sveltia-cms)（Decap/Netlify CMS 的现代替代，
免费、体积小、支持中文界面）。**它需要在你的 GitHub 仓库上启用一次 OAuth，才能写入文件。**

## 为什么需要 OAuth 代理

浏览器里的 CMS 要直接调 GitHub API 提交 commit，必须有 access token。GitHub 的网页授权
不允许纯前端换取 token（client_secret 不能暴露在浏览器里），所以需要一个几十行的代理
交换 code。这个代理跑在 Cloudflare Workers 免费版上，不产生费用。

## 三步启用

### 1. 创建 GitHub OAuth App

打开 <https://github.com/settings/developers> → New OAuth App：

| 字段 | 值 |
|---|---|
| Application name | `huruiheng-cms` |
| Homepage URL | `https://你的站点域名` |
| Authorization callback URL | `https://huruiheng-auth.<你的子域>.workers.dev/callback` |

记下 **Client ID** 与 **Client Secret**。

### 2. 部署 OAuth 代理

```bash
git clone https://github.com/sveltia/sveltia-cms-auth
cd sveltia-cms-auth
npm install
npx wrangler deploy
npx wrangler secret put GITHUB_CLIENT_ID       # 粘贴上一步的 Client ID
npx wrangler secret put GITHUB_CLIENT_SECRET   # 粘贴 Client Secret
```

部署后会得到一个 `https://sveltia-cms-auth.<子域>.workers.dev` 地址。
编辑 `wrangler.toml` 里的 `ALLOWED_DOMAINS`，填你的站点域名（多个用逗号分隔）。

### 3. 填写配置并部署站点

编辑 `public/admin/config.yml` 顶部两行：

```yaml
backend:
  name: github
  repo: 你的GitHub用户名/huruiheng-site
  branch: main
  base_url: https://sveltia-cms-auth.<你的子域>.workers.dev
```

然后重新部署站点：

```bash
./scripts/deploy.sh
```

访问 `https://你的域名/admin/`，用 GitHub 登录即可编辑。

## 用起来是什么样

| 原来的 WordPress 操作 | 现在的做法 |
|---|---|
| 新建文章 | 后台「文章 → New」，填标题/日期/标签/摘要/正文 |
| 上传图片 | 编辑器里直接拖入，文件进 `public/uploads/`，自动插入 `/uploads/xx.png` |
| 草稿 | Sveltia 的 Draft 状态存在浏览器；要真正暂存就开一个分支 |
| 定时发布 | 写 `date` 为未来日期，构建时过滤（需在模板里加一行判断） |
| 修订历史 | 每次保存是一个 Git commit，可 diff、可回滚 |
| 发布 | 保存即提交，Cloudflare Pages 自动重新构建（约 1 分钟） |

## 不接 GitHub 也能改内容

CMS 只是便利层。内容本质是 Markdown 文件：

```bash
# 1. 本地改 src/content/posts/xxx.md
# 2. 预览
pnpm dev
# 3. 发布
./scripts/deploy.sh
```

缺点是没有网页端编辑，优点是零依赖、零配置、不依赖任何第三方授权。

## 如果以后要「完全在 Cloudflare 内」的后台

可以不用 GitHub：Pages Functions + D1 存内容 + R2 存图片 + Cloudflare Access 做登录，
做一个自定义的轻量后台。代价是要自己实现编辑器与发布流程，工作量约为当前 CMS 方案的 10 倍，
且会失去 Git 版本历史。除非有强需求，不建议。
