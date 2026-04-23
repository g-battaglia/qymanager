"""CLI commands for QY70 dense-factory encoder/decoder."""

import json
from collections import defaultdict
from pathlib import Path

import click

from qymanager.formats.qy70.encoder_dense import (
    DenseEncoder, decode_event, encode_event, DenseEvent,
)
from qymanager.formats.qy70.sysex_parser import SysExParser


@click.group(name="qy70-dense")
def qy70_dense():
    """QY70 dense-factory pattern encoder/decoder commands."""
    pass


@qy70_dense.command("decode")
@click.argument("syx_file", type=click.Path(exists=True))
@click.option("--track", type=int, default=None, help="Track index 0-7 (default: all)")
@click.option("--section", type=int, default=0, help="Section (default 0)")
@click.option("--output", "-o", type=click.Path(), help="Save JSON output")
def decode_cmd(syx_file, track, section, output):
    """Decode SGT-style pattern bytes to events via R tables."""
    enc = DenseEncoder()
    enc.load_sgt_tables()

    parser = SysExParser()
    msgs = parser.parse_file(syx_file)
    tracks = defaultdict(bytes)
    for m in msgs:
        if not (m.address_high == 0x02 and
                (m.address_mid <= 0x1F or m.address_mid == 0x7E)
                and m.decoded_data):
            continue
        if m.address_low == 0x7F:
            continue
        sec = m.address_low // 8
        trk = m.address_low % 8
        if sec == section:
            tracks[trk] += m.decoded_data

    names = {0: "RHY1", 1: "RHY2", 2: "PAD", 3: "BASS",
             4: "CHD1", 5: "CHD2", 6: "PHR1", 7: "PHR2"}
    results = {}
    for trk in sorted(tracks.keys()):
        if track is not None and trk != track:
            continue
        name = names.get(trk, f"TRK{trk}")
        if name not in enc.R_tables:
            click.echo(f"  {name}: no R table (skipping)", err=True)
            continue
        events = enc.decode(tracks[trk], name)
        results[name] = [
            {"idx": i, "note": e.note, "velocity": e.velocity, "gate": e.gate}
            for i, e in enumerate(events)
        ]
        click.echo(f"  {name}: {len(events)} events decoded")

    if output:
        Path(output).write_text(json.dumps(results, indent=2))
        click.echo(f"Saved → {output}")


@qy70_dense.command("roundtrip")
@click.argument("syx_file", type=click.Path(exists=True))
def roundtrip_cmd(syx_file):
    """Verify encoder bit-exact roundtrip on all tracks."""
    enc = DenseEncoder()
    enc.load_sgt_tables()

    parser = SysExParser()
    msgs = parser.parse_file(syx_file)
    tracks = defaultdict(bytes)
    for m in msgs:
        if not (m.address_high == 0x02 and
                (m.address_mid <= 0x1F or m.address_mid == 0x7E)
                and m.decoded_data):
            continue
        if m.address_low <= 7:
            tracks[m.address_low] += m.decoded_data

    names = {0: "RHY1", 1: "RHY2", 2: "PAD", 3: "BASS",
             4: "CHD1", 5: "CHD2", 6: "PHR1", 7: "PHR2"}
    total_m = 0
    total_n = 0
    for trk in sorted(tracks.keys()):
        name = names.get(trk, f"TRK{trk}")
        if name not in enc.R_tables:
            continue
        result = enc.roundtrip_test(tracks[trk], name)
        click.echo(f"  {name}: {result['matches']}/{result['total']} "
                   f"({result['percent']}%)")
        total_m += result['matches']
        total_n += result['total']
    click.echo(f"\nTotal: {total_m}/{total_n}")


@qy70_dense.command("info")
def info_cmd():
    """Show loaded R tables info."""
    enc = DenseEncoder()
    enc.load_sgt_tables()
    click.echo("Loaded R tables:")
    for name, table in enc.R_tables.items():
        click.echo(f"  {name}: N={len(table)}  first8={table[:8]}")


if __name__ == "__main__":
    qy70_dense()
