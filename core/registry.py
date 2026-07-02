"""Load data_type plugins, YAML configuration, and build the two dashboard views."""

from __future__ import annotations

import copy
import importlib
import os
from pathlib import Path
from typing import Any

import yaml

from core.plugin_base import DataTypePlugin, compute_site_status

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"

_PLUGIN_REGISTRY: dict[str, str] = {
    "scalar_site": "data_types.scalar_site.plugin:ScalarSitePlugin",
    "hydrophone": "data_types.hydrophone.plugin:HydrophonePlugin",
    "seismometer": "data_types.seismometer.plugin:SeismometerPlugin",
    "adcp": "data_types.adcp.plugin:AdcpPlugin",
}


def load_yaml(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / name
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def enabled_data_types() -> list[str]:
    raw = os.getenv("ENABLED_DATA_TYPES", "scalar_site")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _load_plugin_class(spec: str) -> type[DataTypePlugin]:
    module_path, class_name = spec.split(":")
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def get_plugins() -> list[DataTypePlugin]:
    plugins: list[DataTypePlugin] = []
    for data_type in enabled_data_types():
        spec = _PLUGIN_REGISTRY.get(data_type)
        if not spec:
            raise ValueError(f"Unknown data_type: {data_type}")
        plugins.append(_load_plugin_class(spec)())
    return plugins


def get_plugin(data_type: str) -> DataTypePlugin:
    spec = _PLUGIN_REGISTRY.get(data_type)
    if not spec:
        raise ValueError(f"Unknown data_type: {data_type}")
    return _load_plugin_class(spec)()


def collect_devices(plugins: list[DataTypePlugin]) -> list[dict[str, Any]]:
    """All atomic devices across enabled plugins (for the PER INSTRUMENT view)."""
    devices: list[dict[str, Any]] = []
    for plugin in plugins:
        for device in plugin.list_devices():
            device.setdefault("dataType", plugin.data_type)
            device.setdefault("dataClass", plugin.data_class)
            devices.append(device)
    return devices


def collect_sites(plugins: list[DataTypePlugin]) -> list[dict[str, Any]]:
    """All sites across enabled plugins, merged by siteCode (PER SITE view).

    Devices from different data types at the same location are combined so a
    site can show both scalar and complex instruments together.
    """
    merged: dict[str, dict[str, Any]] = {}
    for plugin in plugins:
        for site in plugin.list_sites():
            code = site["site_code"]
            existing = merged.get(code)
            if existing is None:
                merged[code] = copy.deepcopy(site)
                continue
            existing["devices"].extend(site.get("devices", []))
            classes = set(existing.get("data_classes", []))
            classes.update(site.get("data_classes", []))
            existing["data_classes"] = sorted(classes)
            if existing.get("latitude") is None:
                existing["latitude"] = site.get("latitude")
            if existing.get("longitude") is None:
                existing["longitude"] = site.get("longitude")

    for site in merged.values():
        site["site_status"] = compute_site_status(site.get("devices", [])).to_dict()
    return list(merged.values())
