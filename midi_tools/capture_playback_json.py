#!/usr/bin/env python3
"""Capture QY70 playback to JSON with proper MIDI clock for external sync.

Improved version: saves machine-readable JSON with all note events,
channel mapping, and timing data. Use with external sync on QY70.

Usage:
  .venv/bin/python3 midi_tools/capture_playback_json.py \
    --bpm 120 --duration 12 -o midi_tools/captured/playback_capture_002.json

QY70 Setup:
  UTILITY → MIDI → MIDI SYNC: External
  UTILITY → MIDI → PATT OUT CH: 9~16
  UTILITY → MIDI → MIDI CONTROL: In/Out
"""
import sys
import time
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


SLOT_CH_MAP = {
    9: 'RHY1/D1', 10: 'RHY2/D2', 11: 'PAD/PC', 12: 'BASS/BA',
    13: 'CHD1/C1', 14: 'CHD2/C2', 15: 'PHR1/C3', 16: 'PHR2/C4',
}


def find_midi_ports():
    import mido
    out_ports = mido.get_output_names()
    in_ports = mido.get_input_names()
    out = next((p for p in out_ports if "steinberg" in p.lower() or "ur22" in p.lower()), None)
    inp = next((p for p in in_ports if "steinberg" in p.lower() or "ur22" in p.lower()), None)
    return inp, out


def main():
    import mido

    parser = argparse.ArgumentParser(description="Capture QY70 playback to JSON")
    parser.add_argument("--bpm", type=int, default=120)
    parser.add_argument("--duration", "-d", type=float, default=12.0)
    parser.add_argument("--output", "-o",
                        default="midi_tools/captured/playback_capture_002.json")
    args = parser.parse_args()

    in_name, out_name = find_midi_ports()
    if not in_name or not out_name:
        print("ERROR: MIDI ports not found")
        print(f"  OUT ports: {mido.get_output_names()}")
        print(f"  IN ports: {mido.get_input_names()}")
        return

    print(f"MIDI OUT: {out_name}")
    print(f"MIDI IN:  {in_name}")
    print(f"BPM: {args.bpm}, Duration: {args.duration}s")

    bpm = args.bpm
    clock_interval = 60.0 / (bpm * 24)
    ticks_per_beat = 24  # MIDI clock resolution
    tick_duration_ms = 60000.0 / (bpm * ticks_per_beat)

    all_events = []
    clock_count = 0

    with mido.open_input(in_name) as midi_in, mido.open_output(out_name) as midi_out:
        # Flush pending
        for _ in midi_in.iter_pending():
            pass

        # Send Start
        print(f"\nSending MIDI Start + Clock at {bpm} BPM...")
        midi_out.send(mido.Message('start'))
        t0 = time.time()
        next_clock = t0

        while time.time() - t0 < args.duration:
            now = time.time()

            # Send clocks
            while now >= next_clock:
                midi_out.send(mido.Message('clock'))
                clock_count += 1
                next_clock += clock_interval

            # Collect incoming messages
            for msg in midi_in.iter_pending():
                t = now - t0

                if msg.type == 'note_on':
                    ch = msg.channel + 1
                    all_events.append({
                        "time_sec": round(t, 4),
                        "type": "note_on",
                        "channel": ch,
                        "note": msg.note,
                        "velocity": msg.velocity,
                        "track": SLOT_CH_MAP.get(ch, f"ch{ch}"),
                    })
                    print(f"  {t:6.2f}s NOTE_ON  ch{ch:2d} ({SLOT_CH_MAP.get(ch, '?'):>10s}) "
                          f"n={msg.note:3d} v={msg.velocity:3d}")

                elif msg.type == 'note_off':
                    ch = msg.channel + 1
                    all_events.append({
                        "time_sec": round(t, 4),
                        "type": "note_off",
                        "channel": ch,
                        "note": msg.note,
                        "velocity": 0,
                        "track": SLOT_CH_MAP.get(ch, f"ch{ch}"),
                    })

                elif msg.type == 'control_change':
                    ch = msg.channel + 1
                    all_events.append({
                        "time_sec": round(t, 4),
                        "type": "cc",
                        "channel": ch,
                        "control": msg.control,
                        "value": msg.value,
                    })

                elif msg.type == 'program_change':
                    ch = msg.channel + 1
                    all_events.append({
                        "time_sec": round(t, 4),
                        "type": "pc",
                        "channel": ch,
                        "program": msg.program,
                    })

            time.sleep(0.0004)

        # Stop
        midi_out.send(mido.Message('stop'))
        time.sleep(0.3)

        # Collect remaining
        for msg in midi_in.iter_pending():
            t = time.time() - t0
            if msg.type == 'note_on':
                ch = msg.channel + 1
                all_events.append({
                    "time_sec": round(t, 4),
                    "type": "note_on",
                    "channel": ch,
                    "note": msg.note,
                    "velocity": msg.velocity,
                    "track": SLOT_CH_MAP.get(ch, f"ch{ch}"),
                })

    # Build result
    note_on_events = [e for e in all_events
                      if e["type"] == "note_on" and e.get("velocity", 0) > 0]

    # Per-channel summary
    channels = {}
    for e in note_on_events:
        ch = e["channel"]
        if ch not in channels:
            channels[ch] = {"notes": {}, "count": 0, "track": e.get("track", "?")}
        channels[ch]["count"] += 1
        n = e["note"]
        if n not in channels[ch]["notes"]:
            channels[ch]["notes"][n] = {"count": 0, "velocities": []}
        channels[ch]["notes"][n]["count"] += 1
        channels[ch]["notes"][n]["velocities"].append(e["velocity"])

    # Compute velocity ranges
    for ch_data in channels.values():
        for n_data in ch_data["notes"].values():
            vels = n_data["velocities"]
            n_data["vel_min"] = min(vels)
            n_data["vel_max"] = max(vels)
            n_data["vel_avg"] = round(sum(vels) / len(vels), 1)

    result = {
        "bpm": bpm,
        "duration": args.duration,
        "capture_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "clocks_sent": clock_count,
        "total_events": len(all_events),
        "note_on_count": len(note_on_events),
        "channels": {str(ch): channels[ch] for ch in sorted(channels)},
        "events": all_events,
    }

    # Save
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)

    # Print summary
    print(f"\n{'='*60}")
    print(f"  CAPTURE SUMMARY")
    print(f"{'='*60}")
    print(f"  Duration: {args.duration}s at {bpm} BPM")
    print(f"  Clocks sent: {clock_count}")
    print(f"  Total events: {len(all_events)}")
    print(f"  Note-on events: {len(note_on_events)}")
    print(f"  Active channels: {sorted(channels.keys())}")

    for ch in sorted(channels):
        ch_data = channels[ch]
        print(f"\n  ch{ch} ({ch_data['track']}): {ch_data['count']} notes")
        for n in sorted(ch_data["notes"], key=int):
            nd = ch_data["notes"][n]
            print(f"    note {n:3d}: {nd['count']:3d} events, "
                  f"vel {nd['vel_min']}-{nd['vel_max']} (avg {nd['vel_avg']})")

    print(f"\n  Saved to: {output_path}")


if __name__ == "__main__":
    main()
