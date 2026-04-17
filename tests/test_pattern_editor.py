"""Tests for the Pipeline B pattern editor (midi_tools/pattern_editor.py)."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from midi_tools.quantizer import (
    QuantizedNote,
    QuantizedPattern,
    QuantizedTrack,
    dict_to_pattern,
    export_json,
    load_quantized_json,
    pattern_to_dict,
    quantize_capture,
)
from midi_tools.pattern_editor import (
    load_pattern,
    op_add_note,
    op_clear_bar,
    op_copy_bar,
    op_humanize_velocity,
    op_kit_remap,
    op_remove_notes,
    op_set_velocity,
    op_shift_time,
    op_transpose,
    save_pattern,
)


FIXTURES = Path(__file__).parent.parent / "midi_tools" / "captured"
SCAFFOLD_DECAY = Path(__file__).parent.parent / "data" / "q7p" / "DECAY.Q7P"


@pytest.fixture
def sgt_capture():
    path = FIXTURES / "sgt_full_capture.json"
    if not path.exists():
        pytest.skip("SGT capture fixture not present")
    return str(path)


@pytest.fixture
def sgt_pattern(sgt_capture):
    return quantize_capture(sgt_capture, bar_count=4)


class TestSerializationRoundtrip:

    def test_dict_roundtrip_preserves_notes(self, sgt_pattern):
        data = pattern_to_dict(sgt_pattern)
        restored = dict_to_pattern(data)
        assert restored.bpm == sgt_pattern.bpm
        assert restored.ppqn == sgt_pattern.ppqn
        assert restored.time_sig == sgt_pattern.time_sig
        assert restored.bar_count == sgt_pattern.bar_count
        assert set(restored.tracks.keys()) == set(sgt_pattern.tracks.keys())
        for idx in sgt_pattern.tracks:
            a = sgt_pattern.tracks[idx].notes
            b = restored.tracks[idx].notes
            assert len(a) == len(b)
            for na, nb in zip(a, b):
                assert na.note == nb.note
                assert na.velocity == nb.velocity
                assert na.bar == nb.bar
                assert na.beat == nb.beat
                assert na.tick_on == nb.tick_on
                assert na.tick_dur == nb.tick_dur

    def test_file_roundtrip(self, sgt_pattern, tmp_path):
        out = tmp_path / "pattern.json"
        export_json(sgt_pattern, str(out))
        restored = load_quantized_json(str(out))
        assert restored.bpm == sgt_pattern.bpm
        assert sum(len(t.notes) for t in restored.active_tracks) == \
            sum(len(t.notes) for t in sgt_pattern.active_tracks)

    def test_load_pattern_detects_capture_format(self, sgt_capture):
        p = load_pattern(sgt_capture)
        assert isinstance(p, QuantizedPattern)
        assert p.bpm > 0

    def test_load_pattern_detects_quantized_format(self, sgt_pattern, tmp_path):
        out = tmp_path / "pattern.json"
        export_json(sgt_pattern, str(out))
        p = load_pattern(str(out))
        assert isinstance(p, QuantizedPattern)
        assert p.bpm == sgt_pattern.bpm


class TestTranspose:

    def test_transpose_melody_up(self, sgt_pattern):
        melody = next(t for t in sgt_pattern.active_tracks if not t.is_drum)
        before = [n.note for n in melody.notes]
        moved = op_transpose(sgt_pattern, melody.track_idx, 2)
        after = [n.note for n in melody.notes]
        assert moved > 0
        for a, b in zip(before, after):
            assert b == a + 2

    def test_transpose_drum_rejected(self, sgt_pattern):
        drum = next(t for t in sgt_pattern.active_tracks if t.is_drum)
        with pytest.raises(ValueError, match="drum"):
            op_transpose(sgt_pattern, drum.track_idx, 2)

    def test_transpose_out_of_range_skipped(self, sgt_pattern):
        melody = next(t for t in sgt_pattern.active_tracks if not t.is_drum)
        # Huge upward shift → some notes should overflow and be skipped
        moved = op_transpose(sgt_pattern, melody.track_idx, 120)
        assert moved >= 0
        for n in melody.notes:
            assert 0 <= n.note <= 127


class TestAddRemove:

    def test_add_note_appears_sorted(self, sgt_pattern):
        t_idx = next(iter(sgt_pattern.tracks))
        before = len(sgt_pattern.tracks[t_idx].notes)
        op_add_note(sgt_pattern, t_idx, bar=0, beat=0, sub=0, note=60, velocity=90)
        assert len(sgt_pattern.tracks[t_idx].notes) == before + 1
        notes = sgt_pattern.tracks[t_idx].notes
        for i in range(1, len(notes)):
            prev, curr = notes[i - 1], notes[i]
            assert (curr.bar, curr.tick_on, curr.note) >= (prev.bar, prev.tick_on, prev.note)

    def test_add_note_creates_new_track(self, sgt_pattern):
        sgt_pattern.tracks.pop(7, None)
        op_add_note(sgt_pattern, track_idx=7, bar=0, beat=0, sub=0, note=64)
        assert 7 in sgt_pattern.tracks
        assert len(sgt_pattern.tracks[7].notes) == 1

    def test_add_note_rejects_bad_bar(self, sgt_pattern):
        with pytest.raises(ValueError, match="bar"):
            op_add_note(sgt_pattern, 0, bar=99, beat=0, sub=0, note=60)

    def test_remove_notes_by_bar(self, sgt_pattern):
        t_idx = next(iter(sgt_pattern.tracks))
        before = len(sgt_pattern.tracks[t_idx].notes)
        bar_0 = sum(1 for n in sgt_pattern.tracks[t_idx].notes if n.bar == 0)
        removed = op_remove_notes(sgt_pattern, t_idx, bar=0)
        assert removed == bar_0
        assert len(sgt_pattern.tracks[t_idx].notes) == before - bar_0
        for n in sgt_pattern.tracks[t_idx].notes:
            assert n.bar != 0


class TestSetVelocity:

    def test_set_velocity_all(self, sgt_pattern):
        t_idx = next(iter(sgt_pattern.tracks))
        changed = op_set_velocity(sgt_pattern, t_idx, velocity=77)
        assert changed == len(sgt_pattern.tracks[t_idx].notes)
        for n in sgt_pattern.tracks[t_idx].notes:
            assert n.velocity == 77

    def test_set_velocity_filtered_by_bar(self, sgt_pattern):
        t_idx = next(iter(sgt_pattern.tracks))
        bar_0 = [n for n in sgt_pattern.tracks[t_idx].notes if n.bar == 0]
        changed = op_set_velocity(sgt_pattern, t_idx, velocity=50, bar=0)
        assert changed == len(bar_0)
        for n in sgt_pattern.tracks[t_idx].notes:
            if n.bar == 0:
                assert n.velocity == 50


class TestShiftTime:

    def test_shift_forward_recomputes_bar(self, sgt_pattern):
        t_idx = next(iter(sgt_pattern.tracks))
        track = sgt_pattern.tracks[t_idx]
        before = [(n.bar, n.tick_on) for n in track.notes]
        # Shift by one bar (1920 ticks at PPQN=480)
        kept = op_shift_time(sgt_pattern, t_idx, 1920)
        # Notes from the last bar are dropped
        last_bar = sgt_pattern.bar_count - 1
        expected_kept = sum(1 for b, _ in before if b < last_bar)
        assert kept == expected_kept
        for n in track.notes:
            assert n.bar >= 1

    def test_shift_backward_drops_underflow(self, sgt_pattern):
        t_idx = next(iter(sgt_pattern.tracks))
        track = sgt_pattern.tracks[t_idx]
        before = len(track.notes)
        # Shift back by 10 bars → all notes dropped
        kept = op_shift_time(sgt_pattern, t_idx, -20 * 1920)
        assert kept == 0
        assert len(track.notes) == 0


class TestCopyBar:

    def test_copy_bar_replace(self, sgt_pattern):
        t_idx = next(iter(sgt_pattern.tracks))
        track = sgt_pattern.tracks[t_idx]
        bar_0 = [n for n in track.notes if n.bar == 0]
        copied = op_copy_bar(sgt_pattern, t_idx, src_bar=0, dst_bar=2, replace=True)
        assert copied == len(bar_0)
        bar_2 = [n for n in track.notes if n.bar == 2]
        assert len(bar_2) == len(bar_0)
        # Notes in bar 2 should match bar 0 structure
        sig_src = sorted((n.tick_on, n.note) for n in bar_0)
        sig_dst = sorted((n.tick_on, n.note) for n in bar_2)
        assert sig_src == sig_dst

    def test_copy_bar_same_src_dst_noop(self, sgt_pattern):
        t_idx = next(iter(sgt_pattern.tracks))
        copied = op_copy_bar(sgt_pattern, t_idx, src_bar=0, dst_bar=0)
        assert copied == 0


class TestClearBar:

    def test_clear_bar_removes_all(self, sgt_pattern):
        t_idx = next(iter(sgt_pattern.tracks))
        track = sgt_pattern.tracks[t_idx]
        bar_count = sum(1 for n in track.notes if n.bar == 1)
        removed = op_clear_bar(sgt_pattern, t_idx, bar=1)
        assert removed == bar_count
        for n in track.notes:
            assert n.bar != 1


class TestKitRemap:

    def test_kit_remap_drum(self, sgt_pattern):
        drum = next(t for t in sgt_pattern.active_tracks if t.is_drum)
        # Pick the most common note in the track
        from collections import Counter
        top = Counter(n.note for n in drum.notes).most_common(1)[0][0]
        count_before = sum(1 for n in drum.notes if n.note == top)
        remapped = op_kit_remap(sgt_pattern, drum.track_idx, src_note=top, dst_note=99)
        assert remapped == count_before
        assert all(n.note != top or False for n in drum.notes if n.note == 99)

    def test_kit_remap_melody_rejected(self, sgt_pattern):
        melody = next(t for t in sgt_pattern.active_tracks if not t.is_drum)
        with pytest.raises(ValueError, match="drum"):
            op_kit_remap(sgt_pattern, melody.track_idx, src_note=60, dst_note=62)


class TestHumanize:

    def test_humanize_deterministic(self, sgt_pattern):
        t_idx = next(iter(sgt_pattern.tracks))
        before = [n.velocity for n in sgt_pattern.tracks[t_idx].notes]
        op_humanize_velocity(sgt_pattern, t_idx, amount=5, seed=42)
        after = [n.velocity for n in sgt_pattern.tracks[t_idx].notes]
        for a, b in zip(before, after):
            assert abs(a - b) <= 5
            assert 1 <= b <= 127

    def test_humanize_zero_is_noop(self, sgt_pattern):
        t_idx = next(iter(sgt_pattern.tracks))
        before = [n.velocity for n in sgt_pattern.tracks[t_idx].notes]
        op_humanize_velocity(sgt_pattern, t_idx, amount=0, seed=1)
        after = [n.velocity for n in sgt_pattern.tracks[t_idx].notes]
        assert before == after


class TestEndToEndEdit:

    def test_edit_and_build_q7p(self, sgt_pattern, tmp_path):
        if not SCAFFOLD_DECAY.exists():
            pytest.skip("DECAY.Q7P scaffold not present")

        from midi_tools.build_q7p_5120 import build_q7p, validate_q7p

        json_path = tmp_path / "edited.json"
        export_json(sgt_pattern, str(json_path))

        reloaded = load_quantized_json(str(json_path))
        melody = next(t for t in reloaded.active_tracks if not t.is_drum)
        op_transpose(reloaded, melody.track_idx, 1)

        q7p_data = build_q7p(reloaded, str(SCAFFOLD_DECAY))
        assert len(q7p_data) == 5120

        with open(SCAFFOLD_DECAY, "rb") as f:
            scaffold_bytes = f.read()
        warnings = validate_q7p(q7p_data, scaffold=scaffold_bytes)
        assert len(warnings) == 0, f"Validator warnings: {warnings}"

    def test_cli_export_and_build(self, sgt_capture, tmp_path):
        if not SCAFFOLD_DECAY.exists():
            pytest.skip("DECAY.Q7P scaffold not present")

        from midi_tools.pattern_editor import main

        json_path = tmp_path / "pattern.json"
        rc = main(["export", sgt_capture, "-o", str(json_path)])
        assert rc == 0
        assert json_path.exists()

        with open(json_path) as f:
            data = json.load(f)
        assert "bpm" in data and "tracks" in data

        out_prefix = tmp_path / "built"
        rc = main([
            "build", str(json_path),
            "-o", str(out_prefix),
            "--scaffold", str(SCAFFOLD_DECAY),
        ])
        assert rc == 0
        assert (tmp_path / "built.Q7P").exists()
        assert (tmp_path / "built.mid").exists()
        assert (tmp_path / "built.Q7P").stat().st_size == 5120
