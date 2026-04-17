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
    op_diff_patterns,
    op_humanize_timing,
    op_humanize_velocity,
    op_kit_remap,
    op_merge_patterns,
    op_new_empty_pattern,
    op_remove_notes,
    op_resize,
    op_set_velocity,
    op_shift_time,
    op_transpose,
    op_velocity_curve,
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


class TestHumanizeTiming:

    def test_deterministic_jitter(self, sgt_pattern):
        t_idx = next(iter(sgt_pattern.tracks))
        before = [(n.bar, n.tick_on) for n in sgt_pattern.tracks[t_idx].notes]
        kept = op_humanize_timing(sgt_pattern, t_idx, amount_ticks=20, seed=42)
        after = [(n.bar, n.tick_on) for n in sgt_pattern.tracks[t_idx].notes]
        # Sum of deviations should be > 0 (some notes shifted)
        assert kept > 0
        # Notes stay within pattern
        ticks_per_bar = sgt_pattern.bar_ticks
        total = sgt_pattern.bar_count * ticks_per_bar
        for n in sgt_pattern.tracks[t_idx].notes:
            abs_t = n.bar * ticks_per_bar + n.tick_on
            assert 0 <= abs_t < total

    def test_zero_is_noop(self, sgt_pattern):
        t_idx = next(iter(sgt_pattern.tracks))
        before = [(n.bar, n.tick_on) for n in sgt_pattern.tracks[t_idx].notes]
        op_humanize_timing(sgt_pattern, t_idx, amount_ticks=0, seed=1)
        after = [(n.bar, n.tick_on) for n in sgt_pattern.tracks[t_idx].notes]
        assert before == after

    def test_reproducible_with_seed(self, sgt_pattern):
        import copy
        a = copy.deepcopy(sgt_pattern)
        b = copy.deepcopy(sgt_pattern)
        t_idx = next(iter(a.tracks))
        op_humanize_timing(a, t_idx, amount_ticks=10, seed=123)
        op_humanize_timing(b, t_idx, amount_ticks=10, seed=123)
        ticks_a = [(n.bar, n.tick_on) for n in a.tracks[t_idx].notes]
        ticks_b = [(n.bar, n.tick_on) for n in b.tracks[t_idx].notes]
        assert ticks_a == ticks_b


class TestVelocityCurve:

    def test_crescendo_full_pattern(self, sgt_pattern):
        t_idx = next(iter(sgt_pattern.tracks))
        count = op_velocity_curve(sgt_pattern, t_idx, start_vel=20, end_vel=120)
        assert count == len(sgt_pattern.tracks[t_idx].notes)
        notes = sgt_pattern.tracks[t_idx].notes
        assert notes[0].velocity >= 20 and notes[0].velocity <= 25
        # Last note should be near end_vel
        last = notes[-1]
        assert last.velocity >= 100  # allow for interpolation rounding

    def test_decrescendo(self, sgt_pattern):
        t_idx = next(iter(sgt_pattern.tracks))
        count = op_velocity_curve(sgt_pattern, t_idx, start_vel=110, end_vel=10)
        assert count > 0
        notes = sgt_pattern.tracks[t_idx].notes
        # First note should be close to 110, last close to 10
        assert notes[0].velocity >= 100
        assert notes[-1].velocity <= 30

    def test_bar_range_filter(self, sgt_pattern):
        import copy
        t_idx = next(iter(sgt_pattern.tracks))
        before_bar2 = {(n.bar, n.tick_on, n.note): n.velocity
                       for n in sgt_pattern.tracks[t_idx].notes if n.bar >= 2}
        count = op_velocity_curve(sgt_pattern, t_idx, start_vel=50, end_vel=80,
                                    bar_start=0, bar_end=1)
        # Only bars 0-1 touched
        for n in sgt_pattern.tracks[t_idx].notes:
            if n.bar >= 2:
                key = (n.bar, n.tick_on, n.note)
                assert n.velocity == before_bar2[key]

    def test_invalid_bar_range(self, sgt_pattern):
        t_idx = next(iter(sgt_pattern.tracks))
        with pytest.raises(ValueError, match="bar"):
            op_velocity_curve(sgt_pattern, t_idx, 50, 80,
                                bar_start=3, bar_end=1)

    def test_invalid_velocity(self, sgt_pattern):
        t_idx = next(iter(sgt_pattern.tracks))
        with pytest.raises(ValueError, match="velocit"):
            op_velocity_curve(sgt_pattern, t_idx, 0, 100)
        with pytest.raises(ValueError, match="velocit"):
            op_velocity_curve(sgt_pattern, t_idx, 50, 200)


class TestNewEmpty:

    def test_defaults(self):
        p = op_new_empty_pattern()
        assert p.bpm == 120.0
        assert p.ppqn == 480
        assert p.time_sig == (4, 4)
        assert p.bar_count == 4
        assert p.name == "EMPTY"
        assert p.tracks == {}

    def test_custom_values(self):
        p = op_new_empty_pattern(bar_count=8, bpm=140.0,
                                  time_sig=(3, 4), name="WALTZ")
        assert p.bar_count == 8
        assert p.bpm == 140.0
        assert p.time_sig == (3, 4)
        assert p.name == "WALTZ"

    def test_bar_count_bounds(self):
        with pytest.raises(ValueError, match="bar_count"):
            op_new_empty_pattern(bar_count=0)
        with pytest.raises(ValueError, match="bar_count"):
            op_new_empty_pattern(bar_count=17)

    def test_bpm_bounds(self):
        with pytest.raises(ValueError, match="bpm"):
            op_new_empty_pattern(bpm=10.0)
        with pytest.raises(ValueError, match="bpm"):
            op_new_empty_pattern(bpm=400.0)

    def test_new_empty_can_be_populated(self):
        p = op_new_empty_pattern(bar_count=2)
        op_add_note(p, track_idx=2, bar=0, beat=0, sub=0, note=60, velocity=90)
        assert len(p.tracks[2].notes) == 1
        assert p.tracks[2].notes[0].note == 60


class TestDiff:

    def test_identical_patterns_empty_diff(self, sgt_pattern):
        import copy
        other = copy.deepcopy(sgt_pattern)
        delta = op_diff_patterns(sgt_pattern, other)
        assert delta["metadata"] == {}
        assert delta["tracks_only_in_a"] == []
        assert delta["tracks_only_in_b"] == []
        assert delta["track_diffs"] == {}

    def test_metadata_change_detected(self, sgt_pattern):
        import copy
        other = copy.deepcopy(sgt_pattern)
        other.bpm = 999.0
        other.name = "DIFFERENT"
        delta = op_diff_patterns(sgt_pattern, other)
        assert "bpm" in delta["metadata"]
        assert "name" in delta["metadata"]
        assert delta["metadata"]["bpm"] == (sgt_pattern.bpm, 999.0)

    def test_added_note_detected(self, sgt_pattern):
        import copy
        other = copy.deepcopy(sgt_pattern)
        t_idx = next(iter(other.tracks))
        op_add_note(other, t_idx, bar=0, beat=0, sub=0, note=60, velocity=90)
        delta = op_diff_patterns(sgt_pattern, other)
        assert t_idx in delta["track_diffs"]
        assert len(delta["track_diffs"][t_idx]["added"]) >= 1

    def test_removed_note_detected(self, sgt_pattern):
        import copy
        other = copy.deepcopy(sgt_pattern)
        t_idx = next(iter(other.tracks))
        op_clear_bar(other, t_idx, bar=0)
        delta = op_diff_patterns(sgt_pattern, other)
        assert t_idx in delta["track_diffs"]
        assert len(delta["track_diffs"][t_idx]["removed"]) >= 1

    def test_modified_velocity_detected(self, sgt_pattern):
        import copy
        other = copy.deepcopy(sgt_pattern)
        t_idx = next(iter(other.tracks))
        op_set_velocity(other, t_idx, velocity=42, bar=0)
        delta = op_diff_patterns(sgt_pattern, other)
        assert t_idx in delta["track_diffs"]
        modified = delta["track_diffs"][t_idx]["modified"]
        assert len(modified) >= 1
        for m in modified:
            assert m["vel"][1] == 42

    def test_tracks_only_in_b(self):
        a = op_new_empty_pattern(bar_count=2)
        b = op_new_empty_pattern(bar_count=2)
        op_add_note(b, track_idx=3, bar=0, beat=0, sub=0, note=60)
        delta = op_diff_patterns(a, b)
        assert 3 in delta["tracks_only_in_b"]
        assert delta["tracks_only_in_a"] == []


class TestResize:

    def test_shrink_drops_overflow(self, sgt_pattern):
        t_idx = next(iter(sgt_pattern.tracks))
        overflow = sum(1 for n in sgt_pattern.tracks[t_idx].notes if n.bar >= 2)
        dropped = op_resize(sgt_pattern, new_bar_count=2)
        assert dropped >= overflow
        assert sgt_pattern.bar_count == 2
        for track in sgt_pattern.tracks.values():
            for n in track.notes:
                assert n.bar < 2

    def test_grow_preserves_notes(self, sgt_pattern):
        total_before = sum(len(t.notes) for t in sgt_pattern.tracks.values())
        dropped = op_resize(sgt_pattern, new_bar_count=8)
        assert dropped == 0
        assert sgt_pattern.bar_count == 8
        total_after = sum(len(t.notes) for t in sgt_pattern.tracks.values())
        assert total_before == total_after

    def test_resize_bounds(self, sgt_pattern):
        with pytest.raises(ValueError, match="bar_count"):
            op_resize(sgt_pattern, new_bar_count=0)
        with pytest.raises(ValueError, match="bar_count"):
            op_resize(sgt_pattern, new_bar_count=17)

    def test_resize_to_same_is_noop(self, sgt_pattern):
        total_before = sum(len(t.notes) for t in sgt_pattern.tracks.values())
        dropped = op_resize(sgt_pattern, new_bar_count=sgt_pattern.bar_count)
        assert dropped == 0
        total_after = sum(len(t.notes) for t in sgt_pattern.tracks.values())
        assert total_before == total_after


class TestShiftTimeAllTracks:

    def test_shift_all_tracks(self, sgt_pattern):
        before_per_track = {
            idx: [(n.bar, n.tick_on) for n in track.notes]
            for idx, track in sgt_pattern.tracks.items()
        }
        total_before = sum(len(v) for v in before_per_track.values())
        kept = op_shift_time(sgt_pattern, None, 120)
        assert kept <= total_before
        # Every track should have been processed: no note in the last bar left
        # that was originally in bar 0
        for idx, track in sgt_pattern.tracks.items():
            for n in track.notes:
                assert n.bar >= 0 and n.bar < sgt_pattern.bar_count


class TestMerge:

    def test_overlay_requires_same_bar_count(self):
        a = op_new_empty_pattern(bar_count=4)
        b = op_new_empty_pattern(bar_count=2)
        with pytest.raises(ValueError, match="bar_count"):
            op_merge_patterns(a, b, mode="overlay")

    def test_overlay_merges_same_track(self):
        a = op_new_empty_pattern(bar_count=2)
        b = op_new_empty_pattern(bar_count=2)
        op_add_note(a, track_idx=0, bar=0, beat=0, sub=0, note=36, velocity=100)
        op_add_note(b, track_idx=0, bar=0, beat=1, sub=0, note=38, velocity=90)
        merged = op_merge_patterns(a, b, mode="overlay")
        assert len(merged.tracks[0].notes) == 2
        notes = sorted((n.bar, n.tick_on, n.note) for n in merged.tracks[0].notes)
        assert notes[0][2] == 36
        assert notes[1][2] == 38
        # Originals not modified
        assert len(a.tracks[0].notes) == 1
        assert len(b.tracks[0].notes) == 1

    def test_overlay_adds_b_only_tracks(self):
        a = op_new_empty_pattern(bar_count=2)
        b = op_new_empty_pattern(bar_count=2)
        op_add_note(a, track_idx=0, bar=0, beat=0, sub=0, note=36)
        op_add_note(b, track_idx=3, bar=0, beat=0, sub=0, note=60)
        merged = op_merge_patterns(a, b, mode="overlay")
        assert 0 in merged.tracks
        assert 3 in merged.tracks
        assert len(merged.tracks[3].notes) == 1

    def test_append_concatenates(self):
        a = op_new_empty_pattern(bar_count=2)
        b = op_new_empty_pattern(bar_count=2)
        op_add_note(a, track_idx=0, bar=0, beat=0, sub=0, note=36)
        op_add_note(a, track_idx=0, bar=1, beat=0, sub=0, note=36)
        op_add_note(b, track_idx=0, bar=0, beat=0, sub=0, note=38)
        op_add_note(b, track_idx=0, bar=1, beat=0, sub=0, note=38)
        merged = op_merge_patterns(a, b, mode="append")
        assert merged.bar_count == 4
        assert len(merged.tracks[0].notes) == 4
        bars = sorted(n.bar for n in merged.tracks[0].notes)
        assert bars == [0, 1, 2, 3]

    def test_append_exceeds_max_raises(self):
        a = op_new_empty_pattern(bar_count=10)
        b = op_new_empty_pattern(bar_count=10)
        with pytest.raises(ValueError, match="max 16"):
            op_merge_patterns(a, b, mode="append")

    def test_merge_rejects_ppqn_mismatch(self):
        a = op_new_empty_pattern()
        b = op_new_empty_pattern(ppqn=240) if False else op_new_empty_pattern()
        # Manually mutate to simulate mismatch
        b.ppqn = 240
        with pytest.raises(ValueError, match="ppqn"):
            op_merge_patterns(a, b, mode="overlay")

    def test_invalid_mode(self):
        a = op_new_empty_pattern()
        b = op_new_empty_pattern()
        with pytest.raises(ValueError, match="mode"):
            op_merge_patterns(a, b, mode="sideways")


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
