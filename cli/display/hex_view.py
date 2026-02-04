"""
Hex dump display utilities.
"""

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()


def display_hex_dump(
    data: bytes,
    title: str = "Hex Dump",
    start_offset: int = 0,
    bytes_per_line: int = 16,
    max_lines: int = 32,
) -> None:
    """Display formatted hex dump with Rich."""

    lines = []
    end = min(len(data), max_lines * bytes_per_line)

    for offset in range(0, end, bytes_per_line):
        chunk = data[offset : offset + bytes_per_line]

        # Hex part
        hex_parts = []
        for i, b in enumerate(chunk):
            if i == 8:
                hex_parts.append(" ")  # Extra space at midpoint
            hex_parts.append(f"{b:02X}")
        hex_str = " ".join(hex_parts)

        # ASCII part
        ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)

        # Address
        addr = start_offset + offset

        lines.append(
            f"[dim]{addr:08X}[/dim]  {hex_str:<{bytes_per_line * 3 + 2}}  [cyan]{ascii_str}[/cyan]"
        )

    if len(data) > end:
        remaining = len(data) - end
        lines.append(f"[dim]... {remaining} more bytes ...[/dim]")

    content = "\n".join(lines)
    console.print(Panel(content, title=title, border_style="blue", expand=False))


def display_hex_comparison(
    data1: bytes,
    data2: bytes,
    title1: str = "File 1",
    title2: str = "File 2",
    bytes_per_line: int = 16,
) -> None:
    """Display side-by-side hex comparison highlighting differences."""

    max_len = max(len(data1), len(data2))
    lines = []

    for offset in range(0, min(max_len, 256), bytes_per_line):
        chunk1 = data1[offset : offset + bytes_per_line] if offset < len(data1) else b""
        chunk2 = data2[offset : offset + bytes_per_line] if offset < len(data2) else b""

        # Build hex strings with diff highlighting
        hex1_parts = []
        hex2_parts = []

        for i in range(bytes_per_line):
            b1 = chunk1[i] if i < len(chunk1) else None
            b2 = chunk2[i] if i < len(chunk2) else None

            if b1 is None:
                hex1_parts.append("[dim]--[/dim]")
            elif b2 is None or b1 != b2:
                hex1_parts.append(f"[red]{b1:02X}[/red]")
            else:
                hex1_parts.append(f"{b1:02X}")

            if b2 is None:
                hex2_parts.append("[dim]--[/dim]")
            elif b1 is None or b1 != b2:
                hex2_parts.append(f"[green]{b2:02X}[/green]")
            else:
                hex2_parts.append(f"{b2:02X}")

        hex1_str = " ".join(hex1_parts)
        hex2_str = " ".join(hex2_parts)

        lines.append(f"[dim]{offset:04X}[/dim] | {hex1_str} | {hex2_str}")

    header = f"[bold]Offset | {title1:<{bytes_per_line * 3}} | {title2}[/bold]"
    console.print(header)
    console.print("-" * (10 + bytes_per_line * 6 + 6))

    for line in lines:
        console.print(line)
