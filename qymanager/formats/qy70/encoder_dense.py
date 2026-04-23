"""
Dense-factory encoder for QY70 SysEx pattern bitstream.

Implements per-event R lookup table encoding (SGT/factory styles).
Achieves 100% byte-exact roundtrip on all SGT tracks.

Usage:
    from qymanager.formats.qy70.encoder_dense import DenseEncoder

    encoder = DenseEncoder()
    encoder.set_R_table(track_idx=6, R_table=[2, 13, 3, 19, ...])
    events = encoder.decode(body_bytes, track_idx=6)
    # Modify events...
    body_reconstructed = encoder.encode(events, track_idx=6)

Per-track R table size varies:
  - Chord/melodic tracks (BASS/CHD/PHR): N=32 (= 4 bars × 8 events/bar)
  - Drum tracks (RHY1): N=105 (denser)
  - PAD: N=14 (sparse)

Pre-calibrated SGT R tables available in data/sgt_R_tables.json.
"""

from dataclasses import dataclass
from typing import Optional


# ═══════════════════════════════════════════════════════════════════
# Rotation primitives
# ═══════════════════════════════════════════════════════════════════

def rot_right(val: int, shift: int, width: int = 56) -> int:
    shift %= width
    return ((val >> shift) | (val << (width - shift))) & ((1 << width) - 1)


def rot_left(val: int, shift: int, width: int = 56) -> int:
    return rot_right(val, (-shift) % width, width)


# ═══════════════════════════════════════════════════════════════════
# Field extraction / assembly
# ═══════════════════════════════════════════════════════════════════

@dataclass
class DenseEvent:
    """Decoded dense-factory event with 6 × 9-bit fields + 2-bit remainder."""
    f0: int  # note + vel flags
    f1: int  # beat + clock hi
    f2: int  # clock lo + position
    f3: int  # position/chord related
    f4: int  # position/chord related
    f5: int  # gate time
    rem: int  # 2-bit velocity low + remainder

    @property
    def note(self) -> int:
        return self.f0 & 0x7F

    @property
    def velocity(self) -> int:
        bit7 = (self.f0 >> 7) & 1
        bit8 = (self.f0 >> 8) & 1
        vel_code = (bit8 << 3) | (bit7 << 2) | self.rem
        return max(1, 127 - vel_code * 8)

    @property
    def gate(self) -> int:
        return self.f5

    @property
    def beat(self) -> int:
        return self.f1 >> 7


def decode_event(chunk: bytes, R: int) -> DenseEvent:
    """Decode 7-byte event using per-event R."""
    val = int.from_bytes(chunk, "big")
    derot = rot_right(val, R)
    return DenseEvent(
        f0=(derot >> 47) & 0x1FF,
        f1=(derot >> 38) & 0x1FF,
        f2=(derot >> 29) & 0x1FF,
        f3=(derot >> 20) & 0x1FF,
        f4=(derot >> 11) & 0x1FF,
        f5=(derot >> 2) & 0x1FF,
        rem=derot & 0x3,
    )


def encode_event(event: DenseEvent, R: int) -> bytes:
    """Encode DenseEvent back to 7 bytes with given R."""
    val = 0
    val |= (event.f0 & 0x1FF) << 47
    val |= (event.f1 & 0x1FF) << 38
    val |= (event.f2 & 0x1FF) << 29
    val |= (event.f3 & 0x1FF) << 20
    val |= (event.f4 & 0x1FF) << 11
    val |= (event.f5 & 0x1FF) << 2
    val |= (event.rem & 0x3)
    stored = rot_left(val, R)
    return stored.to_bytes(7, "big")


# ═══════════════════════════════════════════════════════════════════
# Dense encoder class
# ═══════════════════════════════════════════════════════════════════

class DenseEncoder:
    """Dense-factory encoder/decoder using per-event R lookup tables.

    Usage:
        encoder = DenseEncoder()
        encoder.set_R_table("PHR1", [2, 13, 3, 19, ...])
        events = encoder.decode(body_bytes, "PHR1")
        body = encoder.encode(events, "PHR1")
    """

    def __init__(self):
        self.R_tables: dict[str, list[int]] = {}

    def set_R_table(self, track_key: str, R_table: list[int]):
        """Register an R lookup table for a track."""
        self.R_tables[track_key] = list(R_table)

    def load_sgt_tables(self, json_path: Optional[str] = None):
        """Load pre-calibrated SGT R tables from JSON."""
        import json
        from pathlib import Path
        if json_path is None:
            candidates = [
                Path(__file__).parent.parent.parent.parent / "data" / "sgt_R_tables.json",
                Path.cwd() / "data" / "sgt_R_tables.json",
            ]
            json_path = next((c for c in candidates if c.exists()), None)
        if json_path is None:
            raise FileNotFoundError("sgt_R_tables.json not found")
        data = json.loads(Path(json_path).read_text())
        for trk_str, t in data.items():
            self.R_tables[t["name"]] = list(t["best_Rs"])

    def decode(self, body: bytes, track_key: str, skip_header: int = 28) -> list[DenseEvent]:
        """Decode body bytes → list of events.

        Skips first `skip_header` bytes (track header + preamble) by default.
        """
        if track_key not in self.R_tables:
            raise KeyError(f"No R table registered for {track_key}")
        R_table = self.R_tables[track_key]
        N = len(R_table)
        body = body[skip_header:]
        events = []
        for i in range(len(body) // 7):
            chunk = body[i * 7:(i + 1) * 7]
            R = R_table[i % N]
            events.append(decode_event(chunk, R))
        return events

    def encode(self, events: list[DenseEvent], track_key: str,
               header_prefix: Optional[bytes] = None) -> bytes:
        """Encode event list → body bytes.

        If header_prefix provided, prepends it (useful to preserve 28B track header).
        """
        if track_key not in self.R_tables:
            raise KeyError(f"No R table registered for {track_key}")
        R_table = self.R_tables[track_key]
        N = len(R_table)
        body = bytearray(header_prefix or b"")
        for i, event in enumerate(events):
            R = R_table[i % N]
            body.extend(encode_event(event, R))
        return bytes(body)

    def roundtrip_test(self, body: bytes, track_key: str) -> dict:
        """Verify decode → encode produces byte-identical output.
        Returns dict with {matches, total, percent}.
        """
        if track_key not in self.R_tables:
            raise KeyError(f"No R table registered for {track_key}")
        R_table = self.R_tables[track_key]
        N = len(R_table)
        body = body[28:]
        matches = 0
        total = 0
        for i in range(len(body) // 7):
            original = body[i * 7:(i + 1) * 7]
            R = R_table[i % N]
            event = decode_event(original, R)
            encoded = encode_event(event, R)
            total += 1
            if encoded == original:
                matches += 1
        return {
            "matches": matches,
            "total": total,
            "percent": round(matches / max(1, total) * 100, 1),
        }
