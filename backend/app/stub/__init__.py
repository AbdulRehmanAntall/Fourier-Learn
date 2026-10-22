"""The Phase 2 stub: fake data behind the real API (docs/frontend.md §8).

Each later phase replaces the stub behind the endpoints it builds. When nothing uses the stub
any more, this package is deleted.
"""

from functools import lru_cache

from app.stub.fixtures import load_fixture_variants
from app.stub.store import StubStore


@lru_cache
def get_store() -> StubStore:
    return StubStore(load_fixture_variants())


def reset_store() -> None:
    """Forget every change and start again from the seed data (used by the tests)."""
    get_store.cache_clear()
