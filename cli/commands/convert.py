"""
Convert command - bidirectional conversion between QY70 and QY700 formats.
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()
app = typer.Typer()


@app.command()
def convert(
    source: Path = typer.Argument(..., help="Source file (.Q7P or .syx)"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
    template: Optional[Path] = typer.Option(
        None, "--template", "-t", help="Template Q7P file for conversion"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed progress"),
) -> None:
    """
    Convert between QY70 SysEx and QY700 Q7P formats.

    Automatically detects input format and converts to the other:

    - .syx -> .Q7P (QY70 to QY700)
    - .Q7P -> .syx (QY700 to QY70)

    Examples:

        qyconv convert style.syx -o pattern.Q7P

        qyconv convert pattern.Q7P -o style.syx

        qyconv convert style.syx -t template.Q7P
    """
    if not source.exists():
        console.print(f"[red]Error: Source file not found: {source}[/red]")
        raise typer.Exit(1)

    suffix = source.suffix.lower()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=not verbose,
    ) as progress:
        if suffix == ".syx":
            # QY70 -> QY700
            output_path = output or source.with_suffix(".Q7P")

            task = progress.add_task("Converting QY70 to QY700...", total=None)

            from qyconv.converters.qy70_to_qy700 import QY70ToQY700Converter

            try:
                converter = QY70ToQY700Converter(str(template) if template else None)
                q7p_data = converter.convert(source)

                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(q7p_data)

                progress.update(task, description="Done!")

            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                if verbose:
                    console.print_exception()
                raise typer.Exit(1)

            console.print(f"[green]Converted:[/green] {source} -> {output_path}")
            console.print(f"[dim]Output size: {len(q7p_data)} bytes[/dim]")

        elif suffix == ".q7p":
            # QY700 -> QY70
            output_path = output or source.with_suffix(".syx")

            task = progress.add_task("Converting QY700 to QY70...", total=None)

            from qyconv.converters.qy700_to_qy70 import QY700ToQY70Converter

            try:
                converter = QY700ToQY70Converter()
                syx_data = converter.convert(source)

                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(syx_data)

                progress.update(task, description="Done!")

            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                if verbose:
                    console.print_exception()
                raise typer.Exit(1)

            # Count messages
            msg_count = syx_data.count(b"\xf0")

            console.print(f"[green]Converted:[/green] {source} -> {output_path}")
            console.print(
                f"[dim]Output size: {len(syx_data)} bytes ({msg_count} SysEx messages)[/dim]"
            )

            # Warnings about conversion limitations
            console.print()
            console.print("[yellow]IMPORTANT - Conversion Limitations:[/yellow]")
            console.print("[yellow]  - QY700 has 16 tracks, QY70 only 8 tracks[/yellow]")
            console.print("[yellow]  - Only first 8 tracks (TR1-TR8) are converted[/yellow]")
            console.print("[yellow]  - Tracks 9-16 data will be lost[/yellow]")
            console.print("[yellow]  - MIDI sequence data may not be fully preserved[/yellow]")
            console.print()

        else:
            console.print(f"[red]Error: Unknown file type: {suffix}[/red]")
            console.print("Supported formats: .Q7P (QY700), .syx (QY70)")
            raise typer.Exit(1)


if __name__ == "__main__":
    app()
