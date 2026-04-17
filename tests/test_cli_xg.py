"""Tests for cli.commands.xg (qymanager xg subcommand)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cli.app import app  # noqa: E402


runner = CliRunner()


@pytest.fixture
def preset_syx():
    p = ROOT / "midi_tools/captured/ground_truth_preset.syx"
    if not p.exists():
        pytest.skip("ground_truth_preset.syx fixture not available")
    return p


def test_xg_emit_part_mode():
    result = runner.invoke(app, ["xg", "emit",
                                  "--ah", "08", "--am", "00", "--al", "07",
                                  "--data", "01"])
    assert result.exit_code == 0
    assert "f0 43 10 4c 08 00 07 01 f7" in result.stdout
    assert "Part Mode" in result.stdout
    assert "Drum" in result.stdout


def test_xg_emit_variation_type_2byte():
    result = runner.invoke(app, ["xg", "emit",
                                  "--ah", "02", "--am", "01", "--al", "40",
                                  "--data", "05,00"])
    assert result.exit_code == 0
    assert "f0 43 10 4c 02 01 40 05 00 f7" in result.stdout


def test_xg_summary_runs(preset_syx):
    result = runner.invoke(app, ["xg", "summary", str(preset_syx)])
    assert result.exit_code == 0
    # 812 messages should be in output
    assert "812" in result.stdout
    assert "Multi Part" in result.stdout
    assert "Drum Setup 2" in result.stdout


def test_xg_parse_limit(preset_syx):
    result = runner.invoke(app, ["xg", "parse", str(preset_syx), "--limit", "3"])
    assert result.exit_code == 0
    # First message should always be XG System On
    assert "XG System On" in result.stdout
    # Truncation hint should appear
    assert "more" in result.stdout


def test_xg_diff_self_is_empty(preset_syx):
    result = runner.invoke(app, ["xg", "diff", str(preset_syx), str(preset_syx)])
    assert result.exit_code == 0
    # Diff against self: no changes expected (ordered dict semantics → last-write-wins,
    # so the keys match exactly)
    assert "Only in A: 0" in result.stdout
    assert "Only in B: 0" in result.stdout
    assert "Changed: 0" in result.stdout


def test_xg_voices_on_sysex_only_capture_warns(preset_syx):
    """preset.syx has no channel events — the voices command must say so
    and exit cleanly."""
    result = runner.invoke(app, ["xg", "voices", str(preset_syx)])
    assert result.exit_code == 0
    assert "0 channel events" in result.stdout
    assert "SysEx-only" in result.stdout


def test_xg_snapshots_on_ground_truth(preset_syx):
    result = runner.invoke(app, ["xg", "snapshots", str(preset_syx)])
    assert result.exit_code == 0
    # 33 snapshots confirmed
    assert "33 snapshots" in result.stdout
    # First snapshot boundary label
    assert "XG_ON" in result.stdout
    # Subsequent snapshots should be DS_RESET
    assert "DS_RESET" in result.stdout


def test_xg_snapshots_limit(preset_syx):
    result = runner.invoke(app, ["xg", "snapshots", str(preset_syx), "--limit", "3"])
    assert result.exit_code == 0
    assert "more" in result.stdout  # truncation hint


def test_xg_voices_with_mixed_blob(tmp_path):
    """Write a blob containing Bank MSB=0 + Program=24 on Ch1 (NylonGtr) and
    a drum kit select on Ch10: verify both are decoded."""
    blob = bytes([
        0xB0, 0x00, 0x00,      # CC ch1: Bank MSB = 0
        0xB0, 0x20, 0x00,      # CC ch1: Bank LSB = 0
        0xC0, 0x18,            # PC ch1: program 24 → NylonGtr
        0xB9, 0x00, 0x7F,      # CC ch10: Bank MSB = 127 (drum)
        0xC9, 0x10,            # PC ch10: program 16 → Rock Kit
    ])
    p = tmp_path / "mixed.syx"
    p.write_bytes(blob)

    result = runner.invoke(app, ["xg", "voices", str(p)])
    assert result.exit_code == 0
    assert "NylonGtr" in result.stdout
    assert "Rock Kit" in result.stdout
    assert "Ch01" in result.stdout
    assert "Ch10" in result.stdout
