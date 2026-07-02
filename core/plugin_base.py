"""Base contract for data_type plugins.

Every monitored data category (hydrophone, scalar water properties, ADCP, ...)
implements this interface. The dashboard can render two ways from the same data:

  * PER INSTRUMENT  -> one map marker per device        (natural for complex data)
  * PER SITE        -> one map marker per site/location  (natural for scalar data)

Plugins expose atomic *devices*. The base class aggregates them into *sites*.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core.status import EntityStatus, StatusLabel, worst_status

# Data classes distinguish how a device is monitored.
DATA_CLASS_COMPLEX = "complex"   # hydrophone, seismometer, ADCP
DATA_CLASS_SCALAR = "scalar"     # CTD, oxygen, fluorometer, pCO2, PAR, pH, ...


class DataTypePlugin(ABC):
    """Contract implemented by each data_type plugin."""

    data_type: str
    data_class: str  # DATA_CLASS_COMPLEX | DATA_CLASS_SCALAR

    @abstractmethod
    def refresh(self) -> None:
        """Fetch or recompute cached monitoring data."""

    @abstractmethod
    def list_devices(self) -> list[dict[str, Any]]:
        """Return atomic device/instrument entities.

        Each device dict should include at least:
            deviceKey, deviceCategoryCode, deviceCode, deviceID, deviceName,
            siteCode, siteName, network, latitude, longitude,
            status {label,color,icon,message}
        Optional: depth, plot_series, jira_tickets, open_annotations, jb_info,
            deviceDetailsUrl, dataSearchUrl.
        The plugin's data_class is stamped onto every device automatically.
        """

    def list_sites(self) -> list[dict[str, Any]]:
        """Aggregate this plugin's devices into site payloads.

        Plugins with configured sites (e.g. scalar_site) may override this to
        also surface sites that currently have zero discovered devices.
        """
        return aggregate_devices_to_sites(self._stamped_devices())

    def _stamped_devices(self) -> list[dict[str, Any]]:
        devices = self.list_devices()
        for device in devices:
            device.setdefault("dataType", self.data_type)
            device.setdefault("dataClass", self.data_class)
        return devices


def aggregate_devices_to_sites(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group atomic devices into site payloads keyed by siteCode."""
    sites: dict[str, dict[str, Any]] = {}
    for device in devices:
        code = device.get("siteCode") or "UNKNOWN"
        site = sites.get(code)
        if site is None:
            site = {
                "site_code": code,
                "site_name": device.get("siteName") or code,
                "network": device.get("network", ""),
                "assignee": device.get("assignee", ""),
                "latitude": device.get("latitude"),
                "longitude": device.get("longitude"),
                "is_ferry": device.get("is_ferry", False),
                "devices": [],
                "data_classes": set(),
                "jira_tickets": [],
                "open_annotations": [],
            }
            sites[code] = site
        site["devices"].append(device)
        if device.get("dataClass"):
            site["data_classes"].add(device["dataClass"])
        if site["latitude"] is None:
            site["latitude"] = device.get("latitude")
        if site["longitude"] is None:
            site["longitude"] = device.get("longitude")

    for site in sites.values():
        site["site_status"] = compute_site_status(site["devices"]).to_dict()
        site["data_classes"] = sorted(c for c in site["data_classes"] if c)
    return list(sites.values())


def compute_site_status(devices: list[dict[str, Any]]) -> EntityStatus:
    if not devices:
        return EntityStatus(StatusLabel.NO_DATA, "No devices discovered")
    statuses = []
    for device in devices:
        label_value = (device.get("status") or {}).get("label", "no_data")
        try:
            statuses.append(EntityStatus(StatusLabel(label_value)))
        except ValueError:
            statuses.append(EntityStatus(StatusLabel.ERROR))
    return worst_status(statuses)
