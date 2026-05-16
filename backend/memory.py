"""In-process session memory (BE-12).

Per the PRD: keep this simple. We store the last regimen and the syntheses
keyed by pair so follow-up queries only re-evaluate the delta.

Single-process dict-based store, no persistence across restarts. Sessions
are keyed by an opaque session_id chosen by the caller (FastAPI uses a
cookie / header; the demo UI sends one explicit value).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Iterable

from backend.schemas import NormalizedDrug, SynthesizedInteraction


@dataclass
class SessionMemory:
    session_id: str
    regimen: list[NormalizedDrug] = field(default_factory=list)
    # key = sorted(pair); value = full SynthesizedInteraction
    syntheses: dict[tuple[str, str], SynthesizedInteraction] = field(default_factory=dict)

    def set_regimen(self, regimen: list[NormalizedDrug]) -> None:
        self.regimen = list(regimen)

    def store_many(self, syntheses: Iterable[SynthesizedInteraction]) -> None:
        for s in syntheses:
            self.syntheses[tuple(sorted(s.drug_pair))] = s

    def partition(
        self, pairs: list[tuple[str, str]]
    ) -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[SynthesizedInteraction]]:
        """Split `pairs` into (new, cached, cached_syntheses)."""
        new_pairs: list[tuple[str, str]] = []
        cached_pairs: list[tuple[str, str]] = []
        cached_syntheses: list[SynthesizedInteraction] = []
        for p in pairs:
            key = tuple(sorted(p))
            if key in self.syntheses:
                cached_pairs.append(p)
                cached_syntheses.append(self.syntheses[key])
            else:
                new_pairs.append(p)
        return new_pairs, cached_pairs, cached_syntheses


_lock = threading.Lock()
_STORE: dict[str, SessionMemory] = {}


def memory_for(session_id: str) -> SessionMemory:
    with _lock:
        mem = _STORE.get(session_id)
        if mem is None:
            mem = SessionMemory(session_id=session_id)
            _STORE[session_id] = mem
        return mem


def reset(session_id: str) -> None:
    """Used by tests and by the API for explicit session wipes."""
    with _lock:
        _STORE.pop(session_id, None)
