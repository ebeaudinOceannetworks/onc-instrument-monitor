"""Unified Commissioning router with instrument-specific strategy handlers."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from core.onc_client import ONCClient

@dataclass
class CommissioningRequest:
    device_id: str            # 💡 Renamed from device_code to accurately match user intent
    location_code: str = ""
    deployment: str = ""      # Format: "begin|end|locationCode"
    review_phase: str = ""    # "quick" or "detailed"
    checklist: dict = None

def list_available_deployments(device_id: str, location_code: str = "") -> dict[str, Any]:
    """Return the device's deployments (most recent first) for the dropdown picker."""
    client = ONCClient()
    resolved_device_code = device_id
    
    # If a numeric ID was provided, look up the true deviceCode from ONC first
    if device_id.isdigit():
        try:
            res = client._onc.getDevices({"deviceId": int(device_id)})
            if isinstance(res, list) and len(res) > 0:
                resolved_device_code = res[0].get("deviceCode", device_id)
            elif isinstance(res, dict) and "devices" in res:
                resolved_device_code = res["devices"][0].get("deviceCode", device_id)
        except Exception:
            pass

    # Pass the resolved alphanumeric deviceCode to list_deployments
    deployments = client.list_deployments(
        device_code=resolved_device_code or None, 
        location_code=location_code or None
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
    
    checklist_html = ""
    try:
        device = client.get_device(device_code=resolved_device_code)
        category_code = device.get("deviceCategoryCode", "").upper()
        
        # Grab the true numeric database ID from the device object
        resolved_device_id = device.get("deviceId", "")
        
        if category_code == "HYDROPHONE":
            from workflows.commissioning_hydrophone import get_hydrophone_checklist_ui
            checklist_html = get_hydrophone_checklist_ui(str(resolved_device_id))
            
    except Exception as e:
        print(f"❌ Error rendering dynamic checklist template asset: {e}")

    return {"deployments": simplified, "checklist_html": checklist_html}

def run_commissioning(request: CommissioningRequest) -> dict[str, Any]:
    if not request.device_id:
        return {"status": "error", "message": "Device ID is required."}

    client = ONCClient()
    resolved_device_code = request.device_id
    
    # Resolve the incoming ID parameter into the true alphanumeric deviceCode string
    if request.device_id.isdigit():
        try:
            res = client._onc.getDevices({"deviceId": int(request.device_id)})
            if isinstance(res, list) and len(res) > 0:
                resolved_device_code = res[0].get("deviceCode", request.device_id)
            elif isinstance(res, dict) and "devices" in res:
                resolved_device_code = res["devices"][0].get("deviceCode", request.device_id)
        except Exception:
            pass

    device = client.get_device(device_code=resolved_device_code)
    
    begin = end = loc = ""
    if request.deployment:
        parts = request.deployment.split("|")
        begin = parts[0] if len(parts) > 0 else ""
        end = parts[1] if len(parts) > 1 else ""
        loc = parts[2] if len(parts) > 2 else ""
    loc = loc or request.location_code or device.get("locationCode", "")

    device_name = device.get("deviceName") or resolved_device_code
    device_id = device.get("deviceId") or "?"
    category_code = device.get("deviceCategoryCode", "").upper()

    report_text = ""
    generated_plots = []

    if category_code == "HYDROPHONE":
        from workflows.commissioning_hydrophone import generate_hydrophone_report
        report_text, generated_plots = generate_hydrophone_report(
            client=client,
            device_name=device_name,
            device_code=resolved_device_code,
            device_id=device_id,
            location_code=loc,
            begin=begin,
            end=end,
            review_phase=request.review_phase or "quick",
            checklist=request.checklist or {}
        )
    else:
        report_text = _render_generic_commissioning(device_name, resolved_device_code, device_id, loc, begin)

    return {
        "status": "ok",
        "device": {"deviceCode": resolved_device_code, "deviceName": device_name, "deviceId": device_id},
        "deployment": {"begin": begin, "end": end, "locationCode": loc},
        "report_text": report_text,
        "plots": generated_plots  
    }