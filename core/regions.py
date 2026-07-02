"""Resolve a device/location to an ONC region (NEPTUNE, VENUS, West Coast, ...).

Builds a ``locationCode -> region`` map by walking the ONC location tree once
per region root (cached to disk). Region roots + labels are configured in
``config/regions.yaml``.
"""

from __future__ import annotations

from core import cache
from core.onc_client import ONCClient

_TREE_TTL = 7 * 24 * 3600  # the location tree changes rarely


class RegionResolver:
    def __init__(self, client: ONCClient | None = None, config: dict | None = None) -> None:
        from core.registry import load_yaml

        self._client = client or ONCClient()
        cfg = config or load_yaml("regions.yaml")
        self._roots: dict[str, str] = cfg.get("region_roots", {})
        self._fallback: str = cfg.get("fallback", "Other")
        self._map: dict[str, str] | None = None

    def resolve(self, location_code: str | None) -> str:
        if self._map is None:
            self._map = self._build()
        if not location_code:
            return self._fallback
        if location_code in self._map:
            return self._map[location_code]
        base = location_code.split(".")[0]
        return self._map.get(base, self._fallback)

    def _build(self) -> dict[str, str]:
        mapping: dict[str, str] = {}
        if not self._client.available:
            return mapping
        for root_code, label in self._roots.items():
            codes = cache.cached(
                f"regiontree:{root_code}",
                _TREE_TTL,
                lambda rc=root_code: self._collect_codes(rc),
            )
            for code in codes:
                mapping.setdefault(code, label)
        return mapping

    def _collect_codes(self, root_code: str) -> list[str]:
        try:
            tree = self._client._onc.getLocationsTree({"locationCode": root_code})
        except Exception:
            return []

        codes: list[str] = []

        def walk(nodes):
            for node in nodes or []:
                loc = node.get("locationCode")
                if loc:
                    codes.append(loc)
                walk(node.get("children"))

        walk(tree)
        return codes


_default_resolver: RegionResolver | None = None


def get_region_resolver() -> RegionResolver:
    """Process-wide resolver (the disk cache keeps tree walks cheap)."""
    global _default_resolver
    if _default_resolver is None:
        _default_resolver = RegionResolver()
    return _default_resolver
