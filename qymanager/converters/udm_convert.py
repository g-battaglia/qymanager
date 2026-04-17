"""UDM-aware cross-device converter.

Orchestrates the chain

    load_device → apply_policy → save_device

so that CLI `qymanager convert --to qy70|qy700 --keep ... --drop ...`
has one place to call. This is the "modern" converter; the legacy
`qy70_to_qy700.py` / `qy700_to_qy70.py` Pipeline B scripts remain
available for capture-based dense-pattern work.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from qymanager.converters.lossy_policy import (
    LossyPolicy,
    WarningRecord,
    apply_policy,
)
from qymanager.formats.io import load_device, save_device
from qymanager.model import Device, DeviceModel


def convert_file(
    input_path: Path,
    output_path: Path,
    *,
    target_model: DeviceModel,
    policy: Optional[LossyPolicy] = None,
) -> tuple[Device, list[WarningRecord]]:
    """Load a UDM Device, apply a lossy policy, save to `output_path`.

    Returns the converted Device and the list of lossy warnings produced.
    """
    device = load_device(input_path)
    policy = policy or LossyPolicy()
    converted, warnings = apply_policy(device, policy, target_model=target_model)
    save_device(converted, output_path)
    return converted, warnings
