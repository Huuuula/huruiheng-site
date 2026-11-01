#!/usr/bin/env python3
"""把 WordPress WXR 导出转换成 Astro 内容集合（Markdown + frontmatter）。

用法：python3 scripts/import-wxr.py <content-export.xml> <src/content>
"""
import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

WXR = Path(sys.argv[1] if len(sys.argv) > 1 else "content-export.xml")
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "src/content")
NS = {
    "wp": "http://wordpress.org/export/1.2/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "excerpt": "http://wordpress.org/export/1.2/excerpt/",
}


def clean_html(html: str) -> str:
    html = re.sub(r"<!--\s*/?wp:.*?-->", "", html, flags=re.S)
    return html.strip()


def inline(node) -> str:
    """行内元素转 Markdown。"""
    if isinstance(node, NavigableString):
        return re.sub(r"\s+", " ", str(node))
    if not isinstance(node, Tag):
        return ""
    name = node.name
    inner = "".join(inline(c) for c in node.children)
    if name in ("strong", "b"):
        return f"**{inner.strip()}**"
    if name in ("em", "i"):
        return f"*{inner.strip()}*"
    if name == "code":
        return f"`{inner.strip()}`"
    if name == "a":
        href = node.get("href", "")
        return f"[{inner.strip()}]({href})" if href else inner
    if name == "br":
        return "  \n"
    if name in ("span", "sup", "sub", "mark", "del", "s"):
        return inner
    return inner


def block(node, depth: int = 0) -> str:
    """块级元素转 Markdown，表格保留 HTML 以保证还原度。"""
    if isinstance(node, NavigableString):
        text = str(node).strip()
        return text + "\n\n" if text else ""
    if not isinstance(node, Tag):
        return ""

    name = node.name
    if name in ("script", "style"):
        return ""
    if name == "p":
        text = inline(node).strip()
        return text + "\n\n" if text else ""
    if name in ("h1", "h2", "h3", "h4"):
        level = int(name[1])
        return f"{'#' * level} {inline(node).strip()}\n\n"
    if name == "blockquote":
        body = "".join(block(c, depth) for c in node.children).strip()
        return "\n".join("> " + line if line else ">" for line in body.splitlines()) + "\n\n"
    if name in ("ul", "ol"):
        ordered = name == "ol"
        lines = []
        for i, li in enumerate(node.find_all("li", recursive=False), 1):
            # li 里可能有嵌套列表，先取直接文本
            text_parts = []
            nested = []
            for child in li.children:
                if isinstance(child, Tag) and child.name in ("ul", "ol"):
                    nested.append(block(child, depth + 1))
                else:
                    text_parts.append(inline(child) if isinstance(child, Tag) else str(child))
            text = re.sub(r"\s+", " ", "".join(text_parts)).strip()
            prefix = f"{i}." if ordered else "-"
            lines.append(f"{'  ' * depth}{prefix} {text}")
            for n in nested:
                lines.append(n.rstrip())
        return "\n".join(lines) + "\n\n"
    if name == "pre":
        code = node.get_text()
        lang = ""
        cls = " ".join(node.get("class", []))
        m = re.search(r"language-([\w-]+)", cls)
        if m:
            lang = m.group(1)
        return f"```{lang}\n{code.rstrip()}\n```\n\n"
    if name == "table":
        table = str(node)
        table = re.sub(r"<!--\s*/?wp:.*?-->", "", table, flags=re.S)
        return table.strip() + "\n\n"
    if name == "figure":
        return "".join(block(c, depth) for c in node.children).strip() + "\n\n"
    if name == "img":
        src = node.get("src", "")
        alt = node.get("alt", "")
        return f"![{alt}]({src})\n\n" if src else ""
    if name == "hr":
        return "---\n\n"
    # 未知容器：递归
    return "".join(block(c, depth) for c in node.children)


def html_to_md(html: str) -> str:
    soup = BeautifulSoup(clean_html(html), "html.parser")
    out = "".join(block(c) for c in soup.children)
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    return out + "\n"


def yaml_value(v) -> str:
    if isinstance(v, list):
        return "[" + ", ".join(json.dumps(x, ensure_ascii=False) for x in v) + "]"
    return json.dumps(v, ensure_ascii=False)


def frontmatter(data: dict) -> str:
    lines = ["---"]
    for k, v in data.items():
        lines.append(f"{k}: {yaml_value(v)}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def text_of(html: str) -> str:
    return re.sub(r"\s+", "", BeautifulSoup(html, "html.parser").get_text())


def main() -> None:
    from xml.etree import ElementTree as ET

    channel = ET.parse(WXR).getroot().find("channel")
    counts = {"post": 0, "project": 0, "page": 0}
    for item in channel.findall("item"):
        ptype = item.findtext("wp:post_type", namespaces=NS)
        status = item.findtext("wp:status", namespaces=NS)
        if status != "publish" or ptype not in counts:
            continue
        title = item.findtext("title") or ""
        slug = item.findtext("wp:post_name", namespaces=NS) or ""
        date = (item.findtext("wp:post_date", namespaces=NS) or "")[:10]
        body = item.findtext("content:encoded", namespaces=NS) or ""
        excerpt = item.findtext("excerpt:encoded", namespaces=NS) or ""
        md = html_to_md(body)

        data = {"title": title, "date": date, "excerpt": BeautifulSoup(excerpt, "html.parser").get_text().strip()}
        folder = OUT / {"post": "posts", "project": "projects", "page": "pages"}[ptype]

        if ptype == "post":
            tags = [
                c.text
                for c in item.findall("category")
                if c.get("domain") == "post_tag" and c.text not in (None, "未分类")
            ]
            no = ""
            for m in item.findall("wp:postmeta", namespaces=NS):
                if m.findtext("wp:meta_key", namespaces=NS) == "no":
                    no = m.findtext("wp:meta_value", namespaces=NS) or ""
            data = {
                "title": title,
                "date": date,
                "no": no,
                "tags": tags,
                "excerpt": data["excerpt"] or text_of(body)[:80],
            }
        elif ptype == "project":
            meta = {
                m.findtext("wp:meta_key", namespaces=NS): m.findtext("wp:meta_value", namespaces=NS)
                for m in item.findall("wp:postmeta", namespaces=NS)
            }
            data = {
                "title": title,
                "date": date,
                "no": meta.get("no", ""),
                "summary": meta.get("summary", ""),
                "status": meta.get("status", ""),
                "stack": [s.strip() for s in (meta.get("stack") or "").split(",") if s.strip()],
                "period": meta.get("period", ""),
                "link": meta.get("link", ""),
                "excerpt": data["excerpt"] or meta.get("summary", ""),
            }
        else:
            data["slug"] = slug

        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{slug}.md").write_text(frontmatter(data) + md, encoding="utf-8")
        counts[ptype] += 1
        print(f"  {ptype:8} {slug:36} {len(md):6} bytes")

    print(f"\n完成：{counts}")


if __name__ == "__main__":
    main()
