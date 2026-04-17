# Contributing to QY Manager

Thanks for your interest in contributing. This project is private during active
reverse-engineering and will open up as the **MS4** milestone lands (see `STATUS.md`).
The sections below describe how to work on the code today; once we go public the same
flow applies with `git push` targets replaced.

## Before you start

- Read `CLAUDE.md` for the project conventions (wiki maintenance, Italian user
  communication, Yamaha QY70/QY700 protocol quirks).
- Skim `STATUS.md` for the current state — it's the north-star summary.
- Browse `wiki/index.md` for the compiled knowledge base. **Every discovery must land
  in the wiki** (that's a hard rule from `CLAUDE.md`).

## Environment

This project uses **[uv](https://docs.astral.sh/uv/)** (Astral) as the package manager.
On external filesystems that do not support hardlinks (e.g. exFAT/NTFS mounted on macOS),
set `UV_LINK_MODE=copy` before any `uv` invocation.

```bash
export UV_LINK_MODE=copy

uv sync --all-extras --group dev   # runtime + MIDI extras + dev tools
uv run pytest                       # full test suite (428+ tests)
uv run ruff check .                 # lint
uv run black --check .              # format
```

## Layout cheatsheet

```
qymanager/
├── model/          # Unified Data Model (UDM) — Device, Pattern, MultiPart, ...
├── formats/        # Parsers + emitters (q7p, qy70 sparse, xg_bulk, smf)
├── editor/         # schema, address_map, ops, realtime
├── converters/     # qy70 ↔ qy700 with lossy policy
└── analysis/       # Q7P/SysEx analyzers (rich CLI output)
cli/
└── commands/       # typer-based subcommands
tests/
├── property/       # Hypothesis-based invariants
├── hardware/       # device-in-the-loop (skipped unless QY_HARDWARE=1)
└── ...             # unit + integration
wiki/               # compiled knowledge base (source of truth for RE findings)
docs/               # raw format documentation
```

## Coding rules

1. **UDM first** — new parsers/emitters decode to / encode from
   `qymanager.model.Device`, never to a dict. Editor logic lives on top of UDM.
2. **No mocks at the hardware boundary** — integration tests that talk to the
   device live in `tests/hardware/` under the `hardware` marker. The conftest
   auto-skips the module unless `QY_HARDWARE=1` is set.
3. **Validate at system boundaries** — `qymanager.editor.schema.validate()` is the
   only place range/enum checks happen. Internal code trusts the UDM.
4. **Frozen `Voice`** — the `Voice` dataclass is `frozen=True`. Update it via
   `dataclasses.replace(voice, program=...)`, never `voice.program = ...`.
5. **No silent SysEx drops** — for realtime MIDI I/O, use `python-rtmidi`
   directly. `mido` drops SysEx on macOS (see `memory/feedback_mido_sysex_bug.md`).
6. **Write tests before declaring done** — unit + property for anything
   non-trivial, hardware markers for anything that only works on the device.

## Pull requests

1. Create a topic branch off `main` (e.g., `feat/drum-alt-group-encoder`).
2. Keep the commit history meaningful: one logical change per commit.
3. Update `STATUS.md`, `wiki/log.md`, and the relevant wiki pages **in the same PR**.
4. Run `uv run pytest` locally and make sure all 428+ tests pass.
5. If you touch any of the format parsers, add a roundtrip test in
   `tests/property/` or `tests/test_<format>_udm.py`.

## Reverse-engineering workflow

- Capture with the QY70 secondary unit (`QY70 #2`) if the experiment is risky.
- Load hypothesis byte maps via `safe_q7p_tester.py` (when it lands).
- Record the hypothesis + confidence in `wiki/open-questions.md` before running
  hardware experiments.
- After a finding: update `wiki/<topic>.md` with the confirmed mapping **and** the
  confidence level (High/Medium/Low), then add a dated entry to `wiki/log.md`.

## Hardware safety

See `wiki/bricking.md`. In short:

- Do **not** write untested offsets to the primary QY700 — use the secondary.
- Keep `TXX.Q7P` + `data/q7p/DECAY.Q7P` as recovery fixtures.
- Always have a known-good Q7P ready to restore if the device starts behaving oddly.

## License

By contributing, you agree that your contributions will be released under the
project's MIT license (see `LICENSE` once published).
