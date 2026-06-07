---
name: product-opportunity-analysis
description: Use when working inside the ClawMax project to turn daily AI technical reports and article bundles into lightweight product opportunity cards without building a full growth or commercialization system.
version: 1.0.0
author: Max / Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [clawmax, project-specific, product-strategy, opportunity-analysis, content-products]
    related_skills: [daily-ai-media-pipeline, ai-technical-report, wechat-article-drafting]
---

# Product Opportunity Analysis

## Overview

This is the project SOP for the first version of `ProductStrategyAgent` in ClawMax.

The goal is to read the daily technical report and optional WeChat article bundle, then produce a small set of product opportunity cards. The output should help the team decide what to test next, not pretend to be a complete product strategy department.

The first version must stay lightweight. User personas, topic conversion signals, reading-data feedback, title A/B tests, promotion strategy, commercialization, and content-product matrix planning are included as fields inside each opportunity card. They are not separate agents or separate systems yet.

## When to Use

Use this skill when:

- The user asks to implement or run `ProductStrategyAgent`.
- A task involves turning `reports/<label>/technical-report.md` into product opportunities.
- The user asks which AI technology trends can become tools, content products, services, templates, or automation products.
- The user wants to include simple growth or commercialization thinking without overcomplicating the third agent.

Do not use this skill for:

- Automatic advertising spend or campaign execution.
- Real financial forecasting.
- Full competitive analysis.
- Replacing human product judgment.
- Creating many specialized growth/data/marketing agents before the basic content pipeline is stable.

## Input Contract

Preferred inputs:

```text
reports/<label>/technical-report.md
reports/<label>/brief.json
reports/<label>/sources.json
articles/<label>/article.json
articles/<label>/final-wechat-article.md
articles/<label>/qa-report.json
```

The report is the factual base. The article bundle is useful because it reveals reader-facing angles, hooks, and content packaging.

## Output Contract

Write outputs under:

```text
products/<label>/
```

Required files:

```text
products/<label>/opportunity-cards.md
products/<label>/opportunities.json
products/<label>/metadata.json
```

Each opportunity should include:

- `name`
- `reality`: `real` or `hypothetical`
- summary
- target user
- user persona
- core scenario
- MVP scope
- implementation difficulty
- risk
- next experiment
- topic conversion signal
- reading-data feedback
- title A/B test
- promotion strategy
- commercial opportunity
- content matrix role
- evidence

## Required Real Product

Always include `ClawMax` as a real opportunity:

```text
name: ClawMax
reality: real
```

It should be framed as the actual project/product under development: an AI media department workflow that turns real-source technical reports into WeChat article bundles, image assets, automatic QA, and eventually draft/publishing gates.

## Hypothetical Products

Hypothetical opportunities are allowed and useful, but must be clearly labeled:

```text
reality: hypothetical
```

Good starter patterns:

- topic radar from source quality + reading feedback;
- reading-data feedback loop;
- content matrix planner;
- workflow template pack;
- QA/publishing gate module.

Do not imply these products exist, have users, or have validated revenue.

## Workflow

1. Identify the input label.
2. Read the technical report and structured files.
3. Read the article bundle if it exists.
4. Extract themes, reader-facing hooks, tools, workflows, and repeated pain points.
5. Create 3-6 opportunities.
6. Include `ClawMax` as the first or most important real opportunity.
7. Add 2-5 hypothetical opportunities that are small enough to test.
8. For each opportunity, add the growth/commercial fields as lightweight hypotheses.
9. Write Markdown cards and structured JSON.
10. Write metadata and run logs.

## Quality Bar

A good opportunity card should answer:

- Who has the problem?
- What exact scenario hurts?
- What is the smallest useful product version?
- What signal would prove readers or users care?
- What data should feed back into the next content/product cycle?
- What is the obvious risk?
- What can be tested in one week?

## Common Pitfalls

1. Making the third agent too large. Fix by keeping growth, data, A/B, promotion, and commercialization inside each card as short fields.
2. Calling hypothetical products real. Fix by using `reality: hypothetical` and plain wording like `假想产品`.
3. Turning every trend into a product. Fix by selecting only a few ideas with clear user pain.
4. Writing a business plan. Fix by outputting cards and next experiments only.
5. Ignoring ClawMax itself. Fix by always including ClawMax as the real product opportunity.
6. Losing traceability. Fix by preserving report/article/source paths in evidence fields.

## Verification Checklist

- [ ] `products/<label>/opportunity-cards.md` exists.
- [ ] `products/<label>/opportunities.json` exists.
- [ ] `products/<label>/metadata.json` exists.
- [ ] At least one opportunity is `ClawMax` with `reality: real`.
- [ ] Hypothetical ideas are labeled `hypothetical` / `假想产品`.
- [ ] Each opportunity includes user persona and next experiment.
- [ ] Each opportunity includes topic conversion, reading feedback, A/B title, promotion, commercialization, and content matrix fields.
- [ ] The output does not claim unvalidated products are already real.
