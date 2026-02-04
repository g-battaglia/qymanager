"""
Info command - display complete pattern information.
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from cli.display.tables import display_q7p_info, display_syx_info

console = Console()
app = typer.Typer()


@app.command()
def info(
    file: Path = typer.Argument(..., help="Pattern file to analyze (.Q7P or .syx)"),
    hex: bool = typer.Option(False, "--hex", "-x", help="Show hex dumps of data areas"),
    raw: bool = typer.Option(False, "--raw", "-r", help="Show unknown/reserved areas"),
    messages: bool = typer.Option(False, "--messages", "-m", help="Show individual SysEx messages"),
    sections: bool = typer.Option(
        True, "--sections/--no-sections", "-s", help="Show section details"
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """
    Display complete pattern file information.

    Shows ALL configuration data from QY70 SysEx or QY700 Q7P files including:

    - Pattern name, number, and flags
    - Tempo and time signature
    - Section configuration (Intro, Main A/B, Fills, Ending)
    - Track settings (channel, volume, pan, program)
    - Raw data dumps for reverse engineering

    Examples:

        qyconv info pattern.Q7P

        qyconv info style.syx --hex

        qyconv info pattern.Q7P --raw --hex
    """
    if not file.exists():
        console.print(f"[red]Error: File not found: {file}[/red]")
        raise typer.Exit(1)

    suffix = file.suffix.lower()

    if suffix == ".q7p":
        from qyconv.analysis.q7p_analyzer import Q7PAnalyzer

        analyzer = Q7PAnalyzer()
        analysis = analyzer.analyze_file(str(file))

        if json_output:
            _output_json(analysis)
        else:
            display_q7p_info(analysis, show_hex=hex, show_raw=raw)

    elif suffix == ".syx":
        from qyconv.analysis.syx_analyzer import SyxAnalyzer

        analyzer = SyxAnalyzer()
        analysis = analyzer.analyze_file(str(file))

        if json_output:
            _output_json(analysis)
        else:
            display_syx_info(analysis, show_sections=sections, show_messages=messages, show_hex=hex)
    else:
        console.print(f"[red]Error: Unknown file type: {suffix}[/red]")
        console.print("Supported formats: .Q7P (QY700), .syx (QY70)")
        raise typer.Exit(1)


def _output_json(analysis) -> None:
    """Output analysis as JSON."""
    import json
    from dataclasses import asdict

    def serialize(obj):
        if isinstance(obj, bytes):
            return obj.hex()
        elif hasattr(obj, "__dict__"):
            return {k: serialize(v) for k, v in obj.__dict__.items() if not k.startswith("_")}
        elif isinstance(obj, dict):
            return {k: serialize(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [serialize(v) for v in obj]
        elif isinstance(obj, tuple):
            return list(obj)
        else:
            return obj

    try:
        data = asdict(analysis)
    except:
        data = serialize(analysis)

    # Convert bytes to hex strings
    def convert_bytes(d):
        if isinstance(d, dict):
            return {k: convert_bytes(v) for k, v in d.items()}
        elif isinstance(d, list):
            return [convert_bytes(v) for v in d]
        elif isinstance(d, bytes):
            return d.hex()
        else:
            return d

    data = convert_bytes(data)
    console.print_json(data=data)


if __name__ == "__main__":
    app()
