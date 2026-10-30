"""
Unit Tests for Deterministic Seed Reproducibility.
"""

import pytest
from scripts.verify_reproducibility import verify_reproducibility


def test_seed_reproducibility():
    is_reproducible = verify_reproducibility(seed=20261022, profile="starter")
    assert is_reproducible is True
