#!/usr/bin/env python3
"""scripts/import-wxr.py 的自测（标准库 unittest，产物全部写 /tmp）。

跑法：
    python3 scripts/tests/test_import_wxr.py -v
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parents[1]
SCRIPT = ROOT / "scripts" / "import-wxr.py"
FIXTURE = TESTS / "fixtures" / "wxr-sample.xml"
VALIDATOR = TESTS / "validate-schema.mjs"

spec = importlib.util.spec_from_file_location("import_wxr", SCRIPT)
import_wxr = importlib.util.module_from_spec(spec)
sys.modules["import_wxr"] = import_wxr  # dataclass 解析注解时需要
sys.dont_write_bytecode = True          # 别在仓库里留 __pycache__
spec.loader.exec_module(import_wxr)

LEGACY = """---
title: "旧文"
date: "2024-01-01"
no: "007"
tags: ["旧"]
excerpt: ""
---

旧文正文。
"""


class ImportWxrTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="wxr-test-", dir="/tmp"))
        self.out = self.tmp / "out"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- 工具 -----------------------------------------------------------

    def run_script(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(FIXTURE), str(self.out), *args],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )

    def read_frontmatter(self, path: Path) -> dict:
        return import_wxr.parse_frontmatter(path.read_text(encoding="utf-8"))

    def post_numbers(self) -> dict[str, str]:
        return {
            p.name: str(self.read_frontmatter(p).get("no", ""))
            for p in sorted((self.out / "posts").glob("*.md"))
        }

    # -- 断言 -----------------------------------------------------------

    def test_dry_run_does_not_touch_disk(self):
        result = self.run_script("--dry-run", "--report")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.out.exists(), "dry-run 不应创建目录或文件")
        self.assertIn("[dry-run] 写入 posts/oldest-post.md  No.001", result.stdout)
        self.assertIn("标签频次", result.stdout)

    def test_skips_attachment_draft_and_trash(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        names = {p.name for p in (self.out / "posts").glob("*.md")}
        self.assertEqual(names, {"oldest-post.md", "中间一篇.md", "中文标题代码块与图片.md"})
        self.assertFalse((self.out / "posts" / "a.md").exists())
        self.assertFalse((self.out / "posts" / "draft-post.md").exists())
        self.assertFalse((self.out / "posts" / "trashed-post.md").exists())
        self.assertTrue((self.out / "pages" / "about.md").exists())
        self.assertIn("未发布(draft) 1", result.stdout)
        self.assertIn("attachment 1", result.stdout)

    def test_chinese_slug_kept(self):
        self.run_script()
        self.assertTrue((self.out / "posts" / "中文标题代码块与图片.md").exists())
        # wp:post_name 是百分号编码时自动解码
        self.assertTrue((self.out / "posts" / "中间一篇.md").exists())
        self.assertEqual(self.read_frontmatter(self.out / "pages" / "about.md")["slug"], "about")

    def test_code_block_entities_are_decoded(self):
        self.run_script()
        body = (self.out / "posts" / "中文标题代码块与图片.md").read_text(encoding="utf-8")
        self.assertIn("```python", body)
        self.assertIn('return "<div class="x">" if tag and True else "&&"', body)
        self.assertNotIn("&lt;div", body)
        self.assertNotIn("&amp;&amp;", body)

    def test_numbering_by_date(self):
        self.run_script()
        self.assertEqual(
            self.post_numbers(),
            {"oldest-post.md": "001", "中间一篇.md": "002", "中文标题代码块与图片.md": "003"},
        )

    def test_existing_number_is_never_reassigned(self):
        posts = self.out / "posts"
        posts.mkdir(parents=True)
        (posts / "legacy.md").write_text(LEGACY, encoding="utf-8")

        self.run_script()
        numbers = self.post_numbers()
        self.assertEqual(numbers["legacy.md"], "007", "既有编号被改动了")
        self.assertEqual(numbers["oldest-post.md"], "001")
        self.assertEqual(numbers["中间一篇.md"], "002")
        self.assertEqual(numbers["中文标题代码块与图片.md"], "003")

    def test_skip_then_force(self):
        first = self.run_script()
        self.assertIn("写入 posts/oldest-post.md", first.stdout)

        second = self.run_script()
        self.assertNotIn("写入 posts/oldest-post.md", second.stdout)
        self.assertIn("跳过 posts/oldest-post.md（已存在）", second.stdout)

        forced = self.run_script("--force")
        self.assertIn("写入 posts/oldest-post.md", forced.stdout)
        self.assertEqual(self.post_numbers()["oldest-post.md"], "001")

    def test_image_list_and_markdown_image(self):
        self.run_script()
        body = (self.out / "posts" / "中文标题代码块与图片.md").read_text(encoding="utf-8")
        self.assertIn("![站点截图](https://old.example.com/wp-content/uploads/2024/03/a.png)", body)
        images = (self.out / "images-to-download.txt").read_text(encoding="utf-8")
        self.assertIn("https://old.example.com/wp-content/uploads/2024/03/a.png", images)

    def test_frontmatter_matches_style(self):
        self.run_script()
        head = (self.out / "posts" / "oldest-post.md").read_text(encoding="utf-8").split("---")[1]
        self.assertIn('title: "Oldest Post"', head)
        self.assertIn('date: "2024-01-05"', head)
        self.assertIn('no: "001"', head)
        self.assertIn('tags: ["DNS"]', head)
        self.assertIn('excerpt: "最早的一篇。"', head)

    def test_zod_schema_accepts_output(self):
        self.run_script()
        payload = []
        for kind in ("posts", "pages"):
            for path in sorted((self.out / kind).glob("*.md")):
                payload.append(
                    {"kind": kind, "file": f"{kind}/{path.name}", "data": self.read_frontmatter(path)}
                )
        dump = self.tmp / "frontmatter.json"
        dump.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        result = subprocess.run(
            ["node", str(VALIDATOR), str(dump)],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("全部通过", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
