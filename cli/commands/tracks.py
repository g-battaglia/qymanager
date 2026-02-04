"""
Tracks command - detailed track information display.
"""

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from qyconv.analysis.q7p_analyzer import Q7PAnalyzer
from qyconv.utils.xg_voices import get_voice_name
from cli.display.formatters import value_bar, pan_bar

console = Console()
app = typer.Typer()

# XG Default values for comparison
XG_DEFAULTS = {
    "volume": 100,
    "pan": 64,
    "reverb_send": 40,
    "chorus_send": 0,
    "variation_send": 0,
    "program": 0,
    "bank_msb": 0,
    "bank_lsb": 0,
}

# Default channels per track (16 tracks)
DEFAULT_CHANNELS = [10, 10, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16]

# 16 track names
TRACK_NAMES = [
    "TR1",
    "TR2",
    "TR3",
    "TR4",
    "TR5",
    "TR6",
    "TR7",
    "TR8",
    "TR9",
    "TR10",
    "TR11",
    "TR12",
    "TR13",
    "TR14",
    "TR15",
    "TR16",
]
TRACK_DESCRIPTIONS = [
    "Track 1 (Drums)",
    "Track 2 (Percussion)",
    "Track 3 (Bass)",
    "Track 4",
    "Track 5",
    "Track 6",
    "Track 7",
    "Track 8",
    "Track 9",
    "Track 10",
    "Track 11",
    "Track 12",
    "Track 13",
    "Track 14",
    "Track 15",
    "Track 16",
]

NUM_TRACKS = 16


def highlight_if_different(value: int, default: int, format_str: str = "{}") -> Text:
    """Return highlighted text if value differs from default."""
    text = Text()
    formatted = format_str.format(value)
    if value != default:
        text.append(formatted, style="bold yellow")
        text.append(f" (≠{default})", style="dim yellow")
    else:
        text.append(formatted)
    return text


def display_track_detail(
    track_num: int,
    name: str,
    description: str,
    channel: int,
    channel_raw: int,
    volume: int,
    pan: int,
    reverb: int,
    chorus: int,
    program: int,
    bank_msb: int,
    bank_lsb: int,
    enabled: bool,
    is_drum: bool,
) -> None:
    """Display detailed info for a single track."""
    # Track header
    status = "[green]ENABLED[/green]" if enabled else "[red]DISABLED[/red]"
    track_type = "[magenta]DRUM[/magenta]" if is_drum else "[cyan]MELODIC[/cyan]"

    header = f"[bold]{name}[/bold] - {description}\n"
    header += f"Status: {status}  Type: {track_type}"

    console.print(Panel(header, title=f"Track {track_num}", border_style="cyan", expand=False))

    # Create detail table
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Parameter", style="cyan", width=20)
    table.add_column("Value", width=50)
    table.add_column("Offset", style="dim", width=12)

    # Channel
    ch_text = Text()
    ch_text.append(f"Ch {channel:2d}")
    if channel_raw != channel - 1 and not (channel_raw == 0 and channel == 10):
        ch_text.append(f" (raw: 0x{channel_raw:02X})", style="dim")
    default_ch = DEFAULT_CHANNELS[track_num - 1]
    if channel != default_ch:
        ch_text.append(f" [≠default {default_ch}]", style="yellow")
    table.add_row("MIDI Channel", ch_text, f"0x{0x190 + track_num - 1:03X}")

    # Program/Bank
    voice_name = get_voice_name(program, bank_msb, channel=channel)
    prog_text = Text()
    prog_text.append(f"Program {program:3d}")
    prog_text.append(f"  Bank {bank_msb}/{bank_lsb}", style="dim")
    prog_text.append(f"\n{voice_name}", style="bold green" if enabled else "dim")
    table.add_row("Voice", prog_text, "TBD")

    # Volume with bar
    vol_bar = value_bar(volume, max_value=127, width=12)
    vol_text = Text()
    vol_text.append(vol_bar)
    if volume != XG_DEFAULTS["volume"]:
        vol_text.append(f"  [≠{XG_DEFAULTS['volume']}]", style="yellow")
    table.add_row("Volume", vol_text, f"0x{0x226 + track_num - 1:03X}")

    # Pan with centered bar
    pan_display = pan_bar(pan, width=13)
    pan_text = Text()
    pan_text.append(pan_display)
    if pan != XG_DEFAULTS["pan"]:
        pan_text.append(f"  [≠C]", style="yellow")
    table.add_row("Pan", pan_text, f"0x{0x276 + track_num - 1:03X}")

    # Reverb Send
    rev_bar = value_bar(reverb, max_value=127, width=12)
    rev_text = Text()
    rev_text.append(rev_bar)
    if reverb != XG_DEFAULTS["reverb_send"]:
        rev_text.append(f"  [≠{XG_DEFAULTS['reverb_send']}]", style="yellow")
    table.add_row("Reverb Send", rev_text, f"0x{0x256 + track_num - 1:03X}")

    # Chorus Send
    cho_bar = value_bar(chorus, max_value=127, width=12)
    cho_text = Text()
    cho_text.append(cho_bar)
    if chorus != XG_DEFAULTS["chorus_send"]:
        cho_text.append(f"  [≠{XG_DEFAULTS['chorus_send']}]", style="yellow")
    table.add_row("Chorus Send", cho_text, "TBD")

    console.print(table)
    console.print()


def display_tracks_summary(analysis) -> None:
    """Display a summary table of all tracks."""
    table = Table(
        title="All Tracks Summary",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Track", width=6)
    table.add_column("Ch", width=4)
    table.add_column("Instrument", width=24)
    table.add_column("Volume", width=24)
    table.add_column("Pan", width=22)
    table.add_column("Rev", width=5)
    table.add_column("", width=4)

    if analysis.sections and analysis.sections[0].tracks:
        for i, track in enumerate(analysis.sections[0].tracks):
            voice = get_voice_name(track.program, track.bank_msb, channel=track.channel)
            vol_bar = value_bar(track.volume, width=10, show_percent=True, show_value=True)
            pan_display = pan_bar(track.pan, width=9)
            status = "[green]On[/green]" if track.enabled else "[dim]Off[/dim]"

            table.add_row(
                track.name,
                str(track.channel),
                voice[:24],
                vol_bar,
                pan_display,
                str(track.reverb_send),
                status,
            )

    console.print(table)


@app.command()
def tracks(
    file: Path = typer.Argument(..., help="Q7P file to analyze"),
    track: int = typer.Option(0, "--track", "-t", help="Show specific track (1-16), 0=all"),
    summary: bool = typer.Option(False, "--summary", "-s", help="Show summary table only"),
    compare_defaults: bool = typer.Option(
        True, "--compare/--no-compare", "-c", help="Highlight non-default values"
    ),
) -> None:
    """
    Display detailed track/channel information.

    Shows for each of 16 tracks:
    - MIDI channel assignment (raw and interpreted)
    - Program/Bank selection with voice name
    - Volume with bar graphic
    - Pan with centered bar graphic
    - Effect sends (reverb, chorus)
    - Comparison with XG defaults

    Examples:

        qyconv tracks pattern.Q7P

        qyconv tracks pattern.Q7P --track 1

        qyconv tracks pattern.Q7P --summary
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

    # Header
    console.print(
        Panel(
            f"[bold]File:[/bold] {file}\n[bold]Pattern:[/bold] {analysis.pattern_name or 'N/A'}",
            title="[bold]Track Information[/bold]",
            border_style="blue",
        )
    )
    console.print()

    if summary:
        display_tracks_summary(analysis)
        return

    # Get raw data for offset display
    data = analyzer.data

    # Detailed track display
    if analysis.sections and analysis.sections[0].tracks:
        tracks_to_show = analysis.sections[0].tracks

        if track > 0:
            if 1 <= track <= NUM_TRACKS:
                tracks_to_show = [tracks_to_show[track - 1]]
            else:
                console.print(f"[red]Invalid track number: {track}. Use 1-{NUM_TRACKS}.[/red]")
                raise typer.Exit(1)

        for i, t in enumerate(tracks_to_show):
            track_idx = t.number - 1 if track == 0 else track - 1
            is_drum = track_idx < 2  # TR1, TR2

            # Get raw channel value
            channel_raw = data[0x190 + track_idx] if len(data) > 0x190 + track_idx else 0

            display_track_detail(
                track_num=t.number,
                name=t.name,
                description=TRACK_DESCRIPTIONS[track_idx],
                channel=t.channel,
                channel_raw=channel_raw,
                volume=t.volume,
                pan=t.pan,
                reverb=t.reverb_send,
                chorus=t.chorus_send,
                program=t.program,
                bank_msb=t.bank_msb,
                bank_lsb=t.bank_lsb,
                enabled=t.enabled,
                is_drum=is_drum,
            )
    else:
        console.print("[yellow]No track data found in file.[/yellow]")


if __name__ == "__main__":
    app()
