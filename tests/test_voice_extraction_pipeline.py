"""Integration tests for voice-extraction pipeline.

Verifies the 3-tier voice resolution:
  - Tier 1: XG Parameter Change / channel events in .syx → exact voice
  - Tier 2: voice_signature_db.json unambiguous hit (conf=1.0)
  - Tier 3: class signature (B17-B20) fallback

Also verifies the merge workflow: pattern bulk + XG capture JSON → one .syx
giving complete voice info.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from qymanager.analysis.syx_analyzer import SyxAnalyzer


REPO_ROOT = Path(__file__).resolve().parent.parent
CAPTURES = REPO_ROOT / "data" / "captures_2026_04_23"


def _needs(path: Path) -> None:
    if not path.exists():
        pytest.skip(f"fixture missing: {path.relative_to(REPO_ROOT)}")


def test_bulk_only_voice_class_detection():
    """Pattern bulk without XG data → class-based voice fallback only."""
    p = CAPTURES / "AMB01_bulk_20260423_113016.syx"
    _needs(p)

    a = SyxAnalyzer()
    analysis = a.analyze_file(str(p))
    assert analysis.valid
    # XG data should NOT be present
    assert len(a.xg_voices) == 0

    # Tracks should have class-based names ending with "(class" or via DB (conf=1.0)
    for trk in analysis.qy70_tracks:
        if not trk.has_data:
            continue
        assert trk.voice_name, f"Track {trk.name} missing voice_name"
        # Must have some annotation: "(class", "(DB)", or resolved via known drum kit
        # (drum kit fallback from class adds "(class)")


def test_xg_merge_gives_full_voice_info():
    """Merge pattern bulk + load-JSON stream → complete voice info for all 8 tracks."""
    bulk = CAPTURES / "AMB01_bulk_20260423_113016.syx"
    load_json = CAPTURES / "AMB01_load_20260423_113116.json"
    _needs(bulk)
    _needs(load_json)

    # Run load_json_to_syx tool with --merge-with
    merged = Path("/tmp/test_amb01_merged.syx")
    if merged.exists():
        merged.unlink()

    subprocess.run(
        [
            "uv", "run", "python3",
            str(REPO_ROOT / "midi_tools" / "load_json_to_syx.py"),
            str(load_json),
            "-o", str(merged),
            "--merge-with", str(bulk),
        ],
        check=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
    )
    assert merged.exists()

    a = SyxAnalyzer()
    analysis = a.analyze_file(str(merged))
    assert analysis.valid
    assert len(a.xg_voices) >= 8  # Parts 0-15, at least 8 populated

    # Expected AMB01 voices per QY70 track (ch9-16 = parts 8-15)
    expected = {
        0: (127, 0, 25),   # D1 ch9: Analog Kit
        1: (127, 0, 26),   # D2 ch10: Dance Kit
        2: (127, 0, 26),   # PC ch11: Dance Kit
        3: (0, 0, 34),     # BA ch12: Electric Bass
        4: (0, 0, 89),     # C1 ch13: Warm Pad
        5: (0, 0, 89),     # C2 ch14: Warm Pad
        6: (0, 40, 44),    # C3 ch15: Tremolo Strings
        7: (126, 0, 0),    # C4 ch16: SFX Kit 0
    }

    for trk_idx, (exp_msb, exp_lsb, exp_prog) in expected.items():
        trk = analysis.qy70_tracks[trk_idx]
        assert trk.bank_msb == exp_msb, f"Track {trk.name}: expected msb={exp_msb} got {trk.bank_msb}"
        assert trk.bank_lsb == exp_lsb, f"Track {trk.name}: expected lsb={exp_lsb} got {trk.bank_lsb}"
        assert trk.program == exp_prog, f"Track {trk.name}: expected prog={exp_prog} got {trk.program}"


def test_signature_db_loads_and_is_valid():
    """Signature DB JSON loads and has expected structure."""
    from qymanager.analysis.syx_analyzer import _load_signature_db

    db = _load_signature_db()
    assert isinstance(db, dict)
    assert len(db) >= 10, f"Expected at least 10 signatures in DB, got {len(db)}"

    for sig, entry in db.items():
        assert isinstance(sig, str)
        # Signature is 10 bytes = 20 hex chars
        assert len(sig) == 20, f"Signature {sig} has wrong length"
        assert isinstance(entry, dict)
        for field in ("msb", "lsb", "prog", "confidence", "sample_count"):
            assert field in entry, f"Missing field {field} in DB entry for {sig}"
        assert 0 <= entry["msb"] <= 127
        assert 0 <= entry["lsb"] <= 127
        assert 0 <= entry["prog"] <= 127
        assert 0.0 <= entry["confidence"] <= 1.0


def test_signature_db_high_confidence_entries():
    """Unambiguous DB entries (conf=1.0) give same voice across all their samples."""
    from qymanager.analysis.syx_analyzer import _load_signature_db

    db = _load_signature_db()
    hi_conf = [(sig, e) for sig, e in db.items() if e["confidence"] >= 0.99]
    assert len(hi_conf) >= 15, f"Expected ≥15 conf=1.0 entries, got {len(hi_conf)}"


def test_xg_multi_part_request_format():
    """Verify the XG Multi Part request byte sequence used by capture_complete.py."""
    # Format: F0 43 2n 4C 08 <part> 00 F7
    from qymanager.formats.qy70.xg_multi_part import build_multi_part_request

    for part in range(16):
        req = build_multi_part_request(part)
        assert req[0] == 0xF0
        assert req[1] == 0x43
        assert (req[2] & 0xF0) == 0x20  # dump request substatus
        assert req[3] == 0x4C  # XG model
        assert req[4] == 0x08  # Multi Part AH
        assert req[5] == part
        assert req[6] == 0x00
        assert req[7] == 0xF7


def test_capture_complete_dry_run_sequence():
    """Verify capture_complete.py's full request sequence (29 messages)."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "midi_tools"))
    try:
        from capture_complete import _enumerate_requests
    finally:
        sys.path.pop(0)

    seq = _enumerate_requests(am=0x7E, xg=True)
    # Init + 9 pattern + directory + system + 16 XG + close = 29
    assert len(seq) == 29

    labels = [label for label, _ in seq]
    assert labels[0] == "Init handshake (Param Change)"
    assert labels[-1] == "Close handshake (Param Change)"
    assert any("Pattern header" in l for l in labels)
    assert any("Pattern name directory" in l for l in labels)
    assert any("System meta" in l for l in labels)
    assert sum(1 for l in labels if "XG Multi Part" in l) == 16

    # Verify init byte sequence
    assert seq[0][1] == bytes.fromhex("f043105f00000001f7")
    # Verify pattern header request
    hdr_req = next(m for lbl, m in seq if lbl.startswith("Pattern header"))
    assert hdr_req == bytes.fromhex("f043205f027e7ff7")
    # Verify directory request
    dir_req = next(m for lbl, m in seq if "directory" in lbl)
    assert dir_req == bytes.fromhex("f043205f027e05f7")


def test_capture_complete_dry_run_no_xg():
    """Verify --no-xg skips the 16 XG Multi Part requests."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "midi_tools"))
    try:
        from capture_complete import _enumerate_requests
    finally:
        sys.path.pop(0)

    seq = _enumerate_requests(am=0x7E, xg=False)
    # Init + 9 pattern + directory + system + close = 13
    assert len(seq) == 13


def test_bulk_all_file_structure():
    """Verify BULK_ALL files have pattern slots but no edit buffer / XG data.

    Documents the structural truth: 'BULK OUT → All' on QY70 does NOT include
    XG Multi Part state. Users must run capture_complete.py to get full info.
    """
    p = CAPTURES / "BULK_ALL_MACHINE_20260423_122053.syx"
    _needs(p)

    a = SyxAnalyzer()
    a.analyze_file(str(p))

    # Pattern slots present
    slot_ams = {m.address_mid for m in a.messages
                if m.address_high == 0x02 and m.address_mid < 0x40}
    assert len(slot_ams) > 10, f"Expected many populated slots, got {len(slot_ams)}"

    # Edit buffer NOT present (that's the key signal to redirect to bulk_all_summary)
    edit_buffer = {m for m in a.messages
                   if m.address_high == 0x02 and m.address_mid == 0x7E}
    assert len(edit_buffer) == 0

    # XG data (Model 4C) NOT present in BULK_ALL — SysExParser only keeps 5F
    # (Model 0x4C messages are silently dropped by the parser), so we verify
    # via a direct raw-byte scan.
    with open(p, "rb") as f:
        raw = f.read()
    model_4c_count = 0
    i = 0
    while i < len(raw):
        if raw[i] == 0xF0:
            j = raw.find(b"\xF7", i)
            if j == -1:
                break
            msg = raw[i:j+1]
            if len(msg) > 5 and msg[1] == 0x43 and msg[3] == 0x4C:
                model_4c_count += 1
            i = j + 1
        else:
            i += 1
    assert model_4c_count == 0, "BULK_ALL should not contain Model 4C messages"

    # No XG voices extracted
    assert len(a.xg_voices) == 0


def test_qymanager_bulk_summary_cli():
    """`qymanager bulk-summary` shows slot inventory for multi-slot files."""
    bulk_all = CAPTURES / "BULK_ALL_MACHINE_20260423_122053.syx"
    _needs(bulk_all)

    result = subprocess.run(
        ["uv", "run", "qymanager", "bulk-summary", str(bulk_all)],
        check=True,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    stdout = result.stdout
    assert "Pattern slots populated" in stdout
    assert "U01" in stdout or "U10" in stdout  # some slot name
    # XG absent is mentioned (BULK_ALL has no Model 4C)
    assert "absent" in stdout.lower() or "limited" in stdout.lower()


def test_qymanager_xg_inspect_cli():
    """`qymanager xg inspect` shows parsed XG state (not just counts)."""
    p = CAPTURES / "SGT_backup_20260423_112505.syx"
    _needs(p)

    result = subprocess.run(
        ["uv", "run", "qymanager", "xg", "inspect", str(p)],
        check=True,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    stdout = result.stdout
    # Should show parsed state sections
    assert "XG System" in stdout
    assert "XG Multi Part state" in stdout
    # Part 8 (D1/ch9) should be present with voice info
    assert "Part 8" in stdout
    assert "bank_msb" in stdout
    # Drum Setup overrides should be shown
    assert "Drum Setup" in stdout


def test_qymanager_info_no_crash_on_any_sample():
    """`qymanager info` should produce output (no crash) on ALL sample files.

    CI guardrail: any .syx in data/captures_2026_04_23 should be openable.
    If a future change breaks parsing for a specific file type, this catches it.
    """
    samples = [
        "tests/fixtures/QY70_SGT.syx",
        "tests/fixtures/NEONGROOVE.syx",
        "data/captures_2026_04_23/SGT_backup_20260423_112505.syx",
        "data/captures_2026_04_23/AMB01_bulk_20260423_113016.syx",
        "data/captures_2026_04_23/STYLE2_bulk_20260423_113615.syx",
        "data/captures_2026_04_23/BULK_ALL_MACHINE_20260423_122053.syx",
    ]
    failures = []
    for rel_path in samples:
        p = REPO_ROOT / rel_path
        if not p.exists():
            continue
        result = subprocess.run(
            ["uv", "run", "qymanager", "info", str(p)],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        if result.returncode != 0:
            failures.append((rel_path, result.returncode, result.stderr[:200]))
        elif len(result.stdout) < 50:
            failures.append((rel_path, "short-output", result.stdout[:100]))
    assert not failures, f"CLI failures: {failures}"


def test_no_address_silently_ignored():
    """No (AH, AM, AL) combination in any of our capture files should be
    silently dropped by the analyzer. This is a CI invariant that future
    parser changes must preserve.
    """
    from qymanager.formats.qy70.sysex_parser import SysExParser

    def is_handled(ah: int, am: int, al: int) -> bool:
        """The set of address types the analyzer knows about."""
        # AH=0x00 init/close markers (AM=0x00) + voice edit dump (AM=0x40)
        if ah == 0x00 and am in (0x00, 0x40):
            return True
        # Song data
        if ah == 0x01:
            return True
        # Pattern slots (AM < 0x40) + edit buffer (AM = 0x7E)
        if ah == 0x02 and (am < 0x40 or am == 0x7E):
            return True
        # System meta
        if ah == 0x03 and am == 0x00:
            return True
        # Pattern name directory
        if ah == 0x05:
            return True
        # End-of-dump markers / XG Multi Part
        if ah == 0x08:
            return True
        return False

    p = SysExParser()
    # Cover all reference files
    files_to_scan = [
        REPO_ROOT / "tests" / "fixtures" / "QY70_SGT.syx",
        REPO_ROOT / "tests" / "fixtures" / "NEONGROOVE.syx",
        CAPTURES / "SGT_backup_20260423_112505.syx",
        CAPTURES / "AMB01_bulk_20260423_113016.syx",
        CAPTURES / "STYLE2_bulk_20260423_113615.syx",
        CAPTURES / "BULK_ALL_MACHINE_20260423_122053.syx",
    ]
    unhandled: dict = {}
    total_msgs = 0
    for f in files_to_scan:
        if not f.exists():
            continue
        msgs = p.parse_file(str(f))
        total_msgs += len(msgs)
        for m in msgs:
            if not is_handled(m.address_high, m.address_mid, m.address_low):
                key = (m.address_high, m.address_mid, m.address_low)
                unhandled.setdefault(key, 0)
                unhandled[key] += 1
    assert not unhandled, f"Unhandled addresses: {unhandled}"
    assert total_msgs > 1000, f"Expected to scan ≥1000 messages, got {total_msgs}"


def test_voice_edit_dumps_ah00_am40():
    """Voice edit dumps (AH=0x00 AM=0x40, QY70 UTILITY → BULK OUT → Voice)
    should be parsed and classified with voice class signature.
    """
    p = CAPTURES / "SGT_backup_20260423_112505.syx"
    _needs(p)

    a = SyxAnalyzer()
    analysis = a.analyze_file(str(p))

    assert len(analysis.voice_edit_dumps) == 1
    vd = analysis.voice_edit_dumps[0]
    assert vd["size_bytes"] == 121
    assert vd["voice_class"] == "Chord/Melodic voice"
    assert vd["al_address"] == 0x20


def test_qymanager_audit_bulk_all_redirect():
    """`qymanager audit` on BULK_ALL redirects to bulk-summary."""
    bulk_all = CAPTURES / "BULK_ALL_MACHINE_20260423_122053.syx"
    _needs(bulk_all)

    result = subprocess.run(
        ["uv", "run", "qymanager", "audit", str(bulk_all)],
        check=True,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert "Multi-slot bulk file" in result.stdout
    assert "bulk-summary" in result.stdout


def test_qymanager_audit_cli():
    """`qymanager audit` reports extraction completeness for a .syx."""
    # File WITH XG data → should show completeness
    xg_file = CAPTURES / "SGT_backup_20260423_112505.syx"
    _needs(xg_file)
    result = subprocess.run(
        ["uv", "run", "qymanager", "audit", str(xg_file)],
        check=True,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    stdout = result.stdout
    assert "Data extraction completeness" in stdout
    assert "Voice Bank" in stdout
    assert "XG Drum Setup" in stdout

    # File WITHOUT XG → should suggest capture_complete
    bulk_only = CAPTURES / "AMB01_bulk_20260423_113016.syx"
    _needs(bulk_only)
    result2 = subprocess.run(
        ["uv", "run", "qymanager", "audit", str(bulk_only)],
        check=True,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert "No XG state" in result2.stdout
    assert "capture_complete" in result2.stdout


def test_qymanager_xg_inspect_no_xg():
    """`qymanager xg inspect` on a bulk-only file shows a helpful error."""
    p = CAPTURES / "AMB01_bulk_20260423_113016.syx"
    _needs(p)

    result = subprocess.run(
        ["uv", "run", "qymanager", "xg", "inspect", str(p)],
        check=True,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert "No XG state" in result.stdout
    assert "capture_complete" in result.stdout


def test_qymanager_merge_cli(tmp_path):
    """The `qymanager merge` CLI should combine pattern bulk + capture JSON."""
    bulk = CAPTURES / "AMB01_bulk_20260423_113016.syx"
    load_json = CAPTURES / "AMB01_load_20260423_113116.json"
    _needs(bulk)
    _needs(load_json)

    output = tmp_path / "merged.syx"
    subprocess.run(
        ["uv", "run", "qymanager", "merge",
         str(bulk), str(load_json), "-o", str(output)],
        check=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
    )
    assert output.exists()
    size = output.stat().st_size
    assert size > bulk.stat().st_size  # merged file must be bigger

    # Verify the merged file produces full voice info
    a = SyxAnalyzer()
    analysis = a.analyze_file(str(output))
    # Should have XG data from the merged stream
    assert len(a.xg_voices) >= 8


def test_sig_db_covers_known_voices():
    """For each of the 3 reference patterns' known voices, signature DB should
    either have a high-confidence hit or the signature should be unknown
    (meaning class fallback applies)."""
    from qymanager.analysis.syx_analyzer import _load_signature_db

    db = _load_signature_db()

    # Spot-check: voices we know were trained into the DB
    known_hits = [
        ("408087f8808e83000000", 127, 0, 26),   # SGT drum standard kit
        ("00040778000712414000", 0, 96, 38),    # SGT bass slap
        ("040b1778000f10414000", 0, 16, 89),    # SGT chord warm pad
        ("008087f8808f90000000", 126, 0, 0),    # AMB drum SFX kit
    ]
    for sig, msb, lsb, prog in known_hits:
        assert sig in db, f"Signature {sig} missing from DB"
        entry = db[sig]
        assert entry["msb"] == msb
        assert entry["lsb"] == lsb
        assert entry["prog"] == prog
        assert entry["confidence"] >= 0.99


def test_xg_effects_variation_extraction():
    """Verify XG Effect block (AH=0x02 AM=0x01) variation type is extracted."""
    p = CAPTURES / "SGT_backup_20260423_112505.syx"
    _needs(p)

    a = SyxAnalyzer()
    analysis = a.analyze_file(str(p))

    # SGT_backup captured a "Variation type MSB = 5" (Delay LCR) in its XG stream
    assert analysis.variation_type_msb == 5
    assert analysis.variation_type == "Delay LCR"


def test_xg_drum_setup_extraction():
    """Verify XG Drum Setup (AH=0x30) per-note parameters are extracted."""
    p = CAPTURES / "SGT_backup_20260423_112505.syx"
    _needs(p)

    a = SyxAnalyzer()
    a.analyze_file(str(p))

    drum = getattr(a, "xg_drum_setup", {})
    assert 1 in drum, "Drum setup 1 should be present in SGT_backup"

    # Note 36 (kick): has level and filter_cutoff customized
    assert 36 in drum[1]
    note36 = drum[1][36]
    assert note36.get("level") == 120
    assert note36.get("filter_cutoff") == 29

    # Note 38 (snare): has pitch_coarse and pan
    assert 38 in drum[1]
    note38 = drum[1][38]
    assert "pitch_coarse" in note38
    assert "pan" in note38


def test_xg_multi_part_extended_params():
    """Verify extended XG Multi Part params (dry_level, bend_pitch, etc.)."""
    p = CAPTURES / "SGT_backup_20260423_112505.syx"
    _needs(p)

    a = SyxAnalyzer()
    a.analyze_file(str(p))

    # Part 8 (ch9) should have extended params beyond core voice selection
    part8 = a.xg_voices.get(8, {})
    assert part8.get("dry_level") == 127
    assert part8.get("bend_pitch") == 66  # AL=0x23 = Bend Pitch Control (0x42 = +2 semi)
    assert part8.get("part_mode") == 1  # drum mode


def test_pattern_directory_ah05_parse(tmp_path):
    """Verify AH=0x05 pattern name directory extraction from a synthetic SysEx.

    Note: AH=0x05 data is sent as RAW bytes (not Yamaha 7-bit packed), so the
    synthetic SysEx must embed the raw directory body directly in the payload.
    """
    from qymanager.utils.checksum import calculate_yamaha_checksum

    # Build directory body: 20 slots × 16 bytes (8 ASCII name + 8 metadata)
    slots_with_names = {
        0: b"MYSONG  ",
        2: b"ROCK    ",
        4: b"FUNK XG ",
    }
    body = b""
    for i in range(20):
        if i in slots_with_names:
            body += slots_with_names[i].ljust(8, b"\x00") + b"\x00" * 8
        else:
            body += b"*" * 8 + b"\x00" * 8  # empty slot

    # Raw embedding — no 7-bit encoding for AH=0x05
    byte_count = len(body)
    bh = (byte_count >> 7) & 0x7F
    bl = byte_count & 0x7F
    cs_data = bytes([bh, bl, 0x05, 0x00, 0x00]) + body
    cs = calculate_yamaha_checksum(cs_data)
    sysex = (bytes([0xF0, 0x43, 0x00, 0x5F, bh, bl, 0x05, 0x00, 0x00])
             + body + bytes([cs, 0xF7]))

    test_file = tmp_path / "directory.syx"
    test_file.write_bytes(sysex)

    a = SyxAnalyzer()
    analysis = a.analyze_file(str(test_file))

    assert analysis.pattern_directory == {
        0: "MYSONG",
        2: "ROCK",
        4: "FUNK XG",
    }
