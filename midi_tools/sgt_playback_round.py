#!/usr/bin/env python3
"""
SGT playback capture round.

QY70 has SGT loaded via external bulk. PATT OUT configured.
Trigger MIDI Clock → capture notes → save as ground truth.

Rounds:
  R1: 4-bar capture @ 151 BPM (SGT default) on current section
  R2: 8-bar capture
  R3: 16-bar capture for longer analysis

Output: data/sgt_rounds/R{n}/playback.json
"""

import json
import sys
import time
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

OUT = Path(__file__).parent.parent / "data" / "sgt_rounds"


def find_port(direction, hint="porta 1"):
    import rtmidi
    m = rtmidi.MidiOut() if direction == "out" else rtmidi.MidiIn()
    for i in range(m.get_port_count()):
        if hint.lower() in m.get_port_name(i).lower():
            return i
    return 0 if m.get_port_count() > 0 else None


def playback_capture(bars: int, bpm: int = 151) -> list:
    """Trigger MIDI Clock, capture all MIDI for bars. Return (t, data) list."""
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

    # Drain stale messages
    pre_count = len(captured)
    time.sleep(0.5)
    drained = len(captured) - pre_count
    if drained:
        print(f"  (drained {drained} stale msgs)")
    captured.clear()

    mo = rtmidi.MidiOut()
    mo.open_port(out_idx)

    t0 = time.time()
    print(f"  MIDI Start @ t0, {bars} bars @ {bpm} BPM")
    mo.send_message([0xFA])

    clock_interval = 60.0 / (bpm * 24)
    next_clock = time.time()
    duration = 60.0 / bpm * 4 * bars
    end = t0 + duration + 0.2
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
    """Extract note events + stats."""
    note_ons = []
    note_offs = []
    cc = []
    pc = []
    sysex = []

    for t, data in events:
        if not data:
            continue
        s = data[0]
        if (s & 0xF0) == 0x90 and len(data) >= 3 and data[2] > 0:
            note_ons.append({"t": round(t, 4), "ch": (s & 0x0F) + 1,
                             "note": data[1], "vel": data[2]})
        elif ((s & 0xF0) == 0x90 and len(data) >= 3 and data[2] == 0) \
             or ((s & 0xF0) == 0x80 and len(data) >= 3):
            note_offs.append({"t": round(t, 4), "ch": (s & 0x0F) + 1,
                              "note": data[1]})
        elif (s & 0xF0) == 0xB0 and len(data) >= 3:
            cc.append({"t": round(t, 4), "ch": (s & 0x0F) + 1,
                       "cc": data[1], "val": data[2]})
        elif (s & 0xF0) == 0xC0 and len(data) >= 2:
            pc.append({"t": round(t, 4), "ch": (s & 0x0F) + 1, "prg": data[1]})
        elif s == 0xF0:
            sysex.append({"t": round(t, 4), "hex": data.hex()})

    # Per-channel note stats
    ch_notes = {}
    for n in note_ons:
        ch_notes.setdefault(n["ch"], []).append(n)

    return {
        "total": len(events),
        "note_ons": note_ons,
        "note_offs": note_offs,
        "cc": cc[:50],  # trim
        "pc": pc,
        "sysex": sysex,
        "note_on_count": len(note_ons),
        "note_off_count": len(note_offs),
        "cc_count": len(cc),
        "pc_count": len(pc),
        "sysex_count": len(sysex),
        "channels_with_notes": sorted(ch_notes.keys()),
        "notes_per_channel": {str(ch): len(v) for ch, v in ch_notes.items()},
    }


def run_round(round_id: str, bars: int, bpm: int = 151):
    d = OUT / round_id
    d.mkdir(parents=True, exist_ok=True)
    print(f"\n═══ Round {round_id}: {bars} bars @ {bpm} BPM ═══")

    events = playback_capture(bars, bpm)
    print(f"  Captured {len(events)} msgs")

    summary = analyze(events)
    summary["round_id"] = round_id
    summary["bars"] = bars
    summary["bpm"] = bpm

    (d / "playback.json").write_text(json.dumps(summary, indent=2))

    # Raw capture too
    raw = [{"t": round(t, 4), "data": data.hex()} for t, data in events]
    (d / "raw.json").write_text(json.dumps(raw))

    print(f"  Note-ons: {summary['note_on_count']}  CC: {summary['cc_count']}  "
          f"PC: {summary['pc_count']}  SysEx: {summary['sysex_count']}")
    print(f"  Channels with notes: {summary['channels_with_notes']}")
    if summary["notes_per_channel"]:
        for ch, n in sorted(summary["notes_per_channel"].items(), key=lambda x: int(x[0])):
            print(f"    ch{ch}: {n} notes")

    if summary["note_ons"]:
        print(f"\n  First 15 note-ons:")
        for n in summary["note_ons"][:15]:
            print(f"    t={n['t']:6.3f}s  ch{n['ch']:>2}  n{n['note']:>3}  v{n['vel']:>3}")

    return summary


def main():
    rounds = [
        ("R1_4bar_first", 4, 151),
        ("R2_8bar_verify", 8, 151),
        ("R3_16bar_deep", 16, 151),
    ]

    results = {}
    for i, (rid, bars, bpm) in enumerate(rounds):
        try:
            results[rid] = run_round(rid, bars, bpm)
        except Exception as e:
            print(f"  ERROR: {e}")
            results[rid] = {"error": str(e)}
        if i < len(rounds) - 1:
            print(f"\n  Inter-round wait 3s...")
            time.sleep(3)

    (OUT / "_rounds_summary.json").write_text(json.dumps({
        rid: {k: v for k, v in r.items() if k not in ("note_ons", "note_offs", "cc", "sysex")}
        for rid, r in results.items()
    }, indent=2))
    print(f"\n═══ Summary → {OUT}/_rounds_summary.json ═══")


if __name__ == "__main__":
    main()
