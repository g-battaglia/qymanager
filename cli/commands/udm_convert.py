"""CLI for UDM-based cross-device conversion (F9).

    qymanager udm-convert in.q7p --to qy70 --out out.syx \\
        --keep variation --drop fill-cc-dd --warn-file out.warnings.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from qymanager.converters.lossy_policy import LossyPolicy, dump_warnings
from qymanager.converters.udm_convert import convert_file
from qymanager.model import DeviceModel

console = Console()


def udm_convert(
    input_path: Path = typer.Argument(
        ..., exists=True, dir_okay=False, readable=True, help="Input file"
    ),
    output_path: Path = typer.Option(
        ..., "--out", "-o", help="Output file (extension picks the emitter)"
    ),
    target: str = typer.Option(
        ..., "--to", help="Target device (qy70 or qy700)"
    ),
    keep: list[str] = typer.Option(
        [], "--keep", help="Accept these field losses silently (repeatable)"
    ),
    drop: list[str] = typer.Option(
        [], "--drop", help="Force drop + warning (repeatable)"
    ),
    warn_file: Optional[Path] = typer.Option(
        None, "--warn-file", help="Write lossy warnings as JSON"
    ),
) -> None:
    """Convert a UDM file to a different target device with a lossy policy."""
    try:
        model = DeviceModel(target.lower())
    except ValueError:
        raise typer.BadParameter(f"target must be qy70 or qy700, got {target!r}")

    policy = LossyPolicy(keep=keep, drop=drop)
    _device, warnings = convert_file(
        input_path, output_path, target_model=model, policy=policy
    )

    console.print(f"[green]Wrote {output_path}[/green]")
    if warnings:
        console.print(
            f"[yellow]Lossy conversion: {len(warnings)} field(s) stripped[/yellow]"
        )
        for w in warnings[:10]:
            console.print(f"  [yellow]•[/yellow] {w.path}: {w.reason}")
        if len(warnings) > 10:
            console.print(f"  [dim]+{len(warnings) - 10} more[/dim]")
    if warn_file is not None:
        warn_file.write_text(json.dumps(dump_warnings(warnings), indent=2))
        console.print(f"[dim]Warnings → {warn_file}[/dim]")
