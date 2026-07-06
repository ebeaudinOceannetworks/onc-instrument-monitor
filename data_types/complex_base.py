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
        import re
        import pandas as pd
        from datetime import datetime, timedelta, timezone

        location_code = dev.get("locationCode") or ""
        site_code = location_code.split(".")[0] if location_code else "UNKNOWN"
        device_id = dev.get("deviceId")
        region = get_region_resolver().resolve(location_code)

        # 1. Pull standard daily summary calculations
        availability = compute_availability(
            self._client,
            dev["deviceCode"],
            self.extensions,
            days=self.availability_days,
            expected_files_per_day=self.expected_files_per_day,
        )

        # 2. Prepare the daily timeline tracking blocks
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.availability_days)
        
        date_list = [(start_time + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(self.availability_days + 1)]
        timeline_data = {d: {ext: [] for ext in self.extensions} for d in date_list}

        params = {
            'deviceCode': dev["deviceCode"],
            'dateFrom': start_time.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
            'dateTo': end_time.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
            'rowLimit': 100000
        }

        try:
            res = self._client._onc.getArchivefileByDevice(params)
            files = res.get('files', []) if isinstance(res, dict) else []
        except Exception:
            files = []

        # Your exact filename timestamp extraction pattern
        pattern = re.compile(r"(\d{8}T\d{6})")

        for f in files:
            # 🟢 THE FIX: Treat f directly as the filename string instead of a dictionary
            filename = str(f) if f else ''
            if not filename:
                continue
                
            ext = filename.split('.')[-1].lower()
            if ext not in self.extensions:
                continue

            match = pattern.search(filename)
            if match:
                try:
                    f_start = pd.to_datetime(match.group(1), format='%Y%m%dT%H%M%S').tz_localize('UTC')
                    date_key = f_start.strftime("%Y-%m-%d")
                    
                    if date_key not in timeline_data:
                        continue

                    # Calculate exact horizontal minute positioning offsets
                    start_minutes = f_start.hour * 60.0 + f_start.minute + f_start.second / 60.0
                    duration_minutes = 5.0 
                    
                    left_pct = (start_minutes / 1440.0) * 100.0
                    width_pct = (duration_minutes / 1440.0) * 100.0

                    timeline_data[date_key][ext].append({
                        "filename": filename,
                        "start_str": f_start.strftime("%H:%M"),
                        "left": round(left_pct, 3),
                        "width": round(width_pct, 3)
                    })
                except Exception:
                    continue

        days_timeline = []
        for d in date_list:
            try:
                dt_obj = datetime.strptime(d, "%Y-%m-%d")
                lbl = dt_obj.strftime("%b-%d")
            except Exception:
                lbl = d
                
            days_timeline.append({
                "date": d,
                "label": lbl,
                "extensions": timeline_data[d]
            })

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
            "archive_timeline": days_timeline,
            "extensions_list": self.extensions,
            "availability_days": self.availability_days,
            "jira_tickets": [],
            "open_annotations": [],
            "plot_series": {},
            "jb_info": [],
        }

        