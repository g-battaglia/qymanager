"""
Parser for XG Multi Part bulk dump responses from QY70.

Request format: F0 43 20 4C 08 <part> 00 F7
Response: 52-byte bulk dump (F0 43 00 4C 00 29 08 00 <part> [41B payload] CS F7)

Use via:
    from qymanager.formats.qy70.xg_multi_part import request_multi_part_dump, parse_multi_part_response

    # Over MIDI
    parts = request_multi_part_dump(port_hint="porta 1")
    for part_num, part_info in parts.items():
        print(f"Part {part_num}: Bank {part_info['bank_msb']}/{part_info['bank_lsb']} Prog {part_info['program']}")
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MultiPartInfo:
    """Decoded XG Multi Part data for one part."""
    part_num: int
    element_reserve: int = 0x02
    bank_msb: int = 0
    bank_lsb: int = 0
    program: int = 0
    rcv_channel: int = 0
    mono_poly: int = 1      # 0=mono, 1=poly
    key_on_assign: int = 1  # 0=single, 1=multi
    part_mode: int = 0      # 0=normal, 1=drum, 2=drum1, 3=drum2
    note_shift: int = 0x40  # 0x40=center (no shift)
    additional: bytes = field(default_factory=bytes)

    @property
    def is_drum(self) -> bool:
        return self.bank_msb == 0x7F or self.part_mode in (1, 2, 3)

    @property
    def voice_name(self) -> str:
        """Rough voice name based on bank+program."""
        if self.is_drum:
            drum_kits = {0: "Standard Kit 1", 1: "Standard Kit 2", 8: "Room Kit",
                         16: "Rock Kit", 24: "Electro Kit", 25: "Analog Kit",
                         32: "Jazz Kit", 40: "Brush Kit", 48: "Symphony Kit"}
            return drum_kits.get(self.program, f"DrumKit#{self.program}")
        gm1 = ["GrandPno", "BritePno", "E.Grand", "HnkyTonk",
               "E.Piano1", "E.Piano2", "Harpsi", "Clavi"]
        # Add more as needed
        return gm1[self.program] if self.program < len(gm1) else f"Voice#{self.program}"


def parse_multi_part_response(data: bytes) -> Optional[MultiPartInfo]:
    """Parse a Multi Part bulk dump response (52 bytes).

    Format: F0 43 00 4C BH BL AH AM AL [payload 41B] CS F7
      - BH BL = 0x00 0x29 (BC=41)
      - AH = 0x08 (Multi Part)
      - AM = 0x00
      - AL = part number (0-15)
    """
    if len(data) != 52:
        return None
    if data[0] != 0xF0 or data[-1] != 0xF7:
        return None
    if data[1] != 0x43 or data[3] != 0x4C:
        return None
    if data[6] != 0x08:  # AH must be Multi Part
        return None

    part_num = data[8]  # AL
    payload = data[9:-2]  # skip checksum + F7
    if len(payload) < 10:
        return None

    return MultiPartInfo(
        part_num=part_num,
        element_reserve=payload[0],
        bank_msb=payload[1],
        bank_lsb=payload[2],
        program=payload[3],
        rcv_channel=payload[4],
        mono_poly=payload[5],
        key_on_assign=payload[6],
        part_mode=payload[7],
        note_shift=payload[8],
        additional=bytes(payload[9:]),
    )


def build_multi_part_request(part: int) -> bytes:
    """Build XG Multi Part bulk dump request SysEx."""
    return bytes([0xF0, 0x43, 0x20, 0x4C, 0x08, part, 0x00, 0xF7])


def request_multi_part_dump(port_hint: str = "porta 1", parts_range=range(16),
                             timeout: float = 0.8) -> dict[int, MultiPartInfo]:
    """Over MIDI: request dump per part, parse responses.

    Returns {part_num: MultiPartInfo}.
    """
    import rtmidi
    import threading
    import time

    def find(m):
        for i in range(m.get_port_count()):
            if port_hint.lower() in m.get_port_name(i).lower():
                return i
        return 0

    mo = rtmidi.MidiOut()
    mi = rtmidi.MidiIn()
    mi.ignore_types(sysex=False, timing=True, active_sense=True)
    captured = []
    stop = [False]

    def listener():
        mi.open_port(find(mi))
        while not stop[0]:
            m = mi.get_message()
            if m:
                captured.append(bytes(m[0]))
            else:
                time.sleep(0.0005)
        mi.close_port()

    t = threading.Thread(target=listener, daemon=True)
    t.start()
    time.sleep(0.3)

    mo.open_port(find(mo))
    results = {}
    for part in parts_range:
        captured.clear()
        time.sleep(0.1)
        mo.send_message(list(build_multi_part_request(part)))
        time.sleep(timeout)
        for msg in captured:
            info = parse_multi_part_response(msg)
            if info is not None and info.part_num == part:
                results[part] = info
                break
    mo.close_port()
    stop[0] = True
    t.join(timeout=1)
    return results
