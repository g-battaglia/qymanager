#!/usr/bin/env python3
"""Capture MIDI playback from QY70 style.

Sends MIDI Start to trigger style playback, captures all incoming MIDI
messages for a specified duration, then sends MIDI Stop.

Uses rtmidi directly (not mido) for all MIDI I/O — mido silently drops
SysEx on macOS CoreMIDI.

Usage:
    python3 midi_tools/capture_playback.py -d 10
    python3 midi_tools/capture_playback.py --bpm 133 --no-start
    python3 midi_tools/capture_playback.py --send-style tests/fixtures/QY70_SGT.syx
"""

import sys
import time
import json
import argparse
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def find_port_idx(midi_obj, preference="steinberg"):
    """Find MIDI port index by name preference."""
    for i in range(midi_obj.get_port_count()):
        name = midi_obj.get_port_name(i)
        if preference.lower() in name.lower():
            return i, name
    if midi_obj.get_port_count() > 0:
        return 0, midi_obj.get_port_name(0)
    return None, None


def send_style_blocking(mo, filepath, init_delay=0.5, msg_delay=0.15):
    """Send a .syx style file via an already-open rtmidi port."""
    from midi_tools.send_style import parse_syx_file

    messages = parse_syx_file(filepath)
    print(f"  Sending {len(messages)} SysEx messages from {filepath}")

    for i, (msg_bytes, info) in enumerate(messages):
        mo.send_message(list(msg_bytes))
        if info["type"] == "init":
            time.sleep(init_delay)
        elif info["type"] != "close":
            time.sleep(msg_delay)

    print(f"  Style sent ({len(messages)} messages)")
    return len(messages)


def capture_playback(
    duration_sec=5.0,
    bpm=120,
    verbose=True,
    send_start=True,
    style_path=None,
):
    """Start style playback on QY70 and capture MIDI output.

    Sends MIDI Start + Clock (24 ppqn) to drive QY70 in External sync mode.
    If style_path is given, sends the style first and waits for it to load.

    Returns list of (timestamp, raw_data) tuples.
    """
    import rtmidi

    mo = rtmidi.MidiOut()
    mi = rtmidi.MidiIn()
    mi.ignore_types(sysex=False, timing=True, active_sense=True)

    out_idx, out_name = find_port_idx(mo)
    in_idx, in_name = find_port_idx(mi)

    if out_idx is None or in_idx is None:
        print(f"ERROR: MIDI ports not found. Out={out_name}, In={in_name}")
        return []

    # 24 MIDI clocks per quarter note
    clock_interval = 60.0 / (bpm * 24)

    if verbose:
        print(f"Input:  {in_name}")
        print(f"Output: {out_name}")
        print(f"Duration: {duration_sec}s")
        print(f"Tempo: {bpm} BPM (clock interval: {clock_interval*1000:.1f}ms)")
        print()

    mo.open_port(out_idx)
    mi.open_port(in_idx)
    time.sleep(0.2)

    # Flush pending
    while mi.get_message():
        pass

    # Optional: send style first
    if style_path:
        print("── Sending style ──")
        send_style_blocking(mo, style_path)
        print("  Waiting 2s for QY70 to process...")
        time.sleep(2.0)
        # Flush any responses from style load
        load_responses = 0
        while mi.get_message():
            load_responses += 1
        if verbose:
            print(f"  Load responses flushed: {load_responses}")
        print()

    # Background listener thread
    captured = []
    stop_flag = threading.Event()

    def listener():
        while not stop_flag.is_set():
            msg = mi.get_message()
            if msg:
                data, delta = msg
                captured.append((time.time(), data))
            else:
                time.sleep(0.0005)

    listener_thread = threading.Thread(target=listener, daemon=True)
    listener_thread.start()

    t0 = time.time()

    # Send MIDI Start
    if send_start:
        if verbose:
            print("── Playback ──")
            print("  Sending MIDI Start (0xFA)...")
        mo.send_message([0xFA])

    # Send clocks and capture for the specified duration
    next_clock = time.time() + clock_interval
    beat_count = 0

    while time.time() - t0 < duration_sec:
        now = time.time()

        # Send clock pulses at the correct rate
        while now >= next_clock:
            mo.send_message([0xF8])
            next_clock += clock_interval

        # Progress every beat
        elapsed = now - t0
        current_beat = int(elapsed * bpm / 60)
        if current_beat > beat_count:
            beat_count = current_beat
            bar = beat_count // 4 + 1
            beat_in_bar = beat_count % 4 + 1
            note_count = sum(
                1
                for _, d in captured
                if len(d) >= 3 and d[0] & 0xF0 == 0x90 and d[2] > 0
            )
            if verbose:
                print(
                    f"  Bar {bar:2d} Beat {beat_in_bar} | "
                    f"notes: {note_count}, msgs: {len(captured)}"
                )

        time.sleep(0.0005)

    # Send MIDI Stop
    mo.send_message([0xFC])
    if verbose:
        print("  Sent MIDI Stop (0xFC)")

    # Capture remaining
    time.sleep(0.5)
    stop_flag.set()
    listener_thread.join(timeout=1.0)

    mo.close_port()
    mi.close_port()

    # Convert to relative timestamps
    return [(ts - t0, data) for ts, data in captured]


GM_DRUMS = {
    35: "Kick2",
    36: "Kick1",
    37: "SideStk",
    38: "Snare1",
    39: "Clap",
    40: "Snare2",
    42: "HHclose",
    44: "HHpedal",
    46: "HHopen",
    49: "Crash1",
    51: "Ride1",
    53: "RideBell",
    56: "Cowbell",
}


def analyze_capture(captured, verbose=True):
    """Analyze captured MIDI data."""
    # Classify all messages
    note_ons = []
    note_offs = []
    ccs = []
    pcs = []
    sysex = []
    other = []

    for t, data in captured:
        if not data:
            continue
        status = data[0]
        if status & 0xF0 == 0x90 and len(data) >= 3:
            ch = (status & 0x0F) + 1
            note, vel = data[1], data[2]
            if vel > 0:
                note_ons.append((t, ch, note, vel))
            else:
                note_offs.append((t, ch, note))
        elif status & 0xF0 == 0x80 and len(data) >= 3:
            ch = (status & 0x0F) + 1
            note_offs.append((t, ch, data[1]))
        elif status & 0xF0 == 0xB0 and len(data) >= 3:
            ch = (status & 0x0F) + 1
            ccs.append((t, ch, data[1], data[2]))
        elif status & 0xF0 == 0xC0 and len(data) >= 2:
            ch = (status & 0x0F) + 1
            pcs.append((t, ch, data[1]))
        elif status == 0xF0:
            sysex.append((t, data))
        elif status not in (0xF8, 0xFA, 0xFC, 0xFE):
            other.append((t, data))

    print(f"\n{'='*60}")
    print(f"  CAPTURE ANALYSIS")
    print(f"{'='*60}")
    print(f"  Total messages: {len(captured)}")
    print(f"  Note-ons: {len(note_ons)}")
    print(f"  Note-offs: {len(note_offs)}")
    print(f"  CC: {len(ccs)}")
    print(f"  Program Changes: {len(pcs)}")
    print(f"  SysEx: {len(sysex)}")

    # Program changes
    if pcs:
        print(f"\n  Program Changes:")
        for t, ch, prg in pcs:
            print(f"    t={t:6.3f}s ch{ch:2d} prg={prg}")

    # Note events by channel
    if note_ons:
        ch_notes = {}
        for t, ch, note, vel in note_ons:
            ch_notes.setdefault(ch, []).append((t, note, vel))

        # PATT OUT CH map (both 1~8 and 9~16)
        ch_map = {
            1: "D1/RHY1", 2: "D2/RHY2", 3: "PC/PAD", 4: "BA/BASS",
            5: "C1/CHD1", 6: "C2/CHD2", 7: "C3/PHR1", 8: "C4/PHR2",
            9: "D1/RHY1", 10: "D2/RHY2", 11: "PC/PAD", 12: "BA/BASS",
            13: "C1/CHD1", 14: "C2/CHD2", 15: "C3/PHR1", 16: "C4/PHR2",
        }

        print(f"\n  Notes by channel:")
        for ch in sorted(ch_notes.keys()):
            notes = ch_notes[ch]
            label = ch_map.get(ch, f"ch{ch}")
            print(f"\n    {label} (ch{ch}): {len(notes)} notes")

            # Show first N events
            for t, note, vel in notes[:16]:
                name = GM_DRUMS.get(note, f"n{note}") if ch in (1, 2, 3, 9, 10, 11) else f"n{note}"
                print(f"      t={t:6.3f}s {name:>8} ({note:3d}) v={vel:3d}")
            if len(notes) > 16:
                print(f"      ... ({len(notes) - 16} more)")

        # Unique notes summary
        print(f"\n  Unique notes per channel:")
        for ch in sorted(ch_notes.keys()):
            notes = ch_notes[ch]
            unique = sorted(set(n for _, n, _ in notes))
            label = ch_map.get(ch, f"ch{ch}")
            names = [GM_DRUMS.get(n, str(n)) for n in unique]
            print(f"    {label}: {names}")

    return {
        "note_ons": note_ons,
        "note_offs": note_offs,
        "ccs": ccs,
        "pcs": pcs,
        "sysex": sysex,
    }


def save_capture_json(captured, filepath):
    """Save captured data to JSON for later analysis."""
    events = []
    for t, data in captured:
        events.append({"t": round(t, 6), "data": list(data)})

    with open(filepath, "w") as f:
        json.dump(
            {"captured_at": time.strftime("%Y-%m-%d %H:%M:%S"), "events": events},
            f,
            indent=2,
        )
    print(f"Saved {len(events)} events to {filepath}")


def main():
    parser = argparse.ArgumentParser(description="Capture QY70 style playback via MIDI")
    parser.add_argument(
        "--duration",
        "-d",
        type=float,
        default=5.0,
        help="Capture duration in seconds (default: 5)",
    )
    parser.add_argument(
        "--bpm", type=int, default=120, help="Tempo in BPM for MIDI clock (default: 120)"
    )
    parser.add_argument(
        "--no-start",
        action="store_true",
        help="Don't send MIDI Start (listen to manual playback)",
    )
    parser.add_argument(
        "--send-style",
        type=str,
        default=None,
        help="Send .syx style file before starting playback",
    )
    parser.add_argument(
        "--save-json",
        type=str,
        default=None,
        help="Save capture to JSON file",
    )
    parser.add_argument("--quiet", "-q", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("  QY70 STYLE PLAYBACK CAPTURE (rtmidi)")
    print("=" * 60)
    print()

    captured = capture_playback(
        args.duration,
        bpm=args.bpm,
        verbose=not args.quiet,
        send_start=not args.no_start,
        style_path=args.send_style,
    )

    print(f"\nTotal captured messages: {len(captured)}")
    result = analyze_capture(captured, verbose=not args.quiet)

    if args.save_json:
        save_capture_json(captured, args.save_json)


if __name__ == "__main__":
    main()
