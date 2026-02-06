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

    # Default MIDI channels for QY70 tracks
    # D1=10, D2=10, PC=3, BA=2, C1=4, C2=5, C3=6, C4=7
    DEFAULT_CHANNELS = [10, 10, 3, 2, 4, 5, 6, 7]

    # Section names (6 sections: Intro, MainA, MainB, FillAB, FillBA, Ending)
    STYLE_SECTION_NAMES = ["Intro", "Main A", "Main B", "Fill AB", "Fill BA", "Ending"]

    # Section names by AL index
    SECTION_NAMES = {
        0x00: "Intro Phrases",
        0x01: "Main A Phrases",
        0x02: "Main B Phrases",
        0x03: "Fill AB Phrases",
        0x04: "Fill BA Phrases",
        0x05: "Ending Phrases",
        0x06: "Section 6",
        0x07: "Section 7",
        0x7F: "Style Header/Config",
    }

    # Track section range
    TRACK_SECTION_START = 0x08
    TRACK_SECTION_END = 0x37  # 0x08 + (6 sections * 8 tracks) - 1

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

    def _analyze(self, filepath: str) -> SyxAnalysis:
        """Perform complete analysis."""

        # Parse messages
        self.messages = self.parser.parse_bytes(self.data)

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

            # Validate checksum
            if msg.raw:
                is_valid = verify_sysex_checksum(msg.raw)
                if is_valid:
                    analysis.valid_checksums += 1
                else:
                    analysis.invalid_checksums += 1

            # Track AL addresses
            al = msg.address_low
            al_counter[al] += 1

            # Capture first 7E 7F message raw payload for tempo extraction
            # The raw data (before 7-bit decode) contains tempo at bytes [2] and [3]
            if al == 0x7F and first_7e7f_raw_payload is None and msg.data:
                first_7e7f_raw_payload = bytes(msg.data)

            # Accumulate decoded data by AL
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

        # Analyze QY70-specific structures (8 tracks, 6 sections)
        self._analyze_qy70_structure(analysis)

        return analysis

    def _detect_format(self, analysis: SyxAnalysis) -> str:
        """
        Detect if file is Pattern or Style format.

        QY70 has two main SysEx formats:
        - Pattern: Single pattern with track data in AL 0x00-0x07
        - Style: Full style with sections, track data in AL 0x08-0x37

        Detection is based on:
        1. Header byte[0] value (Pattern < 0x08, Style >= 0x08)
        2. AL address distribution in the file

        Returns:
            "pattern", "style", or "unknown"
        """
        al_addresses = set(analysis.al_histogram.keys())

        # Check header byte[0] as format indicator
        # Pattern files have header[0] < 0x08 (e.g., 0x03)
        # Style files have header[0] >= 0x08 (e.g., 0x4C, 0x5E)
        if analysis.header_decoded and len(analysis.header_decoded) > 0:
            header_byte = analysis.header_decoded[0]
            if header_byte < 0x08:
                return "pattern"

        # Fallback: check AL address distribution
        has_phrase_data = any(al < 8 and al != 0x7F for al in al_addresses)
        has_track_data = any(8 <= al <= 0x37 for al in al_addresses)

        if has_track_data:
            return "style"
        elif has_phrase_data:
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
                # Style format: track data is in AL 0x08-0x37
                # AL = 0x08 + (section * 8) + track
                for sec_idx in range(6):
                    al = self.TRACK_SECTION_START + (sec_idx * 8) + track_idx
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
                # Extract from track header (bytes after common 12-byte prefix)
                # Based on analysis: offset 14-15 = bank/program for melody tracks
                #
                # Pattern at offset 14-15:
                # - 0x40 0x80 = "QY70 default" encoding (use track-type default voice)
                # - Otherwise = Bank MSB, Program number
                #
                # QY70 track-type default voices:
                # - RHY1/RHY2 (drum, channel 10): Standard Kit
                # - BASS (channel 2): Acoustic Bass (program 32)
                # - CHD1/CHD2 (chord): Piano (program 0)
                # - PAD: Pad (program 88)
                # - PHR1/PHR2: Piano (program 0)

                is_default_encoding = (
                    len(first_track_data) > 15
                    and first_track_data[14] == 0x40
                    and first_track_data[15] == 0x80
                )

                if is_default_encoding:
                    # Use QY70 track-type defaults based on track name
                    if is_drum:
                        # D1, D2 = Drums
                        bank_msb = 127
                        program = 0
                        voice_name = get_drum_kit_name(program)
                    elif track_name == "BA":
                        # BA = Acoustic Bass
                        bank_msb = 0
                        program = 32  # Acoustic Bass
                        voice_name = get_voice_name(program, bank_msb, bank_lsb)
                    elif track_name == "PC":
                        # PC = Percussion/Chord - use Piano as default
                        bank_msb = 0
                        program = 0
                        voice_name = get_voice_name(program, bank_msb, bank_lsb)
                    else:
                        # C1-C4 = Chord tracks = Piano
                        bank_msb = 0
                        program = 0
                        voice_name = get_voice_name(program, bank_msb, bank_lsb)
                else:
                    # Explicit bank/program encoding
                    raw_bank = first_track_data[14]
                    raw_program = first_track_data[15]
                    # Valid MIDI values are 0-127
                    if raw_bank < 128 and raw_program < 128:
                        bank_msb = raw_bank
                        program = raw_program
                    # Get voice name (correct parameter order: program, bank_msb, bank_lsb, channel)
                    voice_name = get_voice_name(program, bank_msb, bank_lsb)

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
            # Style format: 6 sections with separate phrase and track data
            for sec_idx in range(6):
                sec_name = self.STYLE_SECTION_NAMES[sec_idx]

                # Check phrase data (AL 0x00-0x05)
                phrase_bytes = 0
                phrase_data: Optional[bytes] = None
                if sec_idx in analysis.sections:
                    phrase_bytes = analysis.sections[sec_idx].total_decoded_bytes
                    phrase_data = analysis.sections[sec_idx].decoded_data

                # Check track data for this section
                track_bytes = 0
                active_tracks: List[int] = []

                for track_idx in range(8):
                    al = self.TRACK_SECTION_START + (sec_idx * 8) + track_idx
                    if al in analysis.sections:
                        section_data = analysis.sections[al]
                        if section_data.total_decoded_bytes > 0:
                            track_bytes += section_data.total_decoded_bytes
                            active_tracks.append(track_idx + 1)

                has_data = phrase_bytes > 0 or track_bytes > 0

                # Try to estimate bar count from phrase data size
                # Rough heuristic: QY70 uses ~32-64 bytes per bar for phrase data
                bar_count = 0
                beat_count = 0
                if phrase_bytes > 0:
                    # Estimate based on data size - more data = more bars
                    # This is a rough approximation
                    bar_count = max(1, phrase_bytes // 32)
                    beat_count = bar_count * 4  # Assume 4/4 time

                section_info = QY70SectionInfo(
                    index=sec_idx,
                    name=sec_name,
                    has_data=has_data,
                    phrase_bytes=phrase_bytes,
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
        """Try to extract pattern name from header data."""
        if len(data) < 10:
            return ""

        # Try first 10 bytes as name
        name_bytes = []
        for b in data[:10]:
            if 32 <= b <= 126:
                name_bytes.append(chr(b))
            else:
                break

        return "".join(name_bytes).strip()

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
