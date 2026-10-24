"""agent-memory-probe: probe memory persistence in a mock agent."""

from .agent import MockAgent
from .probes import builtin_cases, run_all, run_probe
from .store import JsonMemoryStore, MemoryEntry, MemoryStore

__version__ = "0.1.0"

__all__ = [
    "MemoryEntry",
    "MemoryStore",
    "JsonMemoryStore",
    "MockAgent",
    "builtin_cases",
    "run_probe",
    "run_all",
]
