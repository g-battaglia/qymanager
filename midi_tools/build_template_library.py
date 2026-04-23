#!/usr/bin/env python3
"""
Build a template library from Summer ground truth.

Strategy: treat each 7-byte event as a (strike_signature → event_bytes) mapping.
Then scan SGT bitstream to find matching event bytes, infer strikes.

This is a LOOKUP-TABLE approach to dense encoding: instead of trying to
mathematically decode, we treat the encoding as opaque and build a dictionary
from observed factory events.

Output: data/template_library.json
"""

import json
from pathlib import Path
from collections import defaultdict

GT_PATH = Path(__file__).parent / "captured" / "summer_ground_truth.json"
SGT_PATH = Path(__file__).parent.parent / "tests" / "fixtures" / "QY70_SGT.syx"
OUT_PATH = Path(__file__).parent.parent / "data" / "template_library.json"


def load_summer_gt():
    return json.loads(GT_PATH.read_text())


def strike_signature(strikes: list) -> tuple:
    """Canonical signature: sorted tuple of (note, subdivision_8th) — ignores velocity."""
    return tuple(sorted((s["note"], s["subdivision_8th"]) for s in strikes))


def velocity_profile(strikes: list) -> tuple:
    """Velocity profile: sorted tuple of (note, sub, vel) — full strike detail."""
    return tuple(sorted((s["note"], s["subdivision_8th"], s["velocity"]) for s in strikes))


def build_library():
    gt = load_summer_gt()
    events = gt["events"]

    # Group by strike signature (note+sub pattern, ignoring velocity)
    by_sig = defaultdict(list)
    for e in events:
        sig = strike_signature(e["expected_strikes"])
        by_sig[sig].append({
            "bar": e["bar"],
            "beat": e["beat"],
            "event_hex": e["event_hex"],
            "event_bytes": bytes(e["event_decimal"]).hex(),
            "strikes": e["expected_strikes"],
        })

    library = {
        "source": str(GT_PATH.name),
        "total_events": len(events),
        "unique_signatures": len(by_sig),
        "templates": [],
    }

    for sig, entries in by_sig.items():
        # Find invariant byte positions / bit positions across entries
        byte_list = [bytes.fromhex(e["event_bytes"]) for e in entries]
        n = len(byte_list)
        invariant_bits_mask = 0
        for bit in range(56):
            vals = {(int.from_bytes(b, "big") >> bit) & 1 for b in byte_list}
            if len(vals) == 1:
                invariant_bits_mask |= (1 << bit)
        # Template fingerprint = the invariant value across all entries
        template_val = int.from_bytes(byte_list[0], "big") & invariant_bits_mask
        template = {
            "signature": [[n, s] for n, s in sig],
            "count": n,
            "instances": entries,
            "invariant_bits_mask": f"0x{invariant_bits_mask:014x}",
            "template_fingerprint": f"0x{template_val:014x}",
            "n_invariant_bits": bin(invariant_bits_mask).count("1"),
        }
        library["templates"].append(template)

    # Sort by count descending
    library["templates"].sort(key=lambda t: -t["count"])

    # Save
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(library, indent=2, default=str))
    print(f"Saved {len(library['templates'])} templates to {OUT_PATH}")

    # Print summary
    print(f"\n═══ Template library summary ═══")
    for t in library["templates"]:
        sig_str = ", ".join(f"n{n}@{s}" for n, s in t["signature"])
        print(f"\n  Signature: [{sig_str}]  count={t['count']}  "
              f"invariant_bits={t['n_invariant_bits']}/56")
        print(f"    Fingerprint: {t['template_fingerprint']}")
        print(f"    Mask:        {t['invariant_bits_mask']}")
        for inst in t["instances"]:
            print(f"    bar{inst['bar']}/beat{inst['beat']}: {inst['event_bytes']}")

    return library


def scan_sgt_for_templates(library):
    """Scan SGT bitstream for matches against Summer templates."""
    from qymanager.formats.qy70.sysex_parser import SysExParser

    parser = SysExParser()
    msgs = parser.parse_file(str(SGT_PATH))

    rhy1_by_section = defaultdict(bytes)
    for m in msgs:
        if m.is_style_data and m.decoded_data and m.address_low % 8 == 0:
            rhy1_by_section[m.address_low // 8] += m.decoded_data

    print(f"\n═══ Scanning SGT for template matches ═══")

    for sec, data in rhy1_by_section.items():
        print(f"\n  SGT Sec{sec} ({len(data)}B):")
        # Slide 7-byte window across data, check against each template
        matches_by_template = defaultdict(list)
        for offset in range(len(data) - 6):
            window = data[offset:offset + 7]
            window_val = int.from_bytes(window, "big")
            for t in library["templates"]:
                mask = int(t["invariant_bits_mask"], 16)
                fp = int(t["template_fingerprint"], 16)
                if (window_val & mask) == fp:
                    sig_str = ",".join(f"n{n}@{s}" for n, s in t["signature"])
                    matches_by_template[sig_str].append(offset)

        for sig, offsets in matches_by_template.items():
            print(f"    [{sig}]: {len(offsets)} matches at offsets {offsets[:10]}"
                  f"{'...' if len(offsets) > 10 else ''}")


if __name__ == "__main__":
    lib = build_library()
    scan_sgt_for_templates(lib)
