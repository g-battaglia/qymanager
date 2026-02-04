"""
Validate command - check Q7P file integrity and structure.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()
app = typer.Typer()


@dataclass
class ValidationIssue:
    """A single validation issue."""

    severity: str  # "error", "warning", "info"
    area: str
    offset: int
    message: str
    expected: str = ""
    actual: str = ""


@dataclass
class ValidationResult:
    """Result of validating a Q7P file."""

    filepath: str
    valid: bool
    errors: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)
    info: List[ValidationIssue] = field(default_factory=list)

    @property
    def total_issues(self) -> int:
        return len(self.errors) + len(self.warnings) + len(self.info)


class Q7PValidator:
    """Validate Q7P file structure and content."""

    HEADER_MAGIC = b"YQ7PAT     V1.00"
    EXPECTED_SIZES = (3072, 5120)  # Both valid file sizes

    # Known valid ranges for various fields
    VALID_TEMPO_RANGE = (200, 3000)  # 20.0 to 300.0 BPM
    VALID_VOLUME_RANGE = (0, 127)
    VALID_PAN_RANGE = (0, 127)
    VALID_CHANNEL_RANGE = (0, 15)

    # Section pointer values that indicate empty/disabled
    EMPTY_SECTION = b"\xfe\xfe"

    def __init__(self, data: bytes, filepath: str):
        self.data = data
        self.filepath = filepath
        self.issues: List[ValidationIssue] = []
        self.file_size = len(data)

    def validate(self) -> ValidationResult:
        """Perform full validation and return result."""
        self.issues = []

        # Core validation
        self._validate_file_size()
        self._validate_header()
        self._validate_tempo()
        self._validate_time_signature()
        self._validate_channels()
        self._validate_volumes()
        self._validate_pans()
        self._validate_section_pointers()
        self._validate_filler_areas()
        self._validate_checksum_areas()

        # Categorize issues
        errors = [i for i in self.issues if i.severity == "error"]
        warnings = [i for i in self.issues if i.severity == "warning"]
        info = [i for i in self.issues if i.severity == "info"]

        # File is valid if no errors
        valid = len(errors) == 0

        return ValidationResult(
            filepath=self.filepath,
            valid=valid,
            errors=errors,
            warnings=warnings,
            info=info,
        )

    def _add_issue(
        self,
        severity: str,
        area: str,
        offset: int,
        message: str,
        expected: str = "",
        actual: str = "",
    ) -> None:
        """Add a validation issue."""
        self.issues.append(
            ValidationIssue(
                severity=severity,
                area=area,
                offset=offset,
                message=message,
                expected=expected,
                actual=actual,
            )
        )

    def _validate_file_size(self) -> None:
        """Check file size is one of the valid sizes (3072 or 5120 bytes)."""
        if len(self.data) not in self.EXPECTED_SIZES:
            self._add_issue(
                "error",
                "File Size",
                0,
                "Invalid file size",
                f"{self.EXPECTED_SIZES[0]} or {self.EXPECTED_SIZES[1]} bytes",
                f"{len(self.data)} bytes",
            )
        else:
            size_type = "small (3072)" if len(self.data) == 3072 else "large (5120)"
            self._add_issue(
                "info",
                "File Size",
                0,
                f"File size is valid ({size_type})",
                f"{len(self.data)} bytes",
                f"{len(self.data)} bytes",
            )

    def _validate_header(self) -> None:
        """Check header magic bytes."""
        if len(self.data) < 16:
            self._add_issue("error", "Header", 0, "File too short to contain header")
            return

        header = self.data[:16]
        if header != self.HEADER_MAGIC:
            self._add_issue(
                "error",
                "Header",
                0,
                "Invalid header magic",
                self.HEADER_MAGIC.decode("ascii", errors="replace"),
                header.decode("ascii", errors="replace"),
            )
        else:
            self._add_issue("info", "Header", 0, "Header magic is valid")

    def _validate_tempo(self) -> None:
        """Check tempo value is in valid range."""
        if len(self.data) < 0x18A:
            return

        raw = (self.data[0x188] << 8) | self.data[0x189]
        tempo = raw / 10.0 if raw > 0 else 120.0

        if raw == 0:
            self._add_issue(
                "warning",
                "Tempo",
                0x188,
                "Tempo is zero (using default 120.0 BPM)",
                "20-300 BPM",
                "0",
            )
        elif raw < self.VALID_TEMPO_RANGE[0] or raw > self.VALID_TEMPO_RANGE[1]:
            self._add_issue(
                "warning",
                "Tempo",
                0x188,
                f"Unusual tempo value: {tempo:.1f} BPM",
                "20-300 BPM",
                f"{tempo:.1f} BPM",
            )
        else:
            self._add_issue("info", "Tempo", 0x188, f"Tempo is {tempo:.1f} BPM")

    def _validate_time_signature(self) -> None:
        """Check time signature byte."""
        if len(self.data) < 0x18B:
            return

        ts_byte = self.data[0x18A]

        # Known valid time signature bytes
        known_ts = {0x0C, 0x14, 0x1C, 0x24, 0x2C, 0x1A, 0x22, 0x32}

        if ts_byte in known_ts:
            self._add_issue(
                "info", "Time Signature", 0x18A, f"Time signature byte: 0x{ts_byte:02X}"
            )
        else:
            self._add_issue(
                "warning",
                "Time Signature",
                0x18A,
                f"Unknown time signature byte: 0x{ts_byte:02X}",
                "Known: 0x1C (4/4), etc.",
                f"0x{ts_byte:02X}",
            )

    def _validate_channels(self) -> None:
        """Check MIDI channel assignments."""
        if len(self.data) < 0x198:
            return

        for i in range(8):
            ch = self.data[0x190 + i]
            if ch > 15:
                self._add_issue(
                    "warning",
                    "Channels",
                    0x190 + i,
                    f"Track {i + 1}: Invalid channel value",
                    "0-15",
                    f"{ch} (0x{ch:02X})",
                )

    def _validate_volumes(self) -> None:
        """Check volume values."""
        if len(self.data) < 0x22E:
            return

        for i in range(8):
            vol = self.data[0x226 + i]
            if vol > 127:
                self._add_issue(
                    "warning",
                    "Volumes",
                    0x226 + i,
                    f"Track {i + 1}: Volume out of MIDI range",
                    "0-127",
                    f"{vol}",
                )

    def _validate_pans(self) -> None:
        """Check pan values."""
        if len(self.data) < 0x27E:
            return

        for i in range(8):
            pan = self.data[0x276 + i]
            if pan > 127:
                self._add_issue(
                    "warning",
                    "Pans",
                    0x276 + i,
                    f"Track {i + 1}: Pan out of MIDI range",
                    "0-127",
                    f"{pan}",
                )

    def _validate_section_pointers(self) -> None:
        """Check section pointer consistency."""
        if len(self.data) < 0x120:
            return

        active_count = 0
        for i in range(6):
            ptr = self.data[0x100 + i * 2 : 0x102 + i * 2]
            if ptr != self.EMPTY_SECTION:
                active_count += 1

        self._add_issue(
            "info",
            "Sections",
            0x100,
            f"{active_count} of 6 sections are active",
        )

    def _validate_filler_areas(self) -> None:
        """Check filler areas contain expected values."""
        if len(self.data) < 0xC00:
            return

        # Fill area (0x9C0-0xB0F) should be mostly 0xFE
        fill_area = self.data[0x9C0:0xB10]
        non_fe_count = sum(1 for b in fill_area if b != 0xFE)
        if non_fe_count > 0:
            self._add_issue(
                "info",
                "Fill Area",
                0x9C0,
                f"Fill area has {non_fe_count} non-0xFE bytes",
                "All 0xFE",
                f"{non_fe_count} different",
            )

        # Pad area (0xB10-0xBFF) should be mostly 0xF8
        pad_area = self.data[0xB10:0xC00]
        non_f8_count = sum(1 for b in pad_area if b != 0xF8)
        if non_f8_count > 0:
            self._add_issue(
                "info",
                "Pad Area",
                0xB10,
                f"Pad area has {non_f8_count} non-0xF8 bytes",
                "All 0xF8",
                f"{non_f8_count} different",
            )

    def _validate_checksum_areas(self) -> None:
        """Note: Q7P doesn't have checksums like SysEx, but we can check data integrity."""
        # For now, just note there's no checksum validation needed
        pass


def display_validation(result: ValidationResult) -> None:
    """Display validation result with Rich formatting."""
    if result.valid:
        status = "[bold green]VALID[/bold green]"
        border = "green"
    else:
        status = "[bold red]INVALID[/bold red]"
        border = "red"

    # Summary panel
    console.print(
        Panel(
            f"[bold]File:[/bold] {result.filepath}\n"
            f"[bold]Status:[/bold] {status}\n\n"
            f"Errors: [red]{len(result.errors)}[/red]  "
            f"Warnings: [yellow]{len(result.warnings)}[/yellow]  "
            f"Info: [blue]{len(result.info)}[/blue]",
            title="[bold]Validation Result[/bold]",
            border_style=border,
        )
    )

    # Issues table (if any errors or warnings)
    if result.errors or result.warnings:
        table = Table(title="Issues", box=box.ROUNDED, show_header=True, header_style="bold cyan")
        table.add_column("Severity", width=10)
        table.add_column("Area", style="cyan", width=16)
        table.add_column("Offset", style="dim", width=8)
        table.add_column("Message", width=40)

        for issue in result.errors:
            table.add_row(
                "[red]ERROR[/red]",
                issue.area,
                f"0x{issue.offset:03X}",
                issue.message,
            )

        for issue in result.warnings:
            table.add_row(
                "[yellow]WARN[/yellow]",
                issue.area,
                f"0x{issue.offset:03X}",
                issue.message,
            )

        console.print(table)

    # Show info items if verbose or no errors/warnings
    if result.info and (not result.errors and not result.warnings):
        info_table = Table(title="Validation Checks", box=box.SIMPLE, show_header=False)
        info_table.add_column("", width=60)

        for issue in result.info:
            info_table.add_row(f"[green]OK[/green] {issue.area}: {issue.message}")

        console.print(info_table)


@app.command()
def validate(
    file: Path = typer.Argument(..., help="Q7P file to validate"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show all validation details"),
    strict: bool = typer.Option(False, "--strict", "-s", help="Treat warnings as errors"),
) -> None:
    """
    Validate a Q7P pattern file structure and content.

    Checks for:

    - Correct file size (3072 bytes)
    - Valid header magic
    - Valid tempo and time signature values
    - MIDI parameter ranges (channels, volumes, pans)
    - Section pointer consistency
    - Filler/padding area integrity

    Examples:

        qyconv validate pattern.Q7P

        qyconv validate pattern.Q7P --strict
    """
    if not file.exists():
        console.print(f"[red]Error: File not found: {file}[/red]")
        raise typer.Exit(1)

    if file.suffix.lower() != ".q7p":
        console.print(f"[red]Error: Only Q7P files supported: {file}[/red]")
        raise typer.Exit(1)

    # Read file
    with open(file, "rb") as f:
        data = f.read()

    # Validate
    validator = Q7PValidator(data, str(file))
    result = validator.validate()

    # In strict mode, treat warnings as errors
    if strict and result.warnings:
        result.valid = False

    # Display result
    display_validation(result)

    # Exit code based on validity
    if not result.valid:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
