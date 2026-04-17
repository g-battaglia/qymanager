"""Typer sub-app for the Pipeline B pattern editor.

Thin wrapper over midi_tools.pattern_editor (argparse) so the editor
is reachable from the main CLI as `qymanager edit <subcommand>`.
"""

from __future__ import annotations

from typing import List, Optional

import typer
from rich.console import Console

from midi_tools.pattern_editor import (
    build_parser,
    load_pattern,
    op_add_note,
    op_clear_bar,
    op_copy_bar,
    op_humanize_velocity,
    op_kit_remap,
    op_remove_notes,
    op_set_velocity,
    op_shift_time,
    op_transpose,
    save_pattern,
)
from midi_tools.quantizer import export_json, load_quantized_json, quantize_capture

console = Console()

edit_app = typer.Typer(
    name="edit",
    help="Edit captured QY70 patterns (Pipeline B prototype).",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@edit_app.command("export")
def export_cmd(
    capture: str = typer.Argument(..., help="Capture JSON path"),
    output: str = typer.Option(..., "-o", "--output", help="Output editable JSON"),
) -> None:
    """Convert a capture JSON to an editable pattern JSON."""
    pattern = load_pattern(capture)
    save_pattern(pattern, output)
    console.print(f"[green]Exported:[/green] {output}")
    console.print(pattern.summary())


@edit_app.command("summary")
def summary_cmd(
    input: str = typer.Argument(..., help="Pattern JSON path"),
) -> None:
    """Print a pattern summary."""
    pattern = load_pattern(input)
    console.print(pattern.summary())


@edit_app.command("list-notes")
def list_notes_cmd(
    input: str = typer.Argument(...),
    track: Optional[int] = typer.Option(None, "--track"),
    bar: Optional[int] = typer.Option(None, "--bar"),
) -> None:
    """List notes (optionally filtered)."""
    pattern = load_pattern(input)
    tracks = [pattern.tracks[track]] if track is not None else pattern.active_tracks
    for t in tracks:
        console.print(f"[cyan]{t.name}[/cyan] (track {t.track_idx}, ch{t.channel}, "
                      f"{'drum' if t.is_drum else 'melody'})")
        for n in t.notes:
            if bar is not None and n.bar != bar:
                continue
            console.print(f"  bar{n.bar} beat{n.beat}.{n.sub:2d}  "
                          f"note={n.note:3d} vel={n.velocity:3d} dur={n.tick_dur:4d}")


@edit_app.command("transpose")
def transpose_cmd(
    input: str = typer.Argument(...),
    track: int = typer.Option(..., "--track"),
    semitones: int = typer.Option(..., "--semitones"),
) -> None:
    """Transpose a melody track by N semitones."""
    pattern = load_pattern(input)
    moved = op_transpose(pattern, track, semitones)
    save_pattern(pattern, input)
    console.print(f"Transposed {moved} notes in track {track} by {semitones:+d} semitones")


@edit_app.command("shift-time")
def shift_time_cmd(
    input: str = typer.Argument(...),
    track: int = typer.Option(..., "--track"),
    ticks: int = typer.Option(..., "--ticks"),
) -> None:
    """Shift track notes by N ticks."""
    pattern = load_pattern(input)
    kept = op_shift_time(pattern, track, ticks)
    save_pattern(pattern, input)
    console.print(f"Shifted track {track} by {ticks:+d} ticks, {kept} notes kept")


@edit_app.command("copy-bar")
def copy_bar_cmd(
    input: str = typer.Argument(...),
    track: int = typer.Option(..., "--track"),
    src: int = typer.Option(..., "--src"),
    dst: int = typer.Option(..., "--dst"),
    append: bool = typer.Option(False, "--append"),
) -> None:
    """Copy bar contents to another bar."""
    pattern = load_pattern(input)
    copied = op_copy_bar(pattern, track, src, dst, replace=not append)
    save_pattern(pattern, input)
    console.print(f"Copied {copied} notes from bar {src} to bar {dst}")


@edit_app.command("clear-bar")
def clear_bar_cmd(
    input: str = typer.Argument(...),
    track: int = typer.Option(..., "--track"),
    bar: int = typer.Option(..., "--bar"),
) -> None:
    """Remove all notes from a bar."""
    pattern = load_pattern(input)
    removed = op_clear_bar(pattern, track, bar)
    save_pattern(pattern, input)
    console.print(f"Cleared {removed} notes in track {track} bar {bar}")


@edit_app.command("kit-remap")
def kit_remap_cmd(
    input: str = typer.Argument(...),
    track: int = typer.Option(..., "--track"),
    src: int = typer.Option(..., "--src"),
    dst: int = typer.Option(..., "--dst"),
) -> None:
    """Remap a drum-kit note (e.g. 36→38)."""
    pattern = load_pattern(input)
    count = op_kit_remap(pattern, track, src, dst)
    save_pattern(pattern, input)
    console.print(f"Remapped {count} drum notes {src} → {dst}")


@edit_app.command("humanize")
def humanize_cmd(
    input: str = typer.Argument(...),
    track: int = typer.Option(..., "--track"),
    amount: int = typer.Option(..., "--amount"),
    seed: Optional[int] = typer.Option(None, "--seed"),
) -> None:
    """Randomize velocity ±amount."""
    pattern = load_pattern(input)
    count = op_humanize_velocity(pattern, track, amount, seed=seed)
    save_pattern(pattern, input)
    console.print(f"Humanized velocity (±{amount}) on {count} notes")


@edit_app.command("set-velocity")
def set_velocity_cmd(
    input: str = typer.Argument(...),
    track: int = typer.Option(..., "--track"),
    velocity: int = typer.Option(..., "--velocity"),
    bar: Optional[int] = typer.Option(None, "--bar"),
    note: Optional[int] = typer.Option(None, "--note"),
) -> None:
    """Set velocity on matching notes."""
    pattern = load_pattern(input)
    changed = op_set_velocity(pattern, track, velocity, bar=bar, note_filter=note)
    save_pattern(pattern, input)
    console.print(f"Set velocity={velocity} on {changed} notes")


@edit_app.command("add-note")
def add_note_cmd(
    input: str = typer.Argument(...),
    track: int = typer.Option(..., "--track"),
    bar: int = typer.Option(..., "--bar"),
    beat: int = typer.Option(..., "--beat"),
    sub: int = typer.Option(0, "--sub"),
    note: int = typer.Option(..., "--note"),
    velocity: int = typer.Option(100, "--velocity"),
    duration: Optional[int] = typer.Option(None, "--duration"),
) -> None:
    """Add a note."""
    pattern = load_pattern(input)
    op_add_note(pattern, track_idx=track, bar=bar, beat=beat, sub=sub,
                note=note, velocity=velocity, duration_ticks=duration)
    save_pattern(pattern, input)
    console.print(f"Added note {note} at track {track} bar{bar} beat{beat}.{sub}")


@edit_app.command("remove-note")
def remove_note_cmd(
    input: str = typer.Argument(...),
    track: int = typer.Option(..., "--track"),
    bar: Optional[int] = typer.Option(None, "--bar"),
    beat: Optional[int] = typer.Option(None, "--beat"),
    note: Optional[int] = typer.Option(None, "--note"),
) -> None:
    """Remove notes matching filter."""
    pattern = load_pattern(input)
    removed = op_remove_notes(pattern, track, bar=bar, beat=beat, note=note)
    save_pattern(pattern, input)
    console.print(f"Removed {removed} notes")


@edit_app.command("set-tempo")
def set_tempo_cmd(
    input: str = typer.Argument(...),
    bpm: float = typer.Argument(...),
) -> None:
    """Change BPM."""
    pattern = load_pattern(input)
    pattern.bpm = bpm
    save_pattern(pattern, input)
    console.print(f"Tempo set to {bpm} BPM")


@edit_app.command("set-name")
def set_name_cmd(
    input: str = typer.Argument(...),
    name: str = typer.Argument(...),
) -> None:
    """Change pattern name."""
    pattern = load_pattern(input)
    pattern.name = name
    save_pattern(pattern, input)
    console.print(f"Name set to {name!r}")


@edit_app.command("build")
def build_cmd(
    input: str = typer.Argument(...),
    output: str = typer.Option(..., "-o", "--output", help="Output prefix"),
    scaffold: str = typer.Option("data/q7p/DECAY.Q7P", "--scaffold"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    """Build .Q7P + .mid from an edited pattern JSON."""
    from midi_tools.build_q7p_5120 import build_q7p, validate_q7p
    from midi_tools.capture_to_q7p import write_smf

    pattern = load_pattern(input)
    q7p_data = build_q7p(pattern, scaffold)
    with open(scaffold, "rb") as f:
        scaffold_bytes = f.read()
    warnings = validate_q7p(q7p_data, scaffold=scaffold_bytes)

    if warnings:
        console.print("[yellow]VALIDATION WARNINGS:[/yellow]")
        for w in warnings:
            console.print(f"  - {w}")
        if not force:
            console.print("[red]Aborted.[/red] Use --force to write anyway.")
            raise typer.Exit(code=1)

    q7p_path = f"{output}.Q7P"
    mid_path = f"{output}.mid"
    with open(q7p_path, "wb") as f:
        f.write(q7p_data)
    write_smf(pattern, mid_path)
    console.print(f"[green]Built:[/green] {q7p_path} ({len(q7p_data)} B), {mid_path}")
    console.print(pattern.summary())
