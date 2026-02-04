"""
QY70 SysEx message parser.

Parses Yamaha QY70 System Exclusive messages for pattern/style data.

QY70 SysEx Format:
- Manufacturer ID: 0x43 (Yamaha)
- Model ID: 0x5F (QY70)
- Device Number: 0x0n for bulk dump, 0x1n for parameter change

Bulk Dump Format:
    F0 43 0n 5F BH BL AH AM AL [data...] CS F7

Where:
    - 0n: Device number (0 = device 1)
    - BH/BL: Byte count (7-bit packed, high/low)
    - AH/AM/AL: Address (high/mid/low)
    - data: 7-bit encoded payload
    - CS: Checksum
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import List, Optional, Tuple, Union
from qyconv.utils.yamaha_7bit import decode_7bit
from qyconv.utils.checksum import verify_checksum


class MessageType(IntEnum):
    """QY70 SysEx message types."""

    PARAMETER_CHANGE = 0x10  # Device number 1n
    BULK_DUMP = 0x00  # Device number 0n
    DUMP_REQUEST = 0x20  # Device number 2n


@dataclass
class SysExMessage:
    """
    Parsed SysEx message.

    Attributes:
        message_type: Type of message (bulk dump, parameter change, etc.)
        device_number: MIDI device number (0-15)
        address: (AH, AM, AL) address tuple
        data: Raw data bytes (7-bit encoded for bulk dumps)
        decoded_data: Decoded 8-bit data (for bulk dumps)
        checksum: Checksum byte (bulk dumps only)
        checksum_valid: Whether checksum verified
        raw: Original raw message bytes
    """

    message_type: MessageType
    device_number: int
    address: Tuple[int, int, int]
    data: bytes
    decoded_data: Optional[bytes] = None
    checksum: int = 0
    checksum_valid: bool = True
    raw: bytes = b""

    @property
    def address_high(self) -> int:
        return self.address[0]

    @property
    def address_mid(self) -> int:
        return self.address[1]

    @property
    def address_low(self) -> int:
        return self.address[2]

    @property
    def is_bulk_dump(self) -> bool:
        return self.message_type == MessageType.BULK_DUMP

    @property
    def is_style_data(self) -> bool:
        """Check if this message contains style/pattern data."""
        # QY70 style data uses address AH=02 AM=7E
        return self.address_high == 0x02 and self.address_mid == 0x7E


class SysExParser:
    """
    Parser for QY70 SysEx messages.

    Example:
        parser = SysExParser()
        messages = parser.parse_file("style.syx")

        for msg in messages:
            if msg.is_style_data:
                print(f"Style data at section {msg.address_low}")
    """

    # Constants
    YAMAHA_ID = 0x43
    QY70_MODEL_ID = 0x5F
    SYSEX_START = 0xF0
    SYSEX_END = 0xF7

    def __init__(self):
        self.messages: List[SysExMessage] = []

    def parse_file(self, filepath: str) -> List[SysExMessage]:
        """
        Parse a SysEx file.

        Args:
            filepath: Path to .syx file

        Returns:
            List of parsed SysEx messages
        """
        with open(filepath, "rb") as f:
            data = f.read()
        return self.parse_bytes(data)

    def parse_bytes(self, data: Union[bytes, bytearray]) -> List[SysExMessage]:
        """
        Parse SysEx data from bytes.

        Args:
            data: Raw SysEx data

        Returns:
            List of parsed SysEx messages
        """
        self.messages = []

        if isinstance(data, bytearray):
            data = bytes(data)

        # Find all SysEx messages
        raw_messages = self._split_messages(data)

        for raw in raw_messages:
            msg = self._parse_message(raw)
            if msg is not None:
                self.messages.append(msg)

        return self.messages

    def _split_messages(self, data: bytes) -> List[bytes]:
        """Split data into individual SysEx messages."""
        messages = []
        start = None

        for i, byte in enumerate(data):
            if byte == self.SYSEX_START:
                start = i
            elif byte == self.SYSEX_END and start is not None:
                messages.append(data[start : i + 1])
                start = None

        return messages

    def _parse_message(self, data: bytes) -> Optional[SysExMessage]:
        """
        Parse a single SysEx message.

        Args:
            data: Raw message bytes (including F0 and F7)

        Returns:
            Parsed message or None if invalid
        """
        if len(data) < 6:
            return None

        # Verify structure
        if data[0] != self.SYSEX_START or data[-1] != self.SYSEX_END:
            return None

        # Check Yamaha manufacturer ID
        if data[1] != self.YAMAHA_ID:
            return None

        # Check QY70 model ID
        if data[3] != self.QY70_MODEL_ID:
            return None

        # Get device number and message type
        device_byte = data[2]
        device_number = device_byte & 0x0F
        type_nibble = device_byte & 0xF0

        try:
            message_type = MessageType(type_nibble)
        except ValueError:
            return None

        if message_type == MessageType.BULK_DUMP:
            return self._parse_bulk_dump(data, device_number)
        elif message_type == MessageType.PARAMETER_CHANGE:
            return self._parse_parameter_change(data, device_number)
        else:
            return None

    def _parse_bulk_dump(self, data: bytes, device_number: int) -> Optional[SysExMessage]:
        """
        Parse a bulk dump message.

        Format: F0 43 0n 5F BH BL AH AM AL [data...] CS F7
        """
        if len(data) < 11:
            return None

        # Byte count (7-bit packed)
        bh = data[4]
        bl = data[5]
        byte_count = (bh << 7) | bl

        # Address
        ah = data[6]
        am = data[7]
        al = data[8]

        # Data (between address and checksum)
        payload = data[9:-2]

        # Checksum
        checksum = data[-2]

        # Verify checksum (over BH BL AH AM AL + data)
        # QY70 includes byte count in checksum calculation
        checksum_data = data[4:-2]  # BH BL AH AM AL + data
        checksum_valid = verify_checksum(checksum_data, checksum)

        # Decode 7-bit data
        decoded = decode_7bit(payload)

        return SysExMessage(
            message_type=MessageType.BULK_DUMP,
            device_number=device_number,
            address=(ah, am, al),
            data=payload,
            decoded_data=decoded,
            checksum=checksum,
            checksum_valid=checksum_valid,
            raw=data,
        )

    def _parse_parameter_change(self, data: bytes, device_number: int) -> Optional[SysExMessage]:
        """
        Parse a parameter change message.

        Format: F0 43 1n 5F AH AM AL DD F7
        """
        if len(data) < 8:
            return None

        # Address
        ah = data[4]
        am = data[5]
        al = data[6]

        # Data (single byte or multiple)
        payload = data[7:-1]

        return SysExMessage(
            message_type=MessageType.PARAMETER_CHANGE,
            device_number=device_number,
            address=(ah, am, al),
            data=payload,
            decoded_data=payload,  # No 7-bit encoding for param changes
            raw=data,
        )

    def get_style_messages(self) -> List[SysExMessage]:
        """Get only style/pattern data messages."""
        return [m for m in self.messages if m.is_style_data]

    def get_messages_by_section(self, section_index: int) -> List[SysExMessage]:
        """
        Get messages for a specific section.

        Args:
            section_index: Section index (AL byte value)

        Returns:
            Messages for that section
        """
        return [m for m in self.messages if m.is_style_data and m.address_low == section_index]


def parse_qy70_sysex(filepath: str) -> List[SysExMessage]:
    """
    Convenience function to parse a QY70 SysEx file.

    Args:
        filepath: Path to .syx file

    Returns:
        List of parsed messages
    """
    parser = SysExParser()
    return parser.parse_file(filepath)
