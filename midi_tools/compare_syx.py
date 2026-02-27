#!/usr/bin/env python3
"""
Byte-level comparison of two QY70 SysEx (.syx) files.

Parses both files into SysEx messages and compares:
- Init/Close messages byte-by-byte
- Bulk dump header structure, payload sizes, checksums
- Device number consistency
- Structural anomalies

Usage:
    python3 midi_tools/compare_syx.py tests/fixtures/QY70_SGT.syx tests/fixtures/NEONGROOVE.syx
"""

import sys
import argparse
from pathlib import Path
from typing import List, Tuple, Optional


# ─── SysEx parsing ───────────────────────────────────────────────────────────


def split_sysex_messages(data: bytes) -> List[bytes]:
    """Split raw file bytes into individual F0...F7 messages."""
    messages = []
    start = None
    for i, b in enumerate(data):
        if b == 0xF0:
            start = i
        elif b == 0xF7 and start is not None:
            messages.append(data[start : i + 1])
            start = None
    return messages


def classify_message(msg: bytes) -> str:
    """Classify a SysEx message as init, close, bulk_dump, param, or unknown."""
    if len(msg) < 6:
        return "short"
    if msg[1] != 0x43:
        return "non-yamaha"

    dev_hi = msg[2] & 0xF0
    if dev_hi == 0x10:
        # Parameter change — check for init/close pattern
        if len(msg) >= 9 and msg[3] == 0x5F:
            if msg[4:7] == b"\x00\x00\x00":
                if msg[7] == 0x01:
                    return "init"
                elif msg[7] == 0x00:
                    return "close"
        return "param"
    elif dev_hi == 0x00:
        return "bulk_dump"
    elif dev_hi == 0x20:
        return "dump_request"
    return "unknown"


def calc_yamaha_checksum(data: bytes) -> int:
    """Yamaha checksum: (128 - (sum & 0x7F)) & 0x7F."""
    return (128 - (sum(data) & 0x7F)) & 0x7F


# ─── Message detail extraction ──────────────────────────────────────────────


class MsgInfo:
    """Extracted details from one SysEx message."""

    def __init__(self, raw: bytes, index: int):
        self.raw = raw
        self.index = index
        self.msg_type = classify_message(raw)
        self.length = len(raw)

        # Common Yamaha fields
        self.manufacturer = raw[1] if len(raw) > 1 else None
        self.device_byte = raw[2] if len(raw) > 2 else None
        self.device_number = (raw[2] & 0x0F) if len(raw) > 2 else None
        self.device_hi_nibble = (raw[2] & 0xF0) if len(raw) > 2 else None
        self.model_id = raw[3] if len(raw) > 3 else None

        # Bulk-dump specific
        self.bh = self.bl = self.byte_count = None
        self.ah = self.am = self.al = None
        self.payload = None
        self.checksum_byte = None
        self.checksum_over_addr_data = None  # CS over AH AM AL + data (writer style)
        self.checksum_over_bc_addr_data = None  # CS over BH BL AH AM AL + data (parser style)
        self.header_bytes = None  # first 9 bytes

        if self.msg_type == "bulk_dump" and len(raw) >= 11:
            self.bh = raw[4]
            self.bl = raw[5]
            self.byte_count = (self.bh << 7) | self.bl
            self.ah = raw[6]
            self.am = raw[7]
            self.al = raw[8]
            self.payload = raw[9:-2]
            self.checksum_byte = raw[-2]
            self.header_bytes = raw[:9]

            # Checksum method A: over AH AM AL + payload (what the writer does)
            cs_a_data = bytes([self.ah, self.am, self.al]) + self.payload
            self.checksum_over_addr_data = calc_yamaha_checksum(cs_a_data)

            # Checksum method B: over BH BL AH AM AL + payload (what the parser verifies)
            cs_b_data = raw[4:-2]  # BH BL AH AM AL + payload
            self.checksum_over_bc_addr_data = calc_yamaha_checksum(cs_b_data)


def parse_file(filepath: str) -> Tuple[bytes, List[MsgInfo]]:
    """Read a .syx file and return raw data + parsed message list."""
    data = Path(filepath).read_bytes()
    raw_msgs = split_sysex_messages(data)
    return data, [MsgInfo(m, i) for i, m in enumerate(raw_msgs)]


# ─── Reporting helpers ───────────────────────────────────────────────────────


def hex_row(data: bytes, max_bytes: int = 32) -> str:
    """Format bytes as hex string, truncating if needed."""
    s = " ".join(f"{b:02X}" for b in data[:max_bytes])
    if len(data) > max_bytes:
        s += f" ... ({len(data)} bytes total)"
    return s


def compare_bytes(label: str, a: bytes, b: bytes):
    """Print byte-by-byte comparison of two byte sequences."""
    max_len = max(len(a), len(b))
    diffs = []
    for i in range(max_len):
        va = a[i] if i < len(a) else None
        vb = b[i] if i < len(b) else None
        if va != vb:
            diffs.append((i, va, vb))

    if not diffs:
        print(f"  {label}: IDENTICAL ({len(a)} bytes)")
        print(f"    {hex_row(a)}")
    else:
        print(f"  {label}: {len(diffs)} DIFFERENCE(S)")
        print(f"    REF : {hex_row(a)}")
        print(f"    TEST: {hex_row(b)}")
        for offset, va, vb in diffs:
            sa = f"0x{va:02X}" if va is not None else "MISSING"
            sb = f"0x{vb:02X}" if vb is not None else "MISSING"
            print(f"    [offset {offset}] REF={sa}  TEST={sb}")


# ─── Main comparison ────────────────────────────────────────────────────────


def run_comparison(ref_path: str, test_path: str):
    print("=" * 78)
    print("QY70 SysEx Byte-Level Comparison")
    print("=" * 78)
    print(f"  REF  (known-good) : {ref_path}")
    print(f"  TEST (under test) : {test_path}")
    print()

    ref_data, ref_msgs = parse_file(ref_path)
    test_data, test_msgs = parse_file(test_path)

    print(
        f"File sizes: REF={len(ref_data)} bytes, TEST={len(test_data)} bytes  "
        f"(delta={len(test_data) - len(ref_data):+d})"
    )
    print(f"Messages:   REF={len(ref_msgs)}, TEST={len(test_msgs)}")
    print()

    # ── 1. Message type counts ───────────────────────────────────────────
    print("─" * 78)
    print("1. MESSAGE TYPE BREAKDOWN")
    print("─" * 78)
    for label, msgs in [("REF", ref_msgs), ("TEST", test_msgs)]:
        counts = {}
        for m in msgs:
            counts[m.msg_type] = counts.get(m.msg_type, 0) + 1
        parts = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        print(f"  {label:4s}: {parts}")
    print()

    # ── 2. Init messages ─────────────────────────────────────────────────
    print("─" * 78)
    print("2. INIT MESSAGE COMPARISON")
    print("─" * 78)
    ref_inits = [m for m in ref_msgs if m.msg_type == "init"]
    test_inits = [m for m in test_msgs if m.msg_type == "init"]
    print(f"  Count: REF={len(ref_inits)}, TEST={len(test_inits)}")

    if ref_inits and test_inits:
        compare_bytes("Init[0]", ref_inits[0].raw, test_inits[0].raw)
    elif not ref_inits:
        print("  WARNING: REF has no init message!")
    elif not test_inits:
        print("  WARNING: TEST has no init message!")
    print()

    # ── 3. Close messages ────────────────────────────────────────────────
    print("─" * 78)
    print("3. CLOSE MESSAGE COMPARISON")
    print("─" * 78)
    ref_closes = [m for m in ref_msgs if m.msg_type == "close"]
    test_closes = [m for m in test_msgs if m.msg_type == "close"]
    print(f"  Count: REF={len(ref_closes)}, TEST={len(test_closes)}")

    if ref_closes and test_closes:
        compare_bytes("Close[0]", ref_closes[0].raw, test_closes[0].raw)
    elif not test_closes:
        print("  WARNING: TEST has no close message!")
    # Check position
    if ref_closes:
        print(f"  REF  close position: message #{ref_closes[0].index} (of {len(ref_msgs)})")
    if test_closes:
        print(f"  TEST close position: message #{test_closes[0].index} (of {len(test_msgs)})")
    print()

    # ── 4. Device number consistency ─────────────────────────────────────
    print("─" * 78)
    print("4. DEVICE NUMBER CONSISTENCY")
    print("─" * 78)
    for label, msgs in [("REF", ref_msgs), ("TEST", test_msgs)]:
        dev_nums = set()
        dev_by_type = {}
        for m in msgs:
            if m.device_number is not None:
                dev_nums.add(m.device_number)
                key = m.msg_type
                if key not in dev_by_type:
                    dev_by_type[key] = set()
                dev_by_type[key].add(m.device_number)
        consistent = len(dev_nums) <= 1
        status = "OK" if consistent else "INCONSISTENT"
        print(f"  {label:4s}: device numbers = {sorted(dev_nums)}  [{status}]")
        if not consistent:
            for mt, devs in sorted(dev_by_type.items()):
                print(f"         {mt}: {sorted(devs)}")
    print()

    # ── 5. Model ID consistency ──────────────────────────────────────────
    print("─" * 78)
    print("5. MODEL ID CHECK")
    print("─" * 78)
    for label, msgs in [("REF", ref_msgs), ("TEST", test_msgs)]:
        model_ids = set(m.model_id for m in msgs if m.model_id is not None)
        print(f"  {label:4s}: model IDs = {['0x%02X' % x for x in sorted(model_ids)]}")
    print()

    # ── 6. Bulk dump analysis ────────────────────────────────────────────
    print("─" * 78)
    print("6. BULK DUMP MESSAGE ANALYSIS")
    print("─" * 78)
    ref_bulks = [m for m in ref_msgs if m.msg_type == "bulk_dump"]
    test_bulks = [m for m in test_msgs if m.msg_type == "bulk_dump"]
    print(f"  Count: REF={len(ref_bulks)}, TEST={len(test_bulks)}")
    print()

    # ── 6a. Checksum validation ──────────────────────────────────────────
    print("  6a. CHECKSUM VALIDATION")
    print("  " + "~" * 74)
    for label, bulks in [("REF", ref_bulks), ("TEST", test_bulks)]:
        cs_a_ok = sum(1 for m in bulks if m.checksum_byte == m.checksum_over_addr_data)
        cs_a_fail = len(bulks) - cs_a_ok
        cs_b_ok = sum(1 for m in bulks if m.checksum_byte == m.checksum_over_bc_addr_data)
        cs_b_fail = len(bulks) - cs_b_ok
        print(f"  {label:4s}: Method A (AH AM AL + data):    {cs_a_ok} pass, {cs_a_fail} fail")
        print(f"  {label:4s}: Method B (BH BL AH AM AL + data): {cs_b_ok} pass, {cs_b_fail} fail")

    # Show details for checksum failures
    for label, bulks in [("REF", ref_bulks), ("TEST", test_bulks)]:
        failures_a = [m for m in bulks if m.checksum_byte != m.checksum_over_addr_data]
        failures_b = [m for m in bulks if m.checksum_byte != m.checksum_over_bc_addr_data]

        # Show which method is used
        if failures_a and not failures_b:
            print(f"\n  {label} uses Method B (BH BL included in checksum)")
        elif failures_b and not failures_a:
            print(f"\n  {label} uses Method A (only AH AM AL in checksum)")
        elif not failures_a and not failures_b:
            print(f"\n  {label}: Both methods pass (checksums happen to match both)")
        else:
            print(f"\n  {label}: NEITHER method validates all messages!")
            # Show individual failures for method B
            for m in failures_b[:5]:
                print(
                    f"    msg#{m.index} AL=0x{m.al:02X}: "
                    f"stored=0x{m.checksum_byte:02X} "
                    f"calcA=0x{m.checksum_over_addr_data:02X} "
                    f"calcB=0x{m.checksum_over_bc_addr_data:02X}"
                )
    print()

    # ── 6b. Byte count validation ────────────────────────────────────────
    print("  6b. BYTE COUNT VALIDATION")
    print("  " + "~" * 74)
    for label, bulks in [("REF", ref_bulks), ("TEST", test_bulks)]:
        bc_ok = 0
        bc_fail = 0
        bc_errors = []
        for m in bulks:
            # The declared byte count should equal the actual payload length
            # (payload = everything between address bytes and checksum)
            actual_payload_len = len(m.payload)
            if m.byte_count == actual_payload_len:
                bc_ok += 1
            else:
                bc_fail += 1
                bc_errors.append(m)

        print(f"  {label:4s}: {bc_ok} pass, {bc_fail} fail  (byte_count == payload length)")
        for m in bc_errors[:10]:
            print(
                f"    msg#{m.index} AL=0x{m.al:02X}: "
                f"declared={m.byte_count}, actual_payload={len(m.payload)}, "
                f"raw_len={m.length}"
            )
    print()

    # ── 6c. Address (AH AM AL) comparison ────────────────────────────────
    print("  6c. ADDRESS (AH, AM, AL) COMPARISON")
    print("  " + "~" * 74)

    ref_addresses = [(m.ah, m.am, m.al) for m in ref_bulks]
    test_addresses = [(m.ah, m.am, m.al) for m in test_bulks]

    ref_ahs = set(m.ah for m in ref_bulks)
    test_ahs = set(m.ah for m in test_bulks)
    ref_ams = set(m.am for m in ref_bulks)
    test_ams = set(m.am for m in test_bulks)
    ref_als = sorted(set(m.al for m in ref_bulks))
    test_als = sorted(set(m.al for m in test_bulks))

    print(f"  REF  AH values: {['0x%02X' % x for x in sorted(ref_ahs)]}")
    print(f"  TEST AH values: {['0x%02X' % x for x in sorted(test_ahs)]}")
    print(f"  REF  AM values: {['0x%02X' % x for x in sorted(ref_ams)]}")
    print(f"  TEST AM values: {['0x%02X' % x for x in sorted(test_ams)]}")
    print(f"  REF  AL values: {['0x%02X' % x for x in ref_als]}")
    print(f"  TEST AL values: {['0x%02X' % x for x in test_als]}")

    # AL values only in one file
    ref_al_set = set(ref_als)
    test_al_set = set(test_als)
    only_ref = sorted(ref_al_set - test_al_set)
    only_test = sorted(test_al_set - ref_al_set)
    if only_ref:
        print(f"  AL only in REF:  {['0x%02X' % x for x in only_ref]}")
    if only_test:
        print(f"  AL only in TEST: {['0x%02X' % x for x in only_test]}")
    print()

    # ── 6d. Payload sizes per AL address ─────────────────────────────────
    print("  6d. PAYLOAD SIZES PER AL ADDRESS")
    print("  " + "~" * 74)

    def msgs_by_al(bulks):
        by_al = {}
        for m in bulks:
            if m.al not in by_al:
                by_al[m.al] = []
            by_al[m.al].append(m)
        return by_al

    ref_by_al = msgs_by_al(ref_bulks)
    test_by_al = msgs_by_al(test_bulks)
    all_als = sorted(set(ref_by_al.keys()) | set(test_by_al.keys()))

    print(
        f"  {'AL':>6s}  {'REF msgs':>9s}  {'REF bytes':>10s}  "
        f"{'TEST msgs':>10s}  {'TEST bytes':>11s}  {'Match':>5s}"
    )
    print(f"  {'─' * 6}  {'─' * 9}  {'─' * 10}  {'─' * 10}  {'─' * 11}  {'─' * 5}")

    for al in all_als:
        r_msgs = ref_by_al.get(al, [])
        t_msgs = test_by_al.get(al, [])
        r_total = sum(len(m.payload) for m in r_msgs)
        t_total = sum(len(m.payload) for m in t_msgs)
        match = "OK" if r_total == t_total and len(r_msgs) == len(t_msgs) else "DIFF"
        print(
            f"  0x{al:02X}    {len(r_msgs):>9d}  {r_total:>10d}  "
            f"{len(t_msgs):>10d}  {t_total:>11d}  {match:>5s}"
        )

    # Total
    r_total_all = sum(len(m.payload) for m in ref_bulks)
    t_total_all = sum(len(m.payload) for m in test_bulks)
    print(
        f"  {'TOTAL':>6s}  {len(ref_bulks):>9d}  {r_total_all:>10d}  "
        f"{len(test_bulks):>10d}  {t_total_all:>11d}"
    )
    print()

    # ── 6e. Header comparison (first 9 bytes of each bulk message) ───────
    print("  6e. BULK HEADER STRUCTURE (first 9 bytes)")
    print("  " + "~" * 74)
    max_compare = min(len(ref_bulks), len(test_bulks))

    header_diffs = 0
    for i in range(max_compare):
        r = ref_bulks[i]
        t = test_bulks[i]
        if r.header_bytes != t.header_bytes:
            header_diffs += 1
            if header_diffs <= 10:
                print(f"  msg#{i}: REF  {hex_row(r.header_bytes)}")
                print(f"  msg#{i}: TEST {hex_row(t.header_bytes)}")
                # Show which bytes differ
                for j in range(min(len(r.header_bytes), len(t.header_bytes))):
                    if r.header_bytes[j] != t.header_bytes[j]:
                        labels = ["F0", "MFR", "DEV", "MDL", "BH", "BL", "AH", "AM", "AL"]
                        lbl = labels[j] if j < len(labels) else f"[{j}]"
                        print(
                            f"         ^ offset {j} ({lbl}): "
                            f"REF=0x{r.header_bytes[j]:02X} TEST=0x{t.header_bytes[j]:02X}"
                        )

    if header_diffs == 0:
        print(f"  All {max_compare} comparable bulk messages have identical headers")
    else:
        print(f"  {header_diffs} header differences found (showed first {min(header_diffs, 10)})")
    print()

    # ── 7. Full message sequence comparison ──────────────────────────────
    print("─" * 78)
    print("7. FULL MESSAGE SEQUENCE")
    print("─" * 78)
    max_show = max(len(ref_msgs), len(test_msgs))
    print(
        f"  {'#':>4s}  {'REF type':>10s} {'REF len':>8s}  "
        f"{'TEST type':>10s} {'TEST len':>8s}  {'Match':>5s}"
    )
    print(f"  {'─' * 4}  {'─' * 10} {'─' * 8}  {'─' * 10} {'─' * 8}  {'─' * 5}")

    seq_diffs = 0
    for i in range(max_show):
        r_type = ref_msgs[i].msg_type if i < len(ref_msgs) else "-"
        r_len = str(ref_msgs[i].length) if i < len(ref_msgs) else "-"
        t_type = test_msgs[i].msg_type if i < len(test_msgs) else "-"
        t_len = str(test_msgs[i].length) if i < len(test_msgs) else "-"
        match = "OK" if r_type == t_type and r_len == t_len else "DIFF"
        if match == "DIFF":
            seq_diffs += 1

        # Show details for bulk dumps
        r_al = ""
        t_al = ""
        if i < len(ref_msgs) and ref_msgs[i].msg_type == "bulk_dump" and ref_msgs[i].al is not None:
            r_al = f" AL=0x{ref_msgs[i].al:02X}"
        if (
            i < len(test_msgs)
            and test_msgs[i].msg_type == "bulk_dump"
            and test_msgs[i].al is not None
        ):
            t_al = f" AL=0x{test_msgs[i].al:02X}"

        # Only print lines with differences, or first/last few, or init/close
        is_interesting = (
            match == "DIFF"
            or r_type in ("init", "close")
            or t_type in ("init", "close")
            or i < 3
            or i >= max_show - 3
        )

        if is_interesting:
            print(
                f"  {i:4d}  {r_type:>10s} {r_len:>8s}{r_al}  "
                f"{t_type:>10s} {t_len:>8s}{t_al}  {match:>5s}"
            )
        elif i == 3 and max_show > 10:
            print(f"  ...   (showing only diffs, init, close, first 3, last 3)")

    print(f"\n  Sequence differences: {seq_diffs}")
    print()

    # ── 8. Checksum deep-dive for TEST file ──────────────────────────────
    print("─" * 78)
    print("8. CHECKSUM DEEP-DIVE (first 5 bulk messages per file)")
    print("─" * 78)

    for label, bulks in [("REF", ref_bulks), ("TEST", test_bulks)]:
        print(f"\n  {label}:")
        for m in bulks[:5]:
            cs_a_match = "✓" if m.checksum_byte == m.checksum_over_addr_data else "✗"
            cs_b_match = "✓" if m.checksum_byte == m.checksum_over_bc_addr_data else "✗"
            print(
                f"    msg#{m.index:3d} AL=0x{m.al:02X}  "
                f"BH=0x{m.bh:02X} BL=0x{m.bl:02X} byte_count={m.byte_count:4d}  "
                f"payload={len(m.payload):4d}B  "
                f"stored_CS=0x{m.checksum_byte:02X}  "
                f"calcA=0x{m.checksum_over_addr_data:02X}{cs_a_match}  "
                f"calcB=0x{m.checksum_over_bc_addr_data:02X}{cs_b_match}"
            )
    print()

    # ── 9. Summary of anomalies ──────────────────────────────────────────
    print("=" * 78)
    print("9. ANOMALY SUMMARY")
    print("=" * 78)

    anomalies = []

    # Check init/close presence
    if not test_inits:
        anomalies.append("CRITICAL: TEST file has no init message")
    if not test_closes:
        anomalies.append("CRITICAL: TEST file has no close message")

    # Check init/close match
    if ref_inits and test_inits and ref_inits[0].raw != test_inits[0].raw:
        anomalies.append(f"WARNING: Init messages differ")
    if ref_closes and test_closes and ref_closes[0].raw != test_closes[0].raw:
        anomalies.append(f"WARNING: Close messages differ")

    # Check close is last message
    if test_closes:
        if test_closes[-1].index != len(test_msgs) - 1:
            anomalies.append(
                f"WARNING: Close message is not the last message in TEST "
                f"(at #{test_closes[-1].index}, total {len(test_msgs)})"
            )

    # Device number consistency
    test_devs = set(m.device_number for m in test_msgs if m.device_number is not None)
    if len(test_devs) > 1:
        anomalies.append(f"CRITICAL: TEST has inconsistent device numbers: {sorted(test_devs)}")

    # Checksum method mismatch
    test_cs_a_fail = sum(1 for m in test_bulks if m.checksum_byte != m.checksum_over_addr_data)
    test_cs_b_fail = sum(1 for m in test_bulks if m.checksum_byte != m.checksum_over_bc_addr_data)
    ref_cs_a_fail = sum(1 for m in ref_bulks if m.checksum_byte != m.checksum_over_addr_data)
    ref_cs_b_fail = sum(1 for m in ref_bulks if m.checksum_byte != m.checksum_over_bc_addr_data)

    if ref_cs_b_fail == 0 and test_cs_b_fail > 0:
        anomalies.append(
            f"CRITICAL: TEST has {test_cs_b_fail} checksum failures "
            f"(Method B: BH BL AH AM AL + data) — REF has 0 failures with same method"
        )
    if ref_cs_a_fail > 0 and test_cs_a_fail == 0:
        anomalies.append(
            f"INFO: REF uses Method B checksums (BH BL included), "
            f"but TEST uses Method A (only AH AM AL) — MISMATCH vs reference!"
        )
    if test_cs_a_fail == 0 and test_cs_b_fail > 0:
        anomalies.append(
            f"BUG: TEST checksums are computed with Method A (AH AM AL + data only), "
            f"but the QY70 expects Method B (BH BL AH AM AL + data). "
            f"The writer is NOT including BH BL in the checksum calculation!"
        )

    # Byte count vs payload
    test_bc_fail = sum(1 for m in test_bulks if m.byte_count != len(m.payload))
    if test_bc_fail > 0:
        anomalies.append(f"WARNING: TEST has {test_bc_fail} byte count mismatches")

    # Message count difference
    if len(ref_msgs) != len(test_msgs):
        anomalies.append(f"INFO: Message count differs: REF={len(ref_msgs)}, TEST={len(test_msgs)}")

    # File size difference
    if len(ref_data) != len(test_data):
        anomalies.append(f"INFO: File size differs: REF={len(ref_data)}, TEST={len(test_data)}")

    if not anomalies:
        print("  No anomalies detected.")
    else:
        for a in anomalies:
            print(f"  * {a}")

    print()
    print("=" * 78)
    print("END OF COMPARISON")
    print("=" * 78)


def main():
    parser = argparse.ArgumentParser(
        description="Byte-level comparison of two QY70 SysEx files",
    )
    parser.add_argument("ref", help="Reference (known-good) .syx file")
    parser.add_argument("test", help="Test (under investigation) .syx file")
    args = parser.parse_args()

    for p in [args.ref, args.test]:
        if not Path(p).exists():
            print(f"ERROR: File not found: {p}")
            sys.exit(1)

    run_comparison(args.ref, args.test)


if __name__ == "__main__":
    main()
