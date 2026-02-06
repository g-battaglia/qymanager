"""
Data validation utilities for QY pattern data.
"""

from typing import Optional, List, Tuple


class ValidationError(Exception):
    """Raised when pattern data validation fails."""

    pass


def validate_midi_value(value: int, name: str = "value") -> None:
    """
    Validate that a value is in MIDI range (0-127).

    Args:
        value: The value to validate
        name: Name of the value for error messages

    Raises:
        ValidationError: If value is out of range
    """
    if not 0 <= value <= 127:
        raise ValidationError(f"{name} must be 0-127, got {value}")


def validate_channel(channel: int) -> None:
    """
    Validate MIDI channel number (1-16).

    Args:
        channel: Channel number

    Raises:
        ValidationError: If channel is out of range
    """
    if not 1 <= channel <= 16:
        raise ValidationError(f"MIDI channel must be 1-16, got {channel}")


def validate_tempo(tempo: int) -> None:
    """
    Validate tempo value for QY devices.

    Args:
        tempo: Tempo in BPM

    Raises:
        ValidationError: If tempo is out of range
    """
    if not 40 <= tempo <= 240:
        raise ValidationError(f"Tempo must be 40-240 BPM, got {tempo}")


def validate_pattern_name(name: str, max_length: int = 10) -> str:
    """
    Validate and normalize pattern name.

    Args:
        name: Pattern name
        max_length: Maximum allowed length (default 10 for QY devices)

    Returns:
        Normalized name (uppercase, padded/truncated to length)

    Raises:
        ValidationError: If name contains invalid characters
    """
    # Allow alphanumeric and basic punctuation
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_./")
    name_upper = name.upper()

    for char in name_upper:
        if char not in allowed:
            raise ValidationError(f"Invalid character '{char}' in pattern name")

    # Truncate if too long
    if len(name_upper) > max_length:
        name_upper = name_upper[:max_length]

    # Pad with spaces if too short
    name_upper = name_upper.ljust(max_length)

    return name_upper


def validate_time_signature(numerator: int, denominator: int) -> None:
    """
    Validate time signature.

    Args:
        numerator: Beats per measure
        denominator: Beat unit (2, 4, 8, 16)

    Raises:
        ValidationError: If time signature is invalid
    """
    if not 1 <= numerator <= 16:
        raise ValidationError(f"Time signature numerator must be 1-16, got {numerator}")

    valid_denominators = [2, 4, 8, 16]
    if denominator not in valid_denominators:
        raise ValidationError(
            f"Time signature denominator must be one of {valid_denominators}, got {denominator}"
        )


def validate_section_length(length: int, max_measures: int = 999) -> None:
    """
    Validate section length in measures.

    Args:
        length: Length in measures
        max_measures: Maximum allowed measures

    Raises:
        ValidationError: If length is invalid
    """
    if not 1 <= length <= max_measures:
        raise ValidationError(f"Section length must be 1-{max_measures}, got {length}")


def validate_q7p_header(data: bytes) -> bool:
    """
    Validate QY700 Q7P file header.

    Args:
        data: File data (at least 16 bytes)

    Returns:
        True if valid Q7P header
    """
    if len(data) < 16:
        return False

    expected = b"YQ7PAT     V1.00"
    return data[:16] == expected


def validate_qy70_sysex_header(data: bytes) -> bool:
    """
    Validate QY70 SysEx message header.

    Args:
        data: SysEx message data

    Returns:
        True if valid QY70 SysEx
    """
    if len(data) < 4:
        return False

    # F0 43 xx 5F
    return data[0] == 0xF0 and data[1] == 0x43 and data[3] == 0x5F
