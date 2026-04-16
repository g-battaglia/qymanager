#!/usr/bin/env python3
"""
Summer ground truth extractor (FULL, all 4 active tracks).

Links Summer's SysEx events per track to the exact MIDI notes captured during
playback (summer_playback_s25.json).

Track → MIDI channel mapping (PATT OUT 9~16, 1-based):
    RHY1 (AL=0x00) → ch9  : 62 drum notes (36,38,42)
    CHD1 (AL=0x03) → ch12 : 40 bass-voice notes (range 26-36)
    CHD2 (AL=0x04) → ch13 : 15 chord-voice notes (range 62-76)
    PHR1 (AL=0x05) → ch14 : silent (track muted or voice at 0 in header)
    PHR2 (AL=0x06) → ch15 : 40 phrase-voice notes (range 62-76)

Each RHY1 event spans 1 quarter-note beat (4 events × 5 bars = 20 events).
CHD/PHR tracks show 8 notes/bar on ch12/ch15 (one every 8th note) and 3
notes/bar on ch13 (chord hits).
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
PATTERN_BARS = 5
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

        print("=" * 72)
        print(f"{name} (AL=0x{al:02x}, ch{ch+1}) — "
              f"{len(track_bytes)} bytes SysEx, {len(notes)} MIDI notes")
        print("=" * 72)
        print(f"Preamble: {track_bytes[:28].hex()}")
        print(f"Events extracted: {len(events)}")

        # Group by segment for segmented tracks (RHY1, CHD1, PHR2)
        # or dump all events sequentially for single-segment tracks (CHD2, PHR1)
        by_seg = defaultdict(list)
        for si, ei, evt, hdr in events:
            by_seg[si].append((ei, evt))

        # Musical bars for each track:
        # Segmented tracks: si=1..5 → bars 1..5 (si=0 is padding)
        # Single-segment tracks: linearize, 12 events, 1 per beat × 5 bars (with some extras)
        is_segmented = len(by_seg) >= 5

        track_out = {
            "name": name,
            "al": al,
            "midi_channel_1based": ch + 1,
            "midi_note_count": len(notes),
            "preamble_hex": track_bytes[:28].hex(),
            "is_segmented": is_segmented,
            "events": [],
        }

        if is_segmented:
            for bar_idx in range(5):
                si = bar_idx + 1
                bar_start = bar_idx * BAR_S
                bar_end = bar_start + BAR_S
                bar_notes = [(t, n, v) for t, n, v in notes
                             if bar_start <= t < bar_end]

                # Slice notes per beat
                beat_notes = defaultdict(list)
                for t, n, v in bar_notes:
                    bar_t = t - bar_start
                    eighth = round(bar_t / (BEAT_S / 2))
                    beat = eighth // 2
                    sub = eighth % 2
                    if beat < 4:
                        beat_notes[beat].append((n, v, sub, t))

                for ei, evt_bytes in by_seg[si]:
                    expected = sorted(beat_notes.get(ei, []),
                                      key=lambda x: (x[2], x[0]))
                    track_out["events"].append({
                        "bar": bar_idx + 1,
                        "beat": ei + 1,
                        "event_hex": evt_bytes.hex(),
                        "event_decimal": list(evt_bytes),
                        "expected_strikes": [
                            {"note": n, "velocity": v, "subdivision_8th": s}
                            for n, v, s, _ in expected
                        ],
                    })
        else:
            # Single-segment encoding. Try to assign each event to a position.
            # Hypothesis: events are ordered sequentially in time.
            # For CHD2 (15 notes, 3/bar) and CHD1/PHR2 (40 notes, 8/bar),
            # this differs from RHY1's 4/bar.
            all_events = sorted(
                [(si, ei, evt) for si, evs in by_seg.items()
                 for ei, evt in evs],
                key=lambda x: (x[0], x[1])
            )
            for idx, (si, ei, evt_bytes) in enumerate(all_events):
                track_out["events"].append({
                    "event_index": idx,
                    "si": si,
                    "ei": ei,
                    "event_hex": evt_bytes.hex(),
                    "event_decimal": list(evt_bytes),
                })

            # Log all MIDI notes for reference
            track_out["midi_notes"] = [
                {"t": round(t, 6), "note": n, "velocity": v}
                for t, n, v in notes
            ]

        # Summary print
        if is_segmented:
            strikes_total = sum(len(e["expected_strikes"])
                                for e in track_out["events"])
            print(f"Structure: 4 events × 5 bars = {len(track_out['events'])} events")
            print(f"Total ground-truth strikes: {strikes_total}")
        else:
            print(f"Structure: linear (non-segmented), {len(all_events)} events")

        # Show first bar for inspection
        if is_segmented and track_out["events"]:
            print(f"\nBar 1 events:")
            for e in track_out["events"][:4]:
                print(f"  e{e['beat']-1}: {e['event_hex']}")
                for s in e["expected_strikes"]:
                    sub_lbl = "8th" if s["subdivision_8th"] == 0 else "8nd"
                    nm = {36: "KICK ", 38: "SNARE", 42: "HAT  "}.get(
                        s["note"], f"N{s['note']:3d}")
                    print(f"       → {nm} vel={s['velocity']:3d} ({sub_lbl})")

        print()
        output["tracks"][name] = track_out

    out_path = Path("midi_tools/captured/summer_ground_truth_full.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Saved full ground truth: {out_path}")


if __name__ == "__main__":
    main()
