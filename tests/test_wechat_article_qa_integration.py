from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = REPO_ROOT / "tests" / "test_wechat_article_agent_run.py"


def load_runner_module():
    spec = importlib.util.spec_from_file_location("wechat_article_agent_runner_for_qa_test", RUNNER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stub_existing_output_validators(monkeypatch, runner):
    monkeypatch.setattr(runner, "validate_draft", lambda path: "draft text" * 200)
    monkeypatch.setattr(
        runner,
        "validate_article_json",
        lambda path: {"sections": [{"type": "intro"}], "title_candidates": ["标题"], "risk_flags": [], "image_assets": []},
    )
    monkeypatch.setattr(runner, "validate_metadata", lambda path, *, report_label, output_label: {"auto_publish": False})
    monkeypatch.setattr(runner, "validate_final_article", lambda path: "final text" * 200)
    monkeypatch.setattr(runner, "validate_html_preview", lambda path: "html text" * 80)
    monkeypatch.setattr(runner, "validate_image_assets", lambda path, *, output_label: [])


def test_validate_outputs_runs_article_bundle_qa_and_returns_summary(tmp_path, monkeypatch):
    runner = load_runner_module()
    output_label = "demo-output"
    article_dir = tmp_path / "articles" / output_label
    article_dir.mkdir(parents=True)
    monkeypatch.setattr(runner, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(runner, "ARTICLES_DIR", tmp_path / "articles")
    stub_existing_output_validators(monkeypatch, runner)

    calls = []

    def fake_qa_article_bundle(label, *, repo_root=None):
        calls.append((label, repo_root))
        return {
            "status": "passed_with_warnings",
            "summary": {"errors": 0, "warnings": 1},
            "output_qa_report": f"articles/{label}/qa-report.json",
            "output_review_notes": f"articles/{label}/review-notes.md",
        }

    monkeypatch.setattr(runner, "qa_article_bundle", fake_qa_article_bundle, raising=False)

    validation = runner.validate_outputs(output_label, report_label="demo-report")

    assert calls == [(output_label, tmp_path)]
    assert validation["qa"]["status"] == "passed_with_warnings"
    assert validation["qa"]["summary"] == {"errors": 0, "warnings": 1}
    assert validation["qa_report_path"] == f"articles/{output_label}/qa-report.json"
    assert validation["review_notes_path"] == f"articles/{output_label}/review-notes.md"


def test_validate_outputs_fails_when_article_bundle_qa_fails(tmp_path, monkeypatch):
    runner = load_runner_module()
    output_label = "demo-output"
    article_dir = tmp_path / "articles" / output_label
    article_dir.mkdir(parents=True)
    monkeypatch.setattr(runner, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(runner, "ARTICLES_DIR", tmp_path / "articles")
    stub_existing_output_validators(monkeypatch, runner)

    def fake_qa_article_bundle(label, *, repo_root=None):
        return {
            "status": "failed",
            "summary": {"errors": 1, "warnings": 0},
            "issues": [{"severity": "error", "code": "article.auto_publish_eligible_not_false"}],
            "output_qa_report": f"articles/{label}/qa-report.json",
            "output_review_notes": f"articles/{label}/review-notes.md",
        }

    monkeypatch.setattr(runner, "qa_article_bundle", fake_qa_article_bundle, raising=False)

    with pytest.raises(runner.TestFailure, match="Article bundle QA failed"):
        runner.validate_outputs(output_label, report_label="demo-report")
