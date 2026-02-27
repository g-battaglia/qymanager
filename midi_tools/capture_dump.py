#!/usr/bin/env python3
"""
Capture SysEx bulk dump from QY70.

Listens on the MIDI input port for SysEx messages and saves them to a file.
The user must manually trigger the bulk dump on the QY70:
  QY70 Menu: UTILITY -> MIDI -> Bulk Dump -> All/Style/Pattern

The script detects the end of a bulk dump by:
1. Receiving the close message (F0 43 10 5F 00 00 00 00 F7)
2. Timeout after no messages for N seconds

Usage:
    python3 midi_tools/capture_dump.py [--port "USB Midi Cable"] [--timeout 30] [--output captured/dump.syx]

Example session:
    1. Run this script
    2. On QY70: UTILITY -> MIDI -> Bulk Dump -> Style
    3. Wait for capture to complete
    4. File saved to midi_tools/captured/
"""

import sys
import time
import argparse
from datetime import datetime
from pathlib import Path
import mido


def find_midi_port(port_name=None):
    """Find a MIDI input port by name or return the first available."""
    ports = mido.get_input_names()
    if not ports:
        return None
    if port_name:
        if port_name in ports:
            return port_name
        matches = [p for p in ports if port_name.lower() in p.lower()]
        if matches:
            return matches[0]
        return None
    for p in ports:
        if "midi" in p.lower() or "usb" in p.lower():
            return p
    return ports[0]


def is_yamaha_close_message(data):
    """Check if SysEx data is the Yamaha bulk dump close message."""
    # Close message: F0 43 1n 5F 00 00 00 00 F7
    # data doesn't include F0/F7, so we check: 43 1x 5F 00 00 00 00
    if len(data) >= 7:
        if (
            data[0] == 0x43
            and (data[1] & 0xF0) == 0x10
            and data[2] == 0x5F
            and data[3] == 0x00
            and data[4] == 0x00
            and data[5] == 0x00
            and data[6] == 0x00
        ):
            return True
    return False


def is_yamaha_init_message(data):
    """Check if SysEx data is the Yamaha bulk dump init message."""
    # Init message: F0 43 1n 5F 00 00 00 01 F7
    if len(data) >= 7:
        if (
            data[0] == 0x43
            and (data[1] & 0xF0) == 0x10
            and data[2] == 0x5F
            and data[3] == 0x00
            and data[4] == 0x00
            and data[5] == 0x00
            and data[6] == 0x01
        ):
            return True
    return False


def is_yamaha_bulk_dump(data):
    """Check if SysEx data is a Yamaha bulk dump message."""
    # Bulk dump: F0 43 0n 5F BH BL AH AM AL [data] CS F7
    if len(data) >= 6:
        if data[0] == 0x43 and (data[1] & 0xF0) == 0x00 and data[2] == 0x5F:
            return True
    return False


def capture_bulk_dump(port_name=None, timeout=60, idle_timeout=5, output_path=None):
    """
    Capture SysEx bulk dump from MIDI input.

    Args:
        port_name: MIDI port name (auto-detect if None)
        timeout: Maximum total wait time in seconds
        idle_timeout: Stop after this many seconds of no messages
        output_path: Output file path (auto-generated if None)

    Returns:
        Path to saved file, or None if nothing captured
    """
    in_port_name = find_midi_port(port_name)
    if not in_port_name:
        print("ERROR: No MIDI input port found.")
        return None

    print(f"Listening on: {in_port_name}")
    print(f"Timeout: {timeout}s total, {idle_timeout}s idle")
    print()
    print(">>> NOW trigger the bulk dump on your QY70:")
    print("    UTILITY -> MIDI -> Bulk Dump -> Style (or Pattern/All)")
    print()

    messages = []
    total_bytes = 0
    bulk_count = 0
    param_count = 0
    got_init = False
    got_close = False

    with mido.open_input(in_port_name) as inport:
        # Flush pending
        for _ in inport.iter_pending():
            pass

        start_time = time.time()
        last_msg_time = time.time()

        while True:
            elapsed = time.time() - start_time
            idle = time.time() - last_msg_time

            # Check timeouts
            if elapsed > timeout:
                print(f"\nTotal timeout ({timeout}s) reached.")
                break

            if messages and idle > idle_timeout:
                print(f"\nIdle timeout ({idle_timeout}s) reached.")
                break

            # Check for close message
            if got_close:
                # Give a tiny grace period for any trailing messages
                time.sleep(0.2)
                for msg in inport.iter_pending():
                    if msg.type == "sysex":
                        messages.append(msg)
                break

            # Poll for messages
            msg = inport.poll()
            if msg:
                last_msg_time = time.time()

                if msg.type == "sysex":
                    messages.append(msg)
                    msg_bytes = len(msg.data) + 2  # +2 for F0/F7
                    total_bytes += msg_bytes

                    if is_yamaha_init_message(msg.data):
                        got_init = True
                        param_count += 1
                        print(f"  [{len(messages):3d}] INIT message (bulk dump starting)")
                    elif is_yamaha_close_message(msg.data):
                        got_close = True
                        param_count += 1
                        print(f"  [{len(messages):3d}] CLOSE message (bulk dump complete)")
                    elif is_yamaha_bulk_dump(msg.data):
                        bulk_count += 1
                        # Extract address
                        if len(msg.data) >= 6:
                            ah, am, al = msg.data[3 + 3], msg.data[3 + 4], msg.data[3 + 5]
                            print(
                                f"  [{len(messages):3d}] Bulk dump: "
                                f"addr={ah:02X} {am:02X} {al:02X}  "
                                f"size={msg_bytes} bytes  "
                                f"total={total_bytes} bytes",
                                end="\r",
                            )
                    else:
                        param_count += 1
                        preview = " ".join(f"{b:02X}" for b in msg.data[:8])
                        print(f"  [{len(messages):3d}] SysEx: {preview}... ({msg_bytes} bytes)")
            else:
                time.sleep(0.005)  # 5ms poll interval

    print()  # Clear the \r line

    if not messages:
        print("No SysEx messages received.")
        print()
        print("Troubleshooting:")
        print("  1. Is the QY70 powered on?")
        print("  2. MIDI cable: QY70 MIDI OUT -> USB Interface MIDI IN")
        print("  3. Did you trigger the bulk dump on the QY70?")
        print("  4. Check QY70: UTILITY -> MIDI -> SysEx = On")
        return None

    # Generate output filename
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(__file__).parent / "captured"
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / f"qy70_dump_{timestamp}.syx"
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save as raw SysEx file
    raw_data = bytearray()
    for msg in messages:
        raw_data.append(0xF0)
        raw_data.extend(msg.data)
        raw_data.append(0xF7)

    with open(output_path, "wb") as f:
        f.write(raw_data)

    # Summary
    print("=" * 60)
    print("Capture Summary")
    print("=" * 60)
    print(f"  Messages:    {len(messages)}")
    print(f"  Bulk dumps:  {bulk_count}")
    print(f"  Param msgs:  {param_count}")
    print(f"  Total bytes: {total_bytes}")
    print(f"  Init msg:    {'Yes' if got_init else 'No'}")
    print(f"  Close msg:   {'Yes' if got_close else 'No'}")
    print(f"  Saved to:    {output_path}")
    print()

    # Quick validation
    if got_init and got_close:
        print("  >>> Complete bulk dump captured successfully!")
    elif got_init and not got_close:
        print("  >>> WARNING: Init received but no close. Dump may be incomplete.")
    elif messages:
        print("  >>> Partial data captured (no init/close markers).")

    return output_path


def main():
    parser = argparse.ArgumentParser(description="Capture SysEx bulk dump from QY70")
    parser.add_argument("--port", default=None, help="MIDI port name (default: auto-detect)")
    parser.add_argument("--timeout", type=int, default=60, help="Max total wait time in seconds")
    parser.add_argument("--idle-timeout", type=int, default=5, help="Stop after N seconds idle")
    parser.add_argument("--output", "-o", default=None, help="Output file path")
    args = parser.parse_args()

    print("=" * 60)
    print("QY70 Bulk Dump Capture")
    print("=" * 60)
    print()

    result = capture_bulk_dump(
        port_name=args.port,
        timeout=args.timeout,
        idle_timeout=args.idle_timeout,
        output_path=args.output,
    )

    return 0 if result else 1


if __name__ == "__main__":
    sys.exit(main())
