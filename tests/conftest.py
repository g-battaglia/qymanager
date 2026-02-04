"""Test configuration and fixtures."""

import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    """Return path to fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture
def qy70_sysex_file(fixtures_dir):
    """Return path to QY70 SysEx test file."""
    return fixtures_dir / "QY70_SGT.syx"


@pytest.fixture
def q7p_file(fixtures_dir):
    """Return path to Q7P test file."""
    return fixtures_dir / "T01.Q7P"


@pytest.fixture
def q7p_empty_file(fixtures_dir):
    """Return path to empty/template Q7P file."""
    return fixtures_dir / "TXX.Q7P"


@pytest.fixture
def qy70_sysex_data(qy70_sysex_file):
    """Return raw bytes of QY70 SysEx file."""
    with open(qy70_sysex_file, "rb") as f:
        return f.read()


@pytest.fixture
def q7p_data(q7p_file):
    """Return raw bytes of Q7P file."""
    with open(q7p_file, "rb") as f:
        return f.read()
