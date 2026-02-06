"""
QYConv - Bidirectional converter for Yamaha QY70 and QY700 pattern files.

This library provides tools to:
- Read and write QY70 SysEx pattern files (.syx)
- Read and write QY700 binary pattern files (.Q7P)
- Convert patterns between QY70 and QY700 formats

Example usage:
    from qymanager import QY70Reader, QY700Writer
    from qymanager.converters import qy70_to_qy700

    # Read QY70 pattern
    pattern = QY70Reader.read("style.syx")

    # Convert and write to QY700 format
    qy700_data = qy70_to_qy700(pattern)
    QY700Writer.write(qy700_data, "pattern.Q7P")
"""

__version__ = "0.4.0"
__author__ = "QYConv Contributors"

from qymanager.formats.qy70.reader import QY70Reader
from qymanager.formats.qy70.writer import QY70Writer
from qymanager.formats.qy700.reader import QY700Reader
from qymanager.formats.qy700.writer import QY700Writer
from qymanager.models.pattern import Pattern
from qymanager.models.section import Section, SectionType
from qymanager.models.track import Track

__all__ = [
    "QY70Reader",
    "QY70Writer",
    "QY700Reader",
    "QY700Writer",
    "Pattern",
    "Section",
    "SectionType",
    "Track",
]
