#!/usr/bin/env python3
"""Unit tests for finalizing a ClawMax WeChat article bundle."""

from __future__ import annotations

import json
import sys
from pathlib import Path
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.finalize_wechat_article import finalize_wechat_article_bundle


class FinalizeWeChatArticleBundleTest(unittest.TestCase):
    def test_finalizer_creates_publish_ready_article_and_image_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            report_label = "2026-05-30-test"
            output_label = report_label
            report_dir = repo_root / "reports" / report_label
            article_dir = repo_root / "articles" / output_label
            (report_dir / "images").mkdir(parents=True)
            article_dir.mkdir(parents=True)

            (report_dir / "technical-report.md").write_text("# 测试报告\n", encoding="utf-8")
            (report_dir / "sources.json").write_text("[]\n", encoding="utf-8")
            (report_dir / "brief.json").write_text("{}\n", encoding="utf-8")

            image_assets = []
            fixture_specs = [
                ("source-1.png", "official_image", "section_illustration", "官方页面配图", "https://example.com/official-image.png", "", ""),
                ("source-2.png", "webpage_screenshot", "section_illustration", "网页截图", "https://example.com/page", "", ""),
                ("source-3.png", "paper_figure", "section_illustration", "论文图表", "https://example.com/paper.pdf", "", ""),
                ("explainer-comic.png", "ai_generated", "section_illustration", "原创讲解漫画", "", "原创猫型讲解员和黑白小鼠学生解释 Agent 审计流程", "openai gpt-image-2-medium via image_generate"),
                ("source-4.png", "github_screenshot", "section_illustration", "GitHub 项目截图", "https://github.com/example/project", "", ""),
            ]
            for index, (filename, kind, purpose, caption, source_url, prompt, notes) in enumerate(fixture_specs, start=1):
                payload = f"fake-png-{index}".encode("utf-8")
                (report_dir / "images" / filename).write_bytes(payload)
                image_assets.append(
                    {
                        "id": Path(filename).stem,
                        "kind": kind,
                        "purpose": purpose,
                        "local_path": f"reports/{report_label}/images/{filename}",
                        "markdown_ref": f"![配图 {index}](./images/{filename})",
                        "caption": caption,
                        "source_url": source_url,
                        "source_title": "Example Source" if source_url else "",
                        "license_or_usage_note": "unit test source-derived placeholder" if source_url else "unit test AI-generated bitmap placeholder",
                        "generation_prompt": prompt,
                        "model": "gpt-image-2-medium" if prompt else "",
                        "provider": "openai" if prompt else "",
                        "tool": "image_generate" if prompt else "",
                        "status": "saved",
                        "notes": notes or "unit test fixture",
                    }
                )
            (report_dir / "image-assets.json").write_text(
                json.dumps(image_assets, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            article = {
                "date": "2026-05-30",
                "title": "AI Agent 开始交作业了",
                "title_candidates": ["AI Agent 开始交作业了"],
                "digest": "一篇用于测试最终公众号文章生成的摘要。",
                "sections": [
                    {
                        "heading": "开场白",
                        "type": "intro",
                        "content_md": "今天想聊一个很具体的问题：AI Agent 不只是会聊天，还要能交付结果。",
                    },
                    {
                        "heading": "AI 前沿",
                        "type": "frontier",
                        "content_md": "### 新变化\n\n模型能力正在进入工程流程，团队更关心可审计、可复盘和可追踪。",
                    },
                    {
                        "heading": "浪里淘金",
                        "type": "gold_rush",
                        "content_md": "这个方向适合正在折腾 AI workflow 的人看。链接：https://example.com/project",
                    },
                    {
                        "heading": "今天值得想一想",
                        "type": "reflection",
                        "content_md": "真正值得看的不是 demo，而是它能不能稳定进入流程。",
                    },
                    {
                        "heading": "结尾互动",
                        "type": "closing",
                        "content_md": "你最希望把哪个工作交给 Agent？",
                    },
                    {
                        "heading": "参考与信息来源",
                        "type": "references",
                        "content_md": "- https://example.com/project",
                    },
                ],
                "source_report": f"reports/{report_label}/technical-report.md",
                "sources": [{"title": "Example", "url": "https://example.com/project"}],
                "risk_flags": [],
                "style_references": [],
                "external_reference_accounts": [],
                "source_attribution_note": "只使用测试来源。",
                "auto_publish_eligible": False,
            }
            (article_dir / "article.json").write_text(json.dumps(article, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            (article_dir / "wechat-draft.md").write_text("# 草稿\n", encoding="utf-8")
            (article_dir / "metadata.json").write_text(
                json.dumps(
                    {
                        "date": "2026-05-30",
                        "source_report": f"reports/{report_label}/technical-report.md",
                        "output_draft": f"articles/{output_label}/wechat-draft.md",
                        "output_article_json": f"articles/{output_label}/article.json",
                        "auto_publish": False,
                        "generator_profile": "wechatarticleagent",
                        "generated_files": [
                            f"articles/{output_label}/wechat-draft.md",
                            f"articles/{output_label}/article.json",
                            f"articles/{output_label}/metadata.json",
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            result = finalize_wechat_article_bundle(
                repo_root=repo_root,
                report_label=report_label,
                output_label=output_label,
                generator_profile="wechatarticleagent",
            )

            final_article = repo_root / result["final_article_path"]
            image_manifest = repo_root / result["image_assets_path"]
            html_preview = repo_root / result["html_preview_path"]
            copied_image = repo_root / "articles" / output_label / "images" / "source-1.png"

            self.assertTrue(final_article.is_file())
            self.assertTrue(image_manifest.is_file())
            self.assertTrue(html_preview.is_file())
            self.assertTrue(copied_image.is_file())
            self.assertEqual(copied_image.read_bytes(), b"fake-png-1")

            final_text = final_article.read_text(encoding="utf-8")
            self.assertIn("# AI Agent 开始交作业了", final_text)
            self.assertIn("![配图 1](./images/source-1.png)", final_text)
            self.assertIn("![配图 5](./images/source-4.png)", final_text)
            self.assertIn("## 开场白", final_text)
            self.assertIn("## AI 前沿", final_text)
            self.assertIn("## 浪里淘金", final_text)
            self.assertIn("## 参考与信息来源", final_text)
            self.assertIn("https://example.com/project", final_text)

            manifest = json.loads(image_manifest.read_text(encoding="utf-8"))
            self.assertEqual(len(manifest), 5)
            self.assertEqual(manifest[0]["local_path"], f"articles/{output_label}/images/source-1.png")
            self.assertEqual(manifest[0]["status"], "saved")
            self.assertEqual(manifest[0]["kind"], "official_image")

            updated_article = json.loads((article_dir / "article.json").read_text(encoding="utf-8"))
            self.assertEqual(updated_article["image_assets"], manifest)

            updated_metadata = json.loads((article_dir / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(updated_metadata["output_final_article"], f"articles/{output_label}/final-wechat-article.md")
            self.assertEqual(updated_metadata["output_image_assets"], f"articles/{output_label}/image-assets.json")
            self.assertIn(f"articles/{output_label}/final-wechat-article.md", updated_metadata["generated_files"])
            self.assertIn(f"articles/{output_label}/wechat-preview.html", updated_metadata["generated_files"])
            self.assertIn(f"articles/{output_label}/image-assets.json", updated_metadata["generated_files"])
            self.assertIn(f"articles/{output_label}/images/source-4.png", updated_metadata["generated_files"])
            self.assertEqual(updated_metadata["output_html_preview"], f"articles/{output_label}/wechat-preview.html")

            html_text = html_preview.read_text(encoding="utf-8")
            self.assertIn("<article", html_text)
            self.assertIn("AI Agent 开始交作业了", html_text)
            self.assertIn("./images/source-1.png", html_text)
            self.assertIn("./images/source-4.png", html_text)


if __name__ == "__main__":
    unittest.main()
