"""Prompt store: Langfuse source with per-group fallback to config/prompts.yaml. No network, no langfuse install."""

import sys
import types
from types import SimpleNamespace

import pytest

from app.agent import prompt_store


class FakeClient:
    def __init__(self, prompts: dict, fail: set[str] = frozenset()):
        self.prompts = prompts
        self.fail = set(fail)

    def get_prompt(self, name, type="text", label=None):
        if name in self.fail:
            raise RuntimeError("boom")
        return SimpleNamespace(prompt=self.prompts[name])


@pytest.fixture
def langfuse_source(monkeypatch):
    settings = SimpleNamespace(prompt_source="langfuse", prompt_label="production")
    monkeypatch.setattr(prompt_store, "get_settings", lambda: settings)
    return settings


def _install_fake_langfuse(monkeypatch, client):
    module = types.ModuleType("langfuse")
    module.get_client = lambda: client
    monkeypatch.setitem(sys.modules, "langfuse", module)


REMOTE = {
    "finrag-planner": [
        {"role": "system", "content": "remote planner {{today}}"},
        {"role": "user", "content": "remote user {{question}}"},
    ],
    "finrag-final": [
        {"role": "system", "content": "remote final"},
        {"role": "user", "content": "remote final user {{question}}"},
    ],
    "finrag-repair": "remote repair {{errors}}",
}


def test_file_source_returns_yaml_defaults(monkeypatch):
    monkeypatch.setattr(prompt_store, "get_settings", lambda: SimpleNamespace(prompt_source="file"))
    prompts = prompt_store.get_prompts()
    assert set(prompts) == set(prompt_store.PROMPT_NAMES)
    assert prompts == prompt_store.default_prompts()


def test_langfuse_source_overrides_all_groups_and_converts_placeholders(monkeypatch, langfuse_source):
    _install_fake_langfuse(monkeypatch, FakeClient(REMOTE))
    prompts = prompt_store.get_prompts()
    assert prompts["planner_system"] == "remote planner {today}"
    assert prompts["planner_user"] == "remote user {question}"
    assert prompts["final_user"] == "remote final user {question}"
    assert prompts["repair"] == "remote repair {errors}"


def test_failed_group_falls_back_to_yaml_only_for_that_group(monkeypatch, langfuse_source):
    _install_fake_langfuse(monkeypatch, FakeClient(REMOTE, fail={"finrag-final"}))
    prompts = prompt_store.get_prompts()
    defaults = prompt_store.default_prompts()
    assert prompts["final_system"] == defaults["final_system"]
    assert prompts["final_user"] == defaults["final_user"]
    assert prompts["planner_system"] == "remote planner {today}"


def test_empty_remote_content_falls_back(monkeypatch, langfuse_source):
    remote = {**REMOTE, "finrag-repair": "   "}
    _install_fake_langfuse(monkeypatch, FakeClient(remote))
    assert prompt_store.get_prompts()["repair"] == prompt_store.default_prompts()["repair"]


def test_missing_langfuse_package_falls_back_to_yaml(monkeypatch, langfuse_source):
    monkeypatch.setitem(sys.modules, "langfuse", None)  # import raises ImportError
    assert prompt_store.get_prompts() == prompt_store.default_prompts()
