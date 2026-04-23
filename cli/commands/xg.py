"""
XG command - parse and analyze XG Parameter Change SysEx streams.

Thin CLI wrapper around midi_tools/xg_param.py.
"""

from pathlib import Path

import typer
from rich.console import Console

console = Console()
app = typer.Typer(help="Analyze XG Parameter Change SysEx streams.")


@app.command("parse")
def parse_cmd(
    file: Path = typer.Argument(..., help="Path to .syx containing XG Param Change"),
    limit: int = typer.Option(
        0, "--limit", "-n", help="Show only first N messages (0 = all)"
    ),
) -> None:
    """Parse a .syx file and print decoded XG messages, one per line."""
    import sys as _sys

    _sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from midi_tools.xg_param import parse_file

    msgs = parse_file(file)
    console.print(f"[dim]# {file}: {len(msgs)} XG Param Change messages[/dim]")
    shown = msgs[:limit] if limit > 0 else msgs
    for m in shown:
        console.print(m.pretty())
    if limit > 0 and len(msgs) > limit:
        console.print(f"[dim]# ... ({len(msgs) - limit} more)[/dim]")


@app.command("summary")
def summary_cmd(
    file: Path = typer.Argument(..., help="Path to .syx containing XG Param Change"),
) -> None:
    """Summarize XG Param Change messages: counts by AH, per-part, per-AL."""
    import sys as _sys
    from collections import Counter

    _sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from midi_tools.xg_param import (
        AH_EFFECT,
        AH_MULTI_PART,
        AH_NAMES,
        EFFECT_AL_NAMES,
        MULTI_PART_AL_NAMES,
        parse_file,
    )

    msgs = parse_file(file)
    console.print(f"[bold]# {file}: {len(msgs)} XG messages[/bold]")
    ah_counts = Counter(m.ah for m in msgs)
    console.print("\n[cyan]## By AH:[/cyan]")
    for ah, c in sorted(ah_counts.items()):
        console.print(f"  0x{ah:02X} {AH_NAMES.get(ah,'?'):<20s}: {c}")

    mp = [m for m in msgs if m.ah == AH_MULTI_PART]
    if mp:
        console.print("\n[cyan]## Multi Part by NN (part):[/cyan]")
        nn_counts = Counter(m.am for m in mp)
        for nn, c in sorted(nn_counts.items()):
            console.print(f"  Part {nn:02d}: {c}")
        console.print("\n[cyan]## Multi Part by AL:[/cyan]")
        al_counts = Counter(m.al for m in mp)
        for al, c in sorted(al_counts.items()):
            name = MULTI_PART_AL_NAMES.get(al, f"AL={al:02X}")
            console.print(f"  0x{al:02X} {name:<30s}: {c}")

    fx = [m for m in msgs if m.ah == AH_EFFECT]
    if fx:
        console.print("\n[cyan]## Effect by AL:[/cyan]")
        al_counts = Counter(m.al for m in fx)
        for al, c in sorted(al_counts.items()):
            name = EFFECT_AL_NAMES.get(al, f"AL={al:02X}")
            console.print(f"  0x{al:02X} {name:<30s}: {c}")


@app.command("diff")
def diff_cmd(
    a: Path = typer.Argument(..., help="First .syx file"),
    b: Path = typer.Argument(..., help="Second .syx file"),
) -> None:
    """Diff two XG streams: only-in-A, only-in-B, changed values."""
    import sys as _sys
    from collections import OrderedDict

    _sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from midi_tools.xg_param import parse_file

    ma = parse_file(a)
    mb = parse_file(b)

    def keyed(msgs):
        d = OrderedDict()
        for m in msgs:
            d[(m.ah, m.am, m.al)] = m
        return d

    ka = keyed(ma)
    kb = keyed(mb)
    only_a = [k for k in ka if k not in kb]
    only_b = [k for k in kb if k not in ka]
    changed = [(k, ka[k], kb[k]) for k in ka if k in kb and ka[k].data != kb[k].data]

    console.print(f"[bold]# Diff {a} vs {b}[/bold]")
    console.print(f"Only in A: {len(only_a)}, Only in B: {len(only_b)}, Changed: {len(changed)}")
    if only_a:
        console.print("\n[cyan]## Only in A:[/cyan]")
        for k in only_a[:20]:
            console.print(f"  {ka[k].decode()}")
    if only_b:
        console.print("\n[cyan]## Only in B:[/cyan]")
        for k in only_b[:20]:
            console.print(f"  {kb[k].decode()}")
    if changed:
        console.print("\n[cyan]## Changed:[/cyan]")
        for k, ma_msg, mb_msg in changed[:40]:
            da = " ".join(f"{x:02X}" for x in ma_msg.data)
            db = " ".join(f"{x:02X}" for x in mb_msg.data)
            console.print(
                f"  AH={k[0]:02X} AM={k[1]:02X} AL={k[2]:02X}: {da} → {db}  "
                f"[dim][{ma_msg.decode()}][/dim]"
            )


@app.command("emit")
def emit_cmd(
    ah: str = typer.Option(..., "--ah", help="Address High (hex, e.g. 08)"),
    am: str = typer.Option(..., "--am", help="Address Mid (hex)"),
    al: str = typer.Option(..., "--al", help="Address Low (hex)"),
    data: str = typer.Option(..., "--data", help="Comma-separated hex data bytes"),
) -> None:
    """Build an XG Param Change and print it as hex + decoded."""
    import sys as _sys

    _sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from midi_tools.xg_param import build_xg, parse_xg

    ah_v = int(ah, 16)
    am_v = int(am, 16)
    al_v = int(al, 16)
    data_v = [int(x, 16) for x in data.split(",")]
    raw = build_xg(ah_v, am_v, al_v, data_v)
    console.print(" ".join(f"{b:02x}" for b in raw))
    m = parse_xg(raw)
    if m:
        console.print(f"[dim]# {m.decode()}[/dim]")


@app.command("snapshots")
def snapshots_cmd(
    file: Path = typer.Argument(..., help="Path to .syx containing XG Param Change"),
    limit: int = typer.Option(
        0, "--limit", "-n", help="Show only first N snapshots (0 = all)"
    ),
    names: bool = typer.Option(
        False, "--names/--no-names",
        help="Expand DS2 notes to Standard Kit names",
    ),
) -> None:
    """Segment an XG stream into per-preset snapshots (XG System On / Drum
    Setup Reset as boundaries) and print a compact summary per snapshot."""
    import sys as _sys

    _sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from midi_tools.xg_param import PART_MODE_NAMES, parse_file, segment_snapshots
    from midi_tools.xg_voices import drum_note_name

    msgs = parse_file(file)
    snaps = segment_snapshots(msgs)
    console.print(
        f"[bold]{file}[/bold]: {len(msgs)} XG msg → {len(snaps)} snapshots"
    )

    shown = snaps[:limit] if limit > 0 else snaps
    for s in shown:
        pm_parts = ", ".join(
            f"P{p:02d}={PART_MODE_NAMES.get(m, str(m))[:3]}"
            for p, m in sorted(s.part_modes.items())
        ) or "—"
        if s.ds2_notes:
            if names:
                ds2 = "notes=" + ", ".join(
                    f"{n:02X}({drum_note_name(n)})" for n in s.ds2_notes
                )
            else:
                ds2 = "notes=" + ",".join(f"{n:02X}" for n in s.ds2_notes)
        else:
            ds2 = "—"
        var = f"var={s.var_type}" if s.var_type else "var=—"
        console.print(
            f"  [cyan]#{s.idx:02d}[/cyan] {s.boundary:<8s} "
            f"msgs={len(s.messages):3d}  {var:<10s}  {pm_parts:<40s}  {ds2}"
        )
    if limit > 0 and len(snaps) > limit:
        console.print(f"  [dim]... ({len(snaps) - limit} more)[/dim]")


@app.command("inspect")
def inspect_cmd(
    file: Path = typer.Argument(..., help="Path to .syx containing XG state"),
) -> None:
    """Show the RESULTING XG state after parsing all Parameter Change messages.

    Unlike `xg summary` (message counts), this shows the ACTUAL per-part voice,
    mixer, filter, effects, drum-setup values from the analyzer's 3-tier
    resolver. Useful to verify what qymanager info would extract.
    """
    from qymanager.analysis.syx_analyzer import SyxAnalyzer

    a = SyxAnalyzer()
    a.analyze_file(str(file))

    console.print(f"[bold]{file}[/bold]")
    console.print()

    # System
    if a.xg_system:
        console.print("[bold yellow]XG System[/bold yellow]")
        for k, v in sorted(a.xg_system.items()):
            console.print(f"  {k}: {v}")
        console.print()

    # Effects
    if a.xg_effects:
        console.print("[bold green]XG Effects[/bold green]")
        for k, v in sorted(a.xg_effects.items()):
            console.print(f"  {k}: {v}")
        console.print()

    # Multi Part per channel
    if a.xg_voices:
        console.print("[bold cyan]XG Multi Part state[/bold cyan]")
        track_names = ["", "", "", "", "", "", "", "",
                       "D1", "D2", "PC", "BA", "C1", "C2", "C3", "C4"]
        for part_num in sorted(a.xg_voices.keys()):
            v = a.xg_voices[part_num]
            if not v:
                continue
            tname = f"{track_names[part_num]}/" if part_num >= 8 and track_names[part_num] else ""
            ch = part_num + 1
            console.print(f"  [cyan]Part {part_num} ({tname}ch{ch})[/cyan]")
            for k, val in sorted(v.items()):
                console.print(f"    {k}: {val}")
        console.print()

    # Drum Setup
    if a.xg_drum_setup:
        console.print("[bold red]XG Drum Setup overrides[/bold red]")
        for setup_num in sorted(a.xg_drum_setup.keys()):
            console.print(f"  [red]Setup {setup_num + 1}[/red]")
            for note_num in sorted(a.xg_drum_setup[setup_num].keys()):
                params = a.xg_drum_setup[setup_num][note_num]
                ps = ", ".join(f"{k}={v}" for k, v in sorted(params.items()))
                console.print(f"    note {note_num:3d}: {ps}")
        console.print()

    # Report nothing if no XG data
    if not (a.xg_system or a.xg_effects or a.xg_voices or a.xg_drum_setup):
        console.print(
            "[yellow]No XG state captured in this file.[/yellow]\n"
            "[dim]This .syx contains only pattern bulk (Model 5F). "
            "For XG state, capture with capture_complete.py or merge a load-stream JSON.[/dim]"
        )


@app.command("voices")
def voices_cmd(
    file: Path = typer.Argument(..., help="Path to .syx/.bin captured with --all"),
) -> None:
    """Extract per-channel voice selection (Bank MSB/LSB + Program) from a
    mixed capture (SysEx + channel events) and resolve voice names.

    Expects a file saved by `capture_xg_stream.py --all`: plain SysEx captures
    don't carry Program Change, so nothing will be resolved.
    """
    import sys as _sys

    _sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from midi_tools.xg_param import parse_all_events
    from midi_tools.xg_voices import voice_name

    xg_msgs, chan_events = parse_all_events(file)
    console.print(
        f"[bold]{file}[/bold]: {len(xg_msgs)} XG / {len(chan_events)} channel events"
    )

    if not chan_events:
        console.print(
            "[yellow]No channel events — probably a SysEx-only capture. "
            "Re-run capture_xg_stream.py with --all.[/yellow]"
        )
        raise typer.Exit(0)

    # Track per-channel Bank MSB/LSB and last Program change.
    bank_msb = [0] * 16
    bank_lsb = [0] * 16
    program = [None] * 16
    timeline: list[tuple[int, int, int, int]] = []  # (ch, msb, lsb, prog)

    for ev in chan_events:
        k, ch = ev.kind, ev.channel
        if k == 0xB0 and len(ev.data) == 2:
            cc, val = ev.data[0], ev.data[1]
            if cc == 0x00:
                bank_msb[ch] = val
            elif cc == 0x20:
                bank_lsb[ch] = val
        elif k == 0xC0 and len(ev.data) == 1:
            program[ch] = ev.data[0]
            timeline.append((ch, bank_msb[ch], bank_lsb[ch], program[ch]))

    console.print(f"\n[cyan]## Program Change events: {len(timeline)}[/cyan]")
    for ch, msb, lsb, prog in timeline[:40]:
        name = voice_name(msb, lsb, prog)
        console.print(
            f"  Ch{ch+1:02d}  Bank {msb:3d}/{lsb:3d}  Prog {prog:3d}  → [bold]{name}[/bold]"
        )
    if len(timeline) > 40:
        console.print(f"  [dim]... ({len(timeline) - 40} more)[/dim]")

    console.print("\n[cyan]## Final state per channel:[/cyan]")
    for ch in range(16):
        if program[ch] is not None:
            name = voice_name(bank_msb[ch], bank_lsb[ch], program[ch])
            console.print(
                f"  Ch{ch+1:02d}  Bank {bank_msb[ch]:3d}/{bank_lsb[ch]:3d}  "
                f"Prog {program[ch]:3d}  → [bold]{name}[/bold]"
            )
