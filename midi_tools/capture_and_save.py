#!/usr/bin/env python3
"""Capture QY70 playback + optional bulk dump, save results.

Usage:
  # Capture playback for 12 seconds at 120 BPM
  .venv/bin/python3 midi_tools/capture_and_save.py --bpm 120 -d 12

  # Then trigger bulk dump on QY70: UTILITY → Bulk Dump → Style
  # Script waits for SysEx data after playback capture
"""
import sys
import time
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def find_midi_ports():
    import mido
    out_ports = mido.get_output_names()
    in_ports = mido.get_input_names()
    out = next((p for p in out_ports if "steinberg" in p.lower() or "ur22" in p.lower()), None)
    inp = next((p for p in in_ports if "steinberg" in p.lower() or "ur22" in p.lower()), None)
    return inp, out


def main():
    import mido

    parser = argparse.ArgumentParser()
    parser.add_argument("--bpm", type=int, default=120)
    parser.add_argument("--duration", "-d", type=float, default=12.0)
    parser.add_argument("--output", "-o", default="midi_tools/captured/playback_capture.json")
    parser.add_argument("--dump-wait", type=float, default=0,
                        help="Seconds to wait for bulk dump after playback (0=skip)")
    args = parser.parse_args()

    in_name, out_name = find_midi_ports()
    if not in_name or not out_name:
        print("ERROR: MIDI ports not found")
        return

    bpm = args.bpm
    clock_interval = 60.0 / (bpm * 24)

    print(f"Capturing at {bpm} BPM for {args.duration}s...")

    all_events = []

    with mido.open_input(in_name) as midi_in, mido.open_output(out_name) as midi_out:
        for _ in midi_in.iter_pending():
            pass

        # Send Start + Clock
        midi_out.send(mido.Message('start'))
        t0 = time.time()
        next_clock = t0

        while time.time() - t0 < args.duration:
            now = time.time()
            while now >= next_clock:
                midi_out.send(mido.Message('clock'))
                next_clock += clock_interval
            for msg in midi_in.iter_pending():
                t = now - t0
                if msg.type == 'note_on':
                    all_events.append({
                        "time": round(t, 4),
                        "type": "note_on",
                        "channel": msg.channel + 1,
                        "note": msg.note,
                        "velocity": msg.velocity
                    })
                elif msg.type == 'control_change':
                    all_events.append({
                        "time": round(t, 4),
                        "type": "cc",
                        "channel": msg.channel + 1,
                        "control": msg.control,
                        "value": msg.value
                    })
                elif msg.type == 'program_change':
                    all_events.append({
                        "time": round(t, 4),
                        "type": "pc",
                        "channel": msg.channel + 1,
                        "program": msg.program
                    })
            time.sleep(0.0004)

        midi_out.send(mido.Message('stop'))
        time.sleep(0.3)
        for msg in midi_in.iter_pending():
            t = time.time() - t0
            if msg.type == 'note_on':
                all_events.append({
                    "time": round(t, 4),
                    "type": "note_on",
                    "channel": msg.channel + 1,
                    "note": msg.note,
                    "velocity": msg.velocity
                })

    # Save
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result = {
        "bpm": bpm,
        "duration": args.duration,
        "capture_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "events": all_events
    }

    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)

    # Stats
    note_events = [e for e in all_events if e["type"] == "note_on" and e["velocity"] > 0]
    channels = set(e["channel"] for e in note_events)
    print(f"\nSaved {len(all_events)} events to {output_path}")
    print(f"Note-on events (vel>0): {len(note_events)}")
    print(f"Active channels: {sorted(channels)}")

    for ch in sorted(channels):
        ch_notes = [e for e in note_events if e["channel"] == ch]
        unique = sorted(set(e["note"] for e in ch_notes))
        print(f"  ch{ch:2d}: {len(ch_notes)} notes, unique: {unique}")


if __name__ == "__main__":
    main()
