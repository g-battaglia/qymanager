"""UDM field editor CLI: read, set, and emit UDM-aware format files.

Usage patterns:

    qymanager field-set   file.syx --set system.master_volume=77 --out out.syx
    qymanager field-get   file.syx system.master_volume
    qymanager field-emit  --set system.master_volume=77
                          --set effects.reverb.type_code=5
                          > edits.syx     # emit XG Param Change SysEx stream

All three share the editor pipeline:
    load → apply_edits (validated) → emit (same format or XG SysEx stream)

Integrates with `cli.app` as standalone commands (not subcommands) so
they can be used offline or together with `--realtime` in F5.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from qymanager.editor.ops import (
    apply_edits,
    get_field,
    make_xg_messages,
)
from qymanager.formats.io import load_device, save_device
from qymanager.model import Device

console = Console()


def _parse_edits(edits: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in edits:
        if "=" not in raw:
            raise typer.BadParameter(f"expected PATH=VALUE, got {raw!r}")
        path, value = raw.split("=", 1)
        out[path.strip()] = value.strip()
    return out


def _apply_and_report(device: Device, edits: dict[str, str]) -> None:
    errors = apply_edits(device, edits)
    if errors:
        console.print("[red]Some edits failed:[/red]")
        for err in errors:
            console.print(f"  [red]✗[/red] {err}")
        raise typer.Exit(code=1)


def field_set(
    input_path: Path = typer.Argument(
        ..., exists=True, dir_okay=False, readable=True, help="Input file (.syx/.q7p/.mid)"
    ),
    output_path: Path = typer.Option(
        ..., "--out", "-o", help="Output path (same format as input)"
    ),
    edits: list[str] = typer.Option(
        [], "--set", "-s", help="PATH=VALUE (repeatable)"
    ),
) -> None:
    """Load a file, apply UDM field edits, save to a new file."""
    if not edits:
        console.print("[yellow]No edits specified (use --set PATH=VALUE)[/yellow]")
        raise typer.Exit(code=1)
    edit_map = _parse_edits(edits)
    device = load_device(input_path)
    _apply_and_report(device, edit_map)
    save_device(device, output_path)
    console.print(
        f"[green]Wrote {len(edit_map)} edit(s) → {output_path}[/green]"
    )


def field_get(
    input_path: Path = typer.Argument(
        ..., exists=True, dir_okay=False, readable=True
    ),
    paths: list[str] = typer.Argument(..., help="UDM paths to read"),
) -> None:
    """Print the current value of one or more UDM paths."""
    device = load_device(input_path)
    table = Table(title=f"UDM fields — {input_path.name}")
    table.add_column("path")
    table.add_column("value")
    for p in paths:
        value = get_field(device, p)
        table.add_row(p, "<unset>" if value is None else repr(value))
    console.print(table)


def field_emit_xg(
    edits: list[str] = typer.Option(
        [], "--set", "-s", help="PATH=VALUE (repeatable)"
    ),
    output_path: Optional[Path] = typer.Option(
        None, "--out", "-o", help="Write SysEx bytes to this file (defaults to stdout)"
    ),
    device_number: int = typer.Option(
        0, "--device", help="Yamaha device number 0..15 (default 0)"
    ),
) -> None:
    """Emit an XG Parameter Change SysEx stream from a set of UDM edits.

    No source file needed — the edits are resolved directly through the
    address_map / schema. Useful for building tiny .syx patches that
    can be sent to hardware or merged into existing dumps.
    """
    if not edits:
        console.print("[yellow]No edits (use --set PATH=VALUE)[/yellow]")
        raise typer.Exit(code=1)
    edit_map = _parse_edits(edits)
    dummy = Device()  # schema/address lookup doesn't touch Device state
    messages = make_xg_messages(dummy, edit_map, device_number=device_number)
    if len(messages) != len(edit_map):
        mapped = {p for p, _ in messages}
        for p in edit_map:
            if p not in mapped:
                console.print(f"[red]No XG address for {p}[/red]")
    blob = b"".join(m for _, m in messages)
    if output_path is not None:
        output_path.write_bytes(blob)
        console.print(f"[green]Wrote {len(blob)}B → {output_path}[/green]")
    else:
        # Binary to stdout — wrap in hex for safety in terminal
        for p, m in messages:
            hex_str = " ".join(f"{b:02X}" for b in m)
            console.print(f"[cyan]{p}[/cyan]: {hex_str}")
