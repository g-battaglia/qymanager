"""
Info command - display complete pattern information.
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from cli.display.tables import display_q7p_info, display_syx_info

console = Console()
app = typer.Typer()


def display_full_q7p_info(filepath: str) -> None:
    """Display complete Q7P analysis using all available commands."""
    from qyconv.analysis.q7p_analyzer import Q7PAnalyzer
    from cli.commands.tracks import display_tracks_summary, display_track_detail, TRACK_DESCRIPTIONS
    from cli.commands.sections import display_section_detail
    from cli.commands.phrase import (
        display_pattern_analysis,
        display_potential_events,
        display_hex_grid,
    )
    from cli.commands.map import (
        analyze_region_density,
        create_density_bar,
        create_visual_map,
        REGIONS,
    )
    from cli.display.formatters import value_bar, pan_bar
    from qyconv.utils.xg_voices import get_voice_name
    from rich.table import Table
    from rich import box

    analyzer = Q7PAnalyzer()
    analysis = analyzer.analyze_file(filepath)
    data = analyzer.data

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 1: OVERVIEW
    # ═══════════════════════════════════════════════════════════════════════════
    console.print()
    console.print("═" * 80)
    console.print("[bold cyan]                         Q7P COMPLETE ANALYSIS[/bold cyan]")
    console.print("═" * 80)
    console.print()

    # Basic info panel
    status = "[green]Valid[/green]" if analysis.valid else "[red]Invalid[/red]"
    active_sections = sum(1 for s in analysis.sections if s.enabled)

    overview = f"""[bold]File:[/bold] {filepath}
[bold]Pattern Name:[/bold] {analysis.pattern_name or "N/A"}
[bold]Pattern Number:[/bold] {analysis.pattern_number}
[bold]Format:[/bold] {analysis.format_version.strip()}
[bold]Status:[/bold] {status}
[bold]File Size:[/bold] {analysis.filesize} bytes
[bold]Data Density:[/bold] {analysis.data_density:.1f}%
[bold]Active Sections:[/bold] {active_sections} of {len(analysis.sections)}"""

    console.print(Panel(overview, title="[bold]Overview[/bold]", border_style="blue"))

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 2: TIMING
    # ═══════════════════════════════════════════════════════════════════════════
    console.print()
    console.print("[bold yellow]▶ TIMING[/bold yellow]")
    console.print("─" * 40)

    timing_table = Table(box=box.SIMPLE, show_header=False)
    timing_table.add_column("Property", style="cyan", width=20)
    timing_table.add_column("Value", width=50)

    timing_table.add_row("Tempo", f"{analysis.tempo:.1f} BPM")
    timing_table.add_row(
        "Tempo Raw", f"0x{analysis.tempo_raw[0]:02X} 0x{analysis.tempo_raw[1]:02X}"
    )
    timing_table.add_row(
        "Time Signature", f"{analysis.time_signature[0]}/{analysis.time_signature[1]}"
    )
    timing_table.add_row("Time Sig Raw", f"0x{analysis.time_signature_raw:02X}")
    timing_table.add_row("Pattern Flags", f"0x{analysis.pattern_flags:02X}")

    console.print(timing_table)

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 3: FILE STRUCTURE MAP
    # ═══════════════════════════════════════════════════════════════════════════
    console.print()
    console.print("[bold yellow]▶ FILE STRUCTURE MAP[/bold yellow]")
    console.print("─" * 40)

    visual_map = create_visual_map(data, width=64)
    console.print(f"[dim]0x000[/dim] {visual_map} [dim]0xBFF[/dim]")
    console.print("[dim](Each char = ~48 bytes, █=data, ░=empty)[/dim]")

    console.print()

    # Regions table
    region_table = Table(box=box.SIMPLE, show_header=True, header_style="dim")
    region_table.add_column("Region", width=16)
    region_table.add_column("Offset", width=14)
    region_table.add_column("Size", width=8)
    region_table.add_column("Density", width=28)

    for start, end, name, desc, color, expected_fill in REGIONS:
        size = end - start
        _, meaningful, density = analyze_region_density(data, start, end, expected_fill)
        bar = create_density_bar(density, width=16)
        region_table.add_row(name, f"0x{start:03X}-0x{end - 1:03X}", f"{size}", bar)

    console.print(region_table)

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 4: TRACKS DETAIL
    # ═══════════════════════════════════════════════════════════════════════════
    console.print()
    console.print("[bold yellow]▶ TRACK CONFIGURATION[/bold yellow]")
    console.print("─" * 40)

    if analysis.sections and analysis.sections[0].tracks:
        track_table = Table(box=box.ROUNDED, show_header=True, header_style="bold")
        track_table.add_column("Track", width=6)
        track_table.add_column("Ch", width=4)
        track_table.add_column("Instrument", width=22)
        track_table.add_column("Volume", width=28)
        track_table.add_column("Pan", width=24)
        track_table.add_column("Rev", width=5)
        track_table.add_column("St", width=4)

        for i, track in enumerate(analysis.sections[0].tracks):
            voice = get_voice_name(track.program, track.bank_msb, channel=track.channel)
            vol_bar = value_bar(track.volume, width=12, show_percent=True, show_value=True)
            pan_display = pan_bar(track.pan, width=11)
            status = "[green]On[/green]" if track.enabled else "[dim]Off[/dim]"

            track_table.add_row(
                track.name,
                str(track.channel),
                voice[:22],
                vol_bar,
                pan_display,
                str(track.reverb_send),
                status,
            )

        console.print(track_table)

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 5: SECTIONS DETAIL
    # ═══════════════════════════════════════════════════════════════════════════
    console.print()
    console.print("[bold yellow]▶ SECTIONS[/bold yellow]")
    console.print("─" * 40)

    section_table = Table(box=box.ROUNDED, show_header=True, header_style="bold")
    section_table.add_column("#", width=3)
    section_table.add_column("Name", width=12)
    section_table.add_column("Status", width=10)
    section_table.add_column("Pointer", width=10)
    section_table.add_column("Config (first 8 bytes)", width=30)

    for section in analysis.sections:
        status = "[green]Active[/green]" if section.enabled else "[dim]Empty[/dim]"
        config_hex = " ".join(f"{b:02X}" for b in section.raw_config[:8])
        section_table.add_row(
            str(section.index),
            section.name,
            status,
            f"0x{section.pointer_hex.upper()}",
            config_hex,
        )

    console.print(section_table)

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 6: PHRASE/SEQUENCE DATA
    # ═══════════════════════════════════════════════════════════════════════════
    console.print()
    console.print("[bold yellow]▶ PHRASE & SEQUENCE DATA[/bold yellow]")
    console.print("─" * 40)

    if analysis.phrase_stats:
        stats = analysis.phrase_stats

        phrase_table = Table(box=box.SIMPLE, show_header=True, header_style="dim")
        phrase_table.add_column("Area", width=18)
        phrase_table.add_column("Size", width=8)
        phrase_table.add_column("Non-Zero", width=10)
        phrase_table.add_column("Meaningful", width=12)
        phrase_table.add_column("Density", width=10)
        phrase_table.add_column("Range", width=14)

        phrase_range = (
            f"0x{stats.min_phrase_byte:02X}-0x{stats.max_phrase_byte:02X}"
            if stats.phrase_non_zero_bytes > 0
            else "N/A"
        )
        seq_range = (
            f"0x{stats.min_sequence_byte:02X}-0x{stats.max_sequence_byte:02X}"
            if stats.sequence_non_zero_bytes > 0
            else "N/A"
        )

        phrase_table.add_row(
            "Phrase (0x360)",
            str(stats.phrase_total_bytes),
            str(stats.phrase_non_zero_bytes),
            str(stats.phrase_non_filler_bytes),
            f"{stats.phrase_density:.1f}%",
            phrase_range,
        )
        phrase_table.add_row(
            "Sequence (0x678)",
            str(stats.sequence_total_bytes),
            str(stats.sequence_non_zero_bytes),
            str(stats.sequence_non_filler_bytes),
            f"{stats.sequence_density:.1f}%",
            seq_range,
        )

        console.print(phrase_table)

        # Event detection
        if stats.sequence_non_filler_bytes > 0:
            console.print()
            console.print(f"[bold]Potential MIDI Events:[/bold]")
            console.print(f"  Note-like values (C1-C4 range): {stats.potential_note_events}")
            console.print(f"  Velocity-like values (64-127): {stats.potential_velocity_values}")
            console.print(f"  Unique byte values in phrase: {stats.phrase_unique_values}")

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 7: RAW DATA AREAS
    # ═══════════════════════════════════════════════════════════════════════════
    console.print()
    console.print("[bold yellow]▶ RAW DATA (Key Areas)[/bold yellow]")
    console.print("─" * 40)

    raw_areas = [
        ("Header (0x000)", analysis.header_raw),
        ("Section Pointers (0x100)", analysis.section_pointers_raw),
        ("Tempo Area (0x180)", analysis.tempo_area_raw),
        ("Channel Area (0x190)", analysis.channel_area_raw),
        ("Volume Table (0x226)", data[0x226:0x22E]),
        ("Reverb Table (0x256)", data[0x256:0x25E]),
        ("Pan Table (0x276)", data[0x276:0x27E]),
    ]

    for name, raw_data in raw_areas:
        hex_str = " ".join(f"{b:02X}" for b in raw_data[:16])
        console.print(f"[cyan]{name}:[/cyan] {hex_str}")

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 8: GLOBAL SETTINGS COMPARISON
    # ═══════════════════════════════════════════════════════════════════════════
    console.print()
    console.print("[bold yellow]▶ GLOBAL SETTINGS vs XG DEFAULTS[/bold yellow]")
    console.print("─" * 40)

    xg_defaults = {"volume": 100, "pan": 64, "reverb": 40, "chorus": 0}

    global_table = Table(box=box.SIMPLE, show_header=True, header_style="dim")
    global_table.add_column("Track", width=8)
    global_table.add_column("Ch", width=6)
    global_table.add_column("Vol", width=10)
    global_table.add_column("Pan", width=10)
    global_table.add_column("Rev", width=10)
    global_table.add_column("Differs?", width=12)

    if analysis.sections and analysis.sections[0].tracks:
        for i, track in enumerate(analysis.sections[0].tracks):
            differs = []
            if track.volume != xg_defaults["volume"]:
                differs.append("Vol")
            if track.pan != xg_defaults["pan"]:
                differs.append("Pan")
            if track.reverb_send != xg_defaults["reverb"]:
                differs.append("Rev")

            diff_str = (
                "[yellow]" + ",".join(differs) + "[/yellow]"
                if differs
                else "[green]Default[/green]"
            )

            global_table.add_row(
                track.name,
                str(track.channel),
                str(track.volume),
                str(track.pan),
                str(track.reverb_send),
                diff_str,
            )

    console.print(global_table)

    console.print()
    console.print("═" * 80)
    console.print("[bold cyan]                         END OF ANALYSIS[/bold cyan]")
    console.print("═" * 80)
    console.print()


@app.command()
def info(
    file: Path = typer.Argument(..., help="Pattern file to analyze (.Q7P or .syx)"),
    full: bool = typer.Option(False, "--full", "-f", help="Show complete extended analysis"),
    hex: bool = typer.Option(False, "--hex", "-x", help="Show hex dumps of data areas"),
    raw: bool = typer.Option(False, "--raw", "-r", help="Show unknown/reserved areas"),
    messages: bool = typer.Option(False, "--messages", "-m", help="Show individual SysEx messages"),
    sections: bool = typer.Option(
        True, "--sections/--no-sections", "-s", help="Show section details"
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """
    Display pattern file information.

    Shows configuration data from QY70 SysEx or QY700 Q7P files including:

    - Pattern name, number, and flags
    - Tempo and time signature
    - Section configuration (Intro, Main A/B, Fills, Ending)
    - Track settings (channel, volume, pan, program)
    - Phrase/sequence statistics

    Use --full for complete extended analysis with:

    - Visual file structure map
    - Bar graphics for all values
    - XG defaults comparison
    - Raw data dumps

    Examples:

        qyconv info pattern.Q7P           # Basic info
        qyconv info pattern.Q7P --full    # Complete analysis
        qyconv info style.syx --hex       # With hex dumps
        qyconv info pattern.Q7P --json    # JSON output
    """
    if not file.exists():
        console.print(f"[red]Error: File not found: {file}[/red]")
        raise typer.Exit(1)

    suffix = file.suffix.lower()

    if suffix == ".q7p":
        if full:
            display_full_q7p_info(str(file))
        else:
            from qyconv.analysis.q7p_analyzer import Q7PAnalyzer

            analyzer = Q7PAnalyzer()
            analysis = analyzer.analyze_file(str(file))

            if json_output:
                _output_json(analysis)
            else:
                display_q7p_info(analysis, show_hex=hex, show_raw=raw)

    elif suffix == ".syx":
        from qyconv.analysis.syx_analyzer import SyxAnalyzer

        analyzer = SyxAnalyzer()
        analysis = analyzer.analyze_file(str(file))

        if json_output:
            _output_json(analysis)
        else:
            display_syx_info(analysis, show_sections=sections, show_messages=messages, show_hex=hex)
    else:
        console.print(f"[red]Error: Unknown file type: {suffix}[/red]")
        console.print("Supported formats: .Q7P (QY700), .syx (QY70)")
        raise typer.Exit(1)


def _output_json(analysis) -> None:
    """Output analysis as JSON."""
    import json
    from dataclasses import asdict

    def serialize(obj):
        if isinstance(obj, bytes):
            return obj.hex()
        elif hasattr(obj, "__dict__"):
            return {k: serialize(v) for k, v in obj.__dict__.items() if not k.startswith("_")}
        elif isinstance(obj, dict):
            return {k: serialize(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [serialize(v) for v in obj]
        elif isinstance(obj, tuple):
            return list(obj)
        else:
            return obj

    try:
        data = asdict(analysis)
    except:
        data = serialize(analysis)

    # Convert bytes to hex strings
    def convert_bytes(d):
        if isinstance(d, dict):
            return {k: convert_bytes(v) for k, v in d.items()}
        elif isinstance(d, list):
            return [convert_bytes(v) for v in d]
        elif isinstance(d, bytes):
            return d.hex()
        else:
            return d

    data = convert_bytes(data)
    console.print_json(data=data)


if __name__ == "__main__":
    app()
