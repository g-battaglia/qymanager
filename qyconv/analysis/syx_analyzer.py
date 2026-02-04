"""
QY70 SysEx file analyzer.

Extracts ALL information from QY70 SysEx bulk dump files including:
- Message structure and statistics
- Section data for each AL address
- Header configuration
- Decoded phrase data
- Checksum validation results
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from collections import Counter

from qyconv.formats.qy70.sysex_parser import SysExParser, SysExMessage, MessageType
from qyconv.utils.yamaha_7bit import decode_7bit
from qyconv.utils.checksum import verify_sysex_checksum


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

    # AL address distribution
    al_addresses: List[int] = field(default_factory=list)
    al_histogram: Dict[int, int] = field(default_factory=dict)

    # Track sections (0x08-0x2F)
    track_sections: Dict[int, bytes] = field(default_factory=dict)

    # Raw statistics
    total_encoded_bytes: int = 0
    total_decoded_bytes: int = 0


class SyxAnalyzer:
    """
    Complete analyzer for QY70 SysEx files.

    Extracts and decodes all message content.
    """

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
                analysis.tempo = self._extract_tempo(data)

            # Track sections
            if self.TRACK_SECTION_START <= al <= self.TRACK_SECTION_END:
                analysis.track_sections[al] = data

        return analysis

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
        """Try to extract tempo from header data."""
        # Common tempo locations
        for offset in [0x0A, 0x0C, 0x10, 0x14]:
            if offset < len(data):
                val = data[offset]
                if 40 <= val <= 240:
                    return val
        return 120

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
