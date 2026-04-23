#!/usr/bin/env python3
"""
probe_runner.py — Differential Ground Truth Matrix probe runner.

Generates minimal-delta QY70 patterns, sends them to hardware, captures
bulk dump response, and byte-diffs against baseline.

Core workflow per probe:
  1. Build pattern spec (bars, events list)
  2. Encode via sparse encoder (R=9×(i+1))
  3. Build SysEx bulk dump messages (158B each, 147B encoded)
  4. Send to QY70 edit buffer (AM=0x7E)
  5. Read back via request_dump (AM=0x7E)
  6. Compare sent vs received byte-by-byte
  7. Save all artifacts under data/probes/{probe_id}/

KNOWN QY70 QUIRK (Session 30c): after a successful bulk send, the QY70
enters "transmitting freeze" on subsequent bulk operations. This runner
supports "one probe per power cycle" mode: runs a single probe, writes
results, exits. User power-cycles QY70, runs next probe.

Usage:
    # List probes
    python3 midi_tools/probe_runner.py list

    # Run a specific probe
    python3 midi_tools/probe_runner.py run P01

    # Dump current edit buffer without sending (sanity check)
    python3 midi_tools/probe_runner.py dump-only

    # Show last probe result
    python3 midi_tools/probe_runner.py show P01
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.utils.yamaha_7bit import encode_7bit, decode_7bit
from qymanager.utils.checksum import calculate_yamaha_checksum

PROBES_DIR = Path(__file__).parent.parent / "data" / "probes"
FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures"
TEMPLATE_SYX = FIXTURES_DIR / "NEONGROOVE.syx"  # known-good structural template

CHUNK_SIZE = 128
EMPTY_MARKER = bytes([0xBF, 0xDF, 0xEF, 0xF7, 0xFB, 0xFD, 0xFE])


# ═══════════════════════════════════════════════════════════════════
# Sparse encoder primitives (mirrors roundtrip_test.py, proven 7/7)
# ═══════════════════════════════════════════════════════════════════

def rot_left(val: int, shift: int, width: int = 56) -> int:
    shift %= width
    return ((val << shift) | (val >> (width - shift))) & ((1 << width) - 1)


def pack_9bit(val: int, idx: int, total: int = 56) -> int:
    shift = total - (idx + 1) * 9
    return 0 if shift < 0 else (val & 0x1FF) << shift


def encode_sparse_event(note: int, velocity: int, gate: int, tick: int, idx: int) -> bytes:
    """Encode one event as 7 barrel-rotated bytes. PROVEN R=9×(i+1) sparse."""
    vel_code = max(0, min(15, round((127 - velocity) / 8)))
    f0_bit8 = (vel_code >> 3) & 1
    f0_bit7 = (vel_code >> 2) & 1
    rem = vel_code & 0x3
    f0 = (f0_bit8 << 8) | (f0_bit7 << 7) | (note & 0x7F)
    beat = tick // 480
    clock = tick % 480
    f1 = (beat << 7) | ((clock >> 2) & 0x7F)
    f2 = (clock & 0x3) << 7
    f5 = gate & 0x1FF
    val = pack_9bit(f0, 0) | pack_9bit(f1, 1) | pack_9bit(f2, 2) | pack_9bit(f5, 5) | (rem & 0x3)
    stored = rot_left(val, (idx + 1) * 9)
    return stored.to_bytes(7, "big")


# ═══════════════════════════════════════════════════════════════════
# SysEx message construction
# ═══════════════════════════════════════════════════════════════════

def build_sysex_msg(device_num: int, ah: int, am: int, al: int, raw_data: bytes) -> bytes:
    """Build a 158-byte QY70 bulk dump message.
    raw_data is padded to 128B. BC = 147 = encoded length.
    Checksum covers BH BL AH AM AL + encoded.
    """
    padded = raw_data + bytes(CHUNK_SIZE - len(raw_data)) if len(raw_data) < CHUNK_SIZE else raw_data[:CHUNK_SIZE]
    encoded = encode_7bit(padded)
    assert len(encoded) == 147, f"encoded={len(encoded)}B expected 147"
    bc = 147
    bh = (bc >> 7) & 0x7F
    bl = bc & 0x7F
    cs_region = bytes([bh, bl, ah, am, al]) + encoded
    cs = calculate_yamaha_checksum(cs_region)
    msg = bytes([0xF0, 0x43, device_num, 0x5F, bh, bl, ah, am, al]) + encoded + bytes([cs, 0xF7])
    assert len(msg) == 158
    return msg


def build_init_msg(device_num: int = 0x00) -> bytes:
    return bytes([0xF0, 0x43, 0x10 | device_num, 0x5F, 0x00, 0x00, 0x00, 0x01, 0xF7])


def build_close_msg(device_num: int = 0x00) -> bytes:
    return bytes([0xF0, 0x43, 0x10 | device_num, 0x5F, 0x00, 0x00, 0x00, 0x00, 0xF7])


# ═══════════════════════════════════════════════════════════════════
# Probe specification
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ProbeEvent:
    note: int
    velocity: int
    gate: int
    tick: int  # absolute tick from pattern start
    track: str = "RHY1"  # RHY1/RHY2/BASS/CHD1/...

    def bar_index(self, ticks_per_bar: int = 1920) -> int:
        return self.tick // ticks_per_bar


@dataclass
class Probe:
    id: str
    description: str
    bars: int
    tempo: int
    events: list[ProbeEvent]
    base_probe: str | None = None  # probe to diff against
    notes: str = ""  # what delta this probe isolates

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# ═══════════════════════════════════════════════════════════════════
# Pattern builder: events → full QY70 .syx bytes
# ═══════════════════════════════════════════════════════════════════

def build_rhy1_track_bytes(events: list[ProbeEvent], bars: int) -> bytes:
    """Build RHY1 (AL=0x00, section 0) decoded bytes for a sparse pattern.

    Structure (sparse):
      preamble 4B: 25 43 60 00
      header 24B: reproduced from known_pattern.syx template
      per-bar: 13B bar header + 7B × N events + delimiter (0xDC)
    """
    # Minimal preamble + header (use known_pattern.syx's RHY1 header as template)
    # Read from fixture
    kp = load_known_pattern_rhy1_header()
    preamble_header = kp[:28]  # first 28 bytes: 4B preamble + 24B header

    # Group events by bar
    by_bar: dict[int, list[ProbeEvent]] = {}
    for e in events:
        by_bar.setdefault(e.bar_index(), []).append(e)

    # Global event index across all bars (for cumulative R=9×(i+1))
    evt_idx = 0
    body = bytearray(preamble_header)

    for bar in range(bars):
        # 13B bar header — use the standard sparse header: 1A 00 ... (from known_pattern)
        bar_header = kp[28:41]  # 13B from known_pattern
        body.extend(bar_header)
        # Per-bar events (re-index per-segment — resets at DC)
        segment_idx = 0
        for e in by_bar.get(bar, []):
            # Tick relative to bar start
            tick_in_bar = e.tick - bar * 1920
            body.extend(encode_sparse_event(e.note, e.velocity, e.gate, tick_in_bar, segment_idx))
            segment_idx += 1
        # Bar delimiter
        body.append(0xDC)

    # Pad to multiple of 128B with empty markers
    remainder = len(body) % CHUNK_SIZE
    if remainder:
        pad_len = CHUNK_SIZE - remainder
        while pad_len >= 7:
            body.extend(EMPTY_MARKER)
            pad_len -= 7
        body.extend(bytes(pad_len))
    return bytes(body)


def load_known_pattern_rhy1_header() -> bytes:
    """Load RHY1 decoded bytes from known_pattern.syx as template."""
    from qymanager.formats.qy70.sysex_parser import SysExParser
    kp_path = Path(__file__).parent / "captured" / "known_pattern.syx"
    parser = SysExParser()
    msgs = parser.parse_file(str(kp_path))
    for m in msgs:
        if m.is_style_data and m.address_low == 0:
            return m.decoded_data
    raise RuntimeError("known_pattern.syx has no RHY1 data")


def build_probe_syx(probe: Probe, device_num: int = 0x00) -> bytes:
    """Build full .syx blob for a probe: Init + RHY1 bulk + Close."""
    rhy1_bytes = build_rhy1_track_bytes(probe.events, probe.bars)
    # Split into 128B chunks, one SysEx message per chunk
    msgs = [build_init_msg(device_num)]
    for offset in range(0, len(rhy1_bytes), CHUNK_SIZE):
        chunk = rhy1_bytes[offset:offset + CHUNK_SIZE]
        msgs.append(build_sysex_msg(device_num, 0x02, 0x7E, 0x00, chunk))
    msgs.append(build_close_msg(device_num))
    return b"".join(msgs)


# ═══════════════════════════════════════════════════════════════════
# Hardware I/O
# ═══════════════════════════════════════════════════════════════════

def find_port(direction: str, hint: str = "steinberg") -> int | None:
    import rtmidi
    m = rtmidi.MidiOut() if direction == "out" else rtmidi.MidiIn()
    for i in range(m.get_port_count()):
        name = m.get_port_name(i)
        if hint.lower() in name.lower() and "porta 1" in name.lower():
            return i
    for i in range(m.get_port_count()):
        if hint.lower() in m.get_port_name(i).lower():
            return i
    return 0 if m.get_port_count() > 0 else None


def send_syx_messages(msgs: list[bytes], delay_ms: int = 150, init_delay_ms: int = 500) -> bool:
    """Send a list of SysEx messages via rtmidi."""
    import rtmidi
    mo = rtmidi.MidiOut()
    idx = find_port("out")
    if idx is None:
        print("ERROR: no MIDI out port")
        return False
    port_name = mo.get_port_name(idx)
    mo.open_port(idx)
    print(f"  Opened OUT: {port_name}")
    try:
        for i, msg in enumerate(msgs):
            mo.send_message(list(msg))
            is_init = len(msg) == 9 and msg[7] == 0x01
            is_close = len(msg) == 9 and msg[7] == 0x00
            if is_init:
                time.sleep(init_delay_ms / 1000.0)
            elif is_close:
                time.sleep(0.1)
            else:
                time.sleep(delay_ms / 1000.0)
        return True
    finally:
        mo.close_port()


def request_and_capture(ah: int = 0x02, am: int = 0x7E, al: int = 0x00, timeout: float = 8.0) -> bytes:
    """Send Init+DumpRequest+Close, capture response SysEx blob."""
    import rtmidi
    import threading

    in_idx = find_port("in")
    out_idx = find_port("out")
    if in_idx is None or out_idx is None:
        raise RuntimeError("MIDI ports not found")

    mi = rtmidi.MidiIn()
    mi.ignore_types(sysex=False, timing=True, active_sense=True)

    collected: list[bytes] = []
    stop_flag = [False]

    def listener():
        mi.open_port(in_idx)
        deadline = time.time() + timeout
        last_msg = time.time()
        got_msg = False
        while time.time() < deadline and not stop_flag[0]:
            msg = mi.get_message()
            if msg:
                data, _ = msg
                if data and data[0] == 0xF0:
                    collected.append(bytes(data))
                    last_msg = time.time()
                    got_msg = True
            else:
                if got_msg and (time.time() - last_msg) > 1.0:
                    break
                time.sleep(0.001)
        mi.close_port()

    t = threading.Thread(target=listener, daemon=True)
    t.start()
    time.sleep(0.3)

    mo = rtmidi.MidiOut()
    mo.open_port(out_idx)
    mo.send_message(list(build_init_msg()))
    time.sleep(0.5)
    mo.send_message([0xF0, 0x43, 0x20, 0x5F, ah, am, al, 0xF7])
    time.sleep(0.2)
    mo.send_message(list(build_close_msg()))
    mo.close_port()

    t.join()
    return b"".join(collected)


# ═══════════════════════════════════════════════════════════════════
# Probe definitions
# ═══════════════════════════════════════════════════════════════════

PROBES = {
    "P00_empty": Probe(
        id="P00_empty",
        description="Empty pattern (1 bar, no events) — baseline for empty-marker detection",
        bars=1, tempo=120, events=[],
        notes="baseline: no events means all bytes should be preamble+header+DC+empty markers",
    ),
    "P01_kick_b1": Probe(
        id="P01_kick_b1",
        description="1 kick on beat 1 (tick 0), vel 127, gate 240",
        bars=1, tempo=120,
        events=[ProbeEvent(note=36, velocity=127, gate=240, tick=0)],
        base_probe="P00_empty",
        notes="isolates minimum-event encoding",
    ),
    "P02_kick_b2": Probe(
        id="P02_kick_b2",
        description="1 kick on beat 2 (tick 480), vel 127, gate 240",
        bars=1, tempo=120,
        events=[ProbeEvent(note=36, velocity=127, gate=240, tick=480)],
        base_probe="P01_kick_b1",
        notes="isolates beat position encoding (F1 beat 2 bits)",
    ),
    "P03_kick_b3": Probe(
        id="P03_kick_b3",
        description="1 kick on beat 3 (tick 960)",
        bars=1, tempo=120,
        events=[ProbeEvent(note=36, velocity=127, gate=240, tick=960)],
        base_probe="P01_kick_b1",
        notes="verifies linear beat progression encoding",
    ),
    "P04_kick_b4": Probe(
        id="P04_kick_b4",
        description="1 kick on beat 4 (tick 1440)",
        bars=1, tempo=120,
        events=[ProbeEvent(note=36, velocity=127, gate=240, tick=1440)],
        base_probe="P01_kick_b1",
        notes="verifies linear beat progression encoding",
    ),
    "P05_snare_b1": Probe(
        id="P05_snare_b1",
        description="1 snare (note 38) on beat 1",
        bars=1, tempo=120,
        events=[ProbeEvent(note=38, velocity=127, gate=240, tick=0)],
        base_probe="P01_kick_b1",
        notes="isolates note number encoding (F0 lo7)",
    ),
    "P06_hh_b1": Probe(
        id="P06_hh_b1",
        description="1 HH closed (note 42) on beat 1",
        bars=1, tempo=120,
        events=[ProbeEvent(note=42, velocity=127, gate=240, tick=0)],
        base_probe="P01_kick_b1",
        notes="third note value for note encoding triangulation",
    ),
    "P07_kick_vel119": Probe(
        id="P07_kick_vel119",
        description="kick on beat 1 vel 119 (vel_code=1)",
        bars=1, tempo=120,
        events=[ProbeEvent(note=36, velocity=119, gate=240, tick=0)],
        base_probe="P01_kick_b1",
        notes="isolates velocity 127→119 (vel_code bit 2 flip)",
    ),
    "P08_kick_vel95": Probe(
        id="P08_kick_vel95",
        description="kick on beat 1 vel 95 (vel_code=4)",
        bars=1, tempo=120,
        events=[ProbeEvent(note=36, velocity=95, gate=240, tick=0)],
        base_probe="P01_kick_b1",
        notes="vel_code bit 3 isolation (F0 bit 8)",
    ),
    "P09_kick_gate120": Probe(
        id="P09_kick_gate120",
        description="kick gate=120 instead of 240",
        bars=1, tempo=120,
        events=[ProbeEvent(note=36, velocity=127, gate=120, tick=0)],
        base_probe="P01_kick_b1",
        notes="isolates gate encoding (F5 9-bit)",
    ),
    "P10_kick_2bars": Probe(
        id="P10_kick_2bars",
        description="1 kick b1 bar1 + 1 kick b1 bar2 (2-bar pattern)",
        bars=2, tempo=120,
        events=[
            ProbeEvent(note=36, velocity=127, gate=240, tick=0),
            ProbeEvent(note=36, velocity=127, gate=240, tick=1920),
        ],
        base_probe="P01_kick_b1",
        notes="isolates bar-count + multi-bar encoding",
    ),
    "P11_2events_same_bar": Probe(
        id="P11_2events_same_bar",
        description="kick b1 + snare b2 (2 events same bar)",
        bars=1, tempo=120,
        events=[
            ProbeEvent(note=36, velocity=127, gate=240, tick=0),
            ProbeEvent(note=38, velocity=127, gate=240, tick=480),
        ],
        base_probe="P01_kick_b1",
        notes="isolates event-index rotation (idx 0 vs 1)",
    ),
    "P12_dense_4events": Probe(
        id="P12_dense_4events",
        description="kick on each beat (4 events per bar, dense-ish)",
        bars=1, tempo=120,
        events=[
            ProbeEvent(note=36, velocity=127, gate=240, tick=0),
            ProbeEvent(note=36, velocity=127, gate=240, tick=480),
            ProbeEvent(note=36, velocity=127, gate=240, tick=960),
            ProbeEvent(note=36, velocity=127, gate=240, tick=1440),
        ],
        base_probe="P01_kick_b1",
        notes="4 events/bar — threshold probe for sparse vs dense trigger",
    ),
    "P13_very_dense_16events": Probe(
        id="P13_very_dense_16events",
        description="16 kicks (every 16th note) — should trigger dense if threshold exists",
        bars=1, tempo=120,
        events=[ProbeEvent(note=36, velocity=127, gate=120, tick=i * 120) for i in range(16)],
        base_probe="P12_dense_4events",
        notes="16 events/bar — likely triggers dense encoding",
    ),
}


# ═══════════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════════

def probe_dir(probe_id: str) -> Path:
    d = PROBES_DIR / probe_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_probe_artifacts(probe: Probe, sent_syx: bytes, received_syx: bytes):
    d = probe_dir(probe.id)
    (d / "spec.json").write_text(json.dumps(probe.to_dict(), indent=2, default=str))
    (d / "sent.syx").write_bytes(sent_syx)
    (d / "received.syx").write_bytes(received_syx)
    print(f"  Saved artifacts to {d}")

    # Quick diff summary
    sent_rhy1 = extract_rhy1_bytes(sent_syx)
    recv_rhy1 = extract_rhy1_bytes(received_syx)
    if sent_rhy1 is not None and recv_rhy1 is not None:
        min_len = min(len(sent_rhy1), len(recv_rhy1))
        diffs = [(i, sent_rhy1[i], recv_rhy1[i])
                 for i in range(min_len) if sent_rhy1[i] != recv_rhy1[i]]
        summary = {
            "sent_rhy1_len": len(sent_rhy1),
            "recv_rhy1_len": len(recv_rhy1),
            "byte_diffs": len(diffs),
            "byte_match_rate": 1 - len(diffs) / max(1, min_len),
            "first_20_diffs": [[i, f"{a:02x}", f"{b:02x}"] for i, a, b in diffs[:20]],
        }
        (d / "diff.json").write_text(json.dumps(summary, indent=2))
        print(f"  RHY1 bytes: sent={len(sent_rhy1)}, recv={len(recv_rhy1)}, diffs={len(diffs)}")
    else:
        print(f"  WARN: could not extract RHY1 from one side (sent={sent_rhy1 is not None}, recv={recv_rhy1 is not None})")


def extract_rhy1_bytes(syx_blob: bytes) -> bytes | None:
    """Extract decoded RHY1 (AL=0x00) bytes concatenated across messages."""
    from qymanager.formats.qy70.sysex_parser import SysExParser
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".syx", delete=False) as f:
        f.write(syx_blob)
        tmp = f.name
    try:
        parser = SysExParser()
        msgs = parser.parse_file(tmp)
        rhy1 = b""
        for m in msgs:
            if m.is_style_data and m.address_low == 0 and m.decoded_data:
                rhy1 += m.decoded_data
        return rhy1 if rhy1 else None
    finally:
        Path(tmp).unlink(missing_ok=True)


def run_probe(probe_id: str, skip_dump: bool = False) -> int:
    probe = PROBES.get(probe_id)
    if probe is None:
        print(f"ERROR: probe {probe_id} not defined")
        return 1
    print(f"═══ Running probe {probe.id} ═══")
    print(f"  Description: {probe.description}")
    print(f"  Events: {len(probe.events)}, Bars: {probe.bars}")

    # Build probe SysEx
    sent_syx = build_probe_syx(probe)
    print(f"  Built sent.syx: {len(sent_syx)} bytes")

    d = probe_dir(probe.id)
    (d / "sent.syx").write_bytes(sent_syx)
    (d / "spec.json").write_text(json.dumps(probe.to_dict(), indent=2, default=str))

    if skip_dump:
        print("  --skip-dump: not sending to hardware")
        return 0

    # Step 1: send
    print(f"  ─── Sending to QY70 edit buffer ───")
    # Parse sent_syx into individual messages
    msgs = []
    i = 0
    while i < len(sent_syx):
        if sent_syx[i] != 0xF0:
            i += 1
            continue
        j = i + 1
        while j < len(sent_syx) and sent_syx[j] != 0xF7:
            j += 1
        msgs.append(sent_syx[i:j + 1])
        i = j + 1
    print(f"  Parsed {len(msgs)} messages to send")

    ok = send_syx_messages(msgs)
    if not ok:
        print("  SEND FAILED")
        return 1

    # Step 2: wait for QY70 to settle, then dump
    print(f"  ─── Waiting 2s, then dumping ───")
    time.sleep(2)
    received_syx = request_and_capture(ah=0x02, am=0x7E, al=0x00, timeout=8.0)
    print(f"  Received {len(received_syx)} bytes")

    # Step 3: save artifacts
    save_probe_artifacts(probe, sent_syx, received_syx)
    return 0


def dump_only() -> int:
    """Just dump current edit buffer, no send."""
    print("═══ Dump current edit buffer ═══")
    received = request_and_capture(ah=0x02, am=0x7E, al=0x00, timeout=8.0)
    print(f"Received {len(received)} bytes")
    d = PROBES_DIR / "_current"
    d.mkdir(parents=True, exist_ok=True)
    out = d / f"dump_{int(time.time())}.syx"
    out.write_bytes(received)
    print(f"Saved to {out}")
    return 0


def list_probes() -> int:
    print(f"Defined probes ({len(PROBES)}):")
    for pid, p in PROBES.items():
        print(f"  {pid:30s} — {p.description}")
    return 0


def show_probe(probe_id: str) -> int:
    d = PROBES_DIR / probe_id
    if not d.exists():
        print(f"No artifacts for {probe_id}")
        return 1
    diff = d / "diff.json"
    if diff.exists():
        print(diff.read_text())
    spec = d / "spec.json"
    if spec.exists():
        print("─── spec ───")
        print(spec.read_text())
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    sub.add_parser("dump-only")
    run_p = sub.add_parser("run")
    run_p.add_argument("probe_id")
    run_p.add_argument("--skip-dump", action="store_true", help="build+save sent.syx but don't touch hardware")
    show_p = sub.add_parser("show")
    show_p.add_argument("probe_id")
    args = ap.parse_args()

    if args.cmd == "list":
        return list_probes()
    if args.cmd == "dump-only":
        return dump_only()
    if args.cmd == "run":
        return run_probe(args.probe_id, skip_dump=args.skip_dump)
    if args.cmd == "show":
        return show_probe(args.probe_id)
    return 1


if __name__ == "__main__":
    sys.exit(main())
