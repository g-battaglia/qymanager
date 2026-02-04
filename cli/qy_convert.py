"""
QYConv Command Line Interface.

Usage:
    qyconv input.syx --output output.Q7P
    qyconv input.Q7P --output output.syx
    qyconv --info file.Q7P
"""

import argparse
import sys
from pathlib import Path


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        prog="qyconv", description="Convert between QY70 SysEx and QY700 Q7P pattern formats"
    )

    parser.add_argument("input", nargs="?", help="Input file (.syx or .Q7P)")

    parser.add_argument("-o", "--output", help="Output file path")

    parser.add_argument(
        "-i", "--info", action="store_true", help="Show file information without converting"
    )

    parser.add_argument("-t", "--template", help="Use template file for Q7P output")

    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")

    args = parser.parse_args()

    if not args.input:
        parser.print_help()
        return 1

    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        return 1

    # Import here to avoid slow startup
    from qyconv.formats.qy70.reader import QY70Reader
    from qyconv.formats.qy700.reader import QY700Reader
    from qyconv.formats.qy70.writer import QY70Writer
    from qyconv.formats.qy700.writer import QY700Writer

    # Detect input format
    suffix = input_path.suffix.lower()

    if args.info:
        return show_info(input_path, suffix, args.verbose)

    # Convert file
    if suffix == ".syx":
        return convert_qy70_to_qy700(input_path, args.output, args.template, args.verbose)
    elif suffix == ".q7p":
        return convert_qy700_to_qy70(input_path, args.output, args.verbose)
    else:
        print(f"Error: Unknown file format: {suffix}", file=sys.stderr)
        print("Supported formats: .syx (QY70), .Q7P (QY700)", file=sys.stderr)
        return 1


def show_info(input_path: Path, suffix: str, verbose: bool) -> int:
    """Show file information."""
    from qyconv.formats.qy70.sysex_parser import SysExParser
    from qyconv.formats.qy700.binary_parser import Q7PParser

    print(f"File: {input_path}")
    print(f"Size: {input_path.stat().st_size} bytes")
    print()

    if suffix == ".syx":
        parser = SysExParser()
        messages = parser.parse_file(str(input_path))

        print("Format: QY70 SysEx")
        print(f"Messages: {len(messages)}")

        style_msgs = parser.get_style_messages()
        print(f"Style data messages: {len(style_msgs)}")

        if verbose:
            print("\nMessage types:")
            from collections import Counter

            types = Counter(m.message_type.name for m in messages)
            for t, c in types.items():
                print(f"  {t}: {c}")

            print("\nStyle sections:")
            sections = set(m.address_low for m in style_msgs)
            for s in sorted(sections):
                count = sum(1 for m in style_msgs if m.address_low == s)
                print(f"  Section 0x{s:02X}: {count} messages")

    elif suffix == ".q7p":
        info = {}
        with open(input_path, "rb") as f:
            data = f.read()

        print("Format: QY700 Q7P")
        print(f"Valid: {data[:16] == b'YQ7PAT     V1.00'}")

        if len(data) >= 0x880:
            # Template name at 0x876 (after 6 bytes of padding)
            name = data[0x876:0x880].decode("ascii", errors="replace").rstrip("\x00 ")
            print(f"Template name: {name!r}")

        if verbose:
            parser = Q7PParser()
            try:
                header, sections = parser.parse_bytes(data)
                print(f"\nPattern number: {header.pattern_number}")
                print(parser.dump_structure())
            except Exception as e:
                print(f"Parse error: {e}")

    return 0


def convert_qy70_to_qy700(input_path: Path, output: str, template: str, verbose: bool) -> int:
    """Convert QY70 SysEx to QY700 Q7P."""
    from qyconv.formats.qy70.reader import QY70Reader
    from qyconv.formats.qy700.writer import QY700Writer

    output_path = Path(output) if output else input_path.with_suffix(".Q7P")

    if verbose:
        print(f"Reading: {input_path}")

    try:
        pattern = QY70Reader.read(input_path)
    except Exception as e:
        print(f"Error reading QY70 file: {e}", file=sys.stderr)
        return 1

    if verbose:
        print(f"Pattern: {pattern.name}")
        print(f"Sections: {len(pattern.sections)}")
        print(f"Writing: {output_path}")

    try:
        if template:
            QY700Writer.write_using_template(pattern, template, output_path)
        else:
            QY700Writer.write(pattern, output_path)
    except Exception as e:
        print(f"Error writing Q7P file: {e}", file=sys.stderr)
        return 1

    print(f"Converted: {input_path} -> {output_path}")
    return 0


def convert_qy700_to_qy70(input_path: Path, output: str, verbose: bool) -> int:
    """Convert QY700 Q7P to QY70 SysEx."""
    from qyconv.formats.qy700.reader import QY700Reader
    from qyconv.formats.qy70.writer import QY70Writer

    output_path = Path(output) if output else input_path.with_suffix(".syx")

    if verbose:
        print(f"Reading: {input_path}")

    try:
        pattern = QY700Reader.read(input_path)
    except Exception as e:
        print(f"Error reading Q7P file: {e}", file=sys.stderr)
        return 1

    if verbose:
        print(f"Pattern: {pattern.name}")
        print(f"Sections: {len(pattern.sections)}")
        print(f"Writing: {output_path}")

    try:
        QY70Writer.write(pattern, output_path)
    except Exception as e:
        print(f"Error writing SysEx file: {e}", file=sys.stderr)
        return 1

    print(f"Converted: {input_path} -> {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
