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

from dataclasses import dataclass
from typing import Optional


@dataclass
class MultiPartInfo:
    """Decoded XG Multi Part data for one part (41-byte bulk dump payload)."""
    part_num: int
    # AL 0x00-0x08
    element_reserve: int = 0x02
    bank_msb: int = 0
    bank_lsb: int = 0
    program: int = 0
    rcv_channel: int = 0
    mono_poly: int = 1
    key_on_assign: int = 1
    part_mode: int = 0
    note_shift: int = 0x40
    # AL 0x09-0x0A (Detune 2-byte)
    detune_msb: int = 0x08
    detune_lsb: int = 0x00
    # AL 0x0B-0x14 (Volume, Velocity, Pan, Limits, Dry, Sends)
    volume: int = 0x64
    velocity_sense_depth: int = 0x40
    velocity_sense_offset: int = 0x40
    pan: int = 0x40
    note_limit_low: int = 0x00
    note_limit_high: int = 0x7F
    dry_level: int = 0x7F
    chorus_send: int = 0x00
    reverb_send: int = 0x28
    variation_send: int = 0x00
    # AL 0x15-0x17 (Vibrato)
    vibrato_rate: int = 0x40
    vibrato_depth: int = 0x40
    vibrato_delay: int = 0x40
    # AL 0x18-0x1C (Filter & EG)
    cutoff: int = 0x40
    resonance: int = 0x40
    eg_attack: int = 0x40
    eg_decay: int = 0x40
    eg_release: int = 0x40
    # AL 0x1D-0x22 (MW Control)
    mw_pitch_control: int = 0x40
    mw_filter_control: int = 0x40
    mw_amplitude_control: int = 0x40
    mw_lfo_pitch_depth: int = 0x0A
    mw_lfo_filter_depth: int = 0x00
    mw_lfo_amplitude_depth: int = 0x00
    # AL 0x23-0x28 (Bend Control)
    bend_pitch: int = 0x42
    bend_filter_control: int = 0x40
    bend_amplitude_control: int = 0x40
    bend_lfo_pitch_depth: int = 0x40
    bend_lfo_filter_depth: int = 0x40
    bend_lfo_amplitude_depth: int = 0x40

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

    def _b(i: int) -> int:
        return payload[i] if i < len(payload) else 0

    return MultiPartInfo(
        part_num=part_num,
        element_reserve=_b(0),
        bank_msb=_b(1),
        bank_lsb=_b(2),
        program=_b(3),
        rcv_channel=_b(4),
        mono_poly=_b(5),
        key_on_assign=_b(6),
        part_mode=_b(7),
        note_shift=_b(8),
        detune_msb=_b(9),
        detune_lsb=_b(10),
        volume=_b(11),
        velocity_sense_depth=_b(12),
        velocity_sense_offset=_b(13),
        pan=_b(14),
        note_limit_low=_b(15),
        note_limit_high=_b(16),
        dry_level=_b(17),
        chorus_send=_b(18),
        reverb_send=_b(19),
        variation_send=_b(20),
        vibrato_rate=_b(21),
        vibrato_depth=_b(22),
        vibrato_delay=_b(23),
        cutoff=_b(24),
        resonance=_b(25),
        eg_attack=_b(26),
        eg_decay=_b(27),
        eg_release=_b(28),
        mw_pitch_control=_b(29),
        mw_filter_control=_b(30),
        mw_amplitude_control=_b(31),
        mw_lfo_pitch_depth=_b(32),
        mw_lfo_filter_depth=_b(33),
        mw_lfo_amplitude_depth=_b(34),
        bend_pitch=_b(35),
        bend_filter_control=_b(36),
        bend_amplitude_control=_b(37),
        bend_lfo_pitch_depth=_b(38),
        bend_lfo_filter_depth=_b(39),
        bend_lfo_amplitude_depth=_b(40),
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
