"""Smoke tests for structured CLI commands (F4)."""

from __future__ import annotations

import io
from pathlib import Path

import mido
import pytest
from typer.testing import CliRunner

from cli.app import app

runner = CliRunner()


@pytest.fixture
def tiny_mid(tmp_path: Path) -> Path:
    mid = mido.MidiFile(type=1, ticks_per_beat=480)
    conductor = mido.MidiTrack()
    conductor.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
    conductor.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    conductor.append(mido.MetaMessage("track_name", name="ORIG", time=0))
    mid.tracks.append(conductor)
    track = mido.MidiTrack()
    track.append(mido.Message("note_on", channel=0, note=60, velocity=100, time=0))
    track.append(mido.Message("note_off", channel=0, note=60, velocity=64, time=480))
    mid.tracks.append(track)
    buf = io.BytesIO()
    mid.save(file=buf)
    path = tmp_path / "tiny.mid"
    path.write_bytes(buf.getvalue())
    return path


class TestSongCommands:
    def test_song_list(self, tiny_mid: Path):
        r = runner.invoke(app, ["song-list", str(tiny_mid)])
        assert r.exit_code == 0
        assert "ORIG" in r.stdout

    def test_song_set(self, tiny_mid: Path, tmp_path: Path):
        out = tmp_path / "out.mid"
        r = runner.invoke(
            app,
            [
                "song-set",
                str(tiny_mid),
                "--out",
                str(out),
                "--name",
                "NEW",
                "--tempo",
                "100.0",
            ],
        )
        assert r.exit_code == 0
        assert out.exists()
        r2 = runner.invoke(app, ["song-list", str(out)])
        assert "NEW" in r2.stdout


class TestPatternCommands:
    def test_pattern_list_q7p(self):
        q7p = Path("data/q7p/SGT.Q7P")
        if not q7p.exists():
            pytest.skip("no SGT.Q7P fixture present")
        r = runner.invoke(app, ["pattern-list", str(q7p)])
        assert r.exit_code == 0
        assert "SGT" in r.stdout or "UNK" in r.stdout

    def test_pattern_list_no_songs_error(self, tmp_path: Path):
        empty = tmp_path / "empty.q7p"
        empty.write_bytes(b"\x00" * 3072)
        # Just checking the command doesn't crash even on junk input
        r = runner.invoke(app, ["pattern-list", str(empty)])
        # Validator may complain but CLI should still return
        assert r.exit_code in (0, 1)
