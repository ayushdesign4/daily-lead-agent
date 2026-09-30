"""Apify API client for running Google Search Scraper actor with credit and error handling."""

import time
import logging
import requests
from typing import List, Dict, Any, Optional

from src.config import (
    APIFY_API_TOKEN,
    APIFY_ACTOR_ID,
    MAX_PAGES_PER_QUERY,
    MAX_QUERIES_PER_BATCH,
)

logger = logging.getLogger(__name__)


class ApifyError(Exception):
    """Base exception for Apify client operations."""
    pass


class ApifyAuthError(ApifyError):
    """Raised when APIFY_API_TOKEN is missing, invalid, or unauthorized (HTTP 401)."""
    pass


class ApifyCreditExhaustedError(ApifyError):
    """Raised when Apify credits, monthly usage, compute units, or quota limits are exceeded."""
    pass


class ApifyTimeoutError(ApifyError):
    """Raised when an Apify actor run exceeds the configured polling timeout."""
    pass


class ApifyClient:
    """Client for interacting with Apify API and Google Search Scraper Actor."""

    BASE_URL = "https://api.apify.com/v2"

    def __init__(
        self,
        token: Optional[str] = None,
        actor_id: str = APIFY_ACTOR_ID,
    ):
        self.token = token or APIFY_API_TOKEN
        self.actor_id = actor_id
        # Convert 'apify/google-search-scraper' to 'apify~google-search-scraper' if needed for REST URL
        self.actor_url_id = self.actor_id.replace("/", "~")

    def _get_headers(self) -> Dict[str, str]:
        if not self.token:
            raise ApifyAuthError("APIFY_API_TOKEN is not configured or is empty.")
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def check_account_status(self) -> Dict[str, Any]:
        """
        Check user account information and usage limits before launching batches.
        Raises ApifyAuthError or ApifyCreditExhaustedError if account is unusable.
        """
        if not self.token:
            raise ApifyAuthError("APIFY_API_TOKEN is not configured.")

        url = f"{self.BASE_URL}/users/me"
        try:
            resp = requests.get(url, headers=self._get_headers(), timeout=20)
            if resp.status_code == 401:
                raise ApifyAuthError(f"Apify authentication failed (HTTP 401): {resp.text}")
            if resp.status_code in (402, 429):
                raise ApifyCreditExhaustedError(f"Apify account credits/limits exhausted (HTTP {resp.status_code}): {resp.text}")
            resp.raise_for_status()
            data = resp.json().get("data", {})

            # Check limits / usage if available in user object
            limits = data.get("limits", {})
            if limits.get("isOverLimit") is True:
                raise ApifyCreditExhaustedError("Apify account has exceeded usage limit (isOverLimit=True).")

            return data
        except requests.RequestException as e:
            if hasattr(e, "response") and e.response is not None:
                if e.response.status_code == 401:
                    raise ApifyAuthError(f"Apify authentication failed: {e.response.text}") from e
                if e.response.status_code in (402, 403, 429):
                    raise ApifyCreditExhaustedError(f"Apify credits/usage limit exceeded: {e.response.text}") from e
            logger.warning(f"Could not check account status due to connection issue: {e}")
            return {}

    def build_actor_input(self, queries: List[str]) -> Dict[str, Any]:
        """
        Build input payload according to specifications:
        - Max 10 queries
        - Max 30 pages per query
        - Country: India ('in')
        - Language: English ('en')
        - Date restriction: last 3 months ('qdr:m3')
        - Mobile results: OFF
        - Enrichment / paid / html: OFF
        """
        if len(queries) > MAX_QUERIES_PER_BATCH:
            queries = queries[:MAX_QUERIES_PER_BATCH]

        # Join queries newline-delimited or as array depending on actor version
        queries_text = "\n".join(queries)

        actor_input = {
            "queries": queries_text,
            "maxPagesPerQuery": MAX_PAGES_PER_QUERY,
            "countryCode": "in",
            "languageCode": "en",
            "mobileResults": False,
            "includeUnfilteredResults": False,
            "saveHtml": False,
            "saveHtmlToKeyValueStore": False,
            # Supported Google Search date parameter for past 3 months
            "tbs": "qdr:m3",
            "customParameters": "tbs=qdr:m3",
        }
        return actor_input

    def run_search_batch(
        self,
        queries: List[str],
        max_wait_seconds: int = 600,
        poll_interval: int = 15,
    ) -> List[Dict[str, Any]]:
        """
        Trigger an Apify search batch with up to 10 queries.
        Monitors run progress until complete and returns dataset items.
        Handles credit exhaustion and rate limits without indefinite retries.
        """
        if not queries:
            logger.warning("run_search_batch called with empty queries list.")
            return []

        # Check account status before calling
        self.check_account_status()

        actor_input = self.build_actor_input(queries)
        start_run_url = f"{self.BASE_URL}/acts/{self.actor_url_id}/runs"

        logger.info(f"Triggering Apify Actor {self.actor_id} with {len(queries)} queries...")
        try:
            resp = requests.post(
                start_run_url,
                headers=self._get_headers(),
                json=actor_input,
                timeout=30,
            )
            if resp.status_code == 401:
                raise ApifyAuthError(f"Apify authentication failed: {resp.text}")
            if resp.status_code in (402, 403, 429):
                raise ApifyCreditExhaustedError(
                    f"Apify credits/usage limit reached on run start (HTTP {resp.status_code}): {resp.text}"
                )
            resp.raise_for_status()
            run_data = resp.json().get("data", {})
        except requests.RequestException as e:
            if hasattr(e, "response") and e.response is not None:
                if e.response.status_code == 401:
                    raise ApifyAuthError(f"Apify authentication failed: {e.response.text}") from e
                if e.response.status_code in (402, 403, 429):
                    raise ApifyCreditExhaustedError(f"Apify credit limit reached: {e.response.text}") from e
            raise ApifyError(f"Failed to start Apify actor run: {e}") from e

        run_id = run_data.get("id")
        default_dataset_id = run_data.get("defaultDatasetId")
        logger.info(f"Apify run started. Run ID: {run_id}, Dataset ID: {default_dataset_id}")

        # Poll run status
        poll_url = f"{self.BASE_URL}/actor-runs/{run_id}"
        elapsed = 0
        run_succeeded = False
        last_status = "UNKNOWN"

        while elapsed < max_wait_seconds:
            time.sleep(poll_interval)
            elapsed += poll_interval

            try:
                poll_resp = requests.get(poll_url, headers=self._get_headers(), timeout=20)
                if poll_resp.status_code == 401:
                    raise ApifyAuthError(f"Apify authentication failed while polling: {poll_resp.text}")
                if poll_resp.status_code in (402, 403, 429):
                    raise ApifyCreditExhaustedError(f"Apify credit limit exceeded while polling: {poll_resp.text}")
                poll_resp.raise_for_status()
                current_run = poll_resp.json().get("data", {})
                status = current_run.get("status")
                last_status = status
                status_message = current_run.get("statusMessage", "").lower()

                logger.info(f"Apify run {run_id} status: {status} ({elapsed}s elapsed)")

                if status == "SUCCEEDED":
                    run_succeeded = True
                    break
                elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
                    # Check if failure was caused by credits or compute limits
                    credit_keywords = ["credit", "compute unit", "quota", "usage limit", "monthly limit", "payment"]
                    if any(kw in status_message for kw in credit_keywords):
                        raise ApifyCreditExhaustedError(
                            f"Apify run {run_id} failed due to credit exhaustion: {status_message}"
                        )
                    if status == "TIMED-OUT":
                        raise ApifyTimeoutError(f"Apify actor run {run_id} timed out on Apify platform: {status_message}")
                    raise ApifyError(f"Apify run {run_id} finished with status {status}: {status_message}")

            except (ApifyAuthError, ApifyCreditExhaustedError, ApifyTimeoutError):
                raise
            except requests.RequestException as e:
                logger.warning(f"Transient error polling Apify run status: {e}")

        if not run_succeeded:
            logger.error(
                f"Apify actor run {run_id} did not finish within {max_wait_seconds}s timeout (last status: {last_status})."
            )
            raise ApifyTimeoutError(
                f"Apify run {run_id} timed out after {elapsed}s without completing successfully (last status: {last_status})."
            )

        # Fetch items from dataset ONLY when run succeeded
        return self.fetch_dataset_items(default_dataset_id)

    def fetch_dataset_items(self, dataset_id: str) -> List[Dict[str, Any]]:
        """Fetch all items from the Apify dataset."""
        if not dataset_id:
            return []

        dataset_url = f"{self.BASE_URL}/datasets/{dataset_id}/items"
        params = {"format": "json", "clean": "true"}

        try:
            resp = requests.get(dataset_url, headers=self._get_headers(), params=params, timeout=60)
            if resp.status_code == 401:
                raise ApifyAuthError(f"Apify authentication failed: {resp.text}")
            if resp.status_code in (402, 403, 429):
                raise ApifyCreditExhaustedError(f"Apify credit limit reached: {resp.text}")
            resp.raise_for_status()
            items = resp.json()
            logger.info(f"Fetched {len(items)} items from Apify dataset {dataset_id}")
            return items
        except (ApifyAuthError, ApifyCreditExhaustedError):
            raise
        except requests.RequestException as e:
            raise ApifyError(f"Failed to fetch Apify dataset items: {e}") from e
