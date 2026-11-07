"""Choosing the Claude models in server/.env (JE_CLAUDE_WRITER, JE_CLAUDE_QUICK).

2026-11-05 the user is testing voices on the phone and wants every call on Haiku to save tokens. Without the
two settings the server must behave exactly as before: Sonnet writes, Haiku does the quick wording.
"""
import json
import logging
from dataclasses import replace

import pytest

from fakes import FakeAnthropic, script_json
from je_server.claude import HAIKU, QUICKS, SONNET, WRITERS, Claude
from je_server.config import load_settings
from je_server.topics import get

TOKEN = {"JE_TOKEN": "x" * 32}


# --- server/.env --------------------------------------------------------------------------------

def test_models_default_to_sonnet_writer_and_haiku_quick():
    s = load_settings(TOKEN)
    assert s.claude_writer == "sonnet" and s.claude_quick == "haiku"


def test_empty_model_settings_keep_the_defaults():
    # .env.example leaves both lines empty
    s = load_settings({**TOKEN, "JE_CLAUDE_WRITER": "", "JE_CLAUDE_QUICK": " "})
    assert s.claude_writer == "sonnet" and s.claude_quick == "haiku"


def test_models_read_from_env():
    s = load_settings({**TOKEN, "JE_CLAUDE_WRITER": "haiku", "JE_CLAUDE_QUICK": "haiku"})
    assert s.claude_writer == "haiku" and s.claude_quick == "haiku"
    s = load_settings({**TOKEN, "JE_CLAUDE_WRITER": " Opus ", "JE_CLAUDE_QUICK": "Sonnet"})
    assert s.claude_writer == "opus" and s.claude_quick == "sonnet"


def test_unknown_model_names_stop_the_server():
    with pytest.raises(ValueError, match="JE_CLAUDE_WRITER must be one of haiku, sonnet, opus, not 'gpt'"):
        load_settings({**TOKEN, "JE_CLAUDE_WRITER": "gpt"})
    with pytest.raises(ValueError, match="JE_CLAUDE_QUICK must be one of haiku, sonnet, not 'opus'"):
        load_settings({**TOKEN, "JE_CLAUDE_QUICK": "opus"})


# --- what each model is sent ----------------------------------------------------------------------

def test_defaults_are_the_spec_settings():
    assert WRITERS["sonnet"] is SONNET and QUICKS["haiku"] is HAIKU


def test_presets_follow_the_api_rules():
    # Claude API (2026-11-05): Opus 5.5 rejects disabled thinking at every effort; Haiku 5.5 takes it, and Sonnet 5.5
    # takes between_tools, only at effort high or below; API version 2026-10-21 rejects temperature/top_p/top_k.
    for preset in [*WRITERS.values(), *QUICKS.values()]:
        assert not {"temperature", "top_p", "top_k"} & preset.keys()
        thinking = preset.get("thinking", {}).get("type")
        if preset["model"] == "claude-opus-5-5":
            assert thinking is None
        elif thinking in ("disabled", "between_tools"):
            assert preset.get("effort", "high") in ("low", "medium", "high")


def test_a_role_keeps_its_settings_when_the_model_changes():
    # writing: thinking off where the model allows, effort low; quick wording: thinking off, no effort sent
    # (feedback() streams without output_config, so a quick preset must not rely on effort)
    assert all(p["effort"] == "low" for p in WRITERS.values())
    assert all("effort" not in p for p in QUICKS.values())
    assert all(p.get("thinking", {}).get("type") != "adaptive" for p in [*WRITERS.values(), *QUICKS.values()])


@pytest.mark.anyio
async def test_haiku_writer_request():
    fake = FakeAnthropic([script_json(user_turns=3)])
    await Claude(fake, writer=WRITERS["haiku"]).make_script("길 묻기", get("other"))
    r = fake.requests[0]
    assert r["model"] == "claude-haiku-5-5" and r["thinking"] == {"type": "disabled"}
    assert r["output_config"]["effort"] == "low" and r["output_config"]["format"]["type"] == "json_schema"


@pytest.mark.anyio
async def test_opus_writer_request_leaves_thinking_unset():
    fake = FakeAnthropic([script_json(user_turns=3)])
    await Claude(fake, writer=WRITERS["opus"]).make_script("길 묻기", get("other"))
    r = fake.requests[0]
    assert r["model"] == "claude-opus-5-5" and "thinking" not in r and r["output_config"]["effort"] == "low"


@pytest.mark.anyio
async def test_sonnet_quick_request():
    fake = FakeAnthropic([json.dumps({"request_ko": "카페에서 주문하는 상황으로 연습하고 싶어."})])
    await Claude(fake, quick=QUICKS["sonnet"]).recommend([], [], get("other"))
    r = fake.requests[0]
    assert r["model"] == "claude-sonnet-5-5" and r["thinking"] == {"type": "between_tools"}
    assert "effort" not in r["output_config"]


# --- wiring ---------------------------------------------------------------------------------------

def test_server_uses_and_logs_the_chosen_models(settings, caplog):
    from je_server.app import build_services

    caplog.set_level(logging.INFO, logger="je_server")
    claude = build_services(replace(settings, claude_writer="haiku", claude_quick="haiku")).engine.claude
    assert claude.writer is WRITERS["haiku"] and claude.quick is QUICKS["haiku"]
    assert "claude models: writer claude-haiku-5-5, quick claude-haiku-5-5" in caplog.text


def test_server_defaults_to_the_spec_models(settings):
    from je_server.app import build_services

    claude = build_services(settings).engine.claude
    assert claude.writer is SONNET and claude.quick is HAIKU
