"""
Map command - visual file structure map.
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


# File regions: start, end, name, description, color, expected_fill
REGIONS: List[Tuple[int, int, str, str, str, int]] = [
    (0x000, 0x010, "Header", "File magic YQ7PAT V1.00", "bright_blue", -1),
    (0x010, 0x012, "Pattern Info", "Pattern number and flags", "cyan", -1),
    (0x012, 0x030, "Reserved 1", "Unknown/reserved area", "dim", 0x00),
    (0x030, 0x032, "Size Marker", "File size indicator", "cyan", -1),
    (0x032, 0x100, "Reserved 2", "Unknown/reserved area", "dim", 0x00),
    (0x100, 0x120, "Section Pointers", "16 section pointer entries", "green", -1),
    (0x120, 0x180, "Section Data", "Section configuration data", "green", -1),
    (0x180, 0x190, "Tempo/Timing", "Tempo, time signature", "yellow", -1),
    (0x190, 0x1A0, "Channels", "MIDI channel assignments", "magenta", -1),
    (0x1A0, 0x1DC, "Reserved 3", "Unknown/reserved area", "dim", 0x00),
    (0x1DC, 0x200, "Track Config", "Track numbers and flags", "magenta", -1),
    (0x200, 0x220, "Reserved 4", "Unknown/reserved area", "dim", 0x00),
    (0x220, 0x250, "Volume Table", "Track volume values", "blue", -1),
    (0x250, 0x270, "Reverb Table", "Reverb send levels", "blue", -1),
    (0x270, 0x2C0, "Pan Table", "Pan positions", "blue", -1),
    (0x2C0, 0x360, "Table 3", "Unknown purpose table", "dim", -1),
    (0x360, 0x678, "Phrase Data", "Pattern phrase data", "red", -1),
    (0x678, 0x870, "Sequence Data", "Event/timing data", "red", -1),
    (0x870, 0x880, "Template Pad", "Template area padding", "cyan", -1),
    (0x880, 0x900, "Template Name", "Pattern name area", "cyan", -1),
    (0x900, 0x9C0, "Pattern Map", "Pattern mapping data", "green", -1),
    (0x9C0, 0xB10, "Fill Area", "Filler bytes (0xFE)", "dim", 0xFE),
    (0xB10, 0xC00, "Pad Area", "Padding bytes (0xF8)", "dim", 0xF8),
]


def analyze_region_density(
    data: bytes, start: int, end: int, expected_fill: int = -1
) -> Tuple[int, int, float]:
    """
    Analyze data density in a region.

    Returns:
        (non_zero_count, meaningful_count, density_percent)
    """
    region_data = data[start:end]
    size = len(region_data)

    if size == 0:
        return 0, 0, 0.0

    # Filler bytes to ignore
    filler = {0x00, 0x20, 0x40, 0x7F, 0xFE, 0xF8}
    if expected_fill >= 0:
        filler.add(expected_fill)

    non_zero = sum(1 for b in region_data if b != 0x00)
    meaningful = sum(1 for b in region_data if b not in filler)
    density = (meaningful / size) * 100

    return non_zero, meaningful, density


def create_density_bar(density: float, width: int = 20) -> Text:
    """Create a colored density bar."""
    fill_count = int((density / 100) * width)
    empty_count = width - fill_count

    text = Text()

    # Color based on density
    if density == 0:
        color = "dim"
    elif density < 25:
        color = "blue"
    elif density < 50:
        color = "cyan"
    elif density < 75:
        color = "yellow"
    else:
        color = "green"

    text.append("█" * fill_count, style=color)
    text.append("░" * empty_count, style="dim")

    return text


def create_visual_map(data: bytes, width: int = 64) -> str:
    """
    Create a visual character map of the entire file.

    Each character represents ~48 bytes (3072 / 64).
    """
    bytes_per_char = len(data) // width
    if bytes_per_char == 0:
        bytes_per_char = 1

    chars = []
    for i in range(width):
        start = i * bytes_per_char
        end = start + bytes_per_char
        chunk = data[start:end]

        # Calculate density
        filler = {0x00, 0x20, 0x40, 0x7F, 0xFE, 0xF8}
        meaningful = sum(1 for b in chunk if b not in filler)
        density = meaningful / len(chunk) if chunk else 0

        # Choose character
        if density == 0:
            chars.append("░")
        elif density < 0.25:
            chars.append("▒")
        elif density < 0.5:
            chars.append("▓")
        else:
            chars.append("█")

    return "".join(chars)


@app.command()
def map(
    file: Path = typer.Argument(..., help="Q7P file to map"),
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Show per-region hex preview"),
) -> None:
    """
    Visual map of Q7P file structure and data density.

    Shows:
    - All file regions with their offsets and sizes
    - Data density bar for each region
    - Percentage of meaningful (non-filler) bytes
    - Visual overview of entire file

    Examples:

        qyconv map pattern.Q7P

        qyconv map pattern.Q7P --detailed
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

    # Header
    console.print(
        Panel(
            f"[bold]File:[/bold] {file}\n"
            f"[bold]Size:[/bold] {len(data)} bytes (0x{len(data):03X})\n"
            f"[bold]Expected:[/bold] 3072 bytes (0xC00)",
            title="[bold]Q7P File Structure Map[/bold]",
            border_style="blue",
        )
    )
    console.print()

    # Visual overview
    visual_map = create_visual_map(data, width=64)
    console.print("[bold]File Overview[/bold] (each char = ~48 bytes, █=data, ░=empty)")
    console.print(f"[dim]0x000[/dim] {visual_map} [dim]0xBFF[/dim]")
    console.print()

    # Main table
    table = Table(
        title="File Regions",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Offset", style="dim", width=14)
    table.add_column("Region", width=16)
    table.add_column("Size", width=8)
    table.add_column("Density", width=22)
    table.add_column("%", width=6)
    table.add_column("Status", width=12)

    total_meaningful = 0
    total_size = 0

    for start, end, name, desc, color, expected_fill in REGIONS:
        size = end - start
        non_zero, meaningful, density = analyze_region_density(data, start, end, expected_fill)

        total_meaningful += meaningful
        total_size += size

        # Create density bar
        bar = create_density_bar(density, width=16)

        # Status
        if density == 0:
            status = "[dim]Empty[/dim]"
        elif density < 10:
            status = "[blue]Sparse[/blue]"
        elif density < 50:
            status = "[cyan]Partial[/cyan]"
        elif density < 90:
            status = "[yellow]Used[/yellow]"
        else:
            status = "[green]Full[/green]"

        # Offset range
        offset_str = f"0x{start:03X}-0x{end - 1:03X}"

        table.add_row(
            offset_str,
            Text(name, style=color),
            f"{size}",
            bar,
            f"{density:5.1f}%",
            status,
        )

    console.print(table)

    # Summary
    overall_density = (total_meaningful / total_size * 100) if total_size > 0 else 0
    console.print()
    console.print(
        f"[bold]Overall Data Density:[/bold] {overall_density:.1f}% ({total_meaningful}/{total_size} bytes)"
    )

    # Detailed view
    if detailed:
        console.print()
        console.print("[bold]Region Details (first 16 bytes of each)[/bold]")
        console.print()

        for start, end, name, desc, color, expected_fill in REGIONS:
            preview = data[start : min(start + 16, end)]
            hex_str = " ".join(f"{b:02X}" for b in preview)
            ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in preview)

            console.print(f"[{color}]{name}[/{color}] (0x{start:03X}): {hex_str}")
            console.print(f"[dim]  {desc}[/dim]")
            console.print(f"[dim]  ASCII: {ascii_str}[/dim]")
            console.print()


if __name__ == "__main__":
    app()
