"""Summarize a BULK_ALL .syx file: list populated user-pattern slots.

The QY70 BULK OUT → All dumps ALL user patterns (AM=0x00-0x3F) into one .syx.
`qymanager info` only inspects edit buffer (AM=0x7E), so for a BULK_ALL file
it shows "Active Sections: 0 of 6". This command fills that gap.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich import box

from qymanager.formats.qy70.sysex_parser import SysExParser

console = Console()


def bulk_summary(
    file: Path = typer.Argument(..., help="BULK_ALL or multi-slot .syx file"),
) -> None:
    """List populated pattern slots, songs, system, and XG data in a multi-slot .syx."""
    if not file.exists():
        console.print(f"[red]Error: file not found: {file}[/red]")
        raise typer.Exit(1)

    p = SysExParser()
    msgs = p.parse_file(str(file))

    # Group by (AH, AM)
    groups: dict[tuple[int, int], list] = defaultdict(list)
    for m in msgs:
        groups[(m.address_high, m.address_mid)].append(m)

    pattern_slots = sorted([(ah, am) for (ah, am) in groups if ah == 0x02 and am < 0x40])
    song_slots = sorted([(ah, am) for (ah, am) in groups if ah == 0x01])
    system_slots = sorted([(ah, am) for (ah, am) in groups if ah == 0x03])
    dir_slots = sorted([(ah, am) for (ah, am) in groups if ah == 0x05])
    edit_buffer = sorted([(ah, am) for (ah, am) in groups if ah == 0x02 and am == 0x7E])

    console.print(f"[bold cyan]File:[/bold cyan] {file}")
    console.print(f"[bold]Total messages:[/bold] {len(msgs)}")
    console.print()

    if pattern_slots:
        table = Table(title=f"Pattern slots populated: {len(pattern_slots)} / 64",
                      box=box.ROUNDED, show_header=True, header_style="bold magenta")
        table.add_column("Slot", style="cyan", width=4)
        table.add_column("Hdr", width=3)
        table.add_column("Tracks", width=22)
        table.add_column("Sections", width=15)
        table.add_column("Bytes", width=8, justify="right")

        for ah, am in pattern_slots:
            ms = groups[(ah, am)]
            als = sorted({m.address_low for m in ms if m.decoded_data})
            track_als = [al for al in als if al <= 0x2F]
            has_header = 0x7F in als
            tracks = sorted({al % 8 for al in track_als})
            sections = sorted({al // 8 for al in track_als})
            total_bytes = sum(len(m.decoded_data or b"") for m in ms)
            slot_name = f"U{am + 1:02d}"
            tracks_str = ",".join(f"{t + 1}" for t in tracks) or "-"
            sections_str = ",".join(str(s + 1) for s in sections) or "-"
            header_tag = "[green]H[/green]" if has_header else "-"
            table.add_row(slot_name, header_tag, tracks_str, sections_str, str(total_bytes))
        console.print(table)

    extras = []
    if edit_buffer:
        extras.append(f"Edit buffer (AM=0x7E): {sum(len(m.decoded_data or b'') for m in groups[(0x02, 0x7E)])} bytes")
    if song_slots:
        total = sum(len(m.decoded_data or b"") for (ah, am) in song_slots for m in groups[(ah, am)])
        extras.append(f"Song data (AH=0x01): {total} bytes")
    if system_slots:
        total = sum(len(m.decoded_data or b"") for (ah, am) in system_slots for m in groups[(ah, am)])
        extras.append(f"System meta (AH=0x03): {total} bytes")
    if dir_slots:
        total = sum(len(m.decoded_data or b"") for (ah, am) in dir_slots for m in groups[(ah, am)])
        extras.append(f"Pattern name directory (AH=0x05): {total} bytes")

    # Check for XG Multi Part (Model 4C) via raw scan
    raw = file.read_bytes()
    xg_count = 0
    i = 0
    while i < len(raw):
        if raw[i] == 0xF0:
            j = raw.find(b"\xF7", i)
            if j == -1:
                break
            msg = raw[i:j + 1]
            if len(msg) > 5 and msg[1] == 0x43 and msg[3] == 0x4C:
                xg_count += 1
            i = j + 1
        else:
            i += 1

    console.print()
    for line in extras:
        console.print(f"  [dim]•[/dim] {line}")
    xg_status = f"{xg_count} messages" if xg_count else "[yellow]absent — voice info limited[/yellow]"
    console.print(f"  [dim]•[/dim] XG Multi Part state (Model 4C): {xg_status}")

    if not xg_count:
        console.print()
        console.print(
            "[dim]Tip: For complete voice info per pattern, use:[/dim]\n"
            "[cyan]  uv run python3 midi_tools/capture_complete.py -o complete.syx[/cyan]\n"
            "[dim]which captures pattern bulk + XG state in one session.[/dim]"
        )
