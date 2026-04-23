#!/usr/bin/env python3
"""
Extract stored SGT from QY70 slots.

Discovery: slot AM=0x00 responds with 7742B pattern data.
Also AM=0x7E edit buffer responds.

Dump both, save, analyze vs QY70_SGT.syx file.
"""

import json
import sys
import time
import threading
import rtmidi
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

OUT = Path(__file__).parent.parent / "data" / "sgt_rounds" / "stored_extract"


def find(m, hint="porta 1"):
    for i in range(m.get_port_count()):
        if hint.lower() in m.get_port_name(i).lower():
            return i
    return 0


def dump(am: int, al: int = 0x00, ah: int = 0x02, timeout: float = 6.0) -> bytes:
    mo = rtmidi.MidiOut()
    mi = rtmidi.MidiIn()
    mi.ignore_types(sysex=False, timing=True, active_sense=True)
    captured = []
    stop = [False]

    def listener():
        mi.open_port(find(mi))
        deadline = time.time() + timeout
        last_msg = time.time()
        got = False
        while time.time() < deadline and not stop[0]:
            m = mi.get_message()
            if m:
                captured.append(bytes(m[0]))
                last_msg = time.time()
                got = True
            elif got and (time.time() - last_msg) > 1.5:
                break
            else:
                time.sleep(0.001)
        mi.close_port()

    t = threading.Thread(target=listener, daemon=True)
    t.start()
    time.sleep(0.3)

    mo.open_port(find(mo))
    mo.send_message([0xF0, 0x43, 0x10, 0x5F, 0x00, 0x00, 0x00, 0x01, 0xF7])
    time.sleep(0.5)
    mo.send_message([0xF0, 0x43, 0x20, 0x5F, ah, am, al, 0xF7])
    # Give time to collect
    time.sleep(4)
    mo.send_message([0xF0, 0x43, 0x10, 0x5F, 0x00, 0x00, 0x00, 0x00, 0xF7])
    mo.close_port()

    stop[0] = True
    t.join(timeout=1)
    return b"".join(captured)


def save(blob: bytes, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob)


def main():
    print("═══ Extract stored SGT from QY70 ═══")

    # 1. Dump slot U01 (AM=0x00)
    print("\n[1] Dumping slot U01 (AM=0x00)...")
    slot_u01 = dump(am=0x00, al=0x00)
    print(f"  Received {len(slot_u01)}B")
    save(slot_u01, OUT / "slot_U01.syx")

    # 2. Dump edit buffer (AM=0x7E)
    print("\n[2] Dumping edit buffer (AM=0x7E)...")
    edit_buf = dump(am=0x7E, al=0x00)
    print(f"  Received {len(edit_buf)}B")
    save(edit_buf, OUT / "edit_buffer.syx")

    # 3. Dump all user pattern slots
    print("\n[3] Sweep AM=0x01-0x07 slots...")
    for am in range(0x01, 0x08):
        d = dump(am=am, al=0x00, timeout=3.0)
        size = len(d)
        if size > 50:
            print(f"  AM=0x{am:02x}: {size}B  <-- HAS DATA")
            save(d, OUT / f"slot_U{am+1:02d}.syx")
        else:
            print(f"  AM=0x{am:02x}: {size}B (empty)")
        time.sleep(0.5)

    # 4. Compare slot vs edit buffer sizes
    print(f"\n═══ Summary ═══")
    print(f"  Slot U01:    {len(slot_u01):>6d}B")
    print(f"  Edit buffer: {len(edit_buf):>6d}B")

    if len(slot_u01) == len(edit_buf):
        match = sum(1 for a, b in zip(slot_u01, edit_buf) if a == b)
        print(f"  Byte match (identical length): {match}/{len(slot_u01)}")
    else:
        print(f"  Sizes differ → slot vs edit differ")

    # 5. Compare with QY70_SGT.syx file
    sgt_file = Path(__file__).parent.parent / "tests" / "fixtures" / "QY70_SGT.syx"
    if sgt_file.exists():
        sgt_bytes = sgt_file.read_bytes()
        print(f"\n  QY70_SGT.syx file: {len(sgt_bytes)}B")
        if len(slot_u01) == len(sgt_bytes):
            match = sum(1 for a, b in zip(slot_u01, sgt_bytes) if a == b)
            print(f"  Slot U01 vs SGT file: {match}/{len(sgt_bytes)} byte match")
        elif len(slot_u01) > 100 and len(sgt_bytes) > 100:
            # Different sizes — compare first 500B
            match = sum(1 for a, b in zip(slot_u01[:500], sgt_bytes[:500]) if a == b)
            print(f"  First 500B match: {match}/500 (sizes differ: slot={len(slot_u01)}, file={len(sgt_bytes)})")


if __name__ == "__main__":
    main()
