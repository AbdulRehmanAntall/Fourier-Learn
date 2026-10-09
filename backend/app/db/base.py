"""Declarative Base for ORM models. No models exist yet.

Future model modules should be imported in app/db/__init__.py so Alembic sees them.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
