# AI 技术报告数字员工

本项目基于 Hermes Agent 构建一个 AI 技术报告数字员工，用于自动生成每日 AI 专业技术报告，并进一步支持微信公众号草稿改写。

项目的核心思路是：

- `profiles/` 负责“谁来做”：定义 Agent 人格、职责边界和默认工作方式。
- `skills/` 负责“怎么做”：定义可复用 SOP、质量标准和流程。
- `scripts/` 负责把项目源文件同步到本地 Hermes runtime。
- `memory/` 保存 ClawMax 项目级业务记忆，例如已报道话题和来源质量。
- `runs/` 保存每次日报生成的运行日志。
- `reports/` 和 `articles/` 分别保存技术报告和公众号草稿产物。

## 当前完成情况

已完成：

- TechnicalReportAgent 的人格、skills 和本地同步流程。
- 真实来源 AI 技术报告生成链路，输出 `technical-report.md`、`sources.json`、`brief.json`、报告图片清单和运行日志。
- WeChatArticleAgent 的公众号文章包生成链路，输出 `wechat-draft.md`、`final-wechat-article.md`、`wechat-preview.html`、`article.json`、`metadata.json`、`image-assets.json` 和 `images/`。
- 公众号文章图片约束：至少 5 张本地图片，其中至少 3 张信源/官方/截图类图片，至少 1 张真实 `image_generate` AI 位图。
- 微信公众号官方 API 草稿创建脚本：可以上传正文图片、上传封面素材、调用 `draft/add` 创建后台草稿，并写入 `wechat-publish.json`。
- profile / skill / runtime env 同步流程：`profiles/profiles.yaml` 声明本地运行所需 env key，`scripts/install_hermes_profiles.py --configure-from-default` 从默认 Hermes `.env` 同步到 profile runtime。
- 集成测试、mock 测试和运行日志。

未完成：

- 每日 6 点定时调度。
- 微信后台自动发布 / 群发。当前只允许创建草稿，`auto_publish=false`。
- 更复杂的公众号排版系统、发布前视觉 QA 和草稿自动回读校验。
- ProductStrategyAgent。

当前仓库处于“真实来源日报、公众号文章包、微信公众号后台草稿创建均已跑通；定时调度和自动发布尚未接入”的阶段。

## 项目架构

```text
Scheduler / 手动运行
↓
TechnicalReportAgent
↓
真实来源检索 + 资料整理 + 专业技术报告生成
↓
reports/<run-label>/
↓
WeChatArticleAgent
↓
公众号文章包生成 + 图片包 + 本地 HTML 预览
↓
articles/<run-label>/
↓
scripts/publish_wechat_article.py
↓
微信公众号官方 API：上传图片 + 创建草稿
↓
人工审阅 / 手动发布
```

第一阶段默认不做自动发布或群发。项目可以通过官方 API 创建微信公众号后台草稿，但最终发布仍需人工审阅。

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
│   ├── collect_source_images.py
│   ├── finalize_wechat_article.py
│   ├── install_hermes_profiles.py
│   └── publish_wechat_article.py
├── tests/
│   ├── test_finalize_wechat_article.py
│   ├── test_publish_wechat_article.py
│   ├── test_technical_report_agent_run.py
│   └── test_wechat_article_agent_run.py
├── memory/
│   ├── covered-topics.json
│   └── source-quality.json
├── runs/
│   ├── .gitkeep
│   ├── daily-report-runs.jsonl
│   └── <run-id>.json
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

### 项目级 memory：业务状态

Hermes 本身有持久记忆功能，适合保存用户偏好、环境经验和通用工作习惯。ClawMax 另外维护项目级 `memory/`，用于保存可审计、可提交、团队共享的业务状态。

当前项目记忆包括：

- `memory/covered-topics.json`：记录已经报道过的话题、最后报道时间、重复报道策略。用于判断某个 AI 话题是否需要再次进入日报。
- `memory/source-quality.json`：记录来源站点的出现次数、置信度分布和标签。用于后续优化检索优先级与失败兜底。

两者不要混用：

- 用户偏好、Hermes 使用经验：写入 Hermes 记忆。
- ClawMax 的报道历史、来源质量、运行状态：写入项目 `memory/` 和 `runs/`。

### runs：运行日志

`runs/` 保存每次日报生成的结构化运行日志：

- `runs/daily-report-runs.jsonl`：追加式总日志。
- `runs/<run-id>.json`：单次运行详情。

日志包含运行模式、profile、skills、输出文件、耗时、来源数量、更新了多少项目记忆，以及 Hermes 子进程继承了哪些代理环境变量。

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
- `profiles/profiles.yaml` 声明的本地 env key，例如 `OPENAI_API_KEY`、`WECHAT_MP_APPID`、`WECHAT_MP_APPSECRET`，从默认 Hermes `.env` 同步到 profile runtime `.env`

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

### 5. 基于技术报告生成最终公众号文章包

```bash
python -u tests/test_wechat_article_agent_run.py \
  --report-label <generated-report-dir> \
  --timeout 540
```

这个命令会：

- 使用另一个 Hermes profile：`wechatarticleagent`。
- 加载 `clawmax:wechat-article-drafting`。
- 加载 `clawmax:daily-ai-media-pipeline`。
- 读取 `reports/<generated-report-dir>/technical-report.md`、`sources.json`、`brief.json`。
- 生成 `articles/<generated-report-dir>/wechat-draft.md`。
- 生成结构化数据 `articles/<generated-report-dir>/article.json`。
- 运行后处理，生成 `articles/<generated-report-dir>/final-wechat-article.md`。
- 生成轻量本地 HTML 预览 `articles/<generated-report-dir>/wechat-preview.html`，用于浏览器审阅排版效果。
- 生成图片清单 `articles/<generated-report-dir>/image-assets.json` 和自包含图片目录 `articles/<generated-report-dir>/images/`。
- 生成交接元数据 `articles/<generated-report-dir>/metadata.json`，其中 `generated_files` 会列出 Markdown、HTML、JSON 和图片清单。
- 让公众号稿件更接近内容产品，而不是专业报告缩写；文风参考只来自用户后续明确提供的公众号素材或可追溯来源。
- 在文末生成 `参考与信息来源`；如果实际采用这些公众号作为信息来源或选题线索，必须注明。
- 校验必需栏目、JSON schema、最终 Markdown、HTML 预览和图片 manifest。
- 写入 `runs/wechat-article-runs.jsonl` 和 `runs/<run-id>.json`。

这里的 Python 脚本不是公众号写稿程序。真正写公众号内容的是 Hermes 里的 `WeChatArticleAgent`；Python 只负责调度、传参、校验和记录日志。

### 6. 可选：创建微信公众号后台草稿

如果你的公众号已经启用开发者密码，并配置好 IP 白名单，可以把本地文章包提交到公众号后台草稿箱：

```bash
python scripts/publish_wechat_article.py \
  --article-label <generated-report-dir> \
  --mode draft
```

这个脚本会：

- 读取 `articles/<generated-report-dir>/article.json` 和 `image-assets.json`。
- 上传正文图片到微信，替换成本地正文 HTML 中可用的微信图片 URL。
- 上传封面图，获取 `thumb_media_id`。
- 调用微信公众号官方 API `draft/add` 创建草稿。
- 写入 `articles/<generated-report-dir>/wechat-publish.json`。

它不会自动发布或群发，`auto_publish` 固定为 `false`。

如果只想验证本地文章包和发布 payload，不调用微信 API：

```bash
python scripts/publish_wechat_article.py \
  --article-label <generated-report-dir> \
  --mode draft \
  --dry-run
```

### 7. 查看生成结果

```bash
sed -n '1,160p' articles/<generated-report-dir>/final-wechat-article.md
python -m json.tool articles/<generated-report-dir>/article.json | sed -n '1,160p'
python -m json.tool articles/<generated-report-dir>/metadata.json | sed -n '1,160p'
```

或直接打开：

```bash
less articles/<generated-report-dir>/final-wechat-article.md
xdg-open articles/<generated-report-dir>/wechat-preview.html 2>/dev/null || true
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

### 运行公众号文章包生成测试

```bash
python -u tests/test_wechat_article_agent_run.py \
  --report-label <generated-report-dir> \
  --timeout 540
```

这个脚本使用 `wechatarticleagent` profile 调用另一个公众号 Agent。Python 只负责选择输入报告、传入本次运行参数、校验 `wechat-draft.md` / `final-wechat-article.md` / `wechat-preview.html` / `article.json` / `metadata.json` / `image-assets.json`、写入运行日志；公众号正文和结构化数据由 WeChatArticleAgent 生成，最终 Markdown、HTML 预览和图片包由后处理脚本稳定产出。

### 创建微信公众号后台草稿

```bash
python scripts/publish_wechat_article.py \
  --article-label <generated-report-dir> \
  --mode draft
```

调试时可先 dry-run：

```bash
python scripts/publish_wechat_article.py \
  --article-label <generated-report-dir> \
  --mode draft \
  --dry-run
```

该脚本会强制微信 API 请求不走代理，避免代理出口 IP 轮换导致微信公众号 IP 白名单错误。

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

### 公众号文章输出

```text
articles/YYYY-MM-DD-or-report-label/
├── wechat-draft.md          # 公众号 Markdown 草稿
├── final-wechat-article.md  # 最终公众号 Markdown 文章，用于人工检查或后续发布适配
├── wechat-preview.html      # 本地 HTML 预览，用于浏览器审阅排版效果
├── article.json             # 结构化文章数据，后续排版、配图、发布使用
├── image-assets.json        # 文章图片清单，记录本地路径、来源、说明和状态
├── images/                  # 文章本地图片，可由报告图片复制或图像模型生成
├── metadata.json            # 本次生成的交接元数据
└── wechat-publish.json      # 可选：微信官方 API 草稿创建 manifest
```

说明：

- `wechat-draft.md`：面向读者的公众号草稿，包含 `AI 前沿` 和 `浪里淘金`。
- `final-wechat-article.md`：由 `article.json` 后处理生成的最终 Markdown 文章，包含摘要、正文栏目、参考来源和本地图片引用，是当前阶段交给人工检查/后续发布适配的主文件。
- `wechat-preview.html`：由同一份结构化数据生成的轻量 HTML 预览，CSS 内嵌，图片使用本地 `./images/...` 相对路径，方便在浏览器里检查排版；它不是已发布到公众号后台的 HTML。
- `article.json`：结构化文章对象，包含标题候选、摘要、sections、sources、risk_flags、`style_references`、`external_reference_accounts`、`source_attribution_note`、`image_assets` 和 `auto_publish_eligible=false`。
- `image-assets.json`：文章图片清单，和 `article.json.image_assets` 保持一致。
- `images/`：文章本地图片目录。图片可以从技术报告复制，也可以由图像模型生成；Markdown 和 HTML 只引用这里的相对路径。
- `metadata.json`：记录输入报告、输出文件、生成 profile 和 `auto_publish=false`；必须包含 `output_final_article`、`output_html_preview`、`output_image_assets`、`output_images_dir` 和完整 `generated_files`，其中 `generated_files` 要列出顶层产物和实际保存的本地图片文件。
- `wechat-publish.json`：当运行 `scripts/publish_wechat_article.py` 时生成。`status=dry_run` 表示只生成本地预览 manifest；`status=draft_created` 表示已经通过微信官方 API 创建后台草稿。该文件不记录 AppSecret 或 access_token。
- 当前阶段不自动发布；可以创建微信公众号后台草稿，但最终发布/群发仍需人工审阅。

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
- 检索窗口不是只看日历当天，而是近期滚动窗口：公司/产品/新闻通常看近 7-14 天，论文、benchmark、GitHub 项目和开发者工具可看近 30-90 天。
- 如果某个主题以前已经提过，只有在出现新版本、新证据、热度继续升高、采用信号、benchmark 更新或争议升级时才再次纳入。
- 覆盖来源应包含官方更新、论文/benchmark、GitHub 项目/Release、开发者生态信号和可信技术媒体。
- 不使用 mock sources 冒充日报。
- 不使用 `example.com` 作为事实来源。
- 不把工程测试说明写进专业报告正文。
- 不在专业报告里加入 `对内容创作的可用素材`，这属于公众号改写阶段。

## 图片规则

当前阶段图片和排版流程保持简单但不再可选：公众号文章原则上不少于 5 张本地图片，其中至少 1 张为 AI 生成图；图片必须保存好、能正确生成或复用、能在 Markdown、HTML 预览和 JSON 中正确引用。暂不做复杂的 Canva 式设计或自动发布后台适配。

技术报告侧可以生成或保存图片：

- 输出目录：`reports/<label>/images/`。
- 图片清单：`reports/<label>/image-assets.json`。
- 生成提示词：只在使用图像生成时写入 `reports/<label>/image-prompts.json`。
- 适合生成的图片：概念图、架构图、流程图、封面图。
- 适合保存来源图片的情况：产品截图、论文图、benchmark 图、官方架构图。

公众号文章侧要形成自包含图片包：

- 输出目录：`articles/<label>/images/`。
- 图片清单：`articles/<label>/image-assets.json`。
- 优先复用并复制 `reports/<label>/images/` 中有用的图片。
- 必要时再生成简单封面图或解释图。
- `wechat-draft.md` 使用相对路径，例如 `![配图说明](./images/hero.png)`。
- `final-wechat-article.md` 是当前阶段主交付文件，也必须只使用 `./images/...` 相对路径。
- `wechat-preview.html` 是轻量本地 HTML 预览，也必须使用本地 `./images/...` 相对路径，不链接临时外部图片。
- `article.json.image_assets` 必须和 `image-assets.json` 指向同一批本地图片。

要求：

- 图片应放在最能支撑正文的位置。
- 外部图片必须保留来源链接和版权/使用语境。
- 生成图必须标注为概念图/解释图，不当成事实证据。
- 不用图像模型伪造产品截图、官方 logo、benchmark 图或论文图。
- 如果公众号文章图片不满足最低要求，应重新生成或修复文章包，不要把无图稿当作合格公众号文章。
- 发布到微信草稿箱时，脚本会把本地 `./images/...` 上传为微信图片 URL；`wechat-preview.html` 仍保留本地相对路径，仅用于本地审阅。

## 常见问题

### 网络检索超时或连接被重置怎么办？

真实来源检索依赖外部网站，出现 timeout、connection reset、TLS reset 或 403 都是正常风险。

建议处理方式：

- 确认本机代理环境变量是否生效：`env | grep -Ei '^(http|https|all|no)_proxy='`。
- 对每个网络请求设置短超时，例如 10-20 秒。
- 单个来源失败时跳过并记录，不要无限重试。
- 优先使用更稳定的官方 RSS/API/GitHub API/arXiv API，而不是重网页爬取。
- 对容易失败的站点准备备用来源，例如官方 blog、GitHub release、arXiv abs 页面、可信二级报道。
- 不要因为某个站点失败而让整份日报失败；只要剩余来源足够，报告应继续生成，并在风险区标注覆盖不足。

当前测试脚本会显式把父进程里的 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`、`NO_PROXY` 及其小写形式传给 Hermes 子进程，并在运行开始时打印 `Proxy env inherited by Hermes`。这能确认 Hermes 进程启动时带了代理变量；但具体某个站点是否成功经过代理，还取决于对应工具/库是否支持这些环境变量。

### `FAIL: brief.json missing key: title` 是什么意思？

这表示报告主体和 `sources.json` 可能已经生成了，但测试脚本在校验 `brief.json` 时发现缺少必填字段 `title`。

`brief.json` 是给后续公众号改写阶段使用的结构化交接文件，必须包含：

```json
{
  "date": "YYYY-MM-DD",
  "title": "报告标题",
  "summary": "摘要",
  "top_items": [],
  "risks": [],
  "ready_for_wechat_drafting": true
}
```

如果缺少 `title`，说明 Agent 没有完全遵守输出 schema。修复方式是更新 `skills/ai-technical-report/SKILL.md` 或重新运行生成，让 `brief.json` 带上完整字段。

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
python -m py_compile scripts/install_hermes_profiles.py scripts/finalize_wechat_article.py scripts/publish_wechat_article.py tests/test_technical_report_agent_run.py tests/test_wechat_article_agent_run.py tests/test_finalize_wechat_article.py tests/test_publish_wechat_article.py
python tests/test_finalize_wechat_article.py
python -m pytest tests/test_publish_wechat_article.py -q -o 'addopts='
python scripts/install_hermes_profiles.py --dry-run --configure-from-default
```

确认没有提交：

- `.env`
- API key / token / cookie
- 本地 `~/.hermes/` 内容
- 不希望公开的 `reports/` 或 `articles/` 产物
- `wechat-publish.json` 中的草稿 media_id 如果不希望公开，也不要提交

## 进一步阅读

- `AGENTS.md`
- `profiles/profiles.yaml`
- `profiles/technical-report-agent.md`
- `profiles/wechat-article-agent.md`
- `skills/ai-technical-report/SKILL.md`
- `skills/daily-ai-media-pipeline/SKILL.md`
- `skills/wechat-article-drafting/SKILL.md`
