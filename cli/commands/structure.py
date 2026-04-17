"""CLI for structured UDM editing: pattern / song / chord / phrase (F4).

Commands operate on whole structures (not single-field paths) because
patterns and songs have nested lists/dicts that don't fit the simple
`PATH=VALUE` DSL of `field-set`. Every command follows the same
pipeline: `load_device → mutate → save_device`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from qymanager.formats.io import load_device, save_device
from qymanager.model import ChordEntry, TimeSig
from qymanager.model.pattern import CHORD_ROOTS, CHORD_TYPES

console = Console()


def _check_pattern_index(device, idx: int):
    if not 0 <= idx < len(device.patterns):
        raise typer.BadParameter(
            f"pattern index {idx} out of range (have {len(device.patterns)})"
        )


def _check_song_index(device, idx: int):
    if not 0 <= idx < len(device.songs):
        raise typer.BadParameter(
            f"song index {idx} out of range (have {len(device.songs)})"
        )


def pattern_set(
    input_path: Path = typer.Argument(..., exists=True, dir_okay=False),
    output_path: Path = typer.Option(..., "--out", "-o"),
    idx: int = typer.Option(0, "--idx", help="Pattern index (default 0)"),
    name: Optional[str] = typer.Option(None, "--name", help="New pattern name (<= 10 chars)"),
    tempo: Optional[float] = typer.Option(None, "--tempo", help="Tempo in BPM"),
    time_sig: Optional[str] = typer.Option(None, "--time-sig", help="e.g. 4/4"),
) -> None:
    """Edit pattern metadata (name, tempo, time signature)."""
    device = load_device(input_path)
    _check_pattern_index(device, idx)
    pat = device.patterns[idx]

    if name is not None:
        if len(name) > 10:
            raise typer.BadParameter(f"name too long ({len(name)} > 10)")
        pat.name = name
    if tempo is not None:
        if not 30.0 <= tempo <= 300.0:
            raise typer.BadParameter(f"tempo must be 30-300, got {tempo}")
        pat.tempo_bpm = tempo
    if time_sig is not None:
        if "/" not in time_sig:
            raise typer.BadParameter(f"expected N/D, got {time_sig!r}")
        n, d = time_sig.split("/", 1)
        pat.time_sig = TimeSig(numerator=int(n), denominator=int(d))

    save_device(device, output_path)
    console.print(f"[green]Pattern[{idx}] updated → {output_path}[/green]")


def pattern_list(
    input_path: Path = typer.Argument(..., exists=True, dir_okay=False),
) -> None:
    """List all patterns in a device file."""
    device = load_device(input_path)
    table = Table(title=f"Patterns in {input_path.name}")
    table.add_column("idx")
    table.add_column("name")
    table.add_column("tempo")
    table.add_column("time_sig")
    table.add_column("measures")
    table.add_column("sections")
    for i, pat in enumerate(device.patterns):
        ts = f"{pat.time_sig.numerator}/{pat.time_sig.denominator}"
        sect = ",".join(s.value for s in pat.sections)
        table.add_row(
            str(i), pat.name or "<unnamed>", f"{pat.tempo_bpm:.1f}",
            ts, str(pat.measures), sect or "-",
        )
    console.print(table)


def chord_add(
    input_path: Path = typer.Argument(..., exists=True, dir_okay=False),
    output_path: Path = typer.Option(..., "--out", "-o"),
    pattern_idx: int = typer.Option(0, "--pattern-idx"),
    measure: int = typer.Option(..., "--measure", help="1-based measure number"),
    beat: int = typer.Option(..., "--beat", help="1-based beat within measure"),
    root: str = typer.Option(..., "--root", help="C, C#, D, D#, ..., B"),
    chord_type: str = typer.Option("MAJ", "--type", help="MAJ/MIN/7/..."),
    on_bass: bool = typer.Option(False, "--on-bass"),
) -> None:
    """Append a chord entry to a pattern's chord track."""
    device = load_device(input_path)
    _check_pattern_index(device, pattern_idx)

    try:
        root_idx = CHORD_ROOTS.index(root)
    except ValueError:
        raise typer.BadParameter(f"root must be one of {CHORD_ROOTS}")
    try:
        type_idx = CHORD_TYPES.index(chord_type)
    except ValueError:
        raise typer.BadParameter(f"type must be one of {CHORD_TYPES}")

    entry = ChordEntry(
        root=root_idx,
        chord_type=type_idx,
        on_bass=on_bass,
        measure=max(0, measure - 1),
        beat=max(0, beat - 1),
    )
    device.patterns[pattern_idx].chord_track.entries.append(entry)
    save_device(device, output_path)
    console.print(
        f"[green]Added {root}{chord_type} @ m{measure}:b{beat} → {output_path}[/green]"
    )


def chord_list(
    input_path: Path = typer.Argument(..., exists=True, dir_okay=False),
    pattern_idx: int = typer.Option(0, "--pattern-idx"),
) -> None:
    """List chord entries in a pattern's chord track."""
    device = load_device(input_path)
    _check_pattern_index(device, pattern_idx)
    entries = device.patterns[pattern_idx].chord_track.entries
    table = Table(title=f"Chord track — pattern {pattern_idx}")
    table.add_column("#")
    table.add_column("measure")
    table.add_column("beat")
    table.add_column("chord")
    table.add_column("onBass")
    for i, e in enumerate(entries):
        table.add_row(
            str(i),
            str(e.measure + 1),
            str(e.beat + 1),
            f"{e.root_name}{e.chord_type_name}",
            str(e.on_bass),
        )
    console.print(table)


def song_set(
    input_path: Path = typer.Argument(..., exists=True, dir_okay=False),
    output_path: Path = typer.Option(..., "--out", "-o"),
    idx: int = typer.Option(0, "--idx"),
    name: Optional[str] = typer.Option(None, "--name"),
    tempo: Optional[float] = typer.Option(None, "--tempo"),
    time_sig: Optional[str] = typer.Option(None, "--time-sig"),
) -> None:
    """Edit song metadata (name, tempo, time signature)."""
    device = load_device(input_path)
    _check_song_index(device, idx)
    song = device.songs[idx]

    if name is not None:
        if len(name) > 10:
            raise typer.BadParameter(f"name too long ({len(name)} > 10)")
        song.name = name
    if tempo is not None:
        song.tempo_bpm = tempo
    if time_sig is not None:
        n, d = time_sig.split("/", 1)
        song.time_sig = TimeSig(numerator=int(n), denominator=int(d))

    save_device(device, output_path)
    console.print(f"[green]Song[{idx}] updated → {output_path}[/green]")


def song_list(
    input_path: Path = typer.Argument(..., exists=True, dir_okay=False),
) -> None:
    """List all songs in a device file."""
    device = load_device(input_path)
    table = Table(title=f"Songs in {input_path.name}")
    table.add_column("idx")
    table.add_column("name")
    table.add_column("tempo")
    table.add_column("time_sig")
    table.add_column("tracks")
    table.add_column("events")
    for i, s in enumerate(device.songs):
        ts = f"{s.time_sig.numerator}/{s.time_sig.denominator}"
        total_events = sum(len(t.events) for t in s.tracks)
        table.add_row(
            str(i), s.name or "<unnamed>", f"{s.tempo_bpm:.1f}",
            ts, str(len(s.tracks)), str(total_events),
        )
    console.print(table)


def phrase_list(
    input_path: Path = typer.Argument(..., exists=True, dir_okay=False),
) -> None:
    """List user phrases (Phrases[]) captured in the UDM device."""
    device = load_device(input_path)
    table = Table(title=f"User phrases in {input_path.name}")
    table.add_column("idx")
    table.add_column("name")
    table.add_column("category")
    table.add_column("type")
    table.add_column("events")
    for i, ph in enumerate(device.phrases_user):
        table.add_row(
            str(i),
            ph.name or "<unnamed>",
            ph.category.value,
            ph.phrase_type.value,
            str(len(ph.events)),
        )
    console.print(table)
