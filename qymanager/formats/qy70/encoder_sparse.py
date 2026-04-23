"""
Sparse encoder for QY70 pattern bitstream.

Implements the PROVEN R=9×(i+1) cumulative barrel rotation encoding for
sparse user patterns. This is NOT suitable for dense factory styles
(see wiki/dense-encoding-spec.md for the three encoding regimes).

Usage:
    from qymanager.formats.qy70.encoder_sparse import encode_sparse_track

    events = [
        SparseEvent(note=36, velocity=127, gate=240, tick=0),
        SparseEvent(note=38, velocity=127, gate=240, tick=960),
    ]
    track_bytes = encode_sparse_track(events, bars=1)

Output format per track (matches known_pattern.syx):
    - 24 B track header (from template)
    - 4 B preamble `25 43 60 00`
    - For each bar:
        - 13 B bar header (from template)
        - N × 7 B barrel-rotated events (cumulative R=9×(i+1), per-segment index)
        - 1 B bar delimiter `0xDC`
    - Zero padding to multiple of 128 B

Reference: wiki/2543-encoding.md, midi_tools/roundtrip_test.py
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


# ═══════════════════════════════════════════════════════════════════
# Rotation primitives (56-bit barrel)
# ═══════════════════════════════════════════════════════════════════

def rot_left(val: int, shift: int, width: int = 56) -> int:
    """Left barrel rotation on a 56-bit value."""
    shift %= width
    return ((val << shift) | (val >> (width - shift))) & ((1 << width) - 1)


def rot_right(val: int, shift: int, width: int = 56) -> int:
    """Right barrel rotation on a 56-bit value (inverse of rot_left)."""
    shift %= width
    return ((val >> shift) | (val << (width - shift))) & ((1 << width) - 1)


def pack_9bit(val: int, idx: int, total: int = 56) -> int:
    """Pack a 9-bit field at position idx in a 56-bit value.
    Position 0 = MSB (bits 55-47), 1 = bits 46-38, ..., 5 = bits 10-2.
    """
    shift = total - (idx + 1) * 9
    return 0 if shift < 0 else (val & 0x1FF) << shift


def extract_9bit(val: int, idx: int, total: int = 56) -> int:
    """Extract a 9-bit field at position idx."""
    shift = total - (idx + 1) * 9
    return (val >> shift) & 0x1FF if shift >= 0 else -1


# ═══════════════════════════════════════════════════════════════════
# Event encoding
# ═══════════════════════════════════════════════════════════════════

@dataclass
class SparseEvent:
    """A single sparse pattern event."""
    note: int       # MIDI note 0-127
    velocity: int   # MIDI velocity 1-127
    gate: int       # Gate time in ticks
    tick: int       # Absolute tick within pattern (0 = start of bar 0)

    def bar_index(self, ticks_per_bar: int = 1920) -> int:
        """Which bar this event belongs to (0-indexed)."""
        return self.tick // ticks_per_bar

    def tick_in_bar(self, ticks_per_bar: int = 1920) -> int:
        """Tick offset within its bar."""
        return self.tick % ticks_per_bar


def encode_event(event: SparseEvent, segment_idx: int) -> bytes:
    """Encode one event as 7 barrel-rotated bytes.

    Uses PROVEN R=9×(i+1) cumulative rotation (Session 14 ground truth).
    segment_idx is the event's position within its bar (resets at each DC delimiter).

    Field layout (after derotation):
        [F0:9][F1:9][F2:9][F3:9][F4:9][F5:9][rem:2]
        F0 = [bit8][bit7][note_7bit]
        F1 = [beat_2bit][clock_hi_7bit]
        F2 = [clock_lo_2bit][pad_7bit]
        F3 = 0 (unused)
        F4 = 0 (unused)
        F5 = gate (9-bit)
        rem = velocity low 2 bits

    Velocity encoding: 4-bit inverted code [F0_bit8][F0_bit7][rem_bit1][rem_bit0]
        vel_code = round((127 - velocity) / 8)
        midi_vel = max(1, 127 - vel_code * 8)
    """
    vel_code = max(0, min(15, round((127 - event.velocity) / 8)))
    f0_bit8 = (vel_code >> 3) & 1
    f0_bit7 = (vel_code >> 2) & 1
    rem = vel_code & 0x3
    f0 = (f0_bit8 << 8) | (f0_bit7 << 7) | (event.note & 0x7F)

    tick_in_bar = event.tick_in_bar()
    beat = tick_in_bar // 480
    clock = tick_in_bar % 480  # 0-479, 9-bit max 511
    f1 = (beat << 7) | ((clock >> 2) & 0x7F)
    f2 = (clock & 0x3) << 7
    f3 = 0
    f4 = 0
    f5 = event.gate & 0x1FF

    val = (
        pack_9bit(f0, 0) |
        pack_9bit(f1, 1) |
        pack_9bit(f2, 2) |
        pack_9bit(f3, 3) |
        pack_9bit(f4, 4) |
        pack_9bit(f5, 5) |
        (rem & 0x3)
    )
    stored = rot_left(val, (segment_idx + 1) * 9)
    return stored.to_bytes(7, "big")


def decode_event(event_bytes: bytes, segment_idx: int) -> dict:
    """Decode 7-byte event back to its components (for validation)."""
    val = int.from_bytes(event_bytes, "big")
    r = (9 * (segment_idx + 1)) % 56
    derot = rot_right(val, r)
    f0 = extract_9bit(derot, 0)
    f1 = extract_9bit(derot, 1)
    f2 = extract_9bit(derot, 2)
    f5 = extract_9bit(derot, 5)
    rem = derot & 0x3
    note = f0 & 0x7F
    bit7 = (f0 >> 7) & 1
    bit8 = (f0 >> 8) & 1
    vel_code = (bit8 << 3) | (bit7 << 2) | rem
    midi_vel = max(1, 127 - vel_code * 8)
    beat = f1 >> 7
    clock = ((f1 & 0x7F) << 2) | (f2 >> 7)
    return {
        "note": note,
        "velocity": midi_vel,
        "gate": f5,
        "tick_in_bar": beat * 480 + clock,
        "beat": beat,
    }


# ═══════════════════════════════════════════════════════════════════
# Track encoding
# ═══════════════════════════════════════════════════════════════════

# Template bytes for track header + preamble + bar header.
# Extracted from known_pattern.syx (proven sparse 7/7).
# These must be loaded at runtime to avoid hardcoding.

_TEMPLATE_CACHE: Optional[dict] = None


def _load_template() -> dict:
    """Load the template track header + bar header from known_pattern.syx."""
    global _TEMPLATE_CACHE
    if _TEMPLATE_CACHE is not None:
        return _TEMPLATE_CACHE

    # Find known_pattern.syx (relative to repo root)
    candidates = [
        Path(__file__).parent.parent.parent.parent / "midi_tools" / "captured" / "known_pattern.syx",
        Path.cwd() / "midi_tools" / "captured" / "known_pattern.syx",
    ]
    kp_path = None
    for c in candidates:
        if c.exists():
            kp_path = c
            break
    if kp_path is None:
        raise FileNotFoundError("known_pattern.syx not found for template load")

    from qymanager.formats.qy70.sysex_parser import SysExParser
    parser = SysExParser()
    msgs = parser.parse_file(str(kp_path))
    for m in msgs:
        if m.is_style_data and m.address_low == 0 and m.decoded_data:
            d = m.decoded_data
            _TEMPLATE_CACHE = {
                "track_header": d[:24],   # 24B track metadata
                "preamble": d[24:28],     # 4B preamble 25 43 60 00
                "bar_header": d[28:41],   # 13B bar header
                "full_header": d[:28],    # convenience
            }
            return _TEMPLATE_CACHE
    raise RuntimeError("known_pattern.syx has no RHY1 AL=0x00 data")


def encode_sparse_track(events: List[SparseEvent], bars: int,
                        ticks_per_bar: int = 1920) -> bytes:
    """Encode a sparse track (events + bar structure) into raw decoded bytes.

    Output structure:
        track_header (24B) + preamble (4B) + per-bar sequence + zero padding

    Per-bar sequence:
        bar_header (13B) + N × 7B events (R=9×(i+1)) + 1B delimiter 0xDC

    Args:
        events: list of SparseEvent, sorted by tick (NOT required — auto-sorted).
        bars: total number of bars in the pattern.
        ticks_per_bar: 480 × time_sig_num, default 1920 (4/4).

    Returns:
        Raw decoded bytes (NOT 7-bit encoded). The caller must 7-bit-encode
        and wrap in SysEx bulk dump messages via writer.
    """
    template = _load_template()
    out = bytearray(template["full_header"])  # 28B

    # Group events by bar
    by_bar: dict[int, list[SparseEvent]] = {b: [] for b in range(bars)}
    for e in sorted(events, key=lambda x: x.tick):
        bar = e.bar_index(ticks_per_bar)
        if 0 <= bar < bars:
            by_bar[bar].append(e)

    # Emit per-bar
    for bar in range(bars):
        out.extend(template["bar_header"])  # 13B
        for seg_idx, evt in enumerate(by_bar[bar]):
            out.extend(encode_event(evt, seg_idx))
        out.append(0xDC)  # bar delimiter

    # Pad to multiple of 128B (bulk message size)
    chunk_size = 128
    remainder = len(out) % chunk_size
    if remainder:
        out.extend(bytes(chunk_size - remainder))
    return bytes(out)


def decode_sparse_track(
    track_data: bytes,
    *,
    header_skip: int = 41,
    event_size: int = 7,
    min_note: int = 12,
    max_note: int = 108,
    max_events: int = 128,
) -> list[dict]:
    """Decode a user-sparse QY70 track into note events via R=9×(i+1).

    Proven 7/7 on `known_pattern.syx` (Session 14) and producing ≥80 %
    musically plausible notes on real user patterns like `MR. Vain` and
    `Summer`. Factory dense styles (SGT / STYLE2 / AMB01) are known to
    fail — see `wiki/decoder-status.md` Session 19/20. Callers should
    gate usage on the *plausibility ratio* this function returns
    implicitly via the `"ctrl"` flag and note range.

    Layout assumed:
        [0..23]  track header (24 B)
        [24..27] preamble (4 B, e.g. 25 43 60 00 for RHY1 drum)
        [28..40] bar header (13 B) — drives chord transposition, not used here
        [41..]   repeated 7-byte events, segment_idx increments until the
                 note falls outside [min_note, max_note] OR bytes are all zero

    Segment index resets per bar in the general case; for one-bar user
    patterns the index runs continuously, which is what this function
    implements. Multi-bar user patterns may need a `0xDC` split — the
    encoder generates `0xDC` delimiters, but the QY70 edit-buffer bulk
    often omits them. We therefore run one long cumulative sequence
    until we hit a clear end-marker (all-zero chunk or out-of-range
    note).
    """
    events: list[dict] = []
    off = header_skip
    seg_idx = 0
    consecutive_ctrl = 0
    while seg_idx < max_events and off + event_size <= len(track_data):
        chunk = track_data[off : off + event_size]
        if all(b == 0 for b in chunk):
            break
        val = int.from_bytes(chunk, "big")
        r = (9 * (seg_idx + 1)) % 56
        derot = rot_right(val, r)
        f0 = extract_9bit(derot, 0)
        f1 = extract_9bit(derot, 1)
        f2 = extract_9bit(derot, 2)
        f5 = extract_9bit(derot, 5)
        rem = derot & 0x3
        note = f0 & 0x7F
        vel_code = ((f0 >> 8) & 1) << 3 | ((f0 >> 7) & 1) << 2 | rem
        midi_vel = max(1, 127 - vel_code * 8)
        beat = f1 >> 7
        clock = ((f1 & 0x7F) << 2) | (f2 >> 7)
        tick_in_bar = beat * 480 + clock
        is_ctrl = note < min_note or note > max_note
        # Early stop: three consecutive ctrl events very likely mean the
        # pattern payload is over and we're hitting trailing padding /
        # segment metadata. Known_pattern ground truth never has > 2
        # ctrl events in a row, and factory dense styles collapse after
        # a handful of events in any case.
        if is_ctrl:
            consecutive_ctrl += 1
            if consecutive_ctrl >= 3:
                break
        else:
            consecutive_ctrl = 0
        events.append(
            {
                "note": int(note),
                "velocity": int(midi_vel),
                "gate": int(f5),
                "beat": int(beat),
                "clock": int(clock),
                "tick": int(tick_in_bar),
                "segment_index": seg_idx,
                "ctrl": bool(is_ctrl),
            }
        )
        off += event_size
        seg_idx += 1
    return events


def sparse_track_plausibility(events: list[dict]) -> float:
    """Share of events whose note falls inside the drum/melodic range."""
    if not events:
        return 0.0
    valid = sum(1 for e in events if not e.get("ctrl"))
    return valid / len(events)


def roundtrip_test(events: List[SparseEvent], bars: int = 1) -> list[dict]:
    """Encode → decode round-trip validation.

    Returns list of dicts with decoded events matching the input.
    Useful for testing encoder correctness.
    """
    encoded = encode_sparse_track(events, bars)
    # Find bar delimiters
    results = []
    offset = 28  # after header+preamble
    bar_idx = 0
    while bar_idx < bars:
        # Skip 13B bar header
        evt_start = offset + 13
        # Find next DC delimiter
        dc_pos = encoded.find(0xDC, evt_start)
        if dc_pos == -1:
            break
        # Decode events in this bar
        n_events = (dc_pos - evt_start) // 7
        for seg_idx in range(n_events):
            evt_bytes = encoded[evt_start + seg_idx * 7:evt_start + (seg_idx + 1) * 7]
            dec = decode_event(evt_bytes, seg_idx)
            dec["bar"] = bar_idx
            dec["tick_absolute"] = bar_idx * 1920 + dec["tick_in_bar"]
            results.append(dec)
        offset = dc_pos + 1
        bar_idx += 1
    return results
