"""
Diff command - compare two Q7P pattern files.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()
app = typer.Typer()


@dataclass
class DiffEntry:
    """A single difference between two files."""

    offset: int
    area: str
    description: str
    value_a: str
    value_b: str
    interpretation: str = ""


@dataclass
class DiffResult:
    """Result of comparing two Q7P files."""

    file_a: str
    file_b: str
    identical: bool
    total_differences: int
    byte_differences: int
    structural_differences: List[DiffEntry]
    summary: str


class Q7PDiffer:
    """Compare two Q7P files and identify differences."""

    # Named regions with their offsets and descriptions
    REGIONS = [
        (0x000, 0x010, "Header", "File magic/version"),
        (0x010, 0x012, "Pattern Info", "Pattern number/flags"),
        (0x012, 0x030, "Reserved 1", "Unknown"),
        (0x030, 0x032, "Size Marker", "File size marker"),
        (0x032, 0x100, "Reserved 2", "Unknown"),
        (0x100, 0x120, "Section Pointers", "16 section pointer entries"),
        (0x120, 0x180, "Section Data", "Section configuration"),
        (0x180, 0x190, "Tempo Area", "Tempo and time signature"),
        (0x190, 0x1A0, "Channel Config", "MIDI channel assignments"),
        (0x1A0, 0x1DC, "Reserved 3", "Unknown"),
        (0x1DC, 0x200, "Track Config", "Track numbers and flags"),
        (0x200, 0x220, "Reserved 4", "Unknown"),
        (0x220, 0x250, "Volume Table", "Track volumes"),
        (0x250, 0x270, "Reverb Table", "Reverb send levels"),
        (0x270, 0x2C0, "Pan Table", "Pan positions"),
        (0x2C0, 0x360, "Table 3", "Unknown purpose"),
        (0x360, 0x678, "Phrase Data", "Pattern phrases"),
        (0x678, 0x870, "Sequence Data", "Event/timing data"),
        (0x870, 0x900, "Template Info", "Pattern name area"),
        (0x900, 0x9C0, "Pattern Map", "Pattern mapping"),
        (0x9C0, 0xB10, "Fill Area", "0xFE filler"),
        (0xB10, 0xC00, "Pad Area", "0xF8 padding"),
    ]

    def __init__(self, data_a: bytes, data_b: bytes, name_a: str, name_b: str):
        self.data_a = data_a
        self.data_b = data_b
        self.name_a = name_a
        self.name_b = name_b

    def get_region_for_offset(self, offset: int) -> Tuple[str, str]:
        """Get region name and description for a given offset."""
        for start, end, name, desc in self.REGIONS:
            if start <= offset < end:
                return name, desc
        return "Unknown", "Unknown region"

    def diff(self) -> DiffResult:
        """Compare the two files and return differences."""
        differences: List[DiffEntry] = []
        byte_diff_count = 0

        # Quick check for identical files
        if self.data_a == self.data_b:
            return DiffResult(
                file_a=self.name_a,
                file_b=self.name_b,
                identical=True,
                total_differences=0,
                byte_differences=0,
                structural_differences=[],
                summary="Files are identical",
            )

        # File size check
        if len(self.data_a) != len(self.data_b):
            differences.append(
                DiffEntry(
                    offset=0,
                    area="File Size",
                    description="File sizes differ",
                    value_a=f"{len(self.data_a)} bytes",
                    value_b=f"{len(self.data_b)} bytes",
                )
            )

        # Byte-by-byte comparison
        min_len = min(len(self.data_a), len(self.data_b))
        current_region = ""
        region_diffs: List[Tuple[int, int, int]] = []  # (offset, val_a, val_b)

        for i in range(min_len):
            if self.data_a[i] != self.data_b[i]:
                byte_diff_count += 1
                region_name, region_desc = self.get_region_for_offset(i)

                # Group consecutive differences in the same region
                if region_name != current_region:
                    # Flush previous region if any
                    if region_diffs:
                        self._add_region_diff(differences, current_region, region_diffs)
                    current_region = region_name
                    region_diffs = []

                region_diffs.append((i, self.data_a[i], self.data_b[i]))

        # Flush last region
        if region_diffs:
            self._add_region_diff(differences, current_region, region_diffs)

        # Add specific structural comparisons
        self._add_structural_diffs(differences)

        return DiffResult(
            file_a=self.name_a,
            file_b=self.name_b,
            identical=False,
            total_differences=len(differences),
            byte_differences=byte_diff_count,
            structural_differences=differences,
            summary=f"{byte_diff_count} byte(s) differ across {len(differences)} region(s)",
        )

    def _add_region_diff(
        self, differences: List[DiffEntry], region: str, diffs: List[Tuple[int, int, int]]
    ) -> None:
        """Add a summarized difference entry for a region."""
        if not diffs:
            return

        # Limit to first 8 differences per region for readability
        preview_count = min(8, len(diffs))
        preview = diffs[:preview_count]

        val_a = " ".join(f"{d[1]:02X}" for d in preview)
        val_b = " ".join(f"{d[2]:02X}" for d in preview)

        if len(diffs) > preview_count:
            val_a += f" ... (+{len(diffs) - preview_count})"
            val_b += f" ... (+{len(diffs) - preview_count})"

        first_offset = diffs[0][0]

        differences.append(
            DiffEntry(
                offset=first_offset,
                area=region,
                description=f"{len(diffs)} byte(s) differ",
                value_a=val_a,
                value_b=val_b,
            )
        )

    def _add_structural_diffs(self, differences: List[DiffEntry]) -> None:
        """Add high-level structural comparisons."""
        # Compare pattern names
        name_a = self._get_pattern_name(self.data_a)
        name_b = self._get_pattern_name(self.data_b)
        if name_a != name_b:
            differences.append(
                DiffEntry(
                    offset=0x876,
                    area="Pattern Name",
                    description="Pattern names differ",
                    value_a=name_a or "(empty)",
                    value_b=name_b or "(empty)",
                    interpretation="Display name",
                )
            )

        # Compare tempo
        tempo_a = self._get_tempo(self.data_a)
        tempo_b = self._get_tempo(self.data_b)
        if tempo_a != tempo_b:
            differences.append(
                DiffEntry(
                    offset=0x188,
                    area="Tempo",
                    description="Tempo differs",
                    value_a=f"{tempo_a:.1f} BPM",
                    value_b=f"{tempo_b:.1f} BPM",
                    interpretation="Pattern tempo",
                )
            )

        # Compare pattern number
        if len(self.data_a) > 0x10 and len(self.data_b) > 0x10:
            num_a = self.data_a[0x10]
            num_b = self.data_b[0x10]
            if num_a != num_b:
                differences.append(
                    DiffEntry(
                        offset=0x10,
                        area="Pattern Number",
                        description="Pattern number differs",
                        value_a=str(num_a),
                        value_b=str(num_b),
                        interpretation="Pattern slot",
                    )
                )

    def _get_pattern_name(self, data: bytes) -> str:
        """Extract pattern name from data."""
        if len(data) >= 0x876 + 10:
            name_bytes = data[0x876 : 0x876 + 10]
            try:
                return name_bytes.decode("ascii").rstrip("\x00 ")
            except:
                return name_bytes.hex()
        return ""

    def _get_tempo(self, data: bytes) -> float:
        """Extract tempo from data."""
        if len(data) >= 0x18A:
            raw = (data[0x188] << 8) | data[0x189]
            if raw > 0:
                return raw / 10.0
        return 120.0


def display_diff(result: DiffResult, verbose: bool = False) -> None:
    """Display diff result with Rich formatting."""
    if result.identical:
        console.print(
            Panel(
                f"[green]Files are identical[/green]\n\n"
                f"File A: {result.file_a}\nFile B: {result.file_b}",
                title="[bold green]No Differences[/bold green]",
                border_style="green",
            )
        )
        return

    # Summary panel
    console.print(
        Panel(
            f"[bold]File A:[/bold] {result.file_a}\n"
            f"[bold]File B:[/bold] {result.file_b}\n\n"
            f"[yellow]{result.summary}[/yellow]",
            title="[bold red]Differences Found[/bold red]",
            border_style="red",
        )
    )

    # Differences table
    table = Table(
        title="Structural Differences",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Offset", style="dim", width=8)
    table.add_column("Area", style="cyan", width=16)
    table.add_column("Description", width=22)
    table.add_column("File A", width=25)
    table.add_column("File B", width=25)

    for diff in result.structural_differences:
        table.add_row(
            f"0x{diff.offset:03X}",
            diff.area,
            diff.description,
            diff.value_a[:25],
            diff.value_b[:25],
        )

    console.print(table)


@app.command()
def diff(
    file_a: Path = typer.Argument(..., help="First Q7P file to compare"),
    file_b: Path = typer.Argument(..., help="Second Q7P file to compare"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed byte differences"),
    raw: bool = typer.Option(False, "--raw", "-r", help="Show raw hex comparison"),
) -> None:
    """
    Compare two Q7P pattern files and show differences.

    Performs byte-by-byte comparison and identifies structural differences
    in tempo, pattern name, sections, tracks, and phrase data.

    Examples:

        qyconv diff T01.Q7P TXX.Q7P

        qyconv diff pattern1.Q7P pattern2.Q7P --verbose
    """
    # Validate files exist
    for f in [file_a, file_b]:
        if not f.exists():
            console.print(f"[red]Error: File not found: {f}[/red]")
            raise typer.Exit(1)
        if f.suffix.lower() != ".q7p":
            console.print(f"[red]Error: Only Q7P files supported: {f}[/red]")
            raise typer.Exit(1)

    # Read files
    with open(file_a, "rb") as f:
        data_a = f.read()
    with open(file_b, "rb") as f:
        data_b = f.read()

    # Perform diff
    differ = Q7PDiffer(data_a, data_b, str(file_a), str(file_b))
    result = differ.diff()

    # Display result
    display_diff(result, verbose=verbose)

    # Exit code based on differences
    if not result.identical:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
