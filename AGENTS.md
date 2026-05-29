# AGENTS.md

## 项目概览

本项目目标是构建一个基于 Hermes 的 AI 公司新媒体部门工作流，让多个 Agent 分工协作，持续产出 AI 相关内容。

当前第一阶段聚焦两个核心 Agent：

- `TechnicalReportAgent`：每天早上 6 点启动，检索最新 AI 前沿信息，生成专业技术报告。
- `WeChatArticleAgent`：读取专业技术报告，生成适合微信公众号发布的口语化推文草稿。

后续可以扩展：

- `ProductStrategyAgent`：读取技术报告，评估是否能转化为虚拟产品或内容产品机会。

当前仓库仍处于早期阶段，公开需求主要来自 `README.md` 和 `PLANS.md`。实现时优先保持结构简单、可解释、方便新人理解，并让流程可以逐步从 mock 数据演进到真实检索和定时调度。

## 沟通与文档语言

- 默认用中文与用户沟通。
- 代码、命令、错误信息、API 名称、库名、文件路径、函数名、变量名保留英文。
- 面向用户的说明、计划、学习笔记和项目文档默认使用中文。
- 对初学者解释 Agent、MCP、Codex、Hermes、OpenAI API、Git、构建工具等概念时，要补充原因、上下文和简单例子。

## 工作模式

- 如果用户只是提问、讨论想法、要求分析或 review，保持只读，不修改文件。
- 只有当用户明确要求“修改 / 实现 / 修复 / 生成 / 删除 / patch / apply”等操作时，才编辑项目文件。
- 编辑前简短说明准备改哪些文件或区域。
- 编辑后说明改了什么，以及如何验证。
- 不要覆盖或回退用户已有改动。当前 `README.md` 可能存在用户未提交修改，处理前先查看 `git status` 和相关 diff。

## 计划与执行

- 小改动可以直接完成并简短总结。
- 如果任务涉及多文件、重构、长时间调试、工作流设计、迁移、硬件安全或用户要求计划，优先使用 `PLANS.md` / ExecPlan。
- ExecPlan 应自包含，主要用中文，持续记录目标、理解、步骤、进展、发现、决策、验证、风险和结果。
- 仓库内尚未建立 `PLANS.md` 时，不要为了小任务强行创建；复杂任务再创建或更新。

## 项目专属 Skills

本项目的 `skills/` 目录存放 ClawMax 项目专属 skills，用来沉淀 AI 新媒体部门工作流中的可复用方法、岗位 SOP 和质量检查标准。

命名原则：

- `profiles/` 描述“谁来做”：Agent 的人格、职责边界和默认工作风格。
- `skills/` 描述“怎么做”：可复用 SOP、输入输出、步骤、质量门槛和常见坑。
- 因此 skill 不按 Agent 命名，而按能力 / 流程命名。这样同一个 SOP 未来可以被人工、定时任务或不同 Agent 复用。

当前优先维护的项目 skills：

- `ai-technical-report`：生成每日 AI 专业技术报告。
- `wechat-article-drafting`：将专业技术报告改写成微信公众号草稿。
- `daily-ai-media-pipeline`：串联每日技术报告与公众号草稿生产流程。

Hermes 识别规则：

- 仓库内 `./skills/<skill-name>/SKILL.md` 是项目源文件，适合提交到 git，方便团队协作和审阅。
- Hermes 默认自动发现的是 `$HERMES_HOME/skills/`，通常是 `~/.hermes/skills/`；不同 profile 会使用对应 profile 的 Hermes home。
- 仅放在项目 `./skills/` 下时，当前会话可以通过 `read_file` 遵循，但 Hermes CLI 的 `-s <skill>`、`/skill <skill>` 或 cron job 的 `skills:` 不一定能自动识别。
- 为了让 Hermes 运行时可直接加载，本项目的 project-local skills 应同步到 `$HERMES_HOME/skills/clawmax/<skill-name>/SKILL.md`。
- 修改项目 `./skills/` 后，如果希望运行时生效，应重新同步到 Hermes skills 目录，并在新会话中使用 `/reload-skills` 或重启会话。

使用规则：

- 当用户要求生成技术报告、微信公众号草稿、每日内容流水线或修改相关工作流时，优先读取并遵循 `skills/` 目录下对应的 `SKILL.md`。
- 如果这些 skills 已同步到 Hermes 的 `$HERMES_HOME/skills/clawmax/`，可以使用 `skill_view`、`/skill <name>`、`hermes -s <name>` 或 cron job 的 `skills:` 加载。
- 如果当前会话无法通过 `skill_view` 找到，则直接读取仓库内对应文件。
- 这些 skills 是 ClawMax 项目的项目级规范。除非用户明确要求，不要将它们套用到其他项目。

## Skill 沉淀规则

本项目允许 Agent 在完成复杂任务后，将可复用工作流总结为项目专属 skill。

- 项目专属 skills 放在 `skills/<skill-name>/SKILL.md`。
- 只有当任务形成稳定、可重复、项目相关的流程时，才创建或更新 skill。
- 不要为一次性小任务、临时讨论或很快会过期的任务进度创建 skill。
- 不要把 PR 编号、commit hash、当天完成记录、临时 TODO 或短期状态写入 skill。
- skill 应记录可复用方法、适用场景、输入输出、步骤、常见坑和验证清单。
- 如果已有相关 skill，应优先更新旧 skill，而不是创建重复 skill。
- 创建或修改 skill 后，应验证 frontmatter 格式有效，并在最终回复中说明新增或更新了哪个 skill。

## 推荐项目结构

仓库尚未定型时，可优先考虑以下结构，除非后续代码框架另有约定：

```text
.
├── README.md
├── AGENTS.md
├── PLANS.md
├── config.yaml       # 非敏感运行配置
├── profiles/         # 不同agent人格文件与专属配置
├── skills/           # 项目专属 skill 源文件
├── memory/
│   ├── covered-topics.json       # 项目级报道记忆
│   └── source-quality.json       # 来源质量记录
├── runs/
│   ├── daily-report-runs.jsonl   # 运行总日志
│   └── <run-id>.json             # 单次运行详情
├── reports/          # 技术报告输出
├── articles/         # 微信稿件输出
├── tests/            # 单元测试或流程测试
└── docs/             # 设计说明、使用说明、决策记录
```

如果 Hermes 已经有固定项目结构，应优先贴合 Hermes 的约定，而不是强行套用新的目录设计。

## 当前业务范围

第一阶段内容生产链路建议保持清晰：

```text
Scheduler
↓
TechnicalReportAgent
↓
reports/YYYY-MM-DD/
↓
WeChatArticleAgent
↓
articles/YYYY-MM-DD/
↓
人工审阅 / 发布
```

微信公众号内容至少包含两个固定栏目：

- `AI 前沿`：把专业报告中的重点内容讲得更轻松易懂。
- `浪里淘金`：主动寻找有吸引力的 AI 项目、工具、案例或开发者玩法。

第一阶段默认不做自动发布，不做完全无人审核链路。

## 实现偏好

- 优先选择清晰、可维护的实现，避免过早抽象。
- 对 OpenAI API、Hermes、MCP、图像生成、文件保存等外部能力使用薄封装，便于替换和测试。
- 对报告生成流程保持阶段清楚：资料检索、资料摘要、专业报告生成、公众号改写、文件保存。
- 对结构化数据使用 JSON、YAML 或类型明确的数据结构，不依赖脆弱的字符串拼接。
- 为关键流程保留可测试边界，例如 prompt 渲染、资料归一化、报告文件命名、输出路径处理。
- 对来源信息保留可追溯字段，例如 `title`、`url`、`published_at`、`source_type`、`confidence`、`tags`。

## 配置约定

`config.yaml` 应该只放非敏感、可版本管理、与运行策略相关的配置，不要放真实密钥。

适合放进 `config.yaml` 的内容：

- 项目默认时区、语言、输出目录。
- 每日调度时间，例如 `06:00`。
- 各个 Agent 的启用开关。
- 检索主题列表，例如 AI 公司名单、重点技术领域、GitHub 搜索主题。
- 输出文件命名规则和保留天数。
- 模型名、temperature、max tokens 这类可公开的推理参数。
- 内容风格设置，例如微信公众号语气、栏目名称、每栏条目数。

不适合放进 `config.yaml` 的内容：

- `OPENAI_API_KEY`、cookie、token、数据库密码。
- 任何用户私密信息。
- 经常变化且只适合本机的临时调试值，除非项目明确约定。

敏感配置应放到 `.env` 或 Hermes 约定的 secret 配置中，只在代码里读取变量名，不在文档或日志中输出真实值。

## 安全与凭据

- 不要提交 `.env`、API key、token、cookie 或任何密钥。
- 读取或讨论环境变量时，只引用变量名，不输出真实值。
- 涉及网络检索、模型调用、图片生成或外部工具调用时，明确区分真实结果、模型推断和需要人工确认的内容。
- 生成报告时应尽量保留来源链接或引用信息，避免把未经确认的内容写成确定事实。

## 验证建议

- 修改代码后根据项目实际工具运行对应检查，例如测试、类型检查、lint 或最小可运行流程。
- 如果尚无测试框架，至少执行能验证当前改动的最小命令，并在最终回复中说明验证范围。
- 对生成文件功能，优先验证输出路径、文件名、编码和重复运行行为。
