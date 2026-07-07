import pytest

from app.db import queries
from app.llm import prompt_library, prompts
from app.services import analyze, research, write


def test_resolve_returns_default_without_override(workspace):
    assert prompt_library.resolve(workspace["ws_id"], "voice") == prompts.SYSTEM_VOICE
    assert prompt_library.resolve(workspace["ws_id"], "email_step_1") == prompts.EMAIL_STEP_SPECS[1]


def test_override_wins_and_reset_restores_default(workspace):
    ws_id = workspace["ws_id"]
    assert prompt_library.set_override(ws_id, "voice", "Write like a calm operator.")
    assert prompt_library.resolve(ws_id, "voice") == "Write like a calm operator."
    prompt_library.clear_override(ws_id, "voice")
    assert prompt_library.resolve(ws_id, "voice") == prompts.SYSTEM_VOICE


def test_blank_or_default_content_clears_override(workspace):
    ws_id = workspace["ws_id"]
    prompt_library.set_override(ws_id, "analysis", "Custom analysis rules.")
    assert not prompt_library.set_override(ws_id, "analysis", "   ")
    assert prompt_library.resolve(ws_id, "analysis") == prompts.ANALYZE_SYSTEM
    assert not prompt_library.set_override(ws_id, "analysis", prompts.ANALYZE_SYSTEM)
    assert prompt_library.overrides(ws_id) == {}


def test_unknown_slot_rejected(workspace):
    with pytest.raises(ValueError):
        prompt_library.resolve(workspace["ws_id"], "nope")
    with pytest.raises(ValueError):
        prompt_library.set_override(workspace["ws_id"], "nope", "x")
    with pytest.raises(ValueError):
        prompt_library.clear_override(workspace["ws_id"], "nope")


def test_overrides_are_scoped_per_workspace(workspace):
    other_owner = queries.create_user("o@example.com", "O", "x")
    other_ws = queries.create_workspace("Other", other_owner, 10)
    prompt_library.set_override(workspace["ws_id"], "voice", "Custom voice A")
    assert prompt_library.resolve(other_ws, "voice") == prompts.SYSTEM_VOICE


def test_every_slot_has_a_default():
    base = prompt_library.defaults()
    for s in prompt_library.slots():
        assert s["key"] in base
        assert s["default"].strip()


def test_email_user_uses_custom_spec():
    offer = {"what_we_sell": "automation", "proof_point": ""}
    hyp = {"statement": "Quotes are slow.", "evidence": []}
    text = prompts.email_user("Acme", offer, hyp, [], 1, "CUSTOM STEP ONE SPEC")
    assert "CUSTOM STEP ONE SPEC" in text
    assert prompts.EMAIL_STEP_SPECS[1] not in text


def test_generation_uses_workspace_prompt_overrides(sample_list, monkeypatch):
    ws_id = sample_list["ws_id"]
    prompt_library.set_override(ws_id, "voice", "OVERRIDDEN VOICE RULES")
    prompt_library.set_override(ws_id, "email_step_1", "OVERRIDDEN EMAIL ONE SPEC")
    prompt_library.set_override(ws_id, "li_dm", "OVERRIDDEN DM SPEC")

    captured = []

    def spy(model, system, user, stub_fn):
        captured.append({"system": system, "user": user})
        return stub_fn()

    monkeypatch.setattr("app.llm.client.complete_json", spy)

    lead = queries.leads_for_list(sample_list["list_id"])[0]
    research.research_lead(lead["id"])
    offer = queries.get_offer_profile(sample_list["profile_id"])
    analyze.analyze_lead(lead["id"], offer)
    write.generate_for_lead(lead["id"], offer)

    email_calls = [c for c in captured if "OVERRIDDEN EMAIL ONE SPEC" in c["user"]]
    assert email_calls and email_calls[0]["system"] == "OVERRIDDEN VOICE RULES"
    dm_calls = [c for c in captured if "OVERRIDDEN DM SPEC" in c["user"]]
    assert dm_calls and dm_calls[0]["system"] == "OVERRIDDEN VOICE RULES"
    assert all(c["system"] != prompts.SYSTEM_VOICE for c in captured
               if "Prospect company" in c["user"])
