"""Email verification client for Mail7 Bulk API with caching, rate-limit backoff, and quota protection."""

import time
import random
import logging
import requests
from typing import List, Dict, Tuple, Optional, Any
from src.state_manager import get_today_ist_date
from src.outreach.config import (
    MAIL7_API_KEY,
    MAIL7_BULK_ENDPOINT,
    MAX_VERIFICATIONS_PER_ACCOUNT_PER_DAY,
)
from src.outreach.quota_ledger import QuotaLedger

logger = logging.getLogger(__name__)


class VerificationResult:
    """Standardized verification result object."""
    def __init__(
        self,
        email: str,
        status: str,  # 'valid', 'invalid', 'unknown', 'verification_error'
        account_id: str = "mail7",
        reason: Optional[str] = None,
        disposable: bool = False,
        accept_all: bool = False,
        raw_response: Optional[Dict[str, Any]] = None,
    ):
        self.email = email.strip().lower()
        self.status = status.lower()
        self.account_id = account_id
        self.reason = reason or ""
        self.disposable = disposable
        self.accept_all = accept_all
        self.raw_response = raw_response or {}

    @property
    def is_deliverable(self) -> bool:
        """Strict policy: only 'valid' is eligible for outreach; unknown, invalid, risky are non-deliverable."""
        return self.status == "valid" and not self.disposable and not self.accept_all

    def to_dict(self) -> Dict[str, Any]:
        return {
            "email": self.email,
            "status": self.status,
            "account_id": self.account_id,
            "reason": self.reason,
            "is_deliverable": self.is_deliverable,
            "disposable": self.disposable,
        }


class Mail7Verifier:
    """Client for validating emails in ONE bulk request via the Mail7 REST API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        ledger: Optional[QuotaLedger] = None,
        dry_run: bool = False,
        sleep_func=None,
        random_func=None,
    ):
        self.api_key = api_key or MAIL7_API_KEY
        self.endpoint = endpoint or MAIL7_BULK_ENDPOINT
        self.ledger = ledger or QuotaLedger()
        self.dry_run = dry_run
        self.sleep_func = sleep_func or time.sleep
        self.random_func = random_func or random.uniform

    def verify_bulk(
        self,
        emails: List[str],
        date_str: Optional[str] = None,
        max_retries: int = 3,
    ) -> Tuple[List[VerificationResult], Optional[str]]:
        """
        Verify all unique emails using existing cache where available, and submitting ALL
        unresolved emails in ONE Mail7 bulk request.
        Returns (results: List[VerificationResult], error_reason: Optional[str]).
        """
        if not date_str:
            date_str = get_today_ist_date()

        # Deduplicate while preserving order
        ordered_unique: List[str] = []
        seen = set()
        for e in emails:
            norm_e = e.strip().lower()
            if norm_e and norm_e not in seen:
                ordered_unique.append(norm_e)
                seen.add(norm_e)

        results_by_email: Dict[str, VerificationResult] = {}
        unresolved_emails: List[str] = []

        # 1. Check cache for definitive outcomes
        for email in ordered_unique:
            cached = self.ledger.get_cached_result(email)
            if cached and cached.get("status") in ("valid", "invalid", "unknown"):
                results_by_email[email] = VerificationResult(
                    email=email,
                    status=cached.get("status", "unknown"),
                    account_id="cache",
                    reason="cached_result",
                )
            else:
                unresolved_emails.append(email)

        logger.info(
            f"Mail7 Bulk Verification: {len(ordered_unique)} total -> "
            f"{len(results_by_email)} cached, {len(unresolved_emails)} unresolved to submit"
        )

        if not unresolved_emails:
            logger.info("All submitted addresses resolved from cache. Zero API calls needed.")
            return [results_by_email[e] for e in ordered_unique], None

        # 2. Dry-run mode simulation
        if self.dry_run:
            logger.info(f"[DRY RUN] Simulating Mail7 bulk validation for {len(unresolved_emails)} emails in ONE call.")
            for email in unresolved_emails:
                results_by_email[email] = VerificationResult(
                    email=email,
                    status="valid",
                    account_id="mail7_simulated",
                    reason="simulated_valid",
                    raw_response={"status": "Valid", "valid": True},
                )
            return [results_by_email[e] for e in ordered_unique], None

        # 3. Guard against missing API key
        if not self.api_key or not self.api_key.strip():
            logger.error("MAIL7_API_KEY secret is not set or empty. Verification paused.")
            for email in unresolved_emails:
                results_by_email[email] = VerificationResult(
                    email=email,
                    status="verification_error",
                    account_id="none",
                    reason="missing_api_key",
                )
            return [results_by_email[e] for e in ordered_unique], "missing_api_key"

        # 4. Prepare multipart form data payload with newline-separated emails
        email_payload = "\n".join(unresolved_emails)
        files = {"emails": (None, email_payload)}
        headers = {"X-API-Key": self.api_key.strip()}

        bulk_data: Optional[Dict[str, Any]] = None
        last_error_reason: Optional[str] = None

        for attempt in range(max_retries):
            try:
                logger.info(
                    f"Posting ONE bulk request with {len(unresolved_emails)} emails to {self.endpoint} "
                    f"(attempt {attempt + 1}/{max_retries})..."
                )
                resp = requests.post(self.endpoint, files=files, headers=headers, timeout=(10, 60))

                if resp.status_code == 401:
                    logger.error("Mail7 returned HTTP 401 Unauthorized: Invalid API key.")
                    last_error_reason = "unauthorized_api_key"
                    break

                if resp.status_code == 403:
                    body_text = resp.text.lower()
                    if any(term in body_text for term in ("quota", "credit", "limit", "exhausted", "payment")):
                        logger.warning("Mail7 returned HTTP 403: Monthly verification quota exhausted.")
                        last_error_reason = "quota_exhausted"
                    else:
                        logger.error("Mail7 returned HTTP 403 Forbidden: API key unauthorized or plan restricted.")
                        last_error_reason = "unauthorized_api_key"
                    break

                if resp.status_code == 402:
                    logger.warning("Mail7 returned HTTP 402 Payment Required: Monthly credit limit exhausted.")
                    last_error_reason = "quota_exhausted"
                    break

                if resp.status_code == 429:
                    retry_header = resp.headers.get("Retry-After", "3")
                    try:
                        retry_after = int(retry_header)
                    except ValueError:
                        retry_after = 3
                    logger.warning(f"Mail7 returned HTTP 429 Too Many Requests. Retrying after {retry_after}s...")
                    last_error_reason = "rate_limited"
                    if attempt < max_retries - 1:
                        jitter = self.random_func(0.5, 1.5)
                        self.sleep_func(retry_after + jitter)
                        continue
                    break

                if resp.status_code == 400:
                    logger.error(f"Mail7 returned HTTP 400 Bad Request: {resp.text[:200]}")
                    last_error_reason = "bad_request"
                    break

                if resp.status_code in (500, 502, 503, 504):
                    logger.warning(f"Mail7 server error HTTP {resp.status_code} (attempt {attempt + 1}/{max_retries})")
                    last_error_reason = f"provider_server_error_{resp.status_code}"
                    if attempt < max_retries - 1:
                        backoff = (2 ** attempt) + self.random_func(0.5, 1.5)
                        self.sleep_func(backoff)
                        continue
                    break

                resp.raise_for_status()
                bulk_data = resp.json()
                break

            except (requests.Timeout, requests.ConnectionError) as e:
                logger.warning(f"Network error communicating with Mail7 (attempt {attempt + 1}/{max_retries}): {e}")
                last_error_reason = f"network_error: {type(e).__name__}"
                if attempt < max_retries - 1:
                    backoff = (2 ** attempt) + self.random_func(0.5, 1.5)
                    self.sleep_func(backoff)
                    continue
                break
            except Exception as e:
                logger.error(f"Unexpected exception during Mail7 verification: {e}")
                last_error_reason = f"unexpected_exception: {type(e).__name__}"
                break

        # If HTTP call failed permanently
        if bulk_data is None:
            for email in unresolved_emails:
                results_by_email[email] = VerificationResult(
                    email=email,
                    status="verification_error",
                    account_id="mail7",
                    reason=last_error_reason or "unknown_http_failure",
                )
            return [results_by_email[e] for e in ordered_unique], last_error_reason

        # 5. Parse, map, and reconcile per-email results
        raw_results = bulk_data.get("results")
        if not isinstance(raw_results, list):
            logger.error(f"Mail7 bulk response missing 'results' list: {bulk_data}")
            for email in unresolved_emails:
                results_by_email[email] = VerificationResult(
                    email=email,
                    status="verification_error",
                    account_id="mail7",
                    reason="malformed_bulk_response",
                )
            return [results_by_email[e] for e in ordered_unique], "malformed_bulk_response"

        # Index returned results by normalized email
        returned_map: Dict[str, Dict[str, Any]] = {}
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            ret_e = str(item.get("email", "")).strip().lower()
            if ret_e and ret_e not in returned_map:
                returned_map[ret_e] = item

        cache_records_to_save: List[Dict[str, str]] = []
        valid_count = 0
        invalid_count = 0

        for email in unresolved_emails:
            norm_e = email.strip().lower()
            if norm_e in returned_map:
                item = returned_map[norm_e]
                raw_st = str(item.get("status", "")).strip().lower()
                raw_valid = item.get("valid")
                details = str(item.get("details", "") or item.get("error", "") or "")

                # Status mapping per Mail7 specification:
                # 'Valid' -> deliverable valid
                # 'Not Valid' -> confirmed invalid
                # 'Unknown' -> uncertain, non-deliverable, free
                if raw_st == "valid" or (raw_valid is True and raw_st != "not valid"):
                    status = "valid"
                    valid_count += 1
                elif raw_st in ("not valid", "not_valid", "invalid") or raw_valid is False:
                    status = "invalid"
                    invalid_count += 1
                elif raw_st == "unknown" or raw_valid is None:
                    status = "unknown"
                else:
                    status = "verification_error"
                    details = f"unrecognized_status: {item.get('status')}"

                vr = VerificationResult(
                    email=email,
                    status=status,
                    account_id="mail7",
                    reason=details,
                    disposable=bool(item.get("is_disposable")),
                    raw_response=item,
                )
                results_by_email[email] = vr

                # Persist definitive outcomes to cache (never cache transient errors)
                if vr.status in ("valid", "invalid", "unknown"):
                    cache_records_to_save.append({
                        "email": email,
                        "account_id": "mail7",
                        "status": vr.status,
                        "date_verified": date_str,
                        "raw_result": details,
                    })
            else:
                # Omitted or missing from bulk response -> verification error requiring review
                logger.warning(f"Address {email} missing from Mail7 bulk response.")
                vr = VerificationResult(
                    email=email,
                    status="verification_error",
                    account_id="mail7",
                    reason="missing_from_bulk_response",
                )
                results_by_email[email] = vr

        # Save definitive cache records
        if cache_records_to_save and not self.dry_run:
            self.ledger.cache_verification_results(cache_records_to_save)

        # Record monthly quota usage: only Valid and Not Valid count against quota
        billable_count = valid_count + invalid_count
        if billable_count > 0 and not self.dry_run:
            self.ledger.record_usage("mail7", billable_count, date_str)

        return [results_by_email[e] for e in ordered_unique], None


class QuickEmailVerifier(Mail7Verifier):
    """
    Backward-compatibility alias wrapping Mail7Verifier.
    Guarantees existing references or imports function seamlessly while routing
    all verifications through Mail7 in ONE bulk request.
    """

    def __init__(self, *args, **kwargs):
        api_key = kwargs.pop("api_key", None) or kwargs.pop("key_1", None) or MAIL7_API_KEY
        kwargs.pop("key_2", None)
        super().__init__(api_key=api_key, **kwargs)

    def plan_and_partition(self, unique_emails: List[str], date_str: Optional[str] = None):
        """Deprecated partition: in Mail7, all emails are verified in one bulk request."""
        return unique_emails, [], 0

    def verify_batches(self, batch_a: List[str], batch_b: List[str], date_str: Optional[str] = None):
        """Deprecated batch verification: merges and verifies in ONE bulk request."""
        all_emails = list(dict.fromkeys(batch_a + batch_b))
        results, _ = self.verify_bulk(all_emails, date_str=date_str)
        return results

    def verify_single_email(self, email: str, api_key: str, account_id: str, max_retries: int = 2) -> VerificationResult:
        """Fallback single verification wrapper using bulk endpoint with 1 email."""
        results, _ = self.verify_bulk([email])
        return results[0] if results else VerificationResult(email=email, status="verification_error", reason="empty_result")
