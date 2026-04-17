"""UDM editor: offline (file-based) and realtime (XG SysEx) editing.

The editor operates on the Unified Data Model (`qymanager.model.Device`).
Offline edits produce a new Device that can be emitted to any supported
format; realtime edits translate the same UDM path/value pair into an
XG Parameter Change SysEx message sent live to the hardware.

Modules:

- `address_map`: path (e.g. "system.master_volume") → XG (AH, AM, AL)
- `schema`: per-field range/enum validation + value encoding/decoding
- `ops`: get/set by path (applied to a Device in-place)
"""
