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


def resolve_data_types_and_categories(onc_client) -> dict[str, Any]:
    """Fetch live categories from ONC and map them into complex prefixes vs a scalar fallback."""
    # Fetch every active device category code currently registered on the ONC network
    raw_categories = onc_client._onc.getDeviceCategories()
    
    # 🚫 DEVICE CATEGORY EXCLUSION: Filter out ex: 'AISRECEIVER'
    all_category_codes = [
        cat['deviceCategoryCode'] for cat in raw_categories 
        if cat['deviceCategoryCode'].upper() != 'AISRECEIVER'
        if cat['deviceCategoryCode'].upper() != 'ADAPTER'
        if cat['deviceCategoryCode'].upper() != 'ALTIMETER'
        if cat['deviceCategoryCode'].upper() != 'BARS'
        if cat['deviceCategoryCode'].upper() != 'BBES'
        if cat['deviceCategoryCode'].upper() != 'BENTHICCRAWLER'
        if cat['deviceCategoryCode'].upper() != 'BIOFOULING'
        if cat['deviceCategoryCode'].upper() != 'BIOSPECTROMETER'
        if cat['deviceCategoryCode'].upper() != 'BOTTOMPROFILER'
        if cat['deviceCategoryCode'].upper() != 'CAMSYSTEM'
        if cat['deviceCategoryCode'].upper() != 'CHEMINI'
        if cat['deviceCategoryCode'].upper() != 'CAMSYSTEM'
        if cat['deviceCategoryCode'].upper() != 'CORAS'
        if cat['deviceCategoryCode'].upper() != 'CORK'
        if cat['deviceCategoryCode'].upper() != 'COVIS'
        if cat['deviceCategoryCode'].upper() != 'CSEM'
        if cat['deviceCategoryCode'].upper() != 'DATALOGGER'
        if cat['deviceCategoryCode'].upper() != 'DC90'
        if cat['deviceCategoryCode'].upper() != 'DEPTH_TEMP'
        if cat['deviceCategoryCode'].upper() != 'DEPTHSENSOR'
        if cat['deviceCategoryCode'].upper() != 'DIVE_COMPUTER'
        if cat['deviceCategoryCode'].upper() != 'DLRAD'
        if cat['deviceCategoryCode'].upper() != 'DOM'
        if cat['deviceCategoryCode'].upper() != 'DRIFTER'
        if cat['deviceCategoryCode'].upper() != 'GTD'
        if cat['deviceCategoryCode'].upper() != 'H2OO2EXCHANGE'
        if cat['deviceCategoryCode'].upper() != 'INTERNAL_DEVICE_MONITOR'
        if cat['deviceCategoryCode'].upper() != 'LIDAR'
        if cat['deviceCategoryCode'].upper() != 'MAGNETOMETER'
        if cat['deviceCategoryCode'].upper() != 'MBPROFILESONAR'
        if cat['deviceCategoryCode'].upper() != 'MBROTARYSONAR'
        if cat['deviceCategoryCode'].upper() != 'METHSENSOR'
        if cat['deviceCategoryCode'].upper() != 'MBIOSENSOR'
        if cat['deviceCategoryCode'].upper() != 'METSTN'
        if cat['deviceCategoryCode'].upper() != 'MODEM'
        if cat['deviceCategoryCode'].upper() != 'MUONTRACKER'
        if cat['deviceCategoryCode'].upper() != 'NAV'
        if cat['deviceCategoryCode'].upper() != 'NODE'
        if cat['deviceCategoryCode'].upper() != 'OCEANOGRAPHICRADAR'
        if cat['deviceCategoryCode'].upper() != 'ORIENTATION'
        if cat['deviceCategoryCode'].upper() != 'PARTANALYZER'
        if cat['deviceCategoryCode'].upper() != 'PIEZOMETER'
        if cat['deviceCategoryCode'].upper() != 'PLANKTONCAMSYSTEM'
        if cat['deviceCategoryCode'].upper() != 'PLANKTONSAMPLER'
        if cat['deviceCategoryCode'].upper() != 'PLATFORM'
        if cat['deviceCategoryCode'].upper() != 'POCAM'
        if cat['deviceCategoryCode'].upper() != 'PONECAMERA'
        if cat['deviceCategoryCode'].upper() != 'POWER_SUPPLY'
        if cat['deviceCategoryCode'].upper() != 'PPPFLT'
        if cat['deviceCategoryCode'].upper() != 'PPPINT'
        if cat['deviceCategoryCode'].upper() != 'PPPORB'
        if cat['deviceCategoryCode'].upper() != 'PTL'
        if cat['deviceCategoryCode'].upper() != 'PYRANOMETER'
        if cat['deviceCategoryCode'].upper() != 'PYRGEOMETER'
        if cat['deviceCategoryCode'].upper() != 'RADIOMETER'
        if cat['deviceCategoryCode'].upper() != 'RAIN_GAUGE'
        if cat['deviceCategoryCode'].upper() != 'REFINEDFUELSFLUOROMETER'
        if cat['deviceCategoryCode'].upper() != 'ROV_CAMERA'
        if cat['deviceCategoryCode'].upper() != 'SEDTRAP'
        if cat['deviceCategoryCode'].upper() != 'SERVER'
        if cat['deviceCategoryCode'].upper() != 'STANDARDMODULE'
        if cat['deviceCategoryCode'].upper() != 'SUSPENDED_SEDPROFILER'
        if cat['deviceCategoryCode'].upper() != 'TARRAY'
        if cat['deviceCategoryCode'].upper() != 'TEMPHUMID'
        if cat['deviceCategoryCode'].upper() != 'TEMPOMINI'
        if cat['deviceCategoryCode'].upper() != 'TEMPSENSOR'
        if cat['deviceCategoryCode'].upper() != 'TOWEDCAMERASYSTEM'
        if cat['deviceCategoryCode'].upper() != 'TRANSMISSOMETER'
        if cat['deviceCategoryCode'].upper() != 'UCRDS'
        if cat['deviceCategoryCode'].upper() != 'UURS'
        if cat['deviceCategoryCode'].upper() != 'UWVOLTAMMETRICSYSTEM'
        if cat['deviceCategoryCode'].upper() != 'VPINST'
        if cat['deviceCategoryCode'].upper() != 'VPBASE'
        if cat['deviceCategoryCode'].upper() != 'WATERSAMPLER'
        if cat['deviceCategoryCode'].upper() != 'WAVE_BUOY'
        if cat['deviceCategoryCode'].upper() != 'WAVELENGTHOPTICALMODULE'
        if cat['deviceCategoryCode'].upper() != 'WETLABS_WQM'
        if cat['deviceCategoryCode'].upper() != 'WINDMONITOR'
        if cat['deviceCategoryCode'].upper() != 'CAMLIGHTS'
        if cat['deviceCategoryCode'].upper() != 'ICE_BUOY'
    ]
    
    # Load configuration file rules
    with open(CONFIG_DIR / "data_types.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    data_types = config.get("data_types", {})
    complex_claimed_categories = set()
    
    # Step through complex types first and let them claim their matching categories
    for name, meta in data_types.items():
        if meta.get("data_class") == "complex":
            prefixes = meta.get("category_prefixes") or meta.get("categories") or []
            
            # Find all live categories matching the prefix tokens (case-insensitive)
            resolved = [
                code for code in all_category_codes
                if any(code.upper().startswith(str(pfx).upper()) for pfx in prefixes)
            ]
            
            meta["resolved_categories"] = resolved
            complex_claimed_categories.update(resolved)
            print(f"📦 Plugin [{name:<12}] dynamically claimed {len(resolved)} categories: {resolved}")

    # Fallback: Assign every single remaining category code directly to Scalar
    scalar_fallback = [
        code for code in all_category_codes 
        if code not in complex_claimed_categories
    ]
    
    if "scalar_site" in data_types:
        data_types["scalar_site"]["resolved_categories"] = scalar_fallback
        print(f"🌊 Plugin [scalar_site ] dynamically absorbed the remaining {len(scalar_fallback)} categories.")

    return data_types


def get_plugins(onc_client: Any) -> list[DataTypePlugin]:
    """Discover, configure, and instantiate all enabled dashboard plugins safely."""
    resolved_spec_map = resolve_data_types_and_categories(onc_client)
    
    plugins: list[DataTypePlugin] = []
    for data_type in enabled_data_types():
        spec = _PLUGIN_REGISTRY.get(data_type)
        if not spec:
            raise ValueError(f"Unknown data_type: {data_type}")
            
        meta = resolved_spec_map.get(data_type, {})
        categories = meta.get("resolved_categories", [])
        plugin_class = _load_plugin_class(spec)
        
        # Safe Initialization Block
        if data_type == "scalar_site":
            plugins.append(plugin_class(categories=categories))
        else:
            plugin_instance = plugin_class()
            plugin_instance.categories = categories
            plugins.append(plugin_instance)
        
    return plugins


def get_plugin(data_type: str, categories: list[str] | None = None) -> DataTypePlugin:
    """Fallback single-plugin loader (useful for testing isolated contexts)."""
    spec = _PLUGIN_REGISTRY.get(data_type)
    if not spec:
        raise ValueError(f"Unknown data_type: {data_type}")
    return _load_plugin_class(spec)(categories=categories or [])


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
    """All sites across enabled plugins, merged by siteCode (PER SITE view)."""
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