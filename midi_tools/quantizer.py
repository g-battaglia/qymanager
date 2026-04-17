#!/usr/bin/env python3
"""MIDI Capture Quantizer for Pipeline B (capture-based conversion).

Reads a playback capture JSON (from send_and_capture.py or capture_playback.py),
parses note_on/note_off pairs, quantizes to a beat grid, and outputs structured
events suitable for Q7P encoding or SMF export.

Channel-to-track mapping (QY70 PATT OUT 9~16):
  Ch  9 = Track 0 (RHY1)    Ch 13 = Track 4 (CHD2)
  Ch 10 = Track 1 (RHY2)    Ch 14 = Track 5 (PAD)
  Ch 11 = Track 2 (BASS)    Ch 15 = Track 6 (PHR1)
  Ch 12 = Track 3 (CHD1)    Ch 16 = Track 7 (PHR2)

Note: The track SLOT names don't always match the voice type.
SGT style has drum voice on BASS slot, bass voice on CHD1 slot.
"""

import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# QY70 PATT OUT 9~16 channel mapping
CHANNEL_TO_TRACK = {
    9: 0,   # RHY1
    10: 1,  # RHY2
    11: 2,  # BASS
    12: 3,  # CHD1
    13: 4,  # CHD2
    14: 5,  # PAD
    15: 6,  # PHR1
    16: 7,  # PHR2
}

TRACK_NAMES = {
    0: "RHY1", 1: "RHY2", 2: "BASS", 3: "CHD1",
    4: "CHD2", 5: "PAD", 6: "PHR1", 7: "PHR2",
}


@dataclass
class QuantizedNote:
    """A single quantized note event."""
    note: int           # MIDI note number
    velocity: int       # 0-127
    tick_on: int        # onset in ticks from bar start
    tick_dur: int       # duration in ticks
    bar: int            # bar number (0-based)
    beat: int           # beat within bar (0-based)
    sub: int            # sub-beat (0 = on beat, 1-3 = 16th subdivisions)

    @property
    def tick_abs(self) -> int:
        """Absolute tick position from start."""
        return self.bar * self._bar_ticks + self.tick_on

    _bar_ticks: int = field(default=0, repr=False)


@dataclass
class QuantizedTrack:
    """All quantized notes for one track."""
    track_idx: int
    channel: int
    notes: List[QuantizedNote] = field(default_factory=list)
    is_drum: bool = False

    @property
    def name(self) -> str:
        return TRACK_NAMES.get(self.track_idx, f"TR{self.track_idx}")

    @property
    def note_set(self) -> set:
        return {n.note for n in self.notes}

    @property
    def bar_count(self) -> int:
        if not self.notes:
            return 0
        return max(n.bar for n in self.notes) + 1


@dataclass
class QuantizedPattern:
    """Complete quantized pattern from a capture."""
    bpm: float
    ppqn: int              # ticks per quarter note
    time_sig: Tuple[int, int]  # (numerator, denominator)
    bar_count: int         # number of bars in one loop
    tracks: Dict[int, QuantizedTrack] = field(default_factory=dict)
    name: str = ""

    @property
    def bar_ticks(self) -> int:
        """Ticks per bar."""
        return self.ppqn * self.time_sig[0] * 4 // self.time_sig[1]

    @property
    def total_ticks(self) -> int:
        return self.bar_ticks * self.bar_count

    @property
    def active_tracks(self) -> List[QuantizedTrack]:
        return [t for t in self.tracks.values() if t.notes]

    def summary(self) -> str:
        lines = [f"Pattern: {self.name or '(unnamed)'}, {self.bpm} BPM, "
                 f"{self.time_sig[0]}/{self.time_sig[1]}, {self.bar_count} bars, "
                 f"PPQN={self.ppqn}"]
        for t in self.active_tracks:
            lines.append(f"  {t.name} (ch{t.channel}): {len(t.notes)} notes, "
                        f"bars 0-{t.bar_count-1}, "
                        f"{'drum' if t.is_drum else 'melody'}, "
                        f"notes: {sorted(t.note_set)}")
        return "\n".join(lines)


def quantize_capture(
    capture_path: str,
    bpm: Optional[float] = None,
    ppqn: int = 480,
    time_sig: Tuple[int, int] = (4, 4),
    bar_count: Optional[int] = None,
    quantize_resolution: int = 16,
    drum_channels: Optional[set] = None,
) -> QuantizedPattern:
    """Quantize a MIDI capture file to a beat grid.

    Args:
        capture_path: Path to capture JSON file.
        bpm: BPM override (uses capture metadata if None).
        ppqn: Ticks per quarter note (default 480, standard MIDI).
        time_sig: Time signature as (numerator, denominator).
        bar_count: Number of bars to extract (auto-detect if None).
        quantize_resolution: Grid resolution in subdivisions per beat
            (4 = 16th notes, 8 = 32nd notes).
        drum_channels: Set of channels to mark as drum tracks.
            Default: {9, 10} (GM drum channels).

    Returns:
        QuantizedPattern with all tracks and notes.
    """
    if drum_channels is None:
        drum_channels = {9, 10}

    with open(capture_path) as f:
        capture = json.load(f)

    if bpm is None:
        bpm = capture.get("bpm", 120)

    raw = capture.get("raw") or capture.get("events", [])
    if not raw:
        raise ValueError("Capture file has no raw/events data")

    # Timing constants
    beat_dur = 60.0 / bpm
    bar_dur = beat_dur * time_sig[0] * 4 / time_sig[1]
    tick_per_sec = ppqn / beat_dur
    ticks_per_bar = ppqn * time_sig[0] * 4 // time_sig[1]
    grid_ticks = ppqn * 4 // quantize_resolution  # e.g. 16 → 120 ticks (16th note at 480 PPQN)

    # Parse raw MIDI events into note_on/note_off by channel
    ch_raw = defaultdict(list)
    for r in raw:
        data = r["data"]
        if len(data) < 3:
            continue
        status = data[0]
        ch = (status & 0x0F) + 1
        note = data[1]
        vel = data[2]
        t = r["t"]

        if (status & 0xF0) == 0x90:
            if vel > 0:
                ch_raw[ch].append(("on", t, note, vel))
            else:
                ch_raw[ch].append(("off", t, note, 0))
        elif (status & 0xF0) == 0x80:
            ch_raw[ch].append(("off", t, note, 0))

    if not ch_raw:
        raise ValueError("No note events found in capture")

    # Find global t0 (earliest note_on across all channels)
    all_on_times = []
    for events in ch_raw.values():
        for typ, t, _, _ in events:
            if typ == "on":
                all_on_times.append(t)
    t0 = min(all_on_times)

    # Auto-detect bar count if not specified
    if bar_count is None:
        max_t = max(t for events in ch_raw.values()
                    for _, t, _, _ in events)
        total_bars = int((max_t - t0) / bar_dur) + 1
        # Try to detect loop: use the first occurrence
        bar_count = _detect_loop_length(ch_raw, t0, bar_dur, grid_ticks,
                                        beat_dur / quantize_resolution,
                                        total_bars)

    # Build quantized tracks
    tracks = {}
    for ch, events in sorted(ch_raw.items()):
        if ch not in CHANNEL_TO_TRACK:
            continue

        track_idx = CHANNEL_TO_TRACK[ch]
        track = QuantizedTrack(
            track_idx=track_idx,
            channel=ch,
            is_drum=ch in drum_channels,
        )

        # Pair note_on with note_off
        on_pending = {}  # note -> (t_on, vel)
        for typ, t, note, vel in events:
            rel_t = t - t0
            if typ == "on":
                on_pending[note] = (rel_t, vel)
            elif typ == "off" and note in on_pending:
                t_on, on_vel = on_pending.pop(note)
                gate_sec = rel_t - t_on

                # Quantize onset
                tick_on_raw = t_on * tick_per_sec
                tick_on_q = round(tick_on_raw / grid_ticks) * grid_ticks

                # Quantize gate (to half the grid resolution)
                half_grid = max(grid_ticks // 2, 1)
                tick_dur_raw = gate_sec * tick_per_sec
                tick_dur_q = max(half_grid, round(tick_dur_raw / half_grid) * half_grid)

                # Compute bar/beat/sub
                bar = int(tick_on_q // ticks_per_bar)
                tick_in_bar = int(tick_on_q % ticks_per_bar)
                beat = tick_in_bar // ppqn
                sub_ticks = tick_in_bar % ppqn
                sub = sub_ticks // grid_ticks

                # Only include notes in the first bar_count bars
                if bar < bar_count:
                    qn = QuantizedNote(
                        note=note,
                        velocity=on_vel,
                        tick_on=tick_in_bar,
                        tick_dur=int(tick_dur_q),
                        bar=bar,
                        beat=beat,
                        sub=sub,
                    )
                    qn._bar_ticks = ticks_per_bar
                    track.notes.append(qn)

        # Sort by absolute position
        track.notes.sort(key=lambda n: (n.bar, n.tick_on, n.note))
        if track.notes:
            tracks[track_idx] = track

    return QuantizedPattern(
        bpm=bpm,
        ppqn=ppqn,
        time_sig=time_sig,
        bar_count=bar_count,
        tracks=tracks,
        name=capture.get("style", ""),
    )


def _detect_loop_length(
    ch_raw: dict,
    t0: float,
    bar_dur: float,
    grid_ticks: int,
    grid_sec: float,
    max_bars: int,
) -> int:
    """Detect the loop length by comparing bar patterns across ALL channels.

    For each candidate loop length, checks ALL channels. The loop length
    must work for every channel (LCM approach). Returns the smallest
    length where all channels with enough data match.
    """
    from math import gcd

    def _lcm(a: int, b: int) -> int:
        return a * b // gcd(a, b)

    # Per-channel loop detection
    ch_loops = {}
    for ch, raw_events in ch_raw.items():
        events = [(t - t0, n) for typ, t, n, _ in raw_events if typ == "on"]
        if len(events) < 4:
            continue

        for loop_len in range(1, min(max_bars // 2 + 1, 13)):
            block_a = []
            block_b = []
            for rel_t, note in events:
                bar = int(rel_t / bar_dur)
                pos = round((rel_t % bar_dur) / grid_sec)
                bar_in_block = bar % loop_len
                if bar < loop_len:
                    block_a.append((bar_in_block, pos, note))
                elif bar < loop_len * 2:
                    block_b.append((bar_in_block, pos, note))

            if len(block_a) > 0 and len(block_b) > 0 and sorted(block_a) == sorted(block_b):
                ch_loops[ch] = loop_len
                break

    if ch_loops:
        # LCM of all detected loop lengths
        result = 1
        for v in ch_loops.values():
            result = _lcm(result, v)
        # Cap at 12 bars (reasonable maximum)
        return min(result, 12, max_bars)

    # Fallback: use 6 bars (common QY70 style length)
    return min(6, max_bars)


def export_json(pattern: QuantizedPattern, output_path: str) -> None:
    """Export quantized pattern as JSON for debugging/editing."""
    data = pattern_to_dict(pattern)
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)


def pattern_to_dict(pattern: QuantizedPattern) -> dict:
    """Serialize a QuantizedPattern to a plain dict (JSON-ready)."""
    data = {
        "bpm": pattern.bpm,
        "ppqn": pattern.ppqn,
        "time_sig": list(pattern.time_sig),
        "bar_count": pattern.bar_count,
        "name": pattern.name,
        "tracks": {},
    }
    for idx, track in pattern.tracks.items():
        data["tracks"][str(idx)] = {
            "name": track.name,
            "channel": track.channel,
            "is_drum": track.is_drum,
            "note_count": len(track.notes),
            "notes": [
                {
                    "note": n.note,
                    "vel": n.velocity,
                    "bar": n.bar,
                    "beat": n.beat,
                    "sub": n.sub,
                    "tick_on": n.tick_on,
                    "tick_dur": n.tick_dur,
                }
                for n in track.notes
            ],
        }
    return data


def dict_to_pattern(data: dict) -> QuantizedPattern:
    """Deserialize a dict (from pattern_to_dict) back to QuantizedPattern.

    This is the inverse of pattern_to_dict / export_json. Used by the
    pattern editor to reload an edited JSON and rebuild Q7P output.
    """
    ppqn = int(data["ppqn"])
    time_sig = tuple(data["time_sig"])
    ticks_per_bar = ppqn * time_sig[0] * 4 // time_sig[1]

    tracks = {}
    for idx_str, tdata in data.get("tracks", {}).items():
        idx = int(idx_str)
        track = QuantizedTrack(
            track_idx=idx,
            channel=int(tdata["channel"]),
            is_drum=bool(tdata.get("is_drum", False)),
        )
        for n in tdata.get("notes", []):
            qn = QuantizedNote(
                note=int(n["note"]),
                velocity=int(n["vel"]),
                tick_on=int(n["tick_on"]),
                tick_dur=int(n["tick_dur"]),
                bar=int(n["bar"]),
                beat=int(n["beat"]),
                sub=int(n["sub"]),
            )
            qn._bar_ticks = ticks_per_bar
            track.notes.append(qn)
        track.notes.sort(key=lambda n: (n.bar, n.tick_on, n.note))
        tracks[idx] = track

    return QuantizedPattern(
        bpm=float(data["bpm"]),
        ppqn=ppqn,
        time_sig=time_sig,
        bar_count=int(data["bar_count"]),
        tracks=tracks,
        name=str(data.get("name", "")),
    )


def load_quantized_json(path: str) -> QuantizedPattern:
    """Load a QuantizedPattern from a JSON file written by export_json."""
    with open(path) as f:
        return dict_to_pattern(json.load(f))


# --- CLI ---

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Quantize MIDI capture to beat grid")
    parser.add_argument("capture", help="Path to capture JSON file")
    parser.add_argument("-b", "--bpm", type=float, help="BPM override")
    parser.add_argument("-n", "--bars", type=int, help="Number of bars to extract")
    parser.add_argument("-r", "--resolution", type=int, default=16,
                       help="Quantize resolution (subdivisions per beat, default: 16)")
    parser.add_argument("-o", "--output", help="Output JSON path")
    parser.add_argument("--ppqn", type=int, default=480,
                       help="Ticks per quarter note (default: 480)")

    args = parser.parse_args()

    pattern = quantize_capture(
        args.capture,
        bpm=args.bpm,
        ppqn=args.ppqn,
        bar_count=args.bars,
        quantize_resolution=args.resolution,
    )

    print(pattern.summary())
    print()

    if args.output:
        export_json(pattern, args.output)
        print(f"Saved to {args.output}")
    else:
        # Print detailed stats
        for track in pattern.active_tracks:
            print(f"\n--- {track.name} (ch{track.channel}) ---")
            for bar in range(min(pattern.bar_count, 3)):
                bar_notes = [n for n in track.notes if n.bar == bar]
                print(f"  Bar {bar}: {len(bar_notes)} notes")
                for n in bar_notes[:8]:
                    print(f"    beat{n.beat}.{n.sub} n={n.note:3d} v={n.velocity:3d} "
                          f"dur={n.tick_dur}")
