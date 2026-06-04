# ExecPlan: ClawMax AI 新媒体部门

## 目标

搭建一个基于 Hermes 的 AI 新媒体部门工作流，让多个 Agent 分工协作，持续产出 AI 内容。

第一阶段只实现两个核心 Agent：

1. `TechnicalReportAgent`：每天早上 6 点启动，搜集和整理最新 AI 前沿信息，生成专业技术报告。
2. `WeChatArticleAgent`：读取专业技术报告，生成适合微信公众号发布的口语化推文。

后续阶段再扩展 `ProductStrategyAgent`：读取专业技术报告，评估 AI 前沿信息能否转化为虚拟产品设计方向。

## 当前进度

### 已完成

- TechnicalReportAgent 人格文件与 skills 体系。
- 本地 Hermes runtime 同步脚本。
- 真实来源技术报告生成链路。
- 技术报告集成测试脚本。
- WeChatArticleAgent 文章生成脚本：读取已有报告，调用另一个 `wechatarticleagent` profile，输出 `wechat-draft.md`、`final-wechat-article.md`、`wechat-preview.html`、`article.json`、`metadata.json`、`image-assets.json` 和 `images/`。
- 公众号结构化数据第一版：`article.json` 用于后续自动排版、配图、QA 和发布。
- 图片最小产物规范：报告和文章都使用本地 `images/` 目录与 `image-assets.json` 清单，先保证能保存、生成和引用图片。
- 公众号最终文章包契约：`article.json` 是结构化源，后处理生成 `final-wechat-article.md`、`wechat-preview.html`、`image-assets.json`、`images/` 和完整 `metadata.json.generated_files`，其中 `generated_files` 覆盖顶层产物和实际保存的本地图片文件。
- 项目级 `memory/` 业务记忆：`covered-topics.json` 与 `source-quality.json`。
- 项目级 `runs/` 运行日志：追加式总日志和单次运行详情。
- README 基础教程与项目架构说明。

### 进行中

- WeChatArticleAgent 文章生成质量打磨与真实样例验证，重点是降低报告腔，让文章更接近公众号内容产品。
- 报告到最终公众号文章包的完整联动验证。
- 将真实来源日报生成进一步稳定化。

### 未完成

- 每日定时调度。
- 自动配图与外部图片整合的完整策略（当前先做最小图片产物，不做复杂设计系统）。
- 公众号后台自动发布。
- ProductStrategyAgent。

当前仓库处于“日报生成已跑通，后续链路仍在搭建”的阶段。

## 当前理解

用户想做的不是单个写作工具，而是一个小型“AI 内容公司”的自动化部门。

整体逻辑是：

```text
每天 06:00 定时启动
↓
TechnicalReportAgent 搜集 AI 前沿信息
↓
生成专业技术报告
↓
WeChatArticleAgent 改写成微信公众号推文，并生成 `final-wechat-article.md`、`wechat-preview.html` 与结构化 `article.json`
↓
自动 QA / 排版 / 配图 / 发布能力逐步接入
```

内容风格上有两个层次：

- 专业报告：偏严肃、准确、可追溯，适合内部阅读和决策。
- 微信推文：口语化、有趣、有传播感，不直接照搬报告。

微信公众号推文至少包含两个栏目：

- `AI 前沿`：把专业报告中的重要内容讲得更轻松、更容易懂。
- `浪里淘金`：Agent 自主寻找有吸引力的 AI 项目、工具、玩法或案例，例如 GitHub 上的新项目、开发者实验、AI 辅助游戏通关等。

## 非目标

第一阶段暂不做以下内容：

- 自动登录微信公众号后台并直接发布（当前先生成草稿、结构化数据、最终 Markdown 和本地 HTML 预览，最终目标仍是全自动发布）。
- 产品 Agent 的完整实现。
- 多平台分发，例如小红书、B 站、知乎、Twitter/X。
- 复杂的用户画像、投放策略和商业化分析。

这些可以在核心内容生产流程稳定后再做。

## Agent 分工

### TechnicalReportAgent

职责：

- 每天 6 点定时启动。
- 搜寻最新 AI 前沿信息。
- 覆盖顶流 AI 公司动态，例如 OpenAI、Anthropic、Google DeepMind、Meta AI、xAI、Mistral、DeepSeek 等。
- 覆盖重点专业领域，例如具身智能、机器人、multimodal models、agents、reasoning、code generation、AI infra 等。
- 检索论文、技术博客、产品更新、开源项目、benchmark、行业事件。
- 对信息做去重、分类、可信度判断和摘要。
- 输出一份结构化专业技术报告。

建议输出格式：

```text
reports/YYYY-MM-DD/technical-report.md
reports/YYYY-MM-DD/sources.json
reports/YYYY-MM-DD/brief.json
```

专业报告建议包含：

- 今日摘要
- 重点新闻
- 论文与研究进展
- 公司与产品动态
- 开源项目与开发者生态
- 具身智能专题
- 风险、争议与待确认信息
- 来源链接

### WeChatArticleAgent

职责：

- 读取 `TechnicalReportAgent` 的报告。
- 将严肃内容转化为微信公众号风格推文。
- 语言更口语化，更像一个懂技术的人在给朋友讲今天 AI 圈发生了什么。
- 保留必要事实，不夸大，不把不确定内容写成确定结论。
- 自主补充 `浪里淘金` 栏目：搜索 GitHub、Hacker News、Product Hunt、Reddit、开发者博客、社交媒体热点等渠道，寻找好玩、有用、有传播点的 AI 项目。

推文建议栏目：

```text
标题
开场白
AI 前沿
浪里淘金
今天值得想一想
结尾互动
```

内容要求：

- `AI 前沿`：来自专业报告，但要简化表达。
- `浪里淘金`：不要求项目极其先进，但必须有吸引力、容易讲清楚、能让读者产生“我想试试”的感觉。
- 每个项目尽量包含：一句话介绍、为什么有意思、适合谁、链接、风险或限制。
- 保留人工审核位置，避免自动发布错误信息。

### ProductStrategyAgent（后续）

职责：

- 读取专业技术报告。
- 判断某些新技术是否能转化为虚拟产品原型、内容产品、工具产品或自动化服务。
- 输出产品机会卡片。

暂定输出：

```text
products/YYYY-MM-DD/opportunity-cards.md
```

每张机会卡片包含：

- 产品想法
- 来源技术或趋势
- 目标用户
- 核心使用场景
- MVP 功能
- 实现难度
- 风险
- 下一步实验

## 系统架构草案

建议先采用简单文件流转，降低早期复杂度：

```text
Hermes Scheduler
↓
TechnicalReportAgent
↓
reports/YYYY-MM-DD/
↓
WeChatArticleAgent
↓
articles/YYYY-MM-DD/
├── wechat-draft.md
├── final-wechat-article.md
├── wechat-preview.html
├── article.json
├── image-assets.json
└── images/
↓
人工审阅
↓
手动发布到微信公众号
```

推荐目录结构：

```text
.
├── README.md
├── AGENTS.md
├── PLANS.md
├── config.yaml
├── profiles/
│   ├── profiles.yaml
│   ├── technical-report-agent.md
│   └── wechat-article-agent.md
├── skills/
│   ├── ai-technical-report/
│   ├── daily-ai-media-pipeline/
│   └── wechat-article-drafting/
├── scripts/
│   └── install_hermes_profiles.py
├── tests/
│   └── test_technical_report_agent_run.py
├── memory/
│   ├── covered-topics.json
│   └── source-quality.json
├── runs/
│   ├── daily-report-runs.jsonl
│   └── <run-id>.json
├── reports/
└── articles/
```

`memory/` 是 ClawMax 项目级业务记忆，记录报道历史和来源质量；`runs/` 是项目级运行日志。Hermes 自带记忆仍用于用户偏好、环境经验和通用工作习惯，不作为 ClawMax 报道历史的唯一来源。

## 数据与来源

第一阶段建议支持这些来源类型：

- Web search：最新新闻、公司博客、技术博客。
- arXiv / Papers with Code：论文和研究趋势。
- GitHub search：开源项目、star 增长、近期更新、README 质量。
- 公司官方来源：OpenAI、Anthropic、Google DeepMind、Meta AI 等官方 blog 或 changelog。
- 社区来源：Hacker News、Reddit、Product Hunt 等，主要用于发现 `浪里淘金` 素材。

对每条来源建议保存：

```json
{
  "title": "string",
  "url": "string",
  "source_type": "paper | company_blog | github | news | community",
  "published_at": "string",
  "retrieved_at": "string",
  "summary": "string",
  "confidence": "high | medium | low",
  "tags": ["agent", "embodied-ai"]
}
```

## 调度策略

目标是每天早上 6 点启动。

可选方案：

- 如果 Hermes 内置 scheduler，优先使用 Hermes scheduler。
- 如果 Hermes 暂时没有稳定调度能力，可以先用 `cron` 或系统任务触发 CLI 命令。
- 本地开发阶段可以先手动运行 `daily_media_pipeline`，确认输出质量后再接定时任务。

建议保留手动重跑能力：

```text
run-daily --date 2026-05-23
run-daily --date today --skip-search
```

## 第一阶段实施步骤

### Step 1: 固化输出格式

定义 `TechnicalReportAgent` 和 `WeChatArticleAgent` 的输入输出文件格式。

验收标准：

- 能手动放入一份 sources 数据。
- 能生成稳定结构的专业报告。
- 能从专业报告生成一篇公众号草稿。

### Step 2: 固化 profiles 与 skills

项目长期规则不放在临时 prompt 里，而是放在：

- `profiles/technical-report-agent.md`
- `profiles/wechat-article-agent.md`
- `skills/ai-technical-report/SKILL.md`
- `skills/wechat-article-drafting/SKILL.md`
- `skills/daily-ai-media-pipeline/SKILL.md`

验收标准：

- profile 明确“谁来做”。
- skill 明确“怎么做”。
- 测试脚本里的 prompt 只保留本次运行参数。
- 修改 profile 或 skill 后能通过同步脚本写入本地 Hermes runtime。

### Step 3: 实现最小 Agent 流程

先不追求复杂检索，做一个本地可运行的最小流程：

```text
读取 mock sources
↓
生成 technical-report.md
↓
生成 wechat-draft.md、final-wechat-article.md、wechat-preview.html、article.json 和图片包
```

验收标准：

- 一条命令可以跑完整流程。
- 输出文件按日期保存。
- 重复运行不会覆盖人工修改稿，或者会生成清晰的新版本。

### Step 4: 接入真实检索

逐步加入 Web search、GitHub search、论文搜索和官方来源。

验收标准：

- 每条信息保留来源链接。
- 能区分高可信来源和低可信来源。
- 技术报告里有 `待确认信息` 区域。

### Step 5: 加入每日调度

把可手动运行的流程接入每天 6 点调度。

验收标准：

- 到点自动运行。
- 运行日志可查看。
- 失败时有错误记录，不静默失败。

### Step 6: 人工审核与发布交接

在自动生成后保留人工审核流程。

验收标准：

- 公众号文章足够接近可发布状态。
- 最终文章中所有外链、事实和项目介绍可追溯。
- 人工只需要做标题、语气、图片和风险把关。

## 内容质量标准

专业报告：

- 准确性优先。
- 尽量引用原始来源。
- 明确标注不确定信息。
- 不把营销文案当作事实。
- 对论文和项目给出简短技术判断，而不是只做搬运。

微信公众号推文：

- 轻松、有趣、可读。
- 不牺牲基本事实准确性。
- 每个板块有清楚的读者收益。
- `浪里淘金` 要有“想点开看看”的吸引力。
- 避免过度标题党。

## 风险与对策

- 风险：搜索结果质量不稳定。
  对策：优先官方来源、论文来源和高质量社区来源；保存来源与可信度。

- 风险：模型生成内容出现幻觉。
  对策：要求每个关键事实绑定来源；低可信内容进入 `待确认信息`。

- 风险：微信公众号内容太严肃，没有传播感。
  对策：推文 Agent 单独定义口语化风格，不直接复制专业报告。

- 风险：`浪里淘金` 变成普通项目列表。
  对策：筛选标准加入“好讲、好玩、好试、能激发转发”的维度。

- 风险：自动发布带来合规或事实错误。
  对策：第一阶段只生成草稿、最终 Markdown、HTML 预览和本地素材包，不自动发布。

## 进展记录

- 2026-05-23：创建本 ExecPlan，明确第一阶段范围：专业技术报告 Agent 和微信公众号推文 Agent；产品 Agent 暂列为后续扩展。

## 当前状态更新

- 已验证 TechnicalReportAgent 的真实来源日报生成链路。
- WeChatArticleAgent 已具备最终公众号文章包输出：`wechat-draft.md`、`final-wechat-article.md`、`wechat-preview.html`、`article.json`、`metadata.json`、`image-assets.json` 和 `images/`。
- 图片和预览链路已明确强制产物规范：公众号文章原则上不少于 5 张本地图片，其中至少 1 张 AI 生成图；保存到本地 `images/`，记录 `image-assets.json`，Markdown/HTML/JSON 使用相对路径引用。
- 自动调度、复杂自动配图、自动发布仍未完成。
- 后续规划应围绕“日报已通、最终文章包初通、调度未通、图片先最小可用”这一真实状态继续推进。

## 待决策问题

1. Hermes 项目最终使用 Python、TypeScript，还是沿用已有 Hermes 模板？
2. OpenAI API 调用是直接在本项目中封装，还是通过 Hermes 已有工具层调用？
3. 搜索能力使用哪种来源：OpenAI 内置 Web search、第三方搜索 API、浏览器自动化，还是手工来源列表？
4. 微信公众号是否只生成 Markdown 草稿，还是后续接入排版 HTML / 图片素材？当前决策：先生成 `final-wechat-article.md` + `wechat-preview.html` + `article.json` + 本地图片包，其中 HTML 是本地预览/审阅产物，不代表已接入公众号后台发布。
5. `浪里淘金` 的素材范围是否允许包含游戏、娱乐、开发者玩具和非严肃 demo？

## 下一步

建议先从最小可运行版本开始：

1. 继续提升 `WeChatArticleAgent` 的真实文章质量，减少报告腔并加强读者收益感。
2. 验证最终文章包契约：`final-wechat-article.md`、`wechat-preview.html`、`article.json`、`metadata.json.generated_files`、`image-assets.json` 与 `images/` 一致。
3. 接入每天 6 点调度。

完成这一步后，再完善复杂自动配图、排版和调度。
