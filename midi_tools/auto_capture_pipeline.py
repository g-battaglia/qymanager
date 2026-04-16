#!/usr/bin/env python3
"""Automated Pipeline B: Send → Capture → Quantize → Convert.

One-shot script that performs the complete Pipeline B workflow:
1. Checks MIDI connectivity
2. Sends a .syx style to QY70
3. Starts MIDI playback (Start + Clock)
4. Captures notes for the specified duration
5. Quantizes to beat grid
6. Generates SMF + Q7P + phrase data

Prerequisites:
  - Steinberg UR22C connected via USB
  - QY70 powered on, PATT OUT=9~16, ECHO BACK=Off, MIDI SYNC=External
  - .venv activated

Usage:
    .venv/bin/python3 midi_tools/auto_capture_pipeline.py tests/fixtures/QY70_SGT.syx -b 151 -n 6 -d 15
    .venv/bin/python3 midi_tools/auto_capture_pipeline.py style.syx --output-dir midi_tools/captured/my_style
"""

import argparse
import json
import os
import struct
import sys
import time
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_midi_ports():
    """Check MIDI port availability. Returns (in_port, out_port) names or raises."""
    import rtmidi
    mi = rtmidi.MidiIn()
    mo = rtmidi.MidiOut()
    in_ports = mi.get_ports()
    out_ports = mo.get_ports()

    if not in_ports or not out_ports:
        print("ERROR: No MIDI ports found.")
        print(f"  IN:  {in_ports or '(none)'}")
        print(f"  OUT: {out_ports or '(none)'}")
        print()
        print("Check:")
        print("  1. Steinberg UR22C is connected via USB")
        print("  2. QY70 is powered on")
        print("  3. MIDI cables: QY70 OUT → UR22C IN, UR22C OUT → QY70 IN")
        sys.exit(1)

    # Find Steinberg port (or first available)
    in_port = next((p for p in in_ports if "Steinberg" in p or "UR22" in p), in_ports[0])
    out_port = next((p for p in out_ports if "Steinberg" in p or "UR22" in p), out_ports[0])
    return in_port, out_port


def send_sysex_file(out_port_name: str, syx_path: str,
                    init_delay: float = 1.0, msg_delay: float = 0.3):
    """Send a .syx file to QY70 via rtmidi."""
    import rtmidi

    with open(syx_path, "rb") as f:
        syx_data = f.read()

    # Parse individual SysEx messages
    messages = []
    i = 0
    while i < len(syx_data):
        if syx_data[i] == 0xF0:
            end = syx_data.index(0xF7, i) + 1
            messages.append(syx_data[i:end])
            i = end
        else:
            i += 1

    print(f"Sending {len(messages)} SysEx messages to {out_port_name}...")
    mo = rtmidi.MidiOut()
    ports = mo.get_ports()
    port_idx = ports.index(out_port_name) if out_port_name in ports else 0
    mo.open_port(port_idx)

    for i, msg in enumerate(messages):
        mo.send_message(list(msg))
        if i == 0:
            time.sleep(init_delay)
        else:
            time.sleep(msg_delay)

    mo.close_port()
    print(f"  Sent {len(messages)} messages ({len(syx_data)} bytes)")
    return len(messages)


def capture_playback(in_port_name: str, out_port_name: str,
                     bpm: float, duration: float, bars: int,
                     style_name: str = "unknown") -> dict:
    """Start MIDI playback and capture notes.

    Sends MIDI Start + Clock to trigger QY70 playback,
    captures all incoming notes for the specified duration.
    """
    import rtmidi

    # Open input
    mi = rtmidi.MidiIn()
    ports = mi.get_ports()
    port_idx = ports.index(in_port_name) if in_port_name in ports else 0
    mi.open_port(port_idx)
    mi.ignore_types(sysex=True, timing=True, active_sense=True)

    # Open output for clock
    mo = rtmidi.MidiOut()
    ports = mo.get_ports()
    out_idx = ports.index(out_port_name) if out_port_name in ports else 0
    mo.open_port(out_idx)

    # Calculate clock interval (24 PPQN)
    clock_interval = 60.0 / (bpm * 24)
    total_clocks = int(duration / clock_interval)

    print(f"Starting playback: {bpm} BPM, {duration}s ({total_clocks} clocks)")
    print(f"  Clock interval: {clock_interval*1000:.1f}ms")

    # Collect raw events
    raw_events = []
    t0 = time.time()

    # Send MIDI Start (0xFA)
    mo.send_message([0xFA])
    time.sleep(0.001)

    # Send clocks and capture
    for _ in range(total_clocks):
        mo.send_message([0xF8])  # MIDI Clock

        # Read all pending input messages
        while True:
            msg = mi.get_message()
            if msg is None:
                break
            data, delta = msg
            raw_events.append({
                "t": round(time.time() - t0, 6),
                "data": data,
            })

        time.sleep(clock_interval)

    # Send MIDI Stop (0xFC)
    mo.send_message([0xFC])
    time.sleep(0.1)

    # Drain remaining messages
    while True:
        msg = mi.get_message()
        if msg is None:
            break
        data, delta = msg
        raw_events.append({
            "t": round(time.time() - t0, 6),
            "data": data,
        })

    mi.close_port()
    mo.close_port()

    elapsed = time.time() - t0
    print(f"  Captured {len(raw_events)} events in {elapsed:.1f}s")

    # Diagnostic: count event types
    note_on_count = 0
    note_off_count = 0
    ch_counts = {}
    for ev in raw_events:
        d = ev["data"]
        status = d[0] & 0xF0
        ch = (d[0] & 0x0F) + 1
        if status == 0x90 and len(d) >= 3 and d[2] > 0:
            note_on_count += 1
            ch_counts[ch] = ch_counts.get(ch, 0) + 1
        elif status == 0x80 or (status == 0x90 and len(d) >= 3 and d[2] == 0):
            note_off_count += 1

    print(f"  Note ON: {note_on_count}, Note OFF: {note_off_count}")
    if ch_counts:
        print(f"  Channel note_on counts: {ch_counts}")
    else:
        print("  WARNING: No notes captured!")

    return {
        "style": style_name,
        "bpm": bpm,
        "duration": duration,
        "channels": ch_counts,
        "raw": raw_events,
    }


def main(args):
    """Run the complete pipeline."""
    output_dir = Path(args.output_dir or f"midi_tools/captured/{Path(args.syx_file).stem}")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Check MIDI
    print("=" * 60)
    print("Step 1: Checking MIDI connectivity")
    in_port, out_port = check_midi_ports()
    print(f"  IN:  {in_port}")
    print(f"  OUT: {out_port}")
    print()

    # Step 2: Send style to QY70
    if args.skip_send:
        print("Step 2: SKIPPED (--skip-send)")
    else:
        print("Step 2: Sending style to QY70")
        send_sysex_file(out_port, args.syx_file)
        print(f"  Waiting {args.load_delay}s for QY70 to load...")
        time.sleep(args.load_delay)
    print()

    # Step 3: Capture playback
    print("Step 3: Capturing MIDI playback")
    capture = capture_playback(in_port, out_port, args.bpm, args.duration, args.bars,
                               style_name=os.path.basename(args.syx_file))
    capture_path = output_dir / "capture.json"
    with open(capture_path, "w") as f:
        json.dump(capture, f, indent=2)
    print(f"  Saved: {capture_path}")
    print()

    # Check if we got any notes
    if not capture["channels"]:
        print("=" * 60)
        print("ABORT: No notes captured. Possible causes:")
        print("  1. Pattern not loaded on QY70 (send failed or wrong slot)")
        print("  2. PATT OUT not set to 9~16 on QY70")
        print("  3. QY70 not in Pattern mode")
        print("  4. MIDI cable issue (QY70 OUT → UR22C IN)")
        print(f"  Raw events saved to: {capture_path}")
        print()
        print("Retry with --skip-send if pattern is already loaded.")
        sys.exit(1)

    # Step 4: Quantize and convert
    print("Step 4: Quantizing and converting")
    from midi_tools.quantizer import quantize_capture
    from midi_tools.capture_to_q7p import write_smf, write_q7p_metadata, encode_phrase_events

    pattern = quantize_capture(
        str(capture_path),
        bpm=args.bpm,
        bar_count=args.bars,
    )
    print(pattern.summary())
    print()

    # Generate outputs
    prefix = str(output_dir / "output")

    smf_path = f"{prefix}.mid"
    write_smf(pattern, smf_path)
    print(f"  SMF: {smf_path}")

    q7p_path = f"{prefix}.Q7P"
    write_q7p_metadata(pattern, output_path=q7p_path)
    print(f"  Q7P: {q7p_path}")

    # Phrase data
    phrases_path = f"{prefix}_phrases.bin"
    total_bytes = 0
    with open(phrases_path, "wb") as f:
        for track in pattern.active_tracks:
            phrase_data = encode_phrase_events(track, pattern)
            track_header = struct.pack(">BBH", track.track_idx, track.channel,
                                       len(phrase_data))
            f.write(track_header)
            f.write(phrase_data)
            total_bytes += len(phrase_data)
    print(f"  Phrases: {phrases_path} ({total_bytes} bytes)")

    print()
    print("=" * 60)
    print(f"Pipeline complete! {len(pattern.active_tracks)} tracks, "
          f"{sum(len(t.notes) for t in pattern.active_tracks)} notes")
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automated Pipeline B")
    parser.add_argument("syx_file", help="Path to .syx style file")
    parser.add_argument("-b", "--bpm", type=float, required=True, help="BPM")
    parser.add_argument("-n", "--bars", type=int, default=6, help="Bars per section")
    parser.add_argument("-d", "--duration", type=float, default=15.0,
                       help="Capture duration in seconds")
    parser.add_argument("-o", "--output-dir", help="Output directory")
    parser.add_argument("--load-delay", type=float, default=3.0,
                       help="Seconds to wait after sending style")
    parser.add_argument("--skip-send", action="store_true",
                       help="Skip sending .syx, assume pattern already loaded")

    args = parser.parse_args()

    if not os.path.exists(args.syx_file):
        print(f"ERROR: File not found: {args.syx_file}")
        sys.exit(1)

    main(args)
