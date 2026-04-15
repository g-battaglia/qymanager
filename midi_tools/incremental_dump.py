#!/usr/bin/env python3
"""QY70 Round-Trip Bulk Dump Experiment.

Sends a .syx style to the QY70, captures the dump back from hardware,
and compares sent vs received data byte-for-byte.

Key finding: QY70 does NOT support remote Dump Request for the edit
buffer (AM=0x7E). The dump must be triggered manually on the QY70:
  UTILITY -> MIDI -> Bulk Dump -> Style

Workflow:
  1. Parse source .syx -> extract per-AL decoded blocks
  2. Send the .syx to QY70 via bulk dump (init/bulk/close)
  3. Wait for QY70 to load (expects ~160 XG parameter responses)
  4. Capture manual bulk dump (user triggers on QY70 hardware)
  5. Compare sent vs received decoded data byte-for-byte

The script also supports:
  --probe: diagnose MIDI connectivity
  --dump-only: just capture without comparison
  --save-dump: save received dump to .syx file

Uses rtmidi directly (NOT mido) -- mido drops SysEx on macOS CoreMIDI.

Usage:
    # Full round-trip (send + manual capture + compare)
    .venv/bin/python3 midi_tools/incremental_dump.py --syx tests/fixtures/QY70_SGT.syx --manual-dump

    # Skip send (style already loaded), capture manual dump
    .venv/bin/python3 midi_tools/incremental_dump.py --skip-send --manual-dump --save-dump

    # Probe MIDI connectivity
    .venv/bin/python3 midi_tools/incremental_dump.py --probe
"""

import sys
import time
import threading
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.utils.yamaha_7bit import encode_7bit, decode_7bit
from qymanager.utils.checksum import calculate_yamaha_checksum, verify_sysex_checksum


# ─── Constants ───────────────────────────────────────────────────────

KNOWN_PATTERN_PATH = Path(__file__).parent / "captured" / "known_pattern.syx"
MIDI_PORT_NAME = "Steinberg UR22C Porta 1"

STYLE_AH = 0x02
STYLE_AM = 0x7E  # Edit buffer

# Timing (from protocol RE)
INIT_DELAY_MS = 500
BULK_DELAY_MS = 150
CLOSE_DELAY_MS = 100
POST_LOAD_WAIT_S = 3.0
DUMP_TIMEOUT_S = 10


# ─── MIDI Port Helpers ───────────────────────────────────────────────

def open_ports():
    """Open MIDI in + out on Porta 1. Returns (MidiOut, MidiIn)."""
    import rtmidi

    mo = rtmidi.MidiOut()
    mi = rtmidi.MidiIn()
    mi.ignore_types(sysex=False, timing=True, active_sense=True)

    out_idx = in_idx = None
    for i in range(mo.get_port_count()):
        if mo.get_port_name(i) == MIDI_PORT_NAME:
            out_idx = i
            break
    for i in range(mi.get_port_count()):
        if mi.get_port_name(i) == MIDI_PORT_NAME:
            in_idx = i
            break

    if out_idx is None or in_idx is None:
        print(f"ERROR: Port '{MIDI_PORT_NAME}' not found")
        print(f"  Out ports: {[mo.get_port_name(i) for i in range(mo.get_port_count())]}")
        print(f"  In ports:  {[mi.get_port_name(i) for i in range(mi.get_port_count())]}")
        return None, None

    mo.open_port(out_idx)
    mi.open_port(in_idx)
    time.sleep(0.3)

    # Flush pending messages
    while mi.get_message():
        pass

    print(f"  MIDI Out: {mo.get_port_name(out_idx)}")
    print(f"  MIDI In:  {mi.get_port_name(in_idx)}")
    return mo, mi


# ─── SysEx Parsing ───────────────────────────────────────────────────

def parse_syx_file(filepath):
    """Parse .syx into list of raw SysEx messages (bytes)."""
    with open(filepath, "rb") as f:
        data = f.read()
    messages = []
    start = None
    for i, b in enumerate(data):
        if b == 0xF0:
            start = i
        elif b == 0xF7 and start is not None:
            messages.append(data[start:i + 1])
            start = None
    return messages


def classify_msg(msg):
    """Return (type, al) for a SysEx message."""
    if len(msg) < 5 or msg[1] != 0x43:
        return ("unknown", None)
    dev = msg[2]
    if (dev & 0xF0) == 0x10:
        if len(msg) >= 8 and msg[3] == 0x5F:
            if msg[4:7] == b"\x00\x00\x00":
                if msg[7] == 0x01:
                    return ("init", None)
                elif msg[7] == 0x00:
                    return ("close", None)
        return ("param", None)
    elif (dev & 0xF0) == 0x00:
        if len(msg) >= 10:
            return ("bulk", msg[8])
    return ("unknown", None)


def extract_decoded_blocks(messages):
    """From a list of SysEx messages, extract per-AL decoded data.

    Returns dict: AL -> concatenated decoded bytes.
    """
    blocks = {}
    for msg in messages:
        mtype, al = classify_msg(msg)
        if mtype != "bulk" or al is None:
            continue
        payload = msg[9:-2]  # Encoded data between address and checksum
        decoded = decode_7bit(payload)
        if al not in blocks:
            blocks[al] = b""
        blocks[al] += decoded
    return blocks


def extract_raw_messages_by_al(messages):
    """Extract per-AL lists of raw bulk messages (for re-emission)."""
    by_al = {}
    for msg in messages:
        mtype, al = classify_msg(msg)
        if mtype != "bulk" or al is None:
            continue
        if al not in by_al:
            by_al[al] = []
        by_al[al].append(msg)
    return by_al


# ─── Send ─────────────────────────────────────────────────────────────

def send_syx(mo, mi, filepath, verbose=True):
    """Send a .syx file to QY70 and wait for load responses."""
    messages = parse_syx_file(filepath)
    if verbose:
        print(f"\n  Sending {len(messages)} SysEx messages from {filepath.name}")
        print(f"  Timing: {INIT_DELAY_MS}ms init, {BULK_DELAY_MS}ms between bulk")

    for i, msg in enumerate(messages):
        mtype, al = classify_msg(msg)
        mo.send_message(list(msg))

        if mtype == "init":
            time.sleep(INIT_DELAY_MS / 1000.0)
        elif mtype == "close":
            pass
        else:
            time.sleep(BULK_DELAY_MS / 1000.0)

        if verbose:
            if mtype == "bulk":
                cs_ok = verify_sysex_checksum(msg)
                print(f"    [{i + 1:3d}/{len(messages)}] Bulk AL=0x{al:02X}"
                      f" {len(msg)}B cs={'OK' if cs_ok else 'BAD'}")
            else:
                print(f"    [{i + 1:3d}/{len(messages)}] {mtype.upper()}")

    print(f"\n  Waiting {POST_LOAD_WAIT_S}s for QY70 to process...")
    time.sleep(POST_LOAD_WAIT_S)

    # Count load responses
    load_count = 0
    sysex_count = 0
    while True:
        msg = mi.get_message()
        if msg is None:
            break
        load_count += 1
        if msg[0][0] == 0xF0:
            sysex_count += 1

    print(f"  QY70 responses: {load_count} total, {sysex_count} SysEx")
    if load_count > 10:
        print("  >>> STYLE LOADED SUCCESSFULLY <<<")
        return True
    else:
        print("  WARNING: Few responses -- style may not have loaded")
        return False


# ─── Dump Request ─────────────────────────────────────────────────────

def request_single_dump(mo, mi, ah, am, al, timeout_s=DUMP_TIMEOUT_S):
    """Send a dump request for one AL and capture response SysEx messages.

    Request format: F0 43 20 5F AH AM AL F7
    Response: multiple bulk dump messages (same format as what we send).

    Uses simple polling loop (no threads) for reliability.
    """
    # Flush input
    while mi.get_message():
        pass

    # Send dump request
    request = [0xF0, 0x43, 0x20, 0x5F, ah, am, al, 0xF7]
    mo.send_message(request)

    # Poll for response
    captured = []
    deadline = time.time() + timeout_s
    last_msg_time = time.time()

    while time.time() < deadline:
        msg = mi.get_message()
        if msg:
            captured.append(bytes(msg[0]))
            last_msg_time = time.time()

            # Check if this is a Close message (end of dump)
            data = msg[0]
            if (len(data) >= 8 and data[0] == 0xF0 and data[1] == 0x43
                    and (data[2] & 0xF0) == 0x10 and data[3] == 0x5F
                    and data[4:8] == bytes([0x00, 0x00, 0x00, 0x00])):
                break
        else:
            # If we've received messages and there's been 1.5s of silence, stop
            if captured and (time.time() - last_msg_time) > 1.5:
                break
            time.sleep(0.001)

    # Separate SysEx from other messages
    sysex_msgs = [m for m in captured if len(m) >= 2 and m[0] == 0xF0 and m[-1] == 0xF7]
    other_msgs = [m for m in captured if not (len(m) >= 2 and m[0] == 0xF0 and m[-1] == 0xF7)]

    return sysex_msgs, other_msgs


def request_full_dump(mo, mi, als=None, verbose=True):
    """Request bulk dump for multiple ALs and return per-AL decoded data.

    Default: tracks 0-7 + header 0x7F (matches a full style).

    NOTE: QY70 only responds to dump requests for stored patterns
    (AM=0x00-0x3F), NOT the edit buffer (AM=0x7E). If the pattern
    is only in the edit buffer, use capture_manual_dump() instead.
    """
    if als is None:
        als = list(range(8)) + [0x7F]

    all_sysex = []
    per_al_decoded = {}

    for al in als:
        label = f"Track {al}" if al < 0x7F else "Header"
        if verbose:
            print(f"    Requesting AL=0x{al:02X} ({label})...")

        # Try AM=0x00 (User Pattern 1) first — stored patterns
        sysex_msgs, other = request_single_dump(mo, mi, STYLE_AH, 0x00, al,
                                                 timeout_s=3)

        if verbose:
            print(f"      -> {len(sysex_msgs)} SysEx, {len(other)} other")

        if sysex_msgs:
            all_sysex.extend(sysex_msgs)
            # Decode each bulk message
            decoded = b""
            for msg in sysex_msgs:
                mtype, msg_al = classify_msg(msg)
                if mtype == "bulk":
                    payload = msg[9:-2]
                    decoded += decode_7bit(payload)
            if decoded:
                per_al_decoded[al] = decoded
                if verbose:
                    print(f"      Decoded: {len(decoded)} bytes")

        time.sleep(0.3)

    return per_al_decoded, all_sysex


def capture_manual_dump(mi, timeout_s=30, verbose=True):
    """Capture a manually-triggered bulk dump from QY70.

    The user must trigger the dump on the QY70 hardware:
      UTILITY -> MIDI -> Bulk Dump -> Style (or Current)

    This captures ALL SysEx messages until we see a Close message
    or the timeout expires.

    Returns per-AL decoded data dict and list of raw SysEx messages.
    """
    if verbose:
        print(f"    Waiting up to {timeout_s}s for manual bulk dump...")
        print(f"    >>> Trigger dump on QY70: UTILITY -> MIDI -> Bulk Dump <<<")

    # Flush
    while mi.get_message():
        pass

    captured = []
    deadline = time.time() + timeout_s
    last_msg_time = None
    got_init = False
    got_close = False

    while time.time() < deadline:
        msg = mi.get_message()
        if msg:
            data = bytes(msg[0])
            # Only collect SysEx
            if len(data) >= 2 and data[0] == 0xF0 and data[-1] == 0xF7:
                captured.append(data)
                last_msg_time = time.time()

                mtype, al = classify_msg(data)
                if mtype == "init":
                    got_init = True
                    if verbose:
                        print(f"      INIT received ({len(captured)} msgs)")
                elif mtype == "close":
                    got_close = True
                    if verbose:
                        print(f"      CLOSE received ({len(captured)} msgs)")
                    break
                elif mtype == "bulk" and verbose:
                    label = f"Track {al}" if al is not None and al < 0x7F else "Header"
                    cs_ok = verify_sysex_checksum(data)
                    print(f"      [{len(captured):3d}] Bulk AL=0x{al:02X} ({label})"
                          f" {len(data)}B cs={'OK' if cs_ok else 'BAD'}", end="\r")
        else:
            # If we got messages and there's been 3s of silence, stop
            if captured and last_msg_time and (time.time() - last_msg_time) > 3.0:
                if verbose:
                    print(f"\n      Timeout (3s silence after {len(captured)} msgs)")
                break
            time.sleep(0.001)

    if verbose:
        print()

    if not captured:
        return {}, []

    if verbose:
        print(f"    Captured {len(captured)} SysEx messages"
              f" (init={'yes' if got_init else 'no'},"
              f" close={'yes' if got_close else 'no'})")

    # Decode per-AL
    per_al_decoded = {}
    for msg in captured:
        mtype, al = classify_msg(msg)
        if mtype != "bulk" or al is None:
            continue
        payload = msg[9:-2]
        decoded = decode_7bit(payload)
        if al not in per_al_decoded:
            per_al_decoded[al] = b""
        per_al_decoded[al] += decoded

    return per_al_decoded, captured


# ─── Comparison ───────────────────────────────────────────────────────

def compare_blocks(sent, received, label=""):
    """Compare two byte sequences and print differences.

    Returns (total_bytes, matching_bytes, diff_positions).
    """
    max_len = max(len(sent), len(received))
    min_len = min(len(sent), len(received))

    diffs = []
    for i in range(min_len):
        if sent[i] != received[i]:
            diffs.append(i)

    # Count length mismatches as diffs
    if len(sent) != len(received):
        for i in range(min_len, max_len):
            diffs.append(i)

    matching = max_len - len(diffs)

    print(f"\n  {label}")
    print(f"    Sent:     {len(sent)} bytes")
    print(f"    Received: {len(received)} bytes")
    print(f"    Matching: {matching}/{max_len} ({100 * matching / max_len:.1f}%)" if max_len > 0 else "    (empty)")

    if diffs:
        print(f"    Differences: {len(diffs)} bytes")
        # Show first 20 diffs in detail
        for pos in diffs[:20]:
            s = sent[pos] if pos < len(sent) else "--"
            r = received[pos] if pos < len(received) else "--"
            s_str = f"0x{s:02X}" if isinstance(s, int) else s
            r_str = f"0x{r:02X}" if isinstance(r, int) else r
            print(f"      offset {pos:4d} (0x{pos:03X}): sent={s_str} recv={r_str}")
        if len(diffs) > 20:
            print(f"      ... ({len(diffs) - 20} more differences)")
    else:
        print(f"    >>> IDENTICAL <<<")

    return max_len, matching, diffs


def compare_hex_dump(data, offset=0, length=64, label=""):
    """Print hex dump of data for visual inspection."""
    print(f"\n  {label} (offset {offset}, {min(length, len(data) - offset)} bytes):")
    for i in range(offset, min(offset + length, len(data)), 16):
        hex_part = " ".join(f"{b:02X}" for b in data[i:i + 16])
        ascii_part = "".join(
            chr(b) if 0x20 <= b < 0x7F else "." for b in data[i:i + 16]
        )
        print(f"    {i:04X}: {hex_part:<48s} {ascii_part}")


# ─── Probe ────────────────────────────────────────────────────────────

def probe_midi():
    """Probe MIDI connectivity to diagnose QY70 communication issues."""
    import rtmidi

    print("=" * 70)
    print("  QY70 MIDI CONNECTIVITY PROBE")
    print("=" * 70)

    mo = rtmidi.MidiOut()
    mi = rtmidi.MidiIn()
    mi.ignore_types(sysex=False, timing=False, active_sense=False)

    out_idx = in_idx = None
    for i in range(mo.get_port_count()):
        if mo.get_port_name(i) == MIDI_PORT_NAME:
            out_idx = i
    for i in range(mi.get_port_count()):
        if mi.get_port_name(i) == MIDI_PORT_NAME:
            in_idx = i

    if out_idx is None or in_idx is None:
        print(f"  ERROR: Port '{MIDI_PORT_NAME}' not found")
        return 1

    mo.open_port(out_idx)
    mi.open_port(in_idx)
    time.sleep(0.3)

    # 1. Check for Active Sense (QY70 OUT -> Computer IN)
    print("\n  [1] Listening for Active Sense (QY70 -> Computer)...")
    active_sense = 0
    other = 0
    deadline = time.time() + 2
    while time.time() < deadline:
        msg = mi.get_message()
        if msg:
            if msg[0][0] == 0xFE:
                active_sense += 1
            else:
                other += 1
                print(f"      Other: {' '.join(f'{b:02X}' for b in msg[0])}")
        else:
            time.sleep(0.01)

    if active_sense > 0:
        print(f"      Active Sense: {active_sense} messages -> QY70 OUT is connected")
    else:
        print(f"      No Active Sense -> QY70 OUT may not be connected")

    # 2. Identity Request
    mi.ignore_types(sysex=False, timing=True, active_sense=True)
    while mi.get_message():
        pass

    print("\n  [2] Identity Request (broadcast)...")
    mo.send_message([0xF0, 0x7E, 0x7F, 0x06, 0x01, 0xF7])
    deadline = time.time() + 3
    got_identity = False
    while time.time() < deadline:
        msg = mi.get_message()
        if msg:
            print(f"      Response: {' '.join(f'{b:02X}' for b in msg[0])}")
            got_identity = True
            break
        time.sleep(0.01)
    if not got_identity:
        print("      No response -> QY70 IN may not be receiving, or SysEx Receive is OFF")

    # 3. Dump request for edit buffer (AM=0x7E) — known to NOT work
    while mi.get_message():
        pass
    print("\n  [3] Dump Request (AM=0x7E, edit buffer, header)...")
    mo.send_message([0xF0, 0x43, 0x20, 0x5F, 0x02, 0x7E, 0x7F, 0xF7])
    deadline = time.time() + 3
    got_dump = False
    while time.time() < deadline:
        msg = mi.get_message()
        if msg:
            print(f"      Response: {' '.join(f'{b:02X}' for b in msg[0][:20])}...")
            got_dump = True
            break
        time.sleep(0.01)
    if not got_dump:
        print("      No response (expected: edit buffer dump not supported)")

    # 3b. Dump request for stored pattern (AM=0x00) — should work if pattern exists
    while mi.get_message():
        pass
    print("\n  [3b] Dump Request (AM=0x00, User Pattern 1, header)...")
    mo.send_message([0xF0, 0x43, 0x20, 0x5F, 0x02, 0x00, 0x7F, 0xF7])
    deadline = time.time() + 5
    got_stored_dump = False
    while time.time() < deadline:
        msg = mi.get_message()
        if msg:
            data = msg[0]
            print(f"      Response: {' '.join(f'{b:02X}' for b in data[:20])}..."
                  f" ({len(data)}B)")
            got_stored_dump = True
            # Read more messages
            time.sleep(1)
            while True:
                msg2 = mi.get_message()
                if msg2 is None:
                    break
                print(f"      + {len(msg2[0])}B")
            break
        time.sleep(0.01)
    if not got_stored_dump:
        print("      No response (User Pattern 1 may be empty)")

    # 4. Try all device numbers
    if not got_identity and not got_dump:
        print("\n  [4] Trying all device numbers (0-15)...")
        for dev in range(16):
            while mi.get_message():
                pass
            mo.send_message([0xF0, 0x7E, dev, 0x06, 0x01, 0xF7])
            time.sleep(0.3)
            while True:
                msg = mi.get_message()
                if msg is None:
                    break
                print(f"      Device {dev}: {' '.join(f'{b:02X}' for b in msg[0])}")

    mo.close_port()
    mi.close_port()

    print("\n  Diagnosis:")
    if active_sense > 0 and not got_identity:
        print("    QY70 OUT -> Computer: OK (Active Sense received)")
        print("    Computer -> QY70 IN:  FAIL (no SysEx response)")
        print()
        print("    Possible causes:")
        print("    1. MIDI cable from computer to QY70 IN not connected")
        print("    2. QY70 is in a menu (exit all menus, go to main screen)")
        print("    3. QY70 UTILITY -> MIDI -> Rcv Ch is set to a specific channel")
        print("    4. QY70 MIDI Receive Switch has SysEx turned off")
        print("    5. Try: UTILITY -> MIDI -> Recv Switch -> Excl = ON")
    elif active_sense > 0 and got_identity and not got_dump and not got_stored_dump:
        print("    QY70 sees Identity Request but not Dump Request")
        print("    Edit buffer (AM=0x7E): not supported (as documented)")
        print("    Stored patterns (AM=0x00): no response (pattern may be empty)")
        print()
        print("    To do a round-trip test:")
        print("    1. Send pattern to edit buffer (script does this)")
        print("    2. Trigger manual dump: UTILITY -> MIDI -> Bulk Dump -> Style")
        print("    3. Run with: --manual-dump --skip-send")
    elif active_sense > 0 and got_identity and not got_dump and got_stored_dump:
        print("    Dump Request works for stored patterns (AM=0x00)")
        print("    Edit buffer (AM=0x7E) dump not supported (as expected)")
        print("    Use --am 00 to request from User Pattern 1")
    elif got_dump:
        print("    ALL OK - QY70 responds to dump requests")
    else:
        print("    No communication in either direction")
        print("    Check: MIDI cables, USB interface, QY70 power")

    return 0


# ─── Main ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="QY70 round-trip bulk dump experiment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Experiment: send known_pattern.syx -> request dump back -> compare.

This tells us whether the QY70 re-encodes data on load/save,
and which bytes (if any) change.

Examples:
    # Full round-trip: send + dump + compare
    .venv/bin/python3 midi_tools/incremental_dump.py

    # Skip send (style already loaded from previous run)
    .venv/bin/python3 midi_tools/incremental_dump.py --skip-send

    # Just request a dump (no comparison)
    .venv/bin/python3 midi_tools/incremental_dump.py --dump-only

    # Save received dump to file
    .venv/bin/python3 midi_tools/incremental_dump.py --save-dump
""",
    )
    parser.add_argument(
        "--skip-send", action="store_true",
        help="Skip sending (style already loaded on QY70)"
    )
    parser.add_argument(
        "--dump-only", action="store_true",
        help="Just dump current style, no comparison"
    )
    parser.add_argument(
        "--save-dump", action="store_true",
        help="Save received dump to .syx file"
    )
    parser.add_argument(
        "--syx", type=str, default=str(KNOWN_PATTERN_PATH),
        help=f"Source .syx file (default: {KNOWN_PATTERN_PATH.name})"
    )
    parser.add_argument(
        "--timeout", type=int, default=DUMP_TIMEOUT_S,
        help=f"Dump request timeout in seconds (default: {DUMP_TIMEOUT_S})"
    )
    parser.add_argument(
        "--tracks", type=str, default=None,
        help="Comma-separated AL values to request (default: 0-7,0x7F)"
    )
    parser.add_argument(
        "--probe", action="store_true",
        help="Probe MIDI connectivity before running experiment"
    )
    parser.add_argument(
        "--manual-dump", action="store_true",
        help="Capture manual bulk dump (trigger on QY70 hardware)"
    )
    parser.add_argument(
        "--am", type=lambda x: int(x, 16), default=0x00,
        help="Address Mid for dump request (hex, default: 00 = User Pattern 1)"
    )

    args = parser.parse_args()
    syx_path = Path(args.syx)

    # ── Probe mode ──
    if args.probe:
        return probe_midi()

    print("=" * 70)
    print("  QY70 ROUND-TRIP BULK DUMP EXPERIMENT")
    print("=" * 70)
    print(f"  Source:  {syx_path}")
    print(f"  Date:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Parse which ALs to request
    if args.tracks:
        als = [int(x, 0) for x in args.tracks.split(",")]
    else:
        als = None  # will default to 0-7 + 0x7F

    # ── Step 1: Parse source .syx ──
    print("── Step 1: Parse source .syx ──")
    if not syx_path.exists():
        print(f"  ERROR: File not found: {syx_path}")
        return 1

    src_messages = parse_syx_file(syx_path)
    src_decoded = extract_decoded_blocks(src_messages)
    src_by_al = extract_raw_messages_by_al(src_messages)

    print(f"  Messages: {len(src_messages)}")
    print(f"  ALs found: {sorted(f'0x{al:02X}' for al in src_decoded.keys())}")
    for al in sorted(src_decoded.keys()):
        label = f"Track {al}" if al < 0x7F else "Header"
        nbulk = len(src_by_al.get(al, []))
        print(f"    AL=0x{al:02X} ({label}): {len(src_decoded[al])} decoded bytes"
              f" ({nbulk} bulk msgs)")

    # ── Step 2: Open MIDI ports ──
    print("\n── Step 2: Open MIDI ports ──")
    mo, mi = open_ports()
    if mo is None:
        return 1

    try:
        # ── Step 3: Send to QY70 ──
        if not args.skip_send and not args.dump_only:
            print("\n── Step 3: Send to QY70 ──")
            loaded = send_syx(mo, mi, syx_path)
            if not loaded:
                print("  Style may not have loaded. Continuing anyway...")
        elif args.skip_send:
            print("\n── Step 3: SKIPPED (--skip-send) ──")
        else:
            print("\n── Step 3: SKIPPED (--dump-only) ──")

        # ── Step 4: Request dump back ──
        if args.manual_dump:
            print("\n── Step 4: Capture MANUAL bulk dump ──")
            print("  QY70 does not support Dump Request for edit buffer (AM=0x7E).")
            print("  Please trigger the dump manually on the QY70 hardware.")
            recv_decoded, recv_sysex = capture_manual_dump(
                mi, timeout_s=args.timeout, verbose=True
            )
        else:
            print("\n── Step 4: Request bulk dump from QY70 ──")
            print(f"  Using AM=0x{args.am:02X}"
                  f" ({'User Pattern ' + str(args.am + 1) if args.am < 0x40 else 'edit buffer'})")
            recv_decoded, recv_sysex = request_full_dump(
                mo, mi, als=als, verbose=True
            )

        if not recv_decoded:
            print("\n  ERROR: No data received from QY70")
            print("  Troubleshooting:")
            print("    1. QY70 only supports Dump Request for AM=0x00-0x3F (stored patterns)")
            print("    2. Edit buffer (AM=0x7E) does NOT support Dump Request")
            print("    3. Use --manual-dump to capture a manual dump from QY70 hardware")
            print("       (UTILITY -> MIDI -> Bulk Dump -> Style)")
            print("    4. Or save the edit buffer to a User Pattern slot first,")
            print("       then request with --am 00")
            return 1

        print(f"\n  Received ALs: {sorted(f'0x{al:02X}' for al in recv_decoded.keys())}")
        for al in sorted(recv_decoded.keys()):
            label = f"Track {al}" if al < 0x7F else "Header"
            print(f"    AL=0x{al:02X} ({label}): {len(recv_decoded[al])} decoded bytes")

        # ── Step 5: Save dump if requested ──
        if args.save_dump and recv_sysex:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dump_path = Path(__file__).parent / "captured" / f"roundtrip_dump_{ts}.syx"
            with open(dump_path, "wb") as f:
                for msg in recv_sysex:
                    f.write(msg)
            total = sum(len(m) for m in recv_sysex)
            print(f"\n  Saved dump: {dump_path} ({total} bytes, {len(recv_sysex)} msgs)")

        # ── Step 6: Compare ──
        if not args.dump_only:
            print("\n" + "=" * 70)
            print("  COMPARISON: SENT vs RECEIVED")
            print("=" * 70)

            total_bytes = 0
            total_match = 0
            total_diffs = 0
            compared_als = 0

            # Compare each AL that exists in both
            all_als = sorted(set(list(src_decoded.keys()) + list(recv_decoded.keys())))
            for al in all_als:
                label = f"Track {al}" if al < 0x7F else "Header"
                full_label = f"AL=0x{al:02X} ({label})"

                if al not in src_decoded:
                    print(f"\n  {full_label}: NOT IN SOURCE (only in received)")
                    continue
                if al not in recv_decoded:
                    print(f"\n  {full_label}: NOT IN RECEIVED (only in source)")
                    continue

                compared_als += 1
                nbytes, nmatch, diffs = compare_blocks(
                    src_decoded[al], recv_decoded[al], full_label
                )
                total_bytes += nbytes
                total_match += nmatch
                total_diffs += len(diffs)

                # If there are differences, show hex dumps of the region
                if diffs:
                    first_diff = diffs[0]
                    dump_start = max(0, (first_diff // 16) * 16)
                    compare_hex_dump(src_decoded[al], dump_start, 64,
                                     f"SENT {full_label}")
                    compare_hex_dump(recv_decoded[al], dump_start, 64,
                                     f"RECV {full_label}")

            # ── Summary ──
            print("\n" + "=" * 70)
            print("  SUMMARY")
            print("=" * 70)
            print(f"  ALs compared:    {compared_als}")
            print(f"  Total bytes:     {total_bytes}")
            print(f"  Matching bytes:  {total_match} ({100 * total_match / total_bytes:.1f}%)"
                  if total_bytes > 0 else "  No data")
            print(f"  Different bytes: {total_diffs}")

            if total_diffs == 0:
                print("\n  >>> PERFECT ROUND-TRIP: QY70 does NOT re-encode data <<<")
                print("  The bulk dump output is byte-for-byte identical to the input.")
            else:
                pct = 100 * total_match / total_bytes if total_bytes > 0 else 0
                print(f"\n  QY70 modified {total_diffs} bytes during load/save.")
                print(f"  Round-trip fidelity: {pct:.1f}%")
                print("  Examine differences above to understand the re-encoding.")

            # ── Bonus: Decode events from received data for RHY1 ──
            if 0 in recv_decoded:
                print("\n" + "=" * 70)
                print("  BONUS: Decode RHY1 events from received dump")
                print("=" * 70)
                decode_rhy1_events(recv_decoded[0])

    finally:
        mo.close_port()
        mi.close_port()

    return 0


def decode_rhy1_events(data):
    """Decode drum events from RHY1 track data for verification."""
    from midi_tools.roundtrip_test import decode_event_raw

    GM_DRUMS = {
        35: "Kick2", 36: "Kick1", 37: "SideStk", 38: "Snare1",
        39: "Clap", 40: "Snare2", 42: "HHclose", 44: "HHpedal",
        46: "HHopen", 49: "Crash1", 51: "Ride1", 53: "RideBell",
    }

    if len(data) < 28:
        print("  Not enough data for RHY1 preamble")
        return

    preamble = data[:28]
    event_data = data[28:]

    print(f"  Preamble (28B): {preamble[:12].hex(' ')} ...")

    # Split by delimiters (DC = bar, 9E = sub-bar)
    delim_pos = sorted(i for i, b in enumerate(event_data) if b in (0xDC, 0x9E))
    segments = []
    prev = 0
    for dp in delim_pos:
        segments.append(event_data[prev:dp])
        prev = dp + 1
    segments.append(event_data[prev:])

    total_events = 0
    for seg_idx, seg in enumerate(segments):
        if len(seg) < 20:
            continue
        header = seg[:13]
        nevts = (len(seg) - 13) // 7
        total_events += nevts

        print(f"\n  Segment {seg_idx}: {nevts} events, header={header.hex(' ')}")
        for i in range(nevts):
            evt = seg[13 + i * 7: 13 + (i + 1) * 7]
            if len(evt) != 7:
                continue
            note, vel, gate, tick, vc, f0, f1, f2, f3, f4, f5, rem = decode_event_raw(evt, i)
            name = GM_DRUMS.get(note, f"n{note}")
            print(f"    e{i}: {name:>8} n={note:3d} v={vel:3d} g={gate:3d} t={tick:4d}"
                  f"  [F3=0x{f3:03X} F4=0x{f4:03X}]")

    print(f"\n  Total events decoded: {total_events}")


if __name__ == "__main__":
    sys.exit(main())
