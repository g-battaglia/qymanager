#!/usr/bin/env python3
"""
Full SGT capture rounds — autonomous RE of dense factory encoding.

Premise:
  - SGT loaded on QY70 (via external bulk from user)
  - Bulk write from PC doesn't overwrite (MIDI quirk)
  - Playback works via MIDI Clock → PATT OUT channels
  - Available QY70_SGT.syx bitstream file locally

Strategy:
  R1: Long capture (40s @ 151 BPM) current section as default
  R2: Second capture (verify determinism)
  R3: 8-bar tight capture
  R4: 16-bar capture for long sequences

Then offline analysis correlates captured MIDI with bitstream bytes.
Each SGT section = 768B decoded. Shared prefix 692B + 76B section-specific.
MAIN A playback duration @ 151 BPM: bars × 1.59s.

Output: data/sgt_rounds/R{N}/playback.json + raw.json
"""

import json
import sys
import time
import threading
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

OUT = Path(__file__).parent.parent / "data" / "sgt_rounds"


def find_port(direction, hint="porta 1"):
    import rtmidi
    m = rtmidi.MidiOut() if direction == "out" else rtmidi.MidiIn()
    for i in range(m.get_port_count()):
        if hint.lower() in m.get_port_name(i).lower():
            return i
    return 0 if m.get_port_count() > 0 else None


def capture(bars: int, bpm: int = 151, verbose: bool = False) -> list:
    """Trigger clock, capture all MIDI, return (t, bytes) list."""
    import rtmidi

    in_idx = find_port("in")
    out_idx = find_port("out")
    mi = rtmidi.MidiIn()
    mi.ignore_types(sysex=False, timing=True, active_sense=True)

    captured = []
    stop = [False]

    def listener():
        mi.open_port(in_idx)
        while not stop[0]:
            m = mi.get_message()
            if m:
                captured.append((time.time(), bytes(m[0])))
            else:
                time.sleep(0.0005)
        mi.close_port()

    t = threading.Thread(target=listener, daemon=True)
    t.start()
    time.sleep(0.3)

    # Drain stale
    time.sleep(0.3)
    captured.clear()

    mo = rtmidi.MidiOut()
    mo.open_port(out_idx)

    t0 = time.time()
    mo.send_message([0xFA])

    clock_interval = 60.0 / (bpm * 24)
    next_clock = time.time()
    duration = 60.0 / bpm * 4 * bars
    end = t0 + duration + 0.3
    while time.time() < end:
        now = time.time()
        while now >= next_clock:
            mo.send_message([0xF8])
            next_clock += clock_interval
        time.sleep(0.0005)
    mo.send_message([0xFC])
    mo.close_port()

    time.sleep(0.8)
    stop[0] = True
    t.join(timeout=1)

    return [(t - t0, d) for t, d in captured]


def analyze(events: list) -> dict:
    note_ons = []
    note_offs = []
    for t, data in events:
        if not data:
            continue
        s = data[0]
        if (s & 0xF0) == 0x90 and len(data) >= 3:
            ch = (s & 0x0F) + 1
            if data[2] > 0:
                note_ons.append({"t": round(t, 4), "ch": ch, "note": data[1], "vel": data[2]})
            else:
                note_offs.append({"t": round(t, 4), "ch": ch, "note": data[1]})
        elif (s & 0xF0) == 0x80 and len(data) >= 3:
            note_offs.append({"t": round(t, 4), "ch": (s & 0x0F) + 1, "note": data[1]})

    ch_notes = {}
    for n in note_ons:
        ch_notes.setdefault(n["ch"], []).append(n)

    return {
        "note_ons": note_ons,
        "note_offs": note_offs,
        "note_on_count": len(note_ons),
        "note_off_count": len(note_offs),
        "channels_with_notes": sorted(ch_notes.keys()),
        "notes_per_channel": {str(k): len(v) for k, v in ch_notes.items()},
        "unique_notes_per_channel": {
            str(k): sorted({n["note"] for n in v}) for k, v in ch_notes.items()
        },
    }


def run_round(rid: str, bars: int, bpm: int = 151):
    d = OUT / rid
    d.mkdir(parents=True, exist_ok=True)

    print(f"\n═══ {rid}: {bars} bars @ {bpm} BPM ═══")
    events = capture(bars, bpm)
    summary = analyze(events)
    summary["round"] = rid
    summary["bars"] = bars
    summary["bpm"] = bpm
    summary["total_msgs"] = len(events)

    (d / "playback.json").write_text(json.dumps(summary, indent=2))
    (d / "raw.json").write_text(json.dumps(
        [{"t": round(t, 4), "data": d.hex()} for t, d in events]
    ))

    print(f"  Total: {len(events)} msgs  Notes: {summary['note_on_count']}")
    for ch, n in sorted(summary["notes_per_channel"].items(), key=lambda x: int(x[0])):
        unique = summary["unique_notes_per_channel"][ch]
        print(f"    ch{ch:>2}: {n:>4} notes, unique: {unique}")
    return summary


def main():
    rounds = [
        ("R1_4bar",  4, 151),
        ("R2_8bar",  8, 151),
        ("R3_16bar", 16, 151),
        ("R4_4bar_verify", 4, 151),  # determinism check
    ]

    results = {}
    for i, (rid, bars, bpm) in enumerate(rounds):
        try:
            results[rid] = run_round(rid, bars, bpm)
        except Exception as e:
            print(f"  ERROR: {e}")
            results[rid] = {"error": str(e)}
        if i < len(rounds) - 1:
            time.sleep(2)

    # Determinism: R1 vs R4 (same duration, should match)
    if "R1_4bar" in results and "R4_4bar_verify" in results:
        r1 = results["R1_4bar"]
        r4 = results["R4_4bar_verify"]
        if "note_ons" in r1 and "note_ons" in r4:
            ns1 = [(n["ch"], n["note"]) for n in r1["note_ons"]]
            ns4 = [(n["ch"], n["note"]) for n in r4["note_ons"]]
            c1 = Counter(ns1)
            c4 = Counter(ns4)
            common = set(c1.keys()) & set(c4.keys())
            print(f"\n═══ Determinism R1 vs R4 ═══")
            print(f"  R1 unique (ch,note): {len(c1)}")
            print(f"  R4 unique (ch,note): {len(c4)}")
            print(f"  Overlap: {len(common)}")

    out = OUT / "_summary.json"
    out.write_text(json.dumps({
        rid: {k: v for k, v in r.items() if k not in ("note_ons", "note_offs")}
        for rid, r in results.items()
    }, indent=2))
    print(f"\n═══ Summary → {out} ═══")


if __name__ == "__main__":
    main()
