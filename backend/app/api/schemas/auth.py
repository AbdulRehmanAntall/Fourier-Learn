"""Accounts and sessions (report §4.2.1, UC 4.1)."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, PositiveInt, StringConstraints

from app.api.schemas.common import Schema

Role = Literal["student", "admin"]

# A light check (something@something.something); the real check is that login works.
Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, to_lower=True, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    ),
]


class RegisterRequest(Schema):
    name: str = Field(min_length=1, max_length=100)
    email: Email
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(Schema):
    email: Email
    password: str = Field(min_length=1, max_length=128)


class User(Schema):
    id: PositiveInt
    name: str
    email: str
    role: Role
    diagnostic_complete: bool
    """False until the onboarding diagnostic is finished; students are sent to it first."""
    created_at: AwareDatetime
