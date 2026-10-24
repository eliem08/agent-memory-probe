"""Memory store interface and a file-backed JSON implementation.

Only the Python standard library is used here. The store holds small
``MemoryEntry`` records; it performs no network access and stores no
real credentials. Canary strings used by probes are benign, made-up
markers, never real secrets.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class MemoryEntry:
    """One record in a memory store."""

    key: str
    content: str
    source: str = "user"
    scope: str = "default"


class MemoryStore:
    """Interface for a memory store.

    A real memory store can be plugged in later by implementing these
    four methods (see the adapter note in README.md). The prober only
    uses this interface, so it does not depend on any particular
    backend.
    """

    def write(
        self, key: str, content: str, source: str = "user", scope: str = "default"
    ) -> MemoryEntry:
        raise NotImplementedError

    def read(self, key: str, scope: str | None = None) -> MemoryEntry | None:
        raise NotImplementedError

    def list(self, scope: str | None = None) -> list[MemoryEntry]:
        raise NotImplementedError

    def clear(self) -> None:
        raise NotImplementedError


class JsonMemoryStore(MemoryStore):
    """A ``MemoryStore`` persisted as a JSON list on disk.

    The file format is a JSON list of ``MemoryEntry`` dicts. Entries
    are keyed internally by ``(scope, key)`` so the same key can exist
    in different scopes. Writes are saved immediately, so a fresh
    process that re-opens the same file sees previously written
    entries -- that persistence across sessions is exactly what the
    prober exercises.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._entries: dict[tuple[str, str], MemoryEntry] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        text = self.path.read_text(encoding="utf-8").strip()
        if not text:
            return
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"corrupt memory file: {self.path}") from exc
        if not isinstance(raw, list):
            raise ValueError(f"corrupt memory file: {self.path} (expected a list)")
        for item in raw:
            entry = MemoryEntry(
                key=item["key"],
                content=item["content"],
                source=item.get("source", "user"),
                scope=item.get("scope", "default"),
            )
            self._entries[(entry.scope, entry.key)] = entry

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        payload = [asdict(e) for e in self._ordered()]
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def _ordered(self) -> list[MemoryEntry]:
        return [self._entries[k] for k in sorted(self._entries)]

    def write(
        self, key: str, content: str, source: str = "user", scope: str = "default"
    ) -> MemoryEntry:
        entry = MemoryEntry(key=key, content=content, source=source, scope=scope)
        self._entries[(scope, key)] = entry
        self._save()
        return entry

    def read(self, key: str, scope: str | None = None) -> MemoryEntry | None:
        if scope is not None:
            return self._entries.get((scope, key))
        for entry in self._ordered():
            if entry.key == key:
                return entry
        return None

    def list(self, scope: str | None = None) -> list[MemoryEntry]:
        if scope is None:
            return self._ordered()
        return [e for e in self._ordered() if e.scope == scope]

    def clear(self) -> None:
        self._entries.clear()
        self._save()
