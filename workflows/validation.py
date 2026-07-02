"""Validation report generator.

Simple, ONW-ready text generator. The user enters a reference device ID (e.g.
the MTC integration-lab reference instrument); this pulls the device metadata
and produces a validation starting-point summary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.onc_client import ONCClient


@dataclass
class ValidationRequest:
    reference_device_id: str


def run_validation(request: ValidationRequest) -> dict[str, Any]:
    ref = (request.reference_device_id or "").strip()
    if not ref:
        return {"status": "error", "message": "Reference device ID is required."}

    client = ONCClient()
    # Accept either a numeric device ID or a device code.
    device = client.get_device(device_id=ref) or client.get_device(device_code=ref)
    if not device:
        return {
            "status": "error",
            "message": f"No device found for reference '{ref}'.",
        }

    device_code = device.get("deviceCode") or ""
    device_name = device.get("deviceName") or device_code
    device_id = device.get("deviceId") or ref

    report_text = _render_validation_text(device_name, device_code, device_id, device)

    return {
        "status": "ok",
        "reference": {"deviceCode": device_code, "deviceName": device_name, "deviceId": device_id},
        "metadata": device,
        "report_text": report_text,
    }


def _render_validation_text(device_name, device_code, device_id, device) -> str:
    return "\n".join(
        [
            f"VALIDATION SUMMARY — reference {device_name}",
            "=" * 60,
            f"Reference device code : {device_code}",
            f"Reference device ID   : {device_id}",
            f"Device type           : {device.get('deviceCategoryCode') or device.get('deviceType') or 'N/A'}",
            "",
            "Steps:",
            "  [ ] Confirm reference device is the MTC integration-lab standard",
            "  [ ] Pull reference scalar data for the validation window",
            "  [ ] Plot device-under-test vs reference with error bars",
            "  [ ] Record offsets / drift vs reference",
            "  [ ] Attach validation results to the JIRA ticket",
            "",
            "Notes:",
            "  - ",
        ]
    )
