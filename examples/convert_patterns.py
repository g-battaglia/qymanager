#!/usr/bin/env python3
"""
Example: Convert QY70 SysEx to QY700 Q7P format

Demonstrates bidirectional conversion between formats.
"""

import sys

sys.path.insert(0, "..")

from pathlib import Path
from qymanager.converters import convert_qy70_to_qy700, convert_qy700_to_qy70


def main():
    # Paths
    syx_file = Path("../tests/fixtures/QY70_SGT.syx")
    template_file = Path("../tests/fixtures/TXX.Q7P")
    output_q7p = Path("output_pattern.Q7P")
    output_syx = Path("output_style.syx")

    # Convert QY70 -> QY700
    print("Converting QY70 SysEx to QY700 Q7P...")
    convert_qy70_to_qy700(
        source_path=syx_file,
        output_path=output_q7p,
        template_path=template_file,  # Use template for unknown areas
    )
    print(f"  Created: {output_q7p} ({output_q7p.stat().st_size} bytes)")

    # Convert back QY700 -> QY70
    print("\nConverting QY700 Q7P back to QY70 SysEx...")
    convert_qy700_to_qy70(source_path=output_q7p, output_path=output_syx)
    print(f"  Created: {output_syx} ({output_syx.stat().st_size} bytes)")

    print("\nDone! You can now load these files into your QY synthesizer.")


if __name__ == "__main__":
    main()
