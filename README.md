# ONC Instrument Monitor

Unified, modular monitoring dashboard for the Ocean Networks Canada DAQ team.

**Working group:** Élise Beaudin, Spencer Bialek, Drew  
**Goal:** One tool for all instruments — without reinventing what already works.

## Vision

- Generalized monitoring with a **plugin (`data_type`) architecture**
- Map-first UI inherited from the [Hydrophone Dashboard](../hydrophonedashboard-main@edc8e6199a0/)
- One global **view toggle** — the same map renders two ways:
  - **By Site** (`Dashboard_site.html`) — one marker per location, natural for **scalar** data
  - **By Instrument** (`Dashboard_instrument.html`) — one marker per device, natural for **complex** data
- Validation and commissioning workflow tabs — Phase 3
- JIRA integration and Oceans 3.0 deep links throughout
- Simple Python + JavaScript stack that the next team member can debug

## Two data classes

Each `data_type` plugin declares a `data_class`:

| data_class | Instruments | Natural view | Detail shows |
|------------|-------------|--------------|--------------|
| `complex`  | hydrophone, seismometer, ADCP | per instrument | availability + archive files + Oceans 3.0 (Phase 2) |
| `scalar`   | CTD, oxygen, fluorometer, pCO2, PAR, pH, … | per site | device grid + 24h clean/raw plots |

Both views are built from the **same atomic devices**. Plugins return devices via
`list_devices()`; the base class aggregates them into sites via `list_sites()`.
The **By Site / By Instrument** toggle in the header switches between the two
pre-generated pages, so there is no complex client-side state to debug.

## Connect the ONC API

The dashboard was showing **0 devices** because there is no `.env` file yet. The generated HTML had an empty token:

```html
<data id="oncdw" data-token=""></data>
```

1. Copy `.env.example` to `.env`
2. Set `ONC_TOKEN=` (or `ONC_API_TOKEN=` as in `notebooks/onc-api.ipynb`)
3. Run `python generate_dashboard.py` or click **Refresh Data** in the UI

The header will show **API: connected** when the token is loaded.

Device discovery uses the same pattern as `Get_Hydrophone_Info+Data_PythonClient.ipynb`:

```python
onc.getLocations({"deviceCategoryCode": "CTD"})
# then filter locationCode matching your site (e.g. ECHO3.*)
```

```bash
cd onc-instrument-monitor
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add ONC_TOKEN
```

Edit `config/scalar_sites.yaml` with your assigned sites, then:

```bash
python generate_dashboard.py   # writes Dashboard.html
python server.py               # http://localhost:5050
```

## Project layout

```
onc-instrument-monitor/
├── server.py                 # Flask server + refresh API
├── generate_dashboard.py     # Build static dashboard HTML
├── config/
│   ├── data_types.yaml       # Registered data_type plugins
│   ├── scalar_sites.yaml     # Site assignments (priority)
│   └── status_rules.yaml     # Per-data_type status thresholds
├── core/                     # Shared: ONC client, JIRA, status, registry
├── data_types/               # Plugins (one folder per data_type)
│   ├── scalar_site/          # ✅ Phase 1 — water properties by site
│   └── hydrophone/           # Phase 2 — wrap hydrophonedashboard
├── workflows/                # Validation & commissioning (Phase 3 stubs)
├── templates/                # Jinja2 UI (hydrophone shell adapted)
└── assets/                   # Map JS, ONCDW widgets, CSS (from hydrophone dashboard)
```

## Adding a site (scalar monitoring)

Edit `config/scalar_sites.yaml`:

```yaml
sites:
  - site_code: ECHO3
    site_name: Strait of Georgia East
    network: VENUS
    latitude: 49.0405
    longitude: -123.3178
    assignee: your.name
    device_category_codes: [CTD, OXYGEN, FLNTU]
```

Refresh the dashboard from the UI or `POST /api/refresh`.

## Adding a new data_type

1. Create `data_types/<name>/plugin.py` implementing `DataTypePlugin`
   - set `data_class = "complex"` or `"scalar"`
   - implement `refresh()` and `list_devices()` (base class aggregates sites)
2. Register in `core/registry.py` (`_PLUGIN_REGISTRY`) and `config/data_types.yaml`
3. Add status rules in `config/status_rules.yaml`
4. Enable via `ENABLED_DATA_TYPES` in `.env` (e.g. `scalar_site,hydrophone`)

Each device dict from `list_devices()` should include: `deviceKey`,
`deviceCategoryCode`, `deviceCode`, `deviceID`, `deviceName`, `siteCode`,
`siteName`, `network`, `latitude`, `longitude`, and `status`.

## Status labels

| Label | Meaning |
|-------|---------|
| Good | Data present for lookback window |
| Intermittent | Partial coverage |
| Bad data | Present but failed quality heuristics |
| No data | Missing in lookback window |
| Compromised | Reserved for cruise-planning flag |

## Roadmap

| Phase | Deliverable |
|-------|-------------|
| **1** ✅ | Scalar site plugin + map shell + device grid + 24h plots |
| **2** | Hydrophone plugin (migrate hydrophonedashboard) |
| **3** | Validation & commissioning report generators |
| **4** | ADCP, seismometer, CODAR plugins |
| **5** | Chatbot for ONC API / download URL generation |

## Related repos in DAQ-dashboard/

| Folder | Role |
|--------|------|
| `hydrophonedashboard-main@…` | UI shell, map, JIRA, complex instrument patterns |
| `daqt-apps2-dev@…` | Streamlit plot templates to extract |
| `oncdw-main` | Oceans 3.0 widget library |

## Debugging guide

| Symptom | Look here |
|---------|-----------|
| Map / tabs broken | `assets/monitor_map.js` |
| Wrong site devices | `config/scalar_sites.yaml`, `data_types/scalar_site/plugin.py` |
| Status wrong | `data_types/scalar_site/status_rules.py` |
| ONC fetch errors | `core/onc_client.py`, `.env` ONC_TOKEN |
| JIRA missing | `core/jira_client.py`, ENABLE_JIRA_INTEGRATION |
