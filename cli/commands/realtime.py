"""Realtime XG MIDI I/O CLI (F5)."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from qymanager.editor.realtime import (
    RealtimeSession,
    list_input_ports,
    list_output_ports,
)

app = typer.Typer(help="Realtime XG Parameter Change I/O.")
console = Console()


@app.command("list-ports")
def list_ports_cmd() -> None:
    """List MIDI input and output ports visible to rtmidi."""
    out_table = Table(title="MIDI Output Ports")
    out_table.add_column("idx")
    out_table.add_column("name")
    for p in list_output_ports():
        out_table.add_row(str(p.index), p.name)
    console.print(out_table)
    in_table = Table(title="MIDI Input Ports")
    in_table.add_column("idx")
    in_table.add_column("name")
    for p in list_input_ports():
        in_table.add_row(str(p.index), p.name)
    console.print(in_table)


@app.command("emit")
def emit_cmd(
    port: str = typer.Option(..., "--port", "-p", help="Output port name (substring match)"),
    edits: list[str] = typer.Option(
        [], "--set", "-s", help="PATH=VALUE (repeatable)"
    ),
    device_number: int = typer.Option(
        0, "--device", help="Yamaha device number 0..15"
    ),
) -> None:
    """Send one or more UDM edits as live XG Parameter Change messages."""
    if not edits:
        console.print("[yellow]No edits (use --set PATH=VALUE)[/yellow]")
        raise typer.Exit(code=1)
    pairs: dict[str, str] = {}
    for raw in edits:
        if "=" not in raw:
            raise typer.BadParameter(f"expected PATH=VALUE, got {raw!r}")
        k, v = raw.split("=", 1)
        pairs[k.strip()] = v.strip()
    with RealtimeSession.open(port) as rt:
        blob = rt.send_udm_edits(pairs, device_number=device_number)
    console.print(f"[green]Sent {len(blob)}B over {len(pairs)} edit(s) → {port}[/green]")


@app.command("watch")
def watch_cmd(
    port: str = typer.Option(..., "--port", "-p", help="Input port (substring match)"),
    timeout: Optional[float] = typer.Option(
        None, "--timeout", help="Stop after N seconds of silence"
    ),
) -> None:
    """Print every XG Parameter Change arriving on the given input port."""
    with RealtimeSession.open_input(port) as rt:
        for ah, am, al, value in rt.watch_xg(timeout_s=timeout):
            console.print(
                f"AH={ah:02X} AM={am:02X} AL={al:02X} → [cyan]{value}[/cyan]"
            )
