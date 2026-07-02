"""Scalar site data_type — site-centric water property monitoring.

Discovers *all* active scalar instruments across the dynamically configured categories
network-wide, then groups them into sites by location. Each device carries its region 
(NEPTUNE / VENUS / West Coast / ...) so the dashboard sidebar groups sites by region.

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

    def __init__(self, categories: list[str]) -> None:
        super().__init__()
        self._client = ONCClient()
        scalar_cfg = load_yaml("scalar_sites.yaml")
        self._rules = load_yaml("status_rules.yaml").get("scalar_site", {})
        
        # 🌊 THE HANDS-OFF FIX: Assign directly to the categories array passed from the registry
        self._categories = categories
        
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
            device_code, hours=self._lookback_hours, quality_control="raw",
        )
        status = evaluate_scalar_status(clean_df, self._rules)

        # JB status
        raw_jb_rows = get_jb_info_for_device(device_id) if device_id else []
        
        # Identify unique connected milestones and query their raw payloads concurrently
        jb_codes = {row.get("devicecode") for row in raw_jb_rows if row.get("devicecode")}
        jb_payloads = {}
        
        from datetime import datetime, timedelta, timezone
        end = datetime.now(timezone.utc)
        lookback = self._lookback_hours if hasattr(self, '_lookback_hours') else 24
        start = end - timedelta(hours=lookback)
        
        for jb_code in jb_codes:
            try:
                params = {
                    "deviceCode": jb_code,
                    "dateFrom": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                    "dateTo": end.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                    "resamplePeriod": 900
                }
                jb_payloads[jb_code] = self._client._onc.getScalardataByDevice(params)
            except Exception:
                jb_payloads[jb_code] = None
        
        # Parse flat database rows into organized structural milestone hop nodes
        hops_map = {}
        for row in raw_jb_rows:
            hop_level = row.get("hop_level", 1)
            jb_code = row.get("devicecode")
            sensor_code = row.get("sensorcode")
            
            if hop_level not in hops_map:
                hops_map[hop_level] = {
                    "device_code": jb_code,
                    "category": row.get("devicecategoryname") or "Component",
                    "status_channel": None,
                    "port_status": "no_data",
                    "port_display": "N/A"
                }
            if sensor_code and "_status" in sensor_code:
                hops_map[hop_level]["status_channel"] = sensor_code

        # Evaluate network metrics and power switch configurations for each hop level
        lineage_breadcrumbs = []
        for level in sorted(hops_map.keys()):
            hop = hops_map[level]
            h_code = hop["device_code"]
            s_code = hop["status_channel"]
            payload = jb_payloads.get(h_code)
            
            # Global Chassis Network Verification
            chassis_online = False
            if isinstance(payload, dict) and isinstance(payload.get("sensorData"), list):
                for stream in payload["sensorData"]:
                    if isinstance(stream, dict):
                        vals = stream.get("data", {}).get("values", [])
                        if isinstance(vals, list) and vals:
                            chassis_online = True
                            break
            
            hop["chassis_status"] = "good" if chassis_online else "no_data"
            hop["chassis_display"] = "Online" if chassis_online else "Passive/Offline"
            
            # Targeted Port Power State Verification
            if s_code and chassis_online:
                raw_value = None
                for stream in payload["sensorData"]:
                    if isinstance(stream, dict) and stream.get("sensorCode") == s_code:
                        values = stream.get("data", {}).get("values", [])
                        if isinstance(values, list) and values:
                            raw_value = values[-1]
                        break
                
                if raw_value is None:
                    hop["port_status"] = "no_data"
                    hop["port_display"] = "Unknown"
                elif float(raw_value) in (3.0, 7.0, 39.0):
                    hop["port_status"] = "good"
                    hop["port_display"] = "On"
                else:
                    hop["port_status"] = "bad"
                    hop["port_display"] = "Off"
            elif s_code:
                hop["port_status"] = "bad"
                hop["port_display"] = "Off"
                
            lineage_breadcrumbs.append(hop)

        # Extract global macro status indicators for high-level sorting summaries
        overall_chassis = "good" if any(h["chassis_status"] == "good" for h in lineage_breadcrumbs) else "no_data"
        overall_port = "good" if any(h["port_status"] == "good" for h in lineage_breadcrumbs) else "no_data"

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

            # Universal breadcrumb properties mappings
            "lineage": lineage_breadcrumbs,
            "jb_chassis_status": overall_chassis,
            "jb_port_status": overall_port
        }


def _series_to_points(df) -> list[dict[str, str | float]]:
    if df is None or df.empty:
        return []
    return [
        {"t": row.datetime.isoformat(), "v": float(row.value)}
        for row in df.itertuples()
        if row.value is not None
    ]