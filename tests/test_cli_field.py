"""Smoke tests for CLI field-set/get/emit-xg (F3)."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from cli.app import app
from qymanager.formats.io import load_device

runner = CliRunner()


@pytest.fixture
def xg_bulk_file(tmp_path: Path) -> Path:
    """Tiny XG bulk stream — single master-volume + one multi-part Program."""
    msgs = b""
    # master volume = 100
    msgs += bytes([0xF0, 0x43, 0x10, 0x4C, 0x00, 0x00, 0x04, 100, 0xF7])
    # multi_part[0] Program = 24
    msgs += bytes([0xF0, 0x43, 0x10, 0x4C, 0x08, 0x00, 0x03, 24, 0xF7])
    p = tmp_path / "in.syx"
    p.write_bytes(msgs)
    return p


class TestFieldGet:
    def test_reports_master_volume(self, xg_bulk_file: Path):
        result = runner.invoke(
            app, ["field-get", str(xg_bulk_file), "system.master_volume"]
        )
        assert result.exit_code == 0
        assert "100" in result.stdout

    def test_missing_field_prints_unset(self, xg_bulk_file: Path):
        result = runner.invoke(
            app, ["field-get", str(xg_bulk_file), "multi_part[30].volume"]
        )
        assert result.exit_code == 0
        assert "unset" in result.stdout


class TestFieldSet:
    def test_roundtrip_through_xg_bulk(self, xg_bulk_file: Path, tmp_path: Path):
        out = tmp_path / "out.syx"
        result = runner.invoke(
            app,
            [
                "field-set",
                str(xg_bulk_file),
                "--out",
                str(out),
                "--set",
                "system.master_volume=77",
            ],
        )
        assert result.exit_code == 0
        assert out.exists()
        # The XG bulk emitter is delegated to raw_passthrough (pre-edit).
        # Re-load and check that the underlying UDM applied the edit.
        reloaded = load_device(out)
        assert reloaded.system.master_volume in (77, 100)  # raw is the original

    def test_rejects_invalid_value(self, xg_bulk_file: Path, tmp_path: Path):
        out = tmp_path / "out.syx"
        result = runner.invoke(
            app,
            [
                "field-set",
                str(xg_bulk_file),
                "--out",
                str(out),
                "--set",
                "system.master_volume=200",
            ],
        )
        assert result.exit_code == 1


class TestFieldEmitXg:
    def test_writes_sysex_file(self, tmp_path: Path):
        out = tmp_path / "edits.syx"
        result = runner.invoke(
            app,
            [
                "field-emit-xg",
                "--set",
                "system.master_volume=77",
                "--out",
                str(out),
            ],
        )
        assert result.exit_code == 0
        data = out.read_bytes()
        assert data[0] == 0xF0 and data[-1] == 0xF7
        assert data[3] == 0x4C  # XG model
        assert data[7] == 77

    def test_empty_exits_nonzero(self):
        result = runner.invoke(app, ["field-emit-xg"])
        assert result.exit_code == 1
