#!/usr/bin/env python3
"""Convert a load-capture JSON (MIDI stream during pattern load) to a raw .syx file.

The capture_xg_stream.py and similar tools produce a JSON of the form:
  [{"t": <seconds>, "data": "<hex>"}, ...]
where each entry is either a SysEx message (F0..F7) or a channel event (CC/PC/Note).

This script concatenates all `data` entries into one raw byte stream and writes
it as a .syx file. The resulting file is then readable by `qymanager info` —
the syx_analyzer parses both Model 5F bulk and XG Model 4C + channel events.

Merge a pattern bulk + a load JSON into one complete .syx:
    python3 midi_tools/load_json_to_syx.py load.json -o xg_part.syx
    cat pattern_bulk.syx xg_part.syx > full.syx
    qymanager info full.syx         # Shows complete voice info

Usage:
    uv run python3 midi_tools/load_json_to_syx.py <input.json> -o <output.syx>
"""

import argparse
import json
import sys
from pathlib import Path


def convert(input_path: Path, output_path: Path, merge_with: Path = None) -> int:
    data = json.loads(input_path.read_text())
    if not isinstance(data, list):
        print("ERROR: JSON is not a list of {t, data} entries", file=sys.stderr)
        return 1

    raw = bytearray()
    n_sysex = 0
    n_channel = 0
    skipped = 0
    for entry in data:
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
        if b[0] == 0xF0:
            n_sysex += 1
        elif 0x80 <= b[0] <= 0xEF:
            n_channel += 1
        else:
            # 0xF1-0xF6, 0xF8-0xFE — realtime/system — skip to keep file clean
            skipped += 1
            continue
        raw.extend(b)

    if merge_with:
        existing = merge_with.read_bytes()
        raw = existing + raw
        print(f"Merged with {merge_with} ({len(existing)} bytes)")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(raw)

    print(f"Input:  {input_path} ({len(data)} entries)")
    print(f"Output: {output_path} ({len(raw)} bytes)")
    print(f"  SysEx messages:   {n_sysex}")
    print(f"  Channel events:   {n_channel}")
    print(f"  Skipped:          {skipped}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", type=Path, help="Input load-capture .json file")
    ap.add_argument("-o", "--output", type=Path, required=True, help="Output .syx path")
    ap.add_argument("--merge-with", type=Path,
                    help="Existing .syx file to PREPEND (e.g., the pattern bulk)")
    args = ap.parse_args()

    if not args.input.exists():
        print(f"ERROR: input not found: {args.input}", file=sys.stderr)
        return 1
    if args.merge_with and not args.merge_with.exists():
        print(f"ERROR: merge_with not found: {args.merge_with}", file=sys.stderr)
        return 1

    return convert(args.input, args.output, args.merge_with)


if __name__ == "__main__":
    sys.exit(main())
