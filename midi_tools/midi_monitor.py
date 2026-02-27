#!/usr/bin/env python3
"""
MIDI Monitor - Listen for ANY incoming MIDI data.

Use this to verify the physical connection:
1. Run this script
2. Press keys/pads on the QY70, or start playback
3. If you see messages, the MIDI OUT -> IN cable works
4. If nothing appears, cables are wrong or QY70 is off

Usage:
    python3 midi_tools/midi_monitor.py [--timeout 30]
"""

import sys
import time
import argparse
import mido


def main():
    parser = argparse.ArgumentParser(description="Monitor ALL incoming MIDI data")
    parser.add_argument("--port", default=None, help="MIDI port name")
    parser.add_argument("--timeout", type=int, default=30, help="Listen duration in seconds")
    args = parser.parse_args()

    ports = mido.get_input_names()
    if not ports:
        print("ERROR: No MIDI input ports found.")
        return 1

    port_name = args.port
    if port_name is None:
        for p in ports:
            if "midi" in p.lower() or "usb" in p.lower():
                port_name = p
                break
        if port_name is None:
            port_name = ports[0]

    print("=" * 60)
    print("MIDI Monitor")
    print("=" * 60)
    print(f"Port: {port_name}")
    print(f"Duration: {args.timeout}s")
    print()
    print("Listening for ANY MIDI data...")
    print(">>> Do something on the QY70:")
    print("    - Press a pad/key")
    print("    - Start playback")
    print("    - Change a parameter")
    print()
    print("If nothing appears, check cables:")
    print("  QY70 MIDI OUT --> USB Interface MIDI IN  (for receiving)")
    print("  QY70 MIDI IN  <-- USB Interface MIDI OUT (for sending)")
    print()
    print("-" * 60)

    count = 0
    with mido.open_input(port_name) as inport:
        # Flush
        for _ in inport.iter_pending():
            pass

        start = time.time()
        while time.time() - start < args.timeout:
            msg = inport.poll()
            if msg:
                count += 1
                elapsed = time.time() - start
                if msg.type == "sysex":
                    data_hex = " ".join(f"{b:02X}" for b in msg.data[:20])
                    if len(msg.data) > 20:
                        data_hex += " ..."
                    print(
                        f"[{elapsed:6.2f}s] #{count:3d} SysEx: F0 {data_hex} F7  ({len(msg.data) + 2} bytes)"
                    )
                elif msg.type == "note_on":
                    print(
                        f"[{elapsed:6.2f}s] #{count:3d} Note ON:  ch={msg.channel + 1:2d}  note={msg.note:3d}  vel={msg.velocity:3d}"
                    )
                elif msg.type == "note_off":
                    print(
                        f"[{elapsed:6.2f}s] #{count:3d} Note OFF: ch={msg.channel + 1:2d}  note={msg.note:3d}"
                    )
                elif msg.type == "control_change":
                    print(
                        f"[{elapsed:6.2f}s] #{count:3d} CC:       ch={msg.channel + 1:2d}  cc={msg.control:3d}  val={msg.value:3d}"
                    )
                elif msg.type == "program_change":
                    print(
                        f"[{elapsed:6.2f}s] #{count:3d} ProgChg:  ch={msg.channel + 1:2d}  prg={msg.program:3d}"
                    )
                elif msg.type == "clock":
                    if count <= 3 or count % 24 == 0:
                        print(f"[{elapsed:6.2f}s] #{count:3d} Clock (MIDI clock tick)")
                elif msg.type == "start":
                    print(f"[{elapsed:6.2f}s] #{count:3d} START (playback started)")
                elif msg.type == "stop":
                    print(f"[{elapsed:6.2f}s] #{count:3d} STOP (playback stopped)")
                elif msg.type == "active_sensing":
                    if count <= 1:
                        print(f"[{elapsed:6.2f}s] #{count:3d} Active Sensing (device is alive!)")
                        print(f"          >>> Connection CONFIRMED - QY70 is sending data")
                    # Don't print every active sensing (comes every 300ms)
                else:
                    print(f"[{elapsed:6.2f}s] #{count:3d} {msg}")
            time.sleep(0.002)

    print("-" * 60)
    print(f"Total messages received: {count}")
    if count == 0:
        print("\nNo data received. The MIDI OUT cable is not working.")
        print("Check: QY70 MIDI OUT port --> USB Interface MIDI IN port")
    else:
        print("\nConnection is working!")

    return 0 if count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
