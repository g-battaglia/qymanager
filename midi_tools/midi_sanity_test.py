#!/usr/bin/env python3
"""
MIDI sanity test: send sparse-encoded pattern to QY70, capture response.

Workflow:
  1. Build known_pattern via encoder_sparse (7 drum events, 1 bar)
  2. Wrap as QY70 SysEx bulk dump (AM=0x7E edit buffer)
  3. Send Init + Bulk + Close
  4. Capture ALL MIDI response (SysEx + channel) for 3 seconds
  5. Report what came back
"""

import sys
import time
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.formats.qy70.encoder_sparse import SparseEvent, encode_sparse_track
from qymanager.utils.yamaha_7bit import encode_7bit
from qymanager.utils.checksum import calculate_yamaha_checksum


def build_bulk_msg(ah, am, al, raw_data, device=0x00):
    padded = raw_data if len(raw_data) >= 128 else raw_data + bytes(128 - len(raw_data))
    padded = padded[:128]
    encoded = encode_7bit(padded)
    bh = (len(encoded) >> 7) & 0x7F
    bl = len(encoded) & 0x7F
    cs = calculate_yamaha_checksum(bytes([bh, bl, ah, am, al]) + encoded)
    return bytes([0xF0, 0x43, device, 0x5F, bh, bl, ah, am, al]) + encoded + bytes([cs, 0xF7])


def classify(raw):
    if not raw:
        return "?"
    s = raw[0]
    if 0x80 <= s <= 0xEF:
        kind = s & 0xF0
        ch = s & 0x0F
        names = {0x80: "NoteOff", 0x90: "NoteOn", 0xA0: "PolyAT", 0xB0: "CC",
                 0xC0: "PgmChg", 0xD0: "ChanAT", 0xE0: "PitchBend"}
        body = " ".join(f"{b:02X}" for b in raw[1:])
        return f"{names.get(kind, '?')} ch{ch+1} {body}"
    if s == 0xF0 and len(raw) >= 4:
        if raw[1] == 0x43:
            cmd = raw[2]
            model = raw[3]
            if model == 0x4C and (cmd & 0xF0) == 0x10:
                if len(raw) >= 8:
                    return f"XG Param AH={raw[4]:02X} AM={raw[5]:02X} AL={raw[6]:02X} DD={raw[7]:02X}"
            if model == 0x5F:
                return f"Seq Model5F cmd=0x{cmd:02X}"
        return f"SysEx {len(raw)}B {raw[:4].hex()}"
    return f"0x{s:02X}"


def find_port(direction, hint="porta 1"):
    import rtmidi
    m = rtmidi.MidiOut() if direction == "out" else rtmidi.MidiIn()
    for i in range(m.get_port_count()):
        n = m.get_port_name(i)
        if hint.lower() in n.lower():
            return i, n
    return None, None


def main():
    import rtmidi

    # ─── Build test pattern ───
    events = [
        SparseEvent(note=36, velocity=127, gate=412, tick=240),   # Kick1
        SparseEvent(note=49, velocity=127, gate=74,  tick=240),   # Crash1
        SparseEvent(note=44, velocity=119, gate=30,  tick=240),   # HHpedal
        SparseEvent(note=44, velocity=95,  gate=30,  tick=720),
        SparseEvent(note=38, velocity=127, gate=200, tick=960),   # Snare1
        SparseEvent(note=44, velocity=95,  gate=30,  tick=960),
        SparseEvent(note=44, velocity=95,  gate=30,  tick=1440),
    ]
    track_bytes = encode_sparse_track(events, bars=1)
    print(f"✓ Sparse encoder: {len(events)} events → {len(track_bytes)}B")

    # ─── Build SysEx messages ───
    init = bytes([0xF0, 0x43, 0x10, 0x5F, 0x00, 0x00, 0x00, 0x01, 0xF7])
    close = bytes([0xF0, 0x43, 0x10, 0x5F, 0x00, 0x00, 0x00, 0x00, 0xF7])
    bulk = build_bulk_msg(0x02, 0x7E, 0x00, track_bytes)
    print(f"✓ Built SysEx: init={len(init)}B + bulk={len(bulk)}B + close={len(close)}B")

    # ─── Find ports ───
    in_idx, in_name = find_port("in")
    out_idx, out_name = find_port("out")
    if in_idx is None or out_idx is None:
        print("✗ MIDI ports not found")
        return 1
    print(f"✓ IN:  {in_name}")
    print(f"✓ OUT: {out_name}")

    # ─── Setup capture thread ───
    mi = rtmidi.MidiIn()
    mi.ignore_types(sysex=False, timing=True, active_sense=True)
    captured = []
    stop = [False]

    def listener():
        mi.open_port(in_idx)
        deadline = time.time() + 5.0
        while time.time() < deadline and not stop[0]:
            msg = mi.get_message()
            if msg:
                data, _ = msg
                if data:
                    captured.append((time.time(), bytes(data)))
            else:
                time.sleep(0.001)
        mi.close_port()

    t = threading.Thread(target=listener, daemon=True)
    t.start()
    time.sleep(0.3)

    # ─── Send ───
    mo = rtmidi.MidiOut()
    mo.open_port(out_idx)
    t0 = time.time()
    print(f"\n─── Sending at t=0.000 ───")
    mo.send_message(list(init))
    print(f"  [{time.time()-t0:5.3f}s] sent Init")
    time.sleep(0.5)
    mo.send_message(list(bulk))
    print(f"  [{time.time()-t0:5.3f}s] sent Bulk ({len(bulk)}B)")
    time.sleep(0.3)
    mo.send_message(list(close))
    print(f"  [{time.time()-t0:5.3f}s] sent Close")
    mo.close_port()

    # Wait for capture
    time.sleep(2.5)
    stop[0] = True
    t.join(timeout=1)

    # ─── Report ───
    print(f"\n─── Received {len(captured)} messages ───")
    if not captured:
        print("  (no response — QY70 may be off, disconnected, or in wrong mode)")
        return 1
    # First 30 events
    for i, (ts, data) in enumerate(captured[:30]):
        print(f"  [{i:3d}] +{ts-t0:5.3f}s  {len(data):3d}B  {classify(data)}")
    if len(captured) > 30:
        print(f"  ...+{len(captured)-30} more")

    # ─── Summary by class ───
    from collections import Counter
    tags = Counter(classify(d) for _, d in captured)
    print(f"\n─── Breakdown ───")
    for tag, n in sorted(tags.items(), key=lambda x: -x[1]):
        print(f"  {n:4d}  {tag}")

    print("\n✓ MIDI send/receive cycle WORKS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
