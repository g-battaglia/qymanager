"""
Sections command - detailed section information display.
"""

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from qymanager.analysis.q7p_analyzer import Q7PAnalyzer
from cli.display.formatters import hex_with_ascii, density_bar

console = Console()
app = typer.Typer()

SECTION_NAMES = [
    "Intro",
    "Main A",
    "Main B",
    "Fill AB",
    "Fill BA",
    "Ending",
    "Main C",
    "Main D",
    "Intro 2",
    "Ending 2",
    "Break",
]

SECTION_DESCRIPTIONS = [
    "Introduction - played at song start",
    "Main pattern A - primary verse/chorus",
    "Main pattern B - variation pattern",
    "Fill A→B - transition from A to B",
    "Fill B→A - transition from B to A",
    "Ending - played at song end",
    "Main pattern C - additional variation",
    "Main pattern D - additional variation",
    "Intro 2 - alternate introduction",
    "Ending 2 - alternate ending",
    "Break - break pattern",
]


def display_section_detail(
    analyzer: Q7PAnalyzer,
    section,
    data: bytes,
    show_hex: bool = True,
) -> None:
    """Display detailed info for a single section."""
    # Section header
    status = "[green]ACTIVE[/green]" if section.enabled else "[red]EMPTY[/red]"

    desc = SECTION_DESCRIPTIONS[section.index] if section.index < len(SECTION_DESCRIPTIONS) else ""

    header = f"[bold]{section.name}[/bold]\n"
    header += f"{desc}\n"
    header += f"Status: {status}  Pointer: 0x{section.pointer_hex.upper()}"

    border_color = "green" if section.enabled else "dim"
    console.print(
        Panel(header, title=f"Section {section.index}", border_style=border_color, expand=False)
    )

    # Config bytes table
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Property", style="cyan", width=24)
    table.add_column("Value", width=50)

    # Pointer info
    table.add_row("Pointer Value", f"0x{section.pointer:04X} ({section.pointer})")
    table.add_row("Pointer Hex", section.pointer_hex.upper())

    # Section offset in file
    section_data_offset = 0x120 + (section.index * 16)
    table.add_row("Config Data Offset", f"0x{section_data_offset:03X}")
    table.add_row("Config Data Size", "16 bytes")

    # Phrase data location
    table.add_row("Phrase Data Offset", f"0x{section.phrase_data_offset:03X}")
    table.add_row("Phrase Data Size", f"{section.phrase_data_size} bytes")

    # Time signature (from section or global)
    table.add_row("Time Signature", f"{section.time_signature[0]}/{section.time_signature[1]}")
    table.add_row("Length (measures)", str(section.length_measures))

    console.print(table)

    if show_hex and section.raw_config:
        # Config hex dump
        console.print()
        console.print("[bold]Configuration Data (16 bytes):[/bold]")
        hex_str = " ".join(f"{b:02X}" for b in section.raw_config)
        ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in section.raw_config)
        console.print(f"  {hex_str}")
        console.print(f"  [dim]{ascii_str}[/dim]")

        # Interpret config bytes
        console.print()
        console.print("[bold]Config Byte Interpretation:[/bold]")
        cfg = section.raw_config
        interp_table = Table(box=box.SIMPLE, show_header=True, header_style="dim")
        interp_table.add_column("Offset", width=8)
        interp_table.add_column("Value", width=10)
        interp_table.add_column("Possible Meaning", width=40)

        meanings = [
            "Section type/flags",
            "Unknown",
            "Unknown",
            "Unknown",
            "Unknown",
            "Unknown",
            "Timing/length?",
            "Timing/length?",
            "Event data?",
            "Event data?",
            "Track enable?",
            "Track enable?",
            "Unknown",
            "Unknown",
            "Unknown",
            "Unknown",
        ]

        for i, b in enumerate(cfg):
            meaning = meanings[i] if i < len(meanings) else "Unknown"
            style = "bold" if b not in (0x00, 0x40, 0xFE) else "dim"
            interp_table.add_row(f"+{i:02X}", f"0x{b:02X} ({b:3d})", Text(meaning, style=style))

        console.print(interp_table)

    # Track enable status for this section
    if section.tracks:
        console.print()
        console.print("[bold]Track Status in this Section:[/bold]")
        track_table = Table(box=box.SIMPLE, show_header=True, header_style="dim")
        track_table.add_column("Track", width=8)
        track_table.add_column("Status", width=10)
        track_table.add_column("Channel", width=8)

        for track in section.tracks:
            status = "[green]On[/green]" if track.enabled else "[dim]Off[/dim]"
            track_table.add_row(track.name, status, f"Ch {track.channel}")

        console.print(track_table)

    console.print()


def display_sections_summary(analysis) -> None:
    """Display summary table of all sections."""
    table = Table(
        title="Sections Overview",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("#", style="dim", width=3)
    table.add_column("Name", width=12)
    table.add_column("Status", width=10)
    table.add_column("Pointer", width=10)
    table.add_column("Config Preview", width=50)

    for section in analysis.sections:
        status = "[green]Active[/green]" if section.enabled else "[dim]Empty[/dim]"
        config_hex = " ".join(f"{b:02X}" for b in section.raw_config[:8])
        config_hex += " ..."

        table.add_row(
            str(section.index),
            section.name,
            status,
            f"0x{section.pointer_hex.upper()}",
            config_hex,
        )

    console.print(table)

    # Stats
    active = sum(1 for s in analysis.sections if s.enabled)
    console.print(f"\n[bold]Active sections:[/bold] {active} of {len(analysis.sections)}")


@app.command()
def sections(
    file: Path = typer.Argument(..., help="Q7P file to analyze"),
    section: int = typer.Option(-1, "--section", "-s", help="Show specific section (0-5), -1=all"),
    summary: bool = typer.Option(False, "--summary", help="Show summary table only"),
    no_hex: bool = typer.Option(False, "--no-hex", help="Hide hex dumps"),
    active_only: bool = typer.Option(False, "--active", "-a", help="Show only active sections"),
) -> None:
    """
    Display detailed section information.

    Shows for each section (Intro, Main A, Main B, Fill AB, Fill BA, Ending):
    - Status (active/empty)
    - Pointer values and offsets
    - Configuration data with interpretation
    - Track enable status per section
    - Phrase data location

    Examples:

        qymanager sections pattern.Q7P

        qymanager sections pattern.Q7P --section 0

        qymanager sections pattern.Q7P --active --summary
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

    # Header
    active_count = sum(1 for s in analysis.sections if s.enabled)
    console.print(
        Panel(
            f"[bold]File:[/bold] {file}\n"
            f"[bold]Pattern:[/bold] {analysis.pattern_name or 'N/A'}\n"
            f"[bold]Active Sections:[/bold] {active_count} of {len(analysis.sections)}",
            title="[bold]Section Information[/bold]",
            border_style="blue",
        )
    )
    console.print()

    if summary:
        display_sections_summary(analysis)
        return

    # Filter sections
    sections_to_show = analysis.sections

    if section >= 0:
        if 0 <= section < len(analysis.sections):
            sections_to_show = [analysis.sections[section]]
        else:
            console.print(
                f"[red]Invalid section number: {section}. Use 0-{len(analysis.sections) - 1}.[/red]"
            )
            raise typer.Exit(1)

    if active_only:
        sections_to_show = [s for s in sections_to_show if s.enabled]
        if not sections_to_show:
            console.print("[yellow]No active sections found.[/yellow]")
            return

    # Display each section
    for sect in sections_to_show:
        display_section_detail(analyzer, sect, data, show_hex=not no_hex)


if __name__ == "__main__":
    app()
