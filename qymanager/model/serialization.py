"""UDM validation and JSON serialization."""

import json
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any

from qymanager.model.device import Device


def _convert_value(val: Any) -> Any:
    if isinstance(val, Enum):
        return val.value
    if isinstance(val, bytes):
        return val.hex()
    if isinstance(val, list):
        return [_convert_value(item) for item in val]
    if isinstance(val, dict):
        return {
            (k.value if isinstance(k, Enum) else str(k)): _convert_value(v)
            for k, v in val.items()
        }
    if is_dataclass(val) and not isinstance(val, type):
        return udm_to_dict(val)
    return val


def udm_to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [_convert_value(item) for item in obj]
    if isinstance(obj, dict):
        return {
            (k.value if isinstance(k, Enum) else str(k)): _convert_value(v)
            for k, v in obj.items()
        }
    if is_dataclass(obj) and not isinstance(obj, type):
        result: dict[str, Any] = {}
        for f in fields(obj):
            if f.name.startswith("_"):
                continue
            val = getattr(obj, f.name)
            result[f.name] = _convert_value(val)
        return result
    return _convert_value(obj)


def device_to_json(device: Device, indent: int = 2) -> str:
    return json.dumps(udm_to_dict(device), indent=indent, ensure_ascii=False)


def validate_device(device: Device) -> list[str]:
    return device.validate()
