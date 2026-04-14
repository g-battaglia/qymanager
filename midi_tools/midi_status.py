#!/usr/bin/env python3
"""
MIDI Status — Diagnostica completa della connessione MIDI.

Verifica porte, connettività bidirezionale, identità dispositivi,
e capacità dump request per QY70/QY700.

Usage:
    python3 midi_tools/midi_status.py
    python3 midi_tools/midi_status.py --port "Steinberg UR22C Porta 1"
    python3 midi_tools/midi_status.py --listen 30   # ascolto passivo 30 sec
"""

import sys
import time
import argparse

try:
    import mido
except ImportError:
    print("ERRORE: mido non installato.")
    print("  pip install mido python-rtmidi")
    sys.exit(1)


def header(text: str):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


def check_ports():
    """Elenca tutte le porte MIDI disponibili."""
    header("1. PORTE MIDI")

    inputs = mido.get_input_names()
    outputs = mido.get_output_names()

    if not inputs and not outputs:
        print("  NESSUNA PORTA TROVATA")
        print("  - Controlla che l'interfaccia MIDI-USB sia collegata")
        print("  - Prova a scollegare e ricollegare il cavo USB")
        return [], []

    print(f"  INPUT  ({len(inputs)}):")
    for p in inputs:
        print(f"    -> {p}")

    print(f"  OUTPUT ({len(outputs)}):")
    for p in outputs:
        print(f"    <- {p}")

    return inputs, outputs


def listen_passive(ports: list, seconds: int = 5):
    """Ascolto passivo su tutte le porte."""
    header(f"2. ASCOLTO PASSIVO ({seconds}s)")
    print("  Premi tasti o muovi controlli sulle macchine collegate...")
    print()

    inputs = []
    for p in ports:
        try:
            inputs.append((p, mido.open_input(p)))
        except Exception as e:
            print(f"  ERRORE apertura {p}: {e}")

    if not inputs:
        return {}

    results = {p: [] for p in ports}
    start = time.time()
    while time.time() - start < seconds:
        for name, inp in inputs:
            msg = inp.poll()
            if msg:
                results[name].append(msg)
                if msg.type == "sysex":
                    h = " ".join(f"{b:02X}" for b in msg.data[:16])
                    print(f"  [{name}] SysEx: F0 {h}... ({len(msg.data)+2}B)")
                elif msg.type not in ("clock", "active_sensing"):
                    print(f"  [{name}] {msg}")
                elif len(results[name]) <= 2:
                    print(f"  [{name}] {msg.type}")
        time.sleep(0.001)

    for _, inp in inputs:
        inp.close()

    for name in ports:
        msgs = results[name]
        types = set(m.type for m in msgs)
        if msgs:
            print(f"  {name}: {len(msgs)} messaggi, tipi: {types}")
        else:
            print(f"  {name}: NESSUN MESSAGGIO")

    return results


def test_output(ports: list):
    """Invia note MIDI per verificare l'output."""
    header("3. TEST OUTPUT (invio Note C4)")
    print("  Se senti suonare una nota, l'output MIDI funziona.")
    print()

    for p in ports:
        try:
            with mido.open_output(p) as out:
                out.send(mido.Message("note_on", note=60, velocity=100, channel=0))
                time.sleep(0.8)
                out.send(mido.Message("note_off", note=60, velocity=0, channel=0))
                print(f"  {p}: nota inviata")
                time.sleep(0.3)
        except Exception as e:
            print(f"  {p}: ERRORE {e}")


YAMAHA_DEVICES = {
    # Family 0x4100 = Yamaha XG/Sequencer family
    # Member codes from official Yamaha Data Lists
    (0x4100, 0x3404): "QY100",
    (0x4100, 0x5502): "QY70",
    # Add more as discovered
}


def identify_yamaha_device(family: int, member: int) -> str:
    """Lookup Yamaha device from Identity Reply codes."""
    key = (family, member)
    if key in YAMAHA_DEVICES:
        return YAMAHA_DEVICES[key]
    if family == 0x4100:
        return "Yamaha XG (sconosciuto)"
    return "Sconosciuto"


def test_identity(in_ports: list, out_ports: list):
    """Invia Identity Request e ascolta risposte."""
    header("4. IDENTITY REQUEST")
    print("  Invio Universal Identity Request (F0 7E 7F 06 01 F7)...")
    print()

    found_devices = []

    for out_name in out_ports:
        for in_name in in_ports:
            try:
                with mido.open_input(in_name) as inp:
                    with mido.open_output(out_name) as out:
                        # Flush
                        for _ in inp.iter_pending():
                            pass

                        out.send(mido.Message("sysex", data=[0x7E, 0x7F, 0x06, 0x01]))
                        time.sleep(2)

                        for resp in inp.iter_pending():
                            if resp.type == "sysex" and len(resp.data) >= 10:
                                d = resp.data
                                if d[0] == 0x7E and d[2] == 0x06 and d[3] == 0x02:
                                    mfr = d[4]
                                    family = (d[6] << 8) | d[5]
                                    member = (d[8] << 8) | d[7]
                                    ver = ".".join(str(d[i]) for i in range(9, min(13, len(d))))

                                    mfr_name = {0x43: "Yamaha"}.get(mfr, f"0x{mfr:02X}")
                                    device_name = identify_yamaha_device(family, member) if mfr == 0x43 else ""
                                    hex_full = " ".join(f"{b:02X}" for b in d)

                                    print(f"  RISPOSTA su OUT={out_name} IN={in_name}:")
                                    print(f"    Raw: F0 {hex_full} F7")
                                    print(f"    Manufacturer: {mfr_name}")
                                    print(f"    Family: 0x{family:04X}")
                                    print(f"    Member: 0x{member:04X}")
                                    if device_name:
                                        print(f"    Device: {device_name}")
                                    print(f"    Version: {ver}")

                                    found_devices.append({
                                        "out": out_name,
                                        "in": in_name,
                                        "mfr": mfr_name,
                                        "family": family,
                                        "member": member,
                                        "device": device_name,
                                    })
            except Exception as e:
                pass  # Skip port combos that fail

    if not found_devices:
        print("  NESSUN DISPOSITIVO HA RISPOSTO")
        print("  Possibili cause:")
        print("    - Cavi MIDI non collegati o invertiti")
        print("    - Macchina spenta o non in modo MIDI")
        print("    - MIDI OUT macchina -> MIDI IN interfaccia (e viceversa)")

    return found_devices


def test_qy70_dump_request(in_ports: list, out_ports: list):
    """Prova il Yamaha Dump Request per QY70."""
    header("5. QY70 DUMP REQUEST")
    print("  Invio Yamaha Dump Request (F0 43 20 5F 02 7E 7F F7)...")
    print()

    for out_name in out_ports:
        for in_name in in_ports:
            try:
                with mido.open_input(in_name) as inp:
                    with mido.open_output(out_name) as out:
                        for _ in inp.iter_pending():
                            pass

                        # Try device numbers 0 and 1
                        for dev in (0, 1):
                            req = [0x43, 0x20 | dev, 0x5F, 0x02, 0x7E, 0x7F]
                            out.send(mido.Message("sysex", data=req))
                            label = f"OUT={out_name} IN={in_name} dev={dev}"

                            time.sleep(2)

                            got = False
                            for resp in inp.iter_pending():
                                if resp.type == "sysex":
                                    h = " ".join(f"{b:02X}" for b in resp.data[:16])
                                    print(f"  RISPOSTA ({label}):")
                                    print(f"    F0 {h}... ({len(resp.data)+2}B)")
                                    got = True

                            if not got:
                                print(f"  Nessuna risposta ({label})")
            except Exception:
                pass

    print()
    print("  Se nessuna risposta: il bulk dump va triggerato manualmente")
    print("  sul QY70: UTILITY -> MIDI -> Bulk Dump")


def print_summary(ports_ok: bool, passive_ok: bool, identity_ok: bool, dump_ok: bool):
    """Riepilogo finale."""
    header("RIEPILOGO")

    def status(ok):
        return "OK" if ok else "FAIL"

    print(f"  Porte MIDI visibili:    {status(ports_ok)}")
    print(f"  Ricezione dati:         {status(passive_ok)}")
    print(f"  Identity Response:      {status(identity_ok)}")
    print(f"  QY70 Dump Request:      {status(dump_ok)}")
    print()

    if not ports_ok:
        print("  -> Collega l'interfaccia MIDI-USB al computer")
    elif not passive_ok and not identity_ok:
        print("  -> Controlla i cavi MIDI:")
        print("     MIDI OUT macchina  -->  MIDI IN interfaccia")
        print("     MIDI OUT interfaccia  -->  MIDI IN macchina")
    elif passive_ok and not identity_ok:
        print("  -> Il dispositivo manda dati ma non risponde a Identity")
        print("     (normale per alcuni synth Yamaha)")
    elif identity_ok and not dump_ok:
        print("  -> Dispositivo connesso ma non supporta Dump Request remoto")
        print("     Usa il menu manuale: UTILITY -> MIDI -> Bulk Dump")

    print()


def main():
    parser = argparse.ArgumentParser(description="MIDI Status — diagnostica connessione")
    parser.add_argument("--port", help="Testa solo questa porta")
    parser.add_argument("--listen", type=int, default=5, help="Secondi di ascolto passivo (default: 5)")
    parser.add_argument("--skip-output", action="store_true", help="Salta test invio note")
    parser.add_argument("--skip-dump", action="store_true", help="Salta test dump request")
    args = parser.parse_args()

    print()
    print("  MIDI STATUS — Diagnostica Connessione QY70/QY700")
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. Check ports
    inputs, outputs = check_ports()
    if not inputs:
        print_summary(False, False, False, False)
        return 1

    if args.port:
        inputs = [p for p in inputs if args.port.lower() in p.lower()]
        outputs = [p for p in outputs if args.port.lower() in p.lower()]
        if not inputs:
            print(f"\n  Porta '{args.port}' non trovata.")
            return 1

    # 2. Passive listen
    passive_results = listen_passive(inputs, args.listen)
    passive_ok = any(len(msgs) > 0 for msgs in passive_results.values())

    # 3. Output test
    if not args.skip_output:
        test_output(outputs)

    # 4. Identity
    devices = test_identity(inputs, outputs)
    identity_ok = len(devices) > 0

    # 5. Dump request
    dump_ok = False
    if not args.skip_dump:
        test_qy70_dump_request(inputs, outputs)
        # dump_ok stays False unless we add response detection

    # Summary
    print_summary(len(inputs) > 0, passive_ok, identity_ok, dump_ok)
    return 0


if __name__ == "__main__":
    sys.exit(main())
