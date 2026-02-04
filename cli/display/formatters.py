"""
Display formatting utilities for CLI output.

Provides bar graphics, percentage displays, and other formatting helpers.
"""

from typing import Optional, Tuple


def value_bar(
    value: int,
    max_value: int = 127,
    width: int = 10,
    filled_char: str = "█",
    empty_char: str = "░",
    show_value: bool = True,
    show_percent: bool = True,
) -> str:
    """
    Create a text-based bar graphic with value and percentage.

    Args:
        value: Current value
        max_value: Maximum value (default 127 for MIDI)
        width: Bar width in characters
        filled_char: Character for filled portion
        empty_char: Character for empty portion
        show_value: Show numeric value
        show_percent: Show percentage

    Returns:
        Formatted string like "91 [████████░░] 71%"
    """
    if max_value <= 0:
        max_value = 1

    # Clamp value
    clamped = max(0, min(value, max_value))

    # Calculate fill
    fill_count = int((clamped / max_value) * width)
    empty_count = width - fill_count

    bar = filled_char * fill_count + empty_char * empty_count
    percent = int((clamped / max_value) * 100)

    parts = []
    if show_value:
        parts.append(f"{value:3d}")
    parts.append(f"[{bar}]")
    if show_percent:
        parts.append(f"{percent:3d}%")

    return " ".join(parts)


def pan_bar(
    pan: int,
    width: int = 11,
    left_char: str = "◀",
    right_char: str = "▶",
    center_char: str = "●",
    empty_char: str = "─",
) -> str:
    """
    Create a centered pan bar graphic.

    Pan encoding (XG):
    - 0 = Random
    - 1-63 = Left (L63-L1)
    - 64 = Center
    - 65-127 = Right (R1-R63)

    Returns:
        Formatted string like "L32 [◀◀◀◀◀●─────] 25%"
    """
    if pan == 0:
        return f"Rnd [{'?' * width}]"

    # Calculate position (0-127 mapped to 0-width)
    # Center is at width//2
    center = width // 2

    # Build bar
    bar = list(empty_char * width)
    bar[center] = center_char  # Always show center marker

    if pan == 64:
        # Centered
        position_str = "  C"
        percent = 50
    elif pan < 64:
        # Left: pan 1 = full left, pan 63 = almost center
        left_amount = 64 - pan  # 1-63 -> 63-1
        pos = center - int((left_amount / 63) * center)
        if pos < 0:
            pos = 0
        bar[pos] = left_char
        position_str = f"L{left_amount:2d}"
        percent = int((pan / 127) * 100)
    else:
        # Right: pan 65 = almost center, pan 127 = full right
        right_amount = pan - 64  # 1-63
        pos = center + int((right_amount / 63) * (width - center - 1))
        if pos >= width:
            pos = width - 1
        bar[pos] = right_char
        position_str = f"R{right_amount:2d}"
        percent = int((pan / 127) * 100)

    return f"{position_str} [{''.join(bar)}] {percent:3d}%"


def hex_with_ascii(data: bytes, offset: int = 0, bytes_per_line: int = 16) -> str:
    """
    Format bytes as hex dump with ASCII representation.

    Returns:
        Multi-line string with format: "0x000: 00 01 02 ...  .ABC..."
    """
    lines = []
    for i in range(0, len(data), bytes_per_line):
        chunk = data[i : i + bytes_per_line]
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)

        # Pad hex part for alignment
        hex_padded = f"{hex_part:<{bytes_per_line * 3 - 1}}"

        lines.append(f"0x{offset + i:03X}: {hex_padded}  {ascii_part}")

    return "\n".join(lines)


def density_bar(
    used: int,
    total: int,
    width: int = 20,
    filled_char: str = "█",
    partial_char: str = "▓",
    empty_char: str = "░",
) -> str:
    """
    Create a density/usage bar with percentage.

    Returns:
        Formatted string like "[████████░░░░░░░░░░░░] 42% (128/304)"
    """
    if total <= 0:
        return f"[{empty_char * width}]  0% (0/0)"

    percent = (used / total) * 100
    fill_count = int((used / total) * width)
    empty_count = width - fill_count

    bar = filled_char * fill_count + empty_char * empty_count

    return f"[{bar}] {percent:5.1f}% ({used}/{total})"


def format_midi_value(value: int, name: str = "Value") -> str:
    """
    Format a MIDI value (0-127) with bar graphic.

    Returns:
        Formatted string like "Volume: 91 [████████░░] 71%"
    """
    return f"{name}: {value_bar(value)}"


def format_channel(raw: int, interpreted: int) -> str:
    """
    Format MIDI channel with raw and interpreted values.

    Returns:
        "Ch 10 (raw: 0x00)" or "Ch 4 (raw: 0x03)"
    """
    return f"Ch {interpreted:2d} (raw: 0x{raw:02X})"


def format_program(program: int, bank_msb: int, bank_lsb: int, name: str = "") -> str:
    """
    Format program/bank selection.

    Returns:
        "Prog 0 Bank 0/0 (Acoustic Grand Piano)"
    """
    result = f"Prog {program:3d} Bank {bank_msb}/{bank_lsb}"
    if name:
        result += f" ({name})"
    return result


def format_tempo(tempo: float, raw_bytes: Tuple[int, int]) -> str:
    """
    Format tempo with raw bytes.

    Returns:
        "120.0 BPM (raw: 0x04 0xB0)"
    """
    return f"{tempo:.1f} BPM (raw: 0x{raw_bytes[0]:02X} 0x{raw_bytes[1]:02X})"


def format_time_signature(num: int, denom: int, raw: int) -> str:
    """
    Format time signature with raw byte.

    Returns:
        "4/4 (raw: 0x1C)"
    """
    return f"{num}/{denom} (raw: 0x{raw:02X})"


def section_status(enabled: bool, pointer_hex: str) -> str:
    """
    Format section status.

    Returns:
        "[ACTIVE] ptr: 0x0020" or "[EMPTY] ptr: 0xFEFE"
    """
    status = "[green]ACTIVE[/green]" if enabled else "[dim]EMPTY[/dim]"
    return f"{status} ptr: 0x{pointer_hex.upper()}"


def byte_range_str(min_val: int, max_val: int) -> str:
    """
    Format a byte range.

    Returns:
        "0x00-0x7F" or "N/A"
    """
    if min_val == 0 and max_val == 0:
        return "N/A"
    return f"0x{min_val:02X}-0x{max_val:02X}"


def highlight_non_default(value: int, default: int, name: str = "") -> str:
    """
    Highlight if value differs from default.

    Returns:
        "[yellow]Volume: 91 (default: 100)[/yellow]" or "Volume: 100"
    """
    if value != default:
        return f"[yellow]{name}: {value} (default: {default})[/yellow]"
    return f"{name}: {value}"


def heatmap_char(density: float) -> str:
    """
    Return a character representing data density (0.0 to 1.0).

    Uses block characters: ░▒▓█
    """
    if density <= 0:
        return "░"
    elif density < 0.25:
        return "░"
    elif density < 0.50:
        return "▒"
    elif density < 0.75:
        return "▓"
    else:
        return "█"


def create_heatmap(data: bytes, width: int = 64, height: int = 8) -> str:
    """
    Create a text-based heatmap of data density.

    Divides data into width*height cells and shows density of non-zero bytes.

    Returns:
        Multi-line string representing the heatmap
    """
    if not data:
        return "No data"

    total_cells = width * height
    bytes_per_cell = max(1, len(data) // total_cells)

    lines = []
    for row in range(height):
        line = ""
        for col in range(width):
            start = (row * width + col) * bytes_per_cell
            end = start + bytes_per_cell
            chunk = data[start:end] if start < len(data) else b""

            if chunk:
                non_zero = sum(1 for b in chunk if b != 0)
                density = non_zero / len(chunk)
                line += heatmap_char(density)
            else:
                line += " "
        lines.append(line)

    return "\n".join(lines)
