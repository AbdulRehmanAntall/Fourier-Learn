"""The tables must match the data dictionary of the report (Table 4.8).

Every entity and attribute of Table 4.8 is there, first and in order, with its type, length and
nullability. The additions the design needs (docs/PLAN.md §13, gap 3) come after them, and only
those listed in ADDITIONS are allowed, so nothing is added without being documented.
"""

import pytest
from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, Numeric, SmallInteger, String, Text

from app.db import Base

# Entity: {attribute: (type, length or precision, nullable)} from Table 4.8.
DATA_DICTIONARY = {
    "student": {
        "student_id": (Integer, None, False),
        "name": (String, 100, False),
        "email": (String, 254, False),
        "password_hash": (String, 255, False),
        "created_at": (DateTime, None, False),
    },
    "concept": {
        "concept_id": (Integer, None, False),
        "name": (String, 100, False),
        "syllabus_code": (String, 20, False),
        "topic_area": (String, 50, False),
    },
    "confidence_record": {
        "record_id": (Integer, None, False),
        "student_id": (Integer, None, False),
        "concept_id": (Integer, None, False),
        "score": (Numeric, (4, 3), False),
        "updated_at": (DateTime, None, False),
    },
    "lesson": {
        "lesson_id": (Integer, None, False),
        "student_id": (Integer, None, False),
        "query_text": (Text, None, False),
        "started_at": (DateTime, None, False),
        "status": (String, 20, False),
    },
    "module": {
        "module_id": (Integer, None, False),
        "lesson_id": (Integer, None, False),
        "concept_id": (Integer, None, False),
        "sequence_no": (Integer, None, False),
        "difficulty_level": (String, 15, False),
        "style": (String, 20, False),
        "video_path": (String, 255, True),
        "render_status": (String, 20, False),
    },
    "interaction_event": {
        "event_id": (Integer, None, False),
        "module_id": (Integer, None, False),
        "student_id": (Integer, None, False),
        "event_type": (String, 25, False),
        "occurred_at": (DateTime, None, False),
    },
    "check_question": {
        "check_id": (Integer, None, False),
        "concept_id": (Integer, None, False),
        "question_text": (Text, None, False),
        "correct_option": (String, 100, False),
    },
    "check_response": {
        "response_id": (Integer, None, False),
        "check_id": (Integer, None, False),
        "module_id": (Integer, None, False),
        "student_id": (Integer, None, False),
        "selected_option": (String, 100, False),
        "is_correct": (Boolean, None, False),
        "answered_at": (DateTime, None, False),
    },
    "glossary_term": {
        "term_id": (Integer, None, False),
        "concept_id": (Integer, None, False),
        "term": (String, 60, False),
        "definition": (Text, None, False),
    },
}


# Additions to Table 4.8 (PLAN §13, gap 3): columns after an entity's own, and extra tables.
ADDITIONS = {
    "lesson": {
        "title": (String, 200, False),
        "mode": (String, 10, False),
        "position": (JSON, None, True),
    },
    "module": {
        "title": (String, 200, False),
        "scene_plan": (JSON, None, True),
        "render_requests": (JSON, None, True),
        "cache_key": (String, 64, True),
        "completed_at": (DateTime, None, True),
    },
    "interaction_event": {
        "beat_index": (Integer, None, True),
        "position_s": (Float, None, True),
        "payload": (JSON, None, True),
    },
    "check_question": {
        "item_type": (String, 10, False),
        "options": (JSON, None, True),
    },
    "concept_prerequisite": {
        "concept_id": (Integer, None, False),
        "prerequisite_id": (Integer, None, False),
    },
    "variant": {
        "cache_key": (String, 64, False),
        "level": (SmallInteger, None, False),
        "voice": (String, 100, False),
        "library_version": (String, 20, False),
        "beat_count": (Integer, None, False),
        "duration_s": (Float, None, False),
        "created_at": (DateTime, None, False),
    },
    "render_job": {
        "job_id": (Integer, None, False),
        "module_id": (Integer, None, False),
        "lesson_id": (Integer, None, False),
        "cache_key": (String, 64, False),
        "level": (SmallInteger, None, False),
        "priority": (SmallInteger, None, False),
        "status": (String, 20, False),
        "attempts": (Integer, None, False),
        "request": (JSON, None, False),
        "worker": (String, 100, True),
        "error": (Text, None, True),
        "log": (Text, None, False),
        "created_at": (DateTime, None, False),
        "started_at": (DateTime, None, True),
        "finished_at": (DateTime, None, True),
        "duration_s": (Float, None, True),
    },
    "stream_event": {
        "event_id": (Integer, None, False),
        "lesson_id": (Integer, None, False),
        "payload": (JSON, None, False),
        "created_at": (DateTime, None, False),
    },
}


def _expected(table_name: str) -> dict:
    return DATA_DICTIONARY.get(table_name, {}) | ADDITIONS.get(table_name, {})


def test_every_entity_and_only_documented_tables():
    assert set(DATA_DICTIONARY) <= set(Base.metadata.tables)
    assert set(Base.metadata.tables) == set(DATA_DICTIONARY) | set(ADDITIONS)


@pytest.mark.parametrize("table_name", sorted(set(DATA_DICTIONARY) | set(ADDITIONS)))
def test_attributes_types_and_nullability(table_name):
    table = Base.metadata.tables[table_name]
    expected = _expected(table_name)
    # Table 4.8's own attributes first and in order, then the additions.
    assert list(table.columns.keys()) == list(expected)
    for column_name, (kind, size, nullable) in expected.items():
        column = table.columns[column_name]
        assert isinstance(column.type, kind), column_name
        assert column.nullable is nullable, column_name
        if kind is String:
            assert column.type.length == size, column_name
        if kind is Numeric:
            assert (column.type.precision, column.type.scale) == size
        if kind is DateTime:
            assert column.type.timezone


def test_primary_keys_are_the_first_attribute():
    for name, table in Base.metadata.tables.items():
        if name == "concept_prerequisite":  # an edge: both ends together
            assert [c.name for c in table.primary_key] == ["concept_id", "prerequisite_id"]
            continue
        assert [c.name for c in table.primary_key] == [next(iter(_expected(name)))]
