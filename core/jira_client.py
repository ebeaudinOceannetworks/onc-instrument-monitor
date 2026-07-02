"""Optional JIRA integration — simplified from hydrophonedashboard."""

from __future__ import annotations

import os
from typing import Any

try:
    from atlassian import Jira
except ImportError:
    Jira = None


class JiraClient:
    def __init__(self) -> None:
        self.enabled = os.getenv("ENABLE_JIRA_INTEGRATION", "false").lower() == "true"
        self._client = None
        if not self.enabled or Jira is None:
            return
        url = os.getenv("JIRA_URL")
        pat = os.getenv("JIRA_PERSONAL_ACCESS_TOKEN")
        cloud = os.getenv("JIRA_CLOUD", "false").lower() == "true"
        if url and pat:
            self._client = Jira(url=url, token=pat, cloud=cloud)

    def search_for_site(self, site_code: str, site_name: str) -> list[dict[str, Any]]:
        if not self._client:
            return []
        projects = os.getenv("JIRA_PROJECT_KEYS", "INSTR,DATA,OPE")
        jql = (
            f'project in ({projects.replace(",", " ")}) '
            f'AND text ~ "{site_code}" ORDER BY updated DESC'
        )
        return self._search(jql)

    def search_for_device(self, device_id: int | str, device_code: str) -> list[dict[str, Any]]:
        if not self._client:
            return []
        projects = os.getenv("JIRA_PROJECT_KEYS", "INSTR,DATA,OPE")
        terms = " OR ".join(f'text ~ "{t}"' for t in [str(device_id), device_code] if t)
        jql = f"project in ({projects.replace(',', ' ')}) AND ({terms}) ORDER BY updated DESC"
        return self._search(jql)

    def _search(self, jql: str) -> list[dict[str, Any]]:
        max_results = int(os.getenv("JIRA_MAX_RESULTS", "10"))
        try:
            result = self._client.jql(jql, limit=max_results)
        except Exception:
            return []
        issues = result.get("issues") or []
        tickets = []
        for issue in issues:
            fields = issue.get("fields") or {}
            tickets.append(
                {
                    "key": issue.get("key"),
                    "summary": fields.get("summary"),
                    "status": (fields.get("status") or {}).get("name"),
                    "url": f"{os.getenv('JIRA_URL')}/browse/{issue.get('key')}",
                }
            )
        return tickets
