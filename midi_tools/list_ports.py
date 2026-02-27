#!/usr/bin/env python3
"""
List available MIDI ports and their details.

Usage:
    python3 midi_tools/list_ports.py
"""

import sys
import mido


def main():
    print("=" * 60)
    print("MIDI Port Scanner")
    print("=" * 60)

    inputs = mido.get_input_names()
    outputs = mido.get_output_names()

    print(f"\nInput ports ({len(inputs)}):")
    if inputs:
        for i, name in enumerate(inputs):
            print(f"  [{i}] {name}")
    else:
        print("  (none found)")

    print(f"\nOutput ports ({len(outputs)}):")
    if outputs:
        for i, name in enumerate(outputs):
            print(f"  [{i}] {name}")
    else:
        print("  (none found)")

    # Check for USB Midi Cable specifically
    midi_cable = [n for n in inputs if "USB Midi" in n or "MIDI" in n.upper()]
    if midi_cable:
        print(f"\n>>> QY70 interface detected: '{midi_cable[0]}'")
        print("    Ready for MIDI communication.")
    else:
        print("\n>>> No USB MIDI interface detected.")
        print("    Connect your USB-MIDI cable and try again.")

    return 0 if (inputs and outputs) else 1


if __name__ == "__main__":
    sys.exit(main())
