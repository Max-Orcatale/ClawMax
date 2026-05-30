---
name: daily-ai-media-pipeline
description: Use when working inside the ClawMax project to run or design the daily AI media workflow that creates a technical report first and then a finalized WeChat article bundle for review.
version: 1.0.0
author: Max / Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [clawmax, project-specific, ai-media, pipeline, scheduling]
    related_skills: [ai-technical-report, wechat-article-drafting]
---

# Daily AI Media Pipeline

## Overview

This is a project-specific skill for the ClawMax AI media workflow. It defines the daily content-production chain that turns AI frontier information into a professional technical report and then into a WeChat public-account article bundle.

The pipeline should stay simple in the first stage: file-based handoff, traceable sources, clear output directories, local Markdown/HTML review artifacts, and no automatic publication before QA/publishing gates exist.

## When to Use

Use this skill when:

- The user asks to run, design, or modify the daily AI media workflow.
- A task involves both `TechnicalReportAgent` and `WeChatArticleAgent`.
- The workflow should produce files under `reports/YYYY-MM-DD/` and `articles/YYYY-MM-DD/`, including `final-wechat-article.md`, `wechat-preview.html`, `article.json`, and image assets.
- The user asks about scheduling, reruns, output naming, or handoff between agents.

Do not use this skill for:

- Publishing directly to WeChat.
- Building unrelated automation pipelines.
- Running long-term product strategy analysis; that belongs to a future `ProductStrategyAgent`.

## Pipeline Shape

First-stage pipeline:

```text
Scheduler or manual run
↓
TechnicalReportAgent
↓
reports/YYYY-MM-DD/
↓
WeChatArticleAgent
↓
articles/YYYY-MM-DD/
  ├─ wechat-draft.md
  ├─ final-wechat-article.md
  ├─ wechat-preview.html
  ├─ article.json
  ├─ image-assets.json
  └─ images/
↓
人工审阅 / 修改 / 发布
```

Default daily schedule target:

```text
06:00 local project timezone
```

Use Hermes cron or another scheduler only after the manual workflow is stable.

## Inputs

Typical inputs:

- Date, usually today.
- Optional topic focus, such as embodied AI, agents, reasoning, multimodal models, or AI infra.
- Non-sensitive settings from `config.yaml`.
- Existing mock sources or real search results.

Never require secrets in `config.yaml`. API keys and tokens belong in `.env` or Hermes secret configuration.

## Outputs

Recommended output layout:

```text
reports/YYYY-MM-DD/technical-report.md
reports/YYYY-MM-DD/sources.json
reports/YYYY-MM-DD/brief.json
articles/YYYY-MM-DD/wechat-draft.md
articles/YYYY-MM-DD/final-wechat-article.md
articles/YYYY-MM-DD/wechat-preview.html
articles/YYYY-MM-DD/article.json
articles/YYYY-MM-DD/metadata.json
articles/YYYY-MM-DD/image-assets.json
articles/YYYY-MM-DD/images/*
```

If rerunning the same date, avoid silently overwriting human-edited files. Prefer versioned outputs such as:

```text
wechat-draft-v2.md
technical-report-v2.md
```

or ask the user before overwriting.

## Workflow

1. Determine run date and topic scope.
2. Prepare output directories for the date.
3. Run the technical report step using `ai-technical-report`.
4. Verify that the technical report and source records exist and are usable.
5. Run the WeChat article step using `wechat-article-drafting`.
6. Run the final article bundle step so `article.json` becomes `final-wechat-article.md`, `wechat-preview.html`, `image-assets.json`, and local `images/`.
7. Verify that the draft, final Markdown, HTML preview, structured JSON, source links, and image manifest satisfy the final bundle contract.
8. Summarize outputs and next human action.
9. If the process exposed a reusable improvement, update the relevant project skill.

## Manual Run First

Before adding daily scheduling, validate the manual path:

```text
mock sources
↓
technical report
↓
wechat draft + article.json
↓
final Markdown + HTML preview + images
↓
human review
```

Only after this produces acceptable drafts should the workflow move to automatic 06:00 scheduling.

## Scheduling Guidance

When using Hermes cron, the scheduled job should be self-contained:

- set `workdir` to the ClawMax repository root;
- load project skills explicitly after they have been synced into `$HERMES_HOME/skills/clawmax/`;
- include the date handling and output paths in the prompt;
- avoid asking clarifying questions because cron runs without a user present;
- report failures clearly instead of failing silently.

Conceptual job shape:

```text
schedule: 0 6 * * *
workdir: /home/max-orca/Max_workspace/Programs/ClawMax
skills:
  - daily-ai-media-pipeline
  - ai-technical-report
  - wechat-article-drafting
```

## Quality Gates

The pipeline is complete only if:

- the report exists;
- sources are saved or clearly embedded;
- the article draft exists;
- `final-wechat-article.md` exists and contains the required sections and source links;
- `wechat-preview.html` exists and preserves title, required sections, source links, and local image references;
- `article.json` and `metadata.json` are valid JSON;
- `metadata.json.output_html_preview` points to `articles/YYYY-MM-DD/wechat-preview.html`;
- `metadata.json.generated_files` includes `wechat-preview.html` and every saved local image file;
- `image-assets.json` exists and matches `article.json.image_assets`;
- uncertainty is visible;
- the final output remains draft/review-only, with no auto-publishing;
- the user can review Markdown or HTML locally before publication.

## Common Pitfalls

1. Automating too early. Fix by stabilizing mock-source and manual runs before scheduling.
2. Treating the WeChat article as the source of truth. Fix by keeping the technical report as the factual base and `article.json` as the structured handoff for generated article artifacts.
3. Overwriting human edits during reruns. Fix by checking existing files and using versioned filenames or backup-then-restore when `--force` is used.
4. Hiding failures in scheduled runs. Fix by writing logs or returning clear error summaries.
5. Mixing secrets into `config.yaml`. Fix by storing only non-sensitive strategy config there.
6. Confusing local HTML preview with publishing. Fix by treating `wechat-preview.html` as a review artifact only until a separate WeChat publishing adapter and QA gate exist.

## Verification Checklist

- [ ] Date-specific report directory exists.
- [ ] Date-specific article directory exists.
- [ ] Technical report was generated before the WeChat draft.
- [ ] Source links or source records are preserved.
- [ ] WeChat draft contains `AI 前沿` and `浪里淘金`.
- [ ] Final Markdown article exists and contains source links.
- [ ] HTML preview exists and is review-only, not published.
- [ ] `article.json.image_assets` matches `image-assets.json`.
- [ ] `metadata.json.output_html_preview` points to `articles/YYYY-MM-DD/wechat-preview.html`.
- [ ] `metadata.json.generated_files` includes `wechat-preview.html` and every saved local image file.
- [ ] Human review remains required before publication.
- [ ] Reruns do not silently overwrite reviewed files.
