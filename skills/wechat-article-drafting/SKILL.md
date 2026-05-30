---
name: wechat-article-drafting
description: Use when working inside the ClawMax project to turn a professional AI technical report into a readable, source-attributed WeChat public-account article bundle with Markdown, HTML preview, images, and structured article.json data.
version: 1.1.0
author: Max / Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [clawmax, project-specific, ai-media, wechat, article-writing]
    related_skills: [ai-technical-report, daily-ai-media-pipeline]
---

# WeChat Article Drafting

## Overview

This is a project-specific SOP skill for the ClawMax AI media workflow. It defines how to convert a professional AI technical report into a readable WeChat public-account article bundle.

Treat the professional report as raw intelligence, not prose to lightly rewrite. The WeChat draft should feel like a content product: it needs an angle, judgment, rhythm, reader benefit, and clear attribution. It should be lighter and more conversational than the technical report, but it must not sacrifice factual accuracy.

Current implementation should generate draft and structured data only. Do not publish automatically from this skill alone. The long-term ClawMax product goal is still full automation: generate, structure, QA, format, add visuals, and publish after reliable automated gates exist.

Image handling and layout should stay minimal but useful: preserve usable report images, generate only necessary explanatory/cover images, save final files locally, reference them correctly from the Markdown and `article.json`, and generate a lightweight local HTML preview for visual review. Do not build a complex Canva-style design layer or attempt WeChat backend publishing unless the user explicitly asks.

For ClawMax-specific style and attribution details, see `references/clawmax-wechat-style-attribution.md`.

## When to Use

Use this skill when:

- The user asks to generate a微信公众号推文 or WeChat article draft.
- There is an existing technical report under `reports/YYYY-MM-DD/` or `reports/<run-label>/` that should be rewritten for public readers.
- The task requires the fixed sections `AI 前沿` and `浪里淘金`.
- The output belongs under `articles/YYYY-MM-DD/` or `articles/<run-label>/`.
- The workflow needs structured `article.json` for later automated QA, formatting, visuals, and publishing.
- The workflow needs image files copied/generated into `articles/<label>/images/` and referenced from the article bundle.

Do not use this skill for:

- Producing the professional technical report itself.
- Directly publishing to WeChat.
- Writing unrelated marketing copy.
- Inventing facts that are not supported by the report, sources, or explicitly cited external references.

## Inputs

Typical inputs:

- `reports/<label>/technical-report.md`
- `reports/<label>/sources.json`
- `reports/<label>/brief.json`
- User instructions about tone, target length, title style, or specific focus.
- Optional additional search results for `浪里淘金`, if the user requests or the workflow allows active discovery.
- Optional external public-account articles used as information leads. If used for facts, claims, or topic selection, they must be cited.
- Optional report image assets from `reports/<label>/image-assets.json` and `reports/<label>/images/`.

## Outputs

Default outputs:

```text
articles/<label>/wechat-draft.md
articles/<label>/final-wechat-article.md
articles/<label>/wechat-preview.html
articles/<label>/article.json
articles/<label>/metadata.json
articles/<label>/image-assets.json
articles/<label>/images/*
```

`wechat-draft.md` is the reader-facing Markdown draft.

`final-wechat-article.md` is the current-stage primary handoff article: a finalized Markdown assembled from `article.json`, with the digest, required sections, source links, and local image references ready for human review or later publishing adapters.

`wechat-preview.html` is a lightweight local visual preview generated from `article.json` and copied images. It is for browser review, typography/layout QA, and future formatting adapter development. It is not a WeChat backend publish artifact and must not imply publication.

`article.json` is the structured article contract for later automated formatting, visual planning, QA, and publishing. It must include at least:

- `date`
- `title`
- `title_candidates`
- `digest`
- `sections` with `heading`, `type`, `content_md`
- `source_report`
- `sources`
- `risk_flags`
- `style_references`
- `external_reference_accounts`
- `source_attribution_note`
- `image_assets`
- `auto_publish_eligible`

`image_assets` should be a practical list of local image files used or prepared for the article. Each item should include at least `id`, `purpose`, `local_path`, `markdown_ref`, `caption`, `source_url` or generation notes, and `status`.

`metadata.json` records the input report, generated files, generator profile, and `auto_publish=false` for the current pre-publish stage. It must include `output_final_article`, `output_html_preview`, `output_image_assets`, `output_images_dir`, and `generated_files` entries for every generated top-level file plus every saved local image file.

Optional output:

```text
articles/<label>/review-notes.md
```

If a draft may contain human edits, do not overwrite it silently. Integration scripts should use a backup-then-restore pattern when `--force` is requested, so a failed model/provider call does not delete the last good article bundle.

## Workflow

1. Read the technical report, `sources.json`, and `brief.json` first.
2. Extract the strongest 3-6 public-facing points from the report.
3. Decide the article angle: what is the reader benefit today?
4. Rewrite around reader curiosity, not report structure. Ask: why would a smart reader care, click, save, or forward this?
5. Draft a conversational opening with a concrete hook. Avoid starting like an abstract, memo, or press release.
6. Write `AI 前沿` from report-backed facts only. Each item should explain why it matters to readers, builders, or AI watchers.
7. Write `浪里淘金` using attractive AI projects, tools, cases, or developer玩法. If adding new discoveries, keep links and mark uncertainty.
8. Add a short reflection section, e.g. `今天值得想一想`.
9. Add a closing interaction question.
10. Prepare article images with the minimum viable image workflow:
    - reuse relevant report images from `reports/<label>/images/` when available;
    - copy selected images into `articles/<label>/images/` so the article bundle is self-contained;
    - generate a simple cover or section illustration only when it clearly improves the article;
    - record all selected/generated images in `articles/<label>/image-assets.json`;
    - insert relative Markdown image references at the most useful point in `wechat-draft.md` or `final-wechat-article.md`.
11. Add `## 参考与信息来源` at the end of `wechat-draft.md` and ensure it also appears in `final-wechat-article.md`.
12. Generate structured `article.json` alongside the Markdown draft so later stages can render, QA, add visuals, and publish without parsing prose.
13. Generate or run a small finalization step that assembles `final-wechat-article.md` from `article.json`, synchronizes `article.json.image_assets` with `image-assets.json`, creates `images/`, and updates `metadata.json` with `output_final_article`, `output_html_preview`, and `output_image_assets`.
14. Generate `wechat-preview.html` as a deterministic local HTML preview using the article title, digest, sections, local image references, and source links. Keep CSS self-contained and conservative; do not treat it as WeChat-published HTML.
15. Include style/source attribution fields: `style_references`, `external_reference_accounts`, `source_attribution_note`.
16. Include `image_assets` in `article.json` and keep it consistent with `image-assets.json`.
17. Put fact risks, uncertainty, title risks, source caveats, and image-source caveats in `risk_flags` or optional `review-notes.md`.
18. Verify the article does not overclaim or hide uncertainty, that every Markdown image reference resolves locally, and that `wechat-preview.html` can be opened locally.

## Article Structure

Recommended `wechat-draft.md` structure:

```markdown
# 标题

## 开场白

## AI 前沿

## 浪里淘金

## 今天值得想一想

## 结尾互动

## 参考与信息来源
```

`AI 前沿` should simplify and explain key report items. `浪里淘金` should make readers feel “这个我想点开试试”. `参考与信息来源` should cite the source report and concrete URLs used in the article. If external public-account articles supplied facts, viewpoints, or topic leads, cite the account name plus article title/link when available.

## Final Article Bundle Contract

The current final article bundle is file-based and deterministic. After the writing step and finalization step, `articles/<label>/` should contain:

```text
wechat-draft.md             # model-written draft for editing/review
final-wechat-article.md     # assembled Markdown handoff article
wechat-preview.html         # lightweight local visual preview
article.json                # structured source of truth for sections and metadata
metadata.json               # run and output pointers
image-assets.json           # local image manifest
images/                     # self-contained local image files
```

Contract rules:

- `article.json` remains the structured source of truth for article sections, source attribution, style references, risk flags, and `image_assets`.
- `final-wechat-article.md` is assembled from `article.json`; it must include title, digest, required sections, source links, and relative local image references.
- `wechat-preview.html` is generated from the same structured data for visual review. It should use local `./images/...` references and self-contained CSS. It is not a published WeChat article and should not include publishing tokens or backend-specific state.
- `metadata.json.generated_files` must list all generated top-level files, including `wechat-preview.html`, plus every saved local image file; `metadata.json` must include `output_final_article`, `output_html_preview`, `output_image_assets`, and `output_images_dir`.
- `article.json.image_assets` must exactly match `image-assets.json` after finalization.
- `auto_publish_eligible` and `metadata.auto_publish` remain `false` until separate automated QA/publishing gates exist.

## Image Asset Rules

Keep image handling boring and reliable:

- Use `articles/<label>/images/` as the article-local image directory.
- Use `articles/<label>/image-assets.json` as the article-local image manifest.
- Prefer copying useful report images from `reports/<label>/images/` rather than regenerating them.
- Generate at most a simple cover or explanatory illustration when no suitable image exists and the article would benefit from one.
- Do not invent product UI, official screenshots, benchmark charts, logos, or paper figures with an image model. Save those from original sources only when appropriate.
- Markdown references in `wechat-draft.md` and `final-wechat-article.md` must be relative to the article file, e.g. `![配图说明](./images/hero.png)`.
- `article.json.image_assets` and `image-assets.json` must refer to the same local files.
- If an image comes from the web, preserve `source_url`, `source_title`, and a short usage/copyright note.
- If image generation fails, keep the article usable without it and mark the asset as `failed` or omit it.
- Do not block article generation merely because optional images failed.

Recommended article image asset record shape:

```json
{
  "id": "hero",
  "purpose": "cover | section_illustration | diagram | screenshot | paper_figure",
  "local_path": "articles/YYYY-MM-DD/images/hero.png",
  "markdown_ref": "![封面图](./images/hero.png)",
  "caption": "string",
  "source_url": "",
  "source_title": "",
  "license_or_usage_note": "",
  "generation_prompt": "",
  "status": "saved | generated | skipped | failed",
  "notes": "string"
}
```

## Style Rules

- Default language is Chinese.
- Keep model names, API names, repository names, commands, and URLs in English.
- Use a relaxed but not childish tone.
- Sound like a technically literate editor explaining “这事为什么有意思” to smart friends.
- Have judgment and selection. It is okay to write phrases like “我更关心的是...”, “这地方先别急着兴奋...”, or “这个项目值得点开看一眼”.
- Use short paragraphs, concrete examples, and natural transitions.
- Explain technical ideas with short analogies or simple examples when helpful.
- Avoid report voice: `重要的是`, `值得注意的是`, `这一趋势表明`, `标志着`, `赋能`, `生态`, `深度融合`, `范式转移`, `全链路`, `闭环`.
- Avoid exaggerated claims such as “彻底颠覆”, “全网最强”, or “必然取代”.
- Do not turn speculation into fact.
- Preserve links for projects or claims that readers may want to verify.
- Current output is draft/structured data plus finalized Markdown, image manifest, and local HTML preview only; do not publish automatically from this skill.

## Reference Account Sampling

The accounts named by the user are **sample sources to read**, not magic style labels:

- `Kyro AI Tech`
- `说说说来话长`
- `数字生命卡兹克`
- `逛逛 Github`

Before claiming a style rule came from these accounts, actually read accessible article samples or user-provided exports. Do not infer their style from account names alone.

Record sampling status explicitly:

- `sampled`: article text was read and a source URL/title is available.
- `indexed_only`: only search-result titles/snippets were found; do not treat this as a verified writing-style sample.
- `blocked`: WeChat/Sogou required CAPTCHA, login, or anti-spider validation.
- `not_found`: no usable result was found.

If samples are `indexed_only`, `blocked`, or `not_found`, do not put the account into `article.json.style_references` as an actually used style source. Instead, mention the access limitation in `source_attribution_note` or project notes.

If an account supplies an actual lead, claim, article, or viewpoint, add it to `article.json.external_reference_accounts` and cite it in `## 参考与信息来源` with account name, article title, and link when available.

## Sampled Style Corpus

The following public-account articles have been actually read during ClawMax project work. Sampling status: `sampled`. These examples are project-shared style evidence, not private local memory.

- `数字生命卡兹克` — 《我折腾了好久的Skills团队共享，终于有产品替我做出来了。》
  - URL: `https://mp.weixin.qq.com/s/ylu0WvLJGNTZiim-NQmPQQ`
  - Useful pattern: open with a real personal/team pain point, then show why a product feature matters. The voice is opinionated and conversational: “说实话”, “这玩意是真的折腾”, “这事真挺抽象”.
- `逛逛GitHub` — 《GitHub 狂揽 1.3 万 Star，Anthropic 开源的知识工作者插件。》
  - URL: `https://mp.weixin.qq.com/s/Tck8poEUxOK3rY_ubqGbjA`
  - Useful pattern: introduce a GitHub/project discovery, explain it in one sentence, then break down role scenarios, commands, install path, and why someone would try it.
- `GitHubDaily` — 《一个 Claude Code 插件，狂揽 20 万 Star！》
  - URL: `https://mp.weixin.qq.com/s/EWfhQMrfHJXyZ-MjfxybNA`
  - Useful pattern: use Trending/Star count as the hook, but quickly move into origin story, workflow, practical use, caveats, and a final trend judgment.

When these sampled articles are used only for style, record them in `article.json.style_references` with `status: "sampled"`, account name, title, URL, and a short note such as `style_reference_only`. Do not cite them as factual sources in the article body unless their facts, claims, viewpoints, or topic leads are actually used.

## Style Transfer Rules from the Sampled Corpus

Use the sampled corpus to shape article rhythm and reader benefit:

- Title formula: “discovery hook + concrete object + light judgment”. Star counts, product names, personal pain points, or unexpected feature combinations can create curiosity, but do not exaggerate.
- Opening: prefer a concrete scene over broad industry background. Start from “我最近遇到一个问题”, “今天刷 GitHub 看到…”, or “这事要从某个产品说起”.
- Paragraph rhythm: keep paragraphs short, usually 1-3 sentences. Use natural transitions like “说实话”, “先说结论”, “接下来说下怎么用”, “但我更关心的是”.
- Explanation style: translate technical concepts into practical consequences first, then name the concept. For example, explain what a Skill/MCP/Agent/Command lets the reader do before discussing architecture.
- Judgment: include informed selection and mild personal stance. Good phrases include “这个地方先别急着兴奋”, “真正值得看的不是 Star 数”, “这个项目适合正在折腾 X 的人”.
- `AI 前沿`: convert report items into plain-language technical observations: what happened, why it is worth discussing now, who is affected, and what still needs watching.
- `浪里淘金`: write each item like a small discovery, not a bibliography. Include one-sentence intro, why it is interesting, who should try it, how to try it, risk/limit, and link.
- Ending: close with a light trend judgment or a reader prompt, not a slogan.
- Avoid copying sentence structure, jokes, article titles, or distinctive wording from the samples. The goal is to learn pacing, structure, and reader orientation.

## WeChat material rule

Public web search is not enough for a reliable style corpus. Do not claim to have read a public account unless the user provides article text, exported material, or a reachable article URL/session that was actually read.

Preferred inputs, in order:

1. User-provided article text, Markdown, HTML, or exported material.
2. User-provided article URLs that can actually be opened and read in the current environment.
3. A user-provided API/MCP/service with legitimate article-body access.

Until one of these exists, say that WeChat reference material is unavailable rather than pretending to have read the reference accounts.

## `浪里淘金` Selection Rules

A good item for `浪里淘金` should satisfy several of these:

- easy to explain in one sentence;
- visually or practically interesting;
- useful to creators, developers, students, or AI enthusiasts;
- has a live demo, GitHub repo, product page, or clear source;
- has a concrete “try this” angle;
- is not merely a generic project list item.

Each item should include, when possible:

- 一句话介绍;
- 为什么有意思;
- 适合谁;
- 链接;
- 风险或限制.

## Common Pitfalls

1. Copying the technical report too directly. Fix by rewriting around reader benefit and plain-language explanations.
2. Passing schema while still sounding like a report. Fix by removing report-voice phrases and adding judgment, rhythm, and concrete examples.
3. Becoming too标题党. Fix by keeping excitement grounded in facts.
4. Losing source links. Fix by preserving links in `参考与信息来源`, `sources`, or `risk_flags`.
5. Making `浪里淘金` a boring bibliography. Fix by selecting fewer, more memorable items and explaining why they are worth trying.
6. Citing style-reference accounts as factual sources when they only influenced tone. Fix by separating `style_references` from `external_reference_accounts`.
7. Publishing automatically from the drafting skill. Fix by keeping `auto_publish_eligible=false` until automated QA, formatting, visual, and publishing gates exist.

## Verification Checklist

- [ ] Draft saved under `articles/<label>/wechat-draft.md` or another user-approved path.
- [ ] `final-wechat-article.md`, `wechat-preview.html`, `article.json`, and `metadata.json` are present.
- [ ] `article.json` and `metadata.json` are valid JSON.
- [ ] `metadata.json.generated_files` includes `wechat-preview.html` and every saved local image file.
- [ ] `metadata.json` includes `output_final_article`, `output_html_preview`, `output_image_assets`, and `output_images_dir`.
- [ ] Article includes `AI 前沿`, `浪里淘金`, and `参考与信息来源`.
- [ ] `article.json.sections` includes at least `intro`, `frontier`, and `gold_rush`.
- [ ] `article.json.style_references` records the reference accounts when used for style direction.
- [ ] `article.json.external_reference_accounts` only records accounts actually used as factual or selection sources.
- [ ] `article.json.source_attribution_note` explains final attribution handling.
- [ ] If images are used, `articles/<label>/image-assets.json` is valid JSON.
- [ ] If images are used, `article.json.image_assets` matches the image manifest.
- [ ] If images are used, local image files exist under `articles/<label>/images/`.
- [ ] Markdown image references are relative paths and resolve from `wechat-draft.md` or `final-wechat-article.md`.
- [ ] `wechat-preview.html` contains the title, required sections, source links, and local `./images/...` references when images exist.
- [ ] Key facts are supported by the technical report or explicit sources.
- [ ] Uncertain claims are marked in the prose or `risk_flags`.
- [ ] Tone is conversational, readable, and not report-like.
- [ ] No auto-publishing was attempted.
