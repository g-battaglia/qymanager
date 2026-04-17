#!/usr/bin/env python3
"""
Capture XG Parameter Change stream from the QY70.

When XG PARM OUT is enabled on the QY70 (UTILITY → MIDI → XG PARM OUT = on),
the device transmits XG Parameter Change messages whenever:
- XG-relevant parameters change
- A new song or pattern is selected

IMPORTANT: XG PARM OUT does NOT transmit Bank Select / Program Change as XG
Parameter Change messages (AL=01/02/03). Those ride as standard MIDI channel
events (0xBn CC0/CC32 + 0xCn Program Change) on each Part's MIDI channel.
Use --all to keep every MIDI event, which is required if you want to know
which voice each Part is using.

Uses rtmidi directly (mido silently drops SysEx on macOS CoreMIDI).

Usage:
    # SysEx only (XG Param Change stream)
    python3 midi_tools/capture_xg_stream.py -o out.syx

    # All events (needed to capture Bank/Program Change)
    python3 midi_tools/capture_xg_stream.py --all -o out.syx

Typical workflow for RE:
    1. On QY70: enable UTILITY → MIDI → XG PARM OUT = on
    2. Run this script with --all: python3 midi_tools/capture_xg_stream.py --all -d 30
    3. On QY70: change pattern/preset (triggers XG + PC emission)
    4. Script saves all captured bytes to file
    5. Analyze: python3 midi_tools/xg_param.py summary <file>
"""

import argparse
import sys
import time
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


def capture(duration: float, port_hint: str, verbose: bool,
            all_events: bool = False) -> list[bytes]:
    """Capture MIDI for `duration` seconds.

    If all_events=False (default): only SysEx (F0..F7) messages are kept.
    If all_events=True: every channel event (note on/off, PC, CC, ...) is
    kept as well — essential to capture Program Change (0xCn) emitted by
    the QY70 at pattern load.
    """
    import rtmidi

    mi = rtmidi.MidiIn()
    mi.ignore_types(sysex=False, timing=True, active_sense=True)

    idx, name = find_port_idx(mi, preference=port_hint)
    if idx is None:
        print(f"ERROR: no MIDI input ports found")
        return []

    print(f"Listening on: {name}" + (" (all events)" if all_events else " (SysEx only)"))
    mi.open_port(idx)

    collected: list[bytes] = []
    start = time.time()

    try:
        while time.time() - start < duration:
            msg = mi.get_message()
            if msg is None:
                time.sleep(0.001)
                continue
            data, _ = msg
            if not data:
                continue
            raw = bytes(data)
            is_sysex = raw[0] == 0xF0
            if not all_events and not is_sysex:
                continue
            collected.append(raw)
            if verbose:
                kind = classify(raw)
                print(f"  [{len(collected):4d}] +{time.time()-start:5.2f}s  {len(raw):3d}B  {kind}")
    finally:
        mi.close_port()

    return collected


def classify(raw: bytes) -> str:
    """Quick classification for display."""
    if not raw:
        return "?"
    status = raw[0]
    # Channel messages (0x80..0xEF)
    if 0x80 <= status <= 0xEF:
        kind = status & 0xF0
        ch = status & 0x0F
        names = {0x80: "NoteOff", 0x90: "NoteOn", 0xA0: "PolyAT", 0xB0: "CC",
                 0xC0: "PgmChg", 0xD0: "ChanAT", 0xE0: "PitchBend"}
        body = " ".join(f"{b:02X}" for b in raw[1:])
        return f"{names.get(kind, '?')} ch={ch+1} {body}"
    if status != 0xF0:
        return f"status=0x{status:02X}"
    if len(raw) < 4:
        return "?"
    if raw[1] != 0x43:
        return "non-Yamaha"
    cmd = raw[2]
    model = raw[3] if len(raw) > 3 else None
    if model == 0x4C:
        if (cmd & 0xF0) == 0x10 and len(raw) >= 8:
            ah, am, al = raw[4], raw[5], raw[6]
            names = {0x00: "Sys", 0x02: "Fx", 0x08: "Part", 0x30: "DS1", 0x31: "DS2"}
            tag = names.get(ah, f"AH={ah:02X}")
            return f"XG {tag} AM={am:02X} AL={al:02X}"
        return "XG ?"
    if model == 0x5F:
        if (cmd & 0xF0) == 0x00:
            return "Seq bulk-dump"
        if (cmd & 0xF0) == 0x10:
            return "Seq param-change"
        return "Seq ?"
    return f"Yamaha model={model:02X}"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-d", "--duration", type=float, default=30.0,
                    help="capture duration in seconds (default 30)")
    ap.add_argument("-o", "--output", type=Path, required=True,
                    help="output .syx path (or .mid-like raw blob if --all)")
    ap.add_argument("--port", default="steinberg",
                    help="MIDI port name hint (default: steinberg)")
    ap.add_argument("-q", "--quiet", action="store_true",
                    help="don't print each captured message")
    ap.add_argument("--all", action="store_true",
                    help="capture every MIDI event, not only SysEx "
                         "(needed to record Program Change at pattern load)")
    args = ap.parse_args()

    msgs = capture(args.duration, args.port, verbose=not args.quiet,
                   all_events=args.all)
    label = "MIDI events" if args.all else "SysEx messages"
    print(f"\nCaptured {len(msgs)} {label}")

    if not msgs:
        print("Nothing to save.")
        return

    blob = b"".join(msgs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(blob)
    print(f"Saved {len(blob)} bytes to {args.output}")

    # Summary
    from collections import Counter
    tags = Counter(classify(m) for m in msgs)
    print("\nBreakdown:")
    for t, c in sorted(tags.items(), key=lambda x: -x[1]):
        print(f"  {c:5d}  {t}")

    # XG-specific summary via xg_param
    try:
        from midi_tools.xg_param import split_sysex, parse_xg, AH_NAMES
        xg_msgs = [m for m in (parse_xg(x) for x in split_sysex(blob)) if m is not None]
        if xg_msgs:
            print(f"\nXG Param Change: {len(xg_msgs)}")
            ah_counts = Counter(m.ah for m in xg_msgs)
            for ah, c in sorted(ah_counts.items()):
                print(f"  0x{ah:02X} {AH_NAMES.get(ah, '?'):<20s}: {c}")
    except ImportError:
        pass


if __name__ == "__main__":
    main()
