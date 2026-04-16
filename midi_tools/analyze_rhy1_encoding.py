#!/usr/bin/env python3
"""
Analyze RHY1 encoding from Summer ground truth.

Goal: find which bytes encode which musical properties by correlating
the 20 events' byte patterns with their ground truth drum strikes.

Tests:
    1. byte 0 pattern IDs vs strike patterns (what drum/subdivision layout)
    2. byte 0 bit 7 vs kick-on-subdivision-1 flag
    3. Can we predict the 3 strikes from the 7 bytes alone?
    4. What's shared between "same-musical-content" events at different positions?
"""

import json
from collections import defaultdict, Counter


def load_gt():
    with open("midi_tools/captured/summer_ground_truth_full.json") as f:
        return json.load(f)


def strike_signature(strikes):
    """Canonical representation: sorted tuples (subdiv, note)."""
    return tuple(sorted((s["subdivision_8th"], s["note"]) for s in strikes))


def strikes_summary(strikes):
    """Human-readable summary for a beat: K+H+H / S+H+H / H+K+H etc."""
    drum = {36: "K", 38: "S", 42: "H"}
    parts = []
    for s in sorted(strikes, key=lambda x: (x["subdivision_8th"], x["note"])):
        sub = s["subdivision_8th"]
        parts.append(f"{drum.get(s['note'], '?')}{sub}")
    return "+".join(parts)


def main():
    gt = load_gt()
    rhy1 = gt["tracks"]["RHY1"]

    print("=" * 72)
    print("RHY1 EVENT TABLE — all 20 events with bytes and expected strikes")
    print("=" * 72)

    for e in rhy1["events"]:
        b = e["event_decimal"]
        bits0 = f"{b[0]:08b}"
        kick_flag = "K1" if (b[0] & 0x80) else "  "
        sig = strikes_summary(e["expected_strikes"])
        vels = ",".join(f"{s['velocity']:3d}"
                        for s in sorted(e["expected_strikes"],
                                        key=lambda x: (x["subdivision_8th"], x["note"])))
        print(f"  bar{e['bar']} beat{e['beat']} | "
              f"{e['event_hex']} | b0={b[0]:02x}({bits0}) {kick_flag} | "
              f"b4-6={b[4]:02x} {b[5]:02x} {b[6]:02x} | "
              f"{sig:15s} | v=[{vels}]")

    print()
    print("=" * 72)
    print("GROUPING: events with same strike signature")
    print("=" * 72)

    by_sig = defaultdict(list)
    for e in rhy1["events"]:
        sig = strikes_summary(e["expected_strikes"])
        by_sig[sig].append(e)

    for sig, events in sorted(by_sig.items(), key=lambda x: -len(x[1])):
        print(f"\n--- {sig} : {len(events)} events ---")
        for e in events:
            b = e["event_decimal"]
            vels = ",".join(f"{s['velocity']:3d}"
                            for s in sorted(e["expected_strikes"],
                                            key=lambda x: (x["subdivision_8th"], x["note"])))
            print(f"   bar{e['bar']}beat{e['beat']} : {e['event_hex']} | vels=[{vels}]")

    print()
    print("=" * 72)
    print("BYTE-0 ANALYSIS: unique byte 0 values and associated patterns")
    print("=" * 72)

    b0_map = defaultdict(list)
    for e in rhy1["events"]:
        b0 = e["event_decimal"][0]
        sig = strikes_summary(e["expected_strikes"])
        b0_map[b0].append((e["bar"], e["beat"], sig, e["event_hex"]))

    for b0 in sorted(b0_map.keys()):
        entries = b0_map[b0]
        bits = f"{b0:08b}"
        print(f"\n  b0=0x{b0:02x} ({bits}): {len(entries)} events")
        for bar, beat, sig, hx in entries:
            print(f"    bar{bar}beat{beat} {sig:15s} {hx}")

    print()
    print("=" * 72)
    print("PAIRWISE COMPARISON: same signature, different bytes")
    print("=" * 72)

    for sig, events in by_sig.items():
        if len(events) < 2:
            continue
        print(f"\n--- {sig} ({len(events)} events) ---")
        # Compute pairwise byte diffs
        for i in range(len(events)):
            for j in range(i + 1, len(events)):
                a = events[i]
                b = events[j]
                ba = a["event_decimal"]
                bb = b["event_decimal"]
                diffs = [(idx, ba[idx], bb[idx]) for idx in range(7) if ba[idx] != bb[idx]]
                va = sorted(a["expected_strikes"],
                            key=lambda x: (x["subdivision_8th"], x["note"]))
                vb = sorted(b["expected_strikes"],
                            key=lambda x: (x["subdivision_8th"], x["note"]))
                va_str = ",".join(f"{s['velocity']:3d}" for s in va)
                vb_str = ",".join(f"{s['velocity']:3d}" for s in vb)
                same_vel = va_str == vb_str
                marker = "✓IDENTICAL VELS" if same_vel else ""
                print(f"   bar{a['bar']}b{a['beat']} vs bar{b['bar']}b{b['beat']}: "
                      f"diff_bytes={len(diffs)} | "
                      f"v_a=[{va_str}] v_b=[{vb_str}] {marker}")
                if len(diffs) <= 4:
                    for idx, va_b, vb_b in diffs:
                        print(f"      byte{idx}: 0x{va_b:02x} ({va_b:3d}) vs 0x{vb_b:02x} ({vb_b:3d})  "
                              f"xor=0x{va_b ^ vb_b:02x}  diff={vb_b - va_b:+d}")


if __name__ == "__main__":
    main()
