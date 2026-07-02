#!/usr/bin/env python3
"""Generate the ONC Instrument Monitor dashboard HTML.

Builds two views from the same underlying device data:
    * site        -> Dashboard_site.html        (PER SITE, scalar-friendly)
    * instrument  -> Dashboard_instrument.html   (PER INSTRUMENT, complex-friendly)
Dashboard.html is a copy of the default view (site).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from core.db import db_configured  # noqa: E402
from core.jira_client import JiraClient  # noqa: E402
from core.onc_client import resolve_onc_token  # noqa: E402
from core.parallel import thread_map  # noqa: E402
from core.registry import (  # noqa: E402
    collect_devices,
    collect_sites,
    get_plugins,
    load_yaml,
)
from core.status import StatusLabel  # noqa: E402

load_dotenv(BASE_DIR / ".env")

DETAIL_DIR = BASE_DIR / "site_details"
DEFAULT_VIEW = "site"
VIEW_FILES = {
    "site": "Dashboard_site.html",
    "instrument": "Dashboard_instrument.html",
}


# --- JIRA enrichment -----------------------------------------------------
def _attach_device_jira(device: dict, jira: JiraClient) -> None:
    if device.get("jira_tickets"):
        return
    device["jira_tickets"] = jira.search_for_device(
        device.get("deviceID"), device.get("deviceCode", "")
    )


def _attach_site_jira(site: dict, jira: JiraClient) -> None:
    # Device-level JIRA is attached via the devices pass (same device objects),
    # so only the site-level ticket search happens here.
    site["jira_tickets"] = jira.search_for_site(site["site_code"], site["site_name"])


# --- marker + nav builders ----------------------------------------------
def _site_marker(site: dict) -> dict:
    status = site.get("site_status", {})
    site_devices = [
        {
            "label": d.get("deviceName") or d.get("deviceCode") or "",
            "deviceCategoryCode": d.get("deviceCategoryCode") or "",
            "deviceCode": d.get("deviceCode") or "",
            "statusColor": (d.get("status") or {}).get("color"),
            "statusIcon": (d.get("status") or {}).get("icon"),
            "statusDisplay": (d.get("status") or {}).get("display", ""),
        }
        for d in site.get("devices", [])
    ]
    return {
        "entityType": "site",
        "locationCode": site["site_code"],
        "locationName": site["site_name"],
        "latitude": site.get("latitude"),
        "longitude": site.get("longitude"),
        "statusColor": status.get("color"),
        "statusIcon": status.get("icon"),
        "displayTitle": site["site_name"],
        "displaySubtitle": f"{len(site.get('devices', []))} instruments",
        "siteName": site["site_name"],
        "siteCode": site["site_code"],
        "sensorLabel": site["site_name"],
        "sensorCode": site["site_code"],
        "devices": site_devices,
        "status": {"overallStatus": status.get("label", "no_data"), "statusMessage": status.get("message", "")},
        "jiraTicketCount": len(site.get("jira_tickets") or []),
        "sectionId": f"site-{site['site_code']}",
    }


def _device_marker(device: dict) -> dict:
    status = device.get("status", {})
    key = device.get("deviceKey") or str(device.get("deviceID") or device.get("deviceCode"))
    instrument_label = device.get("deviceName") or device.get("deviceCode") or ""
    return {
        "entityType": "instrument",
        "locationCode": key,
        "locationName": device.get("locationName") or device.get("siteName") or "",
        "latitude": device.get("latitude"),
        "longitude": device.get("longitude"),
        "statusColor": status.get("color"),
        "statusIcon": status.get("icon"),
        "statusDisplay": status.get("display", ""),
        "displayTitle": instrument_label,
        "displaySubtitle": device.get("locationName") or device.get("siteName") or "",
        "siteName": device.get("siteName") or "",
        "siteCode": device.get("siteCode") or "",
        "sensorLabel": instrument_label,
        "sensorCode": device.get("deviceCode") or "",
        "deviceCategoryCode": device.get("deviceCategoryCode") or "",
        "status": {
            "overallStatus": status.get("label", "no_data"),
            "statusDisplay": status.get("display", ""),
            "statusMessage": status.get("message", ""),
            "lastDataDate": (device.get("availability") or {}).get("last_data_date"),
        },
        "jiraTicketCount": len(device.get("jira_tickets") or []),
        "sectionId": f"device-{key}",
        "dataClass": device.get("dataClass"),
    }


def _nav_groups_by_site(sites: list[dict]) -> list[dict]:
    groups: dict[str, dict] = {}
    for site in sorted(sites, key=lambda s: (s.get("network", "") or "", s["site_name"])):
        label = site.get("network") or "Other"
        group = groups.setdefault(label, {"label": label, "entries": []})
        status = site.get("site_status", {})
        group["entries"].append(
            {
                "locationCode": site["site_code"],
                "name": site["site_name"],
                "meta": f"{site['site_code']} · {len(site.get('devices', []))} devices",
                "statusColor": status.get("color"),
                "statusIcon": status.get("icon"),
            }
        )
    return list(groups.values())


def _nav_groups_by_instrument(devices: list[dict]) -> list[dict]:
    groups: dict[str, dict] = {}
    for device in sorted(devices, key=lambda d: (d.get("deviceCategoryCode", ""), d.get("deviceCode", ""))):
        label = device.get("deviceCategoryCode") or "Instruments"
        group = groups.setdefault(label, {"label": label, "entries": []})
        status = device.get("status", {})
        key = device.get("deviceKey") or str(device.get("deviceID"))
        group["entries"].append(
            {
                "locationCode": key,
                "name": device.get("deviceName") or device.get("deviceCode"),
                "meta": f"{device.get('deviceCode')} · {device.get('siteName') or ''}",
                "statusColor": status.get("color"),
                "statusIcon": status.get("icon"),
            }
        )
    return list(groups.values())


def _summary(status_dicts: list[dict]) -> dict:
    counts = {label.value: 0 for label in StatusLabel}
    for status in status_dicts:
        label = status.get("label", "error")
        counts[label] = counts.get(label, 0) + 1
    total = len(status_dicts)
    needs_attention = counts.get("no_data", 0) + counts.get("bad", 0) + counts.get("intermittent", 0)
    return {"total": total, "counts": counts, "needs_attention": needs_attention}


def _write_detail_json(sites: list[dict]) -> None:
    DETAIL_DIR.mkdir(parents=True, exist_ok=True)
    for site in sites:
        path = DETAIL_DIR / f"{site['site_code']}.json"
        path.write_text(json.dumps(site, indent=2, default=str), encoding="utf-8")


# --- main entry ----------------------------------------------------------
def generate_all() -> dict[str, Path]:
    token = resolve_onc_token()
    jira = JiraClient()
    plugins = get_plugins()
    for plugin in plugins:
        plugin.refresh()

    sites = collect_sites(plugins)
    devices = collect_devices(plugins)

    # JIRA lookups are network-bound; run them concurrently.
    thread_map(lambda s: _attach_site_jira(s, jira), sites)
    thread_map(lambda d: _attach_device_jira(d, jira), devices)

    _write_detail_json(sites)

    status_labels = load_yaml("status_rules.yaml").get("labels", {})
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    env = Environment(loader=FileSystemLoader(str(BASE_DIR / "templates")), autoescape=True)
    template = env.get_template("dashboard.html.j2")

    common = dict(
        dashboard_title=os.getenv("DASHBOARD_TITLE", "ONC Instrument Monitor"),
        dashboard_variant="public",
        dashboard_generated_at_utc=generated_at,
        dashboard_url_prefix=os.getenv("DASHBOARD_URL_PREFIX", ""),
        token=token,
        status_labels=status_labels,
        api_connected=bool(token),
        db_configured=db_configured(),
        view_files=VIEW_FILES,
    )

    outputs: dict[str, Path] = {}

    # PER SITE view
    site_html = template.render(
        view="site",
        summary=_summary([s.get("site_status", {}) for s in sites]),
        nav_groups=_nav_groups_by_site(sites),
        map_markers=[_site_marker(s) for s in sites],
        sites=sites,
        devices=[],
        **common,
    )
    site_path = BASE_DIR / VIEW_FILES["site"]
    site_path.write_text(site_html, encoding="utf-8")
    outputs["site"] = site_path

    # PER INSTRUMENT view
    instrument_html = template.render(
        view="instrument",
        summary=_summary([d.get("status", {}) for d in devices]),
        nav_groups=_nav_groups_by_instrument(devices),
        map_markers=[_device_marker(d) for d in devices],
        sites=[],
        devices=devices,
        **common,
    )
    instrument_path = BASE_DIR / VIEW_FILES["instrument"]
    instrument_path.write_text(instrument_html, encoding="utf-8")
    outputs["instrument"] = instrument_path

    # Default landing = site view
    (BASE_DIR / "Dashboard.html").write_text(site_html, encoding="utf-8")
    outputs["default"] = BASE_DIR / "Dashboard.html"
    return outputs


def generate() -> Path:
    """Backward-compatible entry point returning the default dashboard."""
    return generate_all()["default"]


if __name__ == "__main__":
    outs = generate_all()
    for name, path in outs.items():
        print(f"{name}: {path}")
    if not resolve_onc_token():
        print("WARNING: No ONC_TOKEN / ONC_API_TOKEN set — device discovery is empty.")
