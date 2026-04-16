#!/usr/bin/env python3
"""
Load a .syx file onto QY70 via SysEx, then dump it back for comparison.

Usage:
    python3 midi_tools/syx_loader.py "data/qy70_sysx/P -  Summer - 20231101.syx"
    python3 midi_tools/syx_loader.py FILE --dump-back --compare
    python3 midi_tools/syx_loader.py --list-ports
"""

import argparse
import json
import sys
import time
from pathlib import Path

import rtmidi


# ─── Constants ────────────────────────────────────────────────────────

SYSEX_START = 0xF0
SYSEX_END = 0xF7
YAMAHA_ID = 0x43
QY70_MODEL_ID = 0x5F
STYLE_AH = 0x02
EDIT_BUFFER_AM = 0x7E

INIT_DELAY = 0.5
MSG_DELAY = 0.15
DUMP_WAIT = 1.5


# ─── SysEx helpers ────────────────────────────────────────────────────

def split_syx_file(data: bytes) -> list:
    """Split a .syx file into individual SysEx messages."""
    msgs = []
    i = 0
    while i < len(data):
        if data[i] == SYSEX_START:
            try:
                j = data.index(SYSEX_END, i) + 1
                msgs.append(data[i:j])
                i = j
            except ValueError:
                break
        else:
            i += 1
    return msgs


def describe_msg(msg: bytes) -> str:
    """Human-readable description of a SysEx message."""
    if len(msg) == 9 and len(msg) > 3 and msg[3] == QY70_MODEL_ID:
        if msg[7] == 0x01:
            return "Init"
        elif msg[7] == 0x00:
            return "Close"
    if len(msg) > 8 and msg[1] == YAMAHA_ID and msg[3] == QY70_MODEL_ID:
        bh, bl = msg[4], msg[5]
        ah, am, al = msg[6], msg[7], msg[8]
        bc = (bh << 7) | bl
        return f"Bulk AH={ah:02X} AM={am:02X} AL={al:02X} ({bc}B payload)"
    return f"Unknown ({len(msg)}B)"


def decode_7bit(encoded: bytes) -> bytes:
    """Decode 7-bit Yamaha format back to 8-bit."""
    result = bytearray()
    pos = 0
    while pos < len(encoded):
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
    return bytes([SYSEX_START, YAMAHA_ID, 0x20, QY70_MODEL_ID,
                  STYLE_AH, EDIT_BUFFER_AM, al, SYSEX_END])


# ─── MIDI I/O ─────────────────────────────────────────────────────────

def find_port(midi_obj, keyword="UR22C"):
    """Find port index matching keyword."""
    for i in range(midi_obj.get_port_count()):
        name = midi_obj.get_port_name(i)
        if keyword.lower() in name.lower():
            return i
    return None


def list_ports():
    mo = rtmidi.MidiOut()
    mi = rtmidi.MidiIn()
    print("Output ports:")
    for i in range(mo.get_port_count()):
        print(f"  [{i}] {mo.get_port_name(i)}")
    print("Input ports:")
    for i in range(mi.get_port_count()):
        print(f"  [{i}] {mi.get_port_name(i)}")
    del mo, mi


def send_syx_file(syx_path: str, port_keyword: str = "UR22C",
                  verbose: bool = True) -> list:
    """Send a .syx file to QY70. Returns the messages sent."""
    data = Path(syx_path).read_bytes()
    msgs = split_syx_file(data)

    if not msgs:
        print("ERROR: No SysEx messages found in file", file=sys.stderr)
        return []

    if verbose:
        print(f"File: {syx_path} ({len(data)} bytes, {len(msgs)} messages)")

    # Open output port
    mo = rtmidi.MidiOut()
    port_idx = find_port(mo, port_keyword)
    if port_idx is None:
        print(f"ERROR: No MIDI port matching '{port_keyword}'", file=sys.stderr)
        print("Available ports:")
        for i in range(mo.get_port_count()):
            print(f"  [{i}] {mo.get_port_name(i)}")
        del mo
        return []

    mo.open_port(port_idx)
    if verbose:
        print(f"Port: {mo.get_port_name(port_idx)}")
        print()

    # Send messages
    for i, msg in enumerate(msgs):
        desc = describe_msg(msg)
        if verbose:
            print(f"  [{i:2d}] {desc} ({len(msg)}B)")

        mo.send_message(list(msg))

        # Longer delay after init, shorter for bulk data
        if len(msg) == 9 and msg[7] == 0x01:  # Init
            time.sleep(INIT_DELAY)
        elif len(msg) == 9 and msg[7] == 0x00:  # Close
            time.sleep(0.3)
        else:
            time.sleep(MSG_DELAY)

    del mo
    if verbose:
        print(f"\nDone — {len(msgs)} messages sent.")
    return msgs


def dump_back(port_keyword: str = "UR22C", verbose: bool = True) -> dict:
    """Dump all tracks from QY70 edit buffer. Returns {al: raw_sysex_msgs}."""
    mo = rtmidi.MidiOut()
    mi = rtmidi.MidiIn()
    mi.ignore_types(sysex=False, timing=False, active_sense=False)

    out_idx = find_port(mo, port_keyword)
    in_idx = find_port(mi, port_keyword)

    if out_idx is None or in_idx is None:
        print(f"ERROR: Port '{port_keyword}' not found", file=sys.stderr)
        del mo, mi
        return {}

    mo.open_port(out_idx)
    mi.open_port(in_idx)

    # Flush
    while mi.get_message():
        pass

    if verbose:
        print(f"Dumping edit buffer from {mo.get_port_name(out_idx)}...")

    # Init handshake
    mo.send_message(list(make_init()))
    time.sleep(INIT_DELAY)

    results = {}
    # Try Main A tracks (0x00-0x07), Main B (0x08-0x0F), header (0x7F)
    als = list(range(0x10)) + [0x7F]

    for al in als:
        # Flush
        while mi.get_message():
            pass

        mo.send_message(list(make_dump_request(al)))
        time.sleep(MSG_DELAY)

        # Collect response
        track_msgs = []
        start = time.time()
        while time.time() - start < DUMP_WAIT:
            msg = mi.get_message()
            if msg:
                data, _ = msg
                if data[0] == SYSEX_START and len(data) > 10:
                    track_msgs.append(bytes(data))
                    start = time.time()  # Reset on each msg
            else:
                time.sleep(0.005)

        if track_msgs:
            results[al] = track_msgs
            if verbose:
                total = sum(len(m) for m in track_msgs)
                print(f"  AL=0x{al:02X}: {len(track_msgs)} msg(s), {total}B total")

    # Close
    mo.send_message(list(make_close()))
    time.sleep(0.1)

    del mo, mi
    return results


def compare_sent_vs_received(sent_msgs: list, received: dict, verbose: bool = True):
    """Compare sent bulk data with dump-back results."""
    # Group sent messages by AL
    sent_by_al = {}
    for msg in sent_msgs:
        if len(msg) > 8 and msg[1] == YAMAHA_ID and msg[3] == QY70_MODEL_ID:
            if len(msg) < 12:
                continue
            al = msg[8]
            if al not in sent_by_al:
                sent_by_al[al] = []
            sent_by_al[al].append(msg)

    print(f"\n=== Comparison ===")
    print(f"Sent tracks: {sorted(f'0x{k:02X}' for k in sent_by_al.keys())}")
    print(f"Received tracks: {sorted(f'0x{k:02X}' for k in received.keys())}")

    for al in sorted(set(list(sent_by_al.keys()) + list(received.keys()))):
        sent_list = sent_by_al.get(al, [])
        recv_list = received.get(al, [])

        al_name = f"AL=0x{al:02X}"
        if al == 0x7F:
            al_name += " (header)"
        elif al < 8:
            names = ["RHY1", "RHY2", "BASS", "CHD1", "CHD2", "PAD", "PHR1", "PHR2"]
            al_name += f" ({names[al]} Main A)"
        elif al < 16:
            names = ["RHY1", "RHY2", "BASS", "CHD1", "CHD2", "PAD", "PHR1", "PHR2"]
            al_name += f" ({names[al-8]} Main B)"

        if not sent_list:
            print(f"\n  {al_name}: NOT SENT, received {len(recv_list)} msg(s)")
            continue
        if not recv_list:
            print(f"\n  {al_name}: sent {len(sent_list)} msg(s), NOT RECEIVED")
            continue

        # Decode both and compare payload
        def decode_bulk_msgs(msg_list):
            decoded = bytearray()
            for m in msg_list:
                payload = m[9:-2]  # Between AL and checksum+F7
                decoded.extend(decode_7bit(payload))
            return bytes(decoded)

        sent_decoded = decode_bulk_msgs(sent_list)
        recv_decoded = decode_bulk_msgs(recv_list)

        if sent_decoded == recv_decoded:
            print(f"\n  {al_name}: MATCH ({len(sent_decoded)}B)")
        else:
            # Count differences
            max_len = max(len(sent_decoded), len(recv_decoded))
            diffs = []
            for i in range(max_len):
                a = sent_decoded[i] if i < len(sent_decoded) else None
                b = recv_decoded[i] if i < len(recv_decoded) else None
                if a != b:
                    diffs.append((i, a, b))

            print(f"\n  {al_name}: {len(diffs)} differences "
                  f"(sent={len(sent_decoded)}B, recv={len(recv_decoded)}B)")
            if verbose:
                for off, a, b in diffs[:20]:
                    a_s = f"{a:02X}" if a is not None else "--"
                    b_s = f"{b:02X}" if b is not None else "--"
                    print(f"    [{off:3d}] sent={a_s} recv={b_s}")
                if len(diffs) > 20:
                    print(f"    ... +{len(diffs)-20} more")


def save_dump(received: dict, path: str):
    """Save dump results as JSON for later analysis."""
    out = {}
    for al, msg_list in received.items():
        out[f"0x{al:02X}"] = {
            "raw_msgs": [m.hex() for m in msg_list],
            "decoded": b"".join(
                decode_7bit(m[9:-2]) for m in msg_list
            ).hex()
        }
    Path(path).write_text(json.dumps(out, indent=2))
    print(f"Saved dump to {path}")


# ─── Main ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Load .syx onto QY70")
    parser.add_argument("syx_file", nargs="?", help="Path to .syx file")
    parser.add_argument("--port", default="UR22C", help="MIDI port keyword")
    parser.add_argument("--list-ports", action="store_true")
    parser.add_argument("--dump-back", action="store_true",
                        help="Dump edit buffer after loading")
    parser.add_argument("--compare", action="store_true",
                        help="Compare sent vs received")
    parser.add_argument("--save-dump", help="Save dump to JSON file")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    if args.list_ports:
        list_ports()
        return

    if not args.syx_file:
        parser.error("syx_file required (or use --list-ports)")

    # Step 1: Send .syx
    print("=== Loading SysEx onto QY70 ===")
    sent = send_syx_file(args.syx_file, args.port, verbose=True)
    if not sent:
        sys.exit(1)

    # Step 2: Dump back
    if args.dump_back:
        print(f"\nWaiting 2s for QY70 to process...")
        time.sleep(2.0)
        print("\n=== Dumping back from QY70 ===")
        received = dump_back(args.port, verbose=True)

        if not received:
            print("WARNING: No data received from dump!")
        else:
            if args.compare:
                compare_sent_vs_received(sent, received, verbose=True)

            if args.save_dump:
                save_dump(received, args.save_dump)
            else:
                # Auto-save
                stem = Path(args.syx_file).stem.replace(" ", "_")
                dump_path = f"data/qy70_bitstream_lab/{stem}_roundtrip.json"
                Path(dump_path).parent.mkdir(parents=True, exist_ok=True)
                save_dump(received, dump_path)


if __name__ == "__main__":
    main()
