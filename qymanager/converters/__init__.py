"""
Pattern converters for QY70 <-> QY700 format conversion.

This module provides bidirectional conversion between:
- QY70 SysEx (.syx) format
- QY700 Q7P (.Q7P) binary format

Example:
    from qymanager.converters import convert_qy70_to_qy700, convert_qy700_to_qy70

    # Convert QY70 style to QY700 pattern
    convert_qy70_to_qy700("style.syx", "pattern.Q7P")

    # Convert QY700 pattern to QY70 style
    convert_qy700_to_qy70("pattern.Q7P", "style.syx")
"""

from qymanager.converters.qy70_to_qy700 import QY70ToQY700Converter, convert_qy70_to_qy700
from qymanager.converters.qy700_to_qy70 import QY700ToQY70Converter, convert_qy700_to_qy70

__all__ = [
    "QY70ToQY700Converter",
    "QY700ToQY70Converter",
    "convert_qy70_to_qy700",
    "convert_qy700_to_qy70",
]
