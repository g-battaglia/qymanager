"""
QY700 Q7P file analyzer.

Extracts ALL information from Q7P pattern files including:
- Header and file metadata
- Pattern configuration
- Section structure and pointers
- Track settings (channel, volume, pan, program, etc.)
- Phrase data and event information
- Raw hex dumps for unknown areas

Based on XG specification from https://www.studio4all.de/htmle/main92.html
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import struct


@dataclass
class TrackInfo:
    """Complete track information with XG parameters."""

    number: int
    name: str
    channel: int  # MIDI channel 1-16
    volume: int  # 0-127, default 100
    pan: int  # 0=Random, 1-63=L, 64=C, 65-127=R
    enabled: bool

    # Voice selection (using defaults until offset found)
    program: int = 0  # 0-127, default 0
    bank_msb: int = 0  # 0=Normal, 127=Drums
    bank_lsb: int = 0  # Voice variation
    voice_name: str = ""  # Resolved from lookup

    # Effect sends (XG defaults)
    reverb_send: int = 40  # 0-127, XG default 40
    chorus_send: int = 0  # 0-127, XG default 0
    variation_send: int = 0  # 0-127, XG default 0

    # Performance parameters
    transpose: int = 0  # -24 to +24 semitones
    velocity_offset: int = 0
    gate_time: int = 100  # Percentage
    delay: int = 0  # Timing offset


@dataclass
class SectionInfo:
    """Complete section information."""

    index: int
    name: str
    enabled: bool
    pointer: int  # Raw pointer value
    pointer_hex: str
    length_measures: int
    time_signature: Tuple[int, int]  # (numerator, denominator)
    tracks: List[TrackInfo] = field(default_factory=list)
    # Raw data
    raw_config: bytes = b""
    phrase_data_offset: int = 0
    phrase_data_size: int = 0


@dataclass
class PhraseStats:
    """Statistics for phrase/sequence data areas."""

    # Phrase area (0x360-0x677)
    phrase_total_bytes: int = 792
    phrase_non_zero_bytes: int = 0
    phrase_non_filler_bytes: int = 0  # Non 0x00/0x40/0x7F
    phrase_density: float = 0.0
    phrase_unique_values: int = 0
    phrase_value_histogram: Dict[int, int] = field(default_factory=dict)

    # Sequence area (0x678-0x86F)
    sequence_total_bytes: int = 504
    sequence_non_zero_bytes: int = 0
    sequence_non_filler_bytes: int = 0
    sequence_density: float = 0.0

    # Potential MIDI event detection
    potential_note_events: int = 0  # Bytes in note range (0x00-0x7F with patterns)
    potential_velocity_values: int = 0

    # Byte range analysis
    min_phrase_byte: int = 0
    max_phrase_byte: int = 0
    min_sequence_byte: int = 0
    max_sequence_byte: int = 0


@dataclass
class Q7PAnalysis:
    """Complete Q7P file analysis result."""

    # File info
    filepath: str
    filesize: int
    valid: bool
    format_version: str

    # Pattern info
    pattern_number: int
    pattern_name: str
    pattern_flags: int

    # Timing
    tempo: float
    tempo_raw: Tuple[int, int]  # Raw bytes
    time_signature: Tuple[int, int]
    time_signature_raw: int = 0  # Raw byte for debugging

    # Sections
    sections: List[SectionInfo] = field(default_factory=list)
    active_section_count: int = 0

    # Global track settings (shared across sections)
    global_channels: List[int] = field(default_factory=list)
    global_volumes: List[int] = field(default_factory=list)
    global_pans: List[int] = field(default_factory=list)
    global_reverb_sends: List[int] = field(default_factory=list)

    # Raw data areas
    header_raw: bytes = b""
    section_pointers_raw: bytes = b""
    section_data_raw: bytes = b""
    tempo_area_raw: bytes = b""
    channel_area_raw: bytes = b""
    track_config_raw: bytes = b""
    volume_table_raw: bytes = b""
    pan_table_raw: bytes = b""
    reverb_table_raw: bytes = b""
    phrase_area_raw: bytes = b""
    sequence_area_raw: bytes = b""
    template_area_raw: bytes = b""

    # Unknown/reserved areas for analysis
    unknown_areas: Dict[str, bytes] = field(default_factory=dict)

    # Statistics
    total_events: int = 0
    data_density: float = 0.0  # Percentage of non-zero/non-filler bytes

    # Phrase/Sequence statistics (NEW)
    phrase_stats: Optional[PhraseStats] = None


class Q7PAnalyzer:
    """
    Complete analyzer for QY700 Q7P pattern files.

    Supports two file formats:
    - 3072 bytes: Basic/template pattern (6 sections max)
    - 5120 bytes: Full pattern (12 sections max)

    Extracts every byte of information from the file structure.
    """

    # File structure offsets (common to both formats)
    HEADER_START = 0x000
    HEADER_SIZE = 16
    HEADER_MAGIC = b"YQ7PAT     V1.00"

    PATTERN_NUMBER = 0x010
    PATTERN_FLAGS = 0x011

    # Size marker area
    SIZE_MARKER = 0x030

    # Section pointers (32 bytes, 16 entries of 2 bytes each)
    SECTION_PTR_START = 0x100
    SECTION_PTR_SIZE = 32

    # Section encoded data
    SECTION_DATA_START = 0x120
    SECTION_DATA_SIZE = 96

    # Supported file sizes
    FILE_SIZE_SMALL = 3072  # Basic/template format
    FILE_SIZE_LARGE = 5120  # Full pattern format
    VALID_FILE_SIZES = (FILE_SIZE_SMALL, FILE_SIZE_LARGE)

    # Offset tables for different file sizes
    # Format: {file_size: {offset_name: offset_value}}
    OFFSETS = {
        3072: {
            "TEMPO_AREA_START": 0x180,
            "TEMPO_VALUE": 0x188,
            "TIME_SIG": 0x18A,
            "CHANNEL_START": 0x190,
            "TRACK_CONFIG_START": 0x1DC,
            "TRACK_NUMBERS": 0x1DC,
            "TRACK_FLAGS": 0x1E4,
            # Voice selection offsets (16 bytes each, may be unused in template)
            "BANK_MSB_START": 0x1E6,  # Bank MSB for 16 tracks
            "PROGRAM_START": 0x1F6,  # Program number for 16 tracks
            "BANK_LSB_START": 0x206,  # Bank LSB for 16 tracks
            "VOLUME_TABLE_START": 0x220,
            "VOLUME_DATA_START": 0x226,
            "REVERB_TABLE_START": 0x250,
            "REVERB_DATA_START": 0x256,
            "PAN_TABLE_START": 0x270,
            "PAN_DATA_START": 0x276,
            "TABLE_3_START": 0x2C0,
            "PHRASE_START": 0x360,
            "PHRASE_SIZE": 792,
            "SEQUENCE_START": 0x678,
            "SEQUENCE_SIZE": 504,
            "TEMPLATE_NAME": 0x876,
            "PATTERN_NAME": 0x876,
            "FILL_AREA_START": 0x9C0,
            "PAD_AREA_START": 0xB10,
            "MAX_SECTIONS": 6,
        },
        5120: {
            "TEMPO_AREA_START": 0xA00,
            "TEMPO_VALUE": 0xA08,
            "TIME_SIG": 0xA0A,
            "CHANNEL_START": 0xA14,
            "TRACK_CONFIG_START": 0xA5C,
            "TRACK_NUMBERS": 0xA5C,
            "TRACK_FLAGS": 0xA64,
            # Voice selection offsets (16 bytes each)
            "BANK_MSB_START": 0xA66,  # Bank MSB for 16 tracks
            "PROGRAM_START": 0xA86,  # Program number for 16 tracks
            "BANK_LSB_START": 0xA96,  # Bank LSB for 16 tracks
            "VOLUME_TABLE_START": 0xAA0,
            "VOLUME_DATA_START": 0xAA6,
            "REVERB_TABLE_START": 0xAD0,
            "REVERB_DATA_START": 0xAD6,
            "PAN_TABLE_START": 0xAF0,
            "PAN_DATA_START": 0xAF6,
            "TABLE_3_START": 0xB40,
            "PHRASE_START": 0x200,
            "PHRASE_SIZE": 2048,
            "SEQUENCE_START": 0xBE0,
            "SEQUENCE_SIZE": 800,
            "TEMPLATE_NAME": 0x10F6,
            "PATTERN_NAME": 0xA00,
            "FILL_AREA_START": 0x1240,
            "PAD_AREA_START": 0x1390,
            "MAX_SECTIONS": 12,
        },
    }

    # Section names (extended for 12 sections)
    SECTION_NAMES = [
        "Intro",
        "Main A",
        "Main B",
        "Fill AB",
        "Fill BA",
        "Ending",
        "Fill AA",
        "Fill BB",
        "Intro 2",
        "Main C",
        "Main D",
        "Ending 2",
    ]

    # QY700 has 16 tracks per pattern (TR1-TR16)
    # Track naming convention based on typical use
    TRACK_NAMES = [
        "TR1",
        "TR2",
        "TR3",
        "TR4",
        "TR5",
        "TR6",
        "TR7",
        "TR8",
        "TR9",
        "TR10",
        "TR11",
        "TR12",
        "TR13",
        "TR14",
        "TR15",
        "TR16",
    ]

    # Legacy names for backward compatibility (first 8 tracks)
    TRACK_NAMES_LEGACY = ["RHY1", "RHY2", "BASS", "CHD1", "CHD2", "CHD3", "CHD4", "CHD5"]

    # Default MIDI channels for each track type (XG convention)
    # TR1, TR2 = Channel 10 (drums), TR3 = Channel 2, TR4-16 = Channels 3-15
    DEFAULT_CHANNELS = [10, 10, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16]

    # Number of tracks
    NUM_TRACKS = 16

    # Time signature lookup table (needs hardware verification)
    # Known: 0x1C = 4/4
    TIME_SIGNATURE_MAP = {
        0x0C: (2, 4),  # Hypothesis
        0x14: (3, 4),  # Hypothesis: 0x1C - 8
        0x1C: (4, 4),  # Confirmed from T01.Q7P
        0x24: (5, 4),  # Hypothesis
        0x2C: (6, 4),  # Hypothesis
        0x1A: (3, 8),  # Hypothesis
        0x22: (6, 8),  # Hypothesis
        0x32: (12, 8),  # Hypothesis
    }

    def __init__(self):
        self.data: bytes = b""
        self.file_size: int = 0
        self._offsets: Dict[str, int] = {}

    def _init_offsets(self) -> None:
        """Initialize offset table based on file size."""
        self.file_size = len(self.data)
        if self.file_size in self.OFFSETS:
            self._offsets = self.OFFSETS[self.file_size]
        else:
            # Default to small format for unknown sizes
            self._offsets = self.OFFSETS[self.FILE_SIZE_SMALL]

    def _get_offset(self, name: str) -> int:
        """Get offset value for current file format."""
        return self._offsets.get(name, 0)

    @property
    def max_sections(self) -> int:
        """Maximum number of sections for current format."""
        return self._offsets.get("MAX_SECTIONS", 6)

    def analyze_file(self, filepath: str) -> Q7PAnalysis:
        """Analyze a Q7P file completely."""
        path = Path(filepath)

        with open(path, "rb") as f:
            self.data = f.read()

        self._init_offsets()
        return self._analyze(str(path))

    def analyze_bytes(self, data: bytes, name: str = "memory") -> Q7PAnalysis:
        """Analyze Q7P data from bytes."""
        self.data = data
        self._init_offsets()
        return self._analyze(name)

    def _analyze(self, filepath: str) -> Q7PAnalysis:
        """Perform complete analysis."""

        # Basic validation - accept both file sizes
        valid = len(self.data) in self.VALID_FILE_SIZES and self.data[:16] == self.HEADER_MAGIC

        ts_tuple, ts_raw = self._get_time_signature()

        analysis = Q7PAnalysis(
            filepath=filepath,
            filesize=len(self.data),
            valid=valid,
            format_version=self.data[:16].decode("ascii", errors="replace")
            if len(self.data) >= 16
            else "",
            pattern_number=self._get_byte(self.PATTERN_NUMBER),
            pattern_name=self._get_template_name(),
            pattern_flags=self._get_byte(self.PATTERN_FLAGS),
            tempo=self._get_tempo(),
            tempo_raw=self._get_tempo_raw(),
            time_signature=ts_tuple,
            time_signature_raw=ts_raw,
        )

        # Extract raw areas using dynamic offsets
        analysis.header_raw = self.data[self.HEADER_START : self.HEADER_START + self.HEADER_SIZE]
        analysis.section_pointers_raw = self.data[
            self.SECTION_PTR_START : self.SECTION_PTR_START + self.SECTION_PTR_SIZE
        ]
        analysis.section_data_raw = self.data[
            self.SECTION_DATA_START : self.SECTION_DATA_START + self.SECTION_DATA_SIZE
        ]

        tempo_start = self._get_offset("TEMPO_AREA_START")
        analysis.tempo_area_raw = self.data[tempo_start : tempo_start + 16]

        channel_start = self._get_offset("CHANNEL_START")
        analysis.channel_area_raw = self.data[channel_start : channel_start + 16]

        track_start = self._get_offset("TRACK_CONFIG_START")
        analysis.track_config_raw = self.data[track_start : track_start + 36]

        vol_start = self._get_offset("VOLUME_TABLE_START")
        analysis.volume_table_raw = self.data[vol_start : vol_start + 48]

        pan_start = self._get_offset("PAN_TABLE_START")
        analysis.pan_table_raw = self.data[pan_start : pan_start + 80]

        rev_start = self._get_offset("REVERB_TABLE_START")
        analysis.reverb_table_raw = self.data[rev_start : rev_start + 32]

        phrase_start = self._get_offset("PHRASE_START")
        phrase_size = self._get_offset("PHRASE_SIZE")
        analysis.phrase_area_raw = self.data[phrase_start : phrase_start + phrase_size]

        seq_start = self._get_offset("SEQUENCE_START")
        seq_size = self._get_offset("SEQUENCE_SIZE")
        analysis.sequence_area_raw = self.data[seq_start : seq_start + seq_size]

        tmpl_name = self._get_offset("TEMPLATE_NAME")
        analysis.template_area_raw = self.data[tmpl_name : tmpl_name + 128]

        # Unknown/reserved areas (simplified for dual format)
        analysis.unknown_areas = {
            "0x012-0x02F": self.data[0x012:0x030],
            "0x032-0x0FF": self.data[0x032:0x100],
        }

        # Global settings
        analysis.global_channels = self._get_channels()
        analysis.global_volumes = self._get_volumes()
        analysis.global_pans = self._get_pans()
        analysis.global_reverb_sends = self._get_reverb_sends()

        # Analyze sections (dynamic count based on format)
        analysis.sections = self._analyze_sections()
        analysis.active_section_count = sum(1 for s in analysis.sections if s.enabled)

        # Calculate data density
        analysis.data_density = self._calculate_density()

        # Analyze phrase/sequence areas
        analysis.phrase_stats = self._analyze_phrase_stats()

        return analysis

    def _get_byte(self, offset: int, default: int = 0) -> int:
        """Get single byte at offset."""
        if offset < len(self.data):
            return self.data[offset]
        return default

    def _get_word(self, offset: int) -> int:
        """Get big-endian word at offset."""
        if offset + 1 < len(self.data):
            return struct.unpack(">H", self.data[offset : offset + 2])[0]
        return 0

    def _get_template_name(self) -> str:
        """Extract template/pattern name."""
        name_offset = self._get_offset("PATTERN_NAME")
        if len(self.data) >= name_offset + 10:
            # For 5120-byte files, the pattern name is 8 chars followed by tempo
            # For 3072-byte files, it's 10 chars
            if self.file_size == self.FILE_SIZE_LARGE:
                name_bytes = self.data[name_offset : name_offset + 8]
            else:
                name_bytes = self.data[name_offset : name_offset + 10]
            try:
                # Filter out non-printable characters
                decoded = ""
                for b in name_bytes:
                    if 0x20 <= b < 0x7F:  # Printable ASCII
                        decoded += chr(b)
                    else:
                        break  # Stop at first non-printable
                return decoded.rstrip()
            except:
                return name_bytes.hex()
        return ""

    def _get_tempo(self) -> float:
        """Get tempo in BPM."""
        tempo_offset = self._get_offset("TEMPO_VALUE")
        raw = self._get_word(tempo_offset)
        if raw > 0:
            return raw / 10.0
        return 120.0

    def _get_tempo_raw(self) -> Tuple[int, int]:
        """Get raw tempo bytes."""
        tempo_offset = self._get_offset("TEMPO_VALUE")
        return (self._get_byte(tempo_offset), self._get_byte(tempo_offset + 1))

    def _get_time_signature(self) -> Tuple[Tuple[int, int], int]:
        """
        Get time signature using lookup table.

        Returns:
            Tuple of ((numerator, denominator), raw_byte)
        """
        ts_offset = self._get_offset("TIME_SIG")
        ts_byte = self._get_byte(ts_offset)

        # Use lookup table if available
        if ts_byte in self.TIME_SIGNATURE_MAP:
            return (self.TIME_SIGNATURE_MAP[ts_byte], ts_byte)

        # Fallback: try to decode (may not be accurate)
        # This is kept for unknown values, returns 4/4 as safe default
        return ((4, 4), ts_byte)

    def _get_channels(self) -> List[int]:
        """
        Get MIDI channel assignments for 16 tracks.

        Encoding (based on observation):
        - 0x00 appears on TR1/TR2 -> interpret as Channel 10 (drums)
        - 0x01-0x0F -> Channel 2-16 (value + 1)
        - Other values -> use as-is or default
        """
        channels = []
        channel_start = self._get_offset("CHANNEL_START")
        for i in range(self.NUM_TRACKS):
            ch_raw = self._get_byte(channel_start + i)

            if ch_raw == 0x00:
                # Value 0 = use default channel for this track type
                channels.append(self.DEFAULT_CHANNELS[i] if i < len(self.DEFAULT_CHANNELS) else 1)
            elif ch_raw <= 0x0F:
                # Value 1-15 = MIDI channel 2-16
                channels.append(ch_raw + 1)
            else:
                # Unknown encoding, use default
                channels.append(self.DEFAULT_CHANNELS[i] if i < len(self.DEFAULT_CHANNELS) else 1)

        return channels

    def _get_volumes(self) -> List[int]:
        """Get volume values for 16 tracks."""
        volumes = []
        vol_start = self._get_offset("VOLUME_DATA_START")
        for i in range(self.NUM_TRACKS):
            vol = self._get_byte(vol_start + i)
            volumes.append(vol if vol <= 127 else 100)
        return volumes

    def _get_pans(self) -> List[int]:
        """
        Get pan values for 16 tracks.

        XG Pan encoding:
        - 0 = Random
        - 1-63 = Left (L63-L1)
        - 64 = Center
        - 65-127 = Right (R1-R63)
        """
        pans = []
        pan_start = self._get_offset("PAN_DATA_START")
        for i in range(self.NUM_TRACKS):
            pan = self._get_byte(pan_start + i)
            pans.append(pan if pan <= 127 else 64)
        return pans

    def _get_reverb_sends(self) -> List[int]:
        """
        Get reverb send levels for 16 tracks.

        XG default reverb send = 40 (0x28)
        """
        sends = []
        rev_start = self._get_offset("REVERB_DATA_START")
        for i in range(self.NUM_TRACKS):
            send = self._get_byte(rev_start + i)
            sends.append(send if send <= 127 else 40)
        return sends

    def _get_bank_msb(self) -> List[int]:
        """
        Get Bank MSB values for 16 tracks.

        XG Bank MSB encoding:
        - 0 = Normal voice
        - 64 = SFX voice
        - 127 = Drum kit
        """
        banks = []
        msb_start = self._get_offset("BANK_MSB_START")
        for i in range(self.NUM_TRACKS):
            msb = self._get_byte(msb_start + i)
            banks.append(msb if msb <= 127 else 0)
        return banks

    def _get_bank_lsb(self) -> List[int]:
        """
        Get Bank LSB values for 16 tracks.

        Bank LSB selects voice variations within the bank.
        """
        banks = []
        lsb_start = self._get_offset("BANK_LSB_START")
        for i in range(self.NUM_TRACKS):
            lsb = self._get_byte(lsb_start + i)
            banks.append(lsb if lsb <= 127 else 0)
        return banks

    def _get_programs(self) -> List[int]:
        """
        Get Program (instrument) numbers for 16 tracks.

        Program 0-127 selects the voice within the current bank.
        """
        programs = []
        prog_start = self._get_offset("PROGRAM_START")
        for i in range(self.NUM_TRACKS):
            prog = self._get_byte(prog_start + i)
            programs.append(prog if prog <= 127 else 0)
        return programs

    def _analyze_sections(self) -> List[SectionInfo]:
        """Analyze all sections (dynamic count based on file format)."""
        sections = []

        # Use dynamic max sections based on file format
        max_sections = self.max_sections
        phrase_start = self._get_offset("PHRASE_START")

        for idx in range(max_sections):
            ptr_offset = self.SECTION_PTR_START + (idx * 2)
            ptr_bytes = self.data[ptr_offset : ptr_offset + 2]
            ptr_value = self._get_word(ptr_offset)

            # Check if section is empty (0xFEFE)
            enabled = ptr_bytes != b"\xfe\xfe"

            # Get section config data
            config_offset = self.SECTION_DATA_START + (idx * 16)
            config_data = (
                self.data[config_offset : config_offset + 16]
                if config_offset + 16 <= len(self.data)
                else b""
            )

            section = SectionInfo(
                index=idx,
                name=self.SECTION_NAMES[idx] if idx < len(self.SECTION_NAMES) else f"Section {idx}",
                enabled=enabled,
                pointer=ptr_value,
                pointer_hex=ptr_bytes.hex(),
                length_measures=4,  # Default, actual parsing needed
                time_signature=(4, 4),
                raw_config=config_data,
                phrase_data_offset=phrase_start + (idx * 80),
                phrase_data_size=80,
            )

            # Add track info for this section
            section.tracks = self._analyze_section_tracks(idx)

            sections.append(section)

        return sections

    def _analyze_section_tracks(self, section_idx: int) -> List[TrackInfo]:
        """Analyze 16 tracks for a section."""
        from qyconv.utils.xg_voices import get_voice_name

        tracks = []

        channels = self._get_channels()
        volumes = self._get_volumes()
        pans = self._get_pans()
        reverb_sends = self._get_reverb_sends()
        bank_msbs = self._get_bank_msb()
        bank_lsbs = self._get_bank_lsb()
        programs = self._get_programs()

        # Track flags (16-bit for 16 tracks)
        track_flags_offset = self._get_offset("TRACK_FLAGS")
        track_flags = self._get_word(track_flags_offset)

        for i in range(self.NUM_TRACKS):
            # Check if track is enabled via flags
            enabled = bool(track_flags & (1 << i))

            channel = (
                channels[i]
                if i < len(channels)
                else self.DEFAULT_CHANNELS[i % len(self.DEFAULT_CHANNELS)]
            )
            bank_msb = bank_msbs[i] if i < len(bank_msbs) else 0
            bank_lsb = bank_lsbs[i] if i < len(bank_lsbs) else 0
            program = programs[i] if i < len(programs) else 0

            # Resolve voice name using the XG lookup
            voice_name = get_voice_name(program, bank_msb, bank_lsb, channel)

            track = TrackInfo(
                number=i + 1,
                name=self.TRACK_NAMES[i] if i < len(self.TRACK_NAMES) else f"TR{i + 1}",
                channel=channel,
                volume=volumes[i] if i < len(volumes) else 100,
                pan=pans[i] if i < len(pans) else 64,
                enabled=enabled,
                program=program,
                bank_msb=bank_msb,
                bank_lsb=bank_lsb,
                voice_name=voice_name,
                reverb_send=reverb_sends[i] if i < len(reverb_sends) else 40,
                chorus_send=0,  # XG default
                variation_send=0,  # XG default
            )
            tracks.append(track)

        return tracks

    def _calculate_density(self) -> float:
        """Calculate percentage of meaningful data (non-zero, non-filler)."""
        if not self.data:
            return 0.0

        meaningful = 0
        for byte in self.data:
            if byte not in (0x00, 0xFE, 0xF8, 0x40, 0x20):
                meaningful += 1

        return (meaningful / len(self.data)) * 100

    def _analyze_phrase_stats(self) -> PhraseStats:
        """
        Analyze phrase and sequence data areas.

        Dynamically uses offsets based on file format.

        Returns:
            PhraseStats with comprehensive analysis of both areas
        """
        # Extract data areas using dynamic offsets
        phrase_start = self._get_offset("PHRASE_START")
        phrase_size = self._get_offset("PHRASE_SIZE")
        seq_start = self._get_offset("SEQUENCE_START")
        seq_size = self._get_offset("SEQUENCE_SIZE")

        phrase_data = self.data[phrase_start : phrase_start + phrase_size]
        seq_data = self.data[seq_start : seq_start + seq_size]

        # Filler bytes to ignore (common padding values)
        filler_bytes = {0x00, 0x40, 0x7F, 0xFE, 0xF8, 0x20}

        # Analyze phrase area
        phrase_non_zero = sum(1 for b in phrase_data if b != 0x00)
        phrase_non_filler = sum(1 for b in phrase_data if b not in filler_bytes)
        phrase_histogram: Dict[int, int] = {}
        for b in phrase_data:
            phrase_histogram[b] = phrase_histogram.get(b, 0) + 1

        # Analyze sequence area
        seq_non_zero = sum(1 for b in seq_data if b != 0x00)
        seq_non_filler = sum(1 for b in seq_data if b not in filler_bytes)

        # Detect potential MIDI events
        # Note events typically have values 0x00-0x7F (0-127)
        # Velocity values are also 0x01-0x7F (1-127)
        potential_notes = 0
        potential_velocities = 0
        for i, b in enumerate(seq_data):
            if 0x24 <= b <= 0x60:  # Common drum/note range (C1 to C4)
                potential_notes += 1
            if 0x40 <= b <= 0x7F:  # Common velocity range
                potential_velocities += 1

        # Calculate density
        phrase_density = (phrase_non_filler / phrase_size * 100) if phrase_size > 0 else 0.0
        seq_density = (seq_non_filler / seq_size * 100) if seq_size > 0 else 0.0

        # Get byte ranges (excluding 0x00 for min)
        non_zero_phrase = [b for b in phrase_data if b != 0x00]
        non_zero_seq = [b for b in seq_data if b != 0x00]

        return PhraseStats(
            phrase_total_bytes=phrase_size,
            phrase_non_zero_bytes=phrase_non_zero,
            phrase_non_filler_bytes=phrase_non_filler,
            phrase_density=phrase_density,
            phrase_unique_values=len(phrase_histogram),
            phrase_value_histogram=phrase_histogram,
            sequence_total_bytes=seq_size,
            sequence_non_zero_bytes=seq_non_zero,
            sequence_non_filler_bytes=seq_non_filler,
            sequence_density=seq_density,
            potential_note_events=potential_notes,
            potential_velocity_values=potential_velocities,
            min_phrase_byte=min(non_zero_phrase) if non_zero_phrase else 0,
            max_phrase_byte=max(non_zero_phrase) if non_zero_phrase else 0,
            min_sequence_byte=min(non_zero_seq) if non_zero_seq else 0,
            max_sequence_byte=max(non_zero_seq) if non_zero_seq else 0,
        )

    def get_hex_dump(self, start: int, size: int, bytes_per_line: int = 16) -> str:
        """Get formatted hex dump of an area."""
        lines = []
        end = min(start + size, len(self.data))

        for offset in range(start, end, bytes_per_line):
            chunk = self.data[offset : offset + bytes_per_line]
            hex_part = " ".join(f"{b:02X}" for b in chunk)
            ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            lines.append(f"{offset:04X}: {hex_part:<{bytes_per_line * 3}}  {ascii_part}")

        return "\n".join(lines)
