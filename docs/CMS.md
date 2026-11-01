# 后台：Git CMS 接入说明

WordPress 后台跑不了 Cloudflare 免费版（没有 PHP）。替代方案是 Git CMS：
在浏览器里写 Markdown、传图、保存，内容以 commit 形式进仓库，触发重新构建。

`/admin/` 接的是 [Sveltia CMS](https://github.com/sveltia/sveltia-cms)（Decap/Netlify CMS 的现代替代，
免费、体积小、中文界面）。

## 架构：为什么 OAuth 端点在站点自己身上

浏览器里的 CMS 要调 GitHub API 提交 commit，必须有 access token。
GitHub 不允许纯前端换 token（client_secret 不能出现在浏览器里），所以需要一个中转：

```
/admin/ 点登录
  → https://huruiheng.pages.dev/auth        （本站 Pages Function）
  → github.com/login/oauth/authorize
  → https://huruiheng.pages.dev/callback    （本站 Pages Function，换 token）
  → postMessage 把 token 交给 /admin/
```

**没有用 Sveltia 官方那个 workers.dev 代理**，因为 `*.workers.dev` 在境内被 DNS 污染，
解析到无关的境外 IP，浏览器根本打不开登录弹窗。放在站点同域下，走 pages.dev 这条能通的链路。

两个端点就在仓库里：

| 文件 | 作用 |
|---|---|
| `functions/auth.ts` | 生成 state、写 HttpOnly Cookie、302 到 GitHub |
| `functions/callback.ts` | 校验 state、换 access token、postMessage 交回 |
| `functions/_lib/oauth.ts` | 握手页面与 Cookie 读取 |

token 只在回调那一次响应里出现：不落日志、不进 Cookie、不写仓库。

## 两条登录路径

`/admin/` 登录页上有两个按钮，各自独立，任一条能用就能进去。

### 路径 A：访问令牌（零配置，实测可用）

「Sign In Using Access Token」→ 粘贴一个 GitHub Personal Access Token。

- 需要权限：classic token 勾 `repo`；fine-grained token 给目标仓库 `Contents: Read and write`
- token 存在浏览器 localStorage，同一个浏览器下次免输；换设备要重新粘
- **不依赖 GitHub OAuth App 的任何配置**，所以不会碰到下面那个回调地址的坑
- 手机端最省事，但粘贴长串令牌略麻烦

### 路径 B：GitHub 授权（体验好，但要求回调地址完全一致）

「Sign In with GitHub」→ 跳 GitHub 授权 → 回调换 token → 自动登录，之后长期免登录。

这条要求 GitHub 上登记的回调地址与 `/auth` 发出的 `redirect_uri`
**逐字符相同**（协议、域名、路径、结尾斜杠都算）。

当前 `/auth` 发出的值固定是：

```
https://huruiheng.pages.dev/callback
```

不一致时的报错长这样：

> **Be careful!** The `redirect_uri` is not associated with this application.

意思是「这个回调地址没有登记在这个应用下」，改登记值即可，代码不用动。

| 你创建的是 | 去哪里改 |
|---|---|
| **OAuth App** | Settings → Developer settings → OAuth Apps → `huruiheng-cms` → **Authorization callback URL** |
| **GitHub App** | Settings → Developer settings → GitHub Apps → `huruiheng-cms` → 左侧 **Identifying and authorizing users** → **Callback URL** |

两者外观很像，用 client ID 前缀分不出来，进去看到哪个界面就改哪个。
GitHub App 还需要把同一个应用 **Install** 到 `Huuuula/huruiheng-site` 仓库，否则拿到的 token 没有仓库权限。

## 已经配好的东西

**GitHub OAuth App**：`huruiheng-cms`（Client ID 与 Secret 见仓库外的 `CREDENTIALS.md`）

| 字段 | 应当填的值 |
|---|---|
| Homepage URL | `https://huruiheng.pages.dev` |
| Authorization callback URL | `https://huruiheng.pages.dev/callback` |

**Cloudflare Pages 环境变量**（生产）：

| 名称 | 类型 | 说明 |
|---|---|---|
| `GITHUB_CLIENT_ID` | secret_text | 明文写不进去，见下方「环境变量的坑」 |
| `GITHUB_CLIENT_SECRET` | secret_text | |
| `ALLOWED_DOMAINS` | secret_text | `huruiheng.pages.dev,localhost` |

`ALLOWED_DOMAINS` 决定哪个来源能收到 token，换正式域名时要把它加进去。

### 环境变量的坑

Cloudflare 的 `PATCH /pages/projects/{name}` 接受 `type: plain_text`，接口也返回成功，
但**函数运行时 `env` 里读不到**——表现是 `/auth` 恒返回 `MISSING_CONFIG`。
三个变量全部设成 `secret_text` 才生效。改完还必须重新部署一次，变量才会注入新版本。
排查时可以在 `functions/api/` 下临时放一个只回 `Object.keys(env)` 的探针。

## 外部依赖

编辑器主体已自托管在 `public/admin/vendor/sveltia-cms.js`（2.6MB，MIT 许可，仅后台加载）。
页面里仍保留 unpkg 作兜底，顺序是「先本地，本地失败才走 CDN」——
原来只引 unpkg，那个域名在境内时通时不通，一旦挂掉整个后台白屏，报错只有一行脚本加载失败，很难判断。

Sveltia 运行时还会从 `cdn.jsdelivr.net` 拉两个字体（Source Sans 3、Material Symbols Outlined）。
字体拿不到只是图标退化成文字（按钮上出现 `article`、`photo` 这类词），不影响登录和保存。

## 改域名时要做三件事

1. `public/admin/config.yml` 的 `base_url` 改成新域名
2. GitHub OAuth App 的 Homepage 与 callback 改成新域名
3. Pages 环境变量 `ALLOWED_DOMAINS` 加上新域名

## 用起来是什么样

| 原来的 WordPress 操作 | 现在的做法 |
|---|---|
| 新建文章 | 后台「文章 → New」，填标题/日期/标签/摘要/正文 |
| 上传图片 | 编辑器里直接拖入，文件进 `public/uploads/`，自动插入 `/uploads/xx.png` |
| 草稿 | Sveltia 的 Draft 状态存在浏览器；要真正暂存就开一个分支 |
| 修订历史 | 每次保存是一个 Git commit，可 diff、可回滚 |
| 发布 | 保存即提交，GitHub Actions 自动构建部署（约 30 秒） |

## 不接 GitHub 也能改内容

CMS 只是便利层。内容本质是 Markdown 文件：

```bash
# 1. 本地改 src/content/posts/xxx.md
# 2. 预览
pnpm dev
# 3. 发布
git push
```

缺点是没有网页端编辑，优点是零依赖、零配置、不依赖任何第三方授权。

## 如果以后要「完全在 Cloudflare 内」的后台

可以不用 GitHub：Pages Functions + D1 存内容 + R2 存图片 + Cloudflare Access 做登录，
做一个自定义的轻量后台。代价是要自己实现编辑器与发布流程，工作量约为当前方案的 10 倍，
且会失去 Git 版本历史。除非有强需求，不建议。
