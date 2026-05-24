---
name: wechat-article-drafting
description: Use when working inside the ClawMax project to turn a professional AI technical report into a clear, conversational WeChat public-account draft with AI 前沿 and 浪里淘金 sections.
version: 1.0.0
author: Max / Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [clawmax, project-specific, ai-media, wechat, article-writing]
    related_skills: [ai-technical-report, daily-ai-media-pipeline]
---

# WeChat Article Drafting

## Overview

This is a project-specific SOP skill for the ClawMax AI media workflow. It defines how to convert a professional AI technical report into a readable WeChat public-account draft.

The article should sound like a technically informed person explaining what happened in the AI world to smart readers. It should be lighter and more conversational than the technical report, but it must not sacrifice factual accuracy.

First-stage ClawMax output is draft-only. Do not automatically publish to WeChat or any other platform.

## When to Use

Use this skill when:

- The user asks to generate a微信公众号推文 or WeChat draft.
- There is an existing technical report under `reports/YYYY-MM-DD/` that should be rewritten for public readers.
- The task requires the fixed sections `AI 前沿` and `浪里淘金`.
- The output belongs under `articles/YYYY-MM-DD/`.

Do not use this skill for:

- Producing the professional technical report itself.
- Automatic publishing.
- Writing unrelated marketing copy.
- Inventing facts that are not supported by the report or sources.

## Inputs

Typical inputs:

- `reports/YYYY-MM-DD/technical-report.md`
- `reports/YYYY-MM-DD/sources.json`, if available
- User instructions about tone, target length, title style, or specific focus
- Additional search results for `浪里淘金`, if the user requests or the workflow allows active discovery

## Outputs

Default outputs:

```text
articles/YYYY-MM-DD/wechat-draft.md
articles/YYYY-MM-DD/review-notes.md
```

If a draft may contain human edits, do not overwrite it silently. Prefer `wechat-draft-v2.md` or a timestamped variant unless the user explicitly approves overwrite.

## Workflow

1. Read the technical report and sources first.
2. Extract the strongest 3-6 public-facing points from the report.
3. Decide the article angle: what is the reader benefit today?
4. Draft a conversational opening that tells readers why they should care.
5. Write `AI 前沿` from report-backed facts only.
6. Write `浪里淘金` using attractive AI projects, tools, cases, or developer玩法. If adding new discoveries, keep links and mark uncertainty.
7. Add a short reflection section, e.g. `今天值得想一想`.
8. Add a closing interaction question.
9. Add `人工审核清单` or separate `review-notes.md` for facts, links, risk points, and title suggestions.
10. Verify the article does not overclaim or hide uncertainty.

## Article Structure

Recommended `wechat-draft.md` structure:

```markdown
# 标题

## 开场白

## AI 前沿

## 浪里淘金

## 今天值得想一想

## 结尾互动

---

## 人工审核清单
```

`AI 前沿` should simplify and explain key report items. `浪里淘金` should make readers feel “这个我想点开试试”.

## Style Rules

- Default language is Chinese.
- Keep model names, API names, repository names, commands, and URLs in English.
- Use a relaxed but not childish tone.
- Explain technical ideas with short analogies or simple examples when helpful.
- Avoid exaggerated claims such as “彻底颠覆”, “全网最强”, or “必然取代”.
- Do not turn speculation into fact.
- Preserve links for projects or claims that readers may want to verify.
- Keep first-stage output as a draft for human review.

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
2. Becoming too标题党. Fix by keeping excitement grounded in facts.
3. Losing source links. Fix by preserving links in the draft or review notes.
4. Making `浪里淘金` a boring list. Fix by selecting fewer, more memorable items and explaining why they are worth trying.
5. Publishing automatically. First-stage ClawMax only creates drafts for human review.

## Verification Checklist

- [ ] Draft saved under `articles/YYYY-MM-DD/` or another user-approved path.
- [ ] Article includes `AI 前沿` and `浪里淘金`.
- [ ] Key facts are supported by the technical report or explicit sources.
- [ ] Uncertain claims are marked or moved to review notes.
- [ ] Tone is conversational and readable.
- [ ] No auto-publishing was attempted.
- [ ] Human review checklist is present.
