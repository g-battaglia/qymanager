"""
XG voice name lookup — minimal subset of the QY70 voice tables.

Source of authority: `manual/QY70/QY70_LIST_BOOK.PDF`
- XG Normal Voice List (pag 2-3)
- XG Drum Voice List (pag 4-5)

We ship only what is needed to make `parse_all_events` captures readable:
- Bank 0 = GM Level 1 (128 programs) — the most common case
- XG Drum Kits (Bank 127, LSB 0, selected programs)

For exotic XG variation banks (Bank 1/3/6/8/..., 64 SFX, etc.) we fall back
to "Bank N Prog X" — extend as needed when a real capture exposes them.
"""

from __future__ import annotations

# GM Level 1 — Bank 0 programs 0..127.
# (Standard General MIDI 1 list, matches the QY70 XG Normal Voice Bank 0.)
GM_VOICES: tuple[str, ...] = (
    "GrandPno", "BrtPno", "EGrand", "HnkyTnk", "E.Piano1", "E.Piano2",
    "Harpsi.", "Clavi.",
    "Celesta", "Glocken", "MusicBox", "Vibes", "Marimba", "Xylophon",
    "TubulBel", "Dulcimer",
    "DrawOrg", "PercOrg", "RockOrg", "ChrchOrg", "ReedOrg", "Acordion",
    "Harmnica", "TangoAcd",
    "NylonGtr", "SteelGtr", "Jazz Gtr", "CleanGtr", "Mute Gtr", "Ovrdrive",
    "Dist.Gtr", "GtrHarmo",
    "Aco. Bs.", "FngrBass", "PickBass", "Fretless", "Slap Bs1", "Slap Bs2",
    "Syn Bs 1", "Syn Bs 2",
    "Violin", "Viola", "Cello", "Contrabs", "Trem Str", "Pizz Str",
    "Harp", "Timpani",
    "Strngs 1", "Strngs 2", "SynStr 1", "SynStr 2", "ChoirAah", "VoiceOoh",
    "SynVoice", "Orch Hit",
    "Trumpet", "Trombone", "Tuba", "Mute Trp", "Fr Horn", "BrassSec",
    "Syn Br 1", "Syn Br 2",
    "SprnoSax", "Alto Sax", "Tenor Sx", "Bari Sax", "Oboe", "Eng Horn",
    "Bassoon", "Clarinet",
    "Piccolo", "Flute", "Recorder", "Pan Flut", "BottlBlw", "Shakhchi",
    "Whistle", "Ocarina",
    "SquareLd", "Saw.Lead", "Calliope", "Chiffer", "Charang", "Voice Ld",
    "Fifths", "Bass&Ld",
    "NewAgePd", "WarmPad", "PolySyPd", "ChoirPad", "BowedPad", "MetalPad",
    "Halo Pad", "SweepPad",
    "Rain", "SoundTrk", "Crystal", "Atmosphr", "Bright", "Goblin",
    "Echoes", "Sci-Fi",
    "Sitar", "Banjo", "Shamisen", "Koto", "Kalimba", "Bagpipe",
    "Fiddle", "Shanai",
    "TnklBell", "Agogo", "SteelDrm", "WoodBlok", "TaikoDrm", "MelodTom",
    "Syn Drum", "RevCymbl",
    "FretNoiz", "BrthNoiz", "Seashore", "Tweet", "Telphone", "Helicptr",
    "Applause", "Gunshot",
)
assert len(GM_VOICES) == 128, f"GM list must be 128 entries, got {len(GM_VOICES)}"


# XG Drum kits — Bank MSB=127, LSB=0 (primary kits shown on QY70 pag 4-5).
# Programs confirmed on the printed table; gaps default to "XG Drum Kit".
XG_DRUM_KITS: dict[int, str] = {
    0: "Standard Kit",
    1: "Standard Kit 2",
    2: "Dry Kit",
    4: "Bright Kit",
    8: "Room Kit",
    10: "Dark Room Kit",
    16: "Rock Kit",
    17: "Rock Kit 2",
    24: "Electro Kit",
    25: "Analog Kit",
    32: "Jazz Kit",
    40: "Brush Kit",
    48: "Classic Kit",
    127: "SFX Kit",
}


# Standard Kit drum note map — XG Drum Voice List (pag 4 of QY70 LIST_BOOK).
# Covers the GM range 13..84 inclusive; other XG kits share the same layout
# with per-voice substitutions (e.g. Rock Kit has Kick Rock on note 36).
GM_DRUM_NOTES: dict[int, str] = {
    13: "Surdo Mute",       14: "Surdo Open",       15: "Hi Q",
    16: "Whip Slap",        17: "Scratch H",        18: "Scratch L",
    19: "Finger Snap",      20: "Click Noise",      21: "Metronome Click",
    22: "Metronome Bell",   23: "Seq Click L",      24: "Seq Click H",
    25: "Brush Tap",        26: "Brush Swirl",      27: "Brush Slap",
    28: "Brush Tap Swirl",  29: "Snare Roll",       30: "Castanet",
    31: "Snare Soft",       32: "Sticks",           33: "Kick Soft",
    34: "Open Rim Shot",    35: "Kick Tight H",     36: "Kick",
    37: "Side Stick",       38: "Snare",            39: "Hand Clap",
    40: "Snare Tight",      41: "Floor Tom H",      42: "Hi-Hat Closed",
    43: "Floor Tom L",      44: "Hi-Hat Pedal",     45: "Low Tom",
    46: "Hi-Hat Open",      47: "Mid Tom L",        48: "Mid Tom H",
    49: "Crash Cymbal 1",   50: "High Tom",         51: "Ride Cymbal 1",
    52: "Chinese Cymbal",   53: "Ride Cup",         54: "Tambourine",
    55: "Splash Cymbal",    56: "Cowbell",          57: "Crash Cymbal 2",
    58: "Vibraslap",        59: "Ride Cymbal 2",    60: "Bongo H",
    61: "Bongo L",          62: "Conga H Mute",     63: "Conga H Open",
    64: "Conga L",          65: "Timbales H",       66: "Timbales L",
    67: "Agogo H",          68: "Agogo L",          69: "Cabasa",
    70: "Maracas",          71: "Samba Whistle H",  72: "Samba Whistle L",
    73: "Guiro Short",      74: "Guiro Long",       75: "Claves",
    76: "Wood Block H",     77: "Wood Block L",     78: "Cuica Mute",
    79: "Cuica Open",       80: "Triangle Mute",    81: "Triangle Open",
    82: "Shaker",           83: "Jingle Bells",     84: "Bell Tree",
}


def drum_note_name(note: int) -> str:
    """Return the Standard Kit name for a drum note, or a fallback label."""
    return GM_DRUM_NOTES.get(note, f"note {note}")


def voice_name(bank_msb: int, bank_lsb: int, program: int) -> str:
    """Return a human-readable voice name.

    Rules:
    - MSB=127 → drum kit selected by `program` (the LSB is the variation bank).
    - MSB=0, LSB=0 → GM program name from `GM_VOICES`.
    - anything else → best-effort fallback "XG MSB/LSB Prog".
    """
    if bank_msb == 127:
        name = XG_DRUM_KITS.get(program, f"XG Drum Kit prog={program}")
        return f"{name} (drum)"
    if bank_msb == 0 and bank_lsb == 0:
        if 0 <= program < 128:
            return GM_VOICES[program]
        return f"GM prog={program}"
    return f"XG MSB={bank_msb} LSB={bank_lsb} Prog={program}"
