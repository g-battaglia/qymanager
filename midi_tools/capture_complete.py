#!/usr/bin/env python3
"""Capture QY70 pattern bulk + XG Multi Part state into ONE .syx file.

The goal: a single file from which ALL pattern data can be recovered,
including:
  - Pattern bulk (Model 5F, AH=0x02) — events, section structure, timing
  - XG Multi Part state (Model 4C, AH=0x08) — Bank/LSB/Prog/Vol/Pan/Rev/Chor per part

This solves the problem that the QY70 pattern bulk alone does NOT contain
resolvable voice info (Bank MSB/LSB/Program are opaque, referenced by
internal ROM index). The XG stream captured at pattern-load time does.

Workflow:
  1. Load the pattern you want to capture on the QY70
  2. Run this script — it performs Init handshake, requests pattern bulk,
     then polls each XG Multi Part (1-16), then closes the handshake
  3. All responses are appended into a single .syx
  4. Use `qymanager info <file>` to see complete info

Usage:
    uv run python3 midi_tools/capture_complete.py -o out.syx
    uv run python3 midi_tools/capture_complete.py --am 0x00 -o slot_u01.syx

Requires: rtmidi, hardware QY70 connected via MIDI (UR22C Porta 1 default).
"""

import argparse
import sys
import time
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


INIT_MSG = bytes([0xF0, 0x43, 0x10, 0x5F, 0x00, 0x00, 0x00, 0x01, 0xF7])
CLOSE_MSG = bytes([0xF0, 0x43, 0x10, 0x5F, 0x00, 0x00, 0x00, 0x00, 0xF7])


def pattern_dump_request(ah: int, am: int, al: int) -> bytes:
    return bytes([0xF0, 0x43, 0x20, 0x5F, ah, am, al, 0xF7])


def xg_multi_part_request(part: int) -> bytes:
    return bytes([0xF0, 0x43, 0x20, 0x4C, 0x08, part, 0x00, 0xF7])


def find_port(midi_obj, hint: str) -> int:
    for i in range(midi_obj.get_port_count()):
        if hint.lower() in midi_obj.get_port_name(i).lower():
            return i
    return -1


def _enumerate_requests(am: int, xg: bool) -> list[tuple[str, bytes]]:
    """Return the full sequence of dump-request messages (without sending).

    Used by --dry-run to verify the tool's behavior without hardware.
    """
    seq = [("Init handshake (Param Change)", INIT_MSG)]
    for al in list(range(8)) + [0x7F]:
        label = f"Pattern track {al}" if al < 8 else f"Pattern header (AL=0x7F)"
        seq.append((label, pattern_dump_request(0x02, am, al)))
    seq.append(("Pattern name directory (AH=0x05)", pattern_dump_request(0x02, 0x7E, 0x05)))
    seq.append(("System meta (AH=0x03)", pattern_dump_request(0x03, 0x00, 0x00)))
    if xg:
        for part in range(16):
            seq.append((f"XG Multi Part {part} (ch{part + 1})", xg_multi_part_request(part)))
    seq.append(("Close handshake (Param Change)", CLOSE_MSG))
    return seq


def capture_session(port_hint: str, am: int, out_path: Path, xg: bool, timeout_per_req: float):
    import rtmidi

    mo = rtmidi.MidiOut()
    mi = rtmidi.MidiIn()
    mi.ignore_types(sysex=False, timing=True, active_sense=True)

    out_idx = find_port(mo, port_hint)
    in_idx = find_port(mi, port_hint)
    if out_idx < 0 or in_idx < 0:
        print(f"ERROR: MIDI port containing '{port_hint}' not found")
        available = [mo.get_port_name(i) for i in range(mo.get_port_count())]
        print(f"Available: {available}")
        return 1

    print(f"Port OUT: {mo.get_port_name(out_idx)}")
    print(f"Port IN:  {mi.get_port_name(in_idx)}")

    captured = []
    stop = [False]

    def listener():
        mi.open_port(in_idx)
        while not stop[0]:
            m = mi.get_message()
            if m:
                captured.append(bytes(m[0]))
            else:
                time.sleep(0.0005)
        mi.close_port()

    t = threading.Thread(target=listener, daemon=True)
    t.start()
    time.sleep(0.3)

    mo.open_port(out_idx)
    print()

    # 1. Init handshake (REQUIRED for pattern dump)
    print("→ Init handshake")
    mo.send_message(list(INIT_MSG))
    time.sleep(0.5)

    # 2. Pattern bulk request (all tracks + header)
    print(f"→ Pattern bulk (AH=0x02 AM=0x{am:02X})")
    # Request each track + header
    pattern_msgs = []
    for al in list(range(8)) + [0x7F]:
        captured.clear()
        mo.send_message(list(pattern_dump_request(0x02, am, al)))
        time.sleep(timeout_per_req)
        pattern_msgs.extend([m for m in captured if m[0] == 0xF0 and len(m) > 4 and m[3] == 0x5F])
    print(f"  Received {len(pattern_msgs)} pattern messages")

    # 3. Pattern name directory (AH=0x05) — 20 user-slot names
    dir_msgs = []
    print("→ Pattern name directory (AH=0x05)")
    captured.clear()
    mo.send_message(list(pattern_dump_request(0x02, 0x7E, 0x05)))
    time.sleep(timeout_per_req)
    dir_msgs = [m for m in captured if m[0] == 0xF0 and len(m) > 4 and m[3] == 0x5F]
    print(f"  Received {len(dir_msgs)} directory messages")

    # 4. System meta (AH=0x03) — Master Tune/Volume/etc
    sys_msgs = []
    print("→ System meta (AH=0x03)")
    captured.clear()
    mo.send_message(list(pattern_dump_request(0x03, 0x00, 0x00)))
    time.sleep(timeout_per_req)
    sys_msgs = [m for m in captured if m[0] == 0xF0 and len(m) > 4 and m[3] == 0x5F]
    print(f"  Received {len(sys_msgs)} system messages")

    # 5. XG Multi Part bulk per part (1-16)
    xg_msgs = []
    if xg:
        print("→ XG Multi Part state (parts 1-16)")
        for part in range(16):
            captured.clear()
            mo.send_message(list(xg_multi_part_request(part)))
            time.sleep(timeout_per_req)
            for msg in captured:
                if (len(msg) > 5 and msg[0] == 0xF0 and msg[3] == 0x4C and msg[1] == 0x43):
                    xg_msgs.append(msg)
        print(f"  Received {len(xg_msgs)} XG messages")

    # 6. Close handshake
    print("→ Close handshake")
    mo.send_message(list(CLOSE_MSG))
    mo.close_port()
    stop[0] = True
    t.join(timeout=1)

    # Write all to file
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        for m in pattern_msgs:
            f.write(m)
        for m in dir_msgs:
            f.write(m)
        for m in sys_msgs:
            f.write(m)
        for m in xg_msgs:
            f.write(m)

    total = (sum(len(m) for m in pattern_msgs) + sum(len(m) for m in dir_msgs) +
             sum(len(m) for m in sys_msgs) + sum(len(m) for m in xg_msgs))
    print(f"\n✓ Saved: {out_path} ({total} bytes)")
    print(f"  Pattern bulk:   {len(pattern_msgs)} msgs")
    print(f"  Name directory: {len(dir_msgs)} msgs")
    print(f"  System meta:    {len(sys_msgs)} msgs")
    print(f"  XG Multi Part:  {len(xg_msgs)} msgs")
    print()
    print(f"Try: uv run qymanager info {out_path}")

    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--output", required=True, help="Output .syx path")
    ap.add_argument("--am", type=lambda x: int(x, 0), default=0x7E,
                    help="Pattern slot (0x00-0x3F user slots, 0x7E=edit buffer default)")
    ap.add_argument("--port", default="porta 1", help="MIDI port hint (default: 'porta 1')")
    ap.add_argument("--no-xg", action="store_true",
                    help="Skip XG Multi Part capture (bulk only)")
    ap.add_argument("--timeout", type=float, default=0.8,
                    help="Timeout per request in seconds (default 0.8)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print request sequence without opening MIDI ports")
    args = ap.parse_args()

    if args.dry_run:
        print("=" * 60)
        print("QY70 Complete Capture — DRY RUN (no MIDI I/O)")
        print("=" * 60)
        seq = _enumerate_requests(args.am, xg=not args.no_xg)
        print(f"\nWould send {len(seq)} messages:\n")
        for i, (label, msg) in enumerate(seq):
            print(f"  [{i + 1:2d}] {label:40s} {msg.hex()}")
        total_req = len(seq)
        print(f"\nTotal requests: {total_req}")
        print(f"Expected responses: ~{total_req - 2} (init/close don't respond)")
        return 0

    print("=" * 60)
    print("QY70 Complete Capture (pattern bulk + XG state)")
    print("=" * 60)
    return capture_session(
        port_hint=args.port,
        am=args.am,
        out_path=Path(args.output),
        xg=not args.no_xg,
        timeout_per_req=args.timeout,
    )


if __name__ == "__main__":
    sys.exit(main())
