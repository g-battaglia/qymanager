"""
Yamaha SysEx checksum calculation utilities.

Yamaha bulk dump messages include a checksum byte calculated as:
1. Sum all bytes from Address High (AH) through the last data byte
2. Take the lower 7 bits of the sum
3. Subtract from 128 (0x80)
4. If result is 128 (0x80), use 0 instead

The checksum ensures data integrity during MIDI transmission.
"""

from typing import Union, List


def calculate_yamaha_checksum(data: Union[bytes, List[int]]) -> int:
    """
    Calculate Yamaha SysEx checksum for bulk dump data.

    The checksum is calculated over the address and data bytes
    (not including F0, manufacturer ID, device ID, model ID, byte count,
    checksum itself, or F7).

    Args:
        data: Bytes to calculate checksum over (typically AH, AM, AL + data)

    Returns:
        Checksum value (0-127)

    Example:
        >>> calculate_yamaha_checksum(bytes([0x02, 0x7E, 0x00, 0x10, 0x20, 0x30]))
        ... # Returns calculated checksum
    """
    if isinstance(data, list):
        data = bytes(data)

    # Sum all bytes
    total = sum(data)

    # Take lower 7 bits
    total_7bit = total & 0x7F

    # Subtract from 128
    checksum = (128 - total_7bit) & 0x7F

    return checksum


def verify_checksum(data: Union[bytes, List[int]], expected_checksum: int) -> bool:
    """
    Verify a Yamaha SysEx checksum.

    Args:
        data: Bytes the checksum was calculated over
        expected_checksum: The checksum byte from the message

    Returns:
        True if checksum is valid, False otherwise
    """
    calculated = calculate_yamaha_checksum(data)
    return calculated == expected_checksum


def verify_sysex_checksum(message: Union[bytes, List[int]]) -> bool:
    """
    Verify checksum of a complete Yamaha bulk dump SysEx message.

    Expects format: F0 43 0n 5F BH BL AH AM AL [data...] CS F7

    Args:
        message: Complete SysEx message including F0 and F7

    Returns:
        True if checksum is valid
    """
    if isinstance(message, list):
        message = bytes(message)

    if len(message) < 11:
        return False

    if message[0] != 0xF0 or message[-1] != 0xF7:
        return False

    # Extract address and data (from AH to last data byte, before checksum)
    # Format: F0 43 0n 5F BH BL AH AM AL [data...] CS F7
    #         0  1  2  3  4  5  6  7  8  ...      -2 -1
    checksum_data = message[6:-2]  # AH AM AL + data
    expected_checksum = message[-2]

    return verify_checksum(checksum_data, expected_checksum)


def add_checksum(data: Union[bytes, List[int]]) -> bytes:
    """
    Calculate and append checksum to data.

    Args:
        data: Address and data bytes (AH, AM, AL + data)

    Returns:
        Original data with checksum appended
    """
    if isinstance(data, list):
        data = bytes(data)

    checksum = calculate_yamaha_checksum(data)
    return data + bytes([checksum])
