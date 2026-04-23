from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from uuid import uuid4

from qymanager.model.device import Device


@dataclass
class DeviceSession:
    _devices: dict[str, Device] = field(default_factory=dict)
    _filenames: dict[str, str] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock)

    def create(self, device: Device, filename: str | None = None) -> str:
        did = str(uuid4())
        with self._lock:
            self._devices[did] = device
            if filename:
                self._filenames[did] = filename
        return did

    def get(self, did: str) -> Device | None:
        with self._lock:
            return self._devices.get(did)

    def get_filename(self, did: str) -> str | None:
        with self._lock:
            return self._filenames.get(did)

    def update(self, did: str, device: Device) -> None:
        with self._lock:
            self._devices[did] = device

    def delete(self, did: str) -> bool:
        with self._lock:
            self._filenames.pop(did, None)
            return self._devices.pop(did, None) is not None

    def list_ids(self) -> list[str]:
        with self._lock:
            return list(self._devices.keys())


_session = DeviceSession()


def get_session() -> DeviceSession:
    return _session
