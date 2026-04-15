#!/usr/bin/env python3
"""Analyze the SysEx message structure for SGT style.

Check: are all 6 D1 messages event data, or are some header/config data?
Compare message ordering and content between known_pattern and SGT.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qymanager.formats.qy70.sysex_parser import SysExParser
from midi_tools.event_decoder import rot_right, extract_9bit

def analyze_messages(syx_path, label):
    """Show all messages for a SysEx file."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)

    print(f"\n{'='*70}")
    print(f"  {label}: {syx_path}")
    print(f"  Total messages: {len(messages)}")
    print(f"{'='*70}")

    # Group by track (AL)
    tracks = {}
    for m in messages:
        if not m.is_style_data:
            continue
        al = m.address_low
        tracks.setdefault(al, []).append(m)

    for al in sorted(tracks.keys()):
        msgs = tracks[al]
        section = al // 8
        track = al % 8
        track_names = {0:"RHY1",1:"RHY2",2:"BASS",3:"CHD1",
                      4:"CHD2",5:"PAD",6:"PHR1",7:"PHR2"}
        tn = track_names.get(track, f"T{track}")

        print(f"\n  AL={al:02X} → Section {section} Track {track} ({tn}): "
              f"{len(msgs)} messages")

        total_decoded = 0
        for mi, m in enumerate(msgs):
            data = m.decoded_data if m.decoded_data else b''
            total_decoded += len(data)

            # Show address fields
            ah = m.address_high if hasattr(m, 'address_high') else '?'
            am = m.address_mid if hasattr(m, 'address_mid') else '?'

            # First 32 bytes hex
            hex_preview = ' '.join(f'{b:02X}' for b in data[:32])

            # Check for known header pattern
            is_track_header = (data[:12] == bytes.fromhex('080482010040200804820100')
                              if len(data) >= 12 else False)

            # Count zero bytes
            zero_count = sum(1 for b in data if b == 0)
            zero_pct = (zero_count / len(data) * 100) if data else 0

            # Look for delimiters in this message
            dc_count = sum(1 for b in data if b == 0xDC)
            se_count = sum(1 for b in data if b == 0x9E)

            print(f"    Msg {mi}: AH={ah} AM={am} → {len(data)} bytes, "
                  f"zeros={zero_pct:.0f}%, DC={dc_count}, 9E={se_count}"
                  f"{' [TRACK HEADER]' if is_track_header else ''}")
            print(f"      {hex_preview}{'...' if len(data) > 32 else ''}")

        print(f"    Total decoded: {total_decoded} bytes")


def compare_rhy1_messages(syx_path):
    """Deep comparison of RHY1 messages — check if they form continuous stream."""
    parser = SysExParser()
    messages = parser.parse_file(syx_path)

    rhy1_msgs = [m for m in messages
                 if m.is_style_data and m.address_low == 0
                 and m.decoded_data]

    if not rhy1_msgs:
        print("No RHY1 messages found")
        return

    print(f"\n{'='*70}")
    print(f"  RHY1 MESSAGE BOUNDARY ANALYSIS")
    print(f"{'='*70}")

    # Show last 8 bytes of each message and first 8 of next
    for i in range(len(rhy1_msgs)):
        data = rhy1_msgs[i].decoded_data
        msg_end = ' '.join(f'{b:02X}' for b in data[-8:])
        if i + 1 < len(rhy1_msgs):
            next_data = rhy1_msgs[i + 1].decoded_data
            msg_start = ' '.join(f'{b:02X}' for b in next_data[:8])
            print(f"  Msg {i} end:   ...{msg_end}")
            print(f"  Msg {i+1} start: {msg_start}...")
            print()
        else:
            print(f"  Msg {i} end:   ...{msg_end}")

    # Test: what if we parse events from message 1 onwards (skipping msg 0)?
    print(f"\n  Test: decode from message 1 onwards (skip message 0)")
    concat_from_1 = b''.join(m.decoded_data for m in rhy1_msgs[1:])
    print(f"  Data from msg 1+: {len(concat_from_1)} bytes")
    print(f"  First 28 bytes: {' '.join(f'{b:02X}' for b in concat_from_1[:28])}")

    # Check if this has the track header pattern
    has_header = (concat_from_1[:12] == bytes.fromhex('080482010040200804820100')
                  if len(concat_from_1) >= 12 else False)
    print(f"  Has track header: {has_header}")

    # Also check: is message 0 just the 28-byte header + initialization?
    msg0 = rhy1_msgs[0].decoded_data
    print(f"\n  Message 0 analysis ({len(msg0)} bytes):")
    print(f"    Track header: {msg0[:28].hex()}")
    print(f"    Preamble: {msg0[24:28].hex()}")
    print(f"    Event area ({len(msg0)-28} bytes):")

    event_area = msg0[28:]
    # Check for bar structure
    delims = [(i, event_area[i]) for i in range(len(event_area))
              if event_area[i] in (0xDC, 0x9E)]
    print(f"    Delimiters: {delims}")

    # Try decoding first event from msg0 event area
    if len(event_area) >= 20:
        header = event_area[:13]
        evt0 = event_area[13:20]
        print(f"    Header: {header.hex()}")
        print(f"    Event 0: {evt0.hex()}")

        val = int.from_bytes(evt0, "big")
        for r in [9, 18, 27, 36, 45, 54, 7]:
            derot = rot_right(val, r)
            f0 = extract_9bit(derot, 0)
            note = f0 & 0x7F
            print(f"      R={r:2d}: note={note:3d}")


def analyze_known_pattern_structure():
    """How many messages does known_pattern have?"""
    parser = SysExParser()
    messages = parser.parse_file("midi_tools/captured/known_pattern.syx")

    rhy1_msgs = [m for m in messages
                 if m.is_style_data and m.address_low == 0
                 and m.decoded_data]

    print(f"\n{'='*70}")
    print(f"  KNOWN_PATTERN: {len(rhy1_msgs)} RHY1 messages")
    print(f"{'='*70}")

    for i, m in enumerate(rhy1_msgs):
        data = m.decoded_data
        ah = m.address_high if hasattr(m, 'address_high') else '?'
        am = m.address_mid if hasattr(m, 'address_mid') else '?'
        zero_pct = sum(1 for b in data if b == 0) / len(data) * 100
        print(f"  Msg {i}: AH={ah} AM={am} {len(data)} bytes, zeros={zero_pct:.0f}%")
        print(f"    {data.hex()[:80]}...")


def main():
    analyze_known_pattern_structure()
    analyze_messages("tests/fixtures/QY70_SGT.syx", "SGT Style")
    compare_rhy1_messages("tests/fixtures/QY70_SGT.syx")


if __name__ == "__main__":
    main()
