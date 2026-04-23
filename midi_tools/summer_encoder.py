#!/usr/bin/env python3
"""
Summer-style encoder: given strike signatures + bar positions, produce
bytes approximating Summer dense-user encoding.

Approach:
  1. Load Summer GT (20 events)
  2. Per (beat, strike_signature), find template invariant bits
  3. Given desired (bar_idx, beat, strikes), emit bytes using template + bar_id bits
  4. Remaining unknown bits set to "best guess" from observed data

Test: encode all 20 Summer events, compare to original bytes.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

GT = Path(__file__).parent / "captured" / "summer_ground_truth.json"


def compute_mask(events_bytes):
    mask = 0
    for bit in range(56):
        vals = {(int.from_bytes(b, "big") >> bit) & 1 for b in events_bytes}
        if len(vals) == 1:
            mask |= (1 << bit)
    return mask


def template_value(events_bytes, mask):
    """Return the constant value on invariant bits (using first event)."""
    val = int.from_bytes(events_bytes[0], "big")
    return val & mask


def find_bar_id_bits(bar_to_bytes: dict, var_positions: list) -> dict:
    """Find min bit subset uniquely identifying each bar."""
    from itertools import combinations
    from math import ceil, log2
    bars = list(bar_to_bytes.keys())
    n_bars = len(bars)
    min_size = max(1, ceil(log2(n_bars)))
    for size in range(min_size, len(var_positions) + 1):
        for subset in combinations(var_positions, size):
            codes = {}
            for bar, bts in bar_to_bytes.items():
                val = int.from_bytes(bts, "big")
                code = tuple((val >> p) & 1 for p in subset)
                codes[bar] = code
            if len(set(codes.values())) == n_bars:
                return {"subset": list(subset), "codes": codes}
    return None


def build_templates(events):
    """Per beat + strike signature, build template."""
    # Signature: tuple of (note, sub) sorted
    groups = defaultdict(list)
    for e in events:
        if e["bar"] == 3:  # skip FILL bar for clean MAIN template
            continue
        sig = tuple(sorted((s["note"], s["subdivision_8th"]) for s in e["expected_strikes"]))
        groups[(e["beat"], sig)].append(e)

    templates = {}
    for (beat, sig), es in groups.items():
        bytes_list = [bytes(e["event_decimal"]) for e in es]
        mask = compute_mask(bytes_list)
        template_val = template_value(bytes_list, mask)
        var_positions = [p for p in range(56) if not (mask >> p) & 1]
        bar_to_bytes = {e["bar"]: bytes(e["event_decimal"]) for e in es}
        bar_id_result = find_bar_id_bits(bar_to_bytes, var_positions)

        templates[(beat, sig)] = {
            "template_value": template_val,
            "invariant_mask": mask,
            "var_positions": var_positions,
            "bar_id_info": bar_id_result,
            "instances": len(es),
            "samples": {e["bar"]: bytes(e["event_decimal"]).hex() for e in es},
        }
    return templates


def encode_event(beat: int, strikes_sig: tuple, bar: int, templates: dict,
                 remaining_bits_value: int = 0) -> bytes:
    """Encode a Summer-style event."""
    key = (beat, strikes_sig)
    if key not in templates:
        return None
    t = templates[key]
    val = t["template_value"]
    # Set bar_id bits
    if t["bar_id_info"] and bar in t["bar_id_info"]["codes"]:
        code = t["bar_id_info"]["codes"][bar]
        for i, pos in enumerate(t["bar_id_info"]["subset"]):
            if code[i]:
                val |= (1 << pos)
    # Set remaining variable bits from remaining_bits_value (bit sequence)
    non_id_positions = [p for p in t["var_positions"]
                        if p not in (t["bar_id_info"]["subset"] if t["bar_id_info"] else [])]
    for i, pos in enumerate(non_id_positions):
        if (remaining_bits_value >> i) & 1:
            val |= (1 << pos)
    return val.to_bytes(7, "big")


def test_encoder():
    gt = json.loads(GT.read_text())
    templates = build_templates(gt["events"])

    print(f"Built {len(templates)} templates (MAIN bars only, bar 3 FILL excluded)")
    for (beat, sig), t in templates.items():
        print(f"\n  Beat {beat}, sig {sig}:")
        print(f"    Template: 0x{t['template_value']:014x}")
        print(f"    Mask: 0x{t['invariant_mask']:014x} ({bin(t['invariant_mask']).count('1')}/56)")
        if t["bar_id_info"]:
            print(f"    Bar ID bits at positions {t['bar_id_info']['subset']}")
            for bar, code in t["bar_id_info"]["codes"].items():
                print(f"      bar{bar} → {''.join(str(c) for c in code)}")

    # Reconstruct each event with remaining_bits=0 and compare
    print(f"\n═══ Encoder reconstruction test (remaining_bits=0) ═══")
    matches_full = 0
    matches_bar_id = 0
    total = 0
    for e in gt["events"]:
        if e["bar"] == 3:
            continue
        sig = tuple(sorted((s["note"], s["subdivision_8th"]) for s in e["expected_strikes"]))
        encoded = encode_event(e["beat"], sig, e["bar"], templates, remaining_bits_value=0)
        if encoded is None:
            continue
        original = bytes(e["event_decimal"])
        total += 1
        if encoded == original:
            matches_full += 1
        # Check bar_ID-bit match (template + bar_id should match without remaining)
        key = (e["beat"], sig)
        mask = templates[key]["invariant_mask"]
        bar_id_info = templates[key]["bar_id_info"]
        if bar_id_info:
            check_mask = mask
            for p in bar_id_info["subset"]:
                check_mask |= (1 << p)
            enc_val = int.from_bytes(encoded, "big") & check_mask
            orig_val = int.from_bytes(original, "big") & check_mask
            if enc_val == orig_val:
                matches_bar_id += 1
        print(f"  bar{e['bar']}/beat{e['beat']}: enc={encoded.hex()}  orig={original.hex()}  "
              f"{'FULL✓' if encoded==original else 'DIFF'}")

    print(f"\nFull match (all bits):  {matches_full}/{total}")
    print(f"Template + bar_ID bits: {matches_bar_id}/{total}  (remaining bits could be anything)")


if __name__ == "__main__":
    test_encoder()
