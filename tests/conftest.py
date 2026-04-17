"""Test configuration and fixtures."""

import os

import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def pytest_collection_modifyitems(config, items):
    """Skip hardware tests unless QY_HARDWARE=1 is set in the environment."""
    if os.environ.get("QY_HARDWARE") == "1":
        return
    skip_hw = pytest.mark.skip(
        reason="hardware tests skipped (set QY_HARDWARE=1 to enable)"
    )
    for item in items:
        if "hardware" in item.keywords:
            item.add_marker(skip_hw)


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
