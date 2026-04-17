"""
XG Parameter Change tool (Model ID 0x4C).

Parse, decode, and (optionally) emit XG SysEx messages.
Use cases:
- Analyze a captured .syx file that contains a stream of XG Param Change
  messages emitted by the QY70 at pattern load (XG PARM OUT setting).
- Diff two XG streams to identify which parameters changed.
- Emit specific XG Param Change messages for reverse engineering.

Protocol reference: wiki/xg-parameters.md
Source of authority: QY70 manual Tables 1-2..1-8 and studio4all.de main90-95.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# XG address space (AH = High byte)
# ---------------------------------------------------------------------------

AH_SYSTEM = 0x00
AH_EFFECT = 0x02
AH_MULTI_PART = 0x08
AH_DRUM_SETUP_1 = 0x30
AH_DRUM_SETUP_2 = 0x31

AH_NAMES = {
    AH_SYSTEM: "System",
    AH_EFFECT: "Effect",
    AH_MULTI_PART: "Multi Part",
    AH_DRUM_SETUP_1: "Drum Setup 1",
    AH_DRUM_SETUP_2: "Drum Setup 2",
}

# System messages (AH=0x00, AM=0x00, AL=...)
SYSTEM_AL_NAMES = {
    0x00: "Master Tune",  # 4 nibble, special
    0x04: "Master Volume",
    0x05: "Master Volume LSB",
    0x06: "Master Transpose",
    0x7D: "Drum Setup Reset",
    0x7E: "XG System On",
    0x7F: "All Parameter Reset",
}

# Effect address map (AH=0x02, AM=0x01, AL=...)
EFFECT_AL_NAMES = {
    # Reverb block (0x00-0x1F)
    0x00: "Reverb Type MSB",
    0x01: "Reverb Type LSB",
    0x02: "Reverb Time",
    0x03: "Reverb Diffusion",
    0x04: "Reverb Initial Delay",
    0x05: "Reverb HPF Cutoff",
    0x06: "Reverb LPF Cutoff",
    0x07: "Reverb Width",
    0x08: "Reverb Height",
    0x09: "Reverb Depth",
    0x0A: "Reverb Wall Variation",
    0x0B: "Reverb Dry/Wet",
    0x0C: "Reverb Return",
    0x0D: "Reverb Pan",
    0x10: "Reverb Delay",
    0x11: "Reverb Density",
    0x12: "Reverb ER/Rev Balance",
    0x14: "Reverb Feedback Level",
    # Chorus block (0x20-0x3F)
    0x20: "Chorus Type MSB",
    0x21: "Chorus Type LSB",
    0x22: "Chorus LFO Frequency",
    0x23: "Chorus LFO Phase Mod Depth",
    0x24: "Chorus Feedback Level",
    0x25: "Chorus Delay Offset",
    0x27: "Chorus EQ Low Frequency",
    0x28: "Chorus EQ Low Gain",
    0x29: "Chorus EQ High Frequency",
    0x2A: "Chorus EQ High Gain",
    0x2B: "Chorus Dry/Wet",
    0x2C: "Chorus Return",
    0x2D: "Chorus Pan",
    0x2E: "Send Chorus→Reverb",
    0x33: "Chorus LFO Phase Difference",
    0x34: "Chorus Input Mode",
    # Variation block (0x40-0x75)
    0x40: "Variation Type MSB",
    0x41: "Variation Type LSB",
    0x42: "Variation Param 1 MSB",
    0x43: "Variation Param 1 LSB",
    0x44: "Variation Param 2 MSB",
    0x45: "Variation Param 2 LSB",
    0x46: "Variation Param 3 MSB",
    0x47: "Variation Param 3 LSB",
    0x48: "Variation Param 4 MSB",
    0x49: "Variation Param 4 LSB",
    0x4A: "Variation Param 5 MSB",
    0x4B: "Variation Param 5 LSB",
    0x4C: "Variation Param 6 MSB",
    0x4D: "Variation Param 6 LSB",
    0x4E: "Variation Param 7 MSB",
    0x4F: "Variation Param 7 LSB",
    0x50: "Variation Param 8 MSB",
    0x51: "Variation Param 8 LSB",
    0x52: "Variation Param 9 MSB",
    0x53: "Variation Param 9 LSB",
    0x54: "Variation Param 10 MSB",
    0x55: "Variation Param 10 LSB",
    0x56: "Variation Return",
    0x57: "Variation Pan",
    0x58: "Send Variation→Reverb",
    0x59: "Send Variation→Chorus",
    0x5A: "Variation Connection",
    0x5B: "Variation Part",
    0x5C: "MW Variation Ctrl Depth",
    0x5D: "PB Variation Ctrl Depth",
    0x5E: "AT Variation Ctrl Depth",
    0x5F: "AC1 Variation Ctrl Depth",
    0x60: "AC2 Variation Ctrl Depth",
}

# Multi Part AL map (AH=0x08, AM=part[0..F], AL=...)
MULTI_PART_AL_NAMES = {
    0x00: "Element Reserve",
    0x01: "Bank Select MSB",
    0x02: "Bank Select LSB",
    0x03: "Program Number",
    0x04: "Receive MIDI Channel",
    0x05: "Mono/Poly Mode",
    0x06: "Same Note Key On Assign",
    0x07: "Part Mode",
    0x08: "Note Shift",
    0x09: "Detune MSB",
    0x0A: "Detune LSB",
    0x0B: "Volume",
    0x0C: "Velocity Sense Depth",
    0x0D: "Velocity Sense Offset",
    0x0E: "Pan",
    0x0F: "Note Limit Low",
    0x10: "Note Limit High",
    0x11: "Dry Level",
    0x12: "Chorus Send",
    0x13: "Reverb Send",
    0x14: "Variation Send",
    0x15: "Vibrato Rate",
    0x16: "Vibrato Depth",
    0x17: "Vibrato Delay",
    0x18: "Filter Cutoff",
    0x19: "Filter Resonance",
    0x1A: "EG Attack Time",
    0x1B: "EG Decay Time",
    0x1C: "EG Release Time",
    0x1D: "MW Pitch Control",
    0x1E: "MW Filter Control",
    0x1F: "MW Amplitude Control",
    0x20: "MW LFO Pitch Mod",
    0x21: "MW LFO Filter Mod",
    0x22: "MW LFO Amp Mod",
    0x23: "Bend Pitch Control",
    0x24: "Bend Filter Control",
    0x25: "Bend Amp Control",
    0x26: "Bend LFO Pitch",
    0x27: "Bend LFO Filter",
    0x28: "Bend LFO Amp",
    0x67: "Portamento Switch",
    0x68: "Portamento Time",
    0x69: "Pitch EG Initial",
    0x6A: "Pitch EG Attack",
    0x6B: "Pitch EG Rel Level",
    0x6C: "Pitch EG Rel Time",
    0x6D: "Velocity Limit Low",
    0x6E: "Velocity Limit High",
}

PART_MODE_NAMES = {0: "Normal", 1: "Drum", 2: "DrumSetup1", 3: "DrumSetup2"}

# Drum Setup AL (AH=0x30/0x31, AM=note number 0x0D..0x5B)
DRUM_SETUP_AL_NAMES = {
    0x00: "Pitch Coarse",
    0x01: "Pitch Fine",
    0x02: "Level",
    0x03: "Alternate Group",
    0x04: "Pan",
    0x05: "Reverb Send",
    0x06: "Chorus Send",
    0x07: "Variation Send",
    0x08: "Key Assign",
    0x09: "Rcv Note Off",
    0x0A: "Rcv Note On",
    0x0B: "Filter Cutoff",
    0x0C: "Filter Resonance",
    0x0D: "EG Attack Rate",
    0x0E: "EG Decay 1 Rate",
    0x0F: "EG Decay 2 Rate",
}


@dataclass
class XGMessage:
    """Parsed XG Parameter Change message."""
    device: int
    ah: int
    am: int
    al: int
    data: bytes  # 1..4 bytes of payload
    raw: bytes

    @property
    def ah_name(self) -> str:
        return AH_NAMES.get(self.ah, f"AH={self.ah:02X}")

    def pretty(self) -> str:
        hx = " ".join(f"{b:02x}" for b in self.raw)
        dec = self.decode()
        return f"{hx}  →  {dec}"

    def decode(self) -> str:
        """Human-readable decode."""
        data_hx = " ".join(f"{b:02X}" for b in self.data)
        if self.ah == AH_SYSTEM:
            name = SYSTEM_AL_NAMES.get(self.al, f"Sys AL={self.al:02X}")
            return f"[System] {name} = {data_hx}"
        elif self.ah == AH_EFFECT:
            name = EFFECT_AL_NAMES.get(self.al, f"Fx AL={self.al:02X}")
            return f"[Effect] {name} = {data_hx}"
        elif self.ah == AH_MULTI_PART:
            part = self.am
            name = MULTI_PART_AL_NAMES.get(self.al, f"Part AL={self.al:02X}")
            extra = ""
            if self.al == 0x07 and len(self.data) == 1:
                extra = f" ({PART_MODE_NAMES.get(self.data[0], '?')})"
            return f"[Part {part:02d}] {name} = {data_hx}{extra}"
        elif self.ah in (AH_DRUM_SETUP_1, AH_DRUM_SETUP_2):
            ds = 1 if self.ah == AH_DRUM_SETUP_1 else 2
            note = self.am
            name = DRUM_SETUP_AL_NAMES.get(self.al, f"DS AL={self.al:02X}")
            return f"[DS{ds} note={note:02X}] {name} = {data_hx}"
        else:
            return f"[AH={self.ah:02X} AM={self.am:02X} AL={self.al:02X}] = {data_hx}"


def split_sysex(blob: bytes) -> list[bytes]:
    """Split a byte blob into individual SysEx messages (F0 .. F7)."""
    msgs: list[bytes] = []
    i = 0
    n = len(blob)
    while i < n:
        if blob[i] == 0xF0:
            j = i + 1
            while j < n and blob[j] != 0xF7:
                j += 1
            if j < n:
                msgs.append(bytes(blob[i : j + 1]))
                i = j + 1
            else:
                break
        else:
            i += 1
    return msgs


def parse_xg(msg: bytes) -> XGMessage | None:
    """Parse a single SysEx message as XG Param Change. Return None if not XG."""
    if len(msg) < 8:
        return None
    if msg[0] != 0xF0 or msg[-1] != 0xF7:
        return None
    if msg[1] != 0x43:
        return None  # not Yamaha
    cmd = msg[2]
    if (cmd & 0xF0) != 0x10:
        return None  # not Parameter Change (1n)
    if msg[3] != 0x4C:
        return None  # not XG model ID
    device = cmd & 0x0F
    ah, am, al = msg[4], msg[5], msg[6]
    data = bytes(msg[7:-1])
    return XGMessage(device=device, ah=ah, am=am, al=al, data=data, raw=bytes(msg))


def parse_file(path: Path) -> list[XGMessage]:
    blob = path.read_bytes()
    out = []
    for m in split_sysex(blob):
        xg = parse_xg(m)
        if xg is not None:
            out.append(xg)
    return out


def build_xg(ah: int, am: int, al: int, data: Iterable[int], device: int = 0) -> bytes:
    """Build a raw XG Param Change SysEx message."""
    payload = bytes(data)
    return bytes([0xF0, 0x43, 0x10 | (device & 0x0F), 0x4C, ah, am, al]) + payload + b"\xF7"


# ---------------------------------------------------------------------------
# MIDI channel-event parsing (needed for mixed captures that also contain
# Program Change / Bank Select emitted by the QY70 at pattern load)
# ---------------------------------------------------------------------------

_CHANNEL_EVENT_LEN = {
    0x80: 3, 0x90: 3, 0xA0: 3, 0xB0: 3,  # NoteOff/On/PolyAT/CC
    0xC0: 2, 0xD0: 2,                      # Program Change / ChanAT
    0xE0: 3,                               # Pitch Bend
}


@dataclass
class MidiEvent:
    """Generic MIDI channel event parsed from a raw capture blob."""
    status: int  # 0x80..0xEF
    channel: int  # 0..15
    data: bytes

    @property
    def kind(self) -> int:
        return self.status & 0xF0

    def decode(self) -> str:
        names = {0x80: "NoteOff", 0x90: "NoteOn", 0xA0: "PolyAT",
                 0xB0: "CC", 0xC0: "PgmChg", 0xD0: "ChanAT", 0xE0: "PitchBend"}
        body = " ".join(f"{b:02X}" for b in self.data)
        return f"Ch{self.channel+1:02d} {names.get(self.kind, '?')} {body}"


def split_stream(blob: bytes) -> list[bytes]:
    """Split a raw MIDI capture blob into individual messages.

    Handles both SysEx (F0..F7) and channel events (0x80..0xEF). Realtime /
    system-common bytes in the F8..FF range are skipped.
    """
    msgs: list[bytes] = []
    i, n = 0, len(blob)
    while i < n:
        b = blob[i]
        if b == 0xF0:
            j = i + 1
            while j < n and blob[j] != 0xF7:
                j += 1
            if j >= n:
                break
            msgs.append(bytes(blob[i : j + 1]))
            i = j + 1
        elif 0x80 <= b <= 0xEF:
            k = b & 0xF0
            length = _CHANNEL_EVENT_LEN.get(k, 1)
            if i + length > n:
                break
            msgs.append(bytes(blob[i : i + length]))
            i += length
        else:
            i += 1  # realtime / continuation / garbage byte — skip
    return msgs


def parse_channel_event(raw: bytes) -> MidiEvent | None:
    if not raw:
        return None
    s = raw[0]
    if not (0x80 <= s <= 0xEF):
        return None
    return MidiEvent(status=s, channel=s & 0x0F, data=bytes(raw[1:]))


def parse_all_events(path: Path) -> tuple[list[XGMessage], list[MidiEvent]]:
    """Parse a blob that may contain both SysEx and MIDI channel events."""
    blob = path.read_bytes()
    xg_msgs: list[XGMessage] = []
    chan_events: list[MidiEvent] = []
    for m in split_stream(blob):
        if m and m[0] == 0xF0:
            xg = parse_xg(m)
            if xg is not None:
                xg_msgs.append(xg)
        else:
            ev = parse_channel_event(m)
            if ev is not None:
                chan_events.append(ev)
    return xg_msgs, chan_events


# ---------------------------------------------------------------------------
# Snapshot segmentation
#
# XG PARM OUT emits a header block each time the pattern/preset changes. Two
# observable boundaries delimit snapshots:
#   - XG System On           (AH=00 AM=00 AL=7E) — opens the very first block
#   - Drum Setup Reset       (AH=00 AM=00 AL=7D) — opens subsequent DS blocks
# Every message between two boundaries (inclusive of the opener) belongs to
# the same snapshot.
# ---------------------------------------------------------------------------

@dataclass
class XGSnapshot:
    """A contiguous block of XG messages between two boundary events."""
    idx: int
    boundary: str               # "XG_ON" or "DS_RESET"
    messages: list[XGMessage]

    @property
    def var_type(self) -> str | None:
        """Hex string of Variation Type MSB+LSB, or None if not set here."""
        for m in self.messages:
            if m.ah == AH_EFFECT and m.al == 0x40 and len(m.data) >= 2:
                return f"{m.data[0]:02x}{m.data[1]:02x}"
        return None

    @property
    def part_modes(self) -> dict[int, int]:
        """Map part index → part mode code for every Part Mode message seen."""
        out: dict[int, int] = {}
        for m in self.messages:
            if m.ah == AH_MULTI_PART and m.al == 0x07 and m.data:
                out[m.am] = m.data[0]
        return out

    @property
    def ds2_notes(self) -> list[int]:
        """Sorted list of DS2 notes touched in this snapshot."""
        notes = {m.am for m in self.messages if m.ah == AH_DRUM_SETUP_2}
        return sorted(notes)


def segment_snapshots(msgs: list[XGMessage]) -> list[XGSnapshot]:
    """Split a flat XG message list into per-preset snapshots."""
    snaps: list[XGSnapshot] = []
    current: list[XGMessage] = []
    current_boundary: str | None = None

    def flush():
        if current and current_boundary is not None:
            snaps.append(
                XGSnapshot(idx=len(snaps), boundary=current_boundary,
                           messages=list(current))
            )

    for m in msgs:
        is_xg_on = m.ah == AH_SYSTEM and m.al == 0x7E
        is_ds_reset = m.ah == AH_SYSTEM and m.al == 0x7D
        if is_xg_on or is_ds_reset:
            flush()
            current = [m]
            current_boundary = "XG_ON" if is_xg_on else "DS_RESET"
        else:
            current.append(m)
    flush()
    return snaps


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_parse(args):
    msgs = parse_file(Path(args.file))
    print(f"# {args.file}: {len(msgs)} XG Param Change messages")
    for m in msgs:
        print(m.pretty())


def cmd_summary(args):
    msgs = parse_file(Path(args.file))
    print(f"# {args.file}: {len(msgs)} XG messages")
    from collections import Counter
    ah_counts = Counter(m.ah for m in msgs)
    print("## By AH:")
    for ah, c in sorted(ah_counts.items()):
        print(f"  0x{ah:02X} {AH_NAMES.get(ah,'?'):<20s}: {c}")

    # Multi Part breakdown
    mp = [m for m in msgs if m.ah == AH_MULTI_PART]
    if mp:
        print(f"\n## Multi Part by NN (part):")
        nn_counts = Counter(m.am for m in mp)
        for nn, c in sorted(nn_counts.items()):
            print(f"  Part {nn:02d}: {c}")
        print(f"\n## Multi Part by AL:")
        al_counts = Counter(m.al for m in mp)
        for al, c in sorted(al_counts.items()):
            name = MULTI_PART_AL_NAMES.get(al, f"AL={al:02X}")
            print(f"  0x{al:02X} {name:<30s}: {c}")

    # Effect breakdown
    fx = [m for m in msgs if m.ah == AH_EFFECT]
    if fx:
        print(f"\n## Effect by AL:")
        al_counts = Counter(m.al for m in fx)
        for al, c in sorted(al_counts.items()):
            name = EFFECT_AL_NAMES.get(al, f"AL={al:02X}")
            print(f"  0x{al:02X} {name:<30s}: {c}")


def cmd_diff(args):
    """Diff two .syx files at message level."""
    a = parse_file(Path(args.a))
    b = parse_file(Path(args.b))
    # Key each message by (ah, am, al)
    from collections import OrderedDict
    def keyed(msgs):
        d = OrderedDict()
        for m in msgs:
            d[(m.ah, m.am, m.al)] = m
        return d
    ka = keyed(a)
    kb = keyed(b)
    only_a = [k for k in ka if k not in kb]
    only_b = [k for k in kb if k not in ka]
    changed = [(k, ka[k], kb[k]) for k in ka if k in kb and ka[k].data != kb[k].data]

    print(f"# Diff {args.a} vs {args.b}")
    print(f"Only in A: {len(only_a)}, Only in B: {len(only_b)}, Changed: {len(changed)}")
    if only_a:
        print("\n## Only in A:")
        for k in only_a[:20]:
            print(f"  {ka[k].decode()}")
    if only_b:
        print("\n## Only in B:")
        for k in only_b[:20]:
            print(f"  {kb[k].decode()}")
    if changed:
        print("\n## Changed:")
        for k, ma, mb in changed[:40]:
            da = " ".join(f"{x:02X}" for x in ma.data)
            db = " ".join(f"{x:02X}" for x in mb.data)
            print(f"  AH={k[0]:02X} AM={k[1]:02X} AL={k[2]:02X}: {da} → {db}  [{ma.decode()}]")


def cmd_emit(args):
    """Build and print a single XG Param Change message."""
    ah = int(args.ah, 16)
    am = int(args.am, 16)
    al = int(args.al, 16)
    data = [int(x, 16) for x in args.data.split(",")]
    raw = build_xg(ah, am, al, data)
    print(" ".join(f"{b:02x}" for b in raw))
    m = parse_xg(raw)
    if m:
        print("# " + m.decode())


def main():
    ap = argparse.ArgumentParser(description="XG Parameter Change tool")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("parse", help="Parse a .syx and print every XG msg")
    p.add_argument("file")
    p.set_defaults(func=cmd_parse)

    p = sub.add_parser("summary", help="Summarize XG messages in a .syx")
    p.add_argument("file")
    p.set_defaults(func=cmd_summary)

    p = sub.add_parser("diff", help="Diff two XG .syx streams")
    p.add_argument("a")
    p.add_argument("b")
    p.set_defaults(func=cmd_diff)

    p = sub.add_parser("emit", help="Build an XG Param Change message")
    p.add_argument("--ah", required=True, help="Address High (hex, e.g. 08)")
    p.add_argument("--am", required=True, help="Address Mid (hex)")
    p.add_argument("--al", required=True, help="Address Low (hex)")
    p.add_argument("--data", required=True, help="Comma-separated hex data bytes (e.g. 40,00)")
    p.set_defaults(func=cmd_emit)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
