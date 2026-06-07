#!/usr/bin/env python3
"""Run Hermes WeChatArticleAgent against an existing ClawMax technical report.

This script is an integration harness, not the article writer.

Architecture:
  - Python validates inputs, builds a short per-run prompt, launches Hermes with
    the `wechatarticleagent` profile, validates generated files, and records run logs.
  - Hermes / WeChatArticleAgent reads the technical report and writes the WeChat
    draft and structured article data.

The Python code intentionally does not generate article prose. It only enforces
file contracts so the workflow can become automated safely.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.finalize_wechat_article import finalize_wechat_article_bundle
from scripts.qa_article_bundle import qa_article_bundle

REPORTS_DIR = REPO_ROOT / "reports"
ARTICLES_DIR = REPO_ROOT / "articles"
RUNS_DIR = REPO_ROOT / "runs"

PROFILE_NAME = "wechatarticleagent"
WECHAT_SKILL = "clawmax:wechat-article-drafting"
PIPELINE_SKILL = "clawmax:daily-ai-media-pipeline"
FINAL_ARTICLE_FILENAME = "final-wechat-article.md"
HTML_PREVIEW_FILENAME = "wechat-preview.html"
IMAGE_ASSETS_FILENAME = "image-assets.json"
IMAGES_DIRNAME = "images"
STYLE_REFERENCE_ACCOUNTS = ("Kyro AI Tech", "说说说来话长", "数字生命卡兹克", "逛逛 Github")
MIN_ARTICLE_IMAGES = 5
MIN_AI_GENERATED_IMAGES = 1
MIN_SOURCE_DERIVED_IMAGES = 3
MAX_COVER_IMAGES = 1
MAX_GENERATED_SVG_IMAGES = 0
SOURCE_DERIVED_IMAGE_KINDS = {
    "source_image",
    "source_screenshot",
    "official_image",
    "official_screenshot",
    "paper_figure",
    "github_screenshot",
    "product_screenshot",
    "webpage_screenshot",
    "og_image",
    "web_source",
}
BITMAP_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
FORBIDDEN_PUBLIC_BODY_PHRASES = (
    "技术报告里",
    "这份技术报告",
    "本次未",
    "本文未",
    "当前环境",
    "style corpus",
    "source_attribution_note",
    "auto_publish",
    "结构化数据",
    "生成流程",
    "ClawMax TechnicalReportAgent",
    "ClawMax sources",
    "ClawMax brief",
)

REQUIRED_REPORT_FILES = ("technical-report.md", "sources.json", "brief.json")
REQUIRED_DRAFT_MARKERS = (
    "# ",
    "## 开场白",
    "## AI 前沿",
    "## 浪里淘金",
    "## 今天值得想一想",
    "## 结尾互动",
    "## 参考与信息来源",
)
REQUIRED_ARTICLE_KEYS = {
    "date",
    "title",
    "title_candidates",
    "digest",
    "sections",
    "source_report",
    "sources",
    "risk_flags",
    "style_references",
    "external_reference_accounts",
    "source_attribution_note",
    "image_assets",
    "auto_publish_eligible",
}
REQUIRED_SECTION_TYPES = {"intro", "frontier", "gold_rush", "references"}
PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
)


class TestFailure(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise TestFailure(message)


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TestFailure(f"Invalid JSON in {path}: {exc}") from exc


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(data, ensure_ascii=False, sort_keys=True) + "\n")


def proxy_env_snapshot() -> dict[str, str]:
    return {key: os.environ[key] for key in PROXY_ENV_KEYS if os.environ.get(key)}


def build_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    for key, value in proxy_env_snapshot().items():
        env[key] = value
    return env


def print_proxy_status() -> None:
    snapshot = proxy_env_snapshot()
    if not snapshot:
        print("Proxy env inherited by Hermes: none")
        return
    print("Proxy env inherited by Hermes:")
    for key in sorted(snapshot):
        print(f"- {key}={snapshot[key]}")


def latest_report_label() -> str:
    candidates = []
    for child in REPORTS_DIR.iterdir() if REPORTS_DIR.is_dir() else []:
        if not child.is_dir():
            continue
        if all((child / name).is_file() for name in REQUIRED_REPORT_FILES):
            candidates.append(child)
    require(bool(candidates), f"No valid report directories found under {REPORTS_DIR}")
    return max(candidates, key=lambda path: path.stat().st_mtime).name


def safe_label(value: str) -> str:
    require(value and "/" not in value and ".." not in value, f"Unsafe report label: {value!r}")
    return value


def validate_report_input(report_label: str) -> dict:
    report_dir = REPORTS_DIR / safe_label(report_label)
    require(report_dir.is_dir(), f"Report directory missing: {report_dir}")
    paths = {name: report_dir / name for name in REQUIRED_REPORT_FILES}
    for name, path in paths.items():
        require(path.is_file(), f"Missing report input file: {path}")
    brief = load_json(paths["brief.json"])
    sources = load_json(paths["sources.json"])
    require(isinstance(brief, dict), "brief.json must be an object")
    require(isinstance(sources, list), "sources.json must be an array")
    return {
        "report_dir": str(report_dir.relative_to(REPO_ROOT)),
        "technical_report": str(paths["technical-report.md"].relative_to(REPO_ROOT)),
        "sources_path": str(paths["sources.json"].relative_to(REPO_ROOT)),
        "brief_path": str(paths["brief.json"].relative_to(REPO_ROOT)),
        "brief": brief,
        "sources": sources,
    }


def backup_existing_output_dir(output_dir: Path, *, force: bool, run_id: str) -> Path | None:
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
        return None
    require(output_dir.is_dir(), f"Output path exists but is not a directory: {output_dir}")
    has_files = any(output_dir.iterdir())
    if not has_files:
        return None
    if not force:
        raise TestFailure(f"Output directory already exists and is not empty: {output_dir}. Use --force to overwrite.")
    backup_dir = ARTICLES_DIR / f".backup-{run_id}"
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    shutil.move(str(output_dir), str(backup_dir))
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Existing output backed up: {backup_dir}")
    return backup_dir


def restore_output_backup(output_dir: Path, backup_dir: Path | None) -> None:
    if backup_dir is None:
        return
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.move(str(backup_dir), str(output_dir))
    print(f"Restored previous output after failure: {output_dir}")


def discard_output_backup(backup_dir: Path | None) -> None:
    if backup_dir is not None and backup_dir.exists():
        shutil.rmtree(backup_dir)


def build_prompt(report_label: str, output_label: str, input_info: dict) -> str:
    today = dt.date.today().isoformat()
    return f"""
请使用 WeChatArticleAgent 基于已有技术报告生成微信公众号内容草稿和结构化数据。

今天日期：{today}

输入目录：reports/{report_label}/
已验证输入文件：
{json.dumps(input_info, ensure_ascii=False, indent=2)}

- input_report: reports/{report_label}/technical-report.md
- input_sources: reports/{report_label}/sources.json
- input_brief: reports/{report_label}/brief.json
- output_dir: articles/{output_label}/
- mode: draft_and_structured_data

你要实际读取 input_dir 里的文件，然后生成以下文件：

1. articles/{output_label}/wechat-draft.md
   - 公众号 Markdown 草稿。
   - 必须包含：# 标题、## 开场白、## AI 前沿、## 浪里淘金、## 今天值得想一想、## 结尾互动、## 参考与信息来源。
   - 风格不要像技术报告摘要。要更像一个懂技术的人在公众号里讲“这事为什么有意思”：有判断、有节奏、有具体例子，少用报告腔。
   - 专业论文不要堆太多，除非能转成生活、工作、产品体验、开发者工具或可尝试项目的具体场景。
   - 开头和结尾必须像正常公众号正文，禁止出现“这份技术报告 / 本文未 / 当前环境 / 结构化数据 / 生成流程 / style corpus unavailable”等内部说明或 AI 口吻。
   - 如果技术报告素材太专业，你要优先从 brief/sources 里提炼生活化角度、工具玩法和读者利益点，而不是照搬论文综述。
   - 用户提到的 `Kyro AI Tech`、`说说说来话长`、`数字生命卡兹克`、`逛逛 Github` 是待采样参考账号，不是可直接冒充已读样本的风格标签。
   - 只有在真实读取到这些公众号文章正文或用户提供导出样本后，才可以把它们写入 style_references；如果只搜到标题/摘要或遇到验证码/反爬，必须在 source_attribution_note 说明 style corpus unavailable。
   - 事实应来自技术报告、sources.json、brief.json；如果补充新素材，必须保留链接和不确定性说明。
   - 文末 `参考与信息来源` 必须列出本稿用到的 report/sources 链接；如果实际采用了上述公众号作为信息来源或选题线索，也必须注明账号名、文章名或可追溯链接。

2. articles/{output_label}/article.json
   - 结构化公众号文章数据，用于后续自动排版、配图和发布。
   - 必须是合法 JSON object。
   - 必须包含这些字段：date, title, title_candidates, digest, sections, source_report, sources, risk_flags, style_references, external_reference_accounts, source_attribution_note, auto_publish_eligible。
   - sections 必须是数组，每项包含 heading, type, content_md。
   - sections 至少包含 type=intro、frontier、gold_rush、references。
   - `参考与信息来源` 对应 section 的 type 必须是 `references`，不要写成 `sources`。
   - title_candidates 必须是数组。
   - sources 必须是数组。
   - risk_flags 必须是数组。
   - style_references 必须是数组；只记录真实读取过并实际用于文风参考的样本账号/文章。当前环境如果无法读取公众号正文，可以为空数组。
   - external_reference_accounts 必须是数组；如果本次没有实际使用这些公众号的信息来源，只写空数组，不要假装引用。
   - source_attribution_note 必须是字符串，说明文末 `参考与信息来源` 如何注明来源。
   - image_assets 必须是数组，且不少于 5 张本地图片；但不能用 5 张手写 SVG/暗色模板图糊弄。
   - 图片结构硬要求：source-derived images 至少 3 张，优先来自 source URL 的官方图、网页截图、论文图、GitHub/产品截图或 og:image；每张必须有非空 source_url。
   - AI 生成图至少 1 张，必须是真正调用 Hermes `image_generate` 工具得到的 PNG/JPG/WEBP 位图；`tool` 字段必须严格等于 `image_generate`，必须有非空 generation_prompt、model、provider，不允许用 agent 手写 SVG、Pillow fallback、compatible bitmap 或本地渲染冒充。
   - cover-like 图片最多 1 张；禁止 generated SVG placeholder。
   - 至少 1 张 AI 图应是知识讲解漫画/原创吉祥物解释图，而不是泛化 dark tech cover。可借鉴“机器猫、黑白鼠”式讲解效果，但不得直接使用受版权保护角色；使用原创猫型/鼠型/机器人讲解员。
   - 你必须实际生成、抓取或准备这些图片文件，保存到 articles/{output_label}/images/，并在 image_assets 中记录 local_path、markdown_ref、caption、kind、status、generation_prompt/source_url/model/provider/tool 等字段。
   - Markdown 正文必须引用这些图片，使用 `./images/...` 相对路径。
   - auto_publish_eligible 现在必须是 false；本阶段只做草稿和结构化数据，不自动发布。

3. articles/{output_label}/metadata.json
   - 运行和交接元数据，必须是合法 JSON object。
   - 至少包含：date, source_report, output_draft, output_article_json, auto_publish=false, generator_profile={PROFILE_NAME}。

不要生成 review-notes.md 作为核心输出；如果你认为有风险，请写入 article.json 的 risk_flags。
完成后只简短说明写入了哪些文件，不要把全文复制到终端。
""".strip()


def build_command(report_label: str, output_label: str, input_info: dict) -> list[str]:
    return [
        "hermes",
        "-p",
        PROFILE_NAME,
        "-s",
        WECHAT_SKILL,
        "-s",
        PIPELINE_SKILL,
        "chat",
        "-q",
        build_prompt(report_label, output_label, input_info),
    ]


def quote_command(command: Iterable[str]) -> str:
    import shlex

    return " ".join(shlex.quote(part) for part in command)


TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def write_mock_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(TINY_PNG)


def build_mock_paragraphs() -> str:
    return "\n\n".join(
        [
            "这次我没有把它当成一条新闻看，而是当成一次内容团队工作流的排练：一个 Agent 先整理素材，一个 Agent 把它讲给普通读者听，最后再由 QA 检查有没有漏文件、漏图片和漏来源。",
            "这里最有意思的不是 mock source 本身，而是这条链路终于有了可验证的交接物。只要 report、article、image-assets、preview 和 QA report 都能稳定出现，后面才谈得上定时运行和微信草稿。",
            "对创作者来说，这像是把每天最麻烦的几件事拆开：有人找资料，有人写稿，有人配图，有人检查。每一步都留下文件，而不是把全部结果藏在一次聊天里。",
            "当然，这还是工程烟测，不是正式报道。里面的 OpenAI agent SDK、具身智能 benchmark 和开发者工具 release 都是 mock 线索，用来确认结构，不用来证明真实行业变化。",
            "我更关心的是这种流程能不能让内容团队少一点玄学。过去一篇文章写完以后，问题常常藏在最后：来源有没有漏、图片是不是本地文件、公众号后台能不能保存、有没有把内部说明写进正文。现在这些问题可以被拆成一个个检查项。",
            "如果明天要接真实日报，这条 smoke 链路的价值就很直接：只要把 mock source 换成真实来源，把占位图换成真实截图和真正的 image_generate 图片，后面的 final article、HTML preview、QA report 和 product cards 都不用重新设计。",
        ]
    )


def write_mock_smoke_outputs(report_label: str, output_label: str, input_info: dict) -> None:
    output_dir = ARTICLES_DIR / output_label
    images_dir = output_dir / IMAGES_DIRNAME
    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)
    image_assets = []
    source_urls = [source.get("url", "https://example.com/mock/source") for source in input_info.get("sources", [])]
    for index in range(3):
        filename = f"source-{index + 1}.png"
        local_path = f"articles/{output_label}/{IMAGES_DIRNAME}/{filename}"
        write_mock_image(REPO_ROOT / local_path)
        image_assets.append(
            {
                "id": f"source-{index + 1}",
                "purpose": "section_illustration",
                "kind": "source_image",
                "local_path": local_path,
                "markdown_ref": f"![mock source image {index + 1}](./{IMAGES_DIRNAME}/{filename})",
                "caption": f"工程烟测 source-derived 图片 {index + 1}",
                "source_url": source_urls[index % len(source_urls)] if source_urls else "https://example.com/mock/source",
                "source_title": f"Smoke source {index + 1}",
                "license_or_usage_note": "mock smoke placeholder, not a real source visual",
                "status": "saved",
                "notes": "工程烟测占位图片，只验证本地图片链路。",
            }
        )
    ai_filename = "ai-explainer.png"
    ai_local_path = f"articles/{output_label}/{IMAGES_DIRNAME}/{ai_filename}"
    write_mock_image(REPO_ROOT / ai_local_path)
    image_assets.append(
        {
            "id": "ai-explainer",
            "purpose": "section_illustration",
            "kind": "generated",
            "local_path": ai_local_path,
            "markdown_ref": f"![mock AI explainer](./{IMAGES_DIRNAME}/{ai_filename})",
            "caption": "工程烟测 AI 讲解图占位",
            "generation_prompt": "Mock smoke test image_generate placeholder for ClawMax workflow explainer.",
            "tool": "image_generate",
            "provider": "mock-smoke-provider",
            "model": "mock-smoke-image-model",
            "status": "saved",
            "notes": "工程烟测占位图片，用于验证 image_generate metadata contract。",
        }
    )
    extra_filename = "workflow-card.png"
    extra_local_path = f"articles/{output_label}/{IMAGES_DIRNAME}/{extra_filename}"
    write_mock_image(REPO_ROOT / extra_local_path)
    image_assets.append(
        {
            "id": "workflow-card",
            "purpose": "diagram",
            "kind": "supporting_image",
            "local_path": extra_local_path,
            "markdown_ref": f"![mock workflow card](./{IMAGES_DIRNAME}/{extra_filename})",
            "caption": "工程烟测工作流卡片占位",
            "status": "saved",
            "notes": "工程烟测占位图片。",
        }
    )
    paragraphs = build_mock_paragraphs()
    draft = f"""# 我给 AI 内容团队跑了一次端到端烟测

## 开场白

{image_assets[0]['markdown_ref']}

{paragraphs}

## AI 前沿

{image_assets[1]['markdown_ref']}

Agent 工作流真正值得看的地方，不是它能不能一次写出一篇漂亮文章，而是它能不能把输入、输出和检查点拆清楚。今天这次 smoke 用 mock source 模拟了三类素材：agent 能力、具身智能 benchmark、开发者工具 release。它们不是真新闻，但很适合验证报告到文章的交接。

如果这套链路稳定，正式日报就可以把真实来源放进同样的位置：source 进 `sources.json`，公共读者角度进 `brief.json`，公众号正文再负责把复杂信息讲得像人话。

## 浪里淘金

{image_assets[2]['markdown_ref']}

这次真正值得淘的不是外部工具，而是 ClawMax 这个项目本身。它已经有三个清楚的角色：技术报告、公众号文章、产品机会卡。每个角色都不需要一次做太多，只要把自己的文件交出来，并且接受下一步检查。

{image_assets[3]['markdown_ref']}

对小团队来说，这种设计比“一个万能 Agent 解决一切”更可靠。你可以先看报告，再看文章预览，再看 QA 报告，最后看产品机会卡。哪一步坏了，就修哪一步。

## 今天值得想一想

{image_assets[4]['markdown_ref']}

如果一条内容流水线不能被验证，它就很难变成产品。今天这个 smoke 的意义是：报告、文章、图片、预览、QA、产品机会卡这些产物都能落到本地目录里，后续才有资格讨论定时运行、微信草稿回读和自动发布。

## 结尾互动

如果你也在做 AI 内容团队，最应该先自动化的可能不是写作本身，而是把每一步的输入输出固定下来。你会先自动化找资料、写稿、配图，还是 QA？

## 参考与信息来源

- reports/{report_label}/technical-report.md
- https://example.com/mock/openai-agent-sdk-smoke
- https://example.com/mock/embodied-ai-benchmark-smoke
- https://example.com/mock/developer-tool-release-smoke
"""
    sections = [
        {"heading": "开场白", "type": "intro", "content_md": paragraphs},
        {"heading": "AI 前沿", "type": "frontier", "content_md": "Agent 工作流的重点是可验证交接，而不是一次性生成。"},
        {"heading": "浪里淘金", "type": "gold_rush", "content_md": "ClawMax 本身是这次 smoke 中的真实项目机会。"},
        {"heading": "今天值得想一想", "type": "reflection", "content_md": "先固定输入输出，再谈自动化。"},
        {"heading": "结尾互动", "type": "closing", "content_md": "你会先自动化找资料、写稿、配图，还是 QA？"},
        {"heading": "参考与信息来源", "type": "references", "content_md": "- reports/{}/technical-report.md\n- https://example.com/mock/openai-agent-sdk-smoke\n- https://example.com/mock/embodied-ai-benchmark-smoke\n- https://example.com/mock/developer-tool-release-smoke".format(report_label)},
    ]
    (output_dir / "wechat-draft.md").write_text(draft, encoding="utf-8")
    article = {
        "date": dt.date.today().isoformat(),
        "title": "我给 AI 内容团队跑了一次端到端烟测",
        "title_candidates": ["我给 AI 内容团队跑了一次端到端烟测", "内容 Agent 靠不靠谱，先看它能不能通过 QA"],
        "digest": "一次明确标记为 mock 的 ClawMax 端到端验证：报告、文章、图片、QA 和产品机会卡全部落地。",
        "sections": sections,
        "source_report": f"reports/{report_label}/technical-report.md",
        "sources": input_info.get("sources", []),
        "risk_flags": ["工程烟测内容，不代表正式 AI 技术日报。", "图片为 mock placeholder，仅验证文件链路。"],
        "style_references": [],
        "external_reference_accounts": [],
        "source_attribution_note": "本次为工程烟测，参考与信息来源只列 mock report 和 mock source URL。",
        "image_assets": image_assets,
        "auto_publish_eligible": False,
    }
    metadata = {
        "date": dt.date.today().isoformat(),
        "source_report": f"reports/{report_label}/technical-report.md",
        "output_draft": f"articles/{output_label}/wechat-draft.md",
        "output_article_json": f"articles/{output_label}/article.json",
        "output_final_article": f"articles/{output_label}/final-wechat-article.md",
        "output_html_preview": f"articles/{output_label}/wechat-preview.html",
        "output_image_assets": f"articles/{output_label}/image-assets.json",
        "output_images_dir": f"articles/{output_label}/images",
        "generated_files": [
            f"articles/{output_label}/wechat-draft.md",
            f"articles/{output_label}/article.json",
            f"articles/{output_label}/metadata.json",
            *[asset["local_path"] for asset in image_assets],
        ],
        "auto_publish": False,
        "generator_profile": PROFILE_NAME,
        "mode": "mock_smoke",
    }
    write_json(output_dir / "article.json", article)
    write_json(output_dir / "metadata.json", metadata)


def run_hermes(command: list[str], *, timeout_seconds: int) -> int:
    process = subprocess.Popen(
        command,
        cwd=REPO_ROOT,
        env=build_subprocess_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )
    assert process.stdout is not None
    try:
        for line in process.stdout:
            print(line, end="")
        return process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        raise


def validate_public_body_text(text: str, *, label: str) -> None:
    for phrase in FORBIDDEN_PUBLIC_BODY_PHRASES:
        require(phrase not in text, f"{label} contains forbidden internal/AI-process phrase: {phrase}")


def validate_draft(path: Path) -> str:
    require(path.is_file(), f"Missing file: {path}")
    text = read_text(path)
    require(len(text.strip()) >= 1200, "wechat-draft.md is too short to be a useful article draft")
    for marker in REQUIRED_DRAFT_MARKERS:
        require(marker in text, f"wechat-draft.md missing required marker: {marker}")
    require("http://" in text or "https://" in text, "wechat-draft.md should preserve at least one source/project link")
    require(f"./{IMAGES_DIRNAME}/" in text, "wechat-draft.md must include local image references")
    validate_public_body_text(text, label="wechat-draft.md")
    return text


def validate_article_json(path: Path) -> dict:
    require(path.is_file(), f"Missing file: {path}")
    data = load_json(path)
    require(isinstance(data, dict), "article.json must be an object")
    for key in sorted(REQUIRED_ARTICLE_KEYS):
        require(key in data, f"article.json missing key: {key}")
    require(isinstance(data["title"], str) and data["title"].strip(), "article.json title must be a non-empty string")
    require(isinstance(data["title_candidates"], list), "article.json title_candidates must be an array")
    require(isinstance(data["digest"], str) and data["digest"].strip(), "article.json digest must be a non-empty string")
    require(isinstance(data["sections"], list) and data["sections"], "article.json sections must be a non-empty array")
    require(isinstance(data["sources"], list), "article.json sources must be an array")
    require(isinstance(data["risk_flags"], list), "article.json risk_flags must be an array")
    require(isinstance(data["style_references"], list), "article.json style_references must be an array")
    require(isinstance(data["external_reference_accounts"], list), "article.json external_reference_accounts must be an array")
    require(isinstance(data["source_attribution_note"], str) and data["source_attribution_note"].strip(), "article.json source_attribution_note must be a non-empty string")
    require(isinstance(data["image_assets"], list), "article.json image_assets must be an array")
    require(data["auto_publish_eligible"] is False, "article.json auto_publish_eligible must be false in this stage")
    section_types = set()
    for index, section in enumerate(data["sections"]):
        require(isinstance(section, dict), f"article.json sections[{index}] must be an object")
        for key in ("heading", "type", "content_md"):
            require(key in section, f"article.json sections[{index}] missing key: {key}")
        require(str(section["content_md"]).strip(), f"article.json sections[{index}].content_md must not be empty")
        section_types.add(str(section["type"]))
    missing_types = REQUIRED_SECTION_TYPES - section_types
    require(not missing_types, f"article.json missing section types: {sorted(missing_types)}")
    return data


def validate_metadata(path: Path, *, report_label: str, output_label: str) -> dict:
    require(path.is_file(), f"Missing file: {path}")
    data = load_json(path)
    require(isinstance(data, dict), "metadata.json must be an object")
    for key in ("date", "source_report", "output_draft", "output_article_json", "output_final_article", "output_html_preview", "output_image_assets", "auto_publish", "generator_profile"):
        require(key in data, f"metadata.json missing key: {key}")
    require(data["auto_publish"] is False, "metadata.json auto_publish must be false in this stage")
    require(data["generator_profile"] == PROFILE_NAME, f"metadata.json generator_profile must be {PROFILE_NAME}")
    require(str(data["source_report"]).endswith(f"reports/{report_label}/technical-report.md"), "metadata.json source_report should point to the input report")
    require(str(data["output_draft"]).endswith(f"articles/{output_label}/wechat-draft.md"), "metadata.json output_draft should point to wechat-draft.md")
    require(str(data["output_article_json"]).endswith(f"articles/{output_label}/article.json"), "metadata.json output_article_json should point to article.json")
    require(str(data["output_final_article"]).endswith(f"articles/{output_label}/final-wechat-article.md"), "metadata.json output_final_article should point to final-wechat-article.md")
    require(str(data["output_html_preview"]).endswith(f"articles/{output_label}/wechat-preview.html"), "metadata.json output_html_preview should point to wechat-preview.html")
    require(str(data["output_image_assets"]).endswith(f"articles/{output_label}/image-assets.json"), "metadata.json output_image_assets should point to image-assets.json")
    generated_files = data.get("generated_files")
    require(isinstance(generated_files, list), "metadata.json generated_files must be an array")
    require(f"articles/{output_label}/wechat-preview.html" in generated_files, "metadata.json generated_files must include wechat-preview.html")
    return data


def validate_final_article(path: Path) -> str:
    require(path.is_file(), f"Missing file: {path}")
    text = read_text(path)
    require(len(text.strip()) >= 1200, "final-wechat-article.md is too short to be a useful final article")
    for marker in REQUIRED_DRAFT_MARKERS:
        require(marker in text, f"final-wechat-article.md missing required marker: {marker}")
    require("http://" in text or "https://" in text, "final-wechat-article.md should preserve at least one source/project link")
    require(f"./{IMAGES_DIRNAME}/" in text, "final-wechat-article.md must include local image references")
    validate_public_body_text(text, label="final-wechat-article.md")
    return text


def validate_html_preview(path: Path) -> str:
    require(path.is_file(), f"Missing file: {path}")
    text = read_text(path)
    require("<article" in text, "wechat-preview.html should contain an article element")
    require("wechat-preview" in text, "wechat-preview.html should include preview-specific styling or class names")
    require("AI 前沿" in text and "浪里淘金" in text, "wechat-preview.html should preserve required article sections")
    require("http://" in text or "https://" in text, "wechat-preview.html should preserve at least one source/project link")
    require(f"./{IMAGES_DIRNAME}/" in text, "wechat-preview.html must include local image references")
    validate_public_body_text(text, label="wechat-preview.html")
    return text


def validate_image_assets(path: Path, *, output_label: str) -> list:
    require(path.is_file(), f"Missing file: {path}")
    data = load_json(path)
    require(isinstance(data, list), "image-assets.json must be an array")
    require(len(data) >= MIN_ARTICLE_IMAGES, f"image-assets.json must contain at least {MIN_ARTICLE_IMAGES} images")
    images_dir = path.parent / IMAGES_DIRNAME
    require(images_dir.is_dir(), f"Missing images directory: {images_dir}")
    ai_bitmap_count = 0
    source_derived_count = 0
    generated_svg_count = 0
    cover_count = 0
    saved_count = 0
    for index, asset in enumerate(data):
        require(isinstance(asset, dict), f"image-assets.json[{index}] must be an object")
        local_path = str(asset.get("local_path") or "")
        status = str(asset.get("status") or "")
        kind = str(asset.get("kind") or asset.get("source_type") or asset.get("origin") or "").lower()
        prompt = str(asset.get("generation_prompt") or asset.get("prompt") or "").strip()
        source_url = str(asset.get("source_url") or asset.get("url") or "").strip()
        tool = str(asset.get("tool") or "").strip()
        model = str(asset.get("model") or "").strip()
        provider = str(asset.get("provider") or "").strip()
        model_blob = " ".join(str(asset.get(key) or "") for key in ("model", "provider", "tool", "notes")).lower()
        suffix = Path(local_path).suffix.lower()
        serialized_asset = json.dumps(asset, ensure_ascii=False).lower()
        is_generated = "generated" in kind or bool(prompt) or "gpt-image" in model_blob or "image_generate" in model_blob
        is_source_derived = bool(source_url) and (kind in SOURCE_DERIVED_IMAGE_KINDS or any(token in kind for token in ("source", "official", "screenshot", "figure", "og_image")))
        is_ai_bitmap = (
            is_generated
            and suffix in BITMAP_IMAGE_SUFFIXES
            and bool(prompt)
            and bool(model)
            and bool(provider)
            and tool == "image_generate"
            and not any(marker in serialized_asset for marker in ["fallback", "compatible", "pillow", "local bitmap rendering"])
        )
        if str(asset.get("purpose") or "").lower() == "cover":
            cover_count += 1
        if is_generated and suffix == ".svg":
            generated_svg_count += 1
        if is_source_derived:
            source_derived_count += 1
        if is_ai_bitmap:
            ai_bitmap_count += 1
        if status == "saved":
            saved_count += 1
            require(local_path.startswith(f"articles/{output_label}/{IMAGES_DIRNAME}/"), f"image-assets.json[{index}].local_path must point inside article images dir")
            require((REPO_ROOT / local_path).is_file(), f"image-assets.json[{index}] file missing: {local_path}")
            markdown_ref = str(asset.get("markdown_ref") or "")
            require(markdown_ref.startswith("![") and f"./{IMAGES_DIRNAME}/" in markdown_ref, f"image-assets.json[{index}].markdown_ref must use relative images path")
    require(saved_count >= MIN_ARTICLE_IMAGES, f"article bundle must include at least {MIN_ARTICLE_IMAGES} saved images")
    require(source_derived_count >= MIN_SOURCE_DERIVED_IMAGES, f"article bundle must include at least {MIN_SOURCE_DERIVED_IMAGES} source-derived images with source_url")
    require(ai_bitmap_count >= MIN_AI_GENERATED_IMAGES, f"article bundle must include at least {MIN_AI_GENERATED_IMAGES} real AI-generated bitmap image with tool exactly image_generate; fallback/compatible/Pillow output is not accepted")
    require(generated_svg_count <= MAX_GENERATED_SVG_IMAGES, "generated SVG placeholder images are not allowed")
    require(cover_count <= MAX_COVER_IMAGES, f"article bundle must include at most {MAX_COVER_IMAGES} cover-like image")
    return data


def validate_outputs(output_label: str, *, report_label: str) -> dict:
    output_dir = ARTICLES_DIR / safe_label(output_label)
    draft_path = output_dir / "wechat-draft.md"
    article_json_path = output_dir / "article.json"
    metadata_path = output_dir / "metadata.json"
    final_article_path = output_dir / FINAL_ARTICLE_FILENAME
    html_preview_path = output_dir / HTML_PREVIEW_FILENAME
    image_assets_path = output_dir / IMAGE_ASSETS_FILENAME
    require(output_dir.is_dir(), f"Output directory missing: {output_dir}")
    draft_text = validate_draft(draft_path)
    article = validate_article_json(article_json_path)
    metadata = validate_metadata(metadata_path, report_label=report_label, output_label=output_label)
    final_text = validate_final_article(final_article_path)
    html_text = validate_html_preview(html_preview_path)
    image_assets = validate_image_assets(image_assets_path, output_label=output_label)
    require(article.get("image_assets") == image_assets, "article.json image_assets must match image-assets.json")
    qa_report = qa_article_bundle(output_label, repo_root=REPO_ROOT)
    require(
        qa_report.get("status") != "failed",
        "Article bundle QA failed. See "
        f"{qa_report.get('output_qa_report') or output_dir / 'qa-report.json'} and "
        f"{qa_report.get('output_review_notes') or output_dir / 'review-notes.md'}",
    )
    return {
        "output_dir": str(output_dir.relative_to(REPO_ROOT)),
        "draft_path": str(draft_path.relative_to(REPO_ROOT)),
        "article_json_path": str(article_json_path.relative_to(REPO_ROOT)),
        "metadata_path": str(metadata_path.relative_to(REPO_ROOT)),
        "final_article_path": str(final_article_path.relative_to(REPO_ROOT)),
        "html_preview_path": str(html_preview_path.relative_to(REPO_ROOT)),
        "image_assets_path": str(image_assets_path.relative_to(REPO_ROOT)),
        "images_dir": str((output_dir / IMAGES_DIRNAME).relative_to(REPO_ROOT)),
        "draft_chars": len(draft_text),
        "final_article_chars": len(final_text),
        "html_preview_chars": len(html_text),
        "image_asset_count": len(image_assets),
        "saved_image_count": sum(1 for asset in image_assets if isinstance(asset, dict) and asset.get("status") == "saved"),
        "section_count": len(article.get("sections") or []),
        "title_candidate_count": len(article.get("title_candidates") or []),
        "risk_flag_count": len(article.get("risk_flags") or []),
        "qa": {
            "status": qa_report.get("status"),
            "summary": qa_report.get("summary", {}),
            "issue_count": len(qa_report.get("issues") or []),
        },
        "qa_report_path": qa_report.get("output_qa_report") or str((output_dir / "qa-report.json").relative_to(REPO_ROOT)),
        "review_notes_path": qa_report.get("output_review_notes") or str((output_dir / "review-notes.md").relative_to(REPO_ROOT)),
        "metadata": metadata,
    }


def write_run_log(run_id: str, event: dict) -> None:
    append_jsonl(RUNS_DIR / "wechat-article-runs.jsonl", {"run_id": run_id, **event})
    write_json(RUNS_DIR / f"{run_id}.json", {"run_id": run_id, **event})


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Hermes WeChatArticleAgent and validate generated article draft + structured data.")
    parser.add_argument("--report-label", default=None, help="Input report directory name under reports/. Default: latest valid report directory.")
    parser.add_argument("--output-label", default=None, help="Output article directory name under articles/. Default: same as report label.")
    parser.add_argument("--force", action="store_true", help="Delete existing non-empty output directory before running.")
    parser.add_argument("--dry-run", action="store_true", help="Print the Hermes command without executing it.")
    parser.add_argument("--timeout", type=int, default=900, help="Hermes run timeout in seconds. Default: 900.")
    parser.add_argument("--mock-smoke", action="store_true", help="Write deterministic mock article outputs, then run finalization and QA without launching Hermes.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    report_label = safe_label(args.report_label or latest_report_label())
    output_label = safe_label(args.output_label or report_label)
    run_id = f"{output_label}-wechat"
    started_at = now_iso()
    start_time = dt.datetime.now(dt.timezone.utc)

    input_info = validate_report_input(report_label)
    # Supervision gate: try to prepare source-derived visual assets before the article agent runs.
    # The finalizer still enforces the hard contract; this step gives the agent real source images
    # so it cannot satisfy the 5-image quota with generated placeholders.
    collector = REPO_ROOT / "scripts" / "collect_source_images.py"
    report_manifest = REPORTS_DIR / report_label / IMAGE_ASSETS_FILENAME
    if collector.is_file() and not report_manifest.is_file():
        print("Collecting source-derived images before running WeChatArticleAgent...")
        subprocess.run([sys.executable, str(collector), "--report-label", report_label, "--max-images", "8"], cwd=REPO_ROOT, env=build_subprocess_env(), check=False)
    output_dir = ARTICLES_DIR / output_label
    command = build_command(report_label, output_label, input_info)

    print(f"Repo root: {REPO_ROOT}")
    print(f"Profile: {PROFILE_NAME}")
    print(f"Input report: {input_info['report_dir']}")
    print(f"Output dir: {output_dir}")
    print_proxy_status()

    if args.dry_run:
        print("\nDry run command:\n")
        print(quote_command(command))
        return 0

    backup_dir = backup_existing_output_dir(output_dir, force=args.force, run_id=run_id)

    print("\nRunning Hermes WeChatArticleAgent integration test...\n")
    try:
        if args.mock_smoke:
            print("Writing deterministic WeChatArticleAgent mock-smoke outputs...\n")
            write_mock_smoke_outputs(report_label, output_label, input_info)
        else:
            exit_code = run_hermes(command, timeout_seconds=args.timeout)
            require(exit_code == 0, f"Hermes command failed with exit code {exit_code}")

        print("\nFinalizing article bundle...\n")
        finalize_wechat_article_bundle(
            repo_root=REPO_ROOT,
            report_label=report_label,
            output_label=output_label,
            generator_profile=PROFILE_NAME,
        )

        print("\nValidating generated article files...\n")
        validation = validate_outputs(output_label, report_label=report_label)
    except Exception:
        restore_output_backup(output_dir, backup_dir)
        raise
    else:
        discard_output_backup(backup_dir)
    finished_at = now_iso()
    duration_seconds = round((dt.datetime.now(dt.timezone.utc) - start_time).total_seconds(), 3)
    write_run_log(
        run_id,
        {
            "status": "completed",
            "mode": "mock_smoke" if args.mock_smoke else "draft_and_structured_data",
            "profile": PROFILE_NAME,
            "skills": [WECHAT_SKILL, PIPELINE_SKILL],
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_seconds": duration_seconds,
            "input_report_label": report_label,
            "output_label": output_label,
            "input_dir": input_info["report_dir"],
            "output_dir": validation["output_dir"],
            "outputs": {
                "draft": validation["draft_path"],
                "article_json": validation["article_json_path"],
                "metadata": validation["metadata_path"],
                "final_article": validation["final_article_path"],
                "html_preview": validation["html_preview_path"],
                "image_assets": validation["image_assets_path"],
                "images_dir": validation["images_dir"],
                "qa_report": validation["qa_report_path"],
                "review_notes": validation["review_notes_path"],
            },
            "metrics": {
                "draft_chars": validation["draft_chars"],
                "final_article_chars": validation["final_article_chars"],
                "html_preview_chars": validation["html_preview_chars"],
                "section_count": validation["section_count"],
                "title_candidate_count": validation["title_candidate_count"],
                "risk_flag_count": validation["risk_flag_count"],
                "image_asset_count": validation["image_asset_count"],
                "saved_image_count": validation["saved_image_count"],
            },
            "qa": validation["qa"],
            "auto_publish": False,
            "proxy_env_keys": sorted(proxy_env_snapshot().keys()),
        },
    )

    print("PASS: WeChatArticleAgent generated a valid final article bundle.")
    print(f"Article bundle: {output_dir}")
    print(f"Final article: {output_dir / FINAL_ARTICLE_FILENAME}")
    print(f"HTML preview: {output_dir / HTML_PREVIEW_FILENAME}")
    print(f"Image assets: {output_dir / IMAGE_ASSETS_FILENAME}")
    print(f"QA status: {validation['qa']['status']}")
    print(f"QA report: {REPO_ROOT / validation['qa_report_path']}")
    print(f"Review notes: {REPO_ROOT / validation['review_notes_path']}")
    print(f"Run log: {RUNS_DIR / (run_id + '.json')}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except TestFailure as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except subprocess.TimeoutExpired as exc:
        print(f"FAIL: command timed out after {exc.timeout} seconds", file=sys.stderr)
        raise SystemExit(1)
