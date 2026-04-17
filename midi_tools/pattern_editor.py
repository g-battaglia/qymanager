#!/usr/bin/env python3
"""Pattern editor CLI for Pipeline B (capture-based).

Loads a MIDI capture or a previously-exported quantized JSON,
applies user edits (add/remove/modify notes, transpose, set tempo/name),
and regenerates the Q7P + SMF output.

Workflow:
    1. Capture MIDI playback from QY70   → capture.json
    2. export                            → pattern.json (editable)
    3. edit pattern.json                 ← CLI operations below
    4. build                             → output.Q7P + output.mid

Examples:
    python3 -m midi_tools.pattern_editor export capture.json -o pattern.json
    python3 -m midi_tools.pattern_editor summary pattern.json
    python3 -m midi_tools.pattern_editor list-notes pattern.json --track 0
    python3 -m midi_tools.pattern_editor transpose pattern.json --track 3 --semitones 2
    python3 -m midi_tools.pattern_editor set-tempo pattern.json 120
    python3 -m midi_tools.pattern_editor build pattern.json -o final --scaffold data/q7p/DECAY.Q7P
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

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


DRUM_CHANNELS = {9, 10}


# --- IO helpers ---

def load_pattern(path: str) -> QuantizedPattern:
    """Load pattern from either a capture JSON or a quantized/editable JSON."""
    with open(path) as f:
        data = json.load(f)

    if "raw" in data or "events" in data:
        return quantize_capture(path)
    if "tracks" in data and "bpm" in data:
        return dict_to_pattern(data)
    raise ValueError(f"Unrecognised JSON format: {path}")


def save_pattern(pattern: QuantizedPattern, path: str) -> None:
    export_json(pattern, path)


# --- Edit operations (pure functions on QuantizedPattern) ---

def op_transpose(pattern: QuantizedPattern, track_idx: int, semitones: int) -> int:
    """Transpose notes in one track by semitones. Returns count moved."""
    track = pattern.tracks.get(track_idx)
    if track is None:
        raise KeyError(f"Track {track_idx} not found")
    if track.is_drum:
        raise ValueError(
            f"Track {track_idx} ({track.name}) is a drum track — "
            f"transpose disabled (would remap kit pieces)."
        )
    moved = 0
    for n in track.notes:
        new_note = n.note + semitones
        if 0 <= new_note <= 127:
            n.note = new_note
            moved += 1
    return moved


def op_add_note(
    pattern: QuantizedPattern,
    track_idx: int,
    bar: int,
    beat: int,
    sub: int,
    note: int,
    velocity: int = 100,
    duration_ticks: Optional[int] = None,
) -> None:
    """Insert a new note at the given bar/beat/sub position."""
    track = pattern.tracks.get(track_idx)
    if track is None:
        track = QuantizedTrack(
            track_idx=track_idx,
            channel=_track_idx_to_channel(track_idx),
            is_drum=_track_idx_to_channel(track_idx) in DRUM_CHANNELS,
        )
        pattern.tracks[track_idx] = track

    if not (0 <= bar < pattern.bar_count):
        raise ValueError(f"bar {bar} out of range [0, {pattern.bar_count})")
    if not (0 <= beat < pattern.time_sig[0]):
        raise ValueError(f"beat {beat} out of range [0, {pattern.time_sig[0]})")

    grid_ticks = pattern.ppqn // 4  # 16th at PPQN=480 → 120 ticks
    if not (0 <= sub < (pattern.ppqn // grid_ticks)):
        raise ValueError(f"sub {sub} out of range for PPQN={pattern.ppqn}")
    if not (0 <= note <= 127) or not (0 <= velocity <= 127):
        raise ValueError("note/velocity must be 0-127")

    tick_on = beat * pattern.ppqn + sub * grid_ticks
    tick_dur = duration_ticks if duration_ticks is not None else grid_ticks

    qn = QuantizedNote(
        note=note,
        velocity=velocity,
        tick_on=tick_on,
        tick_dur=tick_dur,
        bar=bar,
        beat=beat,
        sub=sub,
    )
    qn._bar_ticks = pattern.bar_ticks
    track.notes.append(qn)
    track.notes.sort(key=lambda n: (n.bar, n.tick_on, n.note))


def op_remove_notes(
    pattern: QuantizedPattern,
    track_idx: int,
    bar: Optional[int] = None,
    beat: Optional[int] = None,
    note: Optional[int] = None,
) -> int:
    """Remove notes matching the given filter (any None = wildcard). Returns count."""
    track = pattern.tracks.get(track_idx)
    if track is None:
        raise KeyError(f"Track {track_idx} not found")

    def matches(n: QuantizedNote) -> bool:
        if bar is not None and n.bar != bar:
            return False
        if beat is not None and n.beat != beat:
            return False
        if note is not None and n.note != note:
            return False
        return True

    before = len(track.notes)
    track.notes = [n for n in track.notes if not matches(n)]
    return before - len(track.notes)


def op_set_velocity(
    pattern: QuantizedPattern,
    track_idx: Optional[int],
    velocity: int,
    bar: Optional[int] = None,
    note_filter: Optional[int] = None,
) -> int:
    """Set velocity on matching notes. track_idx=None → all tracks.
    Returns total count changed."""
    if not (1 <= velocity <= 127):
        raise ValueError("velocity must be 1-127")

    changed = 0
    for track in _resolve_target_tracks(pattern, track_idx):
        for n in track.notes:
            if bar is not None and n.bar != bar:
                continue
            if note_filter is not None and n.note != note_filter:
                continue
            n.velocity = velocity
            changed += 1
    return changed


def _track_idx_to_channel(track_idx: int) -> int:
    """Inverse of CHANNEL_TO_TRACK mapping (track_idx → MIDI channel)."""
    return 9 + track_idx  # ch 9..16 for tracks 0..7


def _resolve_target_tracks(pattern: QuantizedPattern,
                             track_idx: Optional[int]) -> List:
    """If track_idx is None, return all pattern tracks; else the single
    requested track. Raises KeyError if a specific idx is not present."""
    if track_idx is None:
        return list(pattern.tracks.values())
    t = pattern.tracks.get(track_idx)
    if t is None:
        raise KeyError(f"Track {track_idx} not found")
    return [t]


def op_shift_time(
    pattern: QuantizedPattern,
    track_idx: Optional[int],
    delta_ticks: int,
) -> int:
    """Shift note onsets by delta_ticks. Notes crossing bar boundaries are
    recomputed (bar/beat/sub). Notes that would land before bar 0 or past
    bar_count are dropped. If track_idx is None, every track is shifted.
    Returns total count kept across affected tracks."""
    if track_idx is None:
        target_tracks = list(pattern.tracks.values())
    else:
        t = pattern.tracks.get(track_idx)
        if t is None:
            raise KeyError(f"Track {track_idx} not found")
        target_tracks = [t]

    grid_ticks = pattern.ppqn // 4
    ticks_per_bar = pattern.bar_ticks
    total_ticks = pattern.bar_count * ticks_per_bar

    total_kept = 0
    for track in target_tracks:
        kept: List[QuantizedNote] = []
        for n in track.notes:
            abs_tick = n.bar * ticks_per_bar + n.tick_on + delta_ticks
            if abs_tick < 0 or abs_tick >= total_ticks:
                continue
            new_bar = abs_tick // ticks_per_bar
            new_tick_in_bar = abs_tick % ticks_per_bar
            new_beat = new_tick_in_bar // pattern.ppqn
            new_sub = (new_tick_in_bar % pattern.ppqn) // grid_ticks
            n.bar = new_bar
            n.tick_on = new_tick_in_bar
            n.beat = new_beat
            n.sub = new_sub
            kept.append(n)
        track.notes = kept
        track.notes.sort(key=lambda n: (n.bar, n.tick_on, n.note))
        total_kept += len(kept)
    return total_kept


def op_copy_bar(
    pattern: QuantizedPattern,
    track_idx: int,
    src_bar: int,
    dst_bar: int,
    replace: bool = True,
) -> int:
    """Copy all notes from src_bar to dst_bar. If replace=True, dst_bar
    is cleared first. Returns count copied."""
    track = pattern.tracks.get(track_idx)
    if track is None:
        raise KeyError(f"Track {track_idx} not found")
    if not (0 <= src_bar < pattern.bar_count) or not (0 <= dst_bar < pattern.bar_count):
        raise ValueError(f"bars must be in [0, {pattern.bar_count})")
    if src_bar == dst_bar:
        return 0

    if replace:
        track.notes = [n for n in track.notes if n.bar != dst_bar]

    copied = 0
    for n in list(track.notes):
        if n.bar == src_bar:
            new_n = QuantizedNote(
                note=n.note,
                velocity=n.velocity,
                tick_on=n.tick_on,
                tick_dur=n.tick_dur,
                bar=dst_bar,
                beat=n.beat,
                sub=n.sub,
            )
            new_n._bar_ticks = pattern.bar_ticks
            track.notes.append(new_n)
            copied += 1
    track.notes.sort(key=lambda n: (n.bar, n.tick_on, n.note))
    return copied


def op_clear_bar(
    pattern: QuantizedPattern,
    track_idx: int,
    bar: int,
) -> int:
    """Remove all notes from a bar. Returns count removed."""
    return op_remove_notes(pattern, track_idx, bar=bar)


def op_kit_remap(
    pattern: QuantizedPattern,
    track_idx: int,
    src_note: int,
    dst_note: int,
) -> int:
    """Remap drum-kit note (e.g. 36→38 = kick→snare). Returns count remapped."""
    track = pattern.tracks.get(track_idx)
    if track is None:
        raise KeyError(f"Track {track_idx} not found")
    if not track.is_drum:
        raise ValueError(f"Track {track_idx} is not a drum track")
    if not (0 <= dst_note <= 127):
        raise ValueError("dst_note must be 0-127")

    count = 0
    for n in track.notes:
        if n.note == src_note:
            n.note = dst_note
            count += 1
    track.notes.sort(key=lambda n: (n.bar, n.tick_on, n.note))
    return count


def op_humanize_velocity(
    pattern: QuantizedPattern,
    track_idx: Optional[int],
    amount: int,
    seed: Optional[int] = None,
) -> int:
    """Add random ±amount to velocity. track_idx=None → all tracks.
    Deterministic if seed is given. Velocity clamped to [1, 127].
    Returns total count modified."""
    import random
    if amount < 0:
        raise ValueError("amount must be non-negative")

    rng = random.Random(seed) if seed is not None else random.Random()
    count = 0
    for track in _resolve_target_tracks(pattern, track_idx):
        for n in track.notes:
            delta = rng.randint(-amount, amount)
            n.velocity = max(1, min(127, n.velocity + delta))
            count += 1
    return count


def op_humanize_timing(
    pattern: QuantizedPattern,
    track_idx: Optional[int],
    amount_ticks: int,
    seed: Optional[int] = None,
) -> int:
    """Add random ±amount_ticks to tick_on. track_idx=None → all tracks.
    Notes that fall outside [0, total_ticks) are dropped.
    Returns total count kept."""
    import random
    if amount_ticks < 0:
        raise ValueError("amount_ticks must be non-negative")

    rng = random.Random(seed) if seed is not None else random.Random()
    grid_ticks = pattern.ppqn // 4
    ticks_per_bar = pattern.bar_ticks
    total_ticks = pattern.bar_count * ticks_per_bar

    total_kept = 0
    for track in _resolve_target_tracks(pattern, track_idx):
        kept: List[QuantizedNote] = []
        for n in track.notes:
            delta = rng.randint(-amount_ticks, amount_ticks)
            abs_tick = n.bar * ticks_per_bar + n.tick_on + delta
            if abs_tick < 0 or abs_tick >= total_ticks:
                continue
            new_bar = abs_tick // ticks_per_bar
            new_tick_in_bar = abs_tick % ticks_per_bar
            n.bar = new_bar
            n.tick_on = new_tick_in_bar
            n.beat = new_tick_in_bar // pattern.ppqn
            n.sub = (new_tick_in_bar % pattern.ppqn) // grid_ticks
            kept.append(n)
        track.notes = kept
        track.notes.sort(key=lambda n: (n.bar, n.tick_on, n.note))
        total_kept += len(kept)
    return total_kept


def op_velocity_curve(
    pattern: QuantizedPattern,
    track_idx: Optional[int],
    start_vel: int,
    end_vel: int,
    bar_start: Optional[int] = None,
    bar_end: Optional[int] = None,
) -> int:
    """Apply a linear velocity ramp from start_vel to end_vel across
    the selected bar range (inclusive). track_idx=None → all tracks.
    If bar_start/bar_end are None, the full pattern range is used.
    Velocity clamped to [1, 127]. Returns total count modified."""
    if not (1 <= start_vel <= 127) or not (1 <= end_vel <= 127):
        raise ValueError("velocities must be in [1, 127]")

    b0 = 0 if bar_start is None else bar_start
    b1 = pattern.bar_count - 1 if bar_end is None else bar_end
    if b0 > b1:
        raise ValueError("bar_start must be <= bar_end")
    if b0 < 0 or b1 >= pattern.bar_count:
        raise ValueError(f"bar range out of pattern bounds [0, {pattern.bar_count - 1}]")

    ticks_per_bar = pattern.bar_ticks
    t_start = b0 * ticks_per_bar
    t_end = (b1 + 1) * ticks_per_bar
    span = max(1, t_end - t_start)

    count = 0
    for track in _resolve_target_tracks(pattern, track_idx):
        for n in track.notes:
            if n.bar < b0 or n.bar > b1:
                continue
            abs_tick = n.bar * ticks_per_bar + n.tick_on
            frac = (abs_tick - t_start) / span
            interp = start_vel + (end_vel - start_vel) * frac
            n.velocity = max(1, min(127, int(round(interp))))
            count += 1
    return count


def op_new_empty_pattern(
    bar_count: int = 4,
    bpm: float = 120.0,
    ppqn: int = 480,
    time_sig: tuple = (4, 4),
    name: str = "EMPTY",
) -> QuantizedPattern:
    """Create a fresh empty pattern with no notes, ready to be programmed."""
    if bar_count < 1 or bar_count > 16:
        raise ValueError("bar_count must be in [1, 16]")
    if not (20 <= bpm <= 300):
        raise ValueError("bpm must be in [20, 300]")
    return QuantizedPattern(
        bpm=float(bpm),
        ppqn=int(ppqn),
        time_sig=tuple(time_sig),
        bar_count=int(bar_count),
        tracks={},
        name=str(name),
    )


def op_diff_patterns(
    a: QuantizedPattern,
    b: QuantizedPattern,
) -> dict:
    """Compare two patterns; return structured delta.

    Keys:
        metadata: dict of (field, (a_val, b_val)) for differing fields
        tracks_only_in_a: list of track_idx
        tracks_only_in_b: list of track_idx
        track_diffs: {track_idx: {"added": [...], "removed": [...], "modified": [...]}}
    """
    out = {
        "metadata": {},
        "tracks_only_in_a": [],
        "tracks_only_in_b": [],
        "track_diffs": {},
    }

    for field in ("bpm", "ppqn", "time_sig", "bar_count", "name"):
        va, vb = getattr(a, field), getattr(b, field)
        if va != vb:
            out["metadata"][field] = (va, vb)

    a_tracks, b_tracks = set(a.tracks), set(b.tracks)
    out["tracks_only_in_a"] = sorted(a_tracks - b_tracks)
    out["tracks_only_in_b"] = sorted(b_tracks - a_tracks)

    def note_key(n: QuantizedNote):
        return (n.bar, n.tick_on, n.note)

    for idx in sorted(a_tracks & b_tracks):
        a_notes = {note_key(n): n for n in a.tracks[idx].notes}
        b_notes = {note_key(n): n for n in b.tracks[idx].notes}

        added_keys = sorted(set(b_notes) - set(a_notes))
        removed_keys = sorted(set(a_notes) - set(b_notes))
        modified = []
        for k in sorted(set(a_notes) & set(b_notes)):
            na, nb = a_notes[k], b_notes[k]
            if na.velocity != nb.velocity or na.tick_dur != nb.tick_dur:
                modified.append({
                    "key": k,
                    "vel": (na.velocity, nb.velocity),
                    "dur": (na.tick_dur, nb.tick_dur),
                })

        if added_keys or removed_keys or modified:
            out["track_diffs"][idx] = {
                "added": [{"bar": k[0], "tick_on": k[1], "note": k[2],
                           "vel": b_notes[k].velocity} for k in added_keys],
                "removed": [{"bar": k[0], "tick_on": k[1], "note": k[2],
                             "vel": a_notes[k].velocity} for k in removed_keys],
                "modified": modified,
            }

    return out


def op_merge_patterns(
    a: QuantizedPattern,
    b: QuantizedPattern,
    mode: str = "overlay",
) -> QuantizedPattern:
    """Merge two patterns.

    mode='overlay': same bar range; tracks on same idx concatenated,
        b-only tracks added. Requires equal bar_count and ppqn.
    mode='append': concatenate b after a; result has
        a.bar_count + b.bar_count bars (up to 16).

    Returns a new QuantizedPattern; inputs are not modified.
    """
    import copy
    if mode not in ("overlay", "append"):
        raise ValueError(f"unknown mode {mode!r}; use 'overlay' or 'append'")
    if a.ppqn != b.ppqn:
        raise ValueError(f"ppqn mismatch: {a.ppqn} vs {b.ppqn}")
    if a.time_sig != b.time_sig:
        raise ValueError(f"time_sig mismatch: {a.time_sig} vs {b.time_sig}")

    if mode == "overlay":
        if a.bar_count != b.bar_count:
            raise ValueError(f"bar_count mismatch for overlay: {a.bar_count} vs {b.bar_count}")
        out = copy.deepcopy(a)
        for idx, tb in b.tracks.items():
            if idx in out.tracks:
                out.tracks[idx].notes.extend(copy.deepcopy(n) for n in tb.notes)
                out.tracks[idx].notes.sort(key=lambda n: (n.bar, n.tick_on, n.note))
            else:
                out.tracks[idx] = copy.deepcopy(tb)
        return out

    # mode == "append"
    total_bars = a.bar_count + b.bar_count
    if total_bars > 16:
        raise ValueError(f"append would produce {total_bars} bars (max 16)")
    out = copy.deepcopy(a)
    out.bar_count = total_bars
    offset = a.bar_count
    for idx, tb in b.tracks.items():
        shifted_notes = []
        for n in tb.notes:
            nn = copy.deepcopy(n)
            nn.bar += offset
            shifted_notes.append(nn)
        if idx in out.tracks:
            out.tracks[idx].notes.extend(shifted_notes)
            out.tracks[idx].notes.sort(key=lambda n: (n.bar, n.tick_on, n.note))
        else:
            new_track = copy.deepcopy(tb)
            new_track.notes = shifted_notes
            out.tracks[idx] = new_track
    return out


def op_resize(pattern: QuantizedPattern, new_bar_count: int) -> int:
    """Change pattern bar count. Notes in bars >= new_bar_count are dropped.
    Returns count dropped."""
    if new_bar_count < 1 or new_bar_count > 16:
        raise ValueError("bar_count must be in [1, 16]")
    dropped = 0
    for track in pattern.tracks.values():
        before = len(track.notes)
        track.notes = [n for n in track.notes if n.bar < new_bar_count]
        dropped += before - len(track.notes)
    pattern.bar_count = new_bar_count
    return dropped


# --- CLI commands ---

def cmd_export(args: argparse.Namespace) -> int:
    pattern = load_pattern(args.input)
    save_pattern(pattern, args.output)
    print(f"Exported: {args.output}")
    print(pattern.summary())
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    pattern = load_pattern(args.input)
    print(pattern.summary())
    return 0


def cmd_list_notes(args: argparse.Namespace) -> int:
    pattern = load_pattern(args.input)
    tracks_to_show = (
        [pattern.tracks[args.track]] if args.track is not None
        else pattern.active_tracks
    )
    for track in tracks_to_show:
        print(f"\n--- {track.name} (track {track.track_idx}, ch{track.channel}, "
              f"{'drum' if track.is_drum else 'melody'}) ---")
        for n in track.notes:
            if args.bar is not None and n.bar != args.bar:
                continue
            note_name = _midi_note_name(n.note) if not track.is_drum else f"kit:{n.note}"
            print(f"  bar{n.bar} beat{n.beat}.{n.sub:2d}  "
                  f"note={n.note:3d} ({note_name:<6}) "
                  f"vel={n.velocity:3d} dur={n.tick_dur:4d}")
    return 0


def cmd_transpose(args: argparse.Namespace) -> int:
    pattern = load_pattern(args.input)
    moved = op_transpose(pattern, args.track, args.semitones)
    save_pattern(pattern, args.input)
    print(f"Transposed {moved} notes in track {args.track} by {args.semitones:+d} semitones")
    return 0


def cmd_add_note(args: argparse.Namespace) -> int:
    pattern = load_pattern(args.input)
    op_add_note(
        pattern,
        track_idx=args.track,
        bar=args.bar,
        beat=args.beat,
        sub=args.sub,
        note=args.note,
        velocity=args.velocity,
        duration_ticks=args.duration,
    )
    save_pattern(pattern, args.input)
    print(f"Added note {args.note} at track {args.track} "
          f"bar{args.bar} beat{args.beat}.{args.sub}")
    return 0


def cmd_remove_note(args: argparse.Namespace) -> int:
    pattern = load_pattern(args.input)
    removed = op_remove_notes(
        pattern,
        track_idx=args.track,
        bar=args.bar,
        beat=args.beat,
        note=args.note,
    )
    save_pattern(pattern, args.input)
    print(f"Removed {removed} notes")
    return 0


def _resolve_track_arg(args: argparse.Namespace) -> Optional[int]:
    """Resolve --track / --all-tracks into a track index or None."""
    all_flag = getattr(args, "all_tracks", False)
    track = getattr(args, "track", None)
    if all_flag and track is not None:
        raise ValueError("use either --track or --all-tracks, not both")
    if not all_flag and track is None:
        raise ValueError("either --track N or --all-tracks is required")
    return None if all_flag else track


def cmd_set_velocity(args: argparse.Namespace) -> int:
    target = _resolve_track_arg(args)
    pattern = load_pattern(args.input)
    changed = op_set_velocity(
        pattern,
        track_idx=target,
        velocity=args.velocity,
        bar=args.bar,
        note_filter=args.note,
    )
    save_pattern(pattern, args.input)
    print(f"Set velocity={args.velocity} on {changed} notes")
    return 0


def cmd_set_tempo(args: argparse.Namespace) -> int:
    pattern = load_pattern(args.input)
    pattern.bpm = args.bpm
    save_pattern(pattern, args.input)
    print(f"Tempo set to {args.bpm} BPM")
    return 0


def cmd_set_name(args: argparse.Namespace) -> int:
    pattern = load_pattern(args.input)
    pattern.name = args.name
    save_pattern(pattern, args.input)
    print(f"Name set to {args.name!r}")
    return 0


def cmd_shift_time(args: argparse.Namespace) -> int:
    if args.all_tracks and args.track is not None:
        raise ValueError("use either --track or --all-tracks, not both")
    if not args.all_tracks and args.track is None:
        raise ValueError("either --track N or --all-tracks is required")
    target = None if args.all_tracks else args.track
    pattern = load_pattern(args.input)
    kept = op_shift_time(pattern, target, args.ticks)
    save_pattern(pattern, args.input)
    label = "all tracks" if target is None else f"track {target}"
    print(f"Shifted {label} by {args.ticks:+d} ticks, {kept} notes kept")
    return 0


def cmd_merge(args: argparse.Namespace) -> int:
    a = load_pattern(args.a)
    b = load_pattern(args.b)
    merged = op_merge_patterns(a, b, mode=args.mode)
    save_pattern(merged, args.output)
    total = sum(len(t.notes) for t in merged.tracks.values())
    print(f"Merged ({args.mode}): {args.output} — "
          f"{merged.bar_count} bars, {len(merged.tracks)} tracks, {total} notes")
    return 0


def cmd_copy_bar(args: argparse.Namespace) -> int:
    pattern = load_pattern(args.input)
    copied = op_copy_bar(pattern, args.track, args.src, args.dst, replace=not args.append)
    save_pattern(pattern, args.input)
    print(f"Copied {copied} notes from bar {args.src} to bar {args.dst}")
    return 0


def cmd_clear_bar(args: argparse.Namespace) -> int:
    pattern = load_pattern(args.input)
    removed = op_clear_bar(pattern, args.track, args.bar)
    save_pattern(pattern, args.input)
    print(f"Cleared {removed} notes in track {args.track} bar {args.bar}")
    return 0


def cmd_kit_remap(args: argparse.Namespace) -> int:
    pattern = load_pattern(args.input)
    count = op_kit_remap(pattern, args.track, args.src, args.dst)
    save_pattern(pattern, args.input)
    print(f"Remapped {count} drum notes {args.src} → {args.dst}")
    return 0


def cmd_humanize(args: argparse.Namespace) -> int:
    target = _resolve_track_arg(args)
    pattern = load_pattern(args.input)
    count = op_humanize_velocity(pattern, target, args.amount, seed=args.seed)
    save_pattern(pattern, args.input)
    label = "all tracks" if target is None else f"track {target}"
    print(f"Humanized velocity (±{args.amount}) on {label}, {count} notes")
    return 0


def cmd_humanize_timing(args: argparse.Namespace) -> int:
    target = _resolve_track_arg(args)
    pattern = load_pattern(args.input)
    kept = op_humanize_timing(pattern, target, args.amount, seed=args.seed)
    save_pattern(pattern, args.input)
    label = "all tracks" if target is None else f"track {target}"
    print(f"Humanized timing (±{args.amount} ticks) on {label}, {kept} notes kept")
    return 0


def cmd_velocity_curve(args: argparse.Namespace) -> int:
    target = _resolve_track_arg(args)
    pattern = load_pattern(args.input)
    count = op_velocity_curve(
        pattern, target, args.start, args.end,
        bar_start=args.bar_start, bar_end=args.bar_end,
    )
    save_pattern(pattern, args.input)
    label = "all tracks" if target is None else f"track {target}"
    print(f"Applied velocity curve {args.start}→{args.end} on {label}, {count} notes")
    return 0


def cmd_new_empty(args: argparse.Namespace) -> int:
    pattern = op_new_empty_pattern(
        bar_count=args.bars,
        bpm=args.bpm,
        time_sig=(args.num, args.den),
        name=args.name,
    )
    save_pattern(pattern, args.output)
    print(f"Created empty pattern: {args.output} "
          f"({args.bars} bars, {args.bpm} BPM, {args.num}/{args.den}, name={args.name!r})")
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    a = load_pattern(args.a)
    b = load_pattern(args.b)
    delta = op_diff_patterns(a, b)

    print(f"=== diff {args.a} → {args.b} ===")
    if delta["metadata"]:
        print("\nMetadata changes:")
        for k, (va, vb) in delta["metadata"].items():
            print(f"  {k}: {va!r} → {vb!r}")
    if delta["tracks_only_in_a"]:
        print(f"\nTracks only in A: {delta['tracks_only_in_a']}")
    if delta["tracks_only_in_b"]:
        print(f"\nTracks only in B: {delta['tracks_only_in_b']}")
    for idx, td in sorted(delta["track_diffs"].items()):
        print(f"\nTrack {idx}: "
              f"+{len(td['added'])} added, "
              f"-{len(td['removed'])} removed, "
              f"~{len(td['modified'])} modified")
        for n in td["added"][:5]:
            print(f"  + bar{n['bar']} tick={n['tick_on']} note={n['note']} vel={n['vel']}")
        if len(td["added"]) > 5:
            print(f"    ...{len(td['added']) - 5} more")
        for n in td["removed"][:5]:
            print(f"  - bar{n['bar']} tick={n['tick_on']} note={n['note']} vel={n['vel']}")
        if len(td["removed"]) > 5:
            print(f"    ...{len(td['removed']) - 5} more")
        for m in td["modified"][:5]:
            print(f"  ~ bar{m['key'][0]} tick={m['key'][1]} note={m['key'][2]}: "
                  f"vel {m['vel'][0]}→{m['vel'][1]}, dur {m['dur'][0]}→{m['dur'][1]}")

    if not any([delta["metadata"], delta["tracks_only_in_a"],
                delta["tracks_only_in_b"], delta["track_diffs"]]):
        print("Patterns are identical.")
    return 0


def cmd_resize(args: argparse.Namespace) -> int:
    pattern = load_pattern(args.input)
    dropped = op_resize(pattern, args.bars)
    save_pattern(pattern, args.input)
    print(f"Resized to {args.bars} bars, dropped {dropped} notes")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    from midi_tools.build_q7p_5120 import build_q7p, validate_q7p
    from midi_tools.capture_to_q7p import write_smf

    pattern = load_pattern(args.input)

    out_q7p = f"{args.output}.Q7P"
    out_mid = f"{args.output}.mid"

    q7p_data = build_q7p(pattern, args.scaffold)
    with open(args.scaffold, "rb") as f:
        scaffold_bytes = f.read()
    warnings = validate_q7p(q7p_data, scaffold=scaffold_bytes)

    if warnings:
        print("VALIDATION WARNINGS:")
        for w in warnings:
            print(f"  - {w}")
        if not args.force:
            print("Aborted. Use --force to write anyway.")
            return 1

    with open(out_q7p, "wb") as f:
        f.write(q7p_data)
    write_smf(pattern, out_mid)

    print(f"Built: {out_q7p} ({len(q7p_data)} bytes), {out_mid}")
    print(pattern.summary())
    return 0


# --- helpers ---

_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

def _midi_note_name(n: int) -> str:
    return f"{_NOTE_NAMES[n % 12]}{n // 12 - 1}"


# --- argparse setup ---

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pattern_editor",
        description="Edit captured QY70 patterns for Q7P output.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_export = sub.add_parser("export", help="Capture JSON → editable pattern JSON")
    p_export.add_argument("input", help="Capture JSON path")
    p_export.add_argument("-o", "--output", required=True, help="Output pattern JSON")
    p_export.set_defaults(func=cmd_export)

    p_summary = sub.add_parser("summary", help="Print pattern summary")
    p_summary.add_argument("input")
    p_summary.set_defaults(func=cmd_summary)

    p_list = sub.add_parser("list-notes", help="List notes")
    p_list.add_argument("input")
    p_list.add_argument("--track", type=int, help="Filter by track index (0-7)")
    p_list.add_argument("--bar", type=int, help="Filter by bar")
    p_list.set_defaults(func=cmd_list_notes)

    p_trans = sub.add_parser("transpose", help="Transpose a melody track")
    p_trans.add_argument("input")
    p_trans.add_argument("--track", type=int, required=True)
    p_trans.add_argument("--semitones", type=int, required=True)
    p_trans.set_defaults(func=cmd_transpose)

    p_add = sub.add_parser("add-note", help="Add a note to a track")
    p_add.add_argument("input")
    p_add.add_argument("--track", type=int, required=True)
    p_add.add_argument("--bar", type=int, required=True)
    p_add.add_argument("--beat", type=int, required=True)
    p_add.add_argument("--sub", type=int, default=0, help="16th sub-beat (0-3)")
    p_add.add_argument("--note", type=int, required=True, help="MIDI note 0-127")
    p_add.add_argument("--velocity", type=int, default=100)
    p_add.add_argument("--duration", type=int, default=None,
                       help="Duration in ticks (default: one grid cell)")
    p_add.set_defaults(func=cmd_add_note)

    p_rm = sub.add_parser("remove-note", help="Remove notes matching a filter")
    p_rm.add_argument("input")
    p_rm.add_argument("--track", type=int, required=True)
    p_rm.add_argument("--bar", type=int)
    p_rm.add_argument("--beat", type=int)
    p_rm.add_argument("--note", type=int)
    p_rm.set_defaults(func=cmd_remove_note)

    p_vel = sub.add_parser("set-velocity", help="Set velocity on matching notes")
    p_vel.add_argument("input")
    p_vel.add_argument("--track", type=int, default=None)
    p_vel.add_argument("--all-tracks", action="store_true",
                        help="Apply to every track")
    p_vel.add_argument("--velocity", type=int, required=True)
    p_vel.add_argument("--bar", type=int)
    p_vel.add_argument("--note", type=int, help="Match only this MIDI note")
    p_vel.set_defaults(func=cmd_set_velocity)

    p_tempo = sub.add_parser("set-tempo", help="Change BPM")
    p_tempo.add_argument("input")
    p_tempo.add_argument("bpm", type=float)
    p_tempo.set_defaults(func=cmd_set_tempo)

    p_name = sub.add_parser("set-name", help="Change pattern name")
    p_name.add_argument("input")
    p_name.add_argument("name")
    p_name.set_defaults(func=cmd_set_name)

    p_shift = sub.add_parser("shift-time",
                             help="Shift track notes by N ticks (drops overflow)")
    p_shift.add_argument("input")
    p_shift.add_argument("--track", type=int, default=None,
                         help="Track index (use --all-tracks to shift every track)")
    p_shift.add_argument("--all-tracks", action="store_true",
                         help="Shift every track")
    p_shift.add_argument("--ticks", type=int, required=True,
                         help="Delta in ticks (PPQN=480 → 120=16th, 240=8th, 480=quarter)")
    p_shift.set_defaults(func=cmd_shift_time)

    p_merge = sub.add_parser("merge",
                              help="Merge two patterns (overlay=same bars | append=concat)")
    p_merge.add_argument("a", help="Pattern A (base)")
    p_merge.add_argument("b", help="Pattern B (to merge in)")
    p_merge.add_argument("-o", "--output", required=True, help="Output pattern JSON")
    p_merge.add_argument("--mode", choices=["overlay", "append"], default="overlay")
    p_merge.set_defaults(func=cmd_merge)

    p_copy = sub.add_parser("copy-bar", help="Copy bar contents to another bar")
    p_copy.add_argument("input")
    p_copy.add_argument("--track", type=int, required=True)
    p_copy.add_argument("--src", type=int, required=True)
    p_copy.add_argument("--dst", type=int, required=True)
    p_copy.add_argument("--append", action="store_true",
                        help="Append to dst instead of replacing")
    p_copy.set_defaults(func=cmd_copy_bar)

    p_clear = sub.add_parser("clear-bar", help="Remove all notes from a bar")
    p_clear.add_argument("input")
    p_clear.add_argument("--track", type=int, required=True)
    p_clear.add_argument("--bar", type=int, required=True)
    p_clear.set_defaults(func=cmd_clear_bar)

    p_kit = sub.add_parser("kit-remap", help="Remap drum-kit note (e.g. 36→38)")
    p_kit.add_argument("input")
    p_kit.add_argument("--track", type=int, required=True)
    p_kit.add_argument("--src", type=int, required=True, help="Source MIDI note")
    p_kit.add_argument("--dst", type=int, required=True, help="Destination MIDI note")
    p_kit.set_defaults(func=cmd_kit_remap)

    p_hum = sub.add_parser("humanize",
                           help="Random ±amount velocity variation")
    p_hum.add_argument("input")
    p_hum.add_argument("--track", type=int, default=None)
    p_hum.add_argument("--all-tracks", action="store_true",
                       help="Apply to every track")
    p_hum.add_argument("--amount", type=int, required=True,
                       help="Max absolute deviation (e.g. 10 → ±10)")
    p_hum.add_argument("--seed", type=int, default=None,
                       help="Random seed for reproducibility")
    p_hum.set_defaults(func=cmd_humanize)

    p_hut = sub.add_parser("humanize-timing",
                            help="Random ±amount_ticks jitter on tick_on")
    p_hut.add_argument("input")
    p_hut.add_argument("--track", type=int, default=None)
    p_hut.add_argument("--all-tracks", action="store_true",
                        help="Apply to every track")
    p_hut.add_argument("--amount", type=int, required=True,
                        help="Max absolute tick deviation (e.g. 30 → ±30 ticks)")
    p_hut.add_argument("--seed", type=int, default=None,
                        help="Random seed for reproducibility")
    p_hut.set_defaults(func=cmd_humanize_timing)

    p_vcurve = sub.add_parser("velocity-curve",
                               help="Linear velocity ramp across bar range")
    p_vcurve.add_argument("input")
    p_vcurve.add_argument("--track", type=int, default=None)
    p_vcurve.add_argument("--all-tracks", action="store_true",
                          help="Apply to every track")
    p_vcurve.add_argument("--start", type=int, required=True,
                          help="Starting velocity (1-127)")
    p_vcurve.add_argument("--end", type=int, required=True,
                          help="Ending velocity (1-127)")
    p_vcurve.add_argument("--bar-start", type=int, default=None,
                          help="First bar in range (default: 0)")
    p_vcurve.add_argument("--bar-end", type=int, default=None,
                          help="Last bar in range (default: last bar)")
    p_vcurve.set_defaults(func=cmd_velocity_curve)

    p_new = sub.add_parser("new-empty", help="Create an empty pattern from scratch")
    p_new.add_argument("-o", "--output", required=True, help="Output pattern JSON")
    p_new.add_argument("--bars", type=int, default=4)
    p_new.add_argument("--bpm", type=float, default=120.0)
    p_new.add_argument("--num", type=int, default=4, help="Time sig numerator")
    p_new.add_argument("--den", type=int, default=4, help="Time sig denominator")
    p_new.add_argument("--name", default="EMPTY")
    p_new.set_defaults(func=cmd_new_empty)

    p_diff = sub.add_parser("diff", help="Compare two pattern JSONs")
    p_diff.add_argument("a", help="Pattern A (before)")
    p_diff.add_argument("b", help="Pattern B (after)")
    p_diff.set_defaults(func=cmd_diff)

    p_resize = sub.add_parser("resize", help="Change pattern bar count (drops overflow)")
    p_resize.add_argument("input")
    p_resize.add_argument("--bars", type=int, required=True)
    p_resize.set_defaults(func=cmd_resize)

    p_build = sub.add_parser("build", help="Build .Q7P + .mid from pattern JSON")
    p_build.add_argument("input")
    p_build.add_argument("-o", "--output", required=True, help="Output prefix")
    p_build.add_argument("--scaffold", default="data/q7p/DECAY.Q7P",
                         help="Q7P scaffold (DECAY for 4-bar, SGT..Q7P for 6-bar)")
    p_build.add_argument("--force", action="store_true",
                         help="Write output even if validator warnings exist")
    p_build.set_defaults(func=cmd_build)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
