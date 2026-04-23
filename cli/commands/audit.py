"""Audit a .syx file for data completeness.

Reports what's extractable vs missing, and suggests workflows to fill gaps.
Useful to answer: "does this .syx give me everything I need?"
"""
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich import box

from qymanager.analysis.syx_analyzer import SyxAnalyzer

console = Console()


def audit(
    file: Path = typer.Argument(..., help=".syx file to audit"),
) -> None:
    """Report what's extractable from a .syx and what's missing.

    Checks each data category (pattern events, voice info, effects, etc.)
    and reports coverage. Suggests capture_complete.py / merge workflows
    to fill gaps.
    """
    if not file.exists():
        console.print(f"[red]Error: file not found: {file}[/red]")
        raise typer.Exit(1)

    a = SyxAnalyzer()
    analysis = a.analyze_file(str(file))

    console.print(f"[bold]Audit: {file}[/bold] ({analysis.filesize} bytes)")
    console.print()

    # Detect multi-slot files early and redirect
    has_edit_buffer = any(m.address_high == 0x02 and m.address_mid == 0x7E
                          for m in a.messages)
    has_slot_data = any(m.address_high == 0x02 and m.address_mid < 0x40
                        for m in a.messages)
    if has_slot_data and not has_edit_buffer:
        slot_count = len({m.address_mid for m in a.messages
                          if m.address_high == 0x02 and m.address_mid < 0x40})
        console.print(
            f"[yellow]Multi-slot bulk file:[/yellow] {slot_count} pattern slot(s) populated, "
            "no edit buffer."
        )
        console.print(
            "[dim]Per-slot audit not supported here. For a slot inventory, run:[/dim]\n"
            f"[cyan]  qymanager bulk-summary {file}[/cyan]"
        )
        return

    # Build report
    rows = []

    # Pattern events
    if has_edit_buffer:
        rows.append(("Pattern events (edit buffer)", "✓", "green",
                     f"{analysis.active_track_count}/8 tracks, {analysis.active_section_count}/6 sections"))
    elif has_slot_data:
        slot_count = len({m.address_mid for m in a.messages
                          if m.address_high == 0x02 and m.address_mid < 0x40})
        rows.append(("Pattern events (user slots)", "~", "yellow",
                     f"{slot_count} slots (run `bulk-summary` for per-slot detail)"))
    else:
        rows.append(("Pattern events", "✗", "red", "no Model 5F AH=0x02 found"))

    # Tempo
    tempo_ok = analysis.tempo != 120 or has_edit_buffer  # 120 is default if no data
    rows.append(("Tempo", "✓" if tempo_ok else "~", "green" if tempo_ok else "yellow",
                 f"{analysis.tempo} BPM"))

    # Time signature
    rows.append(("Time signature", "~", "yellow",
                 f"{analysis.time_signature[0]}/{analysis.time_signature[1]} (assumed, not decoded)"))

    # Pattern directory (AH=0x05)
    if analysis.pattern_directory:
        rows.append(("Pattern name directory", "✓", "green",
                     f"{len(analysis.pattern_directory)} slot name(s)"))
    else:
        rows.append(("Pattern name directory", "✗", "red",
                     "AH=0x05 not in file — request separately via capture_complete.py"))

    # Voice identification per track
    if a.xg_voices:
        xg_parts = [p for p in range(8, 16) if a.xg_voices.get(p, {}).get("program") is not None]
        rows.append(("Voice Bank/LSB/Prog (ground truth via XG)", "✓", "green",
                     f"{len(xg_parts)}/8 tracks with exact voice"))
    else:
        # Check if any track has a known signature in DB
        from qymanager.analysis.syx_analyzer import _load_signature_db
        db = _load_signature_db()
        db_hits = 0
        class_hits = 0
        total = 0
        for trk in analysis.qy70_tracks:
            if not trk.has_data:
                continue
            total += 1
            if trk.voice_name and "(DB)" in trk.voice_name:
                db_hits += 1
            elif trk.voice_name and "(class" in trk.voice_name.lower():
                class_hits += 1
        rows.append(("Voice Bank/LSB/Prog (no XG)", "~", "yellow",
                     f"{db_hits} via DB, {class_hits} via class fallback, {total} total tracks"))

    # Mixer (volume/pan/rev/cho per track)
    has_mixer_xg = a.xg_voices and any("volume" in v for v in a.xg_voices.values())
    if has_mixer_xg:
        rows.append(("Mixer (Vol/Pan/Rev/Cho)", "✓", "green",
                     "per-track values from XG stream"))
    else:
        rows.append(("Mixer (Vol/Pan/Rev/Cho)", "✗", "red",
                     "no XG data — values default to XG init (100/center/40/0)"))

    # Global effects
    if a.xg_effects:
        fx_parts = sum(1 for k in a.xg_effects if "_msb" in k)
        rows.append(("Global effects types", "✓", "green",
                     f"{fx_parts} effect type(s) extracted (reverb/chorus/variation)"))
    else:
        rows.append(("Global effects types", "~", "yellow",
                     "defaults applied (Hall 1 / Chorus 1 / No Variation)"))

    # XG System
    if a.xg_system:
        rows.append(("XG System params", "✓", "green",
                     f"{len(a.xg_system)} param(s): {', '.join(sorted(a.xg_system.keys()))}"))
    else:
        rows.append(("XG System params", "~", "yellow",
                     "not captured — Master Tune/Vol fall back to XG defaults"))

    # XG Drum Setup
    if a.xg_drum_setup:
        total_notes = sum(len(notes) for notes in a.xg_drum_setup.values())
        rows.append(("XG Drum Setup overrides", "✓", "green",
                     f"{total_notes} note customization(s) across {len(a.xg_drum_setup)} setup(s)"))
    else:
        rows.append(("XG Drum Setup overrides", "—", "dim",
                     "none (only means no custom overrides, not missing data)"))

    # Render
    table = Table(
        title="Data extraction completeness",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Category", width=42)
    table.add_column("", width=3, justify="center")
    table.add_column("Details", overflow="fold")

    for label, mark, color, detail in rows:
        table.add_row(label, f"[{color}]{mark}[/{color}]", detail)

    console.print(table)
    console.print()

    # Legend
    console.print("[dim]Legend: ✓ complete · ~ partial/assumed · ✗ missing · — not applicable[/dim]")

    # Actionable suggestions
    suggestions = []
    if not a.xg_voices:
        suggestions.append(
            "[yellow]• No XG state → voice Bank/LSB/Prog unreliable.[/yellow] "
            "Run [cyan]capture_complete.py -o full.syx[/cyan] on the QY70, "
            "or [cyan]qymanager merge bulk.syx capture.json -o full.syx[/cyan]."
        )
    if not analysis.pattern_directory and has_edit_buffer:
        suggestions.append(
            "[dim]• Pattern name directory absent: single-pattern files usually skip AH=0x05. "
            "Not critical unless you need the slot name.[/dim]"
        )
    if suggestions:
        console.print()
        console.print("[bold]Suggestions:[/bold]")
        for s in suggestions:
            console.print(f"  {s}")
