"""GPT Researcher retriever plugin backed by looot (https://looot.ai)."""

import logging
import os
import time
import uuid

import requests

from gpt_researcher.retrievers.base import BaseRetriever

__all__ = ["LoootSearch"]

logger = logging.getLogger(__name__)

DEFAULT_API_BASE = "https://api.looot.ai"
ENDPOINT_ID = "serper-search"
TERMINAL_STATUSES = {"completed", "failed", "blocked", "stopped"}
WAIT_SECONDS = 30  # server-side wait on the POST
POLL_INTERVAL = 1.0
POLL_DEADLINE = 60.0  # total seconds from the first request
REQUEST_TIMEOUT = 40  # must exceed WAIT_SECONDS


class LoootSearch(BaseRetriever):
    """Web search through looot's `serper-search` endpoint."""

    requires_scraping = True

    def __init__(self, query, query_domains=None):
        self.query = query
        self.query_domains = query_domains or []
        token = os.environ.get("LOOOT_TOKEN")
        if not token:
            raise Exception(
                "looot token not found. Set the LOOOT_TOKEN environment variable. "
                "Get one at https://looot.ai"
            )
        self.token = token
        self.api_base = os.environ.get("LOOOT_API_BASE", DEFAULT_API_BASE).rstrip("/")

    def _build_query(self):
        query = self.query
        if self.query_domains:
            query += " site:" + " OR site:".join(self.query_domains)
        return query

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def _poll(self, run_id, deadline):
        url = f"{self.api_base}/v1/runs/{run_id}"
        while time.monotonic() < deadline:
            time.sleep(POLL_INTERVAL)
            resp = requests.get(url, headers=self._headers(), timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            run = resp.json()
            if run.get("status") in TERMINAL_STATUSES:
                return run
        return None

    def search(self, max_results=7):
        """Return [{"href": url, "body": snippet}, ...]; [] on any failure."""
        try:
            deadline = time.monotonic() + POLL_DEADLINE
            resp = requests.post(
                f"{self.api_base}/v1/runs",
                params={"wait": WAIT_SECONDS},
                headers=self._headers(),
                json={
                    "endpointId": ENDPOINT_ID,
                    "input": {"q": self._build_query(), "num": max_results},
                    "idempotencyKey": str(uuid.uuid4()),
                },
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            run = resp.json()
            if run.get("status") not in TERMINAL_STATUSES:
                run = self._poll(run.get("runId"), deadline) if run.get("runId") else None
                if run is None:
                    logger.warning("looot search did not finish before the deadline")
                    return []
            if run.get("status") != "completed":
                error = run.get("error") or {}
                logger.warning(
                    "looot search %s: %s %s",
                    run.get("status"), error.get("code", ""), error.get("message", ""),
                )
                return []
            organic = (run.get("result") or {}).get("organic") or []
        except (requests.RequestException, ValueError, AttributeError, TypeError) as exc:
            logger.warning("looot search failed: %s", exc)
            return []
        return [
            {"href": item["link"], "body": item.get("snippet") or ""}
            for item in organic
            if isinstance(item, dict) and item.get("link")
        ]
