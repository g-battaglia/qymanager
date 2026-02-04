"""
Rich table displays for pattern information.

Provides beautiful formatted output for Q7P and SysEx file analysis.
"""

from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
from rich.text import Text
from rich.columns import Columns
from rich import box

from qyconv.analysis.q7p_analyzer import Q7PAnalysis, SectionInfo, TrackInfo, PhraseStats
from qyconv.analysis.syx_analyzer import SyxAnalysis, SectionData
from qyconv.utils.xg_voices import get_voice_name


console = Console()


def pan_to_string(pan: int) -> str:
    """
    Convert XG pan value to readable string.

    XG Pan encoding:
    - 0 = Random
    - 1-63 = Left (L63-L1)
    - 64 = Center
    - 65-127 = Right (R1-R63)
    """
    if pan == 0:
        return "Rnd"  # Random
    elif pan == 64:
        return "C"
    elif pan < 64:
        return f"L{64 - pan}"
    else:
        return f"R{pan - 64}"


def display_voice_settings(analysis: Q7PAnalysis) -> None:
    """Display voice/instrument settings table with XG parameters."""
    table = Table(
        title="Voice Settings", box=box.ROUNDED, show_header=True, header_style="bold cyan"
    )
    table.add_column("Track", style="cyan", width=6)
    table.add_column("Ch", width=3)
    table.add_column("Prog", width=5)
    table.add_column("Bank", width=6)
    table.add_column("Instrument", width=22)
    table.add_column("Vol", width=4)
    table.add_column("Pan", width=4)
    table.add_column("Rev", width=4)
    table.add_column("Cho", width=4)
    table.add_column("", width=4)  # Status

    # Use tracks from first section
    if analysis.sections and analysis.sections[0].tracks:
        for track in analysis.sections[0].tracks:
            bank_str = f"{track.bank_msb}/{track.bank_lsb}"
            voice = get_voice_name(track.program, track.bank_msb, channel=track.channel)
            status = "[green]On[/green]" if track.enabled else "[dim]Off[/dim]"

            table.add_row(
                track.name,
                str(track.channel),
                str(track.program),
                bank_str,
                voice[:22],  # Truncate long names
                str(track.volume),
                pan_to_string(track.pan),
                str(track.reverb_send),
                str(track.chorus_send),
                status,
            )

    console.print(table)


def display_phrase_stats(analysis: Q7PAnalysis) -> None:
    """Display phrase and sequence data statistics."""
    stats = analysis.phrase_stats
    if not stats:
        return

    # Phrase/Sequence Statistics table
    table = Table(
        title="Phrase & Sequence Data",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold yellow",
    )
    table.add_column("Area", style="cyan", width=18)
    table.add_column("Size", width=8)
    table.add_column("Non-Zero", width=12)
    table.add_column("Meaningful", width=12)
    table.add_column("Density", width=10)
    table.add_column("Range", width=12)

    # Phrase row
    phrase_status = (
        "[green]Has Data[/green]" if stats.phrase_non_filler_bytes > 0 else "[dim]Empty[/dim]"
    )
    phrase_range = (
        f"0x{stats.min_phrase_byte:02X}-0x{stats.max_phrase_byte:02X}"
        if stats.phrase_non_zero_bytes > 0
        else "N/A"
    )
    table.add_row(
        "Phrase (0x360)",
        f"{stats.phrase_total_bytes}",
        f"{stats.phrase_non_zero_bytes}",
        f"{stats.phrase_non_filler_bytes}",
        f"{stats.phrase_density:.1f}%",
        phrase_range,
    )

    # Sequence row
    seq_status = (
        "[green]Has Data[/green]" if stats.sequence_non_filler_bytes > 0 else "[dim]Empty[/dim]"
    )
    seq_range = (
        f"0x{stats.min_sequence_byte:02X}-0x{stats.max_sequence_byte:02X}"
        if stats.sequence_non_zero_bytes > 0
        else "N/A"
    )
    table.add_row(
        "Sequence (0x678)",
        f"{stats.sequence_total_bytes}",
        f"{stats.sequence_non_zero_bytes}",
        f"{stats.sequence_non_filler_bytes}",
        f"{stats.sequence_density:.1f}%",
        seq_range,
    )

    console.print(table)

    # Show MIDI event detection hints (if sequence has data)
    if stats.sequence_non_filler_bytes > 0:
        hint_panel = f"""[bold]Potential MIDI Events Detected:[/bold]
  Note-like values (C1-C4 range): {stats.potential_note_events}
  Velocity-like values (64-127): {stats.potential_velocity_values}
  Unique byte values in phrase: {stats.phrase_unique_values}"""
        console.print(
            Panel(hint_panel, title="Event Analysis", border_style="yellow", expand=False)
        )

    # Show top histogram values if there's data
    if stats.phrase_non_filler_bytes > 0 and stats.phrase_value_histogram:
        # Get top 5 non-filler values
        filler = {0x00, 0x40, 0x7F, 0xFE, 0xF8, 0x20}
        filtered = {k: v for k, v in stats.phrase_value_histogram.items() if k not in filler}
        if filtered:
            top_values = sorted(filtered.items(), key=lambda x: x[1], reverse=True)[:5]
            hist_str = ", ".join(f"0x{v:02X}:{c}" for v, c in top_values)
            console.print(f"[dim]Top phrase values: {hist_str}[/dim]")


def display_q7p_info(analysis: Q7PAnalysis, show_hex: bool = False, show_raw: bool = False) -> None:
    """Display complete Q7P file information with Rich formatting."""

    # Header panel
    status = "[green]Valid[/green]" if analysis.valid else "[red]Invalid[/red]"

    header_content = f"""[bold]Pattern:[/bold] {analysis.pattern_name or "N/A"}
[bold]Number:[/bold] {analysis.pattern_number}
[bold]Format:[/bold] {analysis.format_version.strip()}
[bold]Status:[/bold] {status}
[bold]File Size:[/bold] {analysis.filesize} bytes
[bold]Data Density:[/bold] {analysis.data_density:.1f}%"""

    console.print(
        Panel(
            header_content,
            title="[bold blue]Q7P Pattern Info[/bold blue]",
            border_style="blue",
            expand=False,
        )
    )

    # Timing panel with raw time signature byte for debugging
    ts_raw_info = (
        f" (raw: 0x{analysis.time_signature_raw:02X})"
        if hasattr(analysis, "time_signature_raw")
        else ""
    )
    timing_content = f"""[bold]Tempo:[/bold] {analysis.tempo:.1f} BPM (raw: 0x{analysis.tempo_raw[0]:02X} 0x{analysis.tempo_raw[1]:02X})
[bold]Time Signature:[/bold] {analysis.time_signature[0]}/{analysis.time_signature[1]}{ts_raw_info}
[bold]Flags:[/bold] 0x{analysis.pattern_flags:02X}"""

    console.print(
        Panel(
            timing_content, title="[bold cyan]Timing[/bold cyan]", border_style="cyan", expand=False
        )
    )

    # Sections table
    section_table = Table(
        title="Sections", box=box.ROUNDED, show_header=True, header_style="bold magenta"
    )
    section_table.add_column("#", style="dim", width=3)
    section_table.add_column("Name", style="cyan", width=12)
    section_table.add_column("Status", width=10)
    section_table.add_column("Pointer", style="dim", width=10)
    section_table.add_column("Config Preview", width=40)

    for section in analysis.sections:
        status = "[green]Active[/green]" if section.enabled else "[dim]Empty[/dim]"
        config_hex = " ".join(f"{b:02X}" for b in section.raw_config[:16])
        section_table.add_row(
            str(section.index), section.name, status, section.pointer_hex, config_hex
        )

    console.print(section_table)

    # Voice Settings table (detailed instrument info)
    display_voice_settings(analysis)

    # Phrase/Sequence Statistics
    display_phrase_stats(analysis)

    if show_hex:
        # Show hex dumps of key areas
        console.print("\n[bold]Raw Data Areas:[/bold]")

        areas = [
            ("Header (0x000-0x00F)", analysis.header_raw),
            ("Section Pointers (0x100-0x11F)", analysis.section_pointers_raw),
            ("Section Data (0x120-0x17F)", analysis.section_data_raw),
            ("Tempo Area (0x180-0x18F)", analysis.tempo_area_raw),
            ("Channel Area (0x190-0x19F)", analysis.channel_area_raw),
            ("Track Config (0x1DC-0x1FF)", analysis.track_config_raw),
            ("Reverb Table (0x250-0x26F)", analysis.reverb_table_raw),
        ]

        for name, data in areas:
            hex_str = " ".join(f"{b:02X}" for b in data)
            console.print(Panel(hex_str, title=name, border_style="dim", expand=False))

    if show_raw:
        # Show all unknown areas
        console.print("\n[bold]Unknown/Reserved Areas:[/bold]")

        for name, data in analysis.unknown_areas.items():
            if any(b not in (0x00, 0x20, 0x40, 0xFE, 0xF8) for b in data):
                hex_lines = []
                for i in range(0, min(len(data), 64), 16):
                    chunk = data[i : i + 16]
                    hex_str = " ".join(f"{b:02X}" for b in chunk)
                    ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
                    hex_lines.append(f"{hex_str}  {ascii_str}")
                if len(data) > 64:
                    hex_lines.append(f"... ({len(data) - 64} more bytes)")
                console.print(
                    Panel("\n".join(hex_lines), title=name, border_style="yellow", expand=False)
                )


def display_syx_info(
    analysis: SyxAnalysis,
    show_sections: bool = True,
    show_messages: bool = False,
    show_hex: bool = False,
) -> None:
    """Display complete SysEx file information with Rich formatting."""

    # Header panel
    status = "[green]Valid[/green]" if analysis.valid else "[red]Invalid[/red]"
    checksum_status = (
        f"[green]{analysis.valid_checksums}[/green]"
        if analysis.invalid_checksums == 0
        else f"[green]{analysis.valid_checksums}[/green]/[red]{analysis.invalid_checksums}[/red]"
    )

    header_content = f"""[bold]File:[/bold] {analysis.filepath}
[bold]Size:[/bold] {analysis.filesize} bytes
[bold]Status:[/bold] {status}
[bold]Pattern Name:[/bold] {analysis.pattern_name or "N/A"}
[bold]Tempo:[/bold] {analysis.tempo} BPM"""

    console.print(
        Panel(
            header_content,
            title="[bold blue]QY70 SysEx Info[/bold blue]",
            border_style="blue",
            expand=False,
        )
    )

    # Message statistics
    stats_table = Table(title="Message Statistics", box=box.ROUNDED, show_header=False)
    stats_table.add_column("Property", style="cyan")
    stats_table.add_column("Value", style="white")

    stats_table.add_row("Total Messages", str(analysis.total_messages))
    stats_table.add_row("Bulk Dump Messages", str(analysis.bulk_dump_messages))
    stats_table.add_row("Parameter Messages", str(analysis.parameter_messages))
    stats_table.add_row("Style Data Messages", str(analysis.style_data_messages))
    stats_table.add_row("Valid Checksums", checksum_status)
    stats_table.add_row("Total Encoded Bytes", str(analysis.total_encoded_bytes))
    stats_table.add_row("Total Decoded Bytes", str(analysis.total_decoded_bytes))
    stats_table.add_row("Unique AL Addresses", str(len(analysis.al_addresses)))

    console.print(stats_table)

    if show_sections:
        # Section summary table
        section_table = Table(
            title="Section Summary (by AL Address)",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
        )
        section_table.add_column("AL", style="dim", width=6)
        section_table.add_column("Name", style="cyan", width=25)
        section_table.add_column("Msgs", width=6)
        section_table.add_column("Bytes", width=8)
        section_table.add_column("Non-Zero", width=10)
        section_table.add_column("Preview", width=35)

        for al in sorted(analysis.sections.keys()):
            section = analysis.sections[al]
            density = (
                (section.non_zero_bytes / section.total_decoded_bytes * 100)
                if section.total_decoded_bytes > 0
                else 0
            )
            preview = section.data_preview[:35]

            section_table.add_row(
                f"0x{al:02X}",
                section.name,
                str(section.message_count),
                str(section.total_decoded_bytes),
                f"{section.non_zero_bytes} ({density:.0f}%)",
                preview,
            )

        console.print(section_table)

    if show_messages:
        # Detailed message table
        msg_table = Table(
            title="Message Details", box=box.SIMPLE, show_header=True, header_style="bold green"
        )
        msg_table.add_column("#", style="dim", width=4)
        msg_table.add_column("Type", width=12)
        msg_table.add_column("Address", width=12)
        msg_table.add_column("Data", width=8)
        msg_table.add_column("Decoded", width=8)
        msg_table.add_column("CS", width=8)

        for msg in analysis.messages[:50]:  # Limit to first 50
            cs_status = "[green]OK[/green]" if msg.checksum_valid else "[red]BAD[/red]"
            msg_table.add_row(
                str(msg.index),
                msg.message_type,
                msg.address_hex,
                str(msg.data_size),
                str(msg.decoded_size),
                cs_status,
            )

        if len(analysis.messages) > 50:
            console.print(f"[dim](Showing first 50 of {len(analysis.messages)} messages)[/dim]")

        console.print(msg_table)

    if show_hex and analysis.header_decoded:
        # Show header hex dump
        console.print("\n[bold]Header Section (AL=0x7F) Decoded:[/bold]")
        hex_lines = []
        data = analysis.header_decoded[:128]
        for i in range(0, len(data), 16):
            chunk = data[i : i + 16]
            hex_str = " ".join(f"{b:02X}" for b in chunk)
            ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            hex_lines.append(f"{i:04X}: {hex_str:<48}  {ascii_str}")
        console.print(Panel("\n".join(hex_lines), border_style="dim", expand=False))


def display_file_info(
    filepath: str,
    show_hex: bool = False,
    show_raw: bool = False,
    show_sections: bool = True,
    show_messages: bool = False,
) -> None:
    """Auto-detect file type and display appropriate info."""
    from pathlib import Path

    path = Path(filepath)
    suffix = path.suffix.lower()

    if suffix == ".q7p":
        from qyconv.analysis.q7p_analyzer import Q7PAnalyzer

        analyzer = Q7PAnalyzer()
        analysis = analyzer.analyze_file(filepath)
        display_q7p_info(analysis, show_hex=show_hex, show_raw=show_raw)

    elif suffix == ".syx":
        from qyconv.analysis.syx_analyzer import SyxAnalyzer

        analyzer = SyxAnalyzer()
        analysis = analyzer.analyze_file(filepath)
        display_syx_info(
            analysis, show_sections=show_sections, show_messages=show_messages, show_hex=show_hex
        )
    else:
        console.print(f"[red]Unknown file type: {suffix}[/red]")
        console.print("Supported formats: .Q7P (QY700), .syx (QY70)")
