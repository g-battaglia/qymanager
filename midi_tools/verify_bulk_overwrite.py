#!/usr/bin/env python3
"""
Test if bulk write with device=2 actually overwrites edit buffer.

Steps:
  1. Dump edit buffer BEFORE (baseline)
  2. Send P01 probe (1 kick) with device=2
  3. Dump edit buffer AFTER
  4. Compare: if differs, overwrite works
"""

import sys
import time
import threading
import rtmidi
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.formats.qy70.encoder_sparse import SparseEvent, encode_sparse_track
from qymanager.utils.yamaha_7bit import encode_7bit
from qymanager.utils.checksum import calculate_yamaha_checksum

OUT = Path(__file__).parent.parent / "data" / "overwrite_test"


def find(m, hint="porta 1"):
    for i in range(m.get_port_count()):
        if hint.lower() in m.get_port_name(i).lower():
            return i
    return 0


def dump_edit_buffer(device_num=0, timeout=6.0) -> bytes:
    mo = rtmidi.MidiOut()
    mi = rtmidi.MidiIn()
    mi.ignore_types(sysex=False, timing=True, active_sense=True)
    captured = []
    stop = [False]

    def listener():
        mi.open_port(find(mi))
        deadline = time.time() + timeout
        last = time.time()
        got = False
        while time.time() < deadline and not stop[0]:
            m = mi.get_message()
            if m:
                captured.append(bytes(m[0]))
                last = time.time()
                got = True
            elif got and (time.time() - last) > 1.5:
                break
            else:
                time.sleep(0.001)
        mi.close_port()

    t = threading.Thread(target=listener, daemon=True)
    t.start()
    time.sleep(0.3)

    mo.open_port(find(mo))
    mo.send_message([0xF0, 0x43, 0x10 | device_num, 0x5F, 0x00, 0x00, 0x00, 0x01, 0xF7])
    time.sleep(0.5)
    mo.send_message([0xF0, 0x43, 0x20 | device_num, 0x5F, 0x02, 0x7E, 0x00, 0xF7])
    time.sleep(4)
    mo.send_message([0xF0, 0x43, 0x10 | device_num, 0x5F, 0x00, 0x00, 0x00, 0x00, 0xF7])
    mo.close_port()
    stop[0] = True
    t.join(timeout=1)
    return b"".join(captured)


def build_bulk(device_num=0, ah=0x02, am=0x7E, al=0x00, raw=None):
    if raw is None or len(raw) < 128:
        raw = (raw or b"") + bytes(128 - len(raw or b""))
    raw = raw[:128]
    encoded = encode_7bit(raw)
    bh = (len(encoded) >> 7) & 0x7F
    bl = len(encoded) & 0x7F
    cs = calculate_yamaha_checksum(bytes([bh, bl, ah, am, al]) + encoded)
    return bytes([0xF0, 0x43, device_num, 0x5F, bh, bl, ah, am, al]) + encoded + bytes([cs, 0xF7])


def send_probe(device_num, probe_bytes):
    mo = rtmidi.MidiOut()
    mo.open_port(find(mo))
    init = bytes([0xF0, 0x43, 0x10 | device_num, 0x5F, 0x00, 0x00, 0x00, 0x01, 0xF7])
    close = bytes([0xF0, 0x43, 0x10 | device_num, 0x5F, 0x00, 0x00, 0x00, 0x00, 0xF7])
    mo.send_message(list(init))
    time.sleep(0.5)
    for i in range(0, len(probe_bytes), 128):
        chunk = probe_bytes[i:i + 128]
        msg = build_bulk(device_num=device_num, raw=chunk)
        mo.send_message(list(msg))
        time.sleep(0.15)
    mo.send_message(list(close))
    mo.close_port()


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    # Test with device=2 (known to accept bulk)
    device = 2

    # Step 1: baseline dump
    print(f"[1] Dump baseline edit buffer (device={device})...")
    before = dump_edit_buffer(device_num=device)
    (OUT / f"before_dev{device}.syx").write_bytes(before)
    print(f"  Received {len(before)}B")

    # Step 2: build probe P01 (1 kick on beat 1)
    print(f"\n[2] Build probe P01 (1 kick beat 1)...")
    events = [SparseEvent(note=36, velocity=127, gate=412, tick=240)]
    track_bytes = encode_sparse_track(events, bars=1)
    print(f"  Track bytes: {len(track_bytes)}")

    # Step 3: send probe with device=2
    print(f"\n[3] Send probe to edit buffer with device={device}...")
    send_probe(device, track_bytes)
    time.sleep(2)

    # Step 4: dump after
    print(f"\n[4] Dump edit buffer AFTER...")
    after = dump_edit_buffer(device_num=device)
    (OUT / f"after_dev{device}.syx").write_bytes(after)
    print(f"  Received {len(after)}B")

    # Step 5: compare
    print(f"\n═══ Comparison ═══")
    print(f"  Before: {len(before)}B")
    print(f"  After:  {len(after)}B")
    if len(before) == len(after):
        match = sum(1 for a, b in zip(before, after) if a == b)
        print(f"  Same size. Byte match: {match}/{len(before)}")
        if match == len(before):
            print(f"  → NO CHANGE (bulk write NOT accepted)")
        elif match > len(before) * 0.95:
            print(f"  → Minor change (partial accept?)")
        else:
            print(f"  → SIGNIFICANT CHANGE (bulk write WORKED!)")
    else:
        diff = abs(len(before) - len(after))
        print(f"  Size changed by {diff}B → bulk write altered edit buffer state")


if __name__ == "__main__":
    main()
