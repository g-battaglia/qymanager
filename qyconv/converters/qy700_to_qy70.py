"""
QY700 to QY70 format converter.

Converts QY700 Q7P (.Q7P) pattern files to QY70 SysEx (.syx) format.
Generates a complete bulk dump that can be loaded into QY70.

The conversion process:
1. Parse Q7P binary file
2. Extract pattern settings (tempo, name, etc.)
3. Extract phrase/MIDI data (for 5120-byte files)
4. Extract section data for each of the 6 sections
5. Encode data as 7-bit Yamaha format
6. Generate SysEx messages with proper checksums
7. Write complete .syx file

Key Discovery: QY70 and QY700 use the SAME proprietary MIDI event format:
- D0 nn vv = Drum note on
- E0 nn vv = Melody note on
- C1 nn pp = Alternate note
- A0-A7 dd = Delta time
- BE xx    = Note off
- F2       = End of phrase

This means MIDI data can be transferred directly between formats!
"""

from pathlib import Path
from typing import Dict, List, Optional, Union
import struct

from qyconv.models.pattern import Pattern
from qyconv.models.section import Section, SectionType
from qyconv.formats.qy700.reader import QY700Reader
from qyconv.formats.qy700.decoder import Q7PPatternDecoder, Q7POffsets
from qyconv.formats.qy700.phrase_parser import QY700PhraseParser, PhraseBlock
from qyconv.utils.yamaha_7bit import encode_7bit
from qyconv.utils.checksum import calculate_yamaha_checksum


class QY700ToQY70Converter:
    """
    Converter from QY700 Q7P format to QY70 SysEx format.

    Generates a complete SysEx bulk dump file that can be loaded
    into a Yamaha QY70 synthesizer.

    Attributes:
        device_number: MIDI device number for SysEx (0-15)
        q7p_data: Raw Q7P file data
    """

    # SysEx constants
    SYSEX_START = 0xF0
    SYSEX_END = 0xF7
    YAMAHA_ID = 0x43
    QY70_MODEL_ID = 0x5F

    # Bulk dump address constants
    STYLE_AH = 0x02  # Style data
    STYLE_AM = 0x7E  # User style memory

    # Section AL values (QY70 specific)
    SECTION_AL = {
        SectionType.INTRO: 0x00,
        SectionType.MAIN_A: 0x01,
        SectionType.MAIN_B: 0x02,
        SectionType.FILL_AB: 0x03,
        SectionType.FILL_BA: 0x04,
        SectionType.ENDING: 0x05,
    }

    # Header/config section
    HEADER_AL = 0x7F

    # Maximum payload per SysEx message (before 7-bit encoding)
    # QY70 appears to use 128-byte blocks
    MAX_PAYLOAD = 128

    # Offset maps for different file sizes
    # Format: (3072-byte offset, 5120-byte offset)
    OFFSETS = {
        "NAME": (0x876, 0xA00),
        "TEMPO": (0x188, 0xA08),
        "TIME_SIG": (0x18A, 0xA0A),
        "CHANNELS": (0x190, 0xA18),
        "SECTION_DATA": (0x120, 0x120),  # Same for both
        "PHRASE_DATA": (0x360, 0x360),  # Same start, different size
        "SEQUENCE_DATA": (0x678, 0x678),  # Same start, different size
        "VOLUME": (0x226, 0x226),  # Same for both (in header area)
        "REVERB": (0x256, 0x256),
        "PAN": (0x276, 0x276),
        "CHORUS": (0x296, 0x296),
    }

    def _get_offset(self, name: str) -> int:
        """Get the correct offset based on file size."""
        offsets = self.OFFSETS.get(name)
        if offsets is None:
            raise ValueError(f"Unknown offset name: {name}")
        return offsets[1] if self._is_extended else offsets[0]

    def __init__(self, device_number: int = 0):
        """
        Initialize converter.

        Args:
            device_number: MIDI device number (0-15)
        """
        self.device_number = device_number & 0x0F
        self.q7p_data: bytes = b""
        self._pattern: Optional[Pattern] = None
        self._file_size: int = 0
        self._is_extended: bool = False  # True for 5120-byte files
        self._phrases: List[PhraseBlock] = []  # Parsed phrase blocks

    def convert(self, source_path: Union[str, Path]) -> bytes:
        """
        Convert Q7P file to SysEx format.

        Args:
            source_path: Path to .Q7P file

        Returns:
            Complete SysEx file data
        """
        source_path = Path(source_path)

        with open(source_path, "rb") as f:
            self.q7p_data = f.read()

        return self.convert_bytes(self.q7p_data)

    def convert_bytes(self, q7p_data: bytes) -> bytes:
        """
        Convert Q7P bytes to SysEx format.

        Args:
            q7p_data: Raw Q7P file data (3072 or 5120 bytes)

        Returns:
            Complete SysEx file data
        """
        if len(q7p_data) not in (3072, 5120):
            raise ValueError(f"Invalid Q7P size: {len(q7p_data)} (expected 3072 or 5120)")

        self.q7p_data = q7p_data
        self._file_size = len(q7p_data)
        self._is_extended = len(q7p_data) == 5120

        # Parse phrases from 5120-byte files
        if self._is_extended:
            phrase_parser = QY700PhraseParser(q7p_data)
            self._phrases = phrase_parser.parse_phrases()
        else:
            self._phrases = []

        # Parse Q7P to get pattern info
        decoder = Q7PPatternDecoder(q7p_data)
        self._pattern = decoder.decode()

        # Build SysEx messages
        messages: List[bytes] = []

        # 1. Generate header section (0x7F)
        header_messages = self._generate_header_section()
        messages.extend(header_messages)

        # 2. Generate each section's data (0x00-0x05)
        for section_type in [
            SectionType.INTRO,
            SectionType.MAIN_A,
            SectionType.MAIN_B,
            SectionType.FILL_AB,
            SectionType.FILL_BA,
            SectionType.ENDING,
        ]:
            section_messages = self._generate_section_messages(section_type)
            messages.extend(section_messages)

        # 3. Generate track data for each section (0x08-0x2F)
        # Track data is at AL = 0x08 + (section_index * 8) + track_index
        for section_idx in range(6):
            track_messages = self._generate_track_messages(section_idx)
            messages.extend(track_messages)

        return b"".join(messages)

    def _generate_header_section(self) -> List[bytes]:
        """Generate SysEx messages for pattern header (section 0x7F)."""
        messages = []

        # Build header data (based on QY70 format)
        header = bytearray(640)  # Approximate header size

        # Extract pattern name from Q7P (8 or 10 bytes)
        name_offset = self._get_offset("NAME")
        if name_offset + 10 <= len(self.q7p_data):
            name_data = self.q7p_data[name_offset : name_offset + 10]
            for i, byte in enumerate(name_data[:10]):
                if 0x20 <= byte <= 0x7E:  # Printable ASCII
                    header[i] = byte
                else:
                    header[i] = 0x20  # Space for non-printable
        else:
            # Fallback to pattern name from decoder
            name = self._pattern.name[:10].upper().ljust(10) if self._pattern else "NEW STYLE "
            for i, char in enumerate(name):
                header[i] = ord(char) if ord(char) < 128 else 0x20

        # Extract tempo from Q7P
        tempo_offset = self._get_offset("TEMPO")
        if tempo_offset + 2 <= len(self.q7p_data):
            raw_tempo = (self.q7p_data[tempo_offset] << 8) | self.q7p_data[tempo_offset + 1]
            tempo = raw_tempo // 10 if raw_tempo > 0 else 120
        else:
            tempo = self._pattern.settings.tempo if self._pattern else 120

        # Tempo in QY70 format (single byte at offset 0x0A)
        header[0x0A] = min(255, max(40, tempo)) & 0x7F

        # Extract time signature from Q7P
        ts_offset = self._get_offset("TIME_SIG")
        if ts_offset + 2 <= len(self.q7p_data):
            header[0x0C] = self.q7p_data[ts_offset]
            header[0x0D] = self.q7p_data[ts_offset + 1]

        # Split header into chunks and create messages
        for chunk_start in range(0, len(header), self.MAX_PAYLOAD):
            chunk = bytes(header[chunk_start : chunk_start + self.MAX_PAYLOAD])
            msg = self._create_bulk_dump_message(self.HEADER_AL, chunk)
            messages.append(msg)

        return messages

    def _generate_section_messages(self, section_type: SectionType) -> List[bytes]:
        """Generate SysEx messages for a pattern section."""
        messages = []
        al = self.SECTION_AL.get(section_type)

        if al is None:
            return messages

        # Extract section data from Q7P
        section_data = self._extract_section_data(section_type)

        if not section_data:
            # Empty section - generate minimal data
            section_data = self._generate_empty_section_data()

        # Split into chunks
        for chunk_start in range(0, len(section_data), self.MAX_PAYLOAD):
            chunk = section_data[chunk_start : chunk_start + self.MAX_PAYLOAD]
            msg = self._create_bulk_dump_message(al, chunk)
            messages.append(msg)

        return messages

    def _extract_section_data(self, section_type: SectionType) -> bytes:
        """
        Extract section data from Q7P file.

        Maps Q7P offset ranges to section data.
        """
        if not self.q7p_data:
            return b""

        section_idx = self.SECTION_AL.get(section_type, 0)

        # Section config from 0x120 area
        config_offset = Q7POffsets.SECTION_DATA_START + (section_idx * 16)
        config_data = self.q7p_data[config_offset : config_offset + 16]

        # Phrase data from 0x360 area
        phrase_offset = Q7POffsets.PHRASE_DATA_START + (section_idx * 80)
        phrase_data = self.q7p_data[phrase_offset : phrase_offset + 80]

        # Combine into section data
        return config_data + phrase_data

    def _generate_empty_section_data(self) -> bytes:
        """Generate data for an empty section."""
        # Minimal section data structure
        data = bytearray(128)

        # Common header pattern observed in QY70 dumps
        data[0:8] = bytes([0x08, 0x04, 0x82, 0x01, 0x00, 0x40, 0x20, 0x08])

        return bytes(data)

    def _generate_track_messages(self, section_idx: int) -> List[bytes]:
        """Generate SysEx messages for track data of a section."""
        messages = []

        # Track data starts at AL = 0x08 for section 0
        # Each section has 8 tracks at consecutive AL values
        base_al = 0x08 + (section_idx * 8)

        # Extract track data from Q7P
        for track_num in range(8):
            al = base_al + track_num
            track_data = self._extract_track_data(section_idx, track_num)

            if track_data:
                # Split if needed
                for chunk_start in range(0, len(track_data), self.MAX_PAYLOAD):
                    chunk = track_data[chunk_start : chunk_start + self.MAX_PAYLOAD]
                    msg = self._create_bulk_dump_message(al, chunk)
                    messages.append(msg)

        return messages

    def _extract_track_data(self, section_idx: int, track_num: int) -> bytes:
        """
        Extract track data from Q7P and build proper QY70 track structure.

        QY70 Track Block Structure (128 bytes per block, can span multiple blocks):
        - Offset 0-11: Common header: 08 04 82 01 00 40 20 08 04 82 01 00
        - Offset 12-13: Constant: 06 1C
        - Offset 14-15: Voice encoding (0x40 0x80 = default, or Bank MSB / Program)
        - Offset 16-17: Note range (Low / High for melody, 0x87 0xF8 for drums)
        - Offset 18-20: Unknown (differs drum vs melody)
        - Offset 21: Flag (0x41 = pan valid, 0x00 = use default)
        - Offset 22: Pan value (0-127, 64=center)
        - Offset 23: Unknown
        - Offset 24+: MIDI sequence data (uses same format as Q7P!)

        Args:
            section_idx: Section index (0-5)
            track_num: Track number (0-7)

        Returns:
            Track data bytes (may be longer than 128 bytes for tracks with MIDI data)
        """
        if not self.q7p_data:
            return b""

        # Track names for reference: RHY1, RHY2, BASS, CHD1, CHD2, PAD, PHR1, PHR2
        is_drum_track = track_num in (0, 1)  # RHY1 and RHY2 are drum tracks

        # Correct Q7P offsets (verified from actual files):
        # Volume: 0x226 + (section_idx * 8) + track_num
        # Reverb: 0x256 + (section_idx * 8) + track_num
        # Pan:    0x276 + (section_idx * 8) + track_num
        # Chorus: 0x296 + (section_idx * 8) + track_num

        vol_offset = 0x226 + (section_idx * 8) + track_num
        reverb_offset = 0x256 + (section_idx * 8) + track_num
        pan_offset = 0x276 + (section_idx * 8) + track_num
        chorus_offset = 0x296 + (section_idx * 8) + track_num

        volume = self.q7p_data[vol_offset] if vol_offset < len(self.q7p_data) else 100
        reverb = self.q7p_data[reverb_offset] if reverb_offset < len(self.q7p_data) else 40
        pan = self.q7p_data[pan_offset] if pan_offset < len(self.q7p_data) else 64
        chorus = self.q7p_data[chorus_offset] if chorus_offset < len(self.q7p_data) else 0

        # Channel from channel table (0x190)
        ch_offset = 0x190 + track_num
        channel = self.q7p_data[ch_offset] if ch_offset < len(self.q7p_data) else track_num

        # Build QY70 track header (24 bytes)
        track_header = bytearray(24)

        # Common header (bytes 0-11) - observed in all QY70 track dumps
        track_header[0:12] = bytes(
            [0x08, 0x04, 0x82, 0x01, 0x00, 0x40, 0x20, 0x08, 0x04, 0x82, 0x01, 0x00]
        )

        # Constant bytes (12-13)
        track_header[12:14] = bytes([0x06, 0x1C])

        # Voice encoding (bytes 14-15)
        # 0x40 0x80 = use track-type default voice
        track_header[14] = 0x40
        track_header[15] = 0x80

        # Note range (bytes 16-17)
        if is_drum_track:
            # Drum tracks use special note range encoding
            track_header[16] = 0x87
            track_header[17] = 0xF8
            # Bytes 18-20 for drums
            track_header[18] = 0x80
            track_header[19] = 0x8E
            track_header[20] = 0x83
        else:
            # Melody tracks: full range
            track_header[16] = 0x07
            track_header[17] = 0x78
            # Bytes 18-20 for melody
            track_header[18] = 0x00
            track_header[19] = 0x0F
            track_header[20] = 0x10

        # Pan flag and value (bytes 21-22)
        if pan != 64:  # Non-default pan
            track_header[21] = 0x41  # Pan valid flag
            track_header[22] = pan & 0x7F
        else:
            track_header[21] = 0x41  # Pan valid flag
            track_header[22] = 0x40  # Center

        # Byte 23: Unknown, typically 0x00
        track_header[23] = 0x00

        # Get MIDI data from parsed phrases (5120-byte files)
        midi_data = self._get_phrase_midi_for_track(section_idx, track_num)

        if midi_data:
            # Combine header + MIDI data
            track_data = bytes(track_header) + midi_data
        else:
            # No MIDI data - create minimal 128-byte block with placeholder
            track_data = bytearray(128)
            track_data[:24] = track_header
            # Add minimal MIDI placeholder
            track_data[24:28] = bytes([0x1F, 0xA3, 0x60, 0x00])  # Observed in empty tracks
            track_data[28:32] = bytes([0xDF, 0x77, 0xC0, 0x8F])

        return bytes(track_data)

    def _get_phrase_midi_for_track(self, section_idx: int, track_num: int) -> bytes:
        """
        Get MIDI data for a specific track from parsed phrases.

        The mapping between sections/tracks and phrases is determined by
        the section config at 0x120 in 5120-byte files.

        Args:
            section_idx: Section index (0-5 for QY70 sections)
            track_num: Track number (0-7)

        Returns:
            Raw MIDI event bytes, or empty if no phrase found
        """
        if not self._phrases:
            return b""

        # For 5120-byte files, phrases are referenced by the section config
        # The config at 0x120 has format: F0 00 FB phrase_idx 00 track_ref C0 04 F2
        # Each entry is 9 bytes

        config_offset = 0x120 + (section_idx * 9)
        if config_offset + 9 > len(self.q7p_data):
            return b""

        # Check for valid config entry
        if self.q7p_data[config_offset] not in (0xF0, 0xF1):
            return b""

        phrase_idx = self.q7p_data[config_offset + 3]

        # Get the phrase if it exists
        if phrase_idx < len(self._phrases):
            phrase = self._phrases[phrase_idx]
            # Return the raw MIDI data - QY70 uses the same event format!
            return phrase.raw_data

        return b""

    def _create_bulk_dump_message(self, al: int, data: bytes) -> bytes:
        """
        Create a single SysEx bulk dump message.

        Format: F0 43 0n 5F BH BL AH AM AL [encoded data] CS F7

        Where:
        - n = device number
        - BH BL = byte count (of encoded data)
        - AH AM AL = address (02 7E xx for style data)
        - CS = checksum (over BH BL AH AM AL + encoded data)

        Args:
            al: Address low byte (section index)
            data: Raw data to encode

        Returns:
            Complete SysEx message
        """
        # Encode data as 7-bit
        encoded = encode_7bit(data)

        # Byte count (of encoded data)
        byte_count = len(encoded)
        bh = (byte_count >> 7) & 0x7F
        bl = byte_count & 0x7F

        # Address
        ah = self.STYLE_AH
        am = self.STYLE_AM

        # Build message body (for checksum calculation)
        # Checksum includes: BH BL AH AM AL + encoded data
        checksum_data = bytes([bh, bl, ah, am, al]) + encoded
        checksum = calculate_yamaha_checksum(checksum_data)

        # Build complete message
        msg = bytearray(
            [
                self.SYSEX_START,
                self.YAMAHA_ID,
                0x00 | self.device_number,  # Bulk dump type
                self.QY70_MODEL_ID,
                bh,
                bl,  # Byte count
                ah,
                am,
                al,  # Address
            ]
        )
        msg.extend(encoded)
        msg.append(checksum)
        msg.append(self.SYSEX_END)

        return bytes(msg)

    def convert_and_save(
        self, source_path: Union[str, Path], output_path: Union[str, Path]
    ) -> None:
        """
        Convert Q7P to SysEx and save to file.

        Args:
            source_path: Path to source .Q7P file
            output_path: Path for output .syx file
        """
        syx_data = self.convert(source_path)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "wb") as f:
            f.write(syx_data)


def convert_qy700_to_qy70(
    source_path: Union[str, Path], output_path: Union[str, Path], device_number: int = 0
) -> None:
    """
    Convert QY700 Q7P file to QY70 SysEx format.

    Convenience function for simple conversion.

    Args:
        source_path: Path to source .Q7P file
        output_path: Path for output .syx file
        device_number: MIDI device number (0-15)

    Example:
        convert_qy700_to_qy70("pattern.Q7P", "style.syx")
    """
    converter = QY700ToQY70Converter(device_number)
    converter.convert_and_save(source_path, output_path)


def convert_pattern_to_syx(pattern: Pattern, device_number: int = 0) -> bytes:
    """
    Convert Pattern object to SysEx bytes.

    Args:
        pattern: Pattern to convert
        device_number: MIDI device number

    Returns:
        SysEx file data
    """
    converter = QY700ToQY70Converter(device_number)

    # We need raw Q7P data to convert properly
    # If pattern has raw data, use it
    if pattern._raw_data and len(pattern._raw_data) == 3072:
        return converter.convert_bytes(pattern._raw_data)

    # Otherwise, generate from pattern
    # This is a fallback that generates minimal SysEx
    messages = []

    # Generate header
    header = bytearray(128)
    name = pattern.name[:10].upper().ljust(10)
    for i, char in enumerate(name):
        header[i] = ord(char) if ord(char) < 128 else 0x20
    header[0x0A] = pattern.settings.tempo & 0x7F

    msg = converter._create_bulk_dump_message(converter.HEADER_AL, bytes(header))
    messages.append(msg)

    # Generate section messages
    for section_type, section in pattern.sections.items():
        if section_type in converter.SECTION_AL:
            al = converter.SECTION_AL[section_type]

            # Build section data
            section_data = bytearray(128)
            section_data[0:8] = bytes([0x08, 0x04, 0x82, 0x01, 0x00, 0x40, 0x20, 0x08])

            if section._raw_data:
                # Copy raw data if available
                copy_len = min(len(section._raw_data), 128)
                section_data[:copy_len] = section._raw_data[:copy_len]

            msg = converter._create_bulk_dump_message(al, bytes(section_data))
            messages.append(msg)

    return b"".join(messages)
