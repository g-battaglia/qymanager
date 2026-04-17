"""Tests for LossyPolicy + apply_policy (F9)."""

import pytest

from qymanager.converters.lossy_policy import (
    LossyPolicy,
    WarningRecord,
    apply_policy,
    dump_warnings,
)
from qymanager.model import (
    Device,
    DeviceModel,
    DrumSetup,
    MultiPart,
    Pattern,
    Section,
    SectionName,
    VariationBlock,
    Voice,
)


def _qy700_like() -> Device:
    pattern = Pattern()
    pattern.sections[SectionName.MAIN_A] = Section(name=SectionName.MAIN_A)
    pattern.sections[SectionName.FILL_CC] = Section(name=SectionName.FILL_CC)
    pattern.sections[SectionName.FILL_DD] = Section(name=SectionName.FILL_DD)
    device = Device(
        model=DeviceModel.QY700,
        patterns=[pattern],
        drum_setup=[DrumSetup(kit_index=0), DrumSetup(kit_index=1)],
    )
    device.multi_part = [
        MultiPart(part_index=i, rx_channel=i, voice=Voice()) for i in range(32)
    ]
    device.effects.variation = VariationBlock(type_code=10, return_level=50)
    return device


class TestTargetQY70:
    def test_variation_dropped_by_default(self):
        device = _qy700_like()
        out, warnings = apply_policy(
            device, LossyPolicy(), target_model=DeviceModel.QY70
        )
        assert out.effects.variation is None
        assert any(w.path == "effects.variation" for w in warnings)

    def test_variation_kept_silences_warning(self):
        device = _qy700_like()
        policy = LossyPolicy(keep=["variation"])
        out, warnings = apply_policy(device, policy, target_model=DeviceModel.QY70)
        # structural strip always happens (QY70 has no Variation block)
        assert out.effects.variation is None
        # but the warning is suppressed because the user accepted the loss
        assert not any(w.path == "effects.variation" for w in warnings)

    def test_parts_17_32_removed(self):
        device = _qy700_like()
        out, warnings = apply_policy(
            device, LossyPolicy(), target_model=DeviceModel.QY70
        )
        assert len(out.multi_part) == 16
        assert any(w.path.startswith("multi_part[16]") for w in warnings)

    def test_drum_kit_2_dropped(self):
        device = _qy700_like()
        out, warnings = apply_policy(
            device, LossyPolicy(), target_model=DeviceModel.QY70
        )
        assert len(out.drum_setup) == 1
        assert any(w.path == "drum_setup[1]" for w in warnings)

    def test_fill_cc_dd_sections_removed(self):
        device = _qy700_like()
        out, warnings = apply_policy(
            device, LossyPolicy(), target_model=DeviceModel.QY70
        )
        sections = out.patterns[0].sections
        assert SectionName.MAIN_A in sections
        assert SectionName.FILL_CC not in sections
        assert SectionName.FILL_DD not in sections
        assert any(w.path.endswith("Fill_CC") for w in warnings)


class TestKeepDropInteraction:
    def test_drop_overrides_keep(self):
        device = _qy700_like()
        policy = LossyPolicy(keep=["all"], drop=["fill-cc-dd"])
        out, warnings = apply_policy(device, policy, target_model=DeviceModel.QY70)
        assert SectionName.FILL_CC not in out.patterns[0].sections
        assert any(w.path.endswith("Fill_CC") for w in warnings)


class TestPurePassthrough:
    def test_same_model_no_warnings(self):
        device = _qy700_like()
        out, warnings = apply_policy(
            device, LossyPolicy(), target_model=DeviceModel.QY700
        )
        assert out.effects.variation is not None
        assert len(out.multi_part) == 32
        assert warnings == []


class TestDumpWarnings:
    def test_json_serialization(self):
        records = [
            WarningRecord(path="x", reason="because", old_value="5"),
        ]
        dumped = dump_warnings(records)
        assert dumped == [{"path": "x", "reason": "because", "old_value": "5"}]
