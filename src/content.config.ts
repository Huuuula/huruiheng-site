import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

/** 文章：/writing/<id>/ */
const posts = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/posts' }),
  schema: z.object({
    title: z.string(),
    date: z.coerce.date(),
    no: z.string().optional(),
    tags: z.array(z.string()).default([]),
    excerpt: z.string().default(''),
  }),
});

/** 项目：/projects/<id>/ */
const projects = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/projects' }),
  schema: z.object({
    title: z.string(),
    date: z.coerce.date(),
    no: z.string().optional(),
    summary: z.string().default(''),
    status: z.string().default(''),
    stack: z.array(z.string()).default([]),
    period: z.string().default(''),
    link: z.string().default(''),
    excerpt: z.string().default(''),
  }),
});

/** 独立页面：目前只有 about 有正文，writing / tags 由模板生成 */
const pages = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/pages' }),
  schema: z.object({
    title: z.string(),
    date: z.coerce.date(),
    excerpt: z.string().default(''),
    slug: z.string().optional(),
  }),
});

export const collections = { posts, projects, pages };
