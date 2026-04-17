"""Lossy-conversion policy: keep/drop fields during QY70↔QY700 conversion.

A `LossyPolicy` is a declarative description of which UDM fields
survive a cross-device conversion. Fields are specified either by
*exact path* (e.g. `"effects.variation"`) or by *prefix* (anything
starting with `"multi_part[17]"`).

Three inputs determine the policy:

- `keep`: names to preserve (beats drop on conflict; use "all" to
  keep everything by default).
- `drop`: names to discard (explicitly set to default / stripped).
- `device_constraint`: pre-built policy for a target device (strips
  parts/sections/variation that don't exist on the target).

Every applied policy emits a `WarningRecord` describing what was
stripped, so callers can write a `.warnings.json` and decide whether
the loss is acceptable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from qymanager.model import Device, DeviceModel


# Named groups — expand to concrete path prefixes
_NAMED_GROUPS: dict[str, list[str]] = {
    "all": [""],  # matches everything
    "variation": ["effects.variation"],
    "fill-cc-dd": ["sections.Fill_CC", "sections.Fill_DD"],
    "parts-17-32": [f"multi_part[{i}]" for i in range(16, 32)],
    "song-tracks-5-35": [f"songs[*].tracks[{i}]" for i in range(4, 35)],
    "drum-kit-2": ["drum_setup[1]"],
    "groove-templates": ["groove_templates"],
    "phrases-user": ["phrases_user"],
    "utility": ["utility"],
    "fingered-zone": ["fingered_zone"],
}


@dataclass
class WarningRecord:
    """A single lossy operation that occurred during conversion."""

    path: str
    reason: str
    old_value: Optional[str] = None

    def to_json(self) -> dict:
        return {
            "path": self.path,
            "reason": self.reason,
            "old_value": self.old_value,
        }


@dataclass
class LossyPolicy:
    """Lossy policy — default warns about every stripped field.

    - `keep=["variation"]`       — user accepts losing that field silently
    - `keep=["all"]`             — accept every loss silently
    - `drop=["fill-cc-dd"]`      — force a warning (overrides keep)
    """

    keep: list[str] = field(default_factory=list)
    drop: list[str] = field(default_factory=list)

    def _expand(self, names: list[str]) -> list[str]:
        out: list[str] = []
        for n in names:
            out.extend(_NAMED_GROUPS.get(n, [n]))
        return out

    def _is_kept(self, path: str) -> bool:
        keep = self._expand(self.keep)
        drop = self._expand(self.drop)
        # drop wins on conflict
        if any(path.startswith(d) and d != "" for d in drop):
            return False
        # "all" is encoded as "" — matches every path
        return any(d == "" or path.startswith(d) for d in keep)


def apply_policy(
    device: Device,
    policy: LossyPolicy,
    *,
    target_model: Optional[DeviceModel] = None,
) -> tuple[Device, list[WarningRecord]]:
    """Return a new Device after applying the lossy policy.

    The input Device is not mutated.
    """
    from copy import deepcopy

    out = deepcopy(device)
    warnings: list[WarningRecord] = []

    if target_model is not None:
        out.model = target_model

    def _warn(path: str, reason: str, old: Optional[str] = None) -> None:
        if policy._is_kept(path):
            return  # user accepted the loss silently
        warnings.append(WarningRecord(path=path, reason=reason, old_value=old))

    # Variation: QY70 has no Variation block at the device level
    if target_model == DeviceModel.QY70 and out.effects.variation is not None:
        _warn("effects.variation", "QY70 has no Variation effect")
        out.effects.variation = None

    # Multi Part 17..32: QY70 only has 16
    if target_model == DeviceModel.QY70 and len(out.multi_part) > 16:
        for idx in range(16, len(out.multi_part)):
            _warn(f"multi_part[{idx}]", "QY70 limit of 16 parts")
        out.multi_part = out.multi_part[:16]

    # Drum Setup 2: QY70 has only one kit
    if target_model == DeviceModel.QY70 and len(out.drum_setup) > 1:
        _warn("drum_setup[1]", "QY70 has a single drum setup")
        out.drum_setup = out.drum_setup[:1]

    # Fill CC/DD sections only exist on QY700
    if target_model == DeviceModel.QY70:
        from qymanager.model import SectionName

        drop_names = {SectionName.FILL_CC, SectionName.FILL_DD}
        for pattern in out.patterns:
            present = [name for name in pattern.sections if name in drop_names]
            for name in present:
                _warn(
                    f"sections.{name.value}",
                    "QY70 has only FILL_AA/FILL_BB",
                )
                del pattern.sections[name]

    # Song tracks 5..35 compressed to 4 for QY70
    if target_model == DeviceModel.QY70:
        for song in out.songs:
            if len(song.tracks) > 4:
                _warn(
                    f"songs[{song.index}].tracks[4:]",
                    "QY70 song supports 4 SEQ tracks",
                )
                song.tracks = song.tracks[:4]

    return out, warnings


def dump_warnings(warnings: list[WarningRecord]) -> list[dict]:
    """Serialize warning records to a JSON-friendly list of dicts."""
    return [w.to_json() for w in warnings]
