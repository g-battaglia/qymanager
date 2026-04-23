#!/usr/bin/env python3
"""Full sweep of all QY70 user pattern slots AM=0x00-0x1F."""

import sys
import time
import threading
import rtmidi
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

OUT = Path(__file__).parent.parent / "data" / "stored_slots"


def find(m, hint="porta 1"):
    for i in range(m.get_port_count()):
        if hint.lower() in m.get_port_name(i).lower():
            return i
    return 0


def dump(am: int, al: int = 0x00, ah: int = 0x02, timeout: float = 5.0) -> bytes:
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
            elif got and (time.time() - last) > 1.2:
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
    time.sleep(3.5)
    mo.send_message([0xF0, 0x43, 0x10, 0x5F, 0x00, 0x00, 0x00, 0x00, 0xF7])
    mo.close_port()

    stop[0] = True
    t.join(timeout=1)
    return b"".join(captured)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"═══ Full slot sweep AM=0x00-0x1F ═══\n")

    results = {}
    for am in range(0x00, 0x20):
        blob = dump(am=am, timeout=4.0)
        size = len(blob)
        results[am] = size
        status = "HAS DATA" if size > 50 else "empty"
        print(f"  AM=0x{am:02x} (U{am+1:02d}): {size:>6d}B  {status}")
        if size > 50:
            (OUT / f"slot_U{am+1:02d}_am{am:02x}.syx").write_bytes(blob)
        time.sleep(0.8)

    # Edit buffer too
    edit = dump(am=0x7E, timeout=5.0)
    (OUT / "edit_buffer.syx").write_bytes(edit)
    print(f"\n  AM=0x7E (edit buffer): {len(edit)}B")

    print(f"\n═══ Summary ═══")
    filled = [am for am, size in results.items() if size > 50]
    print(f"  Filled slots: {len(filled)} → {[f'U{am+1:02d}' for am in filled]}")
    total_bytes = sum(results.values()) + len(edit)
    print(f"  Total data extracted: {total_bytes}B")


if __name__ == "__main__":
    main()
