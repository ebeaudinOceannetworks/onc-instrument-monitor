"""Shared base for complex data types (hydrophone, seismometer, ADCP).

Complex instruments are monitored PER INSTRUMENT using archived-file data
availability. A concrete plugin only needs to set ``data_type`` and provide
config (categories + expected extensions) in ``config/data_types.yaml``.
"""

from __future__ import annotations

from typing import Any

from core.availability import compute_availability
from core.onc_client import ONCClient
from core.parallel import thread_map
from core.plugin_base import DATA_CLASS_COMPLEX, DataTypePlugin
from core.regions import get_region_resolver
from core.registry import load_yaml


class ComplexInstrumentPlugin(DataTypePlugin):
    data_class = DATA_CLASS_COMPLEX

    def __init__(self) -> None:
        self._client = ONCClient()
        cfg = load_yaml("data_types.yaml").get("data_types", {}).get(self.data_type, {})
        self.categories: list[str] = cfg.get("categories") or []
        self.extensions: list[str] = cfg.get("archive_extensions") or []
        self.expected_files_per_day = int(cfg.get("expected_files_per_day", 288))
        self.availability_days = int(cfg.get("availability_days", 7))
        self._devices: list[dict[str, Any]] | None = None

    def refresh(self) -> None:
        self._devices = None

    def list_devices(self) -> list[dict[str, Any]]:
        if self._devices is not None:
            return self._devices
        if not self._client.available:
            self._devices = []
            return self._devices

        discovered: list[dict[str, Any]] = []
        seen: set[str] = set()
        for category in self.categories:
            for dev in self._client.discover_active_devices(category):
                code = dev.get("deviceCode")
                if not code or code in seen:
                    continue
                seen.add(code)
                discovered.append(dev)

        # Availability lookups are network-bound, so build devices concurrently.
        self._devices = thread_map(self._build_device, discovered)
        return self._devices

    def _build_device(self, dev: dict[str, Any]) -> dict[str, Any]:
        location_code = dev.get("locationCode") or ""
        site_code = location_code.split(".")[0] if location_code else "UNKNOWN"
        device_id = dev.get("deviceId")
        region = get_region_resolver().resolve(location_code)

        availability = compute_availability(
            self._client,
            dev["deviceCode"],
            self.extensions,
            days=self.availability_days,
            expected_files_per_day=self.expected_files_per_day,
        )

        return {
            "deviceKey": str(device_id or dev["deviceCode"]),
            "dataType": self.data_type,
            "dataClass": DATA_CLASS_COMPLEX,
            "deviceCategoryCode": dev.get("deviceCategoryCode", ""),
            "deviceCode": dev["deviceCode"],
            "deviceID": device_id,
            "deviceName": dev.get("deviceName") or dev["deviceCode"],
            "siteCode": site_code,
            "siteName": dev.get("locationName") or site_code,
            "locationName": dev.get("locationName") or location_code,
            "network": region,
            "region": region,
            "locationCode": location_code,
            "depth": dev.get("depth"),
            "latitude": dev.get("latitude"),
            "longitude": dev.get("longitude"),
            "deviceDetailsUrl": self._client.oceans3_device_url(device_id) if device_id else "",
            "dataSearchUrl": self._client.oceans3_data_search_url(dev["deviceCode"]),
            "status": availability["status"],
            "availability": availability,
            "jira_tickets": [],
            "open_annotations": [],
            "plot_series": {},
            "jb_info": [],
        }
