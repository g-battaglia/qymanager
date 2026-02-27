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
    from qymanager.analysis.q7p_analyzer import Q7PAnalyzer
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
    from qymanager.utils.xg_voices import get_voice_name
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


def display_full_syx_info(filepath: str) -> None:
    """Display complete SysEx analysis using all available information."""
    from qymanager.analysis.syx_analyzer import SyxAnalyzer
    from qymanager.utils.xg_effects import XG_DEFAULTS
    from cli.display.formatters import value_bar, pan_bar
    from rich.table import Table
    from rich import box

    analyzer = SyxAnalyzer()
    analysis = analyzer.analyze_file(filepath)

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 1: OVERVIEW
    # ═══════════════════════════════════════════════════════════════════════════
    console.print()
    console.print("═" * 80)
    console.print("[bold cyan]                    QY70 SYSEX COMPLETE ANALYSIS[/bold cyan]")
    console.print("═" * 80)
    console.print()

    status = "[green]Valid[/green]" if analysis.valid else "[red]Invalid[/red]"

    # Determine file type from format_type field
    if analysis.format_type == "pattern":
        file_type = "[cyan]Pattern[/cyan] (single pattern, AL 0x00-0x07)"
    elif analysis.format_type == "style":
        file_type = "[green]Style[/green] (full style, AL 0x00-0x2F)"
    else:
        file_type = "[yellow]Unknown[/yellow]"

    # Extract name from filename if not in SysEx data
    # QY70 SysEx bulk dumps don't contain the pattern/style name
    pattern_name = analysis.pattern_name
    if not pattern_name:
        # Extract from filename (e.g., "P - MR. Vain - 20231101.syx" -> "MR. Vain")
        from pathlib import Path

        filename = Path(filepath).stem  # Remove extension
        # Try to extract meaningful name from common QY70 filename patterns
        if " - " in filename:
            parts = filename.split(" - ")
            if len(parts) >= 2:
                pattern_name = parts[1].strip()  # Usually the second part is the name
            else:
                pattern_name = filename
        else:
            pattern_name = filename

    overview = f"""[bold]File:[/bold] {filepath}
[bold]Pattern/Style Name:[/bold] {pattern_name}
[bold]Format:[/bold] {file_type}
[bold]Status:[/bold] {status}
[bold]File Size:[/bold] {analysis.filesize} bytes
[bold]Data Density:[/bold] {analysis.data_density:.1f}%
[bold]Active Sections:[/bold] {analysis.active_section_count} of 6
[bold]Active Tracks:[/bold] {analysis.active_track_count} of 8"""

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

    timing_table.add_row("Tempo", f"{analysis.tempo} BPM")
    timing_table.add_row(
        "Time Signature", f"{analysis.time_signature[0]}/{analysis.time_signature[1]}"
    )
    timing_table.add_row("Time Sig Raw", f"0x{analysis.time_signature_raw:02X}")

    console.print(timing_table)

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 3: GLOBAL EFFECTS
    # ═══════════════════════════════════════════════════════════════════════════
    console.print()
    console.print("[bold yellow]▶ GLOBAL EFFECTS[/bold yellow]")
    console.print("─" * 40)

    effects_table = Table(box=box.SIMPLE, show_header=False)
    effects_table.add_column("Effect", style="cyan", width=12)
    effects_table.add_column("Type", width=20)
    effects_table.add_column("MSB/LSB", width=12)

    effects_table.add_row(
        "Reverb",
        analysis.reverb_type,
        f"0x{analysis.reverb_type_msb:02X}/0x{analysis.reverb_type_lsb:02X}",
    )
    effects_table.add_row(
        "Chorus",
        analysis.chorus_type,
        f"0x{analysis.chorus_type_msb:02X}/0x{analysis.chorus_type_lsb:02X}",
    )
    effects_table.add_row(
        "Variation",
        analysis.variation_type,
        f"0x{analysis.variation_type_msb:02X}/0x{analysis.variation_type_lsb:02X}",
    )

    console.print(effects_table)

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 4: SYSEX MESSAGE STATISTICS
    # ═══════════════════════════════════════════════════════════════════════════
    console.print()
    console.print("[bold yellow]▶ SYSEX MESSAGE STATISTICS[/bold yellow]")
    console.print("─" * 40)

    stats_table = Table(box=box.SIMPLE, show_header=False)
    stats_table.add_column("Property", style="cyan", width=25)
    stats_table.add_column("Value", width=40)

    checksum_status = (
        f"[green]{analysis.valid_checksums} valid[/green]"
        if analysis.invalid_checksums == 0
        else f"[green]{analysis.valid_checksums} valid[/green], [red]{analysis.invalid_checksums} invalid[/red]"
    )

    stats_table.add_row("Total Messages", str(analysis.total_messages))
    stats_table.add_row("Bulk Dump Messages", str(analysis.bulk_dump_messages))
    stats_table.add_row("Parameter Messages", str(analysis.parameter_messages))
    stats_table.add_row("Checksums", checksum_status)
    stats_table.add_row("Total Encoded", f"{analysis.total_encoded_bytes} bytes")
    stats_table.add_row("Total Decoded", f"{analysis.total_decoded_bytes} bytes")
    stats_table.add_row(
        "Compression Ratio",
        f"{(1 - analysis.total_decoded_bytes / analysis.total_encoded_bytes) * 100:.1f}% expansion"
        if analysis.total_encoded_bytes > 0
        else "N/A",
    )

    console.print(stats_table)

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 5: TRACK CONFIGURATION (with bar graphics)
    # ═══════════════════════════════════════════════════════════════════════════
    console.print()
    console.print("[bold yellow]▶ TRACK CONFIGURATION (8 tracks)[/bold yellow]")
    console.print("─" * 80)

    # Use simple table format for better fit
    track_table = Table(box=box.SIMPLE, show_header=True, header_style="bold", expand=False)
    track_table.add_column("Track", style="cyan", no_wrap=True)
    track_table.add_column("Ch", no_wrap=True)
    track_table.add_column("Instrument", no_wrap=True)
    track_table.add_column("B/P", no_wrap=True)
    track_table.add_column("Vol", no_wrap=True)
    track_table.add_column("Pan", no_wrap=True)
    track_table.add_column("Rv", no_wrap=True)
    track_table.add_column("Ch", no_wrap=True)

    for track in analysis.qy70_tracks:
        if track.has_data:
            voice = track.voice_name[:18] if track.voice_name else f"Prog {track.program}"
            bank_prg = f"{track.bank_msb}/{track.program}"
            # Simple volume display
            vol_pct = int(track.volume / 127 * 100)
            vol_bar = f"{track.volume:3d} [{'█' * (vol_pct // 10)}{'░' * (10 - vol_pct // 10)}]"
            # Simple pan display
            if track.pan == 64:
                pan_str = "  C  "
            elif track.pan < 64:
                pan_str = f"L{64 - track.pan:2d}"
            else:
                pan_str = f"R{track.pan - 64:2d}"
            status_icon = "[green]●[/green]"
        else:
            voice = "[dim]---[/dim]"
            bank_prg = "[dim]-[/dim]"
            vol_bar = "[dim]---[/dim]"
            pan_str = "[dim]-[/dim]"

        rev_str = str(track.reverb_send) if track.has_data else "[dim]-[/dim]"
        cho_str = str(track.chorus_send) if track.has_data else "[dim]-[/dim]"

        track_table.add_row(
            track.name,
            str(track.channel),
            voice,
            bank_prg,
            vol_bar,
            pan_str,
            rev_str,
            cho_str,
        )

    console.print(track_table)

    # QY70 track descriptions
    console.print()
    console.print("[dim]Track Types: D1/D2=Drums, PC=Percussion, BA=Bass, C1-C4=Chord[/dim]")

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 5b: TRACK NOTE RANGES AND EVENTS
    # ═══════════════════════════════════════════════════════════════════════════
    console.print()
    console.print("[bold yellow]▶ TRACK NOTE RANGES & EVENTS[/bold yellow]")
    console.print("─" * 80)

    range_table = Table(box=box.SIMPLE, show_header=True, header_style="bold", expand=False)
    range_table.add_column("Track", style="cyan", no_wrap=True)
    range_table.add_column("Note Range", no_wrap=True)
    range_table.add_column("Events", no_wrap=True)
    range_table.add_column("Density", no_wrap=True)
    range_table.add_column("Activity", no_wrap=True)

    for track in analysis.qy70_tracks:
        if track.has_data:
            # Note range (only for melody tracks)
            if track.note_range_str:
                range_str = track.note_range_str
            elif track.is_drum_track:
                range_str = "[dim]Drums[/dim]"
            else:
                range_str = f"{track.note_low}-{track.note_high}"

            # Event count
            event_str = str(track.event_count) if track.event_count > 0 else "[dim]0[/dim]"

            # Data density
            density_str = f"{track.data_density:.0f}%"

            # Activity bar (based on events)
            activity_level = min(10, track.event_count // 5)
            activity_bar = f"[{'█' * activity_level}{'░' * (10 - activity_level)}]"
        else:
            range_str = "[dim]---[/dim]"
            event_str = "[dim]---[/dim]"
            density_str = "[dim]---[/dim]"
            activity_bar = "[dim]---[/dim]"

        range_table.add_row(
            track.name,
            range_str,
            event_str,
            density_str,
            activity_bar,
        )

    console.print(range_table)

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 6: SECTIONS (6 style sections)
    # ═══════════════════════════════════════════════════════════════════════════
    console.print()
    console.print("[bold yellow]▶ STYLE SECTIONS (6 sections)[/bold yellow]")
    console.print("─" * 80)

    section_table = Table(box=box.SIMPLE, show_header=True, header_style="bold", expand=False)
    section_table.add_column("#", no_wrap=True)
    section_table.add_column("Name", no_wrap=True)
    section_table.add_column("Status", no_wrap=True)
    section_table.add_column("Bars", no_wrap=True)
    section_table.add_column("Phrase", no_wrap=True)
    section_table.add_column("Track Data", no_wrap=True)
    section_table.add_column("Active Tracks", no_wrap=True)

    for sec in analysis.qy70_sections:
        status_str = "[green]Active[/green]" if sec.has_data else "[dim]Empty[/dim]"
        bars_str = f"~{sec.bar_count}" if sec.bar_count > 0 else "[dim]-[/dim]"
        phrase_str = f"{sec.phrase_bytes}B" if sec.phrase_bytes > 0 else "[dim]-[/dim]"
        track_str = f"{sec.track_bytes}B" if sec.track_bytes > 0 else "[dim]-[/dim]"
        tracks_str = (
            ", ".join(str(t) for t in sec.active_tracks) if sec.active_tracks else "[dim]None[/dim]"
        )

        section_table.add_row(
            str(sec.index),
            sec.name,
            status_str,
            bars_str,
            phrase_str,
            track_str,
            tracks_str,
        )

    console.print(section_table)
    console.print("[dim]Note: Bar count is estimated from phrase data size[/dim]")

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 7: AL ADDRESS BREAKDOWN (all data sections)
    # ═══════════════════════════════════════════════════════════════════════════
    console.print()
    console.print("[bold yellow]▶ DATA SECTIONS BY AL ADDRESS[/bold yellow]")
    console.print("─" * 40)

    al_table = Table(box=box.SIMPLE, show_header=True, header_style="dim")
    al_table.add_column("AL", width=6)
    al_table.add_column("Name", width=22)
    al_table.add_column("Msgs", width=5)
    al_table.add_column("Bytes", width=8)
    al_table.add_column("Density", width=10)
    al_table.add_column("Preview (first 12 bytes)", width=40)

    for al in sorted(analysis.sections.keys()):
        section = analysis.sections[al]
        density = (
            (section.non_zero_bytes / section.total_decoded_bytes * 100)
            if section.total_decoded_bytes > 0
            else 0
        )
        # Get first 12 bytes for preview
        preview_bytes = section.decoded_data[:12] if section.decoded_data else b""
        preview = " ".join(f"{b:02X}" for b in preview_bytes)

        al_table.add_row(
            f"0x{al:02X}",
            section.name[:22],
            str(section.message_count),
            str(section.total_decoded_bytes),
            f"{density:.0f}%",
            preview,
        )

    console.print(al_table)

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 8: TRACK VS XG DEFAULTS COMPARISON
    # ═══════════════════════════════════════════════════════════════════════════
    console.print()
    console.print("[bold yellow]▶ TRACK SETTINGS vs XG DEFAULTS[/bold yellow]")
    console.print("─" * 40)

    defaults_table = Table(box=box.SIMPLE, show_header=True, header_style="dim")
    defaults_table.add_column("Track", width=8)
    defaults_table.add_column("Vol", width=10)
    defaults_table.add_column("Pan", width=10)
    defaults_table.add_column("Rev", width=10)
    defaults_table.add_column("Cho", width=10)
    defaults_table.add_column("Differs?", width=20)

    for track in analysis.qy70_tracks:
        if not track.has_data:
            continue

        differs = []
        if track.volume != XG_DEFAULTS["volume"]:
            differs.append(f"Vol({track.volume}≠{XG_DEFAULTS['volume']})")
        if track.pan != XG_DEFAULTS["pan"]:
            differs.append(f"Pan({track.pan}≠{XG_DEFAULTS['pan']})")
        if track.reverb_send != XG_DEFAULTS["reverb_send"]:
            differs.append(f"Rev({track.reverb_send}≠{XG_DEFAULTS['reverb_send']})")
        if track.chorus_send != XG_DEFAULTS["chorus_send"]:
            differs.append(f"Cho({track.chorus_send}≠{XG_DEFAULTS['chorus_send']})")

        diff_str = (
            "[yellow]" + ", ".join(differs) + "[/yellow]"
            if differs
            else "[green]All Default[/green]"
        )

        defaults_table.add_row(
            track.name,
            str(track.volume),
            str(track.pan),
            str(track.reverb_send),
            str(track.chorus_send),
            diff_str,
        )

    console.print(defaults_table)
    console.print("[dim]XG Defaults: Volume=100, Pan=64 (C), Reverb=40, Chorus=0[/dim]")

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 9: HEADER HEX DUMP
    # ═══════════════════════════════════════════════════════════════════════════
    if analysis.header_decoded:
        console.print()
        console.print("[bold yellow]▶ HEADER DATA (AL=0x7F) DECODED[/bold yellow]")
        console.print("─" * 40)

        hex_lines = []
        data = analysis.header_decoded
        for i in range(0, len(data), 16):
            chunk = data[i : i + 16]
            hex_str = " ".join(f"{b:02X}" for b in chunk)
            ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            hex_lines.append(f"{i:04X}: {hex_str:<48}  {ascii_str}")

        console.print("\n".join(hex_lines))

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 10: FIRST TRACK DATA SAMPLE
    # ═══════════════════════════════════════════════════════════════════════════
    console.print()
    console.print("[bold yellow]▶ TRACK DATA SAMPLES (first 32 bytes each)[/bold yellow]")
    console.print("─" * 40)

    track_names = ["D1", "D2", "PC", "BA", "C1", "C2", "C3", "C4"]

    for track_idx in range(8):
        # Check both Pattern format (AL 0x00-0x07) and Style format (AL 0x00-0x2F)
        found = False

        if analysis.format_type == "pattern":
            # Pattern format: track data in AL 0x00-0x07
            al = track_idx
            if al in analysis.sections:
                section = analysis.sections[al]
                if section.total_decoded_bytes > 0:
                    preview_data = section.decoded_data[:32]
                    hex_str = " ".join(f"{b:02X}" for b in preview_data)
                    console.print(f"[cyan]{track_names[track_idx]}:[/cyan] {hex_str}")
                    found = True

        if not found:
            # Style format: track data in AL 0x00-0x2F
            for sec_idx in range(6):
                al = sec_idx * 8 + track_idx
                if al in analysis.sections:
                    section = analysis.sections[al]
                    if section.total_decoded_bytes > 0:
                        preview_data = section.decoded_data[:32]
                        hex_str = " ".join(f"{b:02X}" for b in preview_data)
                        console.print(f"[cyan]{track_names[track_idx]}:[/cyan] {hex_str}")
                        break

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 11: MESSAGE LIST (first 20)
    # ═══════════════════════════════════════════════════════════════════════════
    console.print()
    console.print("[bold yellow]▶ MESSAGE LIST (first 20)[/bold yellow]")
    console.print("─" * 40)

    msg_table = Table(box=box.SIMPLE, show_header=True, header_style="dim")
    msg_table.add_column("#", width=4)
    msg_table.add_column("Type", width=15)
    msg_table.add_column("Address", width=12)
    msg_table.add_column("Encoded", width=10)
    msg_table.add_column("Decoded", width=10)
    msg_table.add_column("CS", width=6)

    for msg in analysis.messages[:20]:
        cs_status = "[green]OK[/green]" if msg.checksum_valid else "[red]BAD[/red]"
        msg_table.add_row(
            str(msg.index),
            msg.message_type,
            msg.address_hex,
            f"{msg.data_size} B",
            f"{msg.decoded_size} B",
            cs_status,
        )

    console.print(msg_table)
    if len(analysis.messages) > 20:
        console.print(f"[dim](Showing first 20 of {len(analysis.messages)} messages)[/dim]")

    # ═══════════════════════════════════════════════════════════════════════════
    # END
    # ═══════════════════════════════════════════════════════════════════════════
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

        qymanager info pattern.Q7P           # Basic info
        qymanager info pattern.Q7P --full    # Complete analysis
        qymanager info style.syx --hex       # With hex dumps
        qymanager info pattern.Q7P --json    # JSON output
    """
    if not file.exists():
        console.print(f"[red]Error: File not found: {file}[/red]")
        raise typer.Exit(1)

    suffix = file.suffix.lower()

    if suffix == ".q7p":
        if full:
            display_full_q7p_info(str(file))
        else:
            from qymanager.analysis.q7p_analyzer import Q7PAnalyzer

            analyzer = Q7PAnalyzer()
            analysis = analyzer.analyze_file(str(file))

            if json_output:
                _output_json(analysis)
            else:
                display_q7p_info(analysis, show_hex=hex, show_raw=raw)

    elif suffix == ".syx":
        if full:
            display_full_syx_info(str(file))
        else:
            from qymanager.analysis.syx_analyzer import SyxAnalyzer

            analyzer = SyxAnalyzer()
            analysis = analyzer.analyze_file(str(file))

            if json_output:
                _output_json(analysis)
            else:
                display_syx_info(
                    analysis, show_sections=sections, show_messages=messages, show_hex=hex
                )
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
