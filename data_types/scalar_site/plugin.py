"""Scalar site data_type — site-centric water property monitoring.

Discovers *all* active scalar instruments across the configured categories
(CTD, oxygen, fluorometer, pCO2, PAR, pH, ...) network-wide, then groups them
into sites by location. Each device carries its region (NEPTUNE / VENUS / West
Coast / ...) so the dashboard sidebar groups sites by region.

Per-device scalar data (clean + raw) is fetched concurrently and cached, so
generation stays fast even with many instruments.
"""

from __future__ import annotations

import os
from typing import Any

from core.db import get_jb_info_for_device
from core.onc_client import ONCClient
from core.parallel import thread_map
from core.plugin_base import (
    DATA_CLASS_SCALAR,
    DataTypePlugin,
    aggregate_devices_to_sites,
)
from core.regions import get_region_resolver
from core.registry import load_yaml
from data_types.scalar_site.status_rules import evaluate_scalar_status


class ScalarSitePlugin(DataTypePlugin):
    data_type = "scalar_site"
    data_class = DATA_CLASS_SCALAR

    def __init__(self) -> None:
        self._client = ONCClient()
        scalar_cfg = load_yaml("scalar_sites.yaml")
        self._rules = load_yaml("status_rules.yaml").get("scalar_site", {})
        self._categories = scalar_cfg.get("default_scalar_categories", [])
        self._include_regions = set(scalar_cfg.get("include_regions") or [])
        self._overrides = scalar_cfg.get("site_overrides") or {}
        self._lookback_hours = int(
            os.getenv("SCALAR_LOOKBACK_HOURS", self._rules.get("lookback_hours", 24))
        )
        self._devices: list[dict[str, Any]] | None = None

    # -- lifecycle ---------------------------------------------------------
    def refresh(self) -> None:
        self._devices = None

    # -- public API --------------------------------------------------------
    def list_devices(self) -> list[dict[str, Any]]:
        if self._devices is not None:
            return self._devices
        if not self._client.available:
            self._devices = []
            return self._devices

        discovered: list[dict[str, Any]] = []
        seen: set[str] = set()
        for category in self._categories:
            for dev in self._client.discover_active_devices(category):
                code = dev.get("deviceCode")
                if not code or code in seen:
                    continue
                seen.add(code)
                discovered.append(dev)

        devices = thread_map(self._build_device, discovered)
        if self._include_regions:
            devices = [d for d in devices if d.get("region") in self._include_regions]
        self._devices = devices
        return devices

    def list_sites(self) -> list[dict[str, Any]]:
        sites = aggregate_devices_to_sites(self.list_devices())
        for site in sites:
            override = self._overrides.get(site["site_code"]) or {}
            if override.get("assignee"):
                site["assignee"] = override["assignee"]
            if override.get("site_name"):
                site["site_name"] = override["site_name"]
        return sites

    # -- internals ---------------------------------------------------------
    def _build_device(self, dev: dict[str, Any]) -> dict[str, Any]:
        location_code = dev.get("locationCode") or ""
        site_code = location_code.split(".")[0] if location_code else "UNKNOWN"
        device_id = dev.get("deviceId")
        device_code = dev["deviceCode"]
        region = get_region_resolver().resolve(location_code)

        clean_df = self._client.get_scalar_by_device(
            device_code, hours=self._lookback_hours, quality_control="clean"
        )
        raw_df = self._client.get_scalar_by_device(
            device_code, hours=self._lookback_hours, quality_control=None
        )
        status = evaluate_scalar_status(clean_df, self._rules)

        return {
            "deviceKey": str(device_id or device_code),
            "dataType": self.data_type,
            "dataClass": DATA_CLASS_SCALAR,
            "deviceCategoryCode": dev.get("deviceCategoryCode") or "",
            "deviceCode": device_code,
            "deviceID": device_id,
            "deviceName": dev.get("deviceName") or device_code,
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
            "dataSearchUrl": self._client.oceans3_data_search_url(device_code),
            "plot_series": {
                "clean": _series_to_points(clean_df),
                "raw": _series_to_points(raw_df),
            },
            "status": status.to_dict(),
            "jira_tickets": [],
            "open_annotations": [],
            "jb_info": get_jb_info_for_device(device_id) if device_id else [],
        }


def _series_to_points(df) -> list[dict[str, str | float]]:
    if df is None or df.empty:
        return []
    return [
        {"t": row.datetime.isoformat(), "v": float(row.value)}
        for row in df.itertuples()
        if row.value is not None
    ]
