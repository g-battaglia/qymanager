#!/usr/bin/env python3
"""Send a style to QY70 and capture playback output.

Combined workflow:
  1. Send .syx bulk dump to QY70 (confirmed working: 160 XG param responses)
  2. Wait for user to select the loaded style and press Play on QY70
  3. Capture MIDI output on PATT OUT CH channels
  4. Save captured data as JSON for analysis

Usage:
    # Send style, then capture (manual playback by user)
    python3 midi_tools/send_and_capture.py tests/fixtures/QY70_SGT.syx

    # Just capture (style already loaded, user presses Play)
    python3 midi_tools/send_and_capture.py --capture-only -d 10

    # Send + auto-start (External sync mode on QY70)
    python3 midi_tools/send_and_capture.py my_style.syx --auto-start --bpm 120

Note: QY70 must be in Pattern mode or Style mode to play the loaded style.
      PATT OUT CH must be set to 9~16 (or 1~8) in UTILITY → MIDI.
      For --auto-start, QY70 MIDI SYNC must be set to External.
"""

import sys
import time
import json
import argparse
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def open_midi_ports():
    """Open rtmidi input and output on Steinberg UR22C Porta 1."""
    import rtmidi

    mo = rtmidi.MidiOut()
    mi = rtmidi.MidiIn()
    mi.ignore_types(sysex=False, timing=True, active_sense=True)

    # Find Porta 1 (prefer first Steinberg match)
    out_idx = in_idx = None
    for i in range(mo.get_port_count()):
        name = mo.get_port_name(i)
        if "steinberg" in name.lower() or "ur22" in name.lower():
            out_idx = i
            break
    for i in range(mi.get_port_count()):
        name = mi.get_port_name(i)
        if "steinberg" in name.lower() or "ur22" in name.lower():
            in_idx = i
            break

    if out_idx is None or in_idx is None:
        print("ERROR: Steinberg UR22C not found")
        return None, None

    mo.open_port(out_idx)
    mi.open_port(in_idx)
    time.sleep(0.3)

    # Flush pending
    while mi.get_message():
        pass

    print(f"MIDI Out: {mo.get_port_name(out_idx)}")
    print(f"MIDI In:  {mi.get_port_name(in_idx)}")
    return mo, mi


def send_style(mo, mi, filepath):
    """Send a .syx file and count load responses."""
    from midi_tools.send_style import parse_syx_file

    messages = parse_syx_file(filepath)
    print(f"\nSending {len(messages)} SysEx messages from {filepath}")
    print(f"  Timing: 500ms init, 150ms between bulk msgs")

    for i, (msg_bytes, info) in enumerate(messages):
        mo.send_message(list(msg_bytes))
        if info["type"] == "init":
            time.sleep(0.5)
        elif info["type"] != "close":
            time.sleep(0.15)

    print(f"  Done. Waiting 3s for QY70 to process...")
    time.sleep(3.0)

    # Count load responses
    load_responses = 0
    sysex = cc = pc = 0
    while True:
        msg = mi.get_message()
        if msg is None:
            break
        load_responses += 1
        data = msg[0]
        if data[0] == 0xF0:
            sysex += 1
        elif data[0] & 0xF0 == 0xB0:
            cc += 1
        elif data[0] & 0xF0 == 0xC0:
            pc += 1

    print(f"  QY70 responses: {load_responses} (SysEx:{sysex} CC:{cc} PC:{pc})")
    if load_responses > 10:
        print("  *** STYLE LOADED SUCCESSFULLY ***")
        return True
    else:
        print("  WARNING: Few responses — style may not have loaded")
        print("  Check: QY70 at main screen (not in menu)")
        return False


def capture_with_listener(mi, mo, duration_sec, auto_start=False, bpm=120):
    """Capture MIDI output with background listener."""
    captured = []
    stop_flag = threading.Event()

    def listener():
        while not stop_flag.is_set():
            msg = mi.get_message()
            if msg:
                captured.append((time.time(), msg[0]))
            else:
                time.sleep(0.0005)

    t = threading.Thread(target=listener, daemon=True)
    t.start()
    t0 = time.time()

    if auto_start:
        print(f"\n  Auto-start: MIDI Start + Clock at {bpm} BPM")
        mo.send_message([0xFA])
        clock_interval = 60.0 / (bpm * 24)
        next_clock = time.time() + clock_interval

        while time.time() - t0 < duration_sec:
            now = time.time()
            while now >= next_clock:
                mo.send_message([0xF8])
                next_clock += clock_interval
            time.sleep(0.0005)

        mo.send_message([0xFC])
    else:
        # Passive capture — wait for user to trigger playback
        beat_check = 0
        while time.time() - t0 < duration_sec:
            elapsed = time.time() - t0
            sec = int(elapsed)
            if sec > beat_check:
                beat_check = sec
                note_count = sum(
                    1
                    for _, d in captured
                    if len(d) >= 3 and d[0] & 0xF0 == 0x90 and d[2] > 0
                )
                print(
                    f"  {sec:3d}s / {int(duration_sec)}s | "
                    f"msgs: {len(captured)}, notes: {note_count}",
                    end="\r",
                )
            time.sleep(0.002)
        print()

    time.sleep(0.5)
    stop_flag.set()
    t.join(timeout=1.0)

    return [(ts - t0, data) for ts, data in captured]


GM_DRUMS = {
    35: "Kick2", 36: "Kick1", 37: "SideStk", 38: "Snare1",
    39: "Clap", 40: "Snare2", 42: "HHclose", 44: "HHpedal",
    46: "HHopen", 49: "Crash1", 51: "Ride1", 53: "RideBell",
}

PATT_OUT_MAP_9_16 = {
    9: "D1/RHY1", 10: "D2/RHY2", 11: "PC/PAD", 12: "BA/BASS",
    13: "C1/CHD1", 14: "C2/CHD2", 15: "C3/PHR1", 16: "C4/PHR2",
}
PATT_OUT_MAP_1_8 = {
    1: "D1/RHY1", 2: "D2/RHY2", 3: "PC/PAD", 4: "BA/BASS",
    5: "C1/CHD1", 6: "C2/CHD2", 7: "C3/PHR1", 8: "C4/PHR2",
}
# Active map — set via --patt-out flag
PATT_OUT_MAP = {**PATT_OUT_MAP_9_16, **PATT_OUT_MAP_1_8}


def analyze_and_save(captured, save_path=None):
    """Analyze captured data and optionally save to JSON."""
    note_ons = []
    note_offs = []
    ccs = []
    pcs = []

    for t, data in captured:
        if not data:
            continue
        status = data[0]
        if status & 0xF0 == 0x90 and len(data) >= 3 and data[2] > 0:
            ch = (status & 0x0F) + 1
            note_ons.append((t, ch, data[1], data[2]))
        elif status & 0xF0 == 0x90 and len(data) >= 3 and data[2] == 0:
            ch = (status & 0x0F) + 1
            note_offs.append((t, ch, data[1]))
        elif status & 0xF0 == 0x80 and len(data) >= 3:
            ch = (status & 0x0F) + 1
            note_offs.append((t, ch, data[1]))
        elif status & 0xF0 == 0xB0 and len(data) >= 3:
            ch = (status & 0x0F) + 1
            ccs.append((t, ch, data[1], data[2]))
        elif status & 0xF0 == 0xC0 and len(data) >= 2:
            ch = (status & 0x0F) + 1
            pcs.append((t, ch, data[1]))

    print(f"\n{'='*60}")
    print(f"  CAPTURE ANALYSIS")
    print(f"{'='*60}")
    print(f"  Total messages:  {len(captured)}")
    print(f"  Note-ons:        {len(note_ons)}")
    print(f"  Note-offs:       {len(note_offs)}")
    print(f"  CC messages:     {len(ccs)}")
    print(f"  Program Changes: {len(pcs)}")

    if pcs:
        print(f"\n  Program Changes:")
        for t, ch, prg in pcs:
            label = PATT_OUT_MAP.get(ch, f"ch{ch}")
            print(f"    t={t:6.3f}s {label} (ch{ch}) prg={prg}")

    if note_ons:
        ch_notes = {}
        for t, ch, note, vel in note_ons:
            ch_notes.setdefault(ch, []).append((t, note, vel))

        print(f"\n  Notes by channel:")
        for ch in sorted(ch_notes.keys()):
            events = ch_notes[ch]
            label = PATT_OUT_MAP.get(ch, f"ch{ch}")
            print(f"\n    {label} (ch{ch}): {len(events)} notes")
            for t, note, vel in events[:20]:
                if ch in (1, 2, 3, 9, 10, 11):
                    name = GM_DRUMS.get(note, f"n{note}")
                else:
                    name = f"n{note}"
                print(f"      t={t:6.3f}s {name:>8} ({note:3d}) v={vel:3d}")
            if len(events) > 20:
                print(f"      ... ({len(events) - 20} more)")

        # Summary
        print(f"\n  Summary:")
        for ch in sorted(ch_notes.keys()):
            events = ch_notes[ch]
            label = PATT_OUT_MAP.get(ch, f"ch{ch}")
            unique = sorted(set(n for _, n, _ in events))
            print(f"    {label}: {len(events)} notes, unique: {unique}")

    if save_path:
        events = [{"t": round(t, 6), "data": list(data)} for t, data in captured]
        with open(save_path, "w") as f:
            json.dump(
                {
                    "captured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "event_count": len(events),
                    "note_on_count": len(note_ons),
                    "events": events,
                },
                f,
                indent=2,
            )
        print(f"\n  Saved to {save_path}")

    return note_ons


def main():
    parser = argparse.ArgumentParser(
        description="Send style to QY70 and capture playback",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Workflow:
    1. Script sends .syx to QY70 via bulk dump (confirmed working)
    2. Select the loaded user style on QY70 (manual step)
    3. Press Play on QY70 (or use --auto-start for External sync)
    4. Script captures MIDI output on PATT OUT channels

QY70 Settings (UTILITY → MIDI):
    PATT OUT CH:  9~16 (or 1~8)
    MIDI CONTROL: In (or In/Out) — for --auto-start
    MIDI SYNC:    External — required for --auto-start
    ECHO BACK:    any

Examples:
    # Send SGT style, capture 10s of manual playback
    python3 midi_tools/send_and_capture.py tests/fixtures/QY70_SGT.syx -d 10

    # Capture only (style already loaded)
    python3 midi_tools/send_and_capture.py --capture-only -d 8

    # Auto-start with external clock
    python3 midi_tools/send_and_capture.py my.syx --auto-start --bpm 133
""",
    )
    parser.add_argument("file", nargs="?", help="Path to .syx style file")
    parser.add_argument(
        "--capture-only", action="store_true", help="Skip sending, just capture"
    )
    parser.add_argument(
        "-d", "--duration", type=float, default=10.0, help="Capture duration (default: 10s)"
    )
    parser.add_argument(
        "--auto-start", action="store_true", help="Send MIDI Start + Clock"
    )
    parser.add_argument("--bpm", type=int, default=120, help="BPM for auto-start clock")
    parser.add_argument(
        "--save",
        "-o",
        type=str,
        default=None,
        help="Save capture to JSON file",
    )

    args = parser.parse_args()

    if not args.capture_only and not args.file:
        parser.error("Specify a .syx file or use --capture-only")

    print("=" * 60)
    print("  QY70 SEND + CAPTURE (rtmidi)")
    print("=" * 60)

    mo, mi = open_midi_ports()
    if mo is None:
        return 1

    try:
        # Send style
        if not args.capture_only:
            loaded = send_style(mo, mi, args.file)
            if loaded:
                print()
                print("  >>> Now select the loaded user style on QY70 <<<")
                print("  >>> Press Play on QY70 when ready <<<")
                print()

        # Capture
        print(f"Capturing for {args.duration}s...")
        if not args.auto_start:
            print("  (Waiting for manual playback on QY70)")

        captured = capture_with_listener(
            mi, mo, args.duration, auto_start=args.auto_start, bpm=args.bpm
        )

        # Analyze
        note_ons = analyze_and_save(captured, save_path=args.save)

        if not note_ons:
            print("\n  No notes captured. Troubleshooting:")
            print("  1. Is the user style selected on QY70?")
            print("  2. Is QY70 playing? (transport indicator moving)")
            print("  3. PATT OUT CH set to 9~16?")
            print("  4. For --auto-start: MIDI SYNC must be External")

    finally:
        mo.close_port()
        mi.close_port()

    return 0


if __name__ == "__main__":
    sys.exit(main())
