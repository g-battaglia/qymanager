#!/usr/bin/env python3
"""Request a bulk dump from the QY70 and save the response.

Sends a Bulk Dump Request via rtmidi (NOT mido — mido drops SysEx on macOS)
and captures the response.

From List Book p.55, section 3-6-3-4:
  F0 43 20 5F AH AM AL F7

Uses rtmidi directly for both sending and receiving.
"""

import sys
import time
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def capture_response(port_name, timeout_s, results):
    """Capture SysEx responses on MIDI IN."""
    import rtmidi
    mi = rtmidi.MidiIn()
    mi.ignore_types(sysex=False, timing=True, active_sense=True)

    port_idx = None
    for i in range(mi.get_port_count()):
        if mi.get_port_name(i) == port_name:
            port_idx = i
            break
    if port_idx is None:
        results.append(("ERROR", f"Port '{port_name}' not found"))
        return

    mi.open_port(port_idx)
    deadline = time.time() + timeout_s
    msg_count = 0
    last_msg_time = time.time()

    while time.time() < deadline:
        msg = mi.get_message()
        if msg:
            data, delta = msg
            results.append(("MSG", bytes(data), delta))
            msg_count += 1
            last_msg_time = time.time()
            # Extend deadline if we're still receiving
            if time.time() + 2 < deadline:
                pass  # Keep original deadline
            else:
                deadline = time.time() + 2  # Give 2 more seconds
        else:
            # If we've received messages and there's been a 1s gap, stop
            if msg_count > 0 and (time.time() - last_msg_time) > 1.0:
                break
            time.sleep(0.001)

    mi.close_port()


def request_dump(ah, am, al, port_name=None, timeout=10):
    """Send bulk dump request and capture response."""
    import rtmidi

    # Find port
    mo = rtmidi.MidiOut()
    ports = [mo.get_port_name(i) for i in range(mo.get_port_count())]

    if not ports:
        print("ERROR: No MIDI ports found")
        return None

    out_port = port_name or next(
        (p for p in ports if "porta 1" in p.lower()), ports[0]
    )
    in_port = out_port  # Same name for in/out on UR22C

    port_idx = next(
        (i for i in range(mo.get_port_count()) if mo.get_port_name(i) == out_port),
        None
    )
    if port_idx is None:
        print(f"ERROR: Port '{out_port}' not found")
        return None

    # Build request: F0 43 20 5F AH AM AL F7
    request = [0xF0, 0x43, 0x20, 0x5F, ah, am, al, 0xF7]

    print(f"Port: {out_port}")
    print(f"Request: {' '.join(f'{b:02X}' for b in request)}")
    print(f"  AH=0x{ah:02X} AM=0x{am:02X} AL=0x{al:02X}")
    print(f"Waiting {timeout}s for response...")

    # Start capture thread
    results = []
    capture_thread = threading.Thread(
        target=capture_response,
        args=(in_port, timeout, results)
    )
    capture_thread.start()
    time.sleep(0.3)  # Let capture settle

    # Send request
    mo.open_port(port_idx)
    mo.send_message(request)
    mo.close_port()

    # Wait for capture
    capture_thread.join()

    # Analyze results
    sysex_msgs = []
    other_msgs = []

    for item in results:
        if item[0] == "MSG":
            data = item[1]
            if data[0] == 0xF0 and data[-1] == 0xF7:
                sysex_msgs.append(data)
            else:
                other_msgs.append(data)
        elif item[0] == "ERROR":
            print(f"ERROR: {item[1]}")

    print(f"\nReceived: {len(sysex_msgs)} SysEx + {len(other_msgs)} other messages")

    if sysex_msgs:
        total_bytes = sum(len(m) for m in sysex_msgs)
        print(f"Total SysEx data: {total_bytes} bytes")
        for i, msg in enumerate(sysex_msgs):
            prefix = ' '.join(f'{b:02X}' for b in msg[:12])
            suffix = ' '.join(f'{b:02X}' for b in msg[-4:])
            print(f"  [{i+1}] {len(msg)}B: {prefix} ... {suffix}")

    return sysex_msgs


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Request bulk dump from QY70")
    parser.add_argument("--ah", type=lambda x: int(x, 16), default=0x02,
                        help="Address High (hex, default: 02 = pattern)")
    parser.add_argument("--am", type=lambda x: int(x, 16), default=0x7E,
                        help="Address Mid (hex, default: 7E = edit buffer)")
    parser.add_argument("--al", type=lambda x: int(x, 16), default=0x00,
                        help="Address Low (hex, default: 00 = RHY1)")
    parser.add_argument("--all-tracks", "-a", action="store_true",
                        help="Request all tracks (AL=0x00-0x07 + 0x7F)")
    parser.add_argument("--port", "-p", default=None, help="MIDI port name")
    parser.add_argument("--timeout", "-t", type=int, default=10,
                        help="Timeout in seconds (default: 10)")
    parser.add_argument("--output", "-o", default=None,
                        help="Save response to .syx file")

    args = parser.parse_args()

    print("=" * 60)
    print("QY70 Bulk Dump Request (rtmidi direct)")
    print("=" * 60)
    print()

    all_msgs = []

    if args.all_tracks:
        # Request header + all 8 tracks
        for al in list(range(8)) + [0x7F]:
            label = f"Track {al}" if al < 8 else "Header"
            print(f"\n--- Requesting {label} (AL=0x{al:02X}) ---")
            msgs = request_dump(args.ah, args.am, al, args.port, args.timeout)
            if msgs:
                all_msgs.extend(msgs)
            time.sleep(0.5)
    else:
        msgs = request_dump(args.ah, args.am, args.al, args.port, args.timeout)
        if msgs:
            all_msgs = msgs

    # Save to file
    if args.output and all_msgs:
        output_path = args.output
        with open(output_path, 'wb') as f:
            for msg in all_msgs:
                f.write(msg)
        total = sum(len(m) for m in all_msgs)
        print(f"\nSaved {len(all_msgs)} messages ({total} bytes) to {output_path}")
    elif all_msgs:
        print(f"\nTotal: {len(all_msgs)} messages received")
        print("Use --output/-o to save to file")
    else:
        print("\nNo response from QY70")
        print("Check: QY70 at main screen, MIDI connected, correct port")


if __name__ == "__main__":
    main()
