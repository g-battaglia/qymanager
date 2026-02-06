"""
Yamaha 7-bit encoding/decoding utilities.

Yamaha uses a 7-bit packing scheme for SysEx data to ensure all bytes
have the high bit (bit 7) clear, as required by MIDI specification.

Encoding scheme:
- Take 7 bytes of raw 8-bit data
- Extract the high bits from each byte into a "header" byte
- Clear the high bits in the original bytes
- Result: 8 bytes (1 header + 7 data bytes) for every 7 input bytes

Example:
    Input:  [0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02]  (7 bytes)
    Header: 0b01000000 (bit 7 of byte 0 is set, so bit 6 of header is set)
    Output: [0x40, 0x00, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02]  (8 bytes)
"""

from typing import List, Union


def decode_7bit(encoded_data: Union[bytes, List[int]]) -> bytes:
    """
    Decode Yamaha 7-bit packed data to 8-bit raw data.

    For every 8 bytes of encoded data, produces 7 bytes of decoded data.
    The first byte of each 8-byte group is the "high-bit header" that
    contains the MSBs for the following 7 bytes.

    Args:
        encoded_data: The 7-bit encoded data from SysEx

    Returns:
        Decoded 8-bit raw data

    Example:
        >>> decode_7bit(bytes([0x40, 0x00, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02]))
        b'\\x80@  \\x10\\x08\\x04\\x02'
    """
    if isinstance(encoded_data, list):
        encoded_data = bytes(encoded_data)

    result = bytearray()

    # Process in groups of 8 bytes (1 header + 7 data)
    for i in range(0, len(encoded_data), 8):
        chunk = encoded_data[i : i + 8]

        if len(chunk) < 2:
            break

        # First byte is the high-bit header
        header = chunk[0]

        # Remaining bytes (up to 7) are the data with cleared high bits
        data_bytes = chunk[1:]

        for j, byte in enumerate(data_bytes):
            # Check if the corresponding bit in the header is set
            # Bit 6 corresponds to byte 0, bit 5 to byte 1, etc.
            high_bit = (header >> (6 - j)) & 0x01
            # Reconstruct the original byte
            result.append(byte | (high_bit << 7))

    return bytes(result)


def encode_7bit(raw_data: Union[bytes, List[int]]) -> bytes:
    """
    Encode 8-bit raw data to Yamaha 7-bit packed format.

    For every 7 bytes of raw data, produces 8 bytes of encoded data.
    The first byte is the "high-bit header" containing the MSBs,
    followed by 7 bytes with their MSBs cleared.

    Args:
        raw_data: The raw 8-bit data to encode

    Returns:
        7-bit encoded data suitable for SysEx transmission

    Example:
        >>> encode_7bit(b'\\x80@  \\x10\\x08\\x04\\x02')
        b'@\\x00@ \\x10\\x08\\x04\\x02'
    """
    if isinstance(raw_data, list):
        raw_data = bytes(raw_data)

    result = bytearray()

    # Process in groups of 7 bytes
    for i in range(0, len(raw_data), 7):
        chunk = raw_data[i : i + 7]

        # Build the high-bit header
        header = 0
        for j, byte in enumerate(chunk):
            high_bit = (byte >> 7) & 0x01
            # Place high bit at position (6 - j) in header
            header |= high_bit << (6 - j)

        result.append(header)

        # Append data bytes with high bits cleared
        for byte in chunk:
            result.append(byte & 0x7F)

    return bytes(result)


def decode_7bit_stream(encoded_data: bytes, expected_length: int = None) -> bytes:
    """
    Decode a stream of 7-bit encoded data with optional length verification.

    Args:
        encoded_data: The encoded data stream
        expected_length: Expected number of decoded bytes (optional)

    Returns:
        Decoded raw data

    Raises:
        ValueError: If decoded length doesn't match expected length
    """
    decoded = decode_7bit(encoded_data)

    if expected_length is not None and len(decoded) != expected_length:
        # Trim or raise depending on the difference
        if len(decoded) > expected_length:
            decoded = decoded[:expected_length]
        else:
            raise ValueError(
                f"Decoded length {len(decoded)} doesn't match expected {expected_length}"
            )

    return decoded


# Alias for backward compatibility
pack_7bit = encode_7bit
unpack_7bit = decode_7bit
