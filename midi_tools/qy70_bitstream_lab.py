#!/usr/bin/env python3
"""
QY70 Bitstream Decoding Laboratory.

Automated experiments to reverse-engineer the QY70's internal note encoding.
Sends controlled patterns via SysEx, dumps them back, and analyzes differences.

Strategy:
  1. Dump current edit buffer as baseline
  2. Send simple test patterns (1 note, 2 notes, etc.)
  3. Dump after each write
  4. Binary diff reveals the encoding

Requires: Steinberg UR22C connected bidirectionally to QY70.
"""

import json
import struct
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import rtmidi


# ─── Constants ────────────────────────────────────────────────────────

SYSEX_START = 0xF0
SYSEX_END = 0xF7
YAMAHA_ID = 0x43
QY70_MODEL_ID = 0x5F
STYLE_AH = 0x02
EDIT_BUFFER_AM = 0x7E

# Timing
INIT_DELAY = 0.3
MSG_DELAY = 0.15
DUMP_WAIT = 1.5
BETWEEN_EXPERIMENTS = 0.5


# ─── Low-level SysEx helpers ─────────────────────────────────────────

def yamaha_checksum(data: bytes) -> int:
    return (0x80 - (sum(data) & 0x7F)) & 0x7F


def encode_7bit(data: bytes) -> bytes:
    result = bytearray()
    for i in range(0, len(data), 7):
        block = data[i:i + 7]
        msb_byte = 0
        for j, b in enumerate(block):
            if b & 0x80:
                msb_byte |= (1 << (6 - j))
        result.append(msb_byte)
        for b in block:
            result.append(b & 0x7F)
    return bytes(result)


def decode_7bit(encoded: bytes) -> bytes:
    """Decode 7-bit Yamaha format back to 8-bit."""
    result = bytearray()
    pos = 0
    while pos < len(encoded):
        if pos + 1 > len(encoded):
            break
        msb_byte = encoded[pos]
        pos += 1
        for j in range(7):
            if pos >= len(encoded):
                break
            byte_val = encoded[pos]
            if msb_byte & (1 << (6 - j)):
                byte_val |= 0x80
            result.append(byte_val)
            pos += 1
    return bytes(result)


def make_init():
    return bytes([SYSEX_START, YAMAHA_ID, 0x10, QY70_MODEL_ID,
                  0x00, 0x00, 0x00, 0x01, SYSEX_END])


def make_close():
    return bytes([SYSEX_START, YAMAHA_ID, 0x10, QY70_MODEL_ID,
                  0x00, 0x00, 0x00, 0x00, SYSEX_END])


def make_dump_request(al: int):
    """F0 43 20 5F 02 7E AL F7"""
    return bytes([SYSEX_START, YAMAHA_ID, 0x20, QY70_MODEL_ID,
                  STYLE_AH, EDIT_BUFFER_AM, al, SYSEX_END])


def make_bulk_dump(al: int, payload_128: bytes) -> bytes:
    """Create bulk dump message for 128-byte payload."""
    encoded = encode_7bit(payload_128)
    bc = len(encoded)
    bh = (bc >> 7) & 0x7F
    bl = bc & 0x7F
    cs_data = bytes([bh, bl, STYLE_AH, EDIT_BUFFER_AM, al]) + encoded
    cs = yamaha_checksum(cs_data)
    msg = bytearray([SYSEX_START, YAMAHA_ID, 0x00, QY70_MODEL_ID,
                      bh, bl, STYLE_AH, EDIT_BUFFER_AM, al])
    msg.extend(encoded)
    msg.append(cs)
    msg.append(SYSEX_END)
    return bytes(msg)


# ─── MIDI I/O ─────────────────────────────────────────────────────────

class QY70Link:
    """Bidirectional MIDI link to QY70."""

    def __init__(self, out_port: int = 0, in_port: int = 0):
        self.midiout = rtmidi.MidiOut()
        self.midiin = rtmidi.MidiIn()
        self.midiin.ignore_types(sysex=False, timing=False, active_sense=False)
        self.midiout.open_port(out_port)
        self.midiin.open_port(in_port)
        # Flush input
        while self.midiin.get_message():
            pass

    def close(self):
        del self.midiin
        del self.midiout

    def send(self, msg: bytes):
        self.midiout.send_message(list(msg))

    def receive_sysex(self, timeout: float = DUMP_WAIT) -> List[bytes]:
        """Receive SysEx messages until timeout."""
        messages = []
        start = time.time()
        while time.time() - start < timeout:
            msg = self.midiin.get_message()
            if msg:
                data, _ = msg
                if data[0] == SYSEX_START:
                    messages.append(bytes(data))
                    start = time.time()  # Reset timeout on each message
            else:
                time.sleep(0.005)
        return messages

    def init_handshake(self):
        """Send init message."""
        self.send(make_init())
        time.sleep(INIT_DELAY)

    def close_handshake(self):
        """Send close message."""
        self.send(make_close())
        time.sleep(0.1)

    def dump_track(self, al: int) -> Optional[bytes]:
        """Request and receive a single track dump."""
        # Flush
        while self.midiin.get_message():
            pass

        self.send(make_dump_request(al))
        time.sleep(MSG_DELAY)

        msgs = self.receive_sysex(timeout=1.0)
        if not msgs:
            return None

        # Parse and decode the response(s)
        decoded_blocks = []
        for msg in msgs:
            if len(msg) < 12:
                continue
            if msg[3] != QY70_MODEL_ID:
                continue
            # Extract encoded payload
            payload = msg[9:-2]  # Between address and checksum
            decoded = decode_7bit(payload)
            decoded_blocks.append(decoded)

        if decoded_blocks:
            return b"".join(decoded_blocks)
        return None

    def dump_all_tracks(self, verbose: bool = False) -> Dict[int, bytes]:
        """Dump all tracks from edit buffer."""
        self.init_handshake()
        tracks = {}

        # Try all possible AL values for the edit buffer
        # Sections 0-5 × 8 tracks + header
        als_to_try = list(range(0x30)) + [0x7F]

        for al in als_to_try:
            data = self.dump_track(al)
            if data and len(data) > 0:
                tracks[al] = data
                if verbose:
                    hex_preview = " ".join(f"{b:02X}" for b in data[:24])
                    print(f"  AL=0x{al:02X}: {len(data):4d}B  {hex_preview}...")

        self.close_handshake()
        return tracks

    def send_pattern(self, track_blocks: Dict[int, bytes],
                     header_data: Optional[bytes] = None):
        """Send a complete pattern to QY70 edit buffer."""
        self.init_handshake()
        time.sleep(0.1)

        for al, payload in sorted(track_blocks.items()):
            # Pad to 128 bytes if needed
            if len(payload) < 128:
                padded = bytearray(128)
                padded[:len(payload)] = payload
                payload = bytes(padded)

            msg = make_bulk_dump(al, payload[:128])
            self.send(msg)
            time.sleep(MSG_DELAY)

        if header_data:
            # Send header in 128-byte chunks
            for i in range(0, len(header_data), 128):
                chunk = header_data[i:i + 128]
                if len(chunk) < 128:
                    padded = bytearray(128)
                    padded[:len(chunk)] = chunk
                    chunk = bytes(padded)
                msg = make_bulk_dump(0x7F, chunk)
                self.send(msg)
                time.sleep(MSG_DELAY)

        self.close_handshake()


# ─── Experiment Framework ─────────────────────────────────────────────

def hex_dump_compare(label_a: str, data_a: bytes,
                     label_b: str, data_b: bytes, max_lines: int = 30):
    """Print side-by-side hex comparison highlighting differences."""
    max_len = max(len(data_a), len(data_b))
    diffs = []
    for i in range(max_len):
        a = data_a[i] if i < len(data_a) else None
        b = data_b[i] if i < len(data_b) else None
        if a != b:
            diffs.append((i, a, b))

    if not diffs:
        print(f"  {label_a} vs {label_b}: IDENTICAL ({len(data_a)} bytes)")
        return

    print(f"  {label_a} ({len(data_a)}B) vs {label_b} ({len(data_b)}B): "
          f"{len(diffs)} bytes differ")
    for offset, a, b in diffs[:max_lines]:
        a_str = f"{a:02X}" if a is not None else "--"
        b_str = f"{b:02X}" if b is not None else "--"
        print(f"    offset {offset:3d} (0x{offset:02X}): {a_str} → {b_str}")
    if len(diffs) > max_lines:
        print(f"    ... and {len(diffs) - max_lines} more differences")


def save_experiment(name: str, tracks: Dict[int, bytes], output_dir: Path):
    """Save experiment results."""
    output_dir.mkdir(parents=True, exist_ok=True)
    result = {}
    for al, data in tracks.items():
        result[f"0x{al:02X}"] = data.hex()
    path = output_dir / f"{name}.json"
    with open(path, "w") as f:
        json.dump(result, f, indent=2)
    return path


def load_experiment(path: Path) -> Dict[int, bytes]:
    """Load saved experiment."""
    with open(path) as f:
        data = json.load(f)
    return {int(k, 16): bytes.fromhex(v) for k, v in data.items()}


# ─── Main Experiment Sequence ─────────────────────────────────────────

def run_experiments():
    """Run the full experiment sequence."""
    output_dir = Path("data/qy70_bitstream_lab")
    output_dir.mkdir(parents=True, exist_ok=True)

    link = QY70Link()

    try:
        # ═══════════════════════════════════════════════════
        # PHASE 1: Dump current state as baseline
        # ═══════════════════════════════════════════════════
        print("=" * 60)
        print("PHASE 1: Dumping current QY70 edit buffer")
        print("=" * 60)

        baseline = link.dump_all_tracks(verbose=True)
        if not baseline:
            print("ERROR: No data received from QY70!")
            return

        save_experiment("00_baseline", baseline, output_dir)
        print(f"\nBaseline: {len(baseline)} track slots with data")

        # Analyze baseline
        print("\nBaseline analysis:")
        for al in sorted(baseline.keys()):
            data = baseline[al]
            nonzero = sum(1 for b in data if b != 0)
            is_header = al == 0x7F
            label = "HEADER" if is_header else f"S{al // 8}T{al % 8}"
            print(f"  {label} (AL=0x{al:02X}): {len(data):4d}B, "
                  f"{nonzero} non-zero bytes")

        time.sleep(BETWEEN_EXPERIMENTS)

        # ═══════════════════════════════════════════════════
        # PHASE 2: Send empty pattern, dump back
        # ═══════════════════════════════════════════════════
        print("\n" + "=" * 60)
        print("PHASE 2: Send minimal empty pattern → dump → compare")
        print("=" * 60)

        # Build simplest possible track: just a header, no MIDI data
        empty_track = bytearray(128)
        # Standard QY70 track header (observed in all dumps)
        empty_track[0:12] = bytes([
            0x08, 0x04, 0x82, 0x01, 0x00, 0x40, 0x20,
            0x08, 0x04, 0x82, 0x01, 0x00
        ])
        empty_track[12:14] = bytes([0x06, 0x1C])
        empty_track[14] = 0x40  # Drum marker
        empty_track[15] = 0x80
        empty_track[16] = 0x87
        empty_track[17] = 0xF8

        # Build minimal header (640 bytes = 5 × 128)
        header = bytearray(640)
        # Tempo = 120 BPM → range=2, offset=63
        header[0] = 63  # offset
        header[5] |= 0x80  # range bit 1
        header[6] |= 0x80  # range bit 0 → range = 0b010 = 2

        # Send just RHY1 (AL=0x00) + header
        print("Sending empty RHY1 track + header...")
        link.send_pattern(
            {0x00: bytes(empty_track)},
            header_data=bytes(header)
        )
        time.sleep(1.0)

        # Dump back
        print("Dumping after write...")
        after_empty = link.dump_all_tracks(verbose=True)
        save_experiment("01_empty_pattern", after_empty, output_dir)

        # Compare with baseline
        if 0x00 in baseline and 0x00 in after_empty:
            print("\nComparing AL=0x00 (RHY1):")
            hex_dump_compare("baseline", baseline[0x00],
                             "after_empty", after_empty[0x00])
        if 0x7F in baseline and 0x7F in after_empty:
            print("\nComparing AL=0x7F (HEADER):")
            hex_dump_compare("baseline", baseline[0x7F],
                             "after_empty", after_empty[0x7F])

        time.sleep(BETWEEN_EXPERIMENTS)

        # ═══════════════════════════════════════════════════
        # PHASE 3: Vary one thing at a time
        # ═══════════════════════════════════════════════════
        print("\n" + "=" * 60)
        print("PHASE 3: Progressive single-variable experiments")
        print("=" * 60)

        experiments = [
            # (name, description, modifications to empty_track)
            ("02_byte24_F2", "Set byte 24 = F2 (end marker?)",
             {24: 0xF2}),
            ("03_byte24_D0", "Set byte 24-27 = D0 3C 24 48 (kick note)",
             {24: 0xD0, 25: 0x3C, 26: 0x24, 27: 0x48}),
            ("04_note_area_fill", "Fill bytes 24-31 with test note pattern",
             {24: 0xD0, 25: 0x3C, 26: 0x24, 27: 0x48,
              28: 0xA3, 29: 0x60, 30: 0xF2, 31: 0x00}),
            ("05_velocity_test", "Same note but velocity=127",
             {24: 0xD0, 25: 0x7F, 26: 0x24, 27: 0x48,
              28: 0xA3, 29: 0x60, 30: 0xF2, 31: 0x00}),
            ("06_note_change", "Change note from 36(kick) to 38(snare)",
             {24: 0xD0, 25: 0x3C, 26: 0x26, 27: 0x48,
              28: 0xA3, 29: 0x60, 30: 0xF2, 31: 0x00}),
            ("07_two_notes", "Two kick notes with delta",
             {24: 0xD0, 25: 0x3C, 26: 0x24, 27: 0x48,
              28: 0xA3, 29: 0x60,
              30: 0xD0, 31: 0x3C, 32: 0x24, 33: 0x48,
              34: 0xA3, 35: 0x60, 36: 0xF2}),
            ("08_melody_E0", "Single melody note E0 format",
             {24: 0xE0, 25: 0x1E, 26: 0x00, 27: 0x3C, 28: 0x7F,
              29: 0xBE, 30: 0x00, 31: 0xF2}),
        ]

        for exp_name, description, mods in experiments:
            print(f"\n--- {exp_name}: {description} ---")

            # Build modified track
            test_track = bytearray(empty_track)
            for offset, value in mods.items():
                test_track[offset] = value

            # Show what we're sending
            hex_data = " ".join(f"{b:02X}" for b in test_track[20:40])
            print(f"  Sending bytes 20-39: {hex_data}")

            # Send
            link.send_pattern({0x00: bytes(test_track)}, header_data=bytes(header))
            time.sleep(0.8)

            # Dump back
            result = link.dump_all_tracks(verbose=False)
            save_experiment(exp_name, result, output_dir)

            # Compare AL=0x00 with the empty version
            if 0x00 in after_empty and 0x00 in result:
                hex_dump_compare(
                    "empty", after_empty[0x00],
                    exp_name, result[0x00],
                    max_lines=20
                )
            elif 0x00 in result:
                data = result[0x00]
                hex_preview = " ".join(f"{b:02X}" for b in data[:40])
                print(f"  Received: {hex_preview}...")

            time.sleep(BETWEEN_EXPERIMENTS)

        # ═══════════════════════════════════════════════════
        # FINAL: Summary
        # ═══════════════════════════════════════════════════
        print("\n" + "=" * 60)
        print("EXPERIMENT COMPLETE")
        print("=" * 60)
        print(f"Results saved to: {output_dir}/")

        # List all saved files
        for f in sorted(output_dir.glob("*.json")):
            print(f"  {f.name}")

    finally:
        link.close()


if __name__ == "__main__":
    run_experiments()
