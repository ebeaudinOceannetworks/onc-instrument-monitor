"""Unified Commissioning router with instrument-specific strategy handlers."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from core.onc_client import ONCClient

@dataclass
class CommissioningRequest:
    device_code: str
    location_code: str = ""
    deployment: str = ""      # Format: "begin|end|locationCode"
    review_phase: str = ""    # "quick" or "detailed"

def list_available_deployments(device_code: str, location_code: str = "") -> list[dict[str, Any]]:
    """Return the device's deployments (most recent first) for the dropdown picker."""
    client = ONCClient()
    deployments = client.list_deployments(
        device_code=device_code or None, location_code=location_code or None
    )
    simplified = []
    for dep in deployments:
        begin = dep.get("begin") or ""
        end = dep.get("end") or ""
        loc = dep.get("locationCode") or ""
        simplified.append({
            "value": f"{begin}|{end}|{loc}",
            "begin": begin,
            "end": end,
            "locationCode": loc,
            "depth": dep.get("depth"),
            "label": f"{loc} · {begin[:10] or '?'} → {end[:10] or 'active'}"
        })
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
    loc = loc or request.location_code or device.get("locationCode", "")

    device_name = device.get("deviceName") or request.device_code
    device_id = device.get("deviceId") or "?"
    category_code = device.get("deviceCategoryCode", "").upper()

    report_text = ""
    generated_plots = []

    # 🚀 STRATEGY ROUTING: Passes the review_phase selection parameter safely
    if category_code == "HYDROPHONE":
        from workflows.commissioning_hydrophone import generate_hydrophone_report
        report_text, generated_plots = generate_hydrophone_report(
            client=client,
            device_name=device_name,
            device_code=request.device_code,
            device_id=device_id,
            location_code=loc,
            begin=begin,
            end=end,
            review_phase=request.review_phase or "quick"
        )
    else:
        report_text = _render_generic_commissioning(device_name, request.device_code, device_id, loc, begin)

    return {
        "status": "ok",
        "device": {"deviceCode": request.device_code, "deviceName": device_name, "deviceId": device_id},
        "deployment": {"begin": begin, "end": end, "locationCode": loc},
        "report_text": report_text,
        "plots": generated_plots  
    }

def _render_generic_commissioning(device_name, device_code, device_id, location_code, begin) -> str:
    return f"GENERIC SERVICE COMMISSIONING SUMMARY — {device_name}\n============================================================\nDevice Code: {device_code}\nDevice ID: {device_id}\nLocation: {location_code}\n"