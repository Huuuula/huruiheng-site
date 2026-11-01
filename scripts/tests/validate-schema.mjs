#!/usr/bin/env node
/**
 * 用 src/content.config.ts 里同一套字段定义（astro 自带的 zod）校验导入产物。
 * 用法：node scripts/tests/validate-schema.mjs <payload.json>
 * payload: [{ kind: "posts" | "pages", file: "...", data: {...} }, ...]
 */
import { readFileSync } from 'node:fs';
import { z } from 'astro/zod';

const posts = z.object({
  title: z.string(),
  date: z.coerce.date(),
  no: z.string().optional(),
  tags: z.array(z.string()).default([]),
  excerpt: z.string().default(''),
});

const pages = z.object({
  title: z.string(),
  date: z.coerce.date(),
  excerpt: z.string().default(''),
  slug: z.string().optional(),
});

const schemas = { posts, pages };
const payload = JSON.parse(readFileSync(process.argv[2], 'utf8'));
let failed = 0;

for (const entry of payload) {
  const schema = schemas[entry.kind];
  if (!schema) {
    console.error(`未知集合: ${entry.kind}`);
    failed += 1;
    continue;
  }
  const result = schema.safeParse(entry.data);
  if (result.success) {
    console.log(`ok   ${entry.file}`);
  } else {
    failed += 1;
    console.error(`FAIL ${entry.file}\n${result.error.message}`);
  }
}

console.log(failed === 0 ? `\n全部通过：${payload.length} 个文件` : `\n失败：${failed}`);
process.exit(failed === 0 ? 0 : 1);
