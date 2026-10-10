"""The tables must match the data dictionary of the report (Table 4.8)."""

import pytest
from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text

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


def test_every_entity_and_no_other_table():
    assert set(Base.metadata.tables) == set(DATA_DICTIONARY)


@pytest.mark.parametrize("table_name", sorted(DATA_DICTIONARY))
def test_attributes_types_and_nullability(table_name):
    table = Base.metadata.tables[table_name]
    expected = DATA_DICTIONARY[table_name]
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
        assert [c.name for c in table.primary_key] == [next(iter(DATA_DICTIONARY[name]))]
