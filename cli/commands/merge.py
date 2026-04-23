"""Merge pattern bulk .syx + XG capture JSON into a single .syx.

Makes the voice-extraction workflow discoverable via the main CLI:

    uv run qymanager merge pattern.syx load.json -o complete.syx
    uv run qymanager info complete.syx

The resulting file contains:
  - The original pattern bulk (Model 5F: events, sections, header)
  - XG Parameter Changes + channel events from the JSON (voice setup per part)

Once merged, `qymanager info` can extract Bank/LSB/Prog/Vol/Pan/Rev/Chor per
track via the XG state parser.
"""
from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

console = Console()


def merge(
    pattern: Path = typer.Argument(..., help="Pattern bulk .syx file"),
    capture_json: Path = typer.Argument(..., help="Load-capture .json file (from capture_xg_stream.py)"),
    output: Path = typer.Option(..., "-o", "--output", help="Output .syx path"),
) -> None:
    """Merge a pattern bulk .syx with an XG capture JSON into one .syx file.

    The capture JSON is a list of `{"t": <sec>, "data": "<hex>"}` entries
    (SysEx + channel events captured during pattern load). These are flattened
    to raw MIDI bytes and appended to the pattern bulk.
    """
    if not pattern.exists():
        console.print(f"[red]Error: pattern file not found: {pattern}[/red]")
        raise typer.Exit(1)
    if not capture_json.exists():
        console.print(f"[red]Error: capture JSON not found: {capture_json}[/red]")
        raise typer.Exit(1)

    try:
        entries = json.loads(capture_json.read_text())
    except json.JSONDecodeError as e:
        console.print(f"[red]Error parsing JSON: {e}[/red]")
        raise typer.Exit(1)

    if not isinstance(entries, list):
        console.print("[red]Error: JSON must be a list of {t, data} entries[/red]")
        raise typer.Exit(1)

    # Flatten capture JSON to raw bytes
    raw = bytearray()
    n_sysex = 0
    n_channel = 0
    skipped = 0
    for entry in entries:
        hx = entry.get("data", "")
        if not hx:
            continue
        try:
            b = bytes.fromhex(hx)
        except ValueError:
            skipped += 1
            continue
        if not b:
            continue
        first = b[0]
        if first == 0xF0:
            n_sysex += 1
        elif 0x80 <= first <= 0xEF:
            n_channel += 1
        else:
            skipped += 1
            continue
        raw.extend(b)

    # Prepend pattern bulk
    existing = pattern.read_bytes()
    merged = existing + bytes(raw)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(merged)

    console.print(f"[green]✓[/green] Wrote [cyan]{output}[/cyan] ({len(merged)} bytes)")
    console.print(
        f"  Pattern bulk: {len(existing)} bytes\n"
        f"  Capture stream: {len(raw)} bytes ({n_sysex} SysEx + {n_channel} channel events, {skipped} skipped)"
    )
    console.print(
        f"\nTry: [cyan]uv run qymanager info {output}[/cyan] to see extracted voices."
    )
