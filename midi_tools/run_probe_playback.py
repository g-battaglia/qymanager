#!/usr/bin/env python3
"""
Probe runner with playback trigger + note capture.

Per probe:
  1. Build sparse-encoded pattern
  2. Send to QY70 edit buffer (AM=0x7E)
  3. Send MIDI Start (0xFA) + Clock (0xF8) at specified BPM for N bars
  4. Send MIDI Stop (0xFC)
  5. Capture all MIDI during playback
  6. Extract note events, compare with input events
  7. Save artifacts

Requires on QY70:
  - PATT OUT CH = 9~16
  - ECHO BACK = Off
  - MIDI SYNC = External
"""

import argparse
import json
import sys
import time
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from midi_tools.probe_runner import (
    PROBES, Probe, build_probe_syx, find_port,
)

PROBES_DIR = Path(__file__).parent.parent / "data" / "probes_pb"


def send_then_play(sent_syx: bytes, bars: int, bpm: int = 120) -> list:
    """Send pattern, auto-start clock, capture everything. Return list of (t, data) tuples."""
    import rtmidi

    in_idx = find_port("in")
    out_idx = find_port("out")
    if in_idx is None or out_idx is None:
        raise RuntimeError("MIDI ports not found")

    mi = rtmidi.MidiIn()
    mi.ignore_types(sysex=False, timing=True, active_sense=True)

    captured: list = []
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

    t_thread = threading.Thread(target=listener, daemon=True)
    t_thread.start()
    time.sleep(0.3)

    mo = rtmidi.MidiOut()
    mo.open_port(out_idx)

    # Parse sent_syx into messages
    msgs = []
    i = 0
    while i < len(sent_syx):
        if sent_syx[i] != 0xF0:
            i += 1
            continue
        j = i + 1
        while j < len(sent_syx) and sent_syx[j] != 0xF7:
            j += 1
        msgs.append(sent_syx[i:j + 1])
        i = j + 1

    # Step 1: Send bulk
    print(f"  Sending {len(msgs)} SysEx messages...")
    for m in msgs:
        mo.send_message(list(m))
        is_init = len(m) == 9 and m[7] == 0x01
        is_close = len(m) == 9 and m[7] == 0x00
        if is_init:
            time.sleep(0.5)
        elif is_close:
            time.sleep(0.1)
        else:
            time.sleep(0.15)

    # Let QY70 process
    print(f"  Waiting 2s for QY70 load...")
    time.sleep(2.0)

    # Step 2: Send MIDI Start + Clock for N bars
    t_start = time.time()
    t0 = t_start  # record as playback start reference
    beats_to_play = bars * 4
    seconds_to_play = 60.0 / bpm * beats_to_play
    clock_interval = 60.0 / (bpm * 24)

    print(f"  MIDI Start: playing {bars} bars @ {bpm} BPM ({seconds_to_play:.2f}s)")
    mo.send_message([0xFA])  # Start

    next_clock = time.time()
    end_time = t_start + seconds_to_play + 0.5  # pad 0.5s
    while time.time() < end_time:
        now = time.time()
        while now >= next_clock:
            mo.send_message([0xF8])
            next_clock += clock_interval
        time.sleep(0.0005)

    mo.send_message([0xFC])  # Stop
    mo.close_port()

    time.sleep(1.0)  # let any late events land
    stop[0] = True
    t_thread.join(timeout=1)

    # Return (time_since_playback_start, data)
    return [(t - t0, d) for t, d in captured]


def classify_playback(events: list) -> dict:
    """Extract note events from captured playback."""
    note_ons = []
    note_offs = []
    for t, data in events:
        if not data:
            continue
        status = data[0]
        if (status & 0xF0) == 0x90 and len(data) >= 3 and data[2] > 0:
            note_ons.append({"t": round(t, 4), "ch": (status & 0x0F) + 1,
                             "note": data[1], "vel": data[2]})
        elif ((status & 0xF0) == 0x90 and len(data) >= 3 and data[2] == 0) \
             or ((status & 0xF0) == 0x80 and len(data) >= 3):
            note_offs.append({"t": round(t, 4), "ch": (status & 0x0F) + 1,
                              "note": data[1]})
    return {
        "note_ons": note_ons,
        "note_offs": note_offs,
        "note_on_count": len(note_ons),
        "note_off_count": len(note_offs),
    }


def run(probe_id: str, bars: int = None, bpm: int = 120) -> dict:
    probe = PROBES.get(probe_id)
    if probe is None:
        return {"error": f"probe {probe_id} not defined"}
    if bars is None:
        bars = max(1, probe.bars)

    d = PROBES_DIR / probe_id
    d.mkdir(parents=True, exist_ok=True)

    sent_syx = build_probe_syx(probe)
    (d / "sent.syx").write_bytes(sent_syx)
    (d / "spec.json").write_text(json.dumps(probe.to_dict(), indent=2, default=str))

    print(f"\n═══ Probe {probe_id} ({probe.description}) ═══")
    print(f"  Input events: {len(probe.events)}, Bars: {bars}, BPM: {bpm}")

    events = send_then_play(sent_syx, bars, bpm)

    summary = classify_playback(events)
    summary["input_events"] = [{"note": e.note, "vel": e.velocity,
                                 "gate": e.gate, "tick": e.tick}
                                for e in probe.events]
    summary["probe_id"] = probe_id
    summary["bars"] = bars
    summary["bpm"] = bpm
    summary["total_captured"] = len(events)

    (d / "playback.json").write_text(json.dumps(summary, indent=2))

    # Save raw capture
    raw_list = [{"t": round(t, 4), "data": d.hex()} for t, d in events]
    (d / "raw.json").write_text(json.dumps(raw_list))

    print(f"  Captured: {len(events)} total msgs, {summary['note_on_count']} note-ons")
    if summary["note_ons"]:
        print(f"  First 5 note-ons:")
        for n in summary["note_ons"][:5]:
            print(f"    t={n['t']:.3f}s ch{n['ch']} n{n['note']} v{n['vel']}")
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("probes", nargs="*", default=None)
    ap.add_argument("--bpm", type=int, default=120)
    ap.add_argument("--bars", type=int, default=None, help="override bars per probe")
    ap.add_argument("--interprobe-wait", type=float, default=3.0)
    args = ap.parse_args()

    if not args.probes:
        args.probes = ["P00_empty", "P01_kick_b1", "P02_kick_b2", "P03_kick_b3",
                       "P04_kick_b4", "P05_snare_b1", "P06_hh_b1",
                       "P07_kick_vel119", "P08_kick_vel95", "P09_kick_gate120",
                       "P11_2events_same_bar", "P12_dense_4events"]

    print(f"═══ Playback probe chain: {len(args.probes)} probes @ {args.bpm} BPM ═══")

    all_results = {}
    for i, pid in enumerate(args.probes):
        print(f"\n[{i+1}/{len(args.probes)}] {pid}")
        try:
            result = run(pid, bars=args.bars, bpm=args.bpm)
            all_results[pid] = result
        except Exception as e:
            all_results[pid] = {"error": str(e)}
            print(f"  ERROR: {e}")

        if i < len(args.probes) - 1:
            print(f"  Waiting {args.interprobe_wait}s...")
            time.sleep(args.interprobe_wait)

    out = PROBES_DIR / "_chain_results.json"
    out.write_text(json.dumps(all_results, indent=2))
    print(f"\n═══ Aggregate → {out} ═══")
    print(f"\n{'Probe':30s} {'Input':>6} {'NoteOn':>7} {'NoteOff':>8}")
    for pid in args.probes:
        r = all_results.get(pid, {})
        in_n = len(r.get("input_events", []))
        on = r.get("note_on_count", 0)
        off = r.get("note_off_count", 0)
        print(f"{pid:30s} {in_n:>6} {on:>7} {off:>8}")


if __name__ == "__main__":
    main()
