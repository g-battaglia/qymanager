"""
Dump command - annotated hex dump of Q7P file.
"""

from pathlib import Path
from typing import List, Tuple

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

console = Console()
app = typer.Typer()


# File regions with start, end, name, description, and color
REGIONS: List[Tuple[int, int, str, str, str]] = [
    (0x000, 0x010, "HEADER", "File magic/version", "bright_blue"),
    (0x010, 0x012, "PAT_INFO", "Pattern number/flags", "cyan"),
    (0x012, 0x030, "RESERVED_1", "Unknown/reserved", "dim"),
    (0x030, 0x032, "SIZE_MARK", "Size marker", "cyan"),
    (0x032, 0x100, "RESERVED_2", "Unknown/reserved", "dim"),
    (0x100, 0x120, "SECT_PTR", "Section pointers (16x2 bytes)", "green"),
    (0x120, 0x180, "SECT_DATA", "Section configuration", "green"),
    (0x180, 0x190, "TEMPO", "Tempo and timing", "yellow"),
    (0x190, 0x1A0, "CHANNELS", "MIDI channel assignments", "magenta"),
    (0x1A0, 0x1DC, "RESERVED_3", "Unknown/reserved", "dim"),
    (0x1DC, 0x200, "TRK_CFG", "Track config/flags", "magenta"),
    (0x200, 0x220, "RESERVED_4", "Unknown/reserved", "dim"),
    (0x220, 0x250, "VOLUMES", "Volume table", "blue"),
    (0x250, 0x270, "REVERB", "Reverb send table", "blue"),
    (0x270, 0x2C0, "PAN", "Pan table", "blue"),
    (0x2C0, 0x360, "TABLE_3", "Unknown table", "dim"),
    (0x360, 0x678, "PHRASE", "Phrase data", "red"),
    (0x678, 0x870, "SEQUENCE", "Sequence/event data", "red"),
    (0x870, 0x880, "TMPL_PAD", "Template padding", "cyan"),
    (0x880, 0x900, "TMPL_NAME", "Template/pattern name", "cyan"),
    (0x900, 0x9C0, "PAT_MAP", "Pattern mapping", "green"),
    (0x9C0, 0xB10, "FILL", "Fill area (0xFE)", "dim"),
    (0xB10, 0xC00, "PAD", "Padding area (0xF8)", "dim"),
]


def get_region_for_offset(offset: int) -> Tuple[str, str, str]:
    """Get region name, description, and color for an offset."""
    for start, end, name, desc, color in REGIONS:
        if start <= offset < end:
            return name, desc, color
    return "UNKNOWN", "Unknown region", "white"


def format_hex_line(
    data: bytes, offset: int, bytes_per_line: int = 16, highlight_non_default: bool = True
) -> Text:
    """
    Format a single line of hex dump with colors and annotations.

    Returns Rich Text object with colored output.
    """
    region_name, region_desc, region_color = get_region_for_offset(offset)

    text = Text()

    # Offset
    text.append(f"0x{offset:03X} ", style="dim")

    # Region tag
    text.append(f"[{region_name:10s}] ", style=region_color)

    # Hex bytes
    for i, byte in enumerate(data):
        # Highlight non-filler bytes
        if byte in (0x00, 0xFE, 0xF8, 0x20, 0x40):
            style = "dim"
        elif byte == 0x7F:
            style = "dim cyan"
        else:
            style = "bold white"

        text.append(f"{byte:02X}", style=style)
        text.append(" ")

    # Pad if less than full line
    if len(data) < bytes_per_line:
        text.append("   " * (bytes_per_line - len(data)))

    # ASCII representation
    text.append(" ", style="dim")
    for byte in data:
        if 32 <= byte < 127:
            text.append(chr(byte), style="green")
        elif byte == 0x00:
            text.append(".", style="dim")
        elif byte in (0xFE, 0xF8):
            text.append("·", style="dim")
        else:
            text.append(".", style="yellow")

    return text


def create_legend() -> Table:
    """Create a legend for the hex dump colors."""
    table = Table(title="Legend", box=box.SIMPLE, show_header=False, expand=False)
    table.add_column("Region", width=12)
    table.add_column("Description", width=30)

    for start, end, name, desc, color in REGIONS:
        size = end - start
        table.add_row(
            Text(name, style=color),
            f"{desc} ({size} bytes, 0x{start:03X}-0x{end - 1:03X})",
        )

    return table


@app.command()
def dump(
    file: Path = typer.Argument(..., help="Q7P file to dump"),
    start: int = typer.Option(0, "--start", "-s", help="Start offset (hex or decimal)"),
    length: int = typer.Option(0, "--length", "-l", help="Number of bytes (0=all)"),
    width: int = typer.Option(16, "--width", "-w", help="Bytes per line"),
    no_legend: bool = typer.Option(False, "--no-legend", help="Hide the legend"),
    region: str = typer.Option(
        "", "--region", "-r", help="Show only specific region (e.g., PHRASE, TEMPO)"
    ),
    non_zero: bool = typer.Option(
        False, "--non-zero", "-n", help="Show only lines with non-zero/non-filler data"
    ),
) -> None:
    """
    Annotated hex dump of a Q7P pattern file.

    Shows the complete file structure with:
    - Color-coded regions (header, sections, tracks, phrases, etc.)
    - Highlighted non-default values
    - ASCII representation
    - Region annotations

    Examples:

        qyconv dump pattern.Q7P

        qyconv dump pattern.Q7P --region PHRASE

        qyconv dump pattern.Q7P --start 0x360 --length 128

        qyconv dump pattern.Q7P --non-zero
    """
    if not file.exists():
        console.print(f"[red]Error: File not found: {file}[/red]")
        raise typer.Exit(1)

    if file.suffix.lower() != ".q7p":
        console.print(f"[red]Error: Only Q7P files supported: {file}[/red]")
        raise typer.Exit(1)

    # Read file
    with open(file, "rb") as f:
        data = f.read()

    # Filter by region if specified
    if region:
        region_upper = region.upper()
        found = False
        for r_start, r_end, r_name, r_desc, r_color in REGIONS:
            if r_name == region_upper:
                start = r_start
                length = r_end - r_start
                found = True
                console.print(f"[{r_color}]Showing region: {r_name} - {r_desc}[/{r_color}]")
                console.print(
                    f"[dim]Offset: 0x{r_start:03X} - 0x{r_end - 1:03X} ({length} bytes)[/dim]\n"
                )
                break
        if not found:
            console.print(f"[red]Unknown region: {region}[/red]")
            console.print("Available regions: " + ", ".join(r[2] for r in REGIONS))
            raise typer.Exit(1)

    # Determine range
    if length == 0:
        length = len(data) - start

    end = min(start + length, len(data))

    # Show legend first
    if not no_legend and not region:
        console.print(create_legend())
        console.print()

    # Header
    console.print(
        Panel(
            f"[bold]File:[/bold] {file}\n"
            f"[bold]Size:[/bold] {len(data)} bytes\n"
            f"[bold]Showing:[/bold] 0x{start:03X} - 0x{end - 1:03X} ({end - start} bytes)",
            title="[bold]Q7P Hex Dump[/bold]",
            border_style="blue",
        )
    )
    console.print()

    # Column headers
    header = Text()
    header.append("OFFSET ", style="dim")
    header.append(f"{'REGION':12s} ", style="dim")
    header.append(" ".join(f"{i:02X}" for i in range(width)), style="dim")
    header.append("  ASCII", style="dim")
    console.print(header)
    console.print("─" * (7 + 13 + width * 3 + 2 + width))

    # Dump lines
    filler_bytes = {0x00, 0xFE, 0xF8, 0x20, 0x40, 0x7F}
    lines_shown = 0

    for offset in range(start, end, width):
        chunk = data[offset : offset + width]

        # Skip filler-only lines if --non-zero
        if non_zero:
            if all(b in filler_bytes for b in chunk):
                continue

        line = format_hex_line(chunk, offset, width)
        console.print(line)
        lines_shown += 1

    console.print()
    console.print(f"[dim]Total: {lines_shown} lines displayed[/dim]")


if __name__ == "__main__":
    app()
