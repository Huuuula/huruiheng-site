#!/usr/bin/env python3
"""WordPress WXR 导出 → Astro 内容集合（Markdown + frontmatter）。

用法：
    python3 scripts/import-wxr.py <wxr.xml> [content_root] [选项]

    content_root 默认 src/content，文章写 <root>/posts/，页面写 <root>/pages/。

选项：
    --dry-run        只打印将要写入的文件 / 编号 / 标题 / 标签，不落盘
    --force          覆盖同名文件（默认跳过并提示）
    --report         输出统计：文章数、跳过数、标签频次、最长标题
    --site-url URL   把指向该站点的绝对内链改成站内相对路径
    --image-list P   待下载图片清单的落盘位置
                     （默认 <content_root>/images-to-download.txt）

规则：
    - 只导 post 与 page；attachment、草稿、回收站、其它 post_type 全部跳过
    - 编号按发布日期升序补齐三位数；磁盘上已有的 no 一律保留，绝不重排
    - slug 优先 wp:post_name（百分号编码会自动解码），为空时用标题，
      中文原样保留（不音译、不转拼音）
    - frontmatter 字段与现有文章逐字一致：双引号字符串、tags 写成 ["a", "b"]

只依赖标准库（xml.etree.ElementTree + html.parser），Python 3.11+ 可直接运行。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET

# --------------------------------------------------------------------------
# 常量
# --------------------------------------------------------------------------

WP_NS = "wordpress.org/export"        # 1.0 / 1.1 / 1.2 都能匹配
CONTENT_NS = "modules/content"       # content:encoded
EXCERPT_NS = "excerpt"               # excerpt:encoded

CJK = r"\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
BR = "\x00br\x00"                    # <br> 的占位符，躲过空白折叠

VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}
HEADING_TAGS = {f"h{i}" for i in range(1, 7)}
BLOCK_TAGS = HEADING_TAGS | {
    "p", "div", "section", "article", "header", "footer", "main", "aside",
    "nav", "figure", "figcaption", "blockquote", "pre", "ul", "ol", "li",
    "dl", "dt", "dd", "table", "thead", "tbody", "tfoot", "tr", "td", "th",
    "hr", "address", "details", "summary", "form", "fieldset", "video",
}
DROP_TAGS = {"script", "style", "noscript", "template", "head", "iframe"}

IGNORED_TAGS = {"未分类", "uncategorized", "uncategorised"}
TEXT_BLOCK_TAGS = {"p", "li", "blockquote", "figcaption"} | HEADING_TAGS

# --------------------------------------------------------------------------
# 极简 DOM：html.parser 建树，避免引入 bs4/lxml
# --------------------------------------------------------------------------


@dataclass
class Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list["Node | str"] = field(default_factory=list)

    def get(self, key: str, default: str = "") -> str:
        return self.attrs.get(key, default)


class _DOMBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("#root")
        self.stack: list[Node] = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k: (v or "") for k, v in attrs})
        self.stack[-1].children.append(node)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, {k: (v or "") for k, v in attrs}))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return
        # 孤立的结束标签：忽略

    def handle_data(self, data):
        if data:
            self.stack[-1].children.append(data)


def parse_html(html: str) -> list["Node | str"]:
    builder = _DOMBuilder()
    builder.feed(html or "")
    builder.close()
    return builder.root.children


def node_text(nodes) -> str:
    """取纯文本（实体已在解析时解码）。"""
    out = []
    for node in nodes:
        if isinstance(node, str):
            out.append(node)
        elif node.tag not in DROP_TAGS:
            out.append(node_text(node.children))
    return "".join(out)


def html_text(html: str) -> str:
    text = node_text(parse_html(html)).replace("\u00a0", " ").replace("\u3000", " ")
    return re.sub(r"\s+", " ", text).strip()


def code_text(nodes) -> str:
    """代码块取原文：不做空白折叠，<br> 换成换行。"""
    out = []
    for node in nodes:
        if isinstance(node, str):
            out.append(node)
        elif node.tag == "br":
            out.append("\n")
        elif node.tag not in DROP_TAGS:
            out.append(code_text(node.children))
    return "".join(out)


def serialize_html(node) -> str:
    """table 等少量元素原样保留 HTML（CommonMark 允许内联 HTML）。"""
    if isinstance(node, str):
        return node.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    attrs = "".join(
        f' {k}="{v.replace("&", "&amp;").replace(chr(34), "&quot;")}"'
        for k, v in node.attrs.items()
    )
    if node.tag in VOID_TAGS:
        return f"<{node.tag}{attrs}>"
    inner = "".join(serialize_html(c) for c in node.children)
    return f"<{node.tag}{attrs}>{inner}</{node.tag}>"


# --------------------------------------------------------------------------
# HTML → Markdown
# --------------------------------------------------------------------------


def polish_inline(text: str) -> str:
    """折叠空白，并去掉中文与中文/中文标点/强调标记之间多余的空格。"""
    text = text.replace("\u00a0", " ").replace("\u3000", " ")
    text = re.sub(r"[ \t\r\n\f\v]+", " ", text)
    text = re.sub(rf"(?<=[{CJK}]) +(?=[{CJK}])", "", text)
    text = re.sub(rf"(?<=[{CJK}]) +(?=[，。、；：？！）》」』”’…—])", "", text)
    text = re.sub(rf"(?<=[，。、；：？！（《「『“‘…—]) +(?=[{CJK}])", "", text)
    text = re.sub(rf"(?<=[{CJK}]) +(?=\*)", "", text)
    text = re.sub(rf"(?<=\*) +(?=[{CJK}])", "", text)
    return text


class Renderer:
    """把 WordPress 正文 HTML 转成 Markdown，并顺带收集图片地址。"""

    def __init__(self, site_url: str = "") -> None:
        self.site_url = site_url.rstrip("/")
        self.site_netloc = urlsplit(self.site_url).netloc.lower() if self.site_url else ""
        self.images: list[tuple[str, str]] = []   # (src, alt)

    # -- 对外入口 --------------------------------------------------------

    def to_markdown(self, html: str) -> str:
        md = self.blocks(parse_html(html), 0)
        md = re.sub(r"\n{3,}", "\n\n", md.strip())
        return md + "\n" if md else ""

    def plain_text(self, html: str) -> str:
        return html_text(html)

    # -- 行内 ------------------------------------------------------------

    def inline(self, nodes) -> str:
        out: list[str] = []
        for node in nodes:
            if isinstance(node, str):
                out.append(node)
                continue
            tag = node.tag
            if tag in DROP_TAGS:
                continue
            inner = self.inline(node.children)
            stripped = inner.strip()

            if tag in ("strong", "b"):
                out.append(f"**{stripped}**" if stripped else "")
            elif tag in ("em", "i"):
                out.append(f"*{stripped}*" if stripped else "")
            elif tag in ("del", "s", "strike"):
                out.append(f"~~{stripped}~~" if stripped else "")
            elif tag == "code":
                out.append(self.inline_code(stripped))
            elif tag == "a":
                out.append(self.link(node, stripped))
            elif tag == "img":
                out.append(self.image(node))
            elif tag == "br":
                out.append(BR)
            elif tag in HEADING_TAGS or tag in ("p", "div"):
                out.append(inner + " ")
            elif tag in ("sup", "sub", "mark", "kbd", "u"):
                out.append(f"<{tag}>{inner}</{tag}>" if stripped else "")
            else:
                out.append(inner)
        return polish_inline("".join(out))

    def inline_code(self, text: str) -> str:
        if not text:
            return ""
        ticks = "`"
        while ticks in text:
            ticks += "`"
        pad = " " if text.startswith("`") or text.endswith("`") else ""
        return f"{ticks}{pad}{text}{pad}{ticks}"

    def link(self, node: Node, text: str) -> str:
        href = node.get("href").strip()
        if not href or href.lower().startswith(("javascript:", "mailto:", "tel:")):
            return text
        href = self.normalize_href(href)
        if not text:
            return href
        title = node.get("title").strip()
        suffix = f' "{title}"' if title else ""
        return f"[{text}]({href}{suffix})"

    def normalize_href(self, href: str) -> str:
        """站内绝对链接 → 站内相对路径（仅当 --site-url 命中时）。"""
        if not self.site_netloc or not href.lower().startswith(("http://", "https://")):
            return href
        parts = urlsplit(href)
        if parts.netloc.lower() != self.site_netloc:
            return href
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        if parts.fragment:
            path += "#" + parts.fragment
        return path

    def image(self, node: Node) -> str:
        src = node.get("src").strip()
        if not src:
            return ""
        alt = re.sub(r"\s+", " ", node.get("alt")).strip()
        self.images.append((src, alt))
        alt = alt.replace("[", "\\[").replace("]", "\\]")
        title = node.get("title").strip()
        suffix = f' "{title}"' if title else ""
        return f"![{alt}]({src}{suffix})"

    # -- 块级 ------------------------------------------------------------

    def blocks(self, nodes, depth: int = 0) -> str:
        parts: list[str] = []
        buffer: list = []

        def flush() -> None:
            if not buffer:
                return
            text = polish_inline(self.inline(buffer)).strip()
            buffer.clear()
            text = text.replace(BR, "\n")
            if text:
                parts.append(text)

        for node in nodes:
            if isinstance(node, str):
                buffer.append(node)
                continue
            if node.tag in DROP_TAGS:
                continue
            if node.tag in BLOCK_TAGS:
                flush()
                block = self.block(node, depth)
                if block.strip():
                    parts.append(block)
            else:
                buffer.append(node)
        flush()
        return "\n\n".join(parts)

    def block(self, node: Node, depth: int) -> str:
        tag = node.tag

        if tag in HEADING_TAGS:
            text = polish_inline(self.inline(node.children)).strip()
            if not text:
                return ""
            return f"{'#' * int(tag[1])} {text.replace(BR, ' ')}"
        if tag == "p":
            text = polish_inline(self.inline(node.children)).strip()
            return text.replace(BR, "\\\n") if text else ""
        if tag in ("ul", "ol"):
            return self.list_block(node, depth)
        if tag == "li":
            return "- " + polish_inline(self.inline(node.children)).strip()
        if tag == "blockquote":
            inner = self.blocks(node.children, depth).strip()
            if not inner:
                return ""
            return "\n".join("> " + ln if ln.strip() else ">" for ln in inner.splitlines())
        if tag == "pre":
            return self.code_block(node)
        if tag == "hr":
            return "---"
        if tag == "figcaption":
            text = polish_inline(self.inline(node.children)).strip()
            return f"*{text}*" if text else ""
        if tag == "table":
            return serialize_html(node)
        if tag in ("dt",):
            text = polish_inline(self.inline(node.children)).strip()
            return f"**{text}**" if text else ""
        if tag in ("dd",):
            text = polish_inline(self.inline(node.children)).strip()
            return f"- {text}" if text else ""
        # div / section / figure / details 等容器：继续往下拆块
        return self.blocks(node.children, depth)

    def list_block(self, node: Node, depth: int) -> str:
        ordered = node.tag == "ol"
        try:
            number = int(node.get("start") or 1)
        except ValueError:
            number = 1
        indent = "    " * depth
        lines: list[str] = []

        for li in [c for c in node.children if isinstance(c, Node) and c.tag == "li"]:
            marker = f"{number}." if ordered else "-"
            number += 1
            inline_nodes, nested, extras = [], [], []
            for child in li.children:
                if isinstance(child, Node) and child.tag in ("ul", "ol"):
                    nested.append(child)
                elif isinstance(child, Node) and child.tag in ("blockquote", "pre", "figure", "table"):
                    extras.append(child)
                else:
                    inline_nodes.append(child)

            text = polish_inline(self.inline(inline_nodes)).strip()
            text = re.sub(r"\s*\n\s*", " ", text.replace(BR, "\n")).strip()
            lines.append(f"{indent}{marker} {text}".rstrip())
            for sub in nested:
                lines.append(self.list_block(sub, depth + 1))
            for extra in extras:
                rendered = self.block(extra, depth + 1)
                pad = "    " * (depth + 1)
                lines.extend(pad + ln if ln.strip() else "" for ln in rendered.splitlines())

        return "\n".join(lines)

    def code_block(self, node: Node) -> str:
        # WordPress 常见三种：<pre><code class="language-x">、
        # <pre class="wp-block-code"><code>、<pre class="brush: php;">
        target = node
        for child in node.children:
            if isinstance(child, Node) and child.tag == "code":
                target = child
                break
        code = code_text(target.children if target is not node else node.children)
        code = code.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
        lang = self.code_lang(node) or self.code_lang(target)
        longest = max((len(m) for m in re.findall(r"`+", code)), default=0)
        fence = "`" * max(3, longest + 1)
        return f"{fence}{lang}\n{code}\n{fence}" if code else ""

    @staticmethod
    def code_lang(node: Node) -> str:
        classes = " ".join(
            filter(None, [node.get("class"), node.get("data-lang"), node.get("lang")])
        )
        for token in classes.split():
            match = re.fullmatch(r"(?:language|lang)-([\w+#.-]+)", token)
            if match:
                return match.group(1)
        match = re.search(r"brush:\s*([\w+#.-]+)", classes)
        return match.group(1) if match else ""


# --------------------------------------------------------------------------
# WXR 解析
# --------------------------------------------------------------------------


def split_tag(tag: str) -> tuple[str, str]:
    if tag.startswith("{"):
        uri, _, name = tag[1:].partition("}")
        return uri, name
    return "", tag


def find_child(item: ET.Element, name: str, ns_hint: str | None = None):
    fallback = None
    for child in item:
        uri, local = split_tag(child.tag)
        if local != name:
            continue
        if ns_hint is None:
            if not uri:
                return child
        elif ns_hint in uri:
            return child
        elif fallback is None:
            fallback = child
    return fallback


def child_text(item: ET.Element, name: str, ns_hint: str | None = None) -> str:
    child = find_child(item, name, ns_hint)
    return "".join(child.itertext()).strip() if child is not None else ""


@dataclass
class Item:
    kind: str                       # post / page
    title: str
    date: str                       # YYYY-MM-DD
    slug: str
    body_html: str
    excerpt_html: str
    tags: list[str]
    categories: list[str]
    post_id: str
    no: str = ""
    markdown: str = ""
    excerpt: str = ""
    images: list[tuple[str, str]] = field(default_factory=list)
    target: Path | None = None
    skipped: str = ""               # 跳过原因，空表示要写

    @property
    def folder(self) -> str:
        return "posts" if self.kind == "post" else "pages"


def normalize_date(raw: str) -> str:
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", (raw or "").strip())
    return match.group(0) if match else ""


def rss_date(item: ET.Element) -> str:
    raw = child_text(item, "pubDate")
    if not raw:
        return ""
    try:
        return parsedate_to_datetime(raw).date().isoformat()
    except (TypeError, ValueError):
        return ""


def clean_slug(raw: str, title: str, post_id: str) -> str:
    """wp:post_name 优先；为空回退标题。中文原样保留（不音译、不转拼音）。"""
    slug = (raw or "").strip()
    if not slug:
        slug = title.strip()
    elif re.fullmatch(r"(?:%[0-9A-Fa-f]{2})+", slug) or re.search(r"%[eE][0-9A-Fa-f]", slug):
        # WP 有时把中文 post_name 存成百分号编码
        slug = unquote(slug)

    slug = slug.replace("\u3000", " ").replace("\u00a0", " ")
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r'[\\/:*?"<>|]', "-", slug)
    slug = re.sub(r"[，。、；：？！“”‘’《》〈〉【】（）〔〕…—～·,.;:!?'\"()\[\]{}#%&@+=$^`~]+", "", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-._ ")
    return slug or f"item-{post_id or 'untitled'}"


def collect_terms(item: ET.Element) -> tuple[list[str], list[str]]:
    tags: list[str] = []
    categories: list[str] = []
    for child in item:
        uri, local = split_tag(child.tag)
        if local != "category" or uri:
            continue
        domain = (child.get("domain") or "").lower()
        text = "".join(child.itertext()).strip()
        if domain == "post_tag":
            bucket = tags
        elif domain == "category":
            bucket = categories
        else:
            continue
        if text and text.lower() not in IGNORED_TAGS and text not in bucket:
            bucket.append(text)
    return tags, categories


def parse_wxr(path: Path) -> tuple[list[Item], Counter]:
    root = ET.parse(str(path)).getroot()
    channel = next((e for e in root if split_tag(e.tag)[1] == "channel"), root)
    items: list[Item] = []
    skipped: Counter = Counter()

    for raw in channel:
        if split_tag(raw.tag)[1] != "item":
            continue

        ptype = child_text(raw, "post_type", WP_NS) or "post"
        status = child_text(raw, "status", WP_NS) or "publish"
        if ptype == "attachment":
            skipped["attachment"] += 1
            continue
        if ptype not in ("post", "page"):
            skipped[f"其它类型({ptype})"] += 1
            continue
        if status != "publish":
            skipped[f"未发布({status})"] += 1
            continue

        title = html_text(child_text(raw, "title"))
        date = (
            normalize_date(child_text(raw, "post_date", WP_NS))
            or normalize_date(child_text(raw, "post_date_gmt", WP_NS))
            or rss_date(raw)
        )
        if not date:
            skipped["缺少发布日期"] += 1
            continue

        post_id = child_text(raw, "post_id", WP_NS)
        slug = clean_slug(child_text(raw, "post_name", WP_NS), title, post_id)
        body = child_text(raw, "encoded", CONTENT_NS)
        excerpt = child_text(raw, "encoded", EXCERPT_NS)
        tags, categories = collect_terms(raw)

        items.append(
            Item(
                kind=ptype,
                title=title,
                date=date,
                slug=slug,
                body_html=body,
                excerpt_html=excerpt,
                tags=tags,
                categories=categories,
                post_id=post_id,
            )
        )
    return items, skipped


# --------------------------------------------------------------------------
# 编号 / frontmatter
# --------------------------------------------------------------------------

FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?", re.S)


def parse_frontmatter(text: str) -> dict:
    """只解析本站 frontmatter 用到的写法（双引号字符串 / 行内数组 / 裸值）。"""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    data: dict = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#") or line.startswith((" ", "\t")):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            continue
        key, value = key.strip(), value.strip()
        if value.startswith("["):
            try:
                data[key] = json.loads(value)
            except json.JSONDecodeError:
                data[key] = [v.strip().strip('"') for v in value.strip("[]").split(",") if v.strip()]
        elif value.startswith('"'):
            try:
                data[key] = json.loads(value)
            except json.JSONDecodeError:
                data[key] = value.strip('"')
        else:
            data[key] = value
    return data


def scan_existing(posts_dir: Path) -> dict[str, dict]:
    existing: dict[str, dict] = {}
    if not posts_dir.is_dir():
        return existing
    for path in sorted(posts_dir.glob("*.md")):
        try:
            data = parse_frontmatter(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        existing[path.stem] = {"no": str(data.get("no", "")), "date": str(data.get("date", ""))}
    return existing


def as_number(value: str) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def assign_numbers(posts: list[Item], existing: dict[str, dict]) -> None:
    """已有编号锁死；新文章按发布日期升序领取最小的未占用编号。"""
    used = {n for info in existing.values() if (n := as_number(info.get("no")))}
    pending: list[Item] = []

    for item in posts:
        keep = as_number(existing.get(item.slug, {}).get("no", ""))
        if keep:
            item.no = f"{keep:03d}"
        else:
            pending.append(item)

    next_no = 1
    for item in sorted(pending, key=lambda i: (i.date, i.slug)):
        while next_no in used:
            next_no += 1
        item.no = f"{next_no:03d}"
        used.add(next_no)
        next_no += 1


def yaml_str(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def yaml_list(values: list[str]) -> str:
    return "[" + ", ".join(yaml_str(v) for v in values) + "]"


def build_frontmatter(item: Item) -> str:
    if item.kind == "post":
        pairs = [
            ("title", yaml_str(item.title)),
            ("date", yaml_str(item.date)),
            ("no", yaml_str(item.no)),
            ("tags", yaml_list(item.tags)),
            ("excerpt", yaml_str(item.excerpt)),
        ]
    else:
        pairs = [
            ("title", yaml_str(item.title)),
            ("date", yaml_str(item.date)),
            ("excerpt", yaml_str(item.excerpt)),
            ("slug", yaml_str(item.slug)),
        ]
    lines = ["---"] + [f"{k}: {v}" for k, v in pairs] + ["---"]
    return "\n".join(lines)


def first_block_text(nodes) -> str:
    """取正文里第一个非空块级元素的纯文本，用作摘要兜底。"""
    for node in nodes:
        if isinstance(node, str):
            continue
        if node.tag in TEXT_BLOCK_TAGS:
            text = html_text(node_text(node.children))
            if text:
                return text
        found = first_block_text(node.children)
        if found:
            return found
    return ""


def make_excerpt(item: Item, renderer: Renderer) -> str:
    text = html_text(item.excerpt_html)
    if not text:
        plain = first_block_text(parse_html(item.body_html)) or renderer.plain_text(item.body_html)
        plain = re.sub(r"\s+", " ", plain).strip()
        text = plain[:80] + ("…" if len(plain) > 80 else "")
    return text


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="WordPress WXR → Astro 内容集合（posts / pages）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("wxr", help="WXR 导出文件")
    parser.add_argument("content_root", nargs="?", default="src/content",
                       help="内容根目录，默认 src/content（写入其下的 posts/ 与 pages/）")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不落盘")
    parser.add_argument("--force", action="store_true", help="覆盖同名文件")
    parser.add_argument("--report", action="store_true", help="输出统计")
    parser.add_argument("--site-url", default="", help="把指向该站点的绝对内链改成站内相对路径")
    parser.add_argument("--image-list", default="", help="待下载图片清单路径")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    wxr = Path(args.wxr)
    if not wxr.is_file():
        print(f"找不到 WXR 文件：{wxr}", file=sys.stderr)
        return 2

    root = Path(args.content_root)
    posts_dir, pages_dir = root / "posts", root / "pages"

    try:
        items, skipped = parse_wxr(wxr)
    except ET.ParseError as exc:
        print(f"WXR 解析失败：{exc}", file=sys.stderr)
        return 2
    existing = scan_existing(posts_dir)

    writes: list[Item] = []
    seen: dict[str, int] = {}
    for item in items:
        # 同一批里重名（标题相同 / post_name 相同）时加 -2、-3 后缀；
        # posts 与 pages 目录不同，同名互不影响，所以按 kind 分开计
        key = f"{item.kind}/{item.slug}"
        count = seen.get(key, 0) + 1
        seen[key] = count
        if count > 1:
            item.slug = f"{item.slug}-{count}"

        folder = posts_dir if item.kind == "post" else pages_dir
        item.target = folder / f"{item.slug}.md"
        if item.target.exists() and not args.force:
            item.skipped = "已存在"
        else:
            writes.append(item)

    assign_numbers([i for i in writes if i.kind == "post"], existing)

    for item in writes:
        renderer = Renderer(args.site_url)
        item.markdown = renderer.to_markdown(item.body_html)
        item.images = renderer.images
        item.excerpt = make_excerpt(item, renderer)

    prefix = "[dry-run] " if args.dry_run else ""
    print(f"{prefix}WXR: {wxr}")
    print(f"{prefix}输出: {root}/posts  {root}/pages")

    for item in writes:
        tags = "、".join(item.tags) if item.tags else "-"
        no = item.no if item.kind == "post" else "—"
        print(f"  {prefix}写入 {item.folder}/{item.slug}.md  No.{no}  {item.title}  标签: {tags}")

    for item in items:
        if item.skipped:
            print(f"  {prefix}跳过 {item.folder}/{item.slug}.md（{item.skipped}）")

    if not args.dry_run:
        for item in writes:
            item.target.parent.mkdir(parents=True, exist_ok=True)
            body = f"{build_frontmatter(item)}\n\n{item.markdown}"
            item.target.write_text(body, encoding="utf-8")

    images = [(item, src, alt) for item in writes for src, alt in item.images]
    image_path = Path(args.image_list) if args.image_list else root / "images-to-download.txt"
    if images:
        lines = [f"{src}\t# {item.folder}/{item.slug}.md" for item, src, _ in images]
        if args.dry_run:
            print(f"\n{prefix}待下载图片 {len(lines)} 张：")
            for line in lines:
                print(f"  {prefix}{line}")
        else:
            image_path.parent.mkdir(parents=True, exist_ok=True)
            image_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            print(f"\n待下载图片 {len(lines)} 张 → {image_path}")

    skipped_total = sum(skipped.values()) + sum(1 for i in items if i.skipped)
    print(f"\n完成：文章 {sum(1 for i in writes if i.kind == 'post')} 篇 / 页面 "
          f"{sum(1 for i in writes if i.kind == 'page')} 个；跳过 {skipped_total}")
    if skipped:
        print("  " + "，".join(f"{k} {v}" for k, v in skipped.items()))

    if args.report:
        print_report(writes, skipped, items)

    return 0


def print_report(writes: list[Item], skipped: Counter, items: list[Item]) -> None:
    posts = [i for i in writes if i.kind == "post"]
    pages = [i for i in writes if i.kind == "page"]
    skipped_existing = sum(1 for i in items if i.skipped)
    tag_counter = Counter(tag for item in posts for tag in item.tags)
    category_counter = Counter(cat for item in posts for cat in item.categories)
    longest = max(posts, key=lambda i: len(i.title), default=None)
    images = sum(len(item.images) for item in writes)

    print("\n———— 报告 ————")
    print(f"文章：写入 {len(posts)}，页面：写入 {len(pages)}")
    print(f"跳过：{skipped_existing + sum(skipped.values())}"
          f"（已存在 {skipped_existing}"
          + "".join(f"，{k} {v}" for k, v in skipped.items()) + "）")
    if tag_counter:
        freq = "、".join(f"{tag} {n}" for tag, n in tag_counter.most_common(10))
        print(f"标签频次：{freq}")
    else:
        print("标签频次：（无）")
    if category_counter:
        # posts schema 没有 category 字段，分类只做统计，不进 frontmatter
        cats = "、".join(f"{c} {n}" for c, n in category_counter.most_common(10))
        print(f"分类（仅统计，不入 frontmatter）：{cats}")
    if longest:
        print(f"最长标题：{longest.title}（{len(longest.title)} 字）")
    print(f"待下载图片：{images} 张")


if __name__ == "__main__":
    raise SystemExit(main())
