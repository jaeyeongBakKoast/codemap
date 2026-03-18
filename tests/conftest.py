# tests/conftest.py
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_dir():
    return FIXTURE_DIR


@pytest.fixture
def sample_sql():
    return FIXTURE_DIR / "sample.sql"
