"""Settings validation (spec.md §3.1).

Direct construction, no HTTP — prior art: `test_engine_listeners.py`.

`session_ttl_days` is `Field(30, ge=0)`. `0` is legal and meaningful: it issues an
instantly-expired token, which is how `test_auth.py` exercises the expiry branch
without reaching into the database. A negative value is nonsense — it would issue
tokens that are already dead — so it fails at `Settings` construction rather than
at the first login.
"""

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_session_ttl_days_defaults_to_30() -> None:
    assert Settings(database_url="sqlite://").session_ttl_days == 30


def test_session_ttl_days_zero_is_accepted() -> None:
    """`0` is legal: an instantly-expired token."""
    assert Settings(database_url="sqlite://", session_ttl_days=0).session_ttl_days == 0


def test_session_ttl_days_negative_raises_validation_error() -> None:
    with pytest.raises(ValidationError) as excinfo:
        Settings(database_url="sqlite://", session_ttl_days=-1)
    assert "session_ttl_days" in str(excinfo.value)
