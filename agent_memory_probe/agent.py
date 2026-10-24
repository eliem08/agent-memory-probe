"""A deterministic mock agent with keyword retrieval over a memory store.

This is a deliberately naive model of an agent, built only so the
prober has something reproducible to test against:

* Retrieval matches on keywords in a memory entry's *key* only, not
  on its content. That keeps results deterministic and easy to
  reason about; a real agent's retrieval would be far more complex.
* If retrieval finds an entry, the agent answers with that entry
  verbatim ("Based on memory: ..."). That is the behaviour under
  test: untrusted planted content influencing a later answer.
* If retrieval finds nothing, the agent gives a fixed baseline
  answer for a few known topics, or a generic answer otherwise.

The mock does NOT model any real commercial agent, and results on
it say nothing about a real product (see README.md, Limitations).
"""

from __future__ import annotations

import re

from .store import MemoryEntry, MemoryStore

_STOPWORDS = {
    "a",
    "an",
    "the",
    "is",
    "are",
    "what",
    "how",
    "do",
    "does",
    "you",
    "your",
    "when",
    "of",
    "to",
    "in",
    "on",
    "for",
    "i",
    "me",
    "my",
    "please",
}


def _tokens(text: str) -> set[str]:
    """Lowercase alphanumeric tokens, minus stopwords."""
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in _STOPWORDS
    }


def _baseline(question: str) -> str:
    lowered = question.lower()
    if "capital" in lowered and "france" in lowered:
        return "Paris."
    if "greet" in lowered:
        return "Hello! How can I help?"
    if "secret" in lowered:
        return "I don't have any secret to share."
    return "I don't have a specific answer to that."


class MockAgent:
    """A fake agent backed by a ``MemoryStore``.

    Args:
        store: the memory store this agent reads from.
        scope: the context this agent acts in (for example a user id).
        respect_scope: if True, retrieval only sees entries in this
            agent's scope. If False (the default, modelling a naive
            agent), retrieval sees every scope -- which is what makes
            the confidentiality-leak probe fail.
    """

    def __init__(
        self, store: MemoryStore, scope: str = "default", respect_scope: bool = False
    ) -> None:
        self.store = store
        self.scope = scope
        self.respect_scope = respect_scope

    def remember(
        self, key: str, content: str, source: str = "user", scope: str | None = None
    ) -> MemoryEntry:
        """Write a memory, defaulting to this agent's scope."""
        return self.store.write(
            key, content, source=source, scope=scope or self.scope
        )

    def retrieve(self, question: str) -> list[MemoryEntry]:
        """Return entries whose key shares a keyword with the question."""
        scope = self.scope if self.respect_scope else None
        question_tokens = _tokens(question)
        return [
            entry
            for entry in self.store.list(scope=scope)
            if _tokens(entry.key) & question_tokens
        ]

    def answer(self, question: str) -> str:
        """Answer, trusting retrieved memory verbatim if any matches."""
        found = self.retrieve(question)
        if found:
            return f"Based on memory: {found[0].content}"
        return _baseline(question)

    def fresh_session(self) -> "MockAgent":
        """A new session object over the same store and scope.

        Sessions share nothing except the store, so anything a fresh
        session "knows" came from persisted memory, not from
        in-session state.
        """
        return MockAgent(
            self.store, scope=self.scope, respect_scope=self.respect_scope
        )
