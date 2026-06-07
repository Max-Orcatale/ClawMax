from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import run_product_strategy_agent as runner


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_inputs(repo: Path, label: str = "demo-label") -> None:
    report_dir = repo / "reports" / label
    article_dir = repo / "articles" / label
    report_dir.mkdir(parents=True)
    article_dir.mkdir(parents=True)

    (report_dir / "technical-report.md").write_text(
        "# AI 技术报告\n\n"
        "## 今日摘要\n\nAgent 工作流、自动 QA、内容生成和 AI coding tools 正在进入团队内部流程。\n\n"
        "## 开源项目与开发者生态\n\n开发者越来越需要可审计的 Agent 流水线，把资料检索、文章生成、QA 和发布草稿串起来。\n\n"
        "## 来源链接\n\n- https://example.com/agent-workflow\n",
        encoding="utf-8",
    )
    write_json(
        report_dir / "brief.json",
        {
            "date": "2026-06-07",
            "title": "Agent 工作流进入内容团队",
            "summary": "Agent 工作流开始从单点聊天变成可审计的内容生产流水线。",
            "top_items": ["Agent workflow", "auto QA", "content automation"],
            "wechat_angles": ["AI 内容团队如何把日报变成公众号草稿"],
            "tools_to_try": ["ClawMax", "AgentKit", "PromptBench Studio"],
        },
    )
    write_json(
        report_dir / "sources.json",
        [
            {
                "title": "Agent workflow example",
                "url": "https://example.com/agent-workflow",
                "source_type": "company_blog",
                "published_at": "2026-06-01",
                "retrieved_at": "2026-06-07T00:00:00Z",
                "summary": "Agent workflow trend",
                "confidence": "medium",
                "tags": ["agent", "workflow"],
            }
        ],
    )
    (article_dir / "final-wechat-article.md").write_text(
        "# AI 内容团队开始自己跑流水线了\n\n"
        "## AI 前沿\n\nAgent 正在从聊天窗口走向真实工作流。\n\n"
        "## 浪里淘金\n\nClawMax 这个项目把日报、公众号草稿、图片和 QA 串起来。\n\n"
        "## 参考与信息来源\n\n- https://example.com/agent-workflow\n",
        encoding="utf-8",
    )
    write_json(
        article_dir / "article.json",
        {
            "title": "AI 内容团队开始自己跑流水线了",
            "digest": "Agent 工作流开始进入内容生产。",
            "sections": [
                {"heading": "AI 前沿", "type": "frontier", "content_md": "Agent 正在从聊天窗口走向真实工作流。"},
                {"heading": "浪里淘金", "type": "gold_rush", "content_md": "ClawMax 这个项目值得看。"},
            ],
            "sources": [{"title": "Agent workflow example", "url": "https://example.com/agent-workflow"}],
            "risk_flags": [],
            "auto_publish_eligible": False,
        },
    )


def test_product_strategy_generates_real_and_hypothetical_opportunities(tmp_path, monkeypatch):
    write_inputs(tmp_path)
    monkeypatch.setattr(runner, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(runner, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(runner, "ARTICLES_DIR", tmp_path / "articles")
    monkeypatch.setattr(runner, "PRODUCTS_DIR", tmp_path / "products")
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path / "runs")

    result = runner.generate_product_strategy("demo-label")

    assert result["status"] == "completed"
    product_dir = tmp_path / "products" / "demo-label"
    assert (product_dir / "opportunity-cards.md").is_file()
    assert (product_dir / "opportunities.json").is_file()
    assert (product_dir / "metadata.json").is_file()

    data = json.loads((product_dir / "opportunities.json").read_text(encoding="utf-8"))
    opportunities = data["opportunities"]
    assert len(opportunities) >= 4
    assert any(item["name"] == "ClawMax" and item["reality"] == "real" for item in opportunities)
    assert all(item["reality"] in {"real", "hypothetical"} for item in opportunities)
    assert any(item["reality"] == "hypothetical" for item in opportunities)
    for item in opportunities:
        assert item["user_persona"]
        assert item["conversion_signal"]
        assert item["reading_data_feedback"]
        assert item["title_ab_test"]
        assert item["promotion_strategy"]
        assert item["commercial_opportunity"]
        assert item["content_matrix_role"]
        assert item["mvp_scope"]
        assert item["risk"]

    markdown = (product_dir / "opportunity-cards.md").read_text(encoding="utf-8")
    assert "# demo-label 产品机会卡" in markdown
    assert "## ClawMax" in markdown
    assert "真实产品" in markdown
    assert "假想产品" in markdown


def test_product_strategy_requires_report_input(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(runner, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(runner, "ARTICLES_DIR", tmp_path / "articles")
    monkeypatch.setattr(runner, "PRODUCTS_DIR", tmp_path / "products")
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path / "runs")

    with pytest.raises(runner.ProductStrategyError, match="Missing report input"):
        runner.generate_product_strategy("missing-label")
