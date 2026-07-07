import httpx

from app import config
from app.llm import client


def test_free_key_preferred_over_anthropic():
    env = {"GROQ_API_KEY": "gsk-x", "ANTHROPIC_API_KEY": "sk-ant-x"}
    assert config.pick_provider(env) == "groq"


def test_anthropic_used_when_only_key_present():
    assert config.pick_provider({"ANTHROPIC_API_KEY": "sk-ant-x"}) == "anthropic"


def test_explicit_provider_override_wins():
    env = {
        "LEADGENIUS_LLM_PROVIDER": "anthropic",
        "GROQ_API_KEY": "gsk-x",
        "ANTHROPIC_API_KEY": "sk-ant-x",
    }
    assert config.pick_provider(env) == "anthropic"


def test_priority_order_among_free_providers():
    env = {"GEMINI_API_KEY": "g-x", "OPENROUTER_API_KEY": "or-x"}
    assert config.pick_provider(env) == "gemini"


def test_no_keys_defaults_to_anthropic_stub():
    assert config.pick_provider({}) == "anthropic"


def test_complete_json_dispatches_to_openai_compat(monkeypatch):
    monkeypatch.setattr(config, "USE_LLM_STUB", False)
    monkeypatch.setattr(config, "LLM_PROVIDER", "groq")
    calls = {}

    def fake_call(model, system, user):
        calls["args"] = (model, system, user)
        return 'noise {"ok": true} noise', 100, 50

    monkeypatch.setattr(client, "_openai_compat_call", fake_call)
    result = client.complete_json("llama-3.3-70b-versatile", "sys", "usr", lambda: {"stub": True})
    assert result == {"ok": True}
    assert calls["args"] == ("llama-3.3-70b-versatile", "sys", "usr")


def test_complete_text_dispatches_to_anthropic(monkeypatch):
    monkeypatch.setattr(config, "USE_LLM_STUB", False)
    monkeypatch.setattr(config, "LLM_PROVIDER", "anthropic")
    monkeypatch.setattr(client, "_anthropic_call", lambda m, s, u: ("  plain text  ", 100, 50))
    assert client.complete_text("claude-sonnet-5", "sys", "usr", lambda: "stub") == "plain text"


def test_openai_compat_request_shape(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(config, "LLM_API_KEY", "gsk-test")
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "hello"}}],
                    "usage": {"prompt_tokens": 12, "completion_tokens": 3}}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr(httpx, "post", fake_post)
    text, in_tokens, out_tokens = client._openai_compat_call("llama-3.1-8b-instant", "sys", "usr")
    assert text == "hello"
    assert (in_tokens, out_tokens) == (12, 3)
    assert captured["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer gsk-test"
    assert captured["json"]["model"] == "llama-3.1-8b-instant"
    assert captured["json"]["messages"][0] == {"role": "system", "content": "sys"}
