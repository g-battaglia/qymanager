"""Tests for QY700 Q7P parser."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.formats.qy700.binary_parser import Q7PParser
from qymanager.formats.qy700.reader import QY700Reader


class TestQ7PParser:
    """Test cases for Q7P binary parser."""

    def test_parse_header(self, q7p_data):
        """Test parsing Q7P header."""
        parser = Q7PParser()
        header, sections = parser.parse_bytes(q7p_data)

        assert header.is_valid()
        assert header.magic == b"YQ7PAT     V1.00"

    def test_file_size_validation(self):
        """Test that incorrect file size is rejected."""
        parser = Q7PParser()

        # Too small
        with pytest.raises(ValueError, match="Invalid Q7P file size"):
            parser.parse_bytes(b"short")

        # Too large
        with pytest.raises(ValueError, match="Invalid Q7P file size"):
            parser.parse_bytes(bytes(4000))

    def test_invalid_header_rejected(self):
        """Test that invalid header is rejected."""
        parser = Q7PParser()

        # Create fake file with wrong header
        fake_data = b"WRONGHEADER12345" + bytes(3072 - 16)

        with pytest.raises(ValueError, match="Invalid Q7P header"):
            parser.parse_bytes(fake_data)

    def test_section_extraction(self, q7p_data):
        """Test that sections are extracted."""
        parser = Q7PParser()
        header, sections = parser.parse_bytes(q7p_data)

        # Should have 6 sections
        assert len(sections) == 6

        # Each section should have an index 0-5
        indices = [s.index for s in sections]
        assert indices == [0, 1, 2, 3, 4, 5]

    def test_get_tempo(self, q7p_data):
        """Test tempo extraction."""
        parser = Q7PParser()
        parser.parse_bytes(q7p_data)

        tempo = parser.get_tempo()

        # Should be a reasonable tempo
        assert 40 <= tempo <= 240

    def test_get_template_name(self, q7p_data):
        """Test template name extraction."""
        parser = Q7PParser()
        parser.parse_bytes(q7p_data)

        name = parser.get_template_name()

        # Should be a string
        assert isinstance(name, str)

    def test_dump_structure(self, q7p_data):
        """Test structure dump for debugging."""
        parser = Q7PParser()
        parser.parse_bytes(q7p_data)

        dump = parser.dump_structure()

        assert "Q7P File Structure" in dump
        assert "Header valid: True" in dump


class TestQY700Reader:
    """Test cases for QY700 reader."""

    def test_read_file(self, q7p_file):
        """Test reading a Q7P file into Pattern."""
        if not q7p_file.exists():
            pytest.skip("Test file not found")

        pattern = QY700Reader.read(q7p_file)

        assert pattern is not None
        assert pattern.source_format == "qy700"

    def test_pattern_has_sections(self, q7p_file):
        """Test that pattern has expected sections."""
        if not q7p_file.exists():
            pytest.skip("Test file not found")

        pattern = QY700Reader.read(q7p_file)

        # Should have at least basic sections
        assert len(pattern.sections) >= 6

    def test_section_has_tracks(self, q7p_file):
        """Test that sections have tracks."""
        if not q7p_file.exists():
            pytest.skip("Test file not found")

        pattern = QY700Reader.read(q7p_file)

        for section in pattern.sections.values():
            assert len(section.tracks) == 8

    def test_can_read_check(self, q7p_file, fixtures_dir):
        """Test file format detection."""
        if not q7p_file.exists():
            pytest.skip("Test file not found")

        # Valid Q7P file
        assert QY700Reader.can_read(q7p_file) is True

        # Invalid file (SysEx)
        syx_file = fixtures_dir / "QY70_SGT.syx"
        if syx_file.exists():
            assert QY700Reader.can_read(syx_file) is False

    def test_get_file_info(self, q7p_file):
        """Test getting file info without full parse."""
        if not q7p_file.exists():
            pytest.skip("Test file not found")

        info = QY700Reader.get_file_info(q7p_file)

        assert info["valid"] is True
        assert info["size"] == 3072
        assert "YQ7PAT" in info["header"]


class TestQ7PComparison:
    """Test comparing different Q7P files."""

    def test_compare_empty_and_filled(self, fixtures_dir):
        """Compare empty template with data-filled pattern."""
        empty_file = fixtures_dir / "TXX.Q7P"
        filled_file = fixtures_dir / "T01.Q7P"

        if not empty_file.exists() or not filled_file.exists():
            pytest.skip("Test files not found")

        empty = QY700Reader.read(empty_file)
        filled = QY700Reader.read(filled_file)

        # Both should be valid patterns
        assert empty is not None
        assert filled is not None

        # Both should have same number of sections
        assert len(empty.sections) == len(filled.sections)
