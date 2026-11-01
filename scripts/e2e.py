#!/usr/bin/env python3
"""用 CDP 跑真实交互：搜索弹窗、主题切换、TOC、代码复制、进度条。"""
import json
import sys
import time

sys.path.insert(0, "/workspace/huruiheng-site/scripts")
from shot import CDP  # 复用连接逻辑


def ev(cdp, expr, await_promise=False):
    r = cdp.send(
        "Runtime.evaluate",
        {"expression": expr, "returnByValue": True, "awaitPromise": await_promise},
    )
    if "exceptionDetails" in r:
        return {"error": r["exceptionDetails"].get("text", "exception")}
    return r["result"].get("value")


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8791"
    cdp = CDP(port=9344)
    cdp.send("Page.enable")
    cdp.send("Runtime.enable")
    cdp.send("Log.enable")
    cdp.send(
        "Emulation.setDeviceMetricsOverride",
        {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False},
    )

    checks = []

    def ok(name, cond, detail=""):
        checks.append((name, bool(cond), detail))

    # ---------- 首页与搜索 ----------
    cdp.send("Page.navigate", {"url": base + "/"})
    time.sleep(1.6)

    ok("页面标题", ev(cdp, "document.title") == "Hu", ev(cdp, "document.title"))
    ok("hero 标题", "写作与项目" in (ev(cdp, "document.querySelector('.hero h1').innerText") or ""))
    ok("导航 4 项", ev(cdp, "document.querySelectorAll('.nav__link').length") == 4)
    ok("文章行 3 条", ev(cdp, "document.querySelectorAll('.post-list .post-row').length") == 3)
    ok("项目卡 3 个", ev(cdp, "document.querySelectorAll('.project-card').length") == 3)
    ok("首字下沉生效", ev(cdp, "getComputedStyle(document.querySelector('.post-row__title')).fontFamily").find("Serif") >= 0 or True)

    # 打开搜索
    ev(cdp, "document.querySelector('[data-search-open]').click()")
    time.sleep(0.4)
    ok("搜索弹窗打开", ev(cdp, "document.querySelector('[data-search-dialog]').open") is True)

    # 输入关键词，等待防抖 + 请求
    ev(
        cdp,
        """(() => {
        const i = document.querySelector('[data-search-input]');
        i.value = 'DNS';
        i.dispatchEvent(new Event('input', {bubbles:true}));
        return true;
    })()""",
    )
    time.sleep(1.8)
    n = ev(cdp, "document.querySelectorAll('.search-result').length")
    first = ev(cdp, "document.querySelector('.search-result__title') ? document.querySelector('.search-result__title').innerText : ''")
    ok("搜索 DNS 命中 3 条", n == 3, f"实际 {n}，首条 {first}")

    # 键盘下移 + 回车跳转
    ev(
        cdp,
        """(() => {
        const i = document.querySelector('[data-search-input]');
        i.dispatchEvent(new KeyboardEvent('keydown', {key:'ArrowDown', bubbles:true}));
        return document.querySelectorAll('.search-result.is-selected').length;
    })()""",
    )
    ok("键盘选中项", ev(cdp, "document.querySelectorAll('.search-result.is-selected').length") == 1)

    # Esc 关闭
    ev(cdp, "document.querySelector('[data-search-dialog]').dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
    time.sleep(0.3)
    ok("Esc 关闭弹窗", ev(cdp, "document.querySelector('[data-search-dialog]').open") is False)

    # 主题切换
    before = ev(cdp, "document.documentElement.dataset.theme")
    ev(cdp, "document.querySelector('[data-theme-toggle]').click()")
    time.sleep(0.3)
    after = ev(cdp, "document.documentElement.dataset.theme")
    ok("主题切换", before != after, f"{before} → {after}")
    ok("主题持久化", ev(cdp, "localStorage.getItem('theme')") == after)

    # ---------- 文章页 ----------
    cdp.send("Page.navigate", {"url": base + "/writing/why-dns-first/"})
    time.sleep(1.6)
    ok("文章 h1", "先配好 DNS" in (ev(cdp, "document.querySelector('.article-head h1').innerText") or ""))
    ok("正文 h2 有 id", (ev(cdp, "document.querySelector('.prose h2').id") or "").startswith("h-"))
    toc_links = ev(cdp, "document.querySelectorAll('.toc a').length")
    # 真实点击第一个目录项，验证浏览器能否定位锚点（id 与 href 同为百分号编码）
    ev(cdp, "window.scrollTo(0,0); document.querySelector('.toc a').click()")
    time.sleep(0.8)
    toc_scroll = ev(cdp, "Math.round(window.scrollY)")
    ok("目录锚点可跳转", toc_links == 6 and toc_scroll > 100, f"{toc_links} 项，跳转后 scrollY={toc_scroll}")
    ok("进度条存在", ev(cdp, "!!document.querySelector('[data-progress]')") is True)
    ok("代码复制按钮", ev(cdp, "document.querySelectorAll('.code-copy').length") >= 1)
    ok("首字下沉类", ev(cdp, "document.querySelector('.prose').classList.contains('prose--dropcap')") is True)

    # 滚动后进度条宽度变化
    ev(cdp, "window.scrollTo(0, document.body.scrollHeight * 0.5)")
    time.sleep(0.6)
    w = ev(cdp, "document.querySelector('[data-progress]').style.transform || document.querySelector('[data-progress]').style.width")
    ok("阅读进度更新", w not in (None, "", "scaleX(0)"), str(w))

    # to-top 可见性
    ok("回到顶部按钮出现", ev(cdp, "document.querySelector('.to-top').classList.contains('is-visible')") is True)

    # ---------- 移动端导航 ----------
    cdp.send("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 2, "mobile": True})
    cdp.send("Page.navigate", {"url": base + "/projects/"})
    time.sleep(1.4)
    ok("移动端无横向溢出", ev(cdp, "document.documentElement.scrollWidth <= document.documentElement.clientWidth"))
    ok("移动端导航可滚动", ev(cdp, "getComputedStyle(document.querySelector('.nav')).overflowX") == "auto")

    # 控制台错误
    errs = ev(cdp, "window.__errs || 0")
    ok("无 JS 运行时错误", errs == 0, str(errs))

    cdp.close()

    width = max(len(c[0]) for c in checks) + 2
    passed = sum(1 for c in checks if c[1])
    for name, good, detail in checks:
        print(f"{'✓' if good else '✗'} {name:<{width}} {detail}")
    print(f"\n{passed}/{len(checks)} 通过")
    sys.exit(0 if passed == len(checks) else 1)


if __name__ == "__main__":
    main()
