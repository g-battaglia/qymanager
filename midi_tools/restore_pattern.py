#!/usr/bin/env python3
"""
Restore a captured QY70 pattern dump back to the QY70 hardware.

Takes a raw capture (e.g., from request_dump.py --all-tracks) and produces
a "restore-ready" .syx file with:
  1. Init handshake at the start
  2. Deduplicated bulk dumps (in canonical order)
  3. Close message at the end

The captured file typically contains multiple redundant copies of the same
14 messages (one set per track request) without Init/Close wrappers.
This script removes duplicates and adds the required framing.

Usage:
    # Create restore-ready file (default: add _restore suffix)
    .venv/bin/python3 midi_tools/restore_pattern.py midi_tools/captured/ground_truth_C_kick.syx

    # Custom output path
    .venv/bin/python3 midi_tools/restore_pattern.py input.syx -o output.syx

    # Create AND send to QY70 immediately (requires QY70 at main screen)
    .venv/bin/python3 midi_tools/restore_pattern.py input.syx --send

    # Target a different User Pattern slot (0-63, default: keep original)
    .venv/bin/python3 midi_tools/restore_pattern.py input.syx --slot 5

Safety:
    - Validates all checksums before writing the restore file
    - Does NOT send unless --send is explicitly passed
    - Preserves the original AM (User Pattern slot) unless --slot is given
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.utils.checksum import verify_sysex_checksum, calculate_yamaha_checksum


INIT_MSG = bytes([0xF0, 0x43, 0x10, 0x5F, 0x00, 0x00, 0x00, 0x01, 0xF7])
CLOSE_MSG = bytes([0xF0, 0x43, 0x10, 0x5F, 0x00, 0x00, 0x00, 0x00, 0xF7])


def parse_syx_messages(data: bytes) -> list[bytes]:
    """Extract individual SysEx messages (F0..F7) from a raw .syx blob."""
    messages = []
    i = 0
    while i < len(data):
        if data[i] != 0xF0:
            i += 1
            continue
        j = i + 1
        while j < len(data) and data[j] != 0xF7:
            j += 1
        if j >= len(data):
            break
        messages.append(data[i : j + 1])
        i = j + 1
    return messages


def is_bulk_dump(msg: bytes) -> bool:
    """Check if a message is a Yamaha bulk dump (F0 43 0n 5F ...)."""
    return (
        len(msg) >= 10
        and msg[0] == 0xF0
        and msg[1] == 0x43
        and (msg[2] & 0xF0) == 0x00
        and msg[3] == 0x5F
    )


def is_init_or_close(msg: bytes) -> bool:
    """Check if a message is an Init or Close message."""
    return (
        len(msg) == 9
        and msg[0] == 0xF0
        and msg[1] == 0x43
        and (msg[2] & 0xF0) == 0x10
        and msg[3] == 0x5F
        and msg[4:7] == b"\x00\x00\x00"
        and msg[7] in (0x00, 0x01)
    )


def get_address(msg: bytes) -> tuple[int, int, int]:
    """Extract (AH, AM, AL) from a bulk dump message."""
    return (msg[6], msg[7], msg[8])


def deduplicate_and_sort(messages: list[bytes]) -> list[bytes]:
    """
    Remove duplicate bulk dumps and return in canonical order.

    Canonical order:
      1. Track data (AL=0x00..0x07) grouped by AL, ordered by capture order
      2. Header (AL=0x7F) last, in capture order

    Deduplication key: full message bytes (identical copies removed).
    Preserves first-seen order within each AL group.
    """
    seen = set()
    unique = []

    for msg in messages:
        if not is_bulk_dump(msg):
            continue
        key = bytes(msg)
        if key in seen:
            continue
        seen.add(key)
        unique.append(msg)

    # Group by AL, preserving capture order within each group
    by_al: dict[int, list[bytes]] = {}
    for msg in unique:
        al = get_address(msg)[2]
        by_al.setdefault(al, []).append(msg)

    # Canonical order: tracks 0-7, then header (0x7F)
    ordered = []
    for al in sorted(k for k in by_al if k != 0x7F):
        ordered.extend(by_al[al])
    if 0x7F in by_al:
        ordered.extend(by_al[0x7F])

    return ordered


def remap_slot(msg: bytes, new_am: int) -> bytes:
    """Change the AM byte (slot) and recalculate checksum."""
    if not is_bulk_dump(msg):
        return msg

    new = bytearray(msg)
    new[7] = new_am

    # Recalculate checksum: covers BH BL AH AM AL + data
    # Message layout: F0 43 0n 5F BH BL AH AM AL [data] CS F7
    #                 0  1  2  3  4  5  6  7  8  9..-3 -2 -1
    payload = bytes(new[4:-2])  # BH BL AH AM AL + data
    new_cs = calculate_yamaha_checksum(payload)
    new[-2] = new_cs

    return bytes(new)


def build_restore_file(
    input_path: Path,
    output_path: Path,
    target_slot: int | None = None,
) -> dict:
    """Build a restore-ready .syx file from a captured dump."""
    raw = input_path.read_bytes()
    all_msgs = parse_syx_messages(raw)

    bulk_msgs = deduplicate_and_sort(all_msgs)

    if not bulk_msgs:
        raise ValueError(f"No bulk dump messages found in {input_path}")

    # Remap slot if requested
    if target_slot is not None:
        if not (0 <= target_slot <= 63):
            raise ValueError(f"Invalid slot {target_slot} (must be 0-63)")
        bulk_msgs = [remap_slot(m, target_slot) for m in bulk_msgs]

    # Verify all checksums
    bad = [m for m in bulk_msgs if not verify_sysex_checksum(m)]
    if bad:
        raise ValueError(f"{len(bad)} message(s) have invalid checksums — aborting")

    # Collect stats
    als = [get_address(m)[2] for m in bulk_msgs]
    ams = set(get_address(m)[1] for m in bulk_msgs)
    total_bytes = 9 + sum(len(m) for m in bulk_msgs) + 9

    # Write output: Init + bulk dumps + Close
    with open(output_path, "wb") as f:
        f.write(INIT_MSG)
        for m in bulk_msgs:
            f.write(m)
        f.write(CLOSE_MSG)

    return {
        "input_messages": len(all_msgs),
        "unique_bulk": len(bulk_msgs),
        "al_distribution": sorted(set(als)),
        "am_slots": sorted(ams),
        "output_bytes": total_bytes,
        "duplicates_removed": len([m for m in all_msgs if is_bulk_dump(m)]) - len(bulk_msgs),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Restore a QY70 pattern dump back to the hardware.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("input", help="Captured .syx file")
    parser.add_argument("-o", "--output", default=None,
                        help="Output path (default: <input>_restore.syx)")
    parser.add_argument("--slot", type=int, default=None,
                        help="Remap to different User Pattern slot (0-63)")
    parser.add_argument("--send", action="store_true",
                        help="After building, send the restore file to the QY70")
    parser.add_argument("--port", default=None, help="MIDI port for --send")
    parser.add_argument("--delay", type=int, default=150,
                        help="Delay between bulk dumps in ms (for --send)")

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: File not found: {input_path}")
        return 1

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_name(input_path.stem + "_restore.syx")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("QY70 Pattern Restore Builder")
    print("=" * 60)
    print(f"Input:  {input_path}")
    print(f"Output: {output_path}")
    if args.slot is not None:
        print(f"Remap:  User Pattern slot -> {args.slot}")
    print()

    try:
        stats = build_restore_file(input_path, output_path, args.slot)
    except ValueError as e:
        print(f"ERROR: {e}")
        return 1

    print(f"  Parsed messages:      {stats['input_messages']}")
    print(f"  Unique bulk dumps:    {stats['unique_bulk']}")
    print(f"  Duplicates removed:   {stats['duplicates_removed']}")
    print(f"  AL tracks present:    {[f'0x{al:02X}' for al in stats['al_distribution']]}")
    print(f"  AM slots:             {[f'0x{am:02X}' for am in stats['am_slots']]}")
    print(f"  Output file size:     {stats['output_bytes']} bytes")
    print(f"  Checksums:            ALL VALID")
    print()
    print(f"Restore file written: {output_path}")

    if args.send:
        print()
        print("=" * 60)
        print("Sending to QY70...")
        print("=" * 60)
        from midi_tools.send_style import send_style_to_qy70
        ok = send_style_to_qy70(
            str(output_path),
            port_name=args.port,
            delay_ms=args.delay,
            verbose=True,
        )
        return 0 if ok else 1
    else:
        print()
        print("To restore this pattern on the QY70 later:")
        print(f"  .venv/bin/python3 midi_tools/send_style.py {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
