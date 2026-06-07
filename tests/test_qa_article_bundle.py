from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import qa_article_bundle as qa


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_valid_bundle(repo: Path, label: str = "demo-label") -> Path:
    article_dir = repo / "articles" / label
    images_dir = article_dir / "images"
    images_dir.mkdir(parents=True)

    for name in ["source-1.png", "source-2.png", "source-3.png", "source-4.png", "explainer.png"]:
        (images_dir / name).write_bytes(b"\x89PNG\r\n\x1a\nfake")

    assets = [
        {
            "id": "source-1",
            "purpose": "section_illustration",
            "kind": "official_image",
            "local_path": f"articles/{label}/images/source-1.png",
            "markdown_ref": "![官方图](./images/source-1.png)",
            "caption": "官方图",
            "source_url": "https://example.com/source-1",
            "source_title": "Source 1",
            "license_or_usage_note": "source-derived fixture",
            "status": "saved",
        },
        {
            "id": "source-2",
            "purpose": "section_illustration",
            "kind": "webpage_screenshot",
            "local_path": f"articles/{label}/images/source-2.png",
            "markdown_ref": "![网页截图](./images/source-2.png)",
            "caption": "网页截图",
            "source_url": "https://example.com/source-2",
            "source_title": "Source 2",
            "license_or_usage_note": "source-derived fixture",
            "status": "saved",
        },
        {
            "id": "source-3",
            "purpose": "section_illustration",
            "kind": "paper_figure",
            "local_path": f"articles/{label}/images/source-3.png",
            "markdown_ref": "![论文图](./images/source-3.png)",
            "caption": "论文图",
            "source_url": "https://example.com/source-3",
            "source_title": "Source 3",
            "license_or_usage_note": "source-derived fixture",
            "status": "saved",
        },
        {
            "id": "source-4",
            "purpose": "section_illustration",
            "kind": "github_screenshot",
            "local_path": f"articles/{label}/images/source-4.png",
            "markdown_ref": "![项目截图](./images/source-4.png)",
            "caption": "项目截图",
            "source_url": "https://example.com/source-4",
            "source_title": "Source 4",
            "license_or_usage_note": "source-derived fixture",
            "status": "saved",
        },
        {
            "id": "explainer",
            "purpose": "section_illustration",
            "kind": "ai_generated",
            "local_path": f"articles/{label}/images/explainer.png",
            "markdown_ref": "![原创讲解图](./images/explainer.png)",
            "caption": "原创讲解图",
            "source_url": "",
            "generation_prompt": "原创猫型讲解员解释 AI Agent QA 流程",
            "tool": "image_generate",
            "provider": "openai",
            "model": "gpt-image-2-medium",
            "status": "saved",
        },
    ]

    article = {
        "date": "2026-06-06",
        "title": "AI Agent 开始交作业了",
        "title_candidates": ["AI Agent 开始交作业了"],
        "digest": "今天聊聊 Agent 怎么从聊天走到真实工作流。",
        "sections": [
            {"heading": "开场白", "type": "intro", "content_md": "今天刷到一个很具体的问题：Agent 能不能稳定交付？"},
            {"heading": "AI 前沿", "type": "frontier", "content_md": "模型工具链正在变得更可审计。"},
            {"heading": "浪里淘金", "type": "gold_rush", "content_md": "这个项目适合正在折腾 AI workflow 的人看。链接：https://example.com/project"},
            {"heading": "今天值得想一想", "type": "reflection", "content_md": "真正值得看的不是 demo，而是能不能进入流程。"},
            {"heading": "结尾互动", "type": "closing", "content_md": "你最想把哪个工作交给 Agent？"},
            {"heading": "参考与信息来源", "type": "references", "content_md": "- https://example.com/project"},
        ],
        "source_report": "reports/demo-label/technical-report.md",
        "sources": [{"title": "Example", "url": "https://example.com/project"}],
        "risk_flags": [],
        "style_references": [],
        "external_reference_accounts": [],
        "source_attribution_note": "测试来源。",
        "image_assets": assets,
        "auto_publish_eligible": False,
    }
    metadata = {
        "output_final_article": f"articles/{label}/final-wechat-article.md",
        "output_html_preview": f"articles/{label}/wechat-preview.html",
        "output_image_assets": f"articles/{label}/image-assets.json",
        "output_images_dir": f"articles/{label}/images",
        "generated_files": [
            f"articles/{label}/wechat-draft.md",
            f"articles/{label}/final-wechat-article.md",
            f"articles/{label}/wechat-preview.html",
            f"articles/{label}/article.json",
            f"articles/{label}/metadata.json",
            f"articles/{label}/image-assets.json",
            *[asset["local_path"] for asset in assets],
        ],
        "auto_publish": False,
    }

    write_json(article_dir / "article.json", article)
    write_json(article_dir / "image-assets.json", assets)
    write_json(article_dir / "metadata.json", metadata)
    (article_dir / "wechat-draft.md").write_text("# 草稿\n\n## AI 前沿\n\n## 浪里淘金\n\n## 参考与信息来源\n", encoding="utf-8")
    (article_dir / "final-wechat-article.md").write_text(
        "# AI Agent 开始交作业了\n\n"
        "![官方图](./images/source-1.png)\n\n"
        "## 开场白\n\n今天刷到一个很具体的问题：Agent 能不能稳定交付？\n\n"
        "## AI 前沿\n\n模型工具链正在变得更可审计。\n\n"
        "![网页截图](./images/source-2.png)\n\n"
        "## 浪里淘金\n\n这个项目适合正在折腾 AI workflow 的人看。链接：https://example.com/project\n\n"
        "![论文图](./images/source-3.png)\n\n"
        "![项目截图](./images/source-4.png)\n\n"
        "![原创讲解图](./images/explainer.png)\n\n"
        "## 参考与信息来源\n\n- https://example.com/project\n",
        encoding="utf-8",
    )
    (article_dir / "wechat-preview.html").write_text(
        "<article><h1>AI Agent 开始交作业了</h1><img src=\"./images/source-1.png\"><h2>AI 前沿</h2><h2>浪里淘金</h2><a href=\"https://example.com/project\">source</a></article>",
        encoding="utf-8",
    )
    return article_dir


def test_valid_article_bundle_passes_and_writes_reports(tmp_path, monkeypatch):
    article_dir = write_valid_bundle(tmp_path)
    monkeypatch.setattr(qa, "REPO_ROOT", tmp_path)

    report = qa.qa_article_bundle("demo-label")

    assert report["status"] == "passed"
    assert report["summary"]["errors"] == 0
    assert (article_dir / "qa-report.json").is_file()
    assert (article_dir / "review-notes.md").is_file()
    notes = (article_dir / "review-notes.md").read_text(encoding="utf-8")
    assert "QA 通过" in notes


def test_bundle_fails_when_required_images_are_missing(tmp_path, monkeypatch):
    article_dir = write_valid_bundle(tmp_path)
    monkeypatch.setattr(qa, "REPO_ROOT", tmp_path)
    assets = json.loads((article_dir / "image-assets.json").read_text(encoding="utf-8"))[:2]
    write_json(article_dir / "image-assets.json", assets)
    article = json.loads((article_dir / "article.json").read_text(encoding="utf-8"))
    article["image_assets"] = assets
    write_json(article_dir / "article.json", article)

    report = qa.qa_article_bundle("demo-label")

    assert report["status"] == "failed"
    assert any(issue["code"] == "image_assets.too_few_saved" for issue in report["issues"])
    assert any(issue["severity"] == "error" for issue in report["issues"])


def test_bundle_fails_when_auto_publish_is_enabled(tmp_path, monkeypatch):
    article_dir = write_valid_bundle(tmp_path)
    monkeypatch.setattr(qa, "REPO_ROOT", tmp_path)
    article = json.loads((article_dir / "article.json").read_text(encoding="utf-8"))
    article["auto_publish_eligible"] = True
    write_json(article_dir / "article.json", article)

    report = qa.qa_article_bundle("demo-label")

    assert report["status"] == "failed"
    assert any(issue["code"] == "article.auto_publish_eligible_not_false" for issue in report["issues"])


def test_bundle_warns_on_report_voice_without_failing(tmp_path, monkeypatch):
    article_dir = write_valid_bundle(tmp_path)
    monkeypatch.setattr(qa, "REPO_ROOT", tmp_path)
    final_path = article_dir / "final-wechat-article.md"
    final_path.write_text(final_path.read_text(encoding="utf-8") + "\n值得注意的是，这一趋势表明生态正在深度融合，形成闭环。\n", encoding="utf-8")

    report = qa.qa_article_bundle("demo-label")

    assert report["status"] == "passed_with_warnings"
    assert any(issue["code"] == "content.report_voice_terms" for issue in report["issues"])


def test_cli_returns_nonzero_for_failed_bundle(tmp_path, monkeypatch):
    article_dir = write_valid_bundle(tmp_path)
    monkeypatch.setattr(qa, "REPO_ROOT", tmp_path)
    (article_dir / "final-wechat-article.md").unlink()

    exit_code = qa.main(["--article-label", "demo-label"])

    assert exit_code == 1
    report = json.loads((article_dir / "qa-report.json").read_text(encoding="utf-8"))
    assert report["status"] == "failed"
