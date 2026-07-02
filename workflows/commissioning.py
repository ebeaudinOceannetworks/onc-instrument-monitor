"""Commissioning report generator.

Simple, ONW-ready text generator. The user enters a device code (+ optional
location); the UI lists that device's real deployments (via ONC) to pick from,
and this produces a commissioning checklist/summary for the selected deployment.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.onc_client import ONCClient


@dataclass
class CommissioningRequest:
    device_code: str
    location_code: str = ""
    # Selected deployment, encoded as "begin|end|locationCode" from the picker.
    deployment: str = ""


def list_available_deployments(device_code: str, location_code: str = "") -> list[dict[str, Any]]:
    """Return the device's deployments (most recent first) for the picker."""
    client = ONCClient()
    deployments = client.list_deployments(
        device_code=device_code or None, location_code=location_code or None
    )
    simplified = []
    for dep in deployments:
        begin = dep.get("begin") or ""
        end = dep.get("end") or ""
        loc = dep.get("locationCode") or ""
        simplified.append(
            {
                "value": f"{begin}|{end}|{loc}",
                "begin": begin,
                "end": end,
                "locationCode": loc,
                "depth": dep.get("depth"),
                "label": f"{loc} · {begin[:10] or '?'} → {end[:10] or 'active'}",
            }
        )
    simplified.sort(key=lambda d: d["begin"], reverse=True)
    return simplified


def run_commissioning(request: CommissioningRequest) -> dict[str, Any]:
    if not request.device_code:
        return {"status": "error", "message": "Device code is required."}

    client = ONCClient()
    device = client.get_device(device_code=request.device_code)

    begin = end = loc = ""
    if request.deployment:
        parts = request.deployment.split("|")
        begin = parts[0] if len(parts) > 0 else ""
        end = parts[1] if len(parts) > 1 else ""
        loc = parts[2] if len(parts) > 2 else ""
    loc = loc or request.location_code

    device_name = device.get("deviceName") or request.device_code
    device_id = device.get("deviceId") or "?"

    report_text = _render_commissioning_text(
        device_name=device_name,
        device_code=request.device_code,
        device_id=device_id,
        location_code=loc,
        begin=begin,
        end=end,
    )

    return {
        "status": "ok",
        "device": {"deviceCode": request.device_code, "deviceName": device_name, "deviceId": device_id},
        "deployment": {"begin": begin, "end": end, "locationCode": loc},
        "report_text": report_text,
    }


def _render_commissioning_text(
    *, device_name, device_code, device_id, location_code, begin, end
) -> str:
    end_label = end[:10] if end else "active"
    return "\n".join(
        [
            f"COMMISSIONING SUMMARY — {device_name}",
            "=" * 60,
            f"Device code : {device_code}",
            f"Device ID   : {device_id}",
            f"Location    : {location_code or 'N/A'}",
            f"Deployment  : {begin[:10] or 'N/A'} -> {end_label}",
            "",
            "Checklist:",
            "  [ ] Device metadata verified in Oceans 3.0",
            "  [ ] Deployment dates and location confirmed",
            "  [ ] Data flowing for all expected sensors",
            "  [ ] Time sync / clock drift checked",
            "  [ ] Calibration sheet attached",
            "  [ ] Commissioning JIRA ticket updated",
            "",
            "Notes:",
            "  - ",
        ]
    )
