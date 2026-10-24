"""The Phase 2 stub: fake data behind the real API (docs/frontend.md §8).

Each later phase replaces the stub behind the endpoints it builds. When nothing uses the stub
any more, this package is deleted.
"""

from functools import lru_cache

from app.stub.fixtures import load_fixture_variants
from app.stub.store import STUB_IDS_FROM, StubStore


@lru_cache
def get_store() -> StubStore:
    return StubStore(load_fixture_variants())


def reset_store() -> None:
    """Forget every change and start again from the seed data (used by the tests)."""
    get_store.cache_clear()


def is_stub_id(lesson_or_module_id: int) -> bool:
    """Whether a lesson or module id belongs to the stub rather than the database."""
    return lesson_or_module_id >= STUB_IDS_FROM


__all__ = ["STUB_IDS_FROM", "StubStore", "get_store", "is_stub_id", "reset_store"]
