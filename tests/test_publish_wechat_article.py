from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import publish_wechat_article as pub


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@pytest.fixture()
def article_bundle(tmp_path, monkeypatch):
    repo = tmp_path
    article_dir = repo / "articles" / "demo-label"
    images_dir = article_dir / "images"
    images_dir.mkdir(parents=True)
    for name in ["cover.png", "source-1.png"]:
        (images_dir / name).write_bytes(b"\x89PNG\r\n\x1a\nfake")

    article = {
        "date": "2026-06-02",
        "title": "AI 开始走出屏幕",
        "digest": "今天聊聊 Physical AI 和 agent runtime。",
        "auto_publish_eligible": False,
        "sections": [
            {
                "heading": "开场白",
                "type": "intro",
                "content_md": "![封面](./images/cover.png)\n\n以前我们说 AI 在屏幕里工作，现在它要进真实世界。",
            },
            {
                "heading": "AI 前沿",
                "type": "frontier",
                "content_md": "- Physical AI 正在升温\n- Agent runtime 变得重要",
            },
            {
                "heading": "参考与信息来源",
                "type": "references",
                "content_md": "[vLLM](https://github.com/vllm-project/vllm)",
            },
        ],
    }
    assets = [
        {
            "id": "cover",
            "purpose": "cover",
            "kind": "ai_generated",
            "local_path": "articles/demo-label/images/cover.png",
            "markdown_ref": "./images/cover.png",
            "tool": "image_generate",
            "provider": "openai",
            "model": "gpt-image-2-medium",
        },
        {
            "id": "source-1",
            "purpose": "section_illustration",
            "kind": "source_image",
            "local_path": "articles/demo-label/images/source-1.png",
            "markdown_ref": "./images/source-1.png",
            "source_url": "https://example.org/source",
        },
    ]
    write_json(article_dir / "article.json", article)
    write_json(article_dir / "image-assets.json", assets)
    (article_dir / "final-wechat-article.md").write_text("# AI 开始走出屏幕\n", encoding="utf-8")

    monkeypatch.setattr(pub, "REPO_ROOT", repo)
    monkeypatch.setattr(pub, "ARTICLES_DIR", repo / "articles")
    return article_dir


def test_dry_run_writes_manifest_without_credentials(article_bundle, monkeypatch):
    monkeypatch.delenv("WECHAT_MP_APPID", raising=False)
    monkeypatch.delenv("WECHAT_MP_APPSECRET", raising=False)

    manifest_path = pub.create_wechat_draft("demo-label", dry_run=True, author="ClawMax", digest_max_chars=120, manifest_filename="wechat-publish.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["status"] == "dry_run"
    assert manifest["auto_publish"] is False
    assert manifest["draft_media_id"] == ""
    assert manifest["thumb"]["thumb_media_id"] == "DRY_RUN_THUMB_MEDIA_ID"
    assert len(manifest["uploaded_images"]) == 2


def test_missing_credentials_fail_for_real_run(article_bundle, monkeypatch, tmp_path):
    monkeypatch.delenv("WECHAT_MP_APPID", raising=False)
    monkeypatch.delenv("WECHAT_MP_APPSECRET", raising=False)
    monkeypatch.setattr(pub, "DEFAULT_HERMES_ENV", tmp_path / "missing.env")

    with pytest.raises(pub.PublishError, match="WECHAT_MP_APPID"):
        pub.create_wechat_draft("demo-label", dry_run=False, author="ClawMax", digest_max_chars=120, manifest_filename="wechat-publish.json")


def test_create_draft_with_mocked_wechat_api(article_bundle, monkeypatch):
    monkeypatch.setenv("WECHAT_MP_APPID", "wx1234567890")
    monkeypatch.setenv("WECHAT_MP_APPSECRET", "secret-value")
    calls = {"content_uploads": 0, "thumb_uploads": 0, "drafts": 0}

    monkeypatch.setattr(pub, "get_access_token", lambda appid, secret: "ACCESS_TOKEN")

    def fake_upload_content(access_token: str, image_path: Path) -> str:
        calls["content_uploads"] += 1
        return f"https://mmbiz.qpic.cn/{image_path.name}"

    def fake_upload_thumb(access_token: str, image_path: Path) -> str:
        calls["thumb_uploads"] += 1
        return "THUMB_MEDIA_ID"

    def fake_add_draft(access_token: str, payload: dict) -> str:
        calls["drafts"] += 1
        article = payload["articles"][0]
        assert article["thumb_media_id"] == "THUMB_MEDIA_ID"
        assert "mmbiz.qpic.cn/cover.png" in article["content"]
        assert "./images/cover.png" not in article["content"]
        return "DRAFT_MEDIA_ID"

    monkeypatch.setattr(pub, "upload_content_image", fake_upload_content)
    monkeypatch.setattr(pub, "upload_thumb_material", fake_upload_thumb)
    monkeypatch.setattr(pub, "add_draft", fake_add_draft)

    manifest_path = pub.create_wechat_draft("demo-label", dry_run=False, author="ClawMax", digest_max_chars=120, manifest_filename="wechat-publish.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["status"] == "draft_created"
    assert manifest["draft_media_id"] == "DRAFT_MEDIA_ID"
    assert manifest["appid_hint"] == "wx1***890"
    assert calls == {"content_uploads": 2, "thumb_uploads": 1, "drafts": 1}


def test_publish_mode_is_rejected():
    with pytest.raises(pub.PublishError, match="Only draft mode"):
        pub.main(["--article-label", "demo-label", "--mode", "publish", "--dry-run"])
