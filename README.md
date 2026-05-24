# AI 技术报告数字员工

本项目基于 Hermes Agent 构建一个 AI 技术报告数字员工，用于自动生成每日 AI 专业技术报告，并进一步支持微信公众号草稿改写。

项目的核心思路是：

- `profiles/` 负责“谁来做”：定义 Agent 人格、职责边界和默认工作方式。
- `skills/` 负责“怎么做”：定义可复用 SOP、质量标准和流程。
- `scripts/` 负责把项目源文件同步到本地 Hermes runtime。
- `reports/` 和 `articles/` 分别保存技术报告和公众号草稿产物。

## 当前完成情况

已完成：

- TechnicalReportAgent 的人格、skills 和本地同步流程。
- 真实来源 AI 技术报告生成链路。
- 集成测试脚本。
- README / 安装 / 目录规范。

未完成：

- WeChatArticleAgent 的完整自动化生成链路。
- 日报到公众号草稿的完整联动验证。
- 每日定时调度。
- 自动配图与外部图片整合的完整策略。
- 公众号后台自动发布。
- ProductStrategyAgent。

当前仓库处于“日报生成已跑通，后续链路仍在搭建”的阶段。

## 项目架构

```text
Scheduler / 手动运行
↓
TechnicalReportAgent
↓
真实来源检索 + 资料整理 + 专业技术报告生成
↓
reports/YYYY-MM-DD/
↓
WeChatArticleAgent
↓
公众号草稿生成
↓
articles/YYYY-MM-DD/
↓
人工审阅 / 发布
```

第一阶段默认不做自动发布，所有报告和文章草稿都应先由人工审阅。

## 目录结构

```text
.
├── README.md
├── AGENTS.md
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
├── reports/
└── articles/
```

## 核心概念

### profiles：谁来做

`profiles/` 是项目中的 Agent 人格源文件。

例如：

- `profiles/technical-report-agent.md`：每日 AI 技术报告 Agent。
- `profiles/wechat-article-agent.md`：微信公众号草稿 Agent。
- `profiles/profiles.yaml`：声明项目 profile 如何安装到本地 Hermes runtime。

同步后，Hermes 会把这些 profile 安装到：

```text
~/.hermes/profiles/<profile-name>/SOUL.md
```

注意：`SOUL.md` 不是项目里的公用人格文件，而是 Hermes 每个 runtime profile 默认读取的入口文件名。项目源文件仍然是 `profiles/*.md`。

### skills：怎么做

`skills/` 是项目 SOP 源文件。

例如：

- `skills/ai-technical-report/SKILL.md`：如何生成专业技术报告。
- `skills/wechat-article-drafting/SKILL.md`：如何把技术报告改写成公众号草稿。
- `skills/daily-ai-media-pipeline/SKILL.md`：如何串联日报和公众号流程。

同步后，这些 skills 会安装到本地 Hermes runtime：

```text
~/.hermes/skills/clawmax/<skill-name>/
~/.hermes/profiles/<profile-name>/skills/clawmax/<skill-name>/
```

### prompt：本次运行参数

测试脚本和手动运行时会通过 `hermes chat -q "..."` 传入一次性的运行参数，例如：

- 本次使用哪个 profile
- 本次加载哪些 skills
- 本次是 real sources 还是 mock smoke test
- 本次输出到哪个目录
- 本次的检索预算

这些参数只描述“这一次任务怎么跑”，不应该替代人格文件或 SOP。长期质量标准必须放在 `profiles/` 和 `skills/` 中。

## Quickstart

### 0. 前置条件

需要先安装并配置 Hermes Agent：

```bash
hermes setup
```

确保默认 Hermes profile 已经配置好模型、provider、base_url 和 API key。

可以用下面命令检查：

```bash
hermes status --all
```

本项目不会把真实 API key 写入仓库。真实密钥只应存在于本地 Hermes 配置或本地环境变量中。

### 1. 克隆项目并进入目录

```bash
git clone https://github.com/Max-Orcatale/ClawMax.git
cd ClawMax
```

### 2. 同步项目 profiles 和 skills 到本地 Hermes runtime

如果你的默认 Hermes profile 已经能正常调用模型，运行：

```bash
python scripts/install_hermes_profiles.py --configure-from-default
```

这会同步：

- `profiles/*.md` 到 `~/.hermes/profiles/<profile>/SOUL.md`
- `skills/*` 到默认 Hermes skills 目录
- `skills/*` 到每个项目 profile 自己的 skills 目录
- 默认 Hermes model/provider/base_url/api_key 配置到项目 profile 的本地 runtime config

这个命令会写入本地 `~/.hermes/`，不会把真实密钥写入项目仓库。

### 3. 验证 profile 和 skills

```bash
hermes -p technicalreportagent status --all
hermes -p technicalreportagent skills list
```

你应该能看到 `technicalreportagent` profile，并且 skills 列表里包含：

```text
clawmax:ai-technical-report
clawmax:daily-ai-media-pipeline
clawmax:wechat-article-drafting
```

### 4. 生成一份真实来源技术报告

```bash
python -u tests/test_technical_report_agent_run.py --timeout 540
```

这个命令会：

- 使用 `technicalreportagent` profile
- 加载 `clawmax:ai-technical-report`
- 加载 `clawmax:daily-ai-media-pipeline`
- 自动检索真实来源
- 生成报告到 `reports/YYYY-MM-DD-real-test-HHMMSS/`
- 验证 `technical-report.md`、`sources.json`、`brief.json`

### 5. 查看生成结果

```bash
ls reports/*real-test-* | tail
sed -n '1,160p' reports/<generated-report-dir>/technical-report.md
```

或直接打开：

```bash
less reports/<generated-report-dir>/technical-report.md
```

## 常用命令

### 预览同步内容，不写入

```bash
python scripts/install_hermes_profiles.py --dry-run --configure-from-default
```

### 同步本地 Hermes runtime

```bash
python scripts/install_hermes_profiles.py --configure-from-default
```

### 运行真实来源技术报告测试

```bash
python -u tests/test_technical_report_agent_run.py --timeout 540
```

### 运行 mock 工程烟测

只验证工程链路，不生成真实日报：

```bash
python -u tests/test_technical_report_agent_run.py --mock-smoke
```

### 进入 TechnicalReportAgent 交互模式

```bash
hermes -p technicalreportagent \
  -s clawmax:ai-technical-report \
  -s clawmax:daily-ai-media-pipeline
```

进入后可以输入：

```text
生成今天的 AI 技术报告，输出到 reports/YYYY-MM-DD/
```

### 进入 WeChatArticleAgent 交互模式

```bash
hermes -p wechatarticleagent \
  -s clawmax:wechat-article-drafting \
  -s clawmax:daily-ai-media-pipeline
```

进入后可以输入：

```text
读取 reports/YYYY-MM-DD/technical-report.md 和 brief.json，生成微信公众号草稿到 articles/YYYY-MM-DD/
```

## 输出文件

### 技术报告输出

```text
reports/YYYY-MM-DD/
├── technical-report.md
├── sources.json
└── brief.json
```

说明：

- `technical-report.md`：专业技术报告正文。
- `sources.json`：结构化来源列表，保留 title、url、source_type、published_at、retrieved_at、summary、confidence、tags。
- `brief.json`：给公众号改写阶段使用的结构化摘要。

### 公众号草稿输出

```text
articles/YYYY-MM-DD/
└── wechat-article.md
```

## 报告质量标准

技术报告不是新闻摘要，也不是测试说明。它应该更像真实公司员工提交的技术情报/研究报告。

每条重点信息应尽量覆盖：

- 事实更新：发生了什么。
- 技术背景：相关模型、论文、API、仓库、benchmark 或产业背景。
- 关键变化：相比之前有什么新变化。
- 影响判断：为什么重要，影响谁。
- 风险与不确定性：哪些信息仍待确认，哪些只是厂商叙事或社区传闻。
- 后续观察：接下来应该跟踪什么信号。

默认要求：

- 自动检索真实来源。
- 不使用 mock sources 冒充日报。
- 不使用 `example.com` 作为事实来源。
- 不把工程测试说明写进专业报告正文。
- 不在专业报告里加入 `对内容创作的可用素材`，这属于公众号改写阶段。

## 图片规则

专业技术报告可以不只是文字。

如果某个主题需要图片，TechnicalReportAgent 可以：

- 生成图片，例如概念图、架构图、流程图。
- 从网上搜寻并引用图片，例如产品截图、论文图、benchmark 图、官方架构图。

要求：

- 图片应放在最能支撑正文的位置。
- 外部图片必须保留来源链接和版权/使用语境。
- 图片是辅助材料，不替代来源证据。
- 如果图片不是必要的，可以跳过。

## 配置与安全

- `config.yaml` 只放非敏感运行配置。
- 不要提交 `.env`、API key、token、cookie 或任何密钥。
- 真实模型配置应保存在本地 Hermes runtime 中。
- 修改 `profiles/` 或 `skills/` 后，需要重新运行同步脚本。

## 推荐开发流程

```text
修改 profiles/ 或 skills/
↓
python scripts/install_hermes_profiles.py --configure-from-default
↓
python -u tests/test_technical_report_agent_run.py --timeout 540
↓
检查 reports/YYYY-MM-DD-real-test-HHMMSS/
↓
确认质量后再进入公众号草稿阶段
```

## 上传前检查

```bash
git status --short
python -m py_compile scripts/install_hermes_profiles.py tests/test_technical_report_agent_run.py
python scripts/install_hermes_profiles.py --dry-run --configure-from-default
```

确认没有提交：

- `.env`
- API key / token / cookie
- 本地 `~/.hermes/` 内容
- 不希望公开的 `reports/` 或 `articles/` 产物

## 进一步阅读

- `AGENTS.md`
- `profiles/profiles.yaml`
- `profiles/technical-report-agent.md`
- `profiles/wechat-article-agent.md`
- `skills/ai-technical-report/SKILL.md`
- `skills/daily-ai-media-pipeline/SKILL.md`
- `skills/wechat-article-drafting/SKILL.md`
