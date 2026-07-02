"""Thin wrapper around ONC OpenAPI discovery and scalar data services."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv
from onc.onc import ONC

from core import cache

load_dotenv()

SCALAR_HOST = "data.oceannetworks.ca"


def _ttl(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def resolve_onc_token() -> str:
    return (
        os.getenv("ONC_TOKEN", "").strip()
        or os.getenv("ONC_API_TOKEN", "").strip()
    )


class ONCClient:
    def __init__(self, token: str | None = None):
        self.token = token or resolve_onc_token()
        self._onc = ONC(self.token) if self.token else None
        self._location_name_cache: dict[str, str] = {}

    @property
    def available(self) -> bool:
        return bool(self.token and self._onc)

    def get_locations_by_category(self, device_category_code: str) -> list[dict[str, Any]]:
        if not self._onc:
            return []
        return self._onc.getLocations({"deviceCategoryCode": device_category_code.upper()})

    def get_deployments(
        self,
        *,
        device_category_code: str,
        location_code: str | None = None,
    ) -> list[dict[str, Any]]:
        if not self._onc:
            return []
        params: dict[str, str] = {"deviceCategoryCode": device_category_code}
        if location_code:
            params["locationCode"] = location_code
        return self._onc.getDeployments(params)

    def get_scalar_by_device(
        self,
        device_code: str,
        *,
        hours: int = 24,
        quality_control: str | None = "clean",
    ) -> pd.DataFrame:
        if not self._onc or not device_code:
            return pd.DataFrame()

        bucket = datetime.now(timezone.utc).strftime("%Y%m%d%H")
        key = f"scalar:{device_code}:{hours}:{quality_control}:{bucket}"
        records = cache.cached(
            key,
            _ttl("SCALAR_TTL", 1800),
            lambda: self._fetch_scalar_records(device_code, hours, quality_control),
        )
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        df["datetime"] = pd.to_datetime(df["datetime"], utc=True, errors="coerce")
        return df.dropna(subset=["datetime"])

    def _fetch_scalar_records(
        self, device_code: str, hours: int, quality_control: str | None
    ) -> list[dict[str, Any]]:
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=hours)
        
        # Initialize the baseline tracking metadata parameters
        params: dict[str, Any] = {
            "deviceCode": device_code,
            "dateFrom": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "dateTo": end.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        }
        if quality_control != "raw":
            params["resamplePeriod"] = _ttl("SCALAR_RESAMPLE_SECONDS", 900)

        if quality_control:
            params["qualityControl"] = quality_control

        try:
            payload = self._onc.getScalardataByDevice(params)
            df = _parse_scalar_payload(payload)
        except Exception:
            df = self._scalar_via_internal_api(
                device_code, hours=hours, is_clean=quality_control == "clean"
            )
        if df is None or df.empty:
            return []
        return [
            {"datetime": row.datetime.isoformat(), "value": float(row.value)}
            for row in df.itertuples()
            if row.value is not None and pd.notna(row.value)
        ]

    def _scalar_via_internal_api(
        self,
        device_code: str,
        *,
        hours: int = 24,
        is_clean: bool = True,
    ) -> pd.DataFrame:
        """Fallback when OpenAPI scalar route is unavailable."""
        if not self.token:
            return pd.DataFrame()
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=hours)
        params = {
            "datefrom": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "dateto": end.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "devicecode": device_code,
            "option": 3,
            "isClean": "true" if is_clean else "false",
            "plotpoints": max(100, min(800, hours * 4)),
        }
        url = f"https://{SCALAR_HOST}/ScalarDataAPIService"
        try:
            response = requests.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=60,
            )
            response.raise_for_status()
            return _parse_scalar_payload(response.json())
        except Exception:
            return pd.DataFrame()

    # -- discovery (deployments -> devices) --------------------------------
    def discover_active_devices(self, category: str, days_back: int = 3650) -> list[dict[str, Any]]:
        """Return currently-deployed devices for a deviceCategoryCode (cached).

        Uses bulk lookups (one getDeployments + one getDevices + one getLocations
        per category) instead of a per-device round trip, then keeps only active
        deployments (``end`` is null). Results are cached to disk.
        """
        if not self._onc:
            return []
        return cache.cached(
            f"discover:{category}",
            _ttl("DISCOVERY_TTL", 21600),
            lambda: self._discover_active_devices(category, days_back),
        )

    def _discover_active_devices(self, category: str, days_back: int) -> list[dict[str, Any]]:
        date_from = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )
        try:
            deployments = self._onc.getDeployments(
                {"deviceCategoryCode": category, "dateFrom": date_from}
            )
        except Exception:
            return []

        # One bulk call each for device IDs/names and location names.
        id_map: dict[str, Any] = {}
        name_map: dict[str, str] = {}
        try:
            for dev in self._onc.getDevices({"deviceCategoryCode": category}) or []:
                code = dev.get("deviceCode")
                if code:
                    id_map[code] = dev.get("deviceId")
                    name_map[code] = dev.get("deviceName")
        except Exception:
            pass

        loc_map: dict[str, str] = {}
        try:
            for loc in self._onc.getLocations({"deviceCategoryCode": category}) or []:
                lc = loc.get("locationCode")
                if lc:
                    loc_map[lc] = loc.get("locationName")
        except Exception:
            pass

        out: list[dict[str, Any]] = []
        for dep in deployments or []:
            if dep.get("end"):  # active deployments only
                continue
            device_code = dep.get("deviceCode")
            if not device_code:
                continue
            location_code = dep.get("locationCode") or ""
            out.append(
                {
                    "deviceCode": device_code,
                    "deviceId": id_map.get(device_code),
                    "deviceName": name_map.get(device_code) or device_code,
                    "deviceCategoryCode": (dep.get("deviceCategoryCode") or category).upper(),
                    "locationCode": location_code,
                    "locationName": loc_map.get(location_code) or location_code,
                    "latitude": dep.get("lat") or dep.get("latitude"),
                    "longitude": dep.get("lon") or dep.get("longitude"),
                    "depth": dep.get("depth"),
                    "begin": dep.get("begin"),
                }
            )
        return out

    def get_archive_files(
        self, device_code: str, extension: str, date_from: str, date_to: str
    ) -> list[Any]:
        """List archived files for a device + extension (cached)."""
        if not self._onc or not device_code:
            return []
        key = f"arch:{device_code}:{extension}:{date_from}:{date_to}"
        return cache.cached(
            key,
            _ttl("AVAILABILITY_TTL", 3600),
            lambda: self._get_archive_files(device_code, extension, date_from, date_to),
        )

    def _get_archive_files(
        self, device_code: str, extension: str, date_from: str, date_to: str
    ) -> list[Any]:
        try:
            resp = self._onc.getArchivefileByDevice(
                {
                    "deviceCode": device_code,
                    "dateFrom": date_from,
                    "dateTo": date_to,
                    "extension": extension,
                }
            )
        except Exception:
            return []
        if isinstance(resp, dict):
            return resp.get("files") or []
        if isinstance(resp, list):
            return resp
        return []

    # -- workflow helpers --------------------------------------------------
    def list_deployments(
        self, *, device_code: str | None = None, location_code: str | None = None
    ) -> list[dict[str, Any]]:
        """Raw deployment history for a device and/or location (commissioning)."""
        if not self._onc:
            return []
        params: dict[str, str] = {}
        if device_code:
            params["deviceCode"] = device_code
        if location_code:
            params["locationCode"] = location_code
        if not params:
            return []
        try:
            return self._onc.getDeployments(params) or []
        except Exception:
            return []

    def get_device(self, *, device_code: str | None = None, device_id: str | None = None) -> dict[str, Any]:
        """Look up a single device's metadata by code or numeric id (validation)."""
        if not self._onc:
            return {}
        for params in ([{"deviceCode": device_code}] if device_code else []) + (
            [{"deviceId": device_id}] if device_id else []
        ):
            try:
                res = self._onc.getDevices(params)
                if res:
                    return res[0]
            except Exception:
                continue
        return {}

    def oceans3_device_url(self, device_id: int | str) -> str:
        return f"https://data.oceannetworks.ca/DeviceListing?DeviceId={device_id}"

    def oceans3_data_search_url(self, device_code: str) -> str:
        return f"https://data.oceannetworks.ca/DataSearch?deviceCode={device_code}"


_PREFERRED_SENSORS = ("temperature", "temp", "oxygen", "salinity", "pressure")


def _parse_scalar_payload(payload: Any) -> pd.DataFrame:
    """Parse ONC scalar data into a single-sensor time series.

    A device (e.g. a CTD) reports several sensors; concatenating them produces a
    meaningless plot, so we pick one representative sensor (preferring
    temperature/oxygen/…, otherwise the first sensor that has data).
    """
    if not payload:
        return pd.DataFrame()

    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = payload.get("sensorData") or payload.get("data") or []
        if isinstance(rows, dict):
            rows = [rows]
    else:
        return pd.DataFrame()

    blocks_with_data: list[tuple[str, list, list]] = []
    for block in rows:
        if not isinstance(block, dict):
            continue
        data = block.get("data") or block
        sample_times = data.get("sampleTimes") or data.get("time") or []
        sample_values = (
            data.get("values")
            or data.get("avg")
            or data.get("value")
            or data.get("data")
            or []
        )
        if sample_times and sample_values:
            name = str(
                block.get("sensorName")
                or block.get("sensorCode")
                or block.get("sensorCategoryCode")
                or ""
            ).lower()
            blocks_with_data.append((name, sample_times, sample_values))

    if not blocks_with_data:
        return pd.DataFrame()

    chosen = None
    for keyword in _PREFERRED_SENSORS:
        for name, times, values in blocks_with_data:
            if keyword in name:
                chosen = (times, values)
                break
        if chosen:
            break
    if chosen is None:
        _, times, values = blocks_with_data[0]
        chosen = (times, values)

    times, values = chosen
    return pd.DataFrame(
        {
            "datetime": pd.to_datetime(times, utc=True, errors="coerce"),
            "value": pd.to_numeric(values, errors="coerce"),
        }
    ).dropna(subset=["datetime"])


def location_matches_site(location_code: str, site_code: str) -> bool:
    loc = (location_code or "").upper()
    site = (site_code or "").upper()
    if not loc or not site:
        return False
    return loc == site or loc.startswith(f"{site}.")
