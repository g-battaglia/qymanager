"""
QYConv - Bidirectional converter for Yamaha QY70/QY700 pattern files.

A modern CLI tool for converting and analyzing QY synthesizer patterns.
"""

import typer
from rich.console import Console

from cli.commands.info import info
from cli.commands.convert import convert
from cli.commands.diff import diff
from cli.commands.validate import validate

__version__ = "0.2.0"

console = Console()

# Main app
app = typer.Typer(
    name="qyconv",
    help="Convert and analyze Yamaha QY70/QY700 pattern files.",
    add_completion=False,
    rich_markup_mode="rich",
)

# Add commands directly
app.command(name="info")(info)
app.command(name="convert")(convert)
app.command(name="diff")(diff)
app.command(name="validate")(validate)


@app.command()
def version() -> None:
    """Show version information."""
    console.print(f"[bold]qyconv[/bold] version {__version__}")
    console.print("[dim]Bidirectional converter for Yamaha QY70/QY700 pattern files[/dim]")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version_flag: bool = typer.Option(False, "--version", "-V", help="Show version"),
) -> None:
    """
    QYConv - Convert and analyze Yamaha QY synthesizer patterns.

    Supports bidirectional conversion between:

    - [cyan]QY70[/cyan] SysEx files (.syx)
    - [cyan]QY700[/cyan] pattern files (.Q7P)

    [bold]Quick Start:[/bold]

        qyconv info pattern.Q7P      # Show pattern information

        qyconv convert in.syx out.Q7P  # Convert QY70 to QY700

        qyconv convert in.Q7P out.syx  # Convert QY700 to QY70

    Use --help with any command for more details.
    """
    if version_flag:
        version()
        raise typer.Exit()

    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


def run() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    run()
