import argparse

import run_full_real_pipeline as pipeline


def test_build_commands_are_real_end_to_end():
    args = argparse.Namespace(
        report_timeout=1800,
        wechat_timeout=2400,
        force=False,
        author="ClawMax",
    )

    commands = pipeline.build_commands(args, report_label="2026-06-07-real-full-test", article_label="2026-06-07-real-full-test-wechat")

    flattened = "\n".join(" ".join(command) for command in commands.values())
    assert "--mock-smoke" not in flattened
    assert "--dry-run" not in flattened
    assert commands["technical_report"][:2] == [pipeline.sys.executable, "tests/test_technical_report_agent_run.py"]
    assert "--output-label" in commands["technical_report"]
    assert commands["wechat_article"][:2] == [pipeline.sys.executable, "tests/test_wechat_article_agent_run.py"]
    assert commands["publish" if False else "wechat_draft"][:2] == [pipeline.sys.executable, "scripts/publish_wechat_article.py"]
    assert commands["wechat_draft"][commands["wechat_draft"].index("--mode") + 1] == "draft"
    assert commands["product_strategy"][:2] == [pipeline.sys.executable, "scripts/run_product_strategy_agent.py"]


def test_safe_label_rejects_path_traversal():
    for value in ["../x", "x/y", "x y", ""]:
        try:
            pipeline.safe_label(value)
        except pipeline.PipelineError:
            pass
        else:
            raise AssertionError(f"unsafe label accepted: {value!r}")
