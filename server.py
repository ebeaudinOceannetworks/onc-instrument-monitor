#!/usr/bin/env python3
"""Flask server for the ONC Instrument Monitor."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

load_dotenv(BASE_DIR / ".env")

from generate_dashboard import VIEW_FILES, generate_all  # noqa: E402
from workflows.commissioning import (  # noqa: E402
    CommissioningRequest,
    list_available_deployments,
    run_commissioning,
)
from workflows.validation import ValidationRequest, run_validation  # noqa: E402

app = Flask(__name__)
DASHBOARD_HTML = BASE_DIR / "Dashboard.html"
DETAIL_DIR = BASE_DIR / "site_details"
_refresh_lock = threading.Lock()


def _ensure_generated():
    if not DASHBOARD_HTML.exists():
        generate_all()


@app.route("/")
def index():
    _ensure_generated()
    view = request.args.get("view", "site")
    filename = VIEW_FILES.get(view, VIEW_FILES["site"])
    return send_from_directory(BASE_DIR, filename)


@app.route("/Dashboard_site.html")
def dashboard_site():
    _ensure_generated()
    return send_from_directory(BASE_DIR, VIEW_FILES["site"])


@app.route("/Dashboard_instrument.html")
def dashboard_instrument():
    _ensure_generated()
    return send_from_directory(BASE_DIR, VIEW_FILES["instrument"])


@app.route("/assets/<path:filename>")
def assets(filename):
    return send_from_directory(BASE_DIR / "assets", filename)


@app.route("/site_details/<site_code>.json")
def site_detail_json(site_code):
    path = DETAIL_DIR / f"{site_code}.json"
    if not path.exists():
        return jsonify({"error": "not found"}), 404
    return Response(path.read_text(encoding="utf-8"), mimetype="application/json")


@app.route("/api/refresh", methods=["POST"])
def refresh():
    if not _refresh_lock.acquire(blocking=False):
        return jsonify({"status": "busy"}), 409
    try:
        outputs = generate_all()
        return jsonify(
            {
                "status": "ok",
                "paths": {name: str(path) for name, path in outputs.items()},
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    finally:
        _refresh_lock.release()


@app.route("/api/workflows/validation", methods=["POST"])
def validation_workflow():
    body = request.get_json(force=True, silent=True) or {}
    result = run_validation(
        ValidationRequest(
            reference_device_id=str(
                body.get("reference_device_id", body.get("device_id", ""))
            ),
        )
    )
    return jsonify(result)


@app.route("/api/workflows/commissioning/deployments", methods=["POST"])
def commissioning_deployments():
    body = request.get_json(force=True, silent=True) or {}
    deployments = list_available_deployments(
        str(body.get("device_code", "")).strip(),
        str(body.get("location_code", "")).strip(),
    )
    return jsonify({"deployments": deployments})


@app.route("/api/workflows/commissioning", methods=["POST"])
def commissioning_workflow():
    body = request.get_json(force=True, silent=True) or {}
    result = run_commissioning(
        CommissioningRequest(
            device_code=str(body.get("device_code", "")),
            location_code=str(body.get("location_code", "")),
            deployment=str(body.get("deployment", "")),
            review_phase=str(body.get("review_phase", "")),
        )
    )
    return jsonify(result)

@app.route('/api/runtime-status')
def get_runtime_status():
    # This is a temporary mock response to satisfy the frontend
    return jsonify({
        "status": "healthy",
        "message": "Backend connected successfully!"
    })


def main():
    host = os.getenv("DASHBOARD_HOST", "0.0.0.0")
    port = int(os.getenv("DASHBOARD_PORT", "5050"))
    _ensure_generated()
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
