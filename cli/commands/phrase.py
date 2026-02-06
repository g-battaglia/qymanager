"""
Phrase command - detailed phrase/sequence data analysis.
"""

from collections import Counter
from pathlib import Path
from typing import List, Tuple

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from qymanager.analysis.q7p_analyzer import Q7PAnalyzer
from cli.display.formatters import density_bar, create_heatmap

console = Console()
app = typer.Typer()


# MIDI note names for interpretation
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_note_name(note: int) -> str:
    """Convert MIDI note number to name (e.g., 60 -> C4)."""
    if note < 0 or note > 127:
        return f"?{note}"
    octave = (note // 12) - 1
    name = NOTE_NAMES[note % 12]
    return f"{name}{octave}"


def find_potential_events(data: bytes) -> List[Tuple[int, str, str]]:
    """
    Attempt to find potential MIDI-like events in data.

    Returns list of (offset, type, description) tuples.
    """
    events = []
    i = 0

    while i < len(data) - 2:
        b0, b1, b2 = (
            data[i],
            data[i + 1] if i + 1 < len(data) else 0,
            data[i + 2] if i + 2 < len(data) else 0,
        )

        # Skip filler bytes
        if b0 in (0x00, 0xFE, 0xF8, 0x40):
            i += 1
            continue

        # Pattern: Note-like value followed by velocity-like value
        if 0x24 <= b0 <= 0x60 and 0x20 <= b1 <= 0x7F:
            note_name = midi_note_name(b0)
            events.append((i, "NOTE?", f"{note_name} vel={b1}"))
            i += 2
            continue

        # Pattern: Delta time followed by event
        if b0 < 0x80 and b1 >= 0x24 and b1 <= 0x7F:
            events.append((i, "DELTA?", f"delta={b0} data=0x{b1:02X}"))
            i += 1
            continue

        # Unknown but non-filler
        if b0 not in (0x00, 0x20, 0x40, 0x7F, 0xFE, 0xF8):
            events.append((i, "DATA", f"0x{b0:02X}"))

        i += 1

    return events


def analyze_byte_patterns(data: bytes) -> dict:
    """Analyze byte patterns and frequencies."""
    if not data:
        return {}

    counter = Counter(data)
    filler = {0x00, 0x20, 0x40, 0x7F, 0xFE, 0xF8}

    return {
        "total_bytes": len(data),
        "unique_values": len(counter),
        "non_zero": sum(1 for b in data if b != 0x00),
        "non_filler": sum(1 for b in data if b not in filler),
        "top_values": counter.most_common(10),
        "min_value": min(data) if data else 0,
        "max_value": max(data) if data else 0,
        "note_range_count": sum(1 for b in data if 0x24 <= b <= 0x60),
        "velocity_range_count": sum(1 for b in data if 0x40 <= b <= 0x7F),
    }


def display_hex_grid(data: bytes, offset: int, title: str, width: int = 16) -> None:
    """Display hex data in a grid with offset and ASCII."""
    console.print(f"[bold]{title}[/bold]")
    console.print(f"[dim]Offset: 0x{offset:03X}, Size: {len(data)} bytes[/dim]")
    console.print()

    # Header
    header = "       " + " ".join(f"{i:02X}" for i in range(width)) + "  ASCII"
    console.print(f"[dim]{header}[/dim]")
    console.print("─" * (7 + width * 3 + 2 + width))

    for i in range(0, len(data), width):
        chunk = data[i : i + width]
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        hex_part = f"{hex_part:<{width * 3 - 1}}"

        # Color non-filler bytes
        text = Text()
        text.append(f"0x{offset + i:03X}: ", style="dim")

        for b in chunk:
            if b == 0x00:
                text.append("00 ", style="dim")
            elif b in (0xFE, 0xF8, 0x40, 0x20):
                text.append(f"{b:02X} ", style="dim cyan")
            elif 0x24 <= b <= 0x60:  # Note range
                text.append(f"{b:02X} ", style="bold green")
            elif 0x40 <= b <= 0x7F:  # Velocity range
                text.append(f"{b:02X} ", style="yellow")
            else:
                text.append(f"{b:02X} ", style="white")

        # Pad if short line
        if len(chunk) < width:
            text.append("   " * (width - len(chunk)))

        text.append(" ")

        # ASCII
        for b in chunk:
            if 32 <= b < 127:
                text.append(chr(b), style="green")
            else:
                text.append(".", style="dim")

        console.print(text)

    console.print()


def display_pattern_analysis(data: bytes, title: str) -> None:
    """Display pattern/frequency analysis."""
    stats = analyze_byte_patterns(data)

    if not stats:
        console.print(f"[yellow]No data to analyze for {title}[/yellow]")
        return

    console.print(f"[bold]{title} Statistics[/bold]")

    table = Table(box=box.SIMPLE, show_header=False)
    table.add_column("Metric", style="cyan", width=24)
    table.add_column("Value", width=40)

    table.add_row("Total Bytes", str(stats["total_bytes"]))
    table.add_row("Unique Values", str(stats["unique_values"]))

    # Non-zero bar
    nz_density = density_bar(stats["non_zero"], stats["total_bytes"], width=20)
    table.add_row("Non-Zero Bytes", f"{stats['non_zero']} {nz_density}")

    # Meaningful data bar
    mf_density = density_bar(stats["non_filler"], stats["total_bytes"], width=20)
    table.add_row("Meaningful Bytes", f"{stats['non_filler']} {mf_density}")

    table.add_row("Value Range", f"0x{stats['min_value']:02X} - 0x{stats['max_value']:02X}")
    table.add_row("Note-like Values (0x24-0x60)", str(stats["note_range_count"]))
    table.add_row("Velocity-like Values (0x40-0x7F)", str(stats["velocity_range_count"]))

    console.print(table)

    # Top values histogram
    console.print()
    console.print("[bold]Top 10 Byte Values:[/bold]")
    hist_table = Table(box=box.SIMPLE, show_header=True, header_style="dim")
    hist_table.add_column("Value", width=10)
    hist_table.add_column("Count", width=8)
    hist_table.add_column("Bar", width=30)
    hist_table.add_column("Note?", width=8)

    max_count = stats["top_values"][0][1] if stats["top_values"] else 1

    for value, count in stats["top_values"]:
        bar_width = int((count / max_count) * 25)
        bar = "█" * bar_width

        # Interpret as note if in range
        note_str = ""
        if 0x00 <= value <= 0x7F:
            note_str = midi_note_name(value)

        style = "dim" if value in (0x00, 0x40, 0x7F, 0xFE, 0xF8) else "white"

        hist_table.add_row(
            f"0x{value:02X} ({value:3d})",
            str(count),
            Text(bar, style="green"),
            note_str,
        )

    console.print(hist_table)


def display_potential_events(data: bytes, title: str, max_events: int = 50) -> None:
    """Display potential MIDI events found in data."""
    events = find_potential_events(data)

    if not events:
        console.print(f"[yellow]No potential events detected in {title}[/yellow]")
        return

    console.print(f"[bold]{title} - Potential Events[/bold]")
    console.print(
        f"[dim]Found {len(events)} potential events (showing first {min(len(events), max_events)})[/dim]"
    )
    console.print()

    table = Table(box=box.SIMPLE, show_header=True, header_style="dim")
    table.add_column("Offset", width=8)
    table.add_column("Type", width=10)
    table.add_column("Interpretation", width=30)
    table.add_column("Raw", width=20)

    for offset, event_type, description in events[:max_events]:
        raw_bytes = " ".join(f"{data[offset + i]:02X}" for i in range(min(4, len(data) - offset)))

        type_style = {
            "NOTE?": "green",
            "DELTA?": "yellow",
            "DATA": "dim",
        }.get(event_type, "white")

        table.add_row(
            f"0x{offset:03X}",
            Text(event_type, style=type_style),
            description,
            raw_bytes,
        )

    console.print(table)

    if len(events) > max_events:
        console.print(f"[dim]... and {len(events) - max_events} more events[/dim]")


@app.command()
def phrase(
    file: Path = typer.Argument(..., help="Q7P file to analyze"),
    area: str = typer.Option(
        "both", "--area", "-a", help="Area to analyze: phrase, sequence, or both"
    ),
    hex_dump: bool = typer.Option(True, "--hex/--no-hex", help="Show hex dump"),
    events: bool = typer.Option(True, "--events/--no-events", help="Attempt MIDI event detection"),
    heatmap: bool = typer.Option(False, "--heatmap", "-m", help="Show data density heatmap"),
    limit: int = typer.Option(256, "--limit", "-l", help="Limit hex dump to N bytes (0=all)"),
) -> None:
    """
    Analyze phrase and sequence data areas in detail.

    Phrase area (0x360-0x677, 792 bytes): Contains pattern phrase data
    Sequence area (0x678-0x86F, 504 bytes): Contains event/timing data

    Provides:
    - Statistical analysis (density, unique values, patterns)
    - Byte frequency histogram
    - Potential MIDI event detection
    - Full hex dump with interpretation
    - Data density heatmap

    Examples:

        qymanager phrase pattern.Q7P

        qymanager phrase pattern.Q7P --area sequence

        qymanager phrase pattern.Q7P --heatmap --limit 0
    """
    if not file.exists():
        console.print(f"[red]Error: File not found: {file}[/red]")
        raise typer.Exit(1)

    if file.suffix.lower() != ".q7p":
        console.print(f"[red]Error: Only Q7P files supported: {file}[/red]")
        raise typer.Exit(1)

    # Analyze file
    analyzer = Q7PAnalyzer()
    analysis = analyzer.analyze_file(str(file))
    data = analyzer.data

    # Extract areas
    phrase_data = data[analyzer.PHRASE_START : analyzer.PHRASE_START + analyzer.PHRASE_SIZE]
    sequence_data = data[analyzer.SEQUENCE_START : analyzer.SEQUENCE_START + analyzer.SEQUENCE_SIZE]

    # Header
    console.print(
        Panel(
            f"[bold]File:[/bold] {file}\n"
            f"[bold]Pattern:[/bold] {analysis.pattern_name or 'N/A'}\n"
            f"[bold]Phrase Area:[/bold] 0x{analyzer.PHRASE_START:03X}-0x{analyzer.PHRASE_START + analyzer.PHRASE_SIZE - 1:03X} ({analyzer.PHRASE_SIZE} bytes)\n"
            f"[bold]Sequence Area:[/bold] 0x{analyzer.SEQUENCE_START:03X}-0x{analyzer.SEQUENCE_START + analyzer.SEQUENCE_SIZE - 1:03X} ({analyzer.SEQUENCE_SIZE} bytes)",
            title="[bold]Phrase/Sequence Analysis[/bold]",
            border_style="red",
        )
    )
    console.print()

    # Determine which areas to show
    show_phrase = area.lower() in ("phrase", "both")
    show_sequence = area.lower() in ("sequence", "both")

    if not show_phrase and not show_sequence:
        console.print(f"[red]Invalid area: {area}. Use 'phrase', 'sequence', or 'both'.[/red]")
        raise typer.Exit(1)

    # Phrase area
    if show_phrase:
        console.print(Panel.fit("[bold red]PHRASE DATA AREA[/bold red]", border_style="red"))
        console.print()

        display_pattern_analysis(phrase_data, "Phrase Area")
        console.print()

        if heatmap:
            console.print("[bold]Phrase Data Heatmap:[/bold]")
            console.print(f"[dim](Each char = ~12 bytes, █=data, ░=empty)[/dim]")
            hm = create_heatmap(phrase_data, width=66, height=3)
            console.print(hm)
            console.print()

        if events:
            display_potential_events(phrase_data, "Phrase Area")
            console.print()

        if hex_dump:
            dump_size = limit if limit > 0 else len(phrase_data)
            display_hex_grid(
                phrase_data[:dump_size],
                analyzer.PHRASE_START,
                f"Phrase Hex Dump (first {dump_size} bytes)",
            )

    # Sequence area
    if show_sequence:
        console.print(Panel.fit("[bold red]SEQUENCE DATA AREA[/bold red]", border_style="red"))
        console.print()

        display_pattern_analysis(sequence_data, "Sequence Area")
        console.print()

        if heatmap:
            console.print("[bold]Sequence Data Heatmap:[/bold]")
            console.print(f"[dim](Each char = ~8 bytes, █=data, ░=empty)[/dim]")
            hm = create_heatmap(sequence_data, width=63, height=2)
            console.print(hm)
            console.print()

        if events:
            display_potential_events(sequence_data, "Sequence Area")
            console.print()

        if hex_dump:
            dump_size = limit if limit > 0 else len(sequence_data)
            display_hex_grid(
                sequence_data[:dump_size],
                analyzer.SEQUENCE_START,
                f"Sequence Hex Dump (first {dump_size} bytes)",
            )


if __name__ == "__main__":
    app()
