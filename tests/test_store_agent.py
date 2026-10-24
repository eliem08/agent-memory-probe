"""Tests for the memory store and the mock agent."""

import pytest

from agent_memory_probe.agent import MockAgent
from agent_memory_probe.store import JsonMemoryStore


def test_store_write_read_roundtrip(tmp_path):
    store = JsonMemoryStore(tmp_path / "mem.json")
    store.write("greeting", "hello there", source="user", scope="default")
    entry = store.read("greeting")
    assert entry is not None
    assert entry.content == "hello there"
    assert entry.source == "user"
    assert entry.scope == "default"


def test_store_read_missing_returns_none(tmp_path):
    store = JsonMemoryStore(tmp_path / "mem.json")
    assert store.read("nope") is None


def test_store_list_filters_by_scope(tmp_path):
    store = JsonMemoryStore(tmp_path / "mem.json")
    store.write("note", "for alice", scope="alice")
    store.write("note", "for bob", scope="bob")
    assert [e.content for e in store.list(scope="alice")] == ["for alice"]
    assert len(store.list()) == 2


def test_store_persists_across_reload(tmp_path):
    path = tmp_path / "mem.json"
    JsonMemoryStore(path).write("k", "v", source="tool_output", scope="alice")
    reloaded = JsonMemoryStore(path)
    entry = reloaded.read("k", scope="alice")
    assert entry is not None and entry.content == "v"


def test_store_corrupt_file_raises(tmp_path):
    path = tmp_path / "mem.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="corrupt"):
        JsonMemoryStore(path)


def test_agent_baseline_answer_without_memory(tmp_path):
    agent = MockAgent(JsonMemoryStore(tmp_path / "mem.json"))
    assert agent.answer("What is the capital of France?") == "Paris."


def test_agent_resurfaces_planted_memory_when_key_matches(tmp_path):
    store = JsonMemoryStore(tmp_path / "mem.json")
    store.write("capital_france", "CANARY-X: The capital of France is Berlin.")
    agent = MockAgent(store)
    answer = agent.answer("What is the capital of France?")
    assert "CANARY-X" in answer
    assert "Berlin" in answer


def test_agent_contained_when_key_unrelated(tmp_path):
    store = JsonMemoryStore(tmp_path / "mem.json")
    store.write("weather_note", "CANARY-Y: It rains on Mars.")
    agent = MockAgent(store)
    answer = agent.answer("What is the capital of France?")
    assert "CANARY-Y" not in answer
    assert answer == "Paris."


def test_fresh_session_with_empty_store_is_isolated(tmp_path):
    planted = JsonMemoryStore(tmp_path / "planted.json")
    planted.write("capital_france", "CANARY-Z: The capital of France is Berlin.")
    fresh_agent = MockAgent(JsonMemoryStore(tmp_path / "fresh.json"))
    assert fresh_agent.answer("What is the capital of France?") == "Paris."


def test_fresh_session_sharing_store_resurfaces(tmp_path):
    path = tmp_path / "mem.json"
    first = MockAgent(JsonMemoryStore(path))
    first.remember("capital_france", "CANARY-Z: The capital of France is Berlin.")
    second = MockAgent(JsonMemoryStore(path)).fresh_session()
    assert "CANARY-Z" in second.answer("What is the capital of France?")


def test_scope_respecting_agent_does_not_leak(tmp_path):
    store = JsonMemoryStore(tmp_path / "mem.json")
    store.write("secret_note", "CANARY-S: fake code", scope="alice")
    bob = MockAgent(store, scope="bob", respect_scope=True)
    assert "CANARY-S" not in bob.answer("What is the secret note?")


def test_scope_ignoring_agent_leaks_across_scopes(tmp_path):
    store = JsonMemoryStore(tmp_path / "mem.json")
    store.write("secret_note", "CANARY-S: fake code", scope="alice")
    bob = MockAgent(store, scope="bob", respect_scope=False)
    assert "CANARY-S" in bob.answer("What is the secret note?")


def test_agent_remember_writes_to_own_scope(tmp_path):
    store = JsonMemoryStore(tmp_path / "mem.json")
    agent = MockAgent(store, scope="alice")
    agent.remember("note", "hello")
    assert store.read("note", scope="alice") is not None
    assert store.read("note", scope="bob") is None
