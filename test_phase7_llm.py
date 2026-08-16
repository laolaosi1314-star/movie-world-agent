"""Phase 7 LLM provider 接入：配置读取 / 提示词合规 / 降级 / 一键切回模板。

纯离线单测：不连数据库、不发网络请求（用 unittest.mock 模拟 httpx）。
运行：python test_phase7_llm.py
"""
import os
import sys
import tempfile

# 不连数据库，仅构造 engine（create_engine 不会立即连接）
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://u:p@localhost:5432/movie_world")

from unittest.mock import patch, MagicMock  # noqa: E402

import app.llm.client as client  # noqa: E402


def _ok(text: str) -> None:
    print("OK", text)


def test_disabled_default():
    os.environ.pop("LLM_ENABLED", None)
    os.environ.pop("LLM_API_KEY", None)
    os.environ.pop("LLM_BASE_URL", None)
    client._ENV_LOADED = False
    c = client.get_llm_client()
    assert isinstance(c, client.RuleBasedClient), type(c)
    assert c.render_narrative({}, {}, "x") is None
    _ok("disabled_default")


def test_prompt_constraints():
    fp = {"event_id": 1, "summary": "星河彼端上映", "metrics": {"box_office": 12.3}}
    style = {"name": "星闻周刊", "stance": "hype",
             "outlet_type": "tabloid", "credibility": 42}
    msgs = client.build_narrative_messages(fp, style, "boxoffice")
    assert len(msgs) == 2
    sys_p = msgs[0]["content"]
    assert "只能使用 FACT_PACK" in sys_p or "严禁编造" in sys_p, "应禁止编造事实"
    assert "不得做任何判定" in sys_p, "应禁止做判定/预测"
    assert "星闻周刊" in sys_p, "应携带媒体名"
    assert "tabloid" not in sys_p.lower() or "小报" in sys_p, "媒体类型应映射到中文标签"
    user_p = msgs[1]["content"]
    assert "boxoffice" in user_p, "应携带 news_type"
    assert "event_id" in user_p, "应携带 fact_pack JSON"
    _ok("prompt_constraints")


class _FakeResp:
    status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return {"choices": [{"message": {"content": "  《星河彼端》票房飘红，业内瞩目。  "}}]}


@patch("httpx.Client")
def test_post_success(mock_cls):
    mock_client = MagicMock()
    mock_cls.return_value.__enter__.return_value = mock_client
    mock_client.post.return_value = _FakeResp()
    cfg = client.LLMConfig(enabled=True, api_key="k",
                           base_url="http://provider/v1", model="m")
    c = client.OpenAICompatibleClient(cfg)
    text = c.render_narrative(
        {"event_id": 1}, {"name": "X", "stance": "hype",
                          "outlet_type": "tabloid", "credibility": 50}, "boxoffice")
    assert text == "《星河彼端》票房飘红，业内瞩目。", repr(text)
    # complete 也走通并返回正文
    assert c.complete("hi") == "《星河彼端》票房飘红，业内瞩目。"
    _ok("post_success")


@patch("httpx.Client")
def test_post_failure_degrade(mock_cls):
    mock_client = MagicMock()
    mock_cls.return_value.__enter__.return_value = mock_client
    mock_client.post.side_effect = Exception("boom")  # 网络/超时错误
    cfg = client.LLMConfig(enabled=True, api_key="k", base_url="http://provider/v1")
    c = client.OpenAICompatibleClient(cfg)
    # 任何异常都必须降级为 None，绝不能抛到调用方
    assert c.render_narrative({}, {}, "news") is None
    assert c.complete("hi") == '{"decision": "pending", "reason": "llm unavailable"}'
    _ok("post_failure_degrade")


def test_config_and_switch():
    os.environ["LLM_ENABLED"] = "true"
    os.environ["LLM_API_KEY"] = "secret"
    os.environ["LLM_BASE_URL"] = "http://provider/v1"
    os.environ["LLM_MODEL"] = "gpt-test"
    client._ENV_LOADED = False

    c = client.get_llm_client()
    assert isinstance(c, client.OpenAICompatibleClient), type(c)
    # 一键切回模板
    rt = client.get_llm_client(force_template=True)
    assert isinstance(rt, client.RuleBasedClient), type(rt)
    # 诊断
    st = client.get_llm_status()
    assert st["engine"] == "llm", st
    st2 = client.get_llm_status(force_template=True)
    assert st2["engine"] == "template", st2

    # 缺密钥 -> 降级模板
    os.environ.pop("LLM_API_KEY", None)
    client._ENV_LOADED = False
    c2 = client.get_llm_client()
    assert isinstance(c2, client.RuleBasedClient), type(c2)
    _ok("config_and_switch")


def test_dotenv_reader():
    os.environ.pop("LLM_ENABLED", None)
    os.environ.pop("LLM_API_KEY", None)
    os.environ.pop("LLM_MODEL", None)
    os.environ.pop("FOO", None)
    fd, path = tempfile.mkstemp(suffix=".env")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write('LLM_ENABLED=true\nLLM_API_KEY=abc123\n# comment line\nFOO=bar\n'
                'LLM_MODEL=deepseek-chat\n')
    client._load_dotenv(path)
    # 仅 LLM_* 被注入（安全过滤：不污染无关环境变量）
    assert os.environ.get("LLM_ENABLED") == "true"
    assert os.environ.get("LLM_API_KEY") == "abc123"
    assert os.environ.get("LLM_MODEL") == "deepseek-chat"
    # 非 LLM_ 变量不应被注入
    assert "FOO" not in os.environ, "非 LLM_ 变量不应被注入"
    os.remove(path)
    _ok("dotenv_reader")


if __name__ == "__main__":
    test_disabled_default()
    test_prompt_constraints()
    test_post_success()
    test_post_failure_degrade()
    test_config_and_switch()
    test_dotenv_reader()
    print("\nALL_PHASE7_TESTS_GREEN")
