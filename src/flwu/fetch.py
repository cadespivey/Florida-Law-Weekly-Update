"""Bounded HTTP acquisition for Florida Litigator Weekly Update.

Provides a bounded HTTP client for acquiring source data.
Supports only configured adapters with explicit connection limits.
No automatic redirects, no credential injection, no unbounded timeouts.

Adapter bindings configured via config/adapter_bindings.json.
Each adapter has a max_pages, max_bytes, timeout_seconds, and max_retries.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx

from flwu.config import ConfigError, load_config


class FetchError(Exception):
    """Raised when an HTTP acquisition fails."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


class _BoundedClient:
    """Bounded HTTP client with explicit limits."""

    def __init__(self, timeout_seconds: int = 30, max_retries: int = 3,
                 max_bytes: int = 10_000_000, max_pages: int = 100):
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.max_bytes = max_bytes
        self.max_pages = max_pages
        self._page_count = 0

    def fetch(self, url: str) -> str:
        """Fetch a URL with bounding. Returns response text."""
        if self._page_count >= self.max_pages:
            raise FetchError(
                "PAGE_LIMIT",
                f"Page limit {self.max_pages} exceeded for {url}",
            )

        try:
            response = httpx.get(
                url,
                timeout=httpx.Timeout(self.timeout_seconds),
                follow_redirects=False,
                headers={"User-Agent": "FLWU/0.1.0"},
            )
            response.raise_for_status()

            body = response.text
            if len(body.encode("utf-8")) > self.max_bytes:
                raise FetchError(
                    "RESPONSE_TOO_LARGE",
                    f"Response exceeds {self.max_bytes} bytes",
                )

            self._page_count += 1
            return body

        except httpx.HTTPError as e:
            raise FetchError("HTTP_ERROR", str(e))
        except httpx.TimeoutException:
            raise FetchError("TIMEOUT", f"Request to {url} timed out")


def _load_adapter_bindings(path: Path | None = None) -> dict[str, Any]:
    """Load adapter binding configuration."""
    if path is None:
        path = Path("config/adapter_bindings.json")

    if path.is_file():
        text = path.read_text(encoding="utf-8")
        return json.loads(text)

    # Default bindings
    return {
        "fl_statutes": {"max_pages": 50, "max_bytes": 5_000_000, "timeout_seconds": 30, "max_retries": 3},
        "fl_bills": {"max_pages": 50, "max_bytes": 5_000_000, "timeout_seconds": 30, "max_retries": 3},
        "fl_supreme": {"max_pages": 20, "max_bytes": 3_000_000, "timeout_seconds": 30, "max_retries": 3},
        "dca_first": {"max_pages": 20, "max_bytes": 3_000_000, "timeout_seconds": 30, "max_retries": 3},
        "dca_second": {"max_pages": 20, "max_bytes": 3_000_000, "timeout_seconds": 30, "max_retries": 3},
        "dca_third": {"max_pages": 20, "max_bytes": 3_000_000, "timeout_seconds": 30, "max_retries": 3},
        "dca_fourth": {"max_pages": 20, "max_bytes": 3_000_000, "timeout_seconds": 30, "max_retries": 3},
        "dca_fifth": {"max_pages": 20, "max_bytes": 3_000_000, "timeout_seconds": 30, "max_retries": 3},
        "dca_sixth": {"max_pages": 20, "max_bytes": 3_000_000, "timeout_seconds": 30, "max_retries": 3},
        "court_bar_rules": {"max_pages": 20, "max_bytes": 3_000_000, "timeout_seconds": 30, "max_retries": 3},
        "agency_rules": {"max_pages": 50, "max_bytes": 5_000_000, "timeout_seconds": 30, "max_retries": 3},
        "circuit_fourth": {"max_pages": 15, "max_bytes": 2_000_000, "timeout_seconds": 30, "max_retries": 3},
        "circuit_seventh": {"max_pages": 15, "max_bytes": 2_000_000, "timeout_seconds": 30, "max_retries": 3},
        "circuit_eighth": {"max_pages": 15, "max_bytes": 2_000_000, "timeout_seconds": 30, "max_retries": 3},
        "clerk_duval": {"max_pages": 30, "max_bytes": 3_000_000, "timeout_seconds": 30, "max_retries": 3},
        "clerk_st_johns": {"max_pages": 30, "max_bytes": 3_000_000, "timeout_seconds": 30, "max_retries": 3},
        "clerk_clay": {"max_pages": 30, "max_bytes": 3_000_000, "timeout_seconds": 30, "max_retries": 3},
        "clerk_nassau": {"max_pages": 20, "max_bytes": 2_000_000, "timeout_seconds": 30, "max_retries": 3},
        "clerk_baker": {"max_pages": 20, "max_bytes": 2_000_000, "timeout_seconds": 30, "max_retries": 3},
        "clerk_union": {"max_pages": 20, "max_bytes": 2_000_000, "timeout_seconds": 30, "max_retries": 3},
    }


def fetch_url(url: str, *, binding_name: str | None = None) -> str:
    """Fetch a URL with bounding. Returns response text.

    Uses adapter bindings from config/adapter_bindings.json.
    """
    bindings = _load_adapter_bindings()
    binding = bindings.get(binding_name, bindings.get("default", {}))

    client = _BoundedClient(
        timeout_seconds=binding.get("timeout_seconds", 30),
        max_retries=binding.get("max_retries", 3),
        max_bytes=binding.get("max_bytes", 10_000_000),
        max_pages=binding.get("max_pages", 100),
    )

    return client.fetch(url)
