#!/usr/bin/env python3
"""
用 CDP 精确截图 + 溢出检测。

命令行参数 --window-size 在 headless 下不可靠（实测被忽略，退化为 800 宽），
这里改成 Emulation.setDeviceMetricsOverride，才能真正按移动端宽度渲染。

用法：
  python3 scripts/shot.py --base http://127.0.0.1:8080 --out /workspace/qa/shots \
      --view desktop,mobile,dark --paths /,/writing/
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import time

import websocket

CHROME = "chromium"


class CDP:
    def __init__(self, port=9333):
        self.port = port
        self.proc = subprocess.Popen(
            [
                CHROME,
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                f"--remote-debugging-port={port}",
                "--remote-allow-origins=*",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.ws = None
        self.id = 0
        self._connect()

    def _connect(self):
        import urllib.request

        for _ in range(60):
            try:
                data = json.load(urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json"))
                pages = [p for p in data if p.get("type") == "page"]
                if pages:
                    self.ws = websocket.create_connection(pages[0]["webSocketDebuggerUrl"], timeout=30)
                    return
            except Exception:
                pass
            time.sleep(0.25)
        raise RuntimeError("无法连接 Chromium CDP")

    def send(self, method, params=None):
        self.id += 1
        self.ws.send(json.dumps({"id": self.id, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.id:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def close(self):
        try:
            self.ws.close()
        finally:
            self.proc.terminate()


VIEWPORTS = {
    "desktop": (1440, 1000, 1, False),
    "mobile": (390, 844, 2, True),
    "tablet": (820, 1180, 2, True),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8080")
    ap.add_argument("--out", default="/workspace/qa/shots")
    ap.add_argument("--paths", default="/")
    ap.add_argument("--view", default="desktop")
    ap.add_argument("--full", action="store_true", help="整页截图而非首屏")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    cdp = CDP()
    cdp.send("Page.enable")
    cdp.send("Runtime.enable")

    results = []
    for view in args.view.split(","):
        dark = view == "dark"
        key = "desktop" if dark else view
        w, h, dpr, mobile = VIEWPORTS[key]
        cdp.send(
            "Emulation.setDeviceMetricsOverride",
            {"width": w, "height": h, "deviceScaleFactor": dpr, "mobile": mobile},
        )
        cdp.send(
            "Emulation.setEmulatedMedia",
            {"features": [{"name": "prefers-color-scheme", "value": "dark" if dark else "light"}]},
        )

        for path in args.paths.split(","):
            url = args.base.rstrip("/") + path
            cdp.send("Page.navigate", {"url": url})
            time.sleep(1.4)

            # 溢出检测：找出超出视口右边界的元素
            expr = """(() => {
              const vw = document.documentElement.clientWidth;
              const bad = [];
              document.querySelectorAll('body *').forEach(el => {
                const r = el.getBoundingClientRect();
                if (r.width > 0 && (r.right > vw + 1 || r.left < -1)) {
                  const cls = typeof el.className === 'string' ? el.className : '';
                  bad.push(el.tagName.toLowerCase() + (cls ? '.' + cls.trim().split(/\\s+/).join('.') : '') +
                           ' [w=' + Math.round(r.width) + ',right=' + Math.round(r.right) + ']');
                }
              });
              return JSON.stringify({
                vw, sw: document.documentElement.scrollWidth,
                overflow: bad.slice(0, 6), count: bad.length,
                title: document.title
              });
            })()"""
            info = json.loads(cdp.send("Runtime.evaluate", {"expression": expr, "returnByValue": True})["result"]["value"])

            params = {"format": "png", "captureBeyondViewport": args.full}
            if args.full:
                metrics = cdp.send("Page.getLayoutMetrics")
                ch = metrics["cssContentSize"]["height"]
                params["clip"] = {"x": 0, "y": 0, "width": w, "height": min(ch, 20000), "scale": 1}

            shot = cdp.send("Page.captureScreenshot", params)
            name = f"{view}-{path.strip('/').replace('/', '-') or 'home'}.png"
            with open(os.path.join(args.out, name), "wb") as f:
                f.write(base64.b64decode(shot["data"]))

            results.append((name, info))

    cdp.close()

    print(f"{'file':46} {'vw':>4} {'sw':>5}  overflow")
    bad_total = 0
    for name, info in results:
        flag = "OK" if info["count"] == 0 else f"!{info['count']}"
        bad_total += info["count"]
        print(f"{name:46} {info['vw']:>4} {info['sw']:>5}  {flag}")
        for o in info["overflow"]:
            print(f"    └ {o}")
    sys.exit(0)


if __name__ == "__main__":
    main()
