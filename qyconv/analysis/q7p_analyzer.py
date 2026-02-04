"""
QY700 Q7P file analyzer.

Extracts ALL information from Q7P pattern files including:
- Header and file metadata
- Pattern configuration
- Section structure and pointers
- Track settings (channel, volume, pan, program, etc.)
- Phrase data and event information
- Raw hex dumps for unknown areas
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import struct


@dataclass
class TrackInfo:
    """Complete track information."""

    number: int
    name: str
    channel: int
    volume: int
    pan: int  # 0-127, 64=center
    program: int
    bank_msb: int
    bank_lsb: int
    enabled: bool
    # Additional settings
    transpose: int = 0
    velocity_offset: int = 0
    gate_time: int = 100
    delay: int = 0


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

    # Sections
    sections: List[SectionInfo] = field(default_factory=list)
    active_section_count: int = 0

    # Global track settings (shared across sections)
    global_channels: List[int] = field(default_factory=list)
    global_volumes: List[int] = field(default_factory=list)
    global_pans: List[int] = field(default_factory=list)

    # Raw data areas
    header_raw: bytes = b""
    section_pointers_raw: bytes = b""
    section_data_raw: bytes = b""
    tempo_area_raw: bytes = b""
    channel_area_raw: bytes = b""
    track_config_raw: bytes = b""
    volume_table_raw: bytes = b""
    pan_table_raw: bytes = b""
    phrase_area_raw: bytes = b""
    sequence_area_raw: bytes = b""
    template_area_raw: bytes = b""

    # Unknown/reserved areas for analysis
    unknown_areas: Dict[str, bytes] = field(default_factory=dict)

    # Statistics
    total_events: int = 0
    data_density: float = 0.0  # Percentage of non-zero/non-filler bytes


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

    # Volume table
    VOLUME_TABLE_START = 0x220
    VOLUME_TABLE_SIZE = 80  # 0x220 - 0x26F

    # Pan table
    PAN_TABLE_START = 0x270
    PAN_TABLE_SIZE = 80  # 0x270 - 0x2BF

    # Additional tables
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
            time_signature=self._get_time_signature(),
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

        # Analyze sections
        analysis.sections = self._analyze_sections()
        analysis.active_section_count = sum(1 for s in analysis.sections if s.enabled)

        # Calculate data density
        analysis.data_density = self._calculate_density()

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

    def _get_time_signature(self) -> Tuple[int, int]:
        """Get time signature."""
        # Time signature encoding needs verification
        ts_byte = self._get_byte(self.TIME_SIG)
        numerator = ((ts_byte >> 4) & 0x0F) or 4
        denominator = (1 << (ts_byte & 0x0F)) if (ts_byte & 0x0F) else 4
        return (numerator, denominator)

    def _get_channels(self) -> List[int]:
        """Get MIDI channel assignments for 8 tracks."""
        channels = []
        for i in range(8):
            ch = self._get_byte(self.CHANNEL_START + i)
            # Channel encoding: value 0x03 seems common
            channels.append(ch)
        return channels

    def _get_volumes(self) -> List[int]:
        """Get volume values for 8 tracks."""
        volumes = []
        # Skip first 6 bytes which seem to be header
        base = self.VOLUME_TABLE_START + 6
        for i in range(8):
            vol = self._get_byte(base + i)
            volumes.append(vol if vol <= 127 else 100)
        return volumes

    def _get_pans(self) -> List[int]:
        """Get pan values for 8 tracks."""
        pans = []
        for i in range(8):
            pan = self._get_byte(self.PAN_TABLE_START + i)
            pans.append(pan if pan <= 127 else 64)
        return pans

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

        # Track flags at 0x1E4-0x1E5
        track_flags = self._get_word(self.TRACK_FLAGS)

        for i in range(8):
            # Check if track is enabled via flags
            enabled = bool(track_flags & (1 << i))

            track = TrackInfo(
                number=i + 1,
                name=self.TRACK_NAMES[i] if i < len(self.TRACK_NAMES) else f"TRK{i + 1}",
                channel=channels[i] if i < len(channels) else i + 1,
                volume=volumes[i] if i < len(volumes) else 100,
                pan=pans[i] if i < len(pans) else 64,
                program=0,  # Need to find program location
                bank_msb=0,
                bank_lsb=0,
                enabled=enabled,
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
