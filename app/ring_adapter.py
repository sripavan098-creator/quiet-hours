"""Adapter from Ring webhook payloads to Quiet Hours' internal event shape.

Ring webhook shape, per the Ring developer docs (notifications page):
    {"meta": {"account_id": ..., "time": "<ISO 8601 send time>"},
     "data": {"id": ..., "type": "motion_detected",
              "attributes": {"source": "<device id>", "timestamp": ..., "sub_type": ...},
              "relationships": {"devices": {"links": {"self": "/v1/devices/<id>"}}}}}

Device ids are mapped to rooms through configuration (RING_DEVICE_ZONES), so
the same code serves the simulator and a real account. Unknown devices and
unknown event types are dropped, not guessed.
"""
from __future__ import annotations

import json
import os
from datetime import datetime

# Ring event type -> Quiet Hours kind. Only types we can interpret are listed.
KIND_BY_RING_TYPE = {
    "motion_detected": "motion",
    "button_press": "ding",
}


class PayloadError(ValueError):
    """The payload is malformed. Ring should not retry it (HTTP 400)."""


def load_zone_map(raw: str | None = None) -> dict[str, str]:
    """Parse RING_DEVICE_ZONES, a JSON object of {ring_device_id: zone_id}."""
    raw = raw if raw is not None else os.environ.get("RING_DEVICE_ZONES", "{}")
    try:
        mapping = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PayloadError(f"RING_DEVICE_ZONES is not valid JSON: {exc}") from exc
    if not isinstance(mapping, dict):
        raise PayloadError("RING_DEVICE_ZONES must be a JSON object")
    return {str(k): str(v) for k, v in mapping.items()}


def normalise(payload, zone_map: dict[str, str], device_names: dict[str, str] | None = None) -> list[dict]:
    """Turn one Ring webhook payload into internal events.

    Returns a list (zero or one item for a single webhook). Raises PayloadError
    for structurally invalid payloads. Events from unmapped devices or unknown
    event types are skipped.
    """
    if not isinstance(payload, dict):
        raise PayloadError("payload must be a JSON object")
    meta = payload.get("meta")
    data = payload.get("data")
    if not isinstance(meta, dict) or not isinstance(data, dict):
        raise PayloadError("payload needs 'meta' and 'data' objects")

    attrs = data.get("attributes") or {}
    device_id = attrs.get("source")
    event_type = data.get("type")
    event_id = data.get("id")
    sent = meta.get("time")
    if not (device_id and event_type and event_id and sent):
        raise PayloadError("data.id, data.type, data.attributes.source and meta.time are required")
    try:
        when = datetime.fromisoformat(str(sent).replace("Z", "+00:00"))
    except ValueError as exc:
        raise PayloadError(f"meta.time is not ISO 8601: {sent}") from exc

    is_sim = str(device_id).startswith("sim.")
    # Real devices: only documented Ring types. Simulated devices may also
    # send "contact_open" (medicine box): Ring's documented webhook list has
    # no contact-sensor type, so that type is not accepted from real devices.
    kind = KIND_BY_RING_TYPE.get(event_type) or (event_type if is_sim else None)
    zone = zone_map.get(device_id)
    if kind is None or zone is None:
        return []

    return [{
        "event_id": str(event_id),
        "device_id": zone,
        "device_name": (device_names or {}).get(zone, zone),
        "ring_device_id": device_id,
        "kind": kind,
        "ring_type": event_type,
        "created_at": when.isoformat(),
        "source": "simulator" if is_sim else "ring",
    }]


def to_ring_payload(event: dict, account_id: str = "ava1.ring.account.SIMULATED") -> dict:
    """Inverse of normalise: build a Ring-shaped webhook body from an internal event.

    Used by the simulator so demo traffic takes exactly the path real webhooks do.
    """
    reverse = {v: k for k, v in KIND_BY_RING_TYPE.items()}
    ring_type = reverse.get(event["kind"], event["kind"])
    device_id = event.get("ring_device_id") or f"sim.{event['device_id']}"
    return {
        "meta": {"account_id": account_id, "time": event["created_at"]},
        "data": {
            "id": event["event_id"],
            "type": ring_type,
            "attributes": {"source": device_id, "sub_type": "human" if ring_type == "motion_detected" else None},
            "relationships": {"devices": {"links": {"self": f"/v1/devices/{device_id}"}}},
        },
    }
