"""Bright Data SERP API client with 3-account rotation, Google dork query builder,
and Apify-compatible dataset output.
"""

import os
import time
import json
import random
import logging
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import requests

from src.config import (
    BRIGHTDATA_API_TOKEN_1,
    BRIGHTDATA_API_TOKEN_2,
    BRIGHTDATA_API_TOKEN_3,
    BRIGHTDATA_ZONE_1,
    BRIGHTDATA_ZONE_2,
    BRIGHTDATA_ZONE_3,
    BRIGHTDATA_TIMEOUT,
    BRIGHTDATA_STATE_FILE,
    MAX_QUERIES_PER_BATCH,
    MAX_PAGES_PER_QUERY,
)
from src.state_manager import atomic_write_json

logger = logging.getLogger(__name__)


class BrightDataError(Exception):
    """Base exception for Bright Data operations."""
    pass


class BrightDataAuthError(BrightDataError):
    """Raised when API token is missing, invalid, or unauthorized (HTTP 401)."""
    pass


class BrightDataPermissionError(BrightDataError):
    """Raised when access is forbidden or zone permissions/KYC fail (HTTP 403)."""
    pass


class BrightDataCreditExhaustedError(BrightDataError):
    """Raised when all Bright Data accounts have exhausted their monthly quota."""
    pass


class BrightDataRateLimitError(BrightDataError):
    """Raised when rate limit or concurrency caps are reached (HTTP 429)."""
    pass


class BrightDataTimeoutError(BrightDataError):
    """Raised when request times out repeatedly."""
    pass


class BrightDataClient:
    """
    Client for interacting with Bright Data SERP API with 3-account pool rotation.
    Provides complete drop-in compatibility with ApifyClient dataset output.
    """

    ENDPOINT = "https://api.brightdata.com/request"

    def __init__(
        self,
        tokens: Optional[List[Optional[str]]] = None,
        zones: Optional[List[str]] = None,
        state_file: Path = BRIGHTDATA_STATE_FILE,
        timeout: int = BRIGHTDATA_TIMEOUT,
        max_pages: int = MAX_PAGES_PER_QUERY,
        max_queries: int = MAX_QUERIES_PER_BATCH,
        sleep_func=None,
    ):
        self.state_file = Path(state_file)
        self.timeout = timeout
        self.max_pages = max_pages
        self.max_queries = max_queries
        self.sleep_func = sleep_func or time.sleep

        # Configure 3 accounts
        if tokens is not None:
            self.tokens = [t.strip() if t else None for t in tokens]
        else:
            self.tokens = [
                BRIGHTDATA_API_TOKEN_1.strip() if BRIGHTDATA_API_TOKEN_1 else None,
                BRIGHTDATA_API_TOKEN_2.strip() if BRIGHTDATA_API_TOKEN_2 else None,
                BRIGHTDATA_API_TOKEN_3.strip() if BRIGHTDATA_API_TOKEN_3 else None,
            ]

        if zones is not None:
            self.zones = zones
        else:
            self.zones = [BRIGHTDATA_ZONE_1, BRIGHTDATA_ZONE_2, BRIGHTDATA_ZONE_3]

        self.state = self.load_state()
        self._check_monthly_reset()

    # ---------------- State & Rotation Management ----------------

    def load_state(self) -> Dict[str, Any]:
        """Load account rotation state from JSON file or return initial state."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "active_account_index" in data:
                        return data
            except Exception as e:
                logger.warning(f"Could not read Bright Data state file ({e}). Initializing default state.")

        now_utc = datetime.now(timezone.utc)
        initial_state = {
            "active_account_index": 0,
            "current_billing_month": now_utc.strftime("%Y-%m"),
            "accounts": [
                {"index": i, "status": "ACTIVE", "exhausted_at": None, "last_used": None}
                for i in range(3)
            ],
        }
        return initial_state

    def save_state(self) -> None:
        """Persist state atomically."""
        try:
            atomic_write_json(self.state_file, self.state)
        except Exception as e:
            logger.error(f"Failed to persist Bright Data state: {e}")

    def _check_monthly_reset(self) -> None:
        """
        Check if the current UTC calendar month has transitioned.
        Bright Data monthly allowances reset on the 1st of each month (00:00 UTC).
        """
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")
        stored_month = self.state.get("current_billing_month")

        if stored_month != current_month:
            logger.info(
                f"New billing cycle detected ({stored_month} -> {current_month}). "
                f"Resetting all 3 Bright Data accounts to ACTIVE status."
            )
            self.state["current_billing_month"] = current_month
            self.state["active_account_index"] = 0
            for acc in self.state.get("accounts", []):
                acc["status"] = "ACTIVE"
                acc["exhausted_at"] = None
            self.save_state()

    def get_active_account(self) -> Tuple[int, Optional[str], str]:
        """
        Return (account_index, token, zone) for the currently active eligible account.
        Raises BrightDataCreditExhaustedError if all accounts are exhausted.
        Raises BrightDataAuthError if no tokens are configured.
        """
        # Ensure at least one token is configured across all accounts
        if not any(self.tokens):
            raise BrightDataAuthError(
                "No Bright Data API tokens configured. "
                "Please configure BRIGHTDATA_API_TOKEN_1, _2, or _3."
            )

        active_idx = self.state.get("active_account_index", 0)
        accounts = self.state.get("accounts", [])

        # Check if active account is valid and ACTIVE
        if 0 <= active_idx < len(self.tokens) and self.tokens[active_idx]:
            acc_status = accounts[active_idx].get("status", "ACTIVE") if active_idx < len(accounts) else "ACTIVE"
            if acc_status == "ACTIVE":
                return active_idx, self.tokens[active_idx], self.zones[active_idx]

        # Active account is not usable, find next eligible account
        for offset in range(1, 3):
            candidate_idx = (active_idx + offset) % 3
            if self.tokens[candidate_idx]:
                cand_status = accounts[candidate_idx].get("status", "ACTIVE") if candidate_idx < len(accounts) else "ACTIVE"
                if cand_status == "ACTIVE":
                    logger.info(f"Switching active Bright Data account to Account {candidate_idx + 1}")
                    self.state["active_account_index"] = candidate_idx
                    self.save_state()
                    return candidate_idx, self.tokens[candidate_idx], self.zones[candidate_idx]

        # No eligible accounts remaining in this billing month
        raise BrightDataCreditExhaustedError(
            "All configured Bright Data accounts have exhausted their monthly quota or are inactive."
        )

    def mark_account_exhausted(self, account_idx: int, reason: str = "quota_exhausted") -> Tuple[int, Optional[str], str]:
        """
        Mark the specified account as EXHAUSTED and rotate to the next available account.
        """
        now_str = datetime.now(timezone.utc).isoformat()
        accounts = self.state.get("accounts", [])
        if 0 <= account_idx < len(accounts):
            accounts[account_idx]["status"] = "EXHAUSTED"
            accounts[account_idx]["exhausted_at"] = now_str
            accounts[account_idx]["exhaustion_reason"] = reason

        logger.warning(
            f"Bright Data Account {account_idx + 1} marked EXHAUSTED ({reason}). "
            f"Rotating to next account..."
        )

        # Look for next eligible account
        for offset in range(1, 3):
            next_idx = (account_idx + offset) % 3
            if self.tokens[next_idx]:
                next_status = accounts[next_idx].get("status", "ACTIVE") if next_idx < len(accounts) else "ACTIVE"
                if next_status == "ACTIVE":
                    self.state["active_account_index"] = next_idx
                    self.save_state()
                    logger.info(f"Successfully rotated to Bright Data Account {next_idx + 1}")
                    return next_idx, self.tokens[next_idx], self.zones[next_idx]

        # All accounts exhausted
        self.save_state()
        raise BrightDataCreditExhaustedError(
            "All 3 Bright Data accounts have exhausted their monthly quota."
        )

    def mark_account_invalid_auth(self, account_idx: int, reason: str = "unauthorized") -> Tuple[int, Optional[str], str]:
        """Mark account as INVALID_AUTH and rotate to next valid account."""
        accounts = self.state.get("accounts", [])
        if 0 <= account_idx < len(accounts):
            accounts[account_idx]["status"] = "INVALID_AUTH"
            accounts[account_idx]["exhausted_at"] = datetime.now(timezone.utc).isoformat()
            accounts[account_idx]["exhaustion_reason"] = reason

        logger.error(
            f"Bright Data Account {account_idx + 1} has invalid/revoked credentials (HTTP 401). "
            f"Attempting rotation to next account..."
        )

        for offset in range(1, 3):
            next_idx = (account_idx + offset) % 3
            if self.tokens[next_idx]:
                next_status = accounts[next_idx].get("status", "ACTIVE") if next_idx < len(accounts) else "ACTIVE"
                if next_status == "ACTIVE":
                    self.state["active_account_index"] = next_idx
                    self.save_state()
                    logger.info(f"Rotated to Bright Data Account {next_idx + 1}")
                    return next_idx, self.tokens[next_idx], self.zones[next_idx]

        self.save_state()
        raise BrightDataAuthError(f"Bright Data authentication failed on all configured accounts: {reason}")

    # ---------------- URL & Query Construction ----------------

    def build_search_url(self, query: str, page: int = 0) -> str:
        """
        Construct Google search URL with location, language, 3-month date restriction,
        pagination offset, and parsed JSON request parameter.
        Page 0: start=0 (results 1-10)
        Page 1: start=10 (results 11-20)
        ...
        Page 19: start=190 (results 191-200)
        """
        encoded_query = urllib.parse.quote_plus(query)
        start_offset = page * 10
        # tbs=qdr:m3 restricts results to past 3 months
        # gl=in (India), hl=en (English)
        # brd_json=1 instructs Bright Data to parse Google SERP into structured JSON
        url = (
            f"https://www.google.com/search?q={encoded_query}"
            f"&gl=in&hl=en&tbs=qdr:m3&start={start_offset}&brd_json=1"
        )
        return url

    # ---------------- HTTP Request Dispatch ----------------

    def _execute_single_request(self, target_url: str) -> List[Dict[str, Any]]:
        """
        Execute a single SERP request against Bright Data API with bounded retries,
        jitter, rate-limit handling, and quota exhaustion rotation.
        Returns list of organic search items.
        """
        max_transient_retries = 3

        while True:
            account_idx, token, zone = self.get_active_account()

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            payload = {
                "zone": zone,
                "url": target_url,
                "format": "raw",
            }

            for attempt in range(max_transient_retries):
                try:
                    resp = requests.post(
                        self.ENDPOINT,
                        headers=headers,
                        json=payload,
                        timeout=self.timeout,
                    )

                    # 1. Check HTTP 401: Invalid Credentials
                    if resp.status_code == 401:
                        self.mark_account_invalid_auth(account_idx, resp.text[:200])
                        break  # Break retry loop to retry with next account

                    # 2. Check HTTP 402 or Quota Headers: Quota Exhausted
                    err_code = resp.headers.get("x-brd-err-code", "").lower()
                    if resp.status_code == 402 or "insufficient_funds" in err_code or "quota" in err_code:
                        self.mark_account_exhausted(account_idx, f"HTTP {resp.status_code}: {resp.text[:200]}")
                        break  # Break retry loop to retry with next account

                    # 3. Check HTTP 429: Concurrency / Rate limit (DO NOT ROTATE, RETRY WITH BACKOFF)
                    if resp.status_code == 429:
                        backoff = (2 ** attempt) + random.uniform(0.5, 1.5)
                        logger.warning(
                            f"Bright Data Account {account_idx + 1} rate limited (HTTP 429). "
                            f"Backing off for {backoff:.1f}s (Attempt {attempt + 1}/{max_transient_retries})..."
                        )
                        self.sleep_func(backoff)
                        continue

                    # 4. Check HTTP 5xx: Transient Server Error (DO NOT ROTATE, RETRY)
                    if 500 <= resp.status_code < 600:
                        backoff = (2 ** attempt) + random.uniform(0.5, 1.5)
                        logger.warning(
                            f"Bright Data server error (HTTP {resp.status_code}). "
                            f"Retrying in {backoff:.1f}s (Attempt {attempt + 1}/{max_transient_retries})..."
                        )
                        self.sleep_func(backoff)
                        continue

                    # 5. Check HTTP 403: Forbidden / KYC
                    if resp.status_code == 403:
                        logger.error(f"Bright Data Account {account_idx + 1} access forbidden (HTTP 403): {resp.text[:200]}")
                        raise BrightDataPermissionError(f"Bright Data Account {account_idx + 1} forbidden: {resp.text[:200]}")

                    # 6. Success: Parse JSON response
                    resp.raise_for_status()
                    try:
                        data = resp.json()
                    except json.JSONDecodeError as jde:
                        logger.warning(f"Malformed JSON from Bright Data: {jde}. Raw snippet: {resp.text[:100]}")
                        return []

                    if isinstance(data, dict):
                        # Standard parsed SERP JSON has top-level 'organic' array
                        organic_items = data.get("organic", [])
                        if isinstance(organic_items, list):
                            return organic_items
                    elif isinstance(data, list):
                        return data

                    return []

                except (requests.ConnectionError, requests.Timeout) as conn_err:
                    if attempt < max_transient_retries - 1:
                        backoff = (2 ** attempt) + random.uniform(0.5, 1.0)
                        logger.warning(
                            f"Transient connection glitch ({type(conn_err).__name__}). "
                            f"Retrying in {backoff:.1f}s..."
                        )
                        self.sleep_func(backoff)
                    else:
                        logger.error(f"Max retries reached on transient error: {conn_err}")
                        return []
            else:
                # If all transient retries exhausted without rotation break, return empty
                logger.error(f"Failed to fetch {target_url} after {max_transient_retries} attempts.")
                return []

    # ---------------- Batch Orchestration ----------------

    def run_search_batch(
        self,
        queries: List[str],
        max_pages: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute a batch of up to 10 queries, requesting up to `max_pages` per query.
        Returns a list of items mapped into the standard Apify-compatible format:
        [{"title": ..., "url": ..., "snippet": ..., "searchQuery": ...}, ...]

        Features:
        - Early stopping: stops querying further pages for a query if zero organic results returned.
        - Mid-batch recovery: preserves results across account rotations.
        """
        if not queries:
            logger.warning("run_search_batch called with empty queries list.")
            return []

        if len(queries) > self.max_queries:
            queries = queries[:self.max_queries]

        pages_to_fetch = max_pages if max_pages is not None else self.max_pages
        dataset_items: List[Dict[str, Any]] = []

        logger.info(
            f"Starting Bright Data SERP batch: {len(queries)} queries | "
            f"Up to {pages_to_fetch} pages per query | Active Account: {self.state.get('active_account_index', 0) + 1}"
        )

        for q_idx, query in enumerate(queries, start=1):
            query_items_count = 0
            logger.info(f"Processing Query {q_idx}/{len(queries)}: {query}")

            for page in range(pages_to_fetch):
                target_url = self.build_search_url(query, page=page)
                organic_results = self._execute_single_request(target_url)

                if not organic_results:
                    logger.info(f"Query {q_idx} page {page + 1}: 0 organic results. Early stopping further pages for this query.")
                    break

                for item in organic_results:
                    if not isinstance(item, dict):
                        continue
                    # Map into Apify-compatible schema: title, url, snippet
                    mapped = {
                        "title": item.get("title", ""),
                        "url": item.get("link") or item.get("url", ""),
                        "snippet": item.get("description") or item.get("snippet", ""),
                        "searchQuery": query,
                        "position": item.get("position"),
                        "page": page + 1,
                    }
                    dataset_items.append(mapped)
                    query_items_count += 1

                # If page had very few results (fewer than 2), Google typically has no deeper pages
                if len(organic_results) < 2:
                    logger.info(f"Query {q_idx} page {page + 1} had only {len(organic_results)} results. Halting pagination for this query.")
                    break

            logger.info(f"Query {q_idx} finished: {query_items_count} search results collected.")

        logger.info(f"Completed Bright Data SERP batch: {len(dataset_items)} total search items collected.")
        return dataset_items
