"""
Unit Tests for Database Integrity & Schema Rules.
"""

import sqlite3
import pytest
from database.db import get_db_connection, init_database
from generator.synthetic_generator import SyntheticDataGenerator
from scripts.run_validation import ValidationSuite


@pytest.fixture(scope="module")
def validated_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    with open("database/schema.sql", "r", encoding="utf-8") as f:
        conn.executescript(f.read())

    gen = SyntheticDataGenerator(seed=20261022, profile_name="starter")
    gen.generate_all()
    gen.export_to_sqlite(conn)

    yield conn
    conn.close()


def test_full_validation_suite_passes(validated_db):
    suite = ValidationSuite(validated_db)
    res = suite.run_all()
    assert res["all_passed"] is True
    assert res["failed"] == 0
    assert res["total_checks"] >= 40
