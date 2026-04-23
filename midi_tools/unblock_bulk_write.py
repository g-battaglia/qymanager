#!/usr/bin/env python3
"""
Systematic unblock of PC→QY70 bulk write.

Tests combinations:
  1. XG System On reset before bulk
  2. Device number sweep (0-15)
  3. Different init sequences (Init vs Protect Off vs both)
  4. Init with Model ID variants
  5. Extended timing delays

For each test, send known_pattern bulk, then dump request AM=0x7E and
verify response differs from baseline (SGT empty-response means overwrite failed).
"""

import sys
import time
import threading
import rtmidi
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from midi_tools.send_style import parse_syx_file

KNOWN = Path(__file__).parent / "captured" / "known_pattern.syx"


def find(m, hint="porta 1"):
    for i in range(m.get_port_count()):
        if hint.lower() in m.get_port_name(i).lower():
            return i
    return 0


def send_and_capture(msg_sequence: list[bytes], capture_s: float = 3.0) -> list[bytes]:
    mo = rtmidi.MidiOut()
    mi = rtmidi.MidiIn()
    mi.ignore_types(sysex=False, timing=True, active_sense=True)
    out_idx = find(mo)
    in_idx = find(mi)

    captured = []
    stop = [False]

    def listener():
        mi.open_port(in_idx)
        while not stop[0]:
            m = mi.get_message()
            if m:
                captured.append(bytes(m[0]))
            else:
                time.sleep(0.0005)
        mi.close_port()

    t = threading.Thread(target=listener, daemon=True)
    t.start()
    time.sleep(0.2)
    captured.clear()

    mo.open_port(out_idx)
    for msg in msg_sequence:
        mo.send_message(list(msg))
        if len(msg) == 9 and msg[7] == 0x01:  # init
            time.sleep(0.5)
        elif len(msg) == 9 and msg[7] == 0x00:  # close
            time.sleep(0.1)
        else:
            time.sleep(0.15)
    mo.close_port()

    time.sleep(capture_s - 0.5)
    stop[0] = True
    t.join(timeout=1)

    return [bytes(m) for m in captured]


def dump_request(am: int = 0x7E, al: int = 0x00) -> list[bytes]:
    """Send dump request, capture response."""
    mo = rtmidi.MidiOut()
    mi = rtmidi.MidiIn()
    mi.ignore_types(sysex=False, timing=True, active_sense=True)

    captured = []
    stop = [False]

    def listener():
        mi.open_port(find(mi))
        deadline = time.time() + 4.0
        while time.time() < deadline and not stop[0]:
            m = mi.get_message()
            if m:
                captured.append(bytes(m[0]))
            else:
                time.sleep(0.001)
        mi.close_port()

    t = threading.Thread(target=listener, daemon=True)
    t.start()
    time.sleep(0.2)

    mo.open_port(find(mo))
    mo.send_message([0xF0, 0x43, 0x10, 0x5F, 0x00, 0x00, 0x00, 0x01, 0xF7])
    time.sleep(0.5)
    mo.send_message([0xF0, 0x43, 0x20, 0x5F, 0x02, am, al, 0xF7])
    time.sleep(3)
    mo.send_message([0xF0, 0x43, 0x10, 0x5F, 0x00, 0x00, 0x00, 0x00, 0xF7])
    mo.close_port()

    stop[0] = True
    t.join(timeout=1)
    return captured


def build_bulk_sequence(device_num: int = 0, prepend_xg_on: bool = False,
                       init_variant: str = "standard") -> list[bytes]:
    msgs = []
    if prepend_xg_on:
        # XG System On
        msgs.append(bytes([0xF0, 0x43, 0x10, 0x4C, 0x00, 0x00, 0x7E, 0x00, 0xF7]))
    # Init variants
    if init_variant == "standard":
        init = bytes([0xF0, 0x43, 0x10 | device_num, 0x5F, 0x00, 0x00, 0x00, 0x01, 0xF7])
    elif init_variant == "write_enable":
        init = bytes([0xF0, 0x43, 0x10 | device_num, 0x5F, 0x00, 0x00, 0x00, 0x01, 0xF7])
    msgs.append(init)

    # Bulk from known_pattern
    known = parse_syx_file(str(KNOWN))
    for m, info in known:
        if info["type"] in ("init", "close"):
            continue
        # Override device number
        m_list = list(m)
        if len(m_list) > 2:
            m_list[2] = (m_list[2] & 0xF0) | device_num
        msgs.append(bytes(m_list))

    close = bytes([0xF0, 0x43, 0x10 | device_num, 0x5F, 0x00, 0x00, 0x00, 0x00, 0xF7])
    msgs.append(close)
    return msgs


def summarize_response(msgs: list[bytes]) -> str:
    if not msgs:
        return "NO RESPONSE"
    n_xg = sum(1 for m in msgs if len(m) >= 4 and m[0] == 0xF0 and m[1] == 0x43 and m[3] == 0x4C)
    n_seq = sum(1 for m in msgs if len(m) >= 4 and m[0] == 0xF0 and m[1] == 0x43 and m[3] == 0x5F)
    n_ch = sum(1 for m in msgs if m and (m[0] & 0xF0) in (0x80, 0x90, 0xA0, 0xB0, 0xC0, 0xD0, 0xE0))
    n_bytes = sum(len(m) for m in msgs)
    return f"{len(msgs)} msgs ({n_bytes}B): XG={n_xg}, Seq5F={n_seq}, Ch={n_ch}"


def test_scenario(name: str, msg_sequence: list[bytes]) -> dict:
    print(f"\n═══ {name} ═══")
    print(f"  Sending {len(msg_sequence)} messages...")
    resp = send_and_capture(msg_sequence, capture_s=3.5)
    print(f"  Load response: {summarize_response(resp)}")
    # Verify with dump request
    time.sleep(1)
    dump = dump_request(am=0x7E, al=0x00)
    print(f"  Dump AM=7E response: {summarize_response(dump)}")
    # Also slot U01
    time.sleep(0.5)
    slot = dump_request(am=0x00, al=0x00)
    print(f"  Dump AM=00 (U01):    {summarize_response(slot)}")
    return {
        "name": name,
        "load_response_count": len(resp),
        "load_response_bytes": sum(len(m) for m in resp),
        "dump_7e_count": len(dump),
        "dump_00_count": len(slot),
    }


def main():
    results = []

    # Scenario 1: baseline standard send
    seq = build_bulk_sequence(device_num=0)
    results.append(test_scenario("Standard device=0", seq))

    # Scenario 2: XG System On first
    seq = build_bulk_sequence(device_num=0, prepend_xg_on=True)
    results.append(test_scenario("XG System On + Standard device=0", seq))

    # Scenario 3: Device 1
    seq = build_bulk_sequence(device_num=1)
    results.append(test_scenario("Standard device=1", seq))

    # Scenario 4: Device number sweep 2-15
    best_by_count = max(results, key=lambda x: x["load_response_count"])
    print(f"\nBest so far: {best_by_count['name']} ({best_by_count['load_response_count']} msgs)")

    for dev in [2, 3, 4, 5, 8, 15]:
        seq = build_bulk_sequence(device_num=dev)
        r = test_scenario(f"Device={dev}", seq)
        results.append(r)
        time.sleep(1)

    # Summary
    print(f"\n{'═' * 60}")
    print(f"  SCENARIO RESULTS")
    print(f"{'═' * 60}")
    print(f"{'Scenario':<40s} {'Load':>6s} {'Dump7E':>8s} {'Dump00':>8s}")
    for r in results:
        print(f"{r['name']:<40s} {r['load_response_count']:>6d} "
              f"{r['dump_7e_count']:>8d} {r['dump_00_count']:>8d}")


if __name__ == "__main__":
    main()
