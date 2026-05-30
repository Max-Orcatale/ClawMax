---
name: ai-technical-report
description: Use when working inside the ClawMax project to generate a daily professional AI technical report with traceable sources, structured sections, optional gpt-image-2 illustrations, and explicit uncertainty handling.
version: 1.1.0
author: Max / Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [clawmax, project-specific, ai-media, technical-report, research, image-generation]
    related_skills: [daily-ai-media-pipeline, wechat-article-drafting]
---

# AI Technical Report

## Overview

This is a project-specific SOP skill for the ClawMax AI media workflow. It defines how to produce a professional daily AI technical report that can be used as the factual source for downstream WeChat article drafting.

The report should prioritize accuracy, traceability, depth, and clear structure. It is not a marketing article and should not optimize for virality. Its main job is to collect, classify, summarize, and evaluate AI frontier information so that later agents or humans can reuse the material safely.

A qualified report should read like an internal company intelligence memo written by a responsible technical analyst, not like a shallow news digest. Each selected item should explain the factual update, technical context, why it matters, who may be affected, what remains uncertain, and what the company or reader should watch next.

The report may include optional images, such as a cover illustration, an architecture diagram, a concept image, or saved source images. Images are supporting material, not evidence. Do not let image generation replace source-backed reporting.

Keep image handling simple: save selected image files into the run directory, keep a small manifest, and use relative Markdown references. Avoid complex design systems, Canva-style composition, or HTML layout at this stage. The minimum acceptable visual workflow is: image files exist locally, Markdown links resolve, and downstream WeChat drafting can reuse them.

Images may come from either generation or web-sourced materials, depending on the report need. If you use a web-sourced image, preserve its source URL, ownership/usage context, and caption it as an illustration or reference image rather than evidence. Place images where they support the adjacent text most naturally instead of collecting them all at the top or bottom.

## When to Use

Use this skill when:

- The user asks for a daily AI technical report.
- The user asks to summarize recent AI frontier news, papers, company updates, benchmarks, or open-source projects.
- The workflow needs a structured source document for the `WeChatArticleAgent` profile.
- The task belongs to the ClawMax project and touches `reports/YYYY-MM-DD/` outputs.
- The report needs optional visual assets generated with an image model such as `gpt-image-2`.

Do not use this skill for:

- Writing the final WeChat public-account article directly.
- Publishing content automatically.
- Producing purely opinion-based posts without sources.
- Treating generated images as factual evidence.
- Writing reports for unrelated projects unless the user explicitly asks to reuse the ClawMax workflow.

## Inputs

Typical inputs:

- User-provided topic, date, or focus area.
- Existing source records, if any.
- Search results from web, arXiv, GitHub, official blogs, benchmarks, community sites, or manually curated links.
- Project config such as target language, output directories, tracked companies, tracked technical areas, and image-generation settings.

Recommended source record shape:

```json
{
  "title": "string",
  "url": "string",
  "source_type": "paper | company_blog | github | news | community | benchmark | other",
  "published_at": "string",
  "retrieved_at": "string",
  "summary": "string",
  "confidence": "high | medium | low",
  "tags": ["agent", "embodied-ai"]
}
```

Recommended image prompt record shape:

```json
{
  "id": "hero",
  "purpose": "cover | diagram | concept | section_illustration",
  "prompt": "string",
  "model": "gpt-image-2-medium",
  "target_path": "reports/YYYY-MM-DD/images/hero.png",
  "markdown_ref": "![封面图](./images/hero.png)",
  "status": "planned | generated | skipped | failed",
  "notes": "string"
}
```

Recommended image asset manifest shape:

```json
{
  "id": "hero",
  "kind": "generated | web_source | user_provided",
  "purpose": "cover | diagram | screenshot | paper_figure | benchmark_chart | concept | section_illustration",
  "local_path": "reports/YYYY-MM-DD/images/hero.png",
  "markdown_ref": "![封面图](./images/hero.png)",
  "source_url": "",
  "source_title": "",
  "license_or_usage_note": "",
  "caption": "string",
  "status": "saved | planned | generated | skipped | failed",
  "notes": "string"
}
```

## Outputs

Default text and data outputs should be saved under:

```text
reports/YYYY-MM-DD/technical-report.md
reports/YYYY-MM-DD/sources.json
reports/YYYY-MM-DD/brief.json
```

Optional image-related outputs should be saved under:

```text
reports/YYYY-MM-DD/image-prompts.json
reports/YYYY-MM-DD/image-assets.json
reports/YYYY-MM-DD/images/*
```

`image-assets.json` is the simple handoff manifest for all saved images, whether generated, web-sourced, or user-provided. Keep it small and practical: local path, Markdown reference, source/copyright context when applicable, caption, status, and notes.

If generated images first land in `$HERMES_HOME/cache/images/`, copy or move the selected images into `reports/YYYY-MM-DD/images/` before linking them from the report.

Use relative Markdown references inside `technical-report.md`, for example:

```markdown
![AI Agent 工作流示意图](./images/agent-workflow.png)
```

If files already exist and may contain human edits, do not overwrite silently. Prefer a timestamped or versioned filename, or ask the user before overwriting.

## Workflow

1. Clarify the date and scope if missing and not inferable.
2. Unless the user explicitly provides `sources.json` or explicitly requests a mock/smoke test, collect real sources automatically from high-quality channels first. Do not limit the search to the literal calendar day. Use a rolling recent window by default:
   - today and the last 7-14 days for company/product/release/news items;
   - the last 30-90 days for papers, benchmarks, GitHub projects, and developer tools when they are gaining traction or remain strategically important;
   - older items only when they explain the background of a current update.
   Prioritize:
   - company official blogs and changelogs;
   - arXiv or paper pages;
   - GitHub repositories, releases, changelogs, star/release activity, and developer ecosystem signals;
   - benchmark reports;
   - reputable technical blogs and news;
   - community sources only as lower-confidence signals.
   If a topic appeared in a previous report, mention it again only when there is a new release, fresh evidence, rising community/developer attention, new benchmark result, adoption signal, or meaningful controversy. Otherwise, skip it to avoid repetition.
3. For a normal daily report, do not use mock sources. Mock sources are only allowed for explicit engineering smoke tests, and smoke-test wording must not appear inside a professional `technical-report.md`.
4. Normalize every source into a structured record.
5. Deduplicate overlapping stories and prefer original sources over reposts.
6. Classify each item into report sections.
7. Assign confidence:
   - `high`: official source, paper, release note, or directly verifiable repository;
   - `medium`: reputable secondary report with enough detail;
   - `low`: social/community rumor, incomplete claim, or unverifiable summary.
8. Generate the technical report in Chinese, while preserving API names, model names, paper titles, repositories, and commands in English.
9. Put uncertain claims into a `待确认信息` or `风险、争议与待确认信息` section.
10. Decide whether images are needed. Only add images when they improve comprehension, presentation, or downstream reuse. It is fine to skip images when they are not useful.
11. If images are needed, use the minimum viable image workflow:
    - plan 1-3 images maximum for a daily report unless the user requests more;
    - prefer saving useful existing source images when they are factual visuals such as product screenshots, paper figures, benchmark charts, or official diagrams;
    - generate images only for conceptual covers, simplified diagrams, or explanatory illustrations;
    - write generation prompts into `image-prompts.json` when generation is used;
    - save every selected image under `reports/YYYY-MM-DD/images/`;
    - write every selected image into `image-assets.json`;
    - insert relative Markdown image references into `technical-report.md`;
    - label conceptual/generated images as illustrations, not evidence.
12. Save report and structured source files.
13. Verify that output paths, links, source references, and image references are present and resolve locally.

## Report Structure

Recommended `technical-report.md` structure:

```markdown
# YYYY-MM-DD AI 技术报告

> 可选：封面图或今日主题图

## 今日摘要

## 重点新闻

## 论文与研究进展

## 公司与产品动态

## 开源项目与开发者生态

## 具身智能专题

## 图表与配图说明

## 风险、争议与待确认信息

## 来源链接
```

Do not include workflow-test commentary, smoke-test explanations, or downstream content-drafting sections in a professional daily technical report. In particular, do not add a section named `对内容创作的可用素材`; that belongs to the WeChat drafting workflow, not this report.

The report does not need to be long for its own sake. Prefer concise analysis with clear source references over broad but shallow coverage.

## Analysis Depth Standard

A normal daily report should not simply list links or restate headlines. It should be useful to a company employee who needs to understand what changed and what to do next.

For each major item, prefer the following substructure:

```markdown
### Item title

- 事实更新：what concretely happened, with source reference.
- 技术背景：the relevant model, API, paper, benchmark, architecture, repo, or ecosystem context.
- 关键变化：what is new compared with previous state, not just what the source says.
- 影响判断：why this matters for developers, AI media, product strategy, research, or infra.
- 风险与不确定性：what is vendor claim, unverified, incomplete, controversial, or likely to change.
- 后续观察：specific follow-up signals to watch, such as docs changes, benchmark reproduction, adoption, pricing, release notes, or competing responses.
```

Depth expectations:

- Cover fewer items with more analysis rather than many shallow bullets.
- For a standard daily report, select roughly 4-8 meaningful sources and write 2-4 well-developed paragraphs or equivalent bullets for each major item.
- `今日摘要` should synthesize cross-source themes, not describe the report-generation process.
- Avoid generic phrases such as “值得关注” without explaining why.
- If a source is too thin to support analysis, put it in `风险、争议与待确认信息` or omit it.

## Output Schemas

`sources.json` must be a JSON array. Each item must include:

- `title`
- `url`
- `source_type`
- `published_at`
- `retrieved_at`
- `summary`
- `confidence`
- `tags`

`brief.json` must be a JSON object. It is the handoff file for downstream drafting and must include:

- `date`: report date string.
- `title`: concise report title.
- `summary`: short executive summary.
- `top_items`: list of major items worth carrying into downstream work.
- `risks`: list of uncertainty, credibility, or follow-up risks.
- `ready_for_wechat_drafting`: boolean; set `true` only when the report is ready for the WeChat drafting stage.

## Image Rules

- Images are optional, not mandatory.
- Keep the first implementation simple: save files, keep a manifest, and reference them correctly. Do not build a complex visual design pipeline yet.
- Default generation model preference: `gpt-image-2-medium`.
- Daily report default: 1-3 images maximum.
- Useful image types:
  - cover image for the day's topic;
  - architecture or workflow diagram;
  - concept illustration for a difficult technical theme;
  - section illustration for a major trend;
  - saved official screenshots, paper figures, benchmark charts, or architecture diagrams when the source permits normal reference and the source URL is preserved.
- Generate images only for conceptual/explanatory visuals. Do not generate factual evidence.
- Avoid generating images for factual evidence, benchmark charts, logos, UI screenshots, or anything that should come from an original source.
- Do not invent official product screenshots, company logos, benchmark numbers, or paper figures.
- Avoid text-heavy generated images. Put exact labels and data in Markdown instead.
- Save prompts and final image paths in `image-prompts.json` for audit and reruns when generation is used.
- Save all selected image files under `reports/YYYY-MM-DD/images/` and record them in `image-assets.json`.
- If generation fails, keep the report usable and mark the image status as `failed` or `skipped`.

## Quality Rules

- Accuracy first; never turn an uncertain claim into a confirmed fact.
- Prefer original sources over summaries.
- Preserve enough source metadata for later audit.
- Separate factual summary from model inference or editorial judgment.
- Do not include secrets, tokens, cookies, or private user data.
- Use Chinese for explanations, but keep names, commands, URLs, and technical identifiers in English.
- Make downstream reuse easy: include concise bullets, tags, and clear section names.
- Generated images must support the report and must not be represented as source evidence.

## Common Pitfalls

1. Treating marketing claims as technical facts. Fix by labeling them as vendor claims unless independently verified.
2. Losing source URLs. Fix by storing `sources.json` and adding a source section in the report.
3. Mixing low-confidence social chatter with confirmed news. Fix by using confidence labels and a 待确认 section.
4. Writing in a WeChat style too early. This report should remain professional and structured; leave 口语化 rewriting to `wechat-article-drafting`.
5. Overwriting reviewed reports. Always check existing files before writing.
6. Letting generated images imply fake evidence. Fix by labeling them as concept illustrations and keeping factual claims in text with sources.
7. Leaving images in `$HERMES_HOME/cache/images/` only. Fix by copying selected images into `reports/YYYY-MM-DD/images/` and using relative links.

## Verification Checklist

- [ ] Report saved under `reports/YYYY-MM-DD/` or another user-approved path.
- [ ] `technical-report.md` has the required major sections.
- [ ] Key facts include source links or source references.
- [ ] Uncertain claims are clearly marked.
- [ ] `sources.json` is valid JSON if generated.
- [ ] `brief.json` is valid JSON if generated.
- [ ] If images are generated, `image-prompts.json` is valid JSON.
- [ ] If any images are used, `image-assets.json` is valid JSON.
- [ ] If any images are used, final image files exist under `reports/YYYY-MM-DD/images/`.
- [ ] Markdown image references use relative paths and resolve from `technical-report.md`.
- [ ] No generated image is presented as factual evidence.
- [ ] No secrets or private credentials appear in outputs.
- [ ] The report can be used as input for `wechat-article-drafting`.
