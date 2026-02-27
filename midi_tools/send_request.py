#!/usr/bin/env python3
"""
Send a SysEx dump request to QY70 and capture the response.

Instead of manually triggering a bulk dump on the QY70, this script
sends a Dump Request message which tells the QY70 to transmit its data.

QY70 Dump Request format:
  F0 43 2n 5F AH AM AL F7

Where:
  n = device number (0-15)
  AH AM AL = address of data to request
    - 02 7E 7F = Style header
    - 02 7E 00-05 = Section data (Intro, MainA, MainB, FillAB, FillBA, Ending)
    - 02 7E 08-2F = Track data (section * 8 + track)

Usage:
    python3 midi_tools/send_request.py --address 02 7E 7F        # Request header
    python3 midi_tools/send_request.py --address 02 7E 08        # Request Intro Track 1
    python3 midi_tools/send_request.py --all                     # Request everything
    python3 midi_tools/send_request.py --style                   # Request full style
"""

import sys
import time
import argparse
from datetime import datetime
from pathlib import Path
import mido


def find_midi_port(port_name=None, direction="input"):
    """Find a MIDI port by name or return the first available."""
    ports = mido.get_input_names() if direction == "input" else mido.get_output_names()
    if not ports:
        return None
    if port_name:
        if port_name in ports:
            return port_name
        matches = [p for p in ports if port_name.lower() in p.lower()]
        return matches[0] if matches else None
    for p in ports:
        if "midi" in p.lower() or "usb" in p.lower():
            return p
    return ports[0]


def send_dump_request(address, port_name=None, device_number=0, timeout=10, output_path=None):
    """
    Send a dump request and capture the response.

    Args:
        address: Tuple of (AH, AM, AL) - the address to request
        port_name: MIDI port name
        device_number: MIDI device number (0-15)
        timeout: Response timeout in seconds
        output_path: Output file path (auto if None)
    """
    in_port = find_midi_port(port_name, "input")
    out_port = find_midi_port(port_name, "output")

    if not in_port or not out_port:
        print("ERROR: No MIDI ports found.")
        return None

    ah, am, al = address
    print(f"Ports: IN={in_port}, OUT={out_port}")
    print(f"Address: {ah:02X} {am:02X} {al:02X}")
    print(f"Device: {device_number}")
    print()

    # Build dump request: F0 43 2n 5F AH AM AL F7
    # Note: mido strips F0/F7, so data = [43, 2n, 5F, AH, AM, AL]
    request_data = [0x43, 0x20 | (device_number & 0x0F), 0x5F, ah, am, al]
    request = mido.Message("sysex", data=request_data)

    print(f"Sending: F0 {' '.join(f'{b:02X}' for b in request_data)} F7")

    responses = []

    with mido.open_input(in_port) as inport:
        with mido.open_output(out_port) as outport:
            # Flush
            for _ in inport.iter_pending():
                pass

            outport.send(request)

            start = time.time()
            last_msg = time.time()

            while time.time() - start < timeout:
                msg = inport.poll()
                if msg and msg.type == "sysex":
                    responses.append(msg)
                    last_msg = time.time()
                    msg_bytes = len(msg.data) + 2
                    preview = " ".join(f"{b:02X}" for b in msg.data[:12])
                    print(f"  Response [{len(responses)}]: {preview}... ({msg_bytes} bytes)")

                    # Check for close message
                    if len(msg.data) >= 7:
                        if (
                            msg.data[0] == 0x43
                            and (msg.data[1] & 0xF0) == 0x10
                            and msg.data[2] == 0x5F
                            and all(b == 0 for b in msg.data[3:7])
                        ):
                            print("  (Close message - dump complete)")
                            break

                elif responses and time.time() - last_msg > 2:
                    # Idle after receiving data
                    break

                time.sleep(0.005)

    if not responses:
        print(f"\nNo response within {timeout}s.")
        return None

    # Save
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(__file__).parent / "captured"
        output_dir.mkdir(exist_ok=True)
        addr_str = f"{ah:02X}{am:02X}{al:02X}"
        output_path = output_dir / f"qy70_req_{addr_str}_{timestamp}.syx"
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    raw_data = bytearray()
    for msg in responses:
        raw_data.append(0xF0)
        raw_data.extend(msg.data)
        raw_data.append(0xF7)

    with open(output_path, "wb") as f:
        f.write(raw_data)

    print(f"\nSaved {len(responses)} messages ({len(raw_data)} bytes) to: {output_path}")
    return output_path


def request_full_style(port_name=None, device_number=0, timeout=30, output_path=None):
    """Request a complete style dump from QY70."""
    in_port = find_midi_port(port_name, "input")
    out_port = find_midi_port(port_name, "output")

    if not in_port or not out_port:
        print("ERROR: No MIDI ports found.")
        return None

    print(f"Ports: IN={in_port}, OUT={out_port}")
    print("Requesting full style dump...")
    print()

    # Request addresses for a complete style:
    # 0x7F = Header
    # 0x00-0x05 = Section phrase data
    # 0x08-0x37 = Track data (6 sections * 8 tracks)
    addresses = []

    # Section phrase data
    for sec in range(6):
        addresses.append((0x02, 0x7E, sec))

    # Track data
    for sec in range(6):
        for trk in range(8):
            al = 0x08 + (sec * 8) + trk
            addresses.append((0x02, 0x7E, al))

    # Header last
    addresses.append((0x02, 0x7E, 0x7F))

    all_messages = []

    with mido.open_input(in_port) as inport:
        with mido.open_output(out_port) as outport:
            for i, (ah, am, al) in enumerate(addresses):
                # Flush
                for _ in inport.iter_pending():
                    pass

                # Send request
                request_data = [0x43, 0x20 | (device_number & 0x0F), 0x5F, ah, am, al]
                outport.send(mido.Message("sysex", data=request_data))

                print(
                    f"  [{i + 1}/{len(addresses)}] Request {ah:02X} {am:02X} {al:02X}...",
                    end="",
                )

                # Wait for response
                start = time.time()
                got_response = False
                while time.time() - start < 3:  # 3s per address
                    msg = inport.poll()
                    if msg and msg.type == "sysex":
                        all_messages.append(msg)
                        got_response = True
                        # Brief wait for multi-part responses
                        time.sleep(0.1)
                        for extra in inport.iter_pending():
                            if extra.type == "sysex":
                                all_messages.append(extra)
                        break
                    time.sleep(0.005)

                if got_response:
                    print(f" OK ({len(all_messages)} total msgs)")
                else:
                    print(" no response")

                time.sleep(0.05)  # Small delay between requests

    if not all_messages:
        print("\nNo data received.")
        return None

    # Save
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(__file__).parent / "captured"
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / f"qy70_style_{timestamp}.syx"
    else:
        output_path = Path(output_path)

    raw_data = bytearray()
    for msg in all_messages:
        raw_data.append(0xF0)
        raw_data.extend(msg.data)
        raw_data.append(0xF7)

    with open(output_path, "wb") as f:
        f.write(raw_data)

    print(f"\nSaved {len(all_messages)} messages ({len(raw_data)} bytes) to: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Send SysEx dump request to QY70")
    parser.add_argument(
        "--address",
        nargs=3,
        type=lambda x: int(x, 16),
        help="Address as 3 hex bytes: AH AM AL (e.g., 02 7E 7F)",
    )
    parser.add_argument("--style", action="store_true", help="Request full style dump")
    parser.add_argument("--port", default=None, help="MIDI port name")
    parser.add_argument("--device", type=int, default=0, help="MIDI device number (0-15)")
    parser.add_argument("--timeout", type=int, default=10, help="Response timeout in seconds")
    parser.add_argument("--output", "-o", default=None, help="Output file path")
    args = parser.parse_args()

    print("=" * 60)
    print("QY70 Dump Request")
    print("=" * 60)
    print()

    if args.style:
        result = request_full_style(args.port, args.device, args.timeout, args.output)
    elif args.address:
        result = send_dump_request(
            tuple(args.address), args.port, args.device, args.timeout, args.output
        )
    else:
        parser.print_help()
        print("\nExamples:")
        print("  python3 midi_tools/send_request.py --address 02 7E 7F   # Header")
        print("  python3 midi_tools/send_request.py --style              # Full style")
        return 1

    return 0 if result else 1


if __name__ == "__main__":
    sys.exit(main())
