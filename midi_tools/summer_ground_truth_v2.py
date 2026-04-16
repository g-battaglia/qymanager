#!/usr/bin/env python3
"""
Summer ground truth v2 — corrected 4-bar pattern interpretation.

Earlier analysis assumed 5-bar pattern based on SysEx having 5 segments.
Playback capture proves otherwise: MIDI repeats every 8 seconds (4 bars at
120 BPM). Therefore:

    Bars 1..4 = real music bars (SysEx segs 1..4)
    Seg 5 = padding/unused bar markers (NOT musical content)

Capture covers ~3 loops = 12 bars + 6 notes tail = 24.75s.

This v2 maps each SysEx segment event to its correct musical bar.
Segment 5 events are flagged as 'unused' — their MIDI counterpart
(t=[8..10]s) is actually bar 1 of loop 2.
"""

import sys
import os
import json
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from midi_tools.analyze_cross_pattern_signatures import parse_all_tracks, extract_events


BPM = 120.0
BEAT_S = 60.0 / BPM
BAR_S = BEAT_S * 4
PATTERN_BARS = 4  # CORRECTED: Summer is 4 bars, not 5
PATTERN_S = BAR_S * PATTERN_BARS

TRACK_INFO = {
    0x00: {"name": "RHY1", "midi_ch": 8},
    0x03: {"name": "CHD1", "midi_ch": 11},
    0x04: {"name": "CHD2", "midi_ch": 12},
    0x05: {"name": "PHR1", "midi_ch": 13},
    0x06: {"name": "PHR2", "midi_ch": 14},
}


def load_midi_by_channel(json_path, max_loop=1):
    by_ch = defaultdict(list)
    with open(json_path) as f:
        data = json.load(f)
    for ev in data["events"]:
        d = ev["data"]
        if len(d) < 3:
            continue
        if (d[0] & 0xF0) != 0x90:
            continue
        if d[2] == 0:
            continue
        t = ev["t"]
        if t >= PATTERN_S * max_loop:
            break
        ch = d[0] & 0x0F
        by_ch[ch].append((t, d[1], d[2]))
    return by_ch


def main():
    sm = parse_all_tracks("data/qy70_sysx/P -  Summer - 20231101.syx")
    midi_by_ch = load_midi_by_channel(
        "midi_tools/captured/summer_playback_s25.json", max_loop=1
    )

    output = {
        "source": "Summer_20231101.syx",
        "bpm": BPM,
        "pattern_bars": PATTERN_BARS,
        "note": "Corrected v2: Summer is 4-bar pattern. Seg 5 = unused markers.",
        "tracks": {},
    }

    for al, info in TRACK_INFO.items():
        name = info["name"]
        ch = info["midi_ch"]
        track_bytes = sm.get(al, b"")
        if not track_bytes:
            continue

        events = extract_events(track_bytes)
        notes = midi_by_ch.get(ch, [])

        by_seg = defaultdict(list)
        for si, ei, evt, hdr in events:
            by_seg[si].append((ei, evt))

        print("=" * 72)
        print(f"{name} (AL=0x{al:02x}, ch{ch+1}) — "
              f"{len(track_bytes)} bytes, {len(notes)} MIDI notes in 4-bar loop")
        print("=" * 72)

        track_out = {
            "name": name,
            "al": al,
            "midi_channel_1based": ch + 1,
            "midi_note_count": len(notes),
            "preamble_hex": track_bytes[:28].hex(),
            "events_by_segment": {},
            "music_bar_events": [],
            "unused_seg5_events": [],
        }

        # Map segs 1..4 to bars 1..4
        for si in range(1, 5):
            bar_idx = si - 1  # 0..3
            bar_start = bar_idx * BAR_S
            bar_end = bar_start + BAR_S
            bar_notes = [(t, n, v) for t, n, v in notes
                         if bar_start <= t < bar_end]

            beat_notes = defaultdict(list)
            for t, n, v in bar_notes:
                bar_t = t - bar_start
                eighth = round(bar_t / (BEAT_S / 2))
                beat = eighth // 2
                sub = eighth % 2
                if beat < 4:
                    beat_notes[beat].append((n, v, sub, t))

            for ei, evt_bytes in by_seg.get(si, []):
                expected = sorted(beat_notes.get(ei, []),
                                  key=lambda x: (x[2], x[0]))
                track_out["music_bar_events"].append({
                    "bar": si,
                    "beat": ei + 1,
                    "segment_idx": si,
                    "event_idx_in_seg": ei,
                    "event_hex": evt_bytes.hex(),
                    "event_decimal": list(evt_bytes),
                    "expected_strikes": [
                        {"note": n, "velocity": v, "subdivision_8th": s}
                        for n, v, s, _ in expected
                    ],
                })

        # Seg 5 events (unused)
        for ei, evt_bytes in by_seg.get(5, []):
            track_out["unused_seg5_events"].append({
                "event_idx_in_seg": ei,
                "event_hex": evt_bytes.hex(),
                "event_decimal": list(evt_bytes),
            })

        # Seg 0 events (init/preamble)
        track_out["seg0_init_events"] = []
        for ei, evt_bytes in by_seg.get(0, []):
            track_out["seg0_init_events"].append({
                "event_idx_in_seg": ei,
                "event_hex": evt_bytes.hex(),
                "event_decimal": list(evt_bytes),
            })

        # Summary
        total_strikes = sum(len(e["expected_strikes"])
                            for e in track_out["music_bar_events"])
        print(f"Music-bar events: {len(track_out['music_bar_events'])}")
        print(f"Seg5 unused events: {len(track_out['unused_seg5_events'])}")
        print(f"Seg0 init events: {len(track_out['seg0_init_events'])}")
        print(f"Total ground-truth strikes (bars 1-4): {total_strikes}")
        print(f"MIDI notes expected: {len(notes)} → match={total_strikes == len(notes)}")

        # Show bar summaries
        bar_events = defaultdict(list)
        for e in track_out["music_bar_events"]:
            bar_events[e["bar"]].append(e)
        for bar in sorted(bar_events):
            evs = bar_events[bar]
            bar_strikes = sum(len(e["expected_strikes"]) for e in evs)
            print(f"  Bar {bar}: {len(evs)} events → {bar_strikes} strikes")

        print()
        output["tracks"][name] = track_out

    out_path = Path("midi_tools/captured/summer_ground_truth_v2.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
