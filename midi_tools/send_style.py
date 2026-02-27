#!/usr/bin/env python3
"""
Transmit a QY70 style file (.syx) to the QY70 via MIDI.

This script sends all SysEx messages from a .syx file to the QY70,
loading the style into the user style memory.

Protocol (from reverse engineering):
  1. Send Init message (F0 43 1n 5F 00 00 00 01 F7), wait 100ms
  2. Send Bulk Dump messages (F0 43 0n 5F BH BL AH AM AL [data] CS F7)
     with 30ms delay between each
  3. Send Close message (F0 43 1n 5F 00 00 00 00 F7)

The QY70 silently discards messages with bad checksums — no ACK/NAK.
The checksum covers BH BL AH AM AL + encoded data (confirmed from SGT reference).

Usage:
    python3 midi_tools/send_style.py tests/fixtures/NEONGROOVE.syx
    python3 midi_tools/send_style.py tests/fixtures/QY70_SGT.syx --delay 50
    python3 midi_tools/send_style.py mystyle.syx --verify-only
    python3 midi_tools/send_style.py mystyle.syx --device 1
"""

import sys
import time
import argparse
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.utils.checksum import verify_sysex_checksum


def find_midi_port(port_name=None, direction="output"):
    """Find a MIDI port by name or return the first available."""
    import mido

    if direction == "output":
        ports = mido.get_output_names()
    else:
        ports = mido.get_input_names()

    if not ports:
        return None

    if port_name:
        if port_name in ports:
            return port_name
        matches = [p for p in ports if port_name.lower() in p.lower()]
        return matches[0] if matches else None

    # Prefer Steinberg UR22C or USB MIDI interfaces
    for p in ports:
        if "steinberg" in p.lower() or "ur22" in p.lower():
            return p
    for p in ports:
        if "midi" in p.lower() or "usb" in p.lower():
            return p

    return ports[0]


def parse_syx_file(filepath):
    """
    Parse a .syx file and extract all SysEx messages.

    Returns:
        List of tuples: (raw_bytes_with_f0_f7, message_info_dict)
    """
    with open(filepath, "rb") as f:
        data = f.read()

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

        msg_bytes = data[i : j + 1]

        # Classify message
        info = classify_message(msg_bytes)
        messages.append((msg_bytes, info))
        i = j + 1

    return messages


def classify_message(msg_bytes):
    """Classify a SysEx message and extract metadata."""
    info = {
        "type": "unknown",
        "device": None,
        "size": len(msg_bytes),
        "al": None,
        "payload_size": 0,
        "checksum_valid": None,
    }

    if len(msg_bytes) < 5:
        info["type"] = "short"
        return info

    if msg_bytes[1] != 0x43:  # Not Yamaha
        return info

    device_byte = msg_bytes[2]
    info["device"] = device_byte & 0x0F
    msg_type_nibble = device_byte & 0xF0

    if msg_type_nibble == 0x10:
        # Parameter Change (Init or Close)
        if len(msg_bytes) >= 8 and msg_bytes[3] == 0x5F:
            if msg_bytes[4:7] == b"\x00\x00\x00":
                if msg_bytes[7] == 0x01:
                    info["type"] = "init"
                elif msg_bytes[7] == 0x00:
                    info["type"] = "close"
                else:
                    info["type"] = "param"
            else:
                info["type"] = "param"
    elif msg_type_nibble == 0x00:
        # Bulk Dump
        info["type"] = "bulk_dump"
        if len(msg_bytes) >= 10:
            info["al"] = msg_bytes[8]
            info["payload_size"] = len(msg_bytes) - 9 - 1 - 1  # minus header, checksum, F7
            info["checksum_valid"] = verify_sysex_checksum(msg_bytes)

    return info


def validate_file(filepath, verbose=True):
    """
    Pre-validate a .syx file before transmission.

    Checks:
    - File structure (init, bulk dumps, close)
    - All checksums valid
    - Device numbers consistent
    - Message sizes correct

    Returns:
        (messages, errors) tuple. errors is empty list if valid.
    """
    messages = parse_syx_file(filepath)
    errors = []

    if not messages:
        errors.append("No SysEx messages found")
        return messages, errors

    if verbose:
        print(f"File: {filepath}")
        print(f"Size: {Path(filepath).stat().st_size} bytes")
        print(f"Messages: {len(messages)}")

    # Check init
    first_bytes, first_info = messages[0]
    if first_info["type"] != "init":
        errors.append(f"First message is not Init (type={first_info['type']})")
    elif verbose:
        print(f"  Init:  OK  [{first_bytes.hex(' ')}]")

    # Check close
    last_bytes, last_info = messages[-1]
    if last_info["type"] != "close":
        errors.append(f"Last message is not Close (type={last_info['type']})")
    elif verbose:
        print(f"  Close: OK  [{last_bytes.hex(' ')}]")

    # Check bulk dumps
    bulk_count = 0
    bad_checksums = 0
    device_numbers = set()
    al_counts = {}

    for msg_bytes, info in messages:
        if info["device"] is not None:
            device_numbers.add(info["device"])

        if info["type"] == "bulk_dump":
            bulk_count += 1

            # Check checksum
            if info["checksum_valid"] is False:
                bad_checksums += 1
                al_str = f"0x{info['al']:02X}" if info["al"] is not None else "?"
                errors.append(f"Checksum FAILED for bulk dump AL={al_str}")

            # Count AL addresses
            if info["al"] is not None:
                al = info["al"]
                al_counts[al] = al_counts.get(al, 0) + 1

            # Check message size (should be 158 for 128-byte decoded blocks)
            if info["size"] != 158:
                errors.append(
                    f"Unexpected message size {info['size']} "
                    f"(expected 158 for standard 128-byte blocks)"
                )

    if verbose:
        print(f"  Bulk dumps: {bulk_count}")
        print(f"  Checksums: {bulk_count - bad_checksums}/{bulk_count} valid")
        print(f"  Device numbers: {device_numbers}")
        print(f"  AL addresses: {len(al_counts)} unique")

        # Show AL distribution
        has_header = 0x7F in al_counts
        track_als = sorted(al for al in al_counts if al != 0x7F)
        sections = set(al // 8 for al in track_als)
        print(f"  Sections: {sorted(sections)} ({len(sections)} sections)")
        if has_header:
            print(f"  Header blocks: {al_counts[0x7F]}")

    if bad_checksums > 0:
        errors.append(f"{bad_checksums} checksums failed!")

    if len(device_numbers) > 1:
        errors.append(f"Inconsistent device numbers: {device_numbers}")

    return messages, errors


def send_style_to_qy70(
    filepath,
    port_name=None,
    delay_ms=30,
    init_delay_ms=100,
    close_delay_ms=50,
    verbose=True,
    device_override=None,
):
    """
    Send a style file to the QY70.

    Protocol:
        1. Open MIDI output port
        2. Pre-validate all messages (checksums, structure)
        3. Send Init message, wait init_delay_ms
        4. Send Bulk Dump messages with delay_ms between each
        5. Wait close_delay_ms, send Close message

    Args:
        filepath: Path to .syx file
        port_name: MIDI output port name (auto-detect if None)
        delay_ms: Delay between bulk dump messages in ms (default: 30)
        init_delay_ms: Delay after Init message in ms (default: 100)
        close_delay_ms: Delay before Close message in ms (default: 50)
        verbose: Print progress
        device_override: Override device number in all messages (0-15)

    Returns:
        True if all messages sent without errors, False otherwise
    """
    import mido

    # ── Step 1: Pre-validate ──
    if verbose:
        print("=" * 60)
        print("QY70 Style Transmission")
        print("=" * 60)
        print()
        print("── Pre-validation ──")

    messages, errors = validate_file(filepath, verbose)

    if errors:
        print()
        print("ERRORS found during validation:")
        for e in errors:
            print(f"  ERROR: {e}")
        print()
        print("Aborting transmission. Fix errors before sending.")
        return False

    if verbose:
        print("  Validation: ALL CHECKS PASSED")
        print()

    # ── Step 2: Find port ──
    out_port = find_midi_port(port_name, "output")
    if not out_port:
        print("ERROR: No MIDI output port found.")
        print("Available ports:")
        for p in mido.get_output_names():
            print(f"  - {p}")
        return False

    if verbose:
        print(f"── Transmission ──")
        print(f"  Port: {out_port}")
        print(f"  Delay: {delay_ms}ms between bulk dumps")
        print(f"  Init delay: {init_delay_ms}ms")
        print(f"  Close delay: {close_delay_ms}ms")
        if device_override is not None:
            print(f"  Device override: {device_override}")
        print()

    # ── Step 3: Send messages ──
    sent_count = 0
    error_count = 0
    total = len(messages)

    try:
        with mido.open_output(out_port) as outport:
            for i, (msg_bytes, info) in enumerate(messages):
                try:
                    # Optionally override device number
                    if device_override is not None:
                        msg_bytes = _override_device(msg_bytes, info, device_override)

                    # Send as raw SysEx via mido (strip F0 and F7)
                    msg_data = list(msg_bytes[1:-1])
                    msg = mido.Message("sysex", data=msg_data)
                    outport.send(msg)
                    sent_count += 1

                    # Progress display
                    if verbose:
                        if info["type"] == "init":
                            print(f"  [{i + 1:3d}/{total}] INIT")
                        elif info["type"] == "close":
                            print(f"  [{i + 1:3d}/{total}] CLOSE")
                        elif info["type"] == "bulk_dump":
                            al = info["al"]
                            sec = al // 8 if al != 0x7F else -1
                            trk = al % 8 if al != 0x7F else -1
                            if al == 0x7F:
                                label = "Header"
                            else:
                                label = f"Sec{sec}/Trk{trk}"
                            cs = "OK" if info["checksum_valid"] else "BAD"
                            print(
                                f"  [{i + 1:3d}/{total}] Bulk AL=0x{al:02X} "
                                f"({label}) {info['payload_size']}B cs={cs}"
                            )
                        else:
                            print(f"  [{i + 1:3d}/{total}] {info['type']}")

                    # Timing
                    if info["type"] == "init":
                        time.sleep(init_delay_ms / 1000.0)
                    elif info["type"] == "close":
                        pass  # No delay after close
                    else:
                        # Check if next message is close — add extra delay
                        if i + 1 < total and messages[i + 1][1]["type"] == "close":
                            time.sleep(close_delay_ms / 1000.0)
                        else:
                            time.sleep(delay_ms / 1000.0)

                except Exception as e:
                    error_count += 1
                    if verbose:
                        print(f"  [{i + 1:3d}] SEND ERROR: {e}")

    except Exception as e:
        print(f"ERROR: Failed to open MIDI port '{out_port}': {e}")
        return False

    # ── Step 4: Summary ──
    if verbose:
        print()
        print("=" * 60)
        elapsed_est = (init_delay_ms + (sent_count - 2) * delay_ms + close_delay_ms) / 1000.0
        print(f"Transmission complete:")
        print(f"  Sent: {sent_count}/{total} messages")
        print(f"  Errors: {error_count}")
        print(f"  Estimated time: {elapsed_est:.1f}s")
        print("=" * 60)
        print()
        if error_count == 0:
            print("The QY70 should now have the style loaded.")
            print("If it didn't work:")
            print("  1. Ensure QY70 is at main screen (not in utility menu)")
            print("  2. Check QY70 device number: UTILITY -> MIDI -> Device No.")
            print(f"     (current script uses device {device_override or 0})")
            print("  3. Try --delay 100 for slower transmission")
            print("  4. Try sending the known-good SGT file first:")
            print("     python3 midi_tools/send_style.py tests/fixtures/QY70_SGT.syx")

    return error_count == 0


def _override_device(msg_bytes, info, device_num):
    """Override the device number in a SysEx message."""
    msg = bytearray(msg_bytes)
    if len(msg) < 3:
        return bytes(msg)

    type_nibble = msg[2] & 0xF0
    msg[2] = type_nibble | (device_num & 0x0F)

    # For bulk dumps, recalculate checksum since the device byte
    # is NOT part of the checksum, so no recalculation needed.
    # Checksum covers BH BL AH AM AL + data — device byte is at position 2,
    # which is before the checksum region.

    return bytes(msg)


def main():
    parser = argparse.ArgumentParser(
        description="Transmit a QY70 style file to the QY70 via MIDI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
    python3 midi_tools/send_style.py tests/fixtures/NEONGROOVE.syx
    python3 midi_tools/send_style.py tests/fixtures/QY70_SGT.syx
    python3 midi_tools/send_style.py mystyle.syx --port "Steinberg UR22C Porta 1"
    python3 midi_tools/send_style.py mystyle.syx --delay 100
    python3 midi_tools/send_style.py mystyle.syx --device 1
    python3 midi_tools/send_style.py mystyle.syx --verify-only

Note: The QY70 must be at the main playing screen (not in menus)
      to receive bulk data. There is no ACK — if checksums fail,
      the QY70 silently discards the data.
""",
    )
    parser.add_argument("file", help="Path to .syx style file")
    parser.add_argument("--port", "-p", default=None, help="MIDI output port name")
    parser.add_argument(
        "--delay",
        "-d",
        type=int,
        default=30,
        help="Delay between bulk dump messages in ms (default: 30)",
    )
    parser.add_argument(
        "--init-delay",
        type=int,
        default=100,
        help="Delay after Init message in ms (default: 100)",
    )
    parser.add_argument(
        "--close-delay",
        type=int,
        default=50,
        help="Delay before Close message in ms (default: 50)",
    )
    parser.add_argument(
        "--device",
        type=int,
        default=None,
        help="Override MIDI device number (0-15). Must match QY70's setting.",
    )
    parser.add_argument(
        "--verify-only",
        "-V",
        action="store_true",
        help="Only validate the file, don't send",
    )
    parser.add_argument("--quiet", "-q", action="store_true", help="Minimal output")

    args = parser.parse_args()

    filepath = Path(args.file)
    if not filepath.exists():
        print(f"ERROR: File not found: {filepath}")
        return 1

    if args.verify_only:
        print("=" * 60)
        print("QY70 SysEx File Validation")
        print("=" * 60)
        print()
        messages, errors = validate_file(filepath, verbose=True)
        print()
        if errors:
            print("VALIDATION FAILED:")
            for e in errors:
                print(f"  - {e}")
            return 1
        else:
            print("VALIDATION PASSED — file is ready for transmission.")
            return 0

    success = send_style_to_qy70(
        filepath,
        port_name=args.port,
        delay_ms=args.delay,
        init_delay_ms=args.init_delay,
        close_delay_ms=args.close_delay,
        verbose=not args.quiet,
        device_override=args.device,
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
