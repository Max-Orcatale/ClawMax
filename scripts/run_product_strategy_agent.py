#!/usr/bin/env python3
"""Generate lightweight product opportunity cards from a ClawMax report/article bundle.

This is the first deterministic ProductStrategyAgent runner. It intentionally
keeps scope small: read the existing technical report and optional WeChat article
bundle, then write a small set of opportunity cards. ClawMax is included as the
real product; other starter opportunities are explicitly marked hypothetical.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = REPO_ROOT / "reports"
ARTICLES_DIR = REPO_ROOT / "articles"
PRODUCTS_DIR = REPO_ROOT / "products"
RUNS_DIR = REPO_ROOT / "runs"

REQUIRED_REPORT_FILES = ("technical-report.md", "sources.json", "brief.json")
OUTPUT_CARDS_FILENAME = "opportunity-cards.md"
OUTPUT_JSON_FILENAME = "opportunities.json"
OUTPUT_METADATA_FILENAME = "metadata.json"
PROFILE_NAME = "productstrategyagent"
STRATEGY_SKILL = "clawmax:product-opportunity-analysis"
PIPELINE_SKILL = "clawmax:daily-ai-media-pipeline"


class ProductStrategyError(RuntimeError):
    pass


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProductStrategyError(message)


def safe_label(value: str) -> str:
    require(bool(value) and "/" not in value and ".." not in value, f"Unsafe label: {value!r}")
    return value


def read_text_if_exists(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def load_json_if_exists(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProductStrategyError(f"Invalid JSON in {path}: {exc}") from exc


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(data, ensure_ascii=False, sort_keys=True) + "\n")


def latest_report_label() -> str:
    candidates = []
    for child in REPORTS_DIR.iterdir() if REPORTS_DIR.is_dir() else []:
        if child.is_dir() and all((child / name).is_file() for name in REQUIRED_REPORT_FILES):
            candidates.append(child)
    require(bool(candidates), f"No valid report directories found under {REPORTS_DIR}")
    return max(candidates, key=lambda path: path.stat().st_mtime).name


def collect_inputs(label: str, article_label: str | None = None) -> dict[str, Any]:
    label = safe_label(label)
    article_label = safe_label(article_label or label)
    report_dir = REPORTS_DIR / label
    require(report_dir.is_dir(), f"Missing report input directory: {report_dir}")
    require((report_dir / "technical-report.md").is_file(), f"Missing report input file: {report_dir / 'technical-report.md'}")

    article_dir = ARTICLES_DIR / article_label
    return {
        "label": label,
        "article_label": article_label,
        "report_dir": report_dir,
        "article_dir": article_dir,
        "technical_report": read_text_if_exists(report_dir / "technical-report.md"),
        "brief": load_json_if_exists(report_dir / "brief.json", {}),
        "sources": load_json_if_exists(report_dir / "sources.json", []),
        "final_article": read_text_if_exists(article_dir / "final-wechat-article.md"),
        "article": load_json_if_exists(article_dir / "article.json", {}),
    }


def infer_themes(inputs: dict[str, Any]) -> list[str]:
    text = "\n".join(
        [
            inputs.get("technical_report") or "",
            json.dumps(inputs.get("brief") or {}, ensure_ascii=False),
            inputs.get("final_article") or "",
            json.dumps(inputs.get("article") or {}, ensure_ascii=False),
        ]
    ).lower()
    theme_checks = [
        ("agent", "Agent 工作流"),
        ("workflow", "工作流自动化"),
        ("qa", "自动 QA"),
        ("github", "开发者工具"),
        ("content", "内容生产"),
        ("wechat", "公众号运营"),
        ("image", "图像与视觉素材"),
        ("benchmark", "评测与数据反馈"),
    ]
    themes = [label for token, label in theme_checks if token in text]
    return themes or ["AI 内容自动化", "Agent 工作流", "开发者工具"]


def source_count(inputs: dict[str, Any]) -> int:
    sources = inputs.get("sources")
    return len(sources) if isinstance(sources, list) else 0


def make_opportunity(
    *,
    name: str,
    reality: str,
    summary: str,
    target_user: str,
    scenario: str,
    mvp_scope: list[str],
    difficulty: str,
    risk: str,
    next_experiment: str,
    user_persona: str,
    conversion_signal: str,
    reading_data_feedback: str,
    title_ab_test: list[str],
    promotion_strategy: str,
    commercial_opportunity: str,
    content_matrix_role: str,
    evidence: list[str],
) -> dict[str, Any]:
    return {
        "name": name,
        "reality": reality,
        "summary": summary,
        "target_user": target_user,
        "user_persona": user_persona,
        "core_scenario": scenario,
        "mvp_scope": mvp_scope,
        "implementation_difficulty": difficulty,
        "risk": risk,
        "next_experiment": next_experiment,
        "conversion_signal": conversion_signal,
        "reading_data_feedback": reading_data_feedback,
        "title_ab_test": title_ab_test,
        "promotion_strategy": promotion_strategy,
        "commercial_opportunity": commercial_opportunity,
        "content_matrix_role": content_matrix_role,
        "evidence": evidence,
    }


def build_opportunities(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    label = inputs["label"]
    article_label = inputs.get("article_label") or label
    themes = infer_themes(inputs)
    count = source_count(inputs)
    report_evidence = [
        f"reports/{label}/technical-report.md",
        f"reports/{label}/brief.json",
        f"reports/{label}/sources.json ({count} sources)",
    ]
    if (ARTICLES_DIR / article_label / "article.json").is_file():
        report_evidence.append(f"articles/{article_label}/article.json")

    return [
        make_opportunity(
            name="ClawMax",
            reality="real",
            summary="面向 AI 新媒体团队的数字员工流水线，把真实来源日报、公众号文章包、图片、自动 QA 和微信草稿创建串成可审计流程。",
            target_user="小型 AI 内容团队、独立创作者、技术媒体编辑、需要持续跟踪 AI 趋势的创业团队。",
            user_persona="懂技术但缺少稳定编辑/研究助理的人，核心痛点是每天找资料、写稿、配图、质检太耗时间。",
            scenario="每天早上自动生成技术报告，随后转成公众号草稿，经过 QA 后进入人工审阅或微信草稿。",
            mvp_scope=["日报生成", "公众号文章包", "本地图片包", "自动 QA", "微信草稿创建"],
            difficulty="medium",
            risk="真实来源质量、图片版权、公众号风格稳定性和微信 API 环境都会影响交付可靠性。",
            next_experiment="把 ProductStrategyAgent 输出接入每日流水线，连续 7 天观察机会卡是否能反哺选题和产品方向。",
            conversion_signal="读者或团队成员收藏文章、请求部署同款流水线、询问能否接自己的公众号/知识库。",
            reading_data_feedback="回收阅读完成率、收藏率、菜单点击和留言问题，用来判断哪类 AI 工作流选题最能转化为产品需求。",
            title_ab_test=["我给 AI 内容团队招了 3 个数字员工", "每天自动写 AI 日报和公众号，靠谱吗？"],
            promotion_strategy="先用公众号连载展示真实生产过程，再在 GitHub/技术社群发布可复用模板和案例。",
            commercial_opportunity="私有化部署、工作流模板包、技术媒体代运营工具、团队版订阅。",
            content_matrix_role="主产品和母案例，所有内容矩阵都可回到 ClawMax 的真实进展。",
            evidence=report_evidence + themes[:3],
        ),
        make_opportunity(
            name="SignalForge 选题雷达",
            reality="hypothetical",
            summary="把技术报告、GitHub 热度、公众号阅读反馈和来源质量记忆合成每日选题排序。",
            target_user="技术媒体编辑、AI 博主、产品市场团队。",
            user_persona="每天要选题但不想只追热点的人，需要知道哪个技术点既真实又有传播潜力。",
            scenario="输入当天来源池和历史文章表现，输出 5 个候选选题及转化假设。",
            mvp_scope=["选题候选列表", "来源可信度", "传播角度", "历史重复提醒"],
            difficulty="low-medium",
            risk="早期没有足够阅读数据时，排序容易变成主观打分。",
            next_experiment="用过去 10 篇文章手工补录阅读数据，比较模型排序和真实表现的相关性。",
            conversion_signal="用户愿意用它决定第二天标题或栏目顺序。",
            reading_data_feedback="记录打开率、读完率、收藏率、转发率和留言关键词，反向更新选题权重。",
            title_ab_test=["今天 AI 圈最值得写的 5 个题", "别只追热点，这些 AI 选题更可能被收藏"],
            promotion_strategy="用每周公开选题榜单吸引创作者试用。",
            commercial_opportunity="选题 SaaS、媒体团队席位、付费数据榜单。",
            content_matrix_role="内容矩阵的前端雷达，负责发现和排序。",
            evidence=themes[:4],
        ),
        make_opportunity(
            name="ReadLoop 阅读反馈器",
            reality="hypothetical",
            summary="把公众号阅读数据、留言和标题版本记录回流到 ClawMax，帮助下一次生成更贴近读者。",
            target_user="已经有稳定发布节奏的公众号运营者。",
            user_persona="想知道文章为什么有人读完、哪里掉队、哪些标题真的有效的内容负责人。",
            scenario="发布后导入阅读数据，生成选题、标题、结构和图片建议。",
            mvp_scope=["手工 CSV 导入", "文章表现摘要", "标题实验记录", "下一篇建议"],
            difficulty="medium",
            risk="微信后台数据获取方式和权限可能限制自动化程度。",
            next_experiment="先手工导入 5 篇文章数据，验证反馈建议是否能改善下一篇标题。",
            conversion_signal="用户根据反馈改标题或结构，并愿意连续导入数据。",
            reading_data_feedback="这是产品核心输入：阅读完成率、分享率、收藏率、留言主题和菜单点击。",
            title_ab_test=["同一篇 AI 文章，标题换一下差多少？", "公众号不是写完就结束，数据会告诉你下一篇怎么写"],
            promotion_strategy="用案例复盘文章展示标题和结构改动前后的差异。",
            commercial_opportunity="数据回流插件、运营复盘报告、内容增长顾问包。",
            content_matrix_role="内容矩阵的反馈层，让生产系统不只会写，还会学习。",
            evidence=["articles/<label>/article.json", "future wechat-publish.json", "manual reading data"],
        ),
        make_opportunity(
            name="MatrixBrief 内容矩阵规划器",
            reality="hypothetical",
            summary="把一份 AI 技术报告拆成公众号、短视频脚本、小红书卡片、GitHub 项目帖和产品机会卡。",
            target_user="希望一份研究素材多平台复用的小团队。",
            user_persona="有研究能力但缺少多平台分发经验的创作者，需要从一份报告快速拆出不同内容形态。",
            scenario="输入日报和文章包，输出不同平台的标题、角度、素材需求和发布优先级。",
            mvp_scope=["平台角度拆解", "标题候选", "素材清单", "发布时间建议"],
            difficulty="medium",
            risk="多平台规则差异大，过早自动化容易产出模板感内容。",
            next_experiment="只选择公众号 + GitHub 项目帖两个渠道做 2 周实验。",
            conversion_signal="同一主题在两个以上平台产生收藏、私信或点击。",
            reading_data_feedback="把不同平台的点击/收藏/评论回流到统一 topic record。",
            title_ab_test=["一份 AI 日报怎么拆成 5 条内容？", "别浪费研究素材，把它变成内容矩阵"],
            promotion_strategy="先作为 ClawMax 的内部扩展模块展示，再开放模板。",
            commercial_opportunity="多平台内容日历、矩阵模板、团队版内容操作台。",
            content_matrix_role="内容矩阵的编排层，负责把一个主题变成多种内容产品。",
            evidence=themes[:3] + ["PLANS.md multi-platform future scope"],
        ),
    ]


def render_cards(label: str, opportunities: list[dict[str, Any]]) -> str:
    lines = [
        f"# {label} 产品机会卡",
        "",
        "说明：本文件由轻量 ProductStrategyAgent 生成。`ClawMax` 是真实产品；其余标记为 `假想产品` 的条目用于探索方向，不代表已经实现。",
        "",
    ]
    for index, item in enumerate(opportunities, start=1):
        reality_label = "真实产品" if item["reality"] == "real" else "假想产品"
        lines.extend(
            [
                f"## {item['name']}",
                "",
                f"- 编号：{index}",
                f"- 状态：{reality_label}",
                f"- 一句话：{item['summary']}",
                f"- 目标用户：{item['target_user']}",
                f"- 用户画像：{item['user_persona']}",
                f"- 核心场景：{item['core_scenario']}",
                f"- MVP 范围：{'；'.join(item['mvp_scope'])}",
                f"- 实现难度：{item['implementation_difficulty']}",
                f"- 风险：{item['risk']}",
                f"- 下一步实验：{item['next_experiment']}",
                f"- 选题转化率信号：{item['conversion_signal']}",
                f"- 阅读数据回流：{item['reading_data_feedback']}",
                f"- 标题 A/B 测试：{' / '.join(item['title_ab_test'])}",
                f"- 投放策略：{item['promotion_strategy']}",
                f"- 商业化机会：{item['commercial_opportunity']}",
                f"- 内容产品矩阵位置：{item['content_matrix_role']}",
                f"- 依据：{'；'.join(str(e) for e in item['evidence'])}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def generate_product_strategy(label: str | None = None, article_label: str | None = None) -> dict[str, Any]:
    label = safe_label(label or latest_report_label())
    article_label = safe_label(article_label or label)
    started_at = now_iso()
    inputs = collect_inputs(label, article_label=article_label)
    opportunities = build_opportunities(inputs)
    product_dir = PRODUCTS_DIR / label
    product_dir.mkdir(parents=True, exist_ok=True)

    cards_path = product_dir / OUTPUT_CARDS_FILENAME
    opportunities_path = product_dir / OUTPUT_JSON_FILENAME
    metadata_path = product_dir / OUTPUT_METADATA_FILENAME

    payload = {
        "label": label,
        "article_label": article_label,
        "generated_at": started_at,
        "source_report": f"reports/{label}/technical-report.md",
        "source_article": f"articles/{article_label}/article.json" if (ARTICLES_DIR / article_label / "article.json").is_file() else "",
        "opportunities": opportunities,
    }
    metadata = {
        "label": label,
        "article_label": article_label,
        "generated_at": started_at,
        "generator_profile": PROFILE_NAME,
        "skills": [STRATEGY_SKILL, PIPELINE_SKILL],
        "mode": "lightweight_deterministic_strategy_scan",
        "source_report": f"reports/{label}/technical-report.md",
        "source_article_dir": f"articles/{article_label}" if (ARTICLES_DIR / article_label).is_dir() else "",
        "outputs": {
            "opportunity_cards": f"products/{label}/{OUTPUT_CARDS_FILENAME}",
            "opportunities_json": f"products/{label}/{OUTPUT_JSON_FILENAME}",
            "metadata": f"products/{label}/{OUTPUT_METADATA_FILENAME}",
        },
        "notes": "ClawMax is the real product. Other opportunities are hypothetical starter cards for review.",
    }

    cards_path.write_text(render_cards(label, opportunities), encoding="utf-8")
    write_json(opportunities_path, payload)
    write_json(metadata_path, metadata)

    result = {
        "status": "completed",
        "label": label,
        "output_dir": f"products/{label}",
        "outputs": metadata["outputs"],
        "opportunity_count": len(opportunities),
        "real_count": sum(1 for item in opportunities if item.get("reality") == "real"),
        "hypothetical_count": sum(1 for item in opportunities if item.get("reality") == "hypothetical"),
    }
    run_id = f"{label}-product-strategy"
    append_jsonl(RUNS_DIR / "product-strategy-runs.jsonl", {"run_id": run_id, **result, "finished_at": now_iso()})
    write_json(RUNS_DIR / f"{run_id}.json", {"run_id": run_id, **result, "finished_at": now_iso()})
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate lightweight product opportunity cards from a ClawMax report/article bundle.")
    parser.add_argument("--report-label", default=None, help="Input report label under reports/. Default: latest valid report directory.")
    parser.add_argument("--article-label", default=None, help="Input article label under articles/. Default: report label.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = generate_product_strategy(args.report_label, article_label=args.article_label)
    print("PASS: ProductStrategyAgent generated product opportunity cards.")
    print(f"Output dir: {REPO_ROOT / result['output_dir']}")
    for name, path in result["outputs"].items():
        print(f"{name}: {REPO_ROOT / path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except ProductStrategyError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
