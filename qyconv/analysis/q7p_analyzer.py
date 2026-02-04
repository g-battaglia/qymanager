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

    Extracts every byte of information from the file structure.
    """

    # File structure offsets
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

    # Tempo and timing
    TEMPO_AREA_START = 0x180
    TEMPO_AREA_SIZE = 16
    TEMPO_VALUE = 0x188
    TIME_SIG = 0x18A

    # Channel configuration
    CHANNEL_START = 0x190
    CHANNEL_SIZE = 16

    # Reserved area
    RESERVED_1_START = 0x1A0
    RESERVED_1_SIZE = 60  # 0x1A0 - 0x1DB

    # Track configuration
    TRACK_CONFIG_START = 0x1DC
    TRACK_NUMBERS = 0x1DC  # 8 bytes
    TRACK_FLAGS = 0x1E4  # 2 bytes
    TRACK_CONFIG_SIZE = 36  # 0x1DC - 0x1FF

    # Reserved area
    RESERVED_2_START = 0x200
    RESERVED_2_SIZE = 32  # 0x200 - 0x21F

    # Volume table (with 6-byte header)
    VOLUME_TABLE_START = 0x220
    VOLUME_DATA_START = 0x226  # Actual volume data starts here
    VOLUME_TABLE_SIZE = 80  # 0x220 - 0x26F

    # Reverb Send table (discovered from XG default 0x28)
    REVERB_TABLE_START = 0x250
    REVERB_DATA_START = 0x256  # Actual reverb data starts here
    REVERB_TABLE_SIZE = 32

    # Pan table (with 6-byte header) - FIXED offset
    PAN_TABLE_START = 0x270
    PAN_DATA_START = 0x276  # Actual pan data starts here (was incorrectly 0x270)
    PAN_TABLE_SIZE = 80  # 0x270 - 0x2BF

    # Additional tables (unknown purpose)
    TABLE_3_START = 0x2C0
    TABLE_3_SIZE = 160  # 0x2C0 - 0x35F

    # Phrase data area
    PHRASE_START = 0x360
    PHRASE_SIZE = 792  # 0x360 - 0x677

    # Sequence/event data
    SEQUENCE_START = 0x678
    SEQUENCE_SIZE = 504  # 0x678 - 0x86F

    # Template info
    TEMPLATE_START = 0x870
    TEMPLATE_PADDING = 0x870  # 6 bytes
    TEMPLATE_NAME = 0x876  # 10 bytes
    TEMPLATE_SIZE = 144  # 0x870 - 0x8FF

    # Pattern mapping area
    PATTERN_MAP_START = 0x900
    PATTERN_MAP_SIZE = 192  # 0x900 - 0x9BF

    # Fill area (0xFE)
    FILL_AREA_START = 0x9C0
    FILL_AREA_SIZE = 336  # 0x9C0 - 0xB0F

    # Padding area (0xF8)
    PAD_AREA_START = 0xB10
    PAD_AREA_SIZE = 240  # 0xB10 - 0xBFF

    FILE_SIZE = 3072

    SECTION_NAMES = [
        "Intro",
        "Main A",
        "Main B",
        "Fill AB",
        "Fill BA",
        "Ending",
        "Main C",
        "Main D",
        "Intro 2",
        "Ending 2",
        "Break",
    ]

    TRACK_NAMES = ["RHY1", "RHY2", "BASS", "CHD1", "CHD2", "CHD3", "CHD4", "CHD5"]

    # Default MIDI channels for each track type (XG convention)
    # RHY1, RHY2 = Channel 10 (drums)
    # BASS = Channel 2, CHD1-5 = Channels 3-7
    DEFAULT_CHANNELS = [10, 10, 2, 3, 4, 5, 6, 7]

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

    def analyze_file(self, filepath: str) -> Q7PAnalysis:
        """Analyze a Q7P file completely."""
        path = Path(filepath)

        with open(path, "rb") as f:
            self.data = f.read()

        return self._analyze(str(path))

    def analyze_bytes(self, data: bytes, name: str = "memory") -> Q7PAnalysis:
        """Analyze Q7P data from bytes."""
        self.data = data
        return self._analyze(name)

    def _analyze(self, filepath: str) -> Q7PAnalysis:
        """Perform complete analysis."""

        # Basic validation
        valid = len(self.data) == self.FILE_SIZE and self.data[:16] == self.HEADER_MAGIC

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

        # Extract raw areas
        analysis.header_raw = self.data[self.HEADER_START : self.HEADER_START + self.HEADER_SIZE]
        analysis.section_pointers_raw = self.data[
            self.SECTION_PTR_START : self.SECTION_PTR_START + self.SECTION_PTR_SIZE
        ]
        analysis.section_data_raw = self.data[
            self.SECTION_DATA_START : self.SECTION_DATA_START + self.SECTION_DATA_SIZE
        ]
        analysis.tempo_area_raw = self.data[
            self.TEMPO_AREA_START : self.TEMPO_AREA_START + self.TEMPO_AREA_SIZE
        ]
        analysis.channel_area_raw = self.data[
            self.CHANNEL_START : self.CHANNEL_START + self.CHANNEL_SIZE
        ]
        analysis.track_config_raw = self.data[
            self.TRACK_CONFIG_START : self.TRACK_CONFIG_START + self.TRACK_CONFIG_SIZE
        ]
        analysis.volume_table_raw = self.data[
            self.VOLUME_TABLE_START : self.VOLUME_TABLE_START + self.VOLUME_TABLE_SIZE
        ]
        analysis.pan_table_raw = self.data[
            self.PAN_TABLE_START : self.PAN_TABLE_START + self.PAN_TABLE_SIZE
        ]
        analysis.reverb_table_raw = self.data[
            self.REVERB_TABLE_START : self.REVERB_TABLE_START + self.REVERB_TABLE_SIZE
        ]
        analysis.phrase_area_raw = self.data[
            self.PHRASE_START : self.PHRASE_START + self.PHRASE_SIZE
        ]
        analysis.sequence_area_raw = self.data[
            self.SEQUENCE_START : self.SEQUENCE_START + self.SEQUENCE_SIZE
        ]
        analysis.template_area_raw = self.data[
            self.TEMPLATE_START : self.TEMPLATE_START + self.TEMPLATE_SIZE
        ]

        # Unknown/reserved areas
        analysis.unknown_areas = {
            "0x012-0x02F": self.data[0x012:0x030],
            "0x032-0x0FF": self.data[0x032:0x100],
            "0x1A0-0x1DB": self.data[
                self.RESERVED_1_START : self.RESERVED_1_START + self.RESERVED_1_SIZE
            ],
            "0x1E6-0x1FF": self.data[0x1E6:0x200],
            "0x200-0x21F": self.data[
                self.RESERVED_2_START : self.RESERVED_2_START + self.RESERVED_2_SIZE
            ],
            "0x2C0-0x35F": self.data[self.TABLE_3_START : self.TABLE_3_START + self.TABLE_3_SIZE],
            "0x880-0x8FF": self.data[0x880:0x900],
            "0x900-0x9BF": self.data[
                self.PATTERN_MAP_START : self.PATTERN_MAP_START + self.PATTERN_MAP_SIZE
            ],
        }

        # Global settings
        analysis.global_channels = self._get_channels()
        analysis.global_volumes = self._get_volumes()
        analysis.global_pans = self._get_pans()
        analysis.global_reverb_sends = self._get_reverb_sends()

        # Analyze sections
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
        if len(self.data) >= self.TEMPLATE_NAME + 10:
            name_bytes = self.data[self.TEMPLATE_NAME : self.TEMPLATE_NAME + 10]
            try:
                return name_bytes.decode("ascii").rstrip("\x00 ")
            except:
                return name_bytes.hex()
        return ""

    def _get_tempo(self) -> float:
        """Get tempo in BPM."""
        raw = self._get_word(self.TEMPO_VALUE)
        if raw > 0:
            return raw / 10.0
        return 120.0

    def _get_tempo_raw(self) -> Tuple[int, int]:
        """Get raw tempo bytes."""
        return (self._get_byte(self.TEMPO_VALUE), self._get_byte(self.TEMPO_VALUE + 1))

    def _get_time_signature(self) -> Tuple[Tuple[int, int], int]:
        """
        Get time signature using lookup table.

        Returns:
            Tuple of ((numerator, denominator), raw_byte)
        """
        ts_byte = self._get_byte(self.TIME_SIG)

        # Use lookup table if available
        if ts_byte in self.TIME_SIGNATURE_MAP:
            return (self.TIME_SIGNATURE_MAP[ts_byte], ts_byte)

        # Fallback: try to decode (may not be accurate)
        # This is kept for unknown values, returns 4/4 as safe default
        return ((4, 4), ts_byte)

    def _get_channels(self) -> List[int]:
        """
        Get MIDI channel assignments for 8 tracks.

        Encoding (based on observation):
        - 0x00 appears on RHY1/RHY2 -> interpret as Channel 10 (drums)
        - 0x01-0x0F -> Channel 2-16 (value + 1)
        - Other values -> use as-is or default
        """
        channels = []
        for i in range(8):
            ch_raw = self._get_byte(self.CHANNEL_START + i)

            if ch_raw == 0x00:
                # Value 0 = use default channel for this track type
                channels.append(self.DEFAULT_CHANNELS[i])
            elif ch_raw <= 0x0F:
                # Value 1-15 = MIDI channel 2-16
                channels.append(ch_raw + 1)
            else:
                # Unknown encoding, use default
                channels.append(self.DEFAULT_CHANNELS[i])

        return channels

    def _get_volumes(self) -> List[int]:
        """Get volume values for 8 tracks."""
        volumes = []
        # Skip first 6 bytes which are header
        for i in range(8):
            vol = self._get_byte(self.VOLUME_DATA_START + i)
            volumes.append(vol if vol <= 127 else 100)
        return volumes

    def _get_pans(self) -> List[int]:
        """
        Get pan values for 8 tracks.

        XG Pan encoding:
        - 0 = Random
        - 1-63 = Left (L63-L1)
        - 64 = Center
        - 65-127 = Right (R1-R63)

        FIXED: Now reading from correct offset 0x276 (was 0x270)
        """
        pans = []
        for i in range(8):
            pan = self._get_byte(self.PAN_DATA_START + i)
            pans.append(pan if pan <= 127 else 64)
        return pans

    def _get_reverb_sends(self) -> List[int]:
        """
        Get reverb send levels for 8 tracks.

        XG default reverb send = 40 (0x28)
        Found at offset 0x256
        """
        sends = []
        for i in range(8):
            send = self._get_byte(self.REVERB_DATA_START + i)
            sends.append(send if send <= 127 else 40)
        return sends

    def _analyze_sections(self) -> List[SectionInfo]:
        """Analyze all sections."""
        sections = []

        for idx in range(6):  # QY700 has 6 main sections like QY70
            ptr_offset = self.SECTION_PTR_START + (idx * 2)
            ptr_bytes = self.data[ptr_offset : ptr_offset + 2]
            ptr_value = self._get_word(ptr_offset)

            # Check if section is empty (0xFEFE)
            enabled = ptr_bytes != b"\xfe\xfe"

            # Get section config data
            config_offset = self.SECTION_DATA_START + (idx * 16)
            config_data = self.data[config_offset : config_offset + 16]

            section = SectionInfo(
                index=idx,
                name=self.SECTION_NAMES[idx] if idx < len(self.SECTION_NAMES) else f"Section {idx}",
                enabled=enabled,
                pointer=ptr_value,
                pointer_hex=ptr_bytes.hex(),
                length_measures=4,  # Default, actual parsing needed
                time_signature=(4, 4),
                raw_config=config_data,
                phrase_data_offset=self.PHRASE_START + (idx * 80),
                phrase_data_size=80,
            )

            # Add track info for this section
            section.tracks = self._analyze_section_tracks(idx)

            sections.append(section)

        return sections

    def _analyze_section_tracks(self, section_idx: int) -> List[TrackInfo]:
        """Analyze tracks for a section."""
        tracks = []

        channels = self._get_channels()
        volumes = self._get_volumes()
        pans = self._get_pans()
        reverb_sends = self._get_reverb_sends()

        # Track flags at 0x1E4-0x1E5
        track_flags = self._get_word(self.TRACK_FLAGS)

        for i in range(8):
            # Check if track is enabled via flags
            enabled = bool(track_flags & (1 << i))

            # Determine if this is a drum track (RHY1/RHY2)
            is_drum = i < 2  # First two tracks are rhythm

            # Set default bank based on track type
            bank_msb = 127 if is_drum else 0  # 127 = drum kit, 0 = normal

            track = TrackInfo(
                number=i + 1,
                name=self.TRACK_NAMES[i] if i < len(self.TRACK_NAMES) else f"TRK{i + 1}",
                channel=channels[i] if i < len(channels) else self.DEFAULT_CHANNELS[i],
                volume=volumes[i] if i < len(volumes) else 100,
                pan=pans[i] if i < len(pans) else 64,
                enabled=enabled,
                program=0,  # Default, offset not yet found
                bank_msb=bank_msb,
                bank_lsb=0,
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

        Phrase area (0x360-0x677): 792 bytes - contains phrase/pattern data
        Sequence area (0x678-0x86F): 504 bytes - contains event/timing data

        Returns:
            PhraseStats with comprehensive analysis of both areas
        """
        # Extract data areas
        phrase_data = self.data[self.PHRASE_START : self.PHRASE_START + self.PHRASE_SIZE]
        seq_data = self.data[self.SEQUENCE_START : self.SEQUENCE_START + self.SEQUENCE_SIZE]

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
        phrase_density = (
            (phrase_non_filler / self.PHRASE_SIZE * 100) if self.PHRASE_SIZE > 0 else 0.0
        )
        seq_density = (seq_non_filler / self.SEQUENCE_SIZE * 100) if self.SEQUENCE_SIZE > 0 else 0.0

        # Get byte ranges (excluding 0x00 for min)
        non_zero_phrase = [b for b in phrase_data if b != 0x00]
        non_zero_seq = [b for b in seq_data if b != 0x00]

        return PhraseStats(
            phrase_total_bytes=self.PHRASE_SIZE,
            phrase_non_zero_bytes=phrase_non_zero,
            phrase_non_filler_bytes=phrase_non_filler,
            phrase_density=phrase_density,
            phrase_unique_values=len(phrase_histogram),
            phrase_value_histogram=phrase_histogram,
            sequence_total_bytes=self.SEQUENCE_SIZE,
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
