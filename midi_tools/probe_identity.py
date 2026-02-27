#!/usr/bin/env python3
"""
Send MIDI Identity Request (Universal SysEx) and listen for response.

This is the safest way to verify the QY70 is connected and responding.
The Identity Request is a standard MIDI message that all devices should respond to.

Request:  F0 7E 7F 06 01 F7  (Universal Non-Realtime, Identity Request)
Response: F0 7E nn 06 02 43 ... F7  (Yamaha manufacturer ID = 0x43)

Usage:
    python3 midi_tools/probe_identity.py [--port "USB Midi Cable"] [--timeout 5]
"""

import sys
import time
import argparse
import mido


def find_midi_port(port_name=None, direction="input"):
    """Find a MIDI port by name or return the first available."""
    if direction == "input":
        ports = mido.get_input_names()
    else:
        ports = mido.get_output_names()

    if not ports:
        return None

    if port_name:
        # Exact match
        if port_name in ports:
            return port_name
        # Partial match
        matches = [p for p in ports if port_name.lower() in p.lower()]
        if matches:
            return matches[0]
        return None

    # Default: first port with "MIDI" or "USB" in name
    for p in ports:
        if "midi" in p.lower() or "usb" in p.lower():
            return p
    return ports[0]


def send_identity_request(port_name=None, timeout=5):
    """Send Identity Request and wait for response."""
    in_port_name = find_midi_port(port_name, "input")
    out_port_name = find_midi_port(port_name, "output")

    if not in_port_name or not out_port_name:
        print("ERROR: No MIDI ports found.")
        print("       Connect your USB-MIDI interface and try again.")
        return False

    print(f"Input port:  {in_port_name}")
    print(f"Output port: {out_port_name}")
    print()

    # Identity Request: F0 7E 7F 06 01 F7
    # 7E = Universal Non-Realtime
    # 7F = All devices (broadcast)
    # 06 01 = General Information: Identity Request
    identity_request = mido.Message("sysex", data=[0x7E, 0x7F, 0x06, 0x01])

    print(f"Sending Identity Request: F0 {' '.join(f'{b:02X}' for b in identity_request.data)} F7")
    print(f"Waiting {timeout}s for response...")
    print()

    responses = []

    with mido.open_input(in_port_name) as inport:
        with mido.open_output(out_port_name) as outport:
            # Flush any pending messages
            for _ in inport.iter_pending():
                pass

            # Send request
            outport.send(identity_request)

            # Wait for response
            start = time.time()
            while time.time() - start < timeout:
                msg = inport.poll()
                if msg:
                    if msg.type == "sysex":
                        responses.append(msg)
                        print(f"SysEx received: F0 {' '.join(f'{b:02X}' for b in msg.data)} F7")

                        # Parse Identity Reply
                        if len(msg.data) >= 5 and msg.data[1] == 0x06 and msg.data[2] == 0x02:
                            manufacturer = msg.data[3]
                            print(f"\n  Identity Reply detected!")
                            print(f"  Device number: {msg.data[0]}")

                            if manufacturer == 0x43:
                                print(f"  Manufacturer: Yamaha (0x43)")
                                if len(msg.data) >= 7:
                                    family = (msg.data[5] << 8) | msg.data[4]
                                    print(f"  Device family: 0x{family:04X}")
                                if len(msg.data) >= 9:
                                    member = (msg.data[7] << 8) | msg.data[6]
                                    print(f"  Device member: 0x{member:04X}")
                                if len(msg.data) >= 13:
                                    version = (
                                        f"{msg.data[8]}.{msg.data[9]}.{msg.data[10]}.{msg.data[11]}"
                                    )
                                    print(f"  Firmware version: {version}")
                                print("\n  >>> QY70 connection CONFIRMED!")
                            else:
                                mfr_names = {
                                    0x41: "Roland",
                                    0x42: "Korg",
                                    0x43: "Yamaha",
                                    0x44: "Casio",
                                    0x7E: "Universal Non-Realtime",
                                }
                                mfr_name = mfr_names.get(
                                    manufacturer, f"Unknown (0x{manufacturer:02X})"
                                )
                                print(f"  Manufacturer: {mfr_name}")
                    else:
                        # Non-SysEx messages (notes, CC, etc.)
                        print(f"  Other: {msg}")
                time.sleep(0.01)

    if not responses:
        print("No SysEx response received.")
        print()
        print("Troubleshooting:")
        print("  1. Is the QY70 powered on?")
        print("  2. MIDI cables correct? (QY70 OUT -> Interface IN, QY70 IN -> Interface OUT)")
        print("  3. Try swapping IN/OUT cables if no response")
        print("  4. Check QY70 MIDI settings: Utility -> MIDI -> SysEx = On")
        return False

    return True


def main():
    parser = argparse.ArgumentParser(description="Send MIDI Identity Request to QY70")
    parser.add_argument("--port", default=None, help="MIDI port name (default: auto-detect)")
    parser.add_argument("--timeout", type=int, default=5, help="Response timeout in seconds")
    args = parser.parse_args()

    print("=" * 60)
    print("QY70 Identity Probe")
    print("=" * 60)
    print()

    success = send_identity_request(args.port, args.timeout)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
