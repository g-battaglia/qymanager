"""
QY70 SysEx file analyzer.

Extracts ALL information from QY70 SysEx bulk dump files including:
- Message structure and statistics
- Section data for each AL address
- Header configuration
- Decoded phrase data
- Checksum validation results
- Note ranges and event counts
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from collections import Counter
import json

from qymanager.formats.qy70.sysex_parser import SysExParser, SysExMessage, MessageType
from qymanager.utils.yamaha_7bit import decode_7bit
from qymanager.utils.checksum import verify_sysex_checksum
from qymanager.utils.xg_voices import get_voice_name
from qymanager.utils.xg_effects import (
    get_reverb_type_name,
    get_chorus_type_name,
    get_variation_type_name,
    get_drum_kit_name,
    XG_DEFAULTS,
)


_SIGNATURE_DB: Optional[Dict[str, Dict[str, int]]] = None


def _nearest_neighbor_voice(
    sig_hex: str,
    db: Dict[str, Dict[str, int]],
    *,
    max_bit_dist: int = 3,
) -> Optional[Tuple[Dict[str, int], int]]:
    """Find the DB entry with the smallest bit-level Hamming distance
    from `sig_hex`, as long as that distance is ≤ `max_bit_dist`.

    Uses the embedded 4-byte class signature (sig10 bytes 3..6 =
    track-data bytes 17..20) as a hard pre-filter: a bass NN will
    never be picked for a chord signature even if the raw Hamming
    distance is small, because the class signature differs. If no
    DB entry shares the class signature we fall back to global NN.

    Returns `(entry, bit_distance)` or `None`. Empirically on the
    2026-04-23 dataset, melodic signatures converge on the correct
    voice at bit_dist ≤ 3 (MR. Vain C1/C2/C3 ↔ Pad 2 warm at
    bit_dist 1-2). Drum signatures do NOT (same Drum Kit 26 has 11
    samples with zero stable bytes), so callers should filter drum
    hits back out to the class fallback.
    """
    if not sig_hex:
        return None
    try:
        target = bytes.fromhex(sig_hex)
    except ValueError:
        return None
    if len(target) != 10:
        return None
    target_class = target[3:7]  # embedded class signature

    def rank(candidates):
        best_entry: Optional[Dict[str, int]] = None
        best_dist = max_bit_dist + 1
        for k, v in candidates:
            try:
                other = bytes.fromhex(k)
            except ValueError:
                continue
            if len(other) != 10:
                continue
            d = sum(bin(x ^ y).count("1") for x, y in zip(target, other))
            if d < best_dist:
                best_dist = d
                best_entry = v
                if d == 0:
                    break
        return (best_entry, best_dist) if best_entry is not None else None

    class_matched = [
        (k, v) for k, v in db.items() if bytes.fromhex(k)[3:7] == target_class
    ]
    if class_matched:
        hit = rank(class_matched)
        if hit is not None:
            return hit
    # Fallback: global NN only when no class peer exists
    return rank(list(db.items()))


def _load_signature_db() -> Dict[str, Dict[str, int]]:
    """Load the 10-byte voice signature → (msb, lsb, prog) lookup database.

    Built from known patterns (SGT, AMB01, STYLE2) captured via hardware on
    2026-04-23. The 10-byte signature is B14-B23 of each track header and is
    a stable fingerprint that correlates with the voice assigned on the QY70.

    The signature encodes ROM-internal voice index and cannot be decoded to
    MSB/LSB/Prog analytically — only via lookup of patterns we've already
    correlated. For unknown signatures we fall back to 4-byte class signature.
    """
    global _SIGNATURE_DB
    if _SIGNATURE_DB is None:
        # data/voice_signature_db.json lives at project root
        db_path = Path(__file__).resolve().parent.parent.parent / "data" / "voice_signature_db.json"
        if db_path.exists():
            try:
                _SIGNATURE_DB = json.loads(db_path.read_text())
            except Exception:
                _SIGNATURE_DB = {}
        else:
            _SIGNATURE_DB = {}
    return _SIGNATURE_DB


def midi_note_to_name(midi_note: int) -> str:
    """Convert MIDI note number to note name (e.g., 60 -> C4)."""
    if midi_note < 0 or midi_note > 127:
        return f"?{midi_note}"
    notes = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    octave = (midi_note // 12) - 1
    note = notes[midi_note % 12]
    return f"{note}{octave}"


@dataclass
class MessageInfo:
    """Information about a single SysEx message."""

    index: int
    message_type: str
    device_number: int
    address: Tuple[int, int, int]
    address_hex: str
    byte_count: int
    data_size: int
    decoded_size: int
    checksum: int
    checksum_valid: bool
    raw_size: int


@dataclass
class SectionData:
    """Decoded section data from QY70."""

    al_index: int
    name: str
    message_count: int
    total_decoded_bytes: int
    decoded_data: bytes
    # Analysis of content
    non_zero_bytes: int
    data_preview: str  # First 32 bytes hex


@dataclass
class QY70TrackInfo:
    """Track information for QY70 (8 tracks)."""

    number: int  # 1-8
    name: str  # D1, D2, PC, BA, C1, C2, C3, C4
    channel: int  # MIDI channel 1-16 (10 = drums)
    has_data: bool  # Whether track has any data in any section
    data_bytes: int  # Total bytes across all sections
    active_sections: List[str]  # Which sections have data for this track

    # Voice settings (extracted from track data header)
    bank_msb: int = 0  # Bank Select MSB (0 = normal, 127 = drums)
    bank_lsb: int = 0  # Bank Select LSB
    program: int = 0  # Program Change (0-127)
    voice_name: str = ""  # Resolved voice name from xg_voices

    # Mixer settings
    volume: int = 100  # CC7 (default 100)
    pan: int = 64  # CC10 (64 = center)
    reverb_send: int = 40  # CC91 (default 40)
    chorus_send: int = 0  # CC93 (default 0)
    variation_send: int = 0  # CC94 (default 0)

    # Note range (for melody tracks)
    note_low: int = 0  # Lowest playable note (MIDI note number)
    note_high: int = 127  # Highest playable note (MIDI note number)
    note_range_str: str = ""  # Human readable range like "C2-C7"

    # Event statistics
    event_count: int = 0  # Estimated number of MIDI events in track
    data_density: float = 0.0  # Percentage of non-zero bytes in sequence data

    # Flags
    is_drum_track: bool = False


@dataclass
class QY70SectionInfo:
    """Section information for QY70 (6 sections)."""

    index: int  # 0-5
    name: str  # Intro, MainA, MainB, FillAB, FillBA, Ending
    has_data: bool  # Whether section has any data
    phrase_bytes: int  # Phrase data size
    track_bytes: int  # Total track data size
    active_tracks: List[int]  # Which tracks (1-8) have data

    # Section length
    bar_count: int = 0  # Number of bars in section (estimated)
    beat_count: int = 0  # Number of beats in section


@dataclass
class SyxAnalysis:
    """Complete QY70 SysEx file analysis result."""

    # File info
    filepath: str
    filesize: int
    valid: bool

    # Message statistics
    total_messages: int
    bulk_dump_messages: int
    parameter_messages: int
    style_data_messages: int
    valid_checksums: int
    invalid_checksums: int

    # Message details
    messages: List[MessageInfo] = field(default_factory=list)

    # Section analysis
    sections: Dict[int, SectionData] = field(default_factory=dict)
    section_summary: List[Tuple[int, str, int]] = field(default_factory=list)  # (AL, name, size)

    # Header section (0x7F)
    header_data: bytes = b""
    header_decoded: bytes = b""

    # Pattern info extracted from header
    pattern_name: str = ""
    tempo: int = 120
    time_signature: Tuple[int, int] = (4, 4)
    time_signature_raw: int = 0

    # Pattern-slot name directory (from AH=0x05 dump), slot_index → name
    pattern_directory: Dict[int, str] = field(default_factory=dict)

    # Voice edit dumps (AH=0x00 AM=0x40 AL=0x20 = user voice edit bulk dump)
    # List of {class_signature, size_bytes, raw_hex_preview}
    voice_edit_dumps: List[Dict[str, Any]] = field(default_factory=list)

    # XG state parsed from Model 4C messages (when .syx has them)
    xg_voices: Dict[int, Dict[str, int]] = field(default_factory=dict)
    xg_effects: Dict[str, int] = field(default_factory=dict)
    xg_system: Dict[str, int] = field(default_factory=dict)
    xg_drum_setup: Dict[int, Dict[int, Dict[str, int]]] = field(default_factory=dict)

    # AL address distribution
    al_addresses: List[int] = field(default_factory=list)
    al_histogram: Dict[int, int] = field(default_factory=dict)

    # Track sections (0x08-0x2F)
    track_sections: Dict[int, bytes] = field(default_factory=dict)

    # Raw statistics
    total_encoded_bytes: int = 0
    total_decoded_bytes: int = 0

    # QY70-specific analysis (8 tracks, 6 sections)
    qy70_tracks: List[QY70TrackInfo] = field(default_factory=list)
    qy70_sections: List[QY70SectionInfo] = field(default_factory=list)
    active_section_count: int = 0
    active_track_count: int = 0
    data_density: float = 0.0

    # Global effects (extracted from header)
    reverb_type: str = "Hall 1"  # Default XG reverb
    reverb_type_msb: int = 0x01
    reverb_type_lsb: int = 0x00
    chorus_type: str = "Chorus 1"  # Default XG chorus
    chorus_type_msb: int = 0x41
    chorus_type_lsb: int = 0x00
    variation_type: str = "No Effect"
    variation_type_msb: int = 0x00
    variation_type_lsb: int = 0x00

    # File format detection
    # "pattern" = Single pattern (AL 0x00-0x07 for track data)
    # "style" = Full style with sections (AL 0x08-0x37 for track data)
    # "unknown" = Could not detect format
    format_type: str = "unknown"


class SyxAnalyzer:
    """
    Complete analyzer for QY70 SysEx files.

    Extracts and decodes all message content.
    The QY70 has 8 tracks per pattern (vs 16 in QY700):
    - D1, D2: Drum tracks (drums, channel 10)
    - PC: Percussion/Chord track (channel 3)
    - BA: Bass track (channel 2)
    - C1-C4: Chord tracks (channels 4-7)

    Note: The track order on the QY70 display is:
    D1, D2, PC, BA, C1, C2, C3, C4 (positions 1-8)

    In the SysEx format, tracks are stored at AL addresses:
    - Style format: AL = 0x08 + (section * 8) + track_index
    - Pattern format: AL = track_index (0-7)
    """

    # QY70 track names as shown on device display
    # Order: D1, D2, PC, BA, C1, C2, C3, C4
    TRACK_NAMES = ["D1", "D2", "PC", "BA", "C1", "C2", "C3", "C4"]

    # Long track names for display
    TRACK_LONG_NAMES = [
        "Drum 1",
        "Drum 2",
        "Perc/Chord",
        "Bass",
        "Chord 1",
        "Chord 2",
        "Chord 3",
        "Chord 4",
    ]

    # Default MIDI channels for QY70 tracks (PATT OUT CH=9~16 mode, verified 2026-04-23)
    # D1/RHY1=ch9, D2/RHY2=ch10, PC/PAD=ch11, BA/BASS=ch12
    # C1/CHD1=ch13, C2/CHD2=ch14, C3/PHR1=ch15, C4/PHR2=ch16
    # Source: hardware playback capture user QY70 + wiki/session-32f-captures.md
    DEFAULT_CHANNELS = [9, 10, 11, 12, 13, 14, 15, 16]

    # Section names (6 sections: Intro, MainA, MainB, FillAB, FillBA, Ending)
    STYLE_SECTION_NAMES = ["Intro", "Main A", "Main B", "Fill AB", "Fill BA", "Ending"]

    # Section names by AL index
    # NOTE: AL 0x00-0x2F are ALL track data (section*8 + track).
    # Only AL 0x7F is the header. There is no separate "phrase data" region.
    # Confirmed by SGT reference: AL=section_idx*8+track_idx for all sections.
    SECTION_NAMES = {
        0x7F: "Style Header/Config",
    }

    # Track section range
    # QY70 uses AL = section_index * 8 + track_index (confirmed from SGT dump)
    # Section 0: AL 0x00-0x07, Section 1: AL 0x08-0x0F, ..., Section 5: AL 0x28-0x2F
    TRACK_SECTION_START = 0x00
    TRACK_SECTION_END = 0x2F  # 6 sections * 8 tracks - 1

    def __init__(self):
        self.parser = SysExParser()
        self.messages: List[SysExMessage] = []
        self.data: bytes = b""

    def analyze_file(self, filepath: str) -> SyxAnalysis:
        """Analyze a SysEx file completely."""
        path = Path(filepath)

        with open(path, "rb") as f:
            self.data = f.read()

        return self._analyze(str(path))

    def analyze_bytes(self, data: bytes, name: str = "memory") -> SyxAnalysis:
        """Analyze SysEx data from bytes."""
        self.data = data
        return self._analyze(name)

    def _parse_xg_multi_part(self) -> Dict[int, Dict[str, int]]:
        """Parse XG Parameter Change messages (Model 4C) for Multi Part info.

        Returns {part_number: {bank_msb, bank_lsb, program, volume, pan, reverb, chorus, part_mode}}

        XG Parameter Change format: F0 43 1n 4C <AH> <AM> <AL> <data> F7
        Multi Part AH=0x08. AM=part number. AL=field:
          0x01 Bank MSB, 0x02 Bank LSB, 0x03 Program
          0x0B Volume, 0x0E Pan, 0x13 Reverb send, 0x12 Chorus send
          0x07 Part Mode

        Also captures XG Effect block (AH=0x02, AM=0x01) Reverb/Chorus/Variation
        type MSB/LSB into self.xg_effects {reverb_type_msb, reverb_type_lsb, ...}.

        Also parses channel events Bank Select (CC#0/32) + Program Change,
        which carry the actual voice info per XG Multi Part stream.
        """
        voices: Dict[int, Dict[str, int]] = {}
        # Effects: reverb/chorus/variation type codes (MSB/LSB pair per effect)
        self.xg_effects: Dict[str, int] = {}
        # System: master tune/volume/transpose (from XG System AH=0x00 AM=0x00)
        self.xg_system: Dict[str, int] = {}
        # Drum Setup: per-note overrides (from AH=0x30/0x31 drum setup 1/2)
        # Structure: {setup_num: {note_num: {param: value}}}
        self.xg_drum_setup: Dict[int, Dict[int, Dict[str, int]]] = {}
        raw = self.data

        # Scan for SysEx messages F0 ... F7 and channel messages
        i = 0
        while i < len(raw):
            b = raw[i]
            if b == 0xF0:
                # Find F7
                j = i + 1
                while j < len(raw) and raw[j] != 0xF7:
                    j += 1
                if j >= len(raw):
                    break
                msg = raw[i:j+1]
                # XG Parameter Change: F0 43 1n 4C AH AM AL data F7
                if (len(msg) >= 9 and msg[1] == 0x43 and msg[3] == 0x4C and
                        (msg[2] & 0xF0) == 0x10):
                    ah, am, al, data_val = msg[4], msg[5], msg[6], msg[7]
                    if ah == 0x08:  # Multi Part
                        part = am
                        voices.setdefault(part, {})
                        # Core voice selection
                        if al == 0x01:
                            voices[part]["bank_msb"] = data_val
                        elif al == 0x02:
                            voices[part]["bank_lsb"] = data_val
                        elif al == 0x03:
                            voices[part]["program"] = data_val
                        # Channel/mode
                        elif al == 0x04:
                            voices[part]["rcv_channel"] = data_val
                        elif al == 0x05:
                            voices[part]["mono_poly"] = data_val
                        elif al == 0x07:
                            voices[part]["part_mode"] = data_val
                        # Note range / shift
                        elif al == 0x08:
                            voices[part]["note_shift"] = data_val
                        elif al == 0x09:
                            voices[part]["detune"] = data_val
                        elif al == 0x0F:
                            voices[part]["note_limit_low"] = data_val
                        elif al == 0x10:
                            voices[part]["note_limit_high"] = data_val
                        # Mixer
                        elif al == 0x0B:
                            voices[part]["volume"] = data_val
                        elif al == 0x0E:
                            voices[part]["pan"] = data_val
                        elif al == 0x11:
                            voices[part]["dry_level"] = data_val
                        # Effect sends
                        elif al == 0x12:
                            voices[part]["chorus"] = data_val
                        elif al == 0x13:
                            voices[part]["reverb"] = data_val
                        elif al == 0x14:
                            voices[part]["variation"] = data_val
                        # Filter
                        elif al == 0x23:
                            voices[part]["filter_cutoff"] = data_val
                        elif al == 0x24:
                            voices[part]["filter_resonance"] = data_val
                    elif ah == 0x02 and am == 0x01:  # Effect block
                        # AL 0x00-0x01 = Reverb type MSB/LSB
                        # AL 0x20-0x21 = Chorus type MSB/LSB
                        # AL 0x40-0x41 = Variation type MSB/LSB
                        if al == 0x00:
                            self.xg_effects["reverb_type_msb"] = data_val
                        elif al == 0x01:
                            self.xg_effects["reverb_type_lsb"] = data_val
                        elif al == 0x20:
                            self.xg_effects["chorus_type_msb"] = data_val
                        elif al == 0x21:
                            self.xg_effects["chorus_type_lsb"] = data_val
                        elif al == 0x40:
                            self.xg_effects["variation_type_msb"] = data_val
                        elif al == 0x41:
                            self.xg_effects["variation_type_lsb"] = data_val
                    elif 0x30 <= ah <= 0x3F:  # Drum Setup (AH=0x30=setup1, 0x31=setup2)
                        # AM = note number (0x0D=13 through 0x5B=91 drum range)
                        # AL = parameter
                        setup_num = ah - 0x30
                        note_num = am
                        self.xg_drum_setup.setdefault(setup_num, {})
                        self.xg_drum_setup[setup_num].setdefault(note_num, {})
                        DRUM_PARAM_NAMES = {
                            0x00: "pitch_coarse",
                            0x01: "pitch_fine",
                            0x02: "level",
                            0x03: "alt_group",
                            0x04: "pan",
                            0x05: "reverb_send",
                            0x06: "chorus_send",
                            0x07: "variation_send",
                            0x08: "key_assign",
                            0x09: "rcv_note_off",
                            0x0A: "rcv_note_on",
                            0x0B: "filter_cutoff",
                            0x0C: "filter_resonance",
                            0x0D: "eg_attack",
                            0x0E: "eg_decay1",
                            0x0F: "eg_decay2",
                        }
                        pname = DRUM_PARAM_NAMES.get(al, f"al_0x{al:02X}")
                        self.xg_drum_setup[setup_num][note_num][pname] = data_val
                    elif ah == 0x00 and am == 0x00:  # XG System
                        # AL 0x00-0x03 = Master Tune (4 nibbles, signed)
                        # AL 0x04 = Master Volume
                        # AL 0x05 = Master Attenuator
                        # AL 0x06 = Master Transpose (signed, 0x40 = 0)
                        # AL 0x7D = Drum Setup Reset
                        # AL 0x7E = XG System On
                        # AL 0x7F = All Parameter Reset
                        if al <= 0x03:
                            self.xg_system[f"master_tune_nibble_{al}"] = data_val
                        elif al == 0x04:
                            self.xg_system["master_volume"] = data_val
                        elif al == 0x05:
                            self.xg_system["master_attenuator"] = data_val
                        elif al == 0x06:
                            self.xg_system["master_transpose"] = data_val
                        elif al == 0x7D:
                            self.xg_system["drum_setup_reset"] = data_val
                        elif al == 0x7E:
                            self.xg_system["xg_system_on"] = data_val
                        elif al == 0x7F:
                            self.xg_system["all_parameter_reset"] = data_val
                i = j + 1
            elif 0x80 <= b <= 0xEF:
                # Channel message
                status = b
                kind = status & 0xF0
                ch = status & 0x0F  # 0-15 = part 0-15
                if kind == 0xB0 and i + 2 < len(raw):  # CC
                    cc, val = raw[i+1], raw[i+2]
                    voices.setdefault(ch, {})
                    if cc == 0:
                        voices[ch]["bank_msb"] = val
                    elif cc == 32:
                        voices[ch]["bank_lsb"] = val
                    elif cc == 7:
                        voices[ch]["volume"] = val
                    elif cc == 10:
                        voices[ch]["pan"] = val
                    elif cc == 91:
                        voices[ch]["reverb"] = val
                    elif cc == 93:
                        voices[ch]["chorus"] = val
                    i += 3
                elif kind == 0xC0 and i + 1 < len(raw):  # Program Change
                    voices.setdefault(ch, {})
                    voices[ch]["program"] = raw[i+1]
                    i += 2
                elif kind in (0x80, 0x90, 0xA0, 0xE0):
                    i += 3
                elif kind in (0xD0,):
                    i += 2
                else:
                    i += 1
            else:
                i += 1

        return voices

    def _analyze(self, filepath: str) -> SyxAnalysis:
        """Perform complete analysis."""

        # Parse Model 5F messages (pattern bulk)
        self.messages = self.parser.parse_bytes(self.data)

        # Parse XG Parameter Change for voice data (Multi Part + channel events)
        # Works for .syx files that contain XG stream (pattern-load capture,
        # bulk backup with XG Multi Part dump, merged captures).
        self.xg_voices = self._parse_xg_multi_part()

        analysis = SyxAnalysis(
            filepath=filepath,
            filesize=len(self.data),
            valid=len(self.messages) > 0,
            total_messages=len(self.messages),
            bulk_dump_messages=0,
            parameter_messages=0,
            style_data_messages=0,
            valid_checksums=0,
            invalid_checksums=0,
        )

        # Analyze messages
        al_counter: Counter = Counter()
        section_data: Dict[int, bytearray] = {}
        first_7e7f_raw_payload: Optional[bytes] = None  # For tempo extraction

        for idx, msg in enumerate(self.messages):
            # Count message types
            if msg.message_type == MessageType.BULK_DUMP:
                analysis.bulk_dump_messages += 1
            elif msg.message_type == MessageType.PARAMETER_CHANGE:
                analysis.parameter_messages += 1

            if msg.is_style_data:
                analysis.style_data_messages += 1

            # Validate checksum (only bulk dumps have meaningful checksums)
            if msg.raw and msg.is_bulk_dump:
                is_valid = verify_sysex_checksum(msg.raw)
                if is_valid:
                    analysis.valid_checksums += 1
                else:
                    analysis.invalid_checksums += 1

            # Only process style data messages (AH=0x02, AM=0x7E) for
            # AL tracking, data accumulation, and tempo extraction.
            # Init/close messages (PARAMETER_CHANGE at 0x00/0x00/0x00) must
            # be excluded — they share AL=0x00 with Section 0 Track 0 and
            # would corrupt track data with spurious bytes.
            if not msg.is_style_data:
                # Still create message info for display purposes
                msg_info = MessageInfo(
                    index=idx,
                    message_type=msg.message_type.name,
                    device_number=msg.device_number,
                    address=msg.address,
                    address_hex=f"{msg.address_high:02X} {msg.address_mid:02X} {msg.address_low:02X}",
                    byte_count=len(msg.data) if msg.data else 0,
                    data_size=len(msg.data) if msg.data else 0,
                    decoded_size=len(msg.decoded_data) if msg.decoded_data else 0,
                    checksum=msg.checksum,
                    checksum_valid=msg.checksum_valid,
                    raw_size=len(msg.raw) if msg.raw else 0,
                )
                analysis.messages.append(msg_info)
                continue

            # Track AL addresses (style data only)
            al = msg.address_low
            al_counter[al] += 1

            # Capture first 7E 7F message raw payload for tempo extraction
            # The raw data (before 7-bit decode) contains tempo at bytes [2] and [3]
            if al == 0x7F and first_7e7f_raw_payload is None and msg.data:
                first_7e7f_raw_payload = bytes(msg.data)

            # Accumulate decoded data by AL (style data only)
            if msg.decoded_data:
                if al not in section_data:
                    section_data[al] = bytearray()
                section_data[al].extend(msg.decoded_data)
                analysis.total_decoded_bytes += len(msg.decoded_data)

            if msg.data:
                analysis.total_encoded_bytes += len(msg.data)

            # Create message info
            msg_info = MessageInfo(
                index=idx,
                message_type=msg.message_type.name,
                device_number=msg.device_number,
                address=msg.address,
                address_hex=f"{msg.address_high:02X} {msg.address_mid:02X} {msg.address_low:02X}",
                byte_count=len(msg.data) if msg.data else 0,
                data_size=len(msg.data) if msg.data else 0,
                decoded_size=len(msg.decoded_data) if msg.decoded_data else 0,
                checksum=msg.checksum,
                checksum_valid=msg.checksum_valid,
                raw_size=len(msg.raw) if msg.raw else 0,
            )
            analysis.messages.append(msg_info)

        # Process AL histogram
        analysis.al_addresses = sorted(al_counter.keys())
        analysis.al_histogram = dict(al_counter)

        # Process section data
        for al, data_bytes in sorted(section_data.items()):
            data = bytes(data_bytes)

            # Determine section name
            if al in self.SECTION_NAMES:
                name = self.SECTION_NAMES[al]
            elif self.TRACK_SECTION_START <= al <= self.TRACK_SECTION_END:
                section_idx = (al - self.TRACK_SECTION_START) // 8
                track_idx = (al - self.TRACK_SECTION_START) % 8
                section_names = ["Intro", "MainA", "MainB", "FillAB", "FillBA", "Ending"]
                sec_name = (
                    section_names[section_idx]
                    if section_idx < len(section_names)
                    else f"Sec{section_idx}"
                )
                name = f"{sec_name} Track {track_idx + 1}"
            else:
                name = f"Unknown 0x{al:02X}"

            # Count non-zero bytes
            non_zero = sum(1 for b in data if b != 0)

            # Create preview
            preview = " ".join(f"{b:02X}" for b in data[:32])
            if len(data) > 32:
                preview += " ..."

            section = SectionData(
                al_index=al,
                name=name,
                message_count=al_counter[al],
                total_decoded_bytes=len(data),
                decoded_data=data,
                non_zero_bytes=non_zero,
                data_preview=preview,
            )
            analysis.sections[al] = section
            analysis.section_summary.append((al, name, len(data)))

            # Special handling for header section
            if al == 0x7F:
                analysis.header_decoded = data
                analysis.pattern_name = self._extract_name(data)
                # Use new tempo extraction from raw payload if available
                if first_7e7f_raw_payload:
                    analysis.tempo = self._extract_tempo_from_raw(first_7e7f_raw_payload)
                else:
                    analysis.tempo = self._extract_tempo(data)
                analysis.time_signature = self._extract_time_signature(data)
                analysis.time_signature_raw = self._extract_time_signature_raw(data)

            # Track sections
            if self.TRACK_SECTION_START <= al <= self.TRACK_SECTION_END:
                analysis.track_sections[al] = data

        # Parse pattern directory from AH=0x05 if present
        analysis.pattern_directory = self._parse_pattern_directory()

        # Parse voice edit dumps (AH=0x00 AM=0x40 from UTILITY → BULK OUT → Voice)
        VOICE_CLASS_MAP = {
            b"\xf8\x80\x8e\x83": "Drum Standard Kit",
            b"\xf8\x80\x8f\x90": "Drum SFX Kit",
            b"\x78\x00\x07\x12": "Bass voice",
            b"\x78\x00\x0f\x10": "Chord/Melodic voice",
            b"\x78\x00\x0e\x03": "Chord variant",
        }
        for msg in self.messages:
            if msg.address_high == 0x00 and msg.address_mid == 0x40 and msg.decoded_data:
                d = msg.decoded_data
                # Find voice class signature (typically at pos 10 from earlier analysis)
                cls = None
                for sig, label in VOICE_CLASS_MAP.items():
                    if sig in d[:20]:
                        cls = label
                        break
                analysis.voice_edit_dumps.append({
                    "al_address": msg.address_low,
                    "size_bytes": len(d),
                    "voice_class": cls or "unknown",
                    "hex_preview": d[:20].hex(),
                })

        # Copy XG parser state onto analysis (so display layer can see it)
        analysis.xg_voices = dict(self.xg_voices)
        analysis.xg_effects = dict(getattr(self, "xg_effects", {}))
        analysis.xg_system = dict(getattr(self, "xg_system", {}))
        analysis.xg_drum_setup = {k: {n: dict(v) for n, v in notes.items()}
                                  for k, notes in getattr(self, "xg_drum_setup", {}).items()}

        # Apply XG Effects overrides if present (from Model 4C AH=0x02 AM=0x01)
        xg_fx = getattr(self, "xg_effects", {})
        if "reverb_type_msb" in xg_fx:
            analysis.reverb_type_msb = xg_fx["reverb_type_msb"]
            analysis.reverb_type_lsb = xg_fx.get("reverb_type_lsb", 0)
            analysis.reverb_type = get_reverb_type_name(
                analysis.reverb_type_msb, analysis.reverb_type_lsb
            )
        if "chorus_type_msb" in xg_fx:
            analysis.chorus_type_msb = xg_fx["chorus_type_msb"]
            analysis.chorus_type_lsb = xg_fx.get("chorus_type_lsb", 0)
            analysis.chorus_type = get_chorus_type_name(
                analysis.chorus_type_msb, analysis.chorus_type_lsb
            )
        if "variation_type_msb" in xg_fx:
            analysis.variation_type_msb = xg_fx["variation_type_msb"]
            analysis.variation_type_lsb = xg_fx.get("variation_type_lsb", 0)
            analysis.variation_type = get_variation_type_name(
                analysis.variation_type_msb, analysis.variation_type_lsb
            )

        # Analyze QY70-specific structures (8 tracks, 6 sections)
        self._analyze_qy70_structure(analysis)

        return analysis

    def _parse_pattern_directory(self) -> Dict[int, str]:
        """Parse AH=0x05 (Pattern Name Directory) if present in the file.

        The QY70 pattern directory is sent as RAW 7-bit-ASCII bytes (no Yamaha
        MSB packing, since every byte already has bit 7 clear for ASCII).
        Each slot is 16 bytes: 8 ASCII name + 8 metadata.

        Empty slots (8 × '*' = 0x2A) are excluded from the result.
        """
        directory: Dict[int, str] = {}
        for msg in self.messages:
            if not (msg.address_high == 0x05 and msg.data):
                continue
            # Use RAW payload bytes, not decoded_data: AH=0x05 isn't 7-bit packed.
            body = bytes(msg.data)
            for slot_idx in range(len(body) // 16):
                raw_name = body[slot_idx * 16:slot_idx * 16 + 8]
                # Filter out empty marker (8 × 0x2A = '*')
                if raw_name == b"\x2a" * 8:
                    continue
                try:
                    name = raw_name.decode("ascii", errors="replace").rstrip()
                except Exception:
                    name = raw_name.hex()
                if name and name != "*" * 8:
                    directory[slot_idx] = name
        return directory

    def _detect_format(self, analysis: SyxAnalysis) -> str:
        """
        Detect if file is Pattern or Style format.

        QY70 has two main SysEx formats:
        - Pattern: Single pattern with track data in AL 0x00-0x07
        - Style: Full style with sections, track data in AL 0x08-0x37

        Detection is based on:
        1. Header decoded byte[0] (format marker):
           - 0x2C (confirmed) = Pattern format (captured from QY70)
           - 0x5E (confirmed) = Style format (from QY70_SGT.syx)
           - Values < 0x08 are pattern, >= 0x08 are style
        2. AL address distribution in the file (fallback)

        Header structure summary (decoded, 640 bytes):
        - 0x000: Format marker (0x2C=pattern, 0x5E=style)
        - 0x001-0x005: Always 00 00 00 00 80
        - 0x006-0x009: Style-specific data (varies)
        - 0x00A-0x00B: Always 01 00
        - 0x010-0x044: Repeating 7-byte structure (section config?)
        - 0x044-0x07F: Voice/mixer data for active tracks (zeros in empty pattern)
        - 0x080-0x08D: Common prefix + timing info
        - 0x096-0x0B7: Per-track config (bank/voice/channel)
        - 0x0B8-0x0C5: Identical structure (track defaults)
        - 0x137-0x1B8: Identical 130 bytes (structural template)
        - 0x1B9-0x21B: Style-specific voice/effect data (all 0xFF in pattern)
        - 0x220-0x27F: Fill pattern data (7-bit encoded defaults)

        Returns:
            "pattern", "style", or "unknown"
        """
        al_addresses = set(analysis.al_histogram.keys())

        # Primary: check header byte[0] as format indicator (most reliable)
        # Pattern: header[0] = 0x2C (confirmed from QY70 capture)
        # Style:   header[0] = 0x5E (confirmed from SGT reference)
        # General rule: header[0] < 0x08 = pattern, >= 0x08 = style
        if analysis.header_decoded and len(analysis.header_decoded) > 0:
            header_byte = analysis.header_decoded[0]
            if header_byte < 0x08:
                return "pattern"
            else:
                return "style"

        # Fallback: check AL address distribution
        # Both patterns and styles use AL 0x00+ for track data.
        # Styles have many AL addresses (6 sections * 8 tracks = up to 48),
        # while patterns have at most 8 (single section) or just the header.
        track_als = [al for al in al_addresses if al != 0x7F and al <= 0x2F]

        if len(track_als) > 8:
            return "style"
        elif len(track_als) > 0:
            return "pattern"
        return "unknown"

    def _analyze_qy70_structure(self, analysis: SyxAnalysis) -> None:
        """Analyze QY70-specific track and section structure."""
        # Detect format first
        analysis.format_type = self._detect_format(analysis)

        # Build track info for 8 tracks
        for track_idx in range(8):
            track_name = self.TRACK_NAMES[track_idx]
            default_channel = self.DEFAULT_CHANNELS[track_idx]
            is_drum = track_idx < 2  # D1 and D2 are drum tracks

            # Find which sections have data for this track
            has_data = False
            total_bytes = 0
            active_sections: List[str] = []
            first_track_data: Optional[bytes] = None

            if analysis.format_type == "pattern":
                # Pattern format: track data is in AL 0x00-0x07
                # AL = track_idx directly (no section offset)
                # Pattern files typically have only one "section" worth of data
                al = track_idx  # AL 0x00 = track 0, AL 0x01 = track 1, etc.
                if al in analysis.sections:
                    section_data = analysis.sections[al]
                    if section_data.total_decoded_bytes > 0:
                        has_data = True
                        total_bytes += section_data.total_decoded_bytes
                        # Pattern has single section, mark as "Pattern"
                        active_sections.append("Pattern")
                        first_track_data = section_data.decoded_data
            else:
                # Style format: track data is in AL 0x00-0x2F
                # AL = section_idx * 8 + track_idx (confirmed from SGT)
                for sec_idx in range(6):
                    al = sec_idx * 8 + track_idx
                    if al in analysis.sections:
                        section_data = analysis.sections[al]
                        if section_data.total_decoded_bytes > 0:
                            has_data = True
                            total_bytes += section_data.total_decoded_bytes
                            active_sections.append(self.STYLE_SECTION_NAMES[sec_idx])
                            # Keep first track data for parameter extraction
                            if first_track_data is None:
                                first_track_data = section_data.decoded_data

            # Extract parameters from first track section data
            bank_msb, bank_lsb, program = 0, 0, 0
            volume, pan = XG_DEFAULTS["volume"], XG_DEFAULTS["pan"]
            reverb_send = XG_DEFAULTS["reverb_send"]
            chorus_send = XG_DEFAULTS["chorus_send"]
            variation_send = XG_DEFAULTS["variation_send"]
            voice_name = ""

            if first_track_data and len(first_track_data) > 24:
                # Voice encoding in track header (verified 2026-04-23 via hardware capture)
                #
                # Track header layout (24 bytes pre-preamble):
                #   B0-B13:  slot/track metadata (largely constant)
                #   B14-B16: voice variant/config (3 bytes)
                #   B17-B20: **voice class signature** (4 bytes) — THIS identifies voice type
                #   B21-B22: mix params (pan/volume flag)
                #   B23:     trailer (usually 0x00)
                #
                # Voice class signatures observed (B17-B20 hex):
                #   f8 80 8e 83 → DRUM kit
                #   78 00 07 12 → BASS voice
                #   78 00 0f 10 → CHORD/MELODIC voice (standard)
                #   78 00 0e 03 → CHORD variant (alt)
                #   0b b5 8a 7b → XG extended (non-GM, LSB-encoded)
                #
                # IMPORTANT: Bank MSB/LSB/Program are NOT directly byte-encoded in
                # the pattern bulk. Exact voice (e.g., "Drum Kit 26" vs "Standard Kit 1")
                # is only retrievable via live XG Multi Part query or capturing the
                # pattern-load PC/CC stream when QY70 switches patterns.
                #
                # See wiki/session-32f-captures.md for full voice mapping of
                # SGT/AMB01/STYLE2 patterns.

                if len(first_track_data) >= 21:
                    voice_class = first_track_data[17:21]
                else:
                    voice_class = b""

                VOICE_CLASS_SIGNATURES = {
                    b"\xf8\x80\x8e\x83": ("drum", 127, 0),
                    b"\xf8\x80\x8f\x90": ("drum-sfx", 126, 0),
                    b"\x78\x00\x07\x12": ("bass", 0, 0),
                    b"\x78\x00\x0f\x10": ("chord", 0, 0),
                    b"\x78\x00\x0e\x03": ("chord-variant", 0, 0),
                    b"\x78\x00\x07\x10": ("chord-short", 0, 0),
                }

                # Tier 1: try 10-byte signature DB lookup (unambiguous hits only)
                # The signature encodes an internal voice reference. Multiple voices
                # can share a signature (e.g. "Analog Kit" vs "Standard Kit" via
                # same drum-slot code), so trust DB only when confidence == 1.0.
                voice_sig10 = first_track_data[14:24].hex() if len(first_track_data) >= 24 else ""
                sig_db = _load_signature_db()
                sig_hit = sig_db.get(voice_sig10) if voice_sig10 else None
                sig_confident = sig_hit and sig_hit.get("confidence", 0) >= 0.99

                if sig_confident:
                    bank_msb = sig_hit.get("msb", 0)
                    bank_lsb = sig_hit.get("lsb", 0)
                    program = sig_hit.get("prog", 0)
                    if bank_msb == 127:
                        voice_name = get_drum_kit_name(program) + " (DB)"
                        if voice_name.startswith("Unknown"):
                            voice_name = f"Drum Kit {program} (DB)"
                    elif bank_msb == 126:
                        voice_name = f"SFX Kit {program} (DB)"
                    else:
                        resolved = get_voice_name(program, bank_msb, bank_lsb)
                        voice_name = f"{resolved} (DB)" if resolved else f"Voice {program}/{bank_msb}/{bank_lsb} (DB)"
                elif voice_sig10 and (
                    nn := _nearest_neighbor_voice(voice_sig10, sig_db, max_bit_dist=3)
                ):
                    # Tier 1.5: nearest-neighbour match. Empirically on the
                    # 2026-04-23 dataset, melodic signatures converge to the
                    # right voice at bit_dist ≤ 3 (MR. Vain ch14 bit_dist=1
                    # → Pad 2 warm). Drum signatures often disagree across
                    # samples so NN stays unreliable for them — we therefore
                    # keep the threshold tight and hand drum-class tracks to
                    # the class fallback below.
                    nn_hit, nn_bit_dist = nn
                    bank_msb = nn_hit.get("msb", 0)
                    bank_lsb = nn_hit.get("lsb", 0)
                    program = nn_hit.get("prog", 0)
                    if bank_msb == 127:
                        # Drum NN is noisy — punt to class fallback.
                        voice_name = ""  # force tier-2 flow below
                        bank_msb = 0
                        program = 0
                    elif bank_msb == 126:
                        voice_name = f"SFX Kit {program} (NN d={nn_bit_dist})"
                    else:
                        resolved = get_voice_name(program, bank_msb, bank_lsb)
                        voice_name = (
                            f"{resolved} (NN d={nn_bit_dist})"
                            if resolved
                            else f"Voice {program}/{bank_msb}/{bank_lsb} (NN d={nn_bit_dist})"
                        )
                if not voice_name:
                    # Tier 2: fallback to 4-byte class signature
                    if voice_class in VOICE_CLASS_SIGNATURES:
                        cls, dflt_msb, dflt_prog = VOICE_CLASS_SIGNATURES[voice_class]
                        bank_msb = dflt_msb
                        program = dflt_prog
                        if cls == "drum":
                            voice_name = get_drum_kit_name(program) + " (class)"
                        elif cls == "drum-sfx":
                            voice_name = "Drum SFX Kit (class — exact via XG query)"
                        elif cls == "bass":
                            voice_name = "Bass voice (class — exact via XG query)"
                        elif cls in ("chord", "chord-short"):
                            voice_name = "Chord/Melodic (class — exact via XG query)"
                        elif cls == "chord-variant":
                            voice_name = "Chord variant (class — exact via XG query)"
                        else:
                            voice_name = f"Class {voice_class.hex()}"
                    else:
                        # Tier 3: unknown class — XG extended / unrecognized
                        voice_name = (
                            f"Unknown (B17-B20={voice_class.hex()})"
                            if voice_class
                            else "Unknown"
                        )

                # Try to extract pan from offset 22 (based on analysis showing 0x40=64=center)
                # But for RHY1, offset 21-22 are 0x00 0x00, which means use default
                if len(first_track_data) > 22:
                    flag_byte = first_track_data[21]
                    potential_pan = first_track_data[22]
                    # If flag byte is 0x41, the pan value is valid; if 0x00, use default
                    if flag_byte == 0x41 and 0 <= potential_pan <= 127:
                        pan = potential_pan
                    # else: keep default pan (64 = center)

            # Extract note range for melody tracks (bytes 16-17)
            note_low, note_high = 0, 127
            note_range_str = ""
            if first_track_data and len(first_track_data) > 17:
                raw_low = first_track_data[16]
                raw_high = first_track_data[17]
                # For melody tracks, values are direct MIDI note numbers
                # For drum tracks, encoding is different (0x87 0xF8)
                if not is_drum and raw_low < 128 and raw_high < 128 and raw_low < raw_high:
                    note_low = raw_low
                    note_high = raw_high
                    note_range_str = f"{midi_note_to_name(note_low)}-{midi_note_to_name(note_high)}"

            # Count events and calculate data density
            event_count = 0
            track_data_density = 0.0
            if first_track_data and len(first_track_data) > 24:
                # Sequence data starts after byte 24
                seq_data = first_track_data[24:]
                if len(seq_data) > 0:
                    # Count non-zero bytes as rough event estimate
                    non_zero = sum(1 for b in seq_data if b != 0 and b != 0xFE and b != 0xF8)
                    # Rough estimate: ~4-6 bytes per MIDI event
                    event_count = non_zero // 4
                    track_data_density = (
                        (non_zero / len(seq_data) * 100) if len(seq_data) > 0 else 0
                    )

            # Override from XG Parameter Change data if available (captured from pattern load)
            # Channel = part+1 (ch9 = part 8 idx); XG voices keyed on 0-indexed part
            xg_part_idx = default_channel - 1  # ch9 → part 8
            xg_voice = getattr(self, 'xg_voices', {}).get(xg_part_idx, {})
            if xg_voice and "program" in xg_voice:
                # XG data available: override with exact values
                bank_msb = xg_voice.get("bank_msb", bank_msb)
                bank_lsb = xg_voice.get("bank_lsb", bank_lsb)
                program = xg_voice["program"]
                # Resolve exact voice name via xg_voices catalog
                if bank_msb == 127:
                    voice_name = get_drum_kit_name(program)
                    if voice_name == "Unknown" or not voice_name:
                        voice_name = f"Drum Kit {program}"
                elif bank_msb == 126:
                    # SFX bank — separate naming table than regular drums
                    voice_name = f"SFX Kit {program}"
                else:
                    voice_name = get_voice_name(program, bank_msb, bank_lsb)
                # Override mix params
                if "volume" in xg_voice:
                    volume = xg_voice["volume"]
                if "pan" in xg_voice:
                    pan = xg_voice["pan"]
                if "reverb" in xg_voice:
                    reverb_send = xg_voice["reverb"]
                if "chorus" in xg_voice:
                    chorus_send = xg_voice["chorus"]

            track_info = QY70TrackInfo(
                number=track_idx + 1,
                name=track_name,
                channel=default_channel,
                has_data=has_data,
                data_bytes=total_bytes,
                active_sections=active_sections,
                bank_msb=bank_msb,
                bank_lsb=bank_lsb,
                program=program,
                voice_name=voice_name,
                volume=volume,
                pan=pan,
                reverb_send=reverb_send,
                chorus_send=chorus_send,
                variation_send=variation_send,
                note_low=note_low,
                note_high=note_high,
                note_range_str=note_range_str,
                event_count=event_count,
                data_density=track_data_density,
                is_drum_track=is_drum,
            )
            analysis.qy70_tracks.append(track_info)

        # Build section info for 6 sections (or 1 section for Pattern format)
        if analysis.format_type == "pattern":
            # Pattern format: single section containing all track data
            # Track data is in AL 0x00-0x07 (one per track)
            track_bytes = 0
            active_tracks: List[int] = []

            for track_idx in range(8):
                al = track_idx  # AL 0x00-0x07
                if al in analysis.sections:
                    section_data = analysis.sections[al]
                    if section_data.total_decoded_bytes > 0:
                        track_bytes += section_data.total_decoded_bytes
                        active_tracks.append(track_idx + 1)

            has_data = track_bytes > 0

            # Estimate bar count from total track data
            bar_count = max(1, track_bytes // 128) if track_bytes > 0 else 0
            beat_count = bar_count * 4

            section_info = QY70SectionInfo(
                index=0,
                name="Pattern",
                has_data=has_data,
                phrase_bytes=0,
                track_bytes=track_bytes,
                active_tracks=active_tracks,
                bar_count=bar_count,
                beat_count=beat_count,
            )
            analysis.qy70_sections.append(section_info)
        else:
            # Style format: 6 sections, each with 8 tracks
            # AL = section_idx * 8 + track_idx (confirmed from SGT reference)
            # There is NO separate "phrase data" region — all AL 0x00-0x2F is track data
            for sec_idx in range(6):
                sec_name = self.STYLE_SECTION_NAMES[sec_idx]

                # Check track data for this section
                track_bytes = 0
                active_tracks: List[int] = []
                first_track_bytes = 0  # Size of first track (for bar estimation)

                for track_idx in range(8):
                    al = sec_idx * 8 + track_idx
                    if al in analysis.sections:
                        section_data = analysis.sections[al]
                        if section_data.total_decoded_bytes > 0:
                            track_bytes += section_data.total_decoded_bytes
                            active_tracks.append(track_idx + 1)
                            if first_track_bytes == 0:
                                first_track_bytes = section_data.total_decoded_bytes

                has_data = track_bytes > 0

                # Estimate bar count from first track data size
                # Track data includes 24-byte header + MIDI events
                # Rough heuristic: ~128-256 bytes per bar of track data
                bar_count = 0
                beat_count = 0
                if first_track_bytes > 24:
                    bar_count = max(1, (first_track_bytes - 24) // 96)
                    beat_count = bar_count * 4  # Assume 4/4 time

                section_info = QY70SectionInfo(
                    index=sec_idx,
                    name=sec_name,
                    has_data=has_data,
                    phrase_bytes=first_track_bytes,  # Repurpose as first track size
                    track_bytes=track_bytes,
                    active_tracks=active_tracks,
                    bar_count=bar_count,
                    beat_count=beat_count,
                )
                analysis.qy70_sections.append(section_info)

        # Calculate summary stats
        analysis.active_section_count = sum(1 for s in analysis.qy70_sections if s.has_data)
        analysis.active_track_count = sum(1 for t in analysis.qy70_tracks if t.has_data)
        analysis.data_density = (
            (analysis.total_decoded_bytes / analysis.filesize * 100)
            if analysis.filesize > 0
            else 0.0
        )

    def _extract_name(self, data: bytes) -> str:
        """
        Try to extract pattern/style name from header data.

        Note: QY70 SysEx bulk dumps do NOT contain the pattern/style name
        in a simple readable format. The first bytes of the header are
        format markers (e.g., 0x4C, 0x5E) not name characters.

        The name extraction is currently not implemented for QY70.
        Returns empty string - the caller should use the filename instead.
        """
        # Header byte 0 meanings (format markers, not name):
        # 0x03 = Pattern format
        # 0x4C = Style (pattern-like)
        # 0x5E = Style (full)
        #
        # The style name, if stored, is likely encoded within the header
        # using a complex 7-bit interleaved format that is not yet decoded.
        #
        # For now, return empty string and let the CLI use the filename.
        return ""

    def _extract_tempo(self, data: bytes) -> int:
        """
        Try to extract tempo from header data.

        Note: This method receives DECODED header data, but the tempo is encoded
        in the RAW payload bytes [2] and [3] of the first 7E 7F message.
        See _extract_tempo_from_raw() for the correct extraction.

        This method is kept for fallback/compatibility but may return incorrect values.
        """
        # Common tempo locations in decoded data (legacy approach)
        for offset in [0x0A, 0x0C, 0x10, 0x14]:
            if offset < len(data):
                val = data[offset]
                if 40 <= val <= 240:
                    return val
        return 120

    def _extract_tempo_from_raw(self, raw_payload: bytes) -> int:
        """
        Extract tempo from RAW payload of first 7E 7F message.

        QY70 tempo encoding:
          tempo_bpm = (range * 95 - 133) + offset

        Where:
          - range = raw_payload[0] (first byte of data after address)
          - offset = raw_payload[1]

        Note: The SysEx parser strips the 7E 7F sub-address bytes,
        so raw_payload starts directly with the tempo bytes.

        Examples:
          - SUMMER 155 BPM: range=0x03, offset=0x03 -> (3*95-133)+3 = 155
          - MR.VAIN 133 BPM: range=0x02, offset=0x4C -> (2*95-133)+76 = 133

        Args:
            raw_payload: Raw payload bytes from the 7E 7F message (before 7-bit decode)
                         This is msg.data, NOT including the 7E 7F sub-address bytes.

        Returns:
            Tempo in BPM, or 120 if extraction fails
        """
        if len(raw_payload) < 2:
            return 120

        tempo_range = raw_payload[0]
        tempo_offset = raw_payload[1]

        # Validate range (should be 1-4 for typical tempos 30-300 BPM)
        if tempo_range < 1 or tempo_range > 10:
            return 120

        # Calculate tempo using the formula
        tempo = (tempo_range * 95 - 133) + tempo_offset

        # Validate result is in reasonable BPM range
        if 30 <= tempo <= 300:
            return tempo

        return 120

    def _extract_time_signature(self, data: bytes) -> Tuple[int, int]:
        """
        Extract time signature from header data.

        Note: QY70 time signature encoding is not fully documented.
        We attempt to find common patterns but default to 4/4 if uncertain.
        """
        # For now, return default 4/4 as the exact encoding is unclear
        # The time signature byte location varies between pattern and style formats
        return (4, 4)

    def _extract_time_signature_raw(self, data: bytes) -> int:
        """Get raw time signature byte (for debugging)."""
        # Try to find a byte that looks like it could be time signature
        # In Mr. Vain: 0x0C = 0x1C, in SGT: different location
        if len(data) > 0x0C:
            return data[0x0C]
        return 0

    def get_section_hex_dump(self, al: int, max_bytes: int = 256) -> str:
        """Get hex dump of a specific section."""
        if al not in self.parser.messages:
            return ""

        # Find all messages for this AL and combine decoded data
        combined = bytearray()
        for msg in self.messages:
            if msg.address_low == al and msg.decoded_data:
                combined.extend(msg.decoded_data)

        if not combined:
            return ""

        data = bytes(combined[:max_bytes])
        lines = []

        for offset in range(0, len(data), 16):
            chunk = data[offset : offset + 16]
            hex_part = " ".join(f"{b:02X}" for b in chunk)
            ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            lines.append(f"{offset:04X}: {hex_part:<48}  {ascii_part}")

        if len(combined) > max_bytes:
            lines.append(f"... ({len(combined) - max_bytes} more bytes)")

        return "\n".join(lines)
