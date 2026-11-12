"""Email verification client for Mail7 Bulk API with 7-account pool rotation, caching, and rate-limit backoff."""

import time
import random
import logging
import requests
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any, Union
from src.state_manager import get_today_ist_date
from src.outreach.config import (
    MAIL7_API_KEYS,
    MAIL7_API_KEY,
    MAIL7_BULK_ENDPOINT,
    MAIL7_POOL_STATE_FILE,
)
from src.outreach.quota_ledger import QuotaLedger
from src.outreach.mail7_pool import Mail7AccountPool, Mail7Account

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
    """Client for validating emails via Mail7 Bulk API with 7-account sequential rotation."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        keys: Optional[List[Optional[str]]] = None,
        pool: Optional[Mail7AccountPool] = None,
        state_file: Optional[Union[Path, str]] = None,
        endpoint: Optional[str] = None,
        ledger: Optional[QuotaLedger] = None,
        dry_run: bool = False,
        sleep_func=None,
        random_func=None,
        chunk_size: int = 35,
        pacing_delay: float = 3.0,
    ):
        self.endpoint = endpoint or MAIL7_BULK_ENDPOINT
        self.ledger = ledger or QuotaLedger()
        self.dry_run = dry_run
        self.sleep_func = sleep_func or time.sleep
        self.random_func = random_func or random.uniform
        self.chunk_size = chunk_size
        self.pacing_delay = pacing_delay

        if pool is not None:
            self.pool = pool
        elif keys is not None:
            self.pool = Mail7AccountPool(keys=keys, state_file=state_file)
        elif api_key:
            # Single key override (backward compatibility with legacy callers/tests)
            self.pool = Mail7AccountPool(keys=[api_key], state_file=state_file)
        else:
            # Default 7-account pool from environment
            self.pool = Mail7AccountPool(keys=MAIL7_API_KEYS, state_file=state_file or MAIL7_POOL_STATE_FILE)

    @property
    def api_key(self) -> Optional[str]:
        """Backward-compatible property returning the active account's API key."""
        acc = self.pool.get_active_account()
        return acc.api_key if acc else None

    def verify_bulk(
        self,
        emails: List[str],
        date_str: Optional[str] = None,
        max_retries: int = 3,
    ) -> Tuple[List[VerificationResult], Optional[str]]:
        """
        Verify all unique emails using existing cache where available, and submitting
        unresolved emails to the Mail7 Bulk API using the persistent 7-account pool.
        Rotates to next available account on confirmed quota exhaustion (HTTP 402/403).
        Returns (results: List[VerificationResult], error_reason: Optional[str]).
        """
        if not date_str:
            date_str = get_today_ist_date()

        # Check for monthly cycle reset
        self.pool.reset_monthly_cycle_if_needed(today_ist_date=date_str)

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

        # 3. Perform resilient bulk verification across the 7-account pool in paced chunks
        final_error_reason: Optional[str] = None
        billable_by_account: Dict[str, int] = {}
        chunk_size = self.chunk_size
        num_chunks = (len(unresolved_emails) + chunk_size - 1) // chunk_size

        for chunk_idx in range(num_chunks):
            chunk_slice = unresolved_emails[chunk_idx * chunk_size : (chunk_idx + 1) * chunk_size]
            current_chunk = [
                e for e in chunk_slice
                if e not in results_by_email or results_by_email[e].status == "verification_error"
            ]
            if not current_chunk:
                continue

            logger.info(f"Processing Mail7 chunk {chunk_idx + 1}/{num_chunks} ({len(current_chunk)} emails)...")

            chunk_resolved = False
            while not chunk_resolved:
                active_account = self.pool.get_active_account()

                if not active_account or not active_account.is_configured:
                    if self.pool.is_all_exhausted():
                        logger.error("All 7 Mail7 accounts in pool are exhausted for this monthly cycle.")
                        final_error_reason = "quota_exhausted"
                    elif any(self.pool.state.get("auth_failed_accounts", [])):
                        logger.error("Active Mail7 account failed authentication. Halting to alert user.")
                        final_error_reason = "unauthorized_api_key"
                    else:
                        logger.error("No valid Mail7 API keys configured in pool.")
                        final_error_reason = "missing_api_key"

                    for email in current_chunk:
                        results_by_email[email] = VerificationResult(
                            email=email,
                            status="verification_error",
                            account_id="mail7_pool",
                            reason=final_error_reason,
                        )
                    chunk_resolved = True
                    break

                logger.info(
                    f"Submitting chunk of {len(current_chunk)} emails to Mail7 using "
                    f"Account {active_account.index} ({active_account.account_id})..."
                )

                verified_chunk_map, chunk_err = self._verify_chunk_with_bisection(
                    chunk_emails=current_chunk,
                    api_key=active_account.api_key,
                    account_id=active_account.account_id,
                    date_str=date_str,
                    max_retries=max_retries,
                )

                # Check for quota exhaustion: rotate to next available account
                if chunk_err == "quota_exhausted":
                    logger.warning(
                        f"Mail7 confirmed quota exhaustion on Account {active_account.index}. "
                        "Rotating to next available account in pool..."
                    )
                    # Preserve any definitively resolved emails from this chunk
                    chunk_cache_records = []
                    for em, vr in verified_chunk_map.items():
                        if vr.status in ("valid", "invalid", "unknown"):
                            results_by_email[em] = vr
                            chunk_cache_records.append({
                                "email": vr.email,
                                "account_id": vr.account_id,
                                "status": vr.status,
                                "date_verified": date_str,
                                "raw_result": vr.reason,
                            })
                    if chunk_cache_records and not self.dry_run:
                        self.ledger.cache_verification_results(chunk_cache_records)

                    next_account = self.pool.mark_account_exhausted(
                        account_index=active_account.index,
                        reason="HTTP 402/403 quota exhaustion",
                    )
                    current_chunk = [
                        e for e in current_chunk
                        if e not in results_by_email or results_by_email[e].status == "verification_error"
                    ]
                    if not next_account:
                        logger.error("All 7 Mail7 accounts in pool have been exhausted.")
                        final_error_reason = "quota_exhausted"
                        for email in current_chunk:
                            results_by_email[email] = VerificationResult(
                                email=email,
                                status="verification_error",
                                account_id=active_account.account_id,
                                reason="quota_exhausted",
                            )
                        chunk_resolved = True
                        break
                    else:
                        logger.info(
                            f"Continuing verification with Account {next_account.index} "
                            f"for {len(current_chunk)} remaining leads in current chunk..."
                        )
                        continue

                elif chunk_err == "unauthorized_api_key":
                    logger.error(
                        f"Mail7 Account {active_account.index} failed authentication (HTTP 401/403). "
                        "Halting to alert user without consuming other accounts."
                    )
                    self.pool.mark_account_auth_failed(active_account.index, reason="HTTP 401/403 auth failure")
                    final_error_reason = "unauthorized_api_key"
                    for email in current_chunk:
                        results_by_email[email] = VerificationResult(
                            email=email,
                            status="verification_error",
                            account_id=active_account.account_id,
                            reason="unauthorized_api_key",
                        )
                    chunk_resolved = True
                    break

                elif chunk_err and chunk_err not in ("bad_request",):
                    final_error_reason = chunk_err
                    for email, vr in verified_chunk_map.items():
                        results_by_email[email] = vr
                    chunk_resolved = True
                    break

                else:
                    # Successfully verified chunk!
                    results_by_email.update(verified_chunk_map)
                    self.pool.record_success(active_account.index)

                    # IMMEDIATELY persist cache entries after each chunk
                    chunk_cache_records = []
                    chunk_billable = 0
                    for vr in verified_chunk_map.values():
                        if vr.status in ("valid", "invalid", "unknown"):
                            chunk_cache_records.append({
                                "email": vr.email,
                                "account_id": vr.account_id,
                                "status": vr.status,
                                "date_verified": date_str,
                                "raw_result": vr.reason,
                            })
                        if vr.status in ("valid", "invalid") and vr.reason != "rejected_by_api_malformed_syntax":
                            chunk_billable += 1

                    if chunk_cache_records and not self.dry_run:
                        self.ledger.cache_verification_results(chunk_cache_records)

                    billable_by_account[active_account.account_id] = (
                        billable_by_account.get(active_account.account_id, 0) + chunk_billable
                    )
                    chunk_resolved = True

                    # Pacing: Sleep between chunks to stay safely below 20 req/min
                    if chunk_idx < num_chunks - 1:
                        self.sleep_func(self.pacing_delay)

            # If unrecoverable auth or quota error occurred, stop further chunks
            if final_error_reason in ("quota_exhausted", "unauthorized_api_key"):
                break

        # 4. Record billable usage per account
        if not self.dry_run:
            for acc_id, count in billable_by_account.items():
                if count > 0:
                    self.ledger.record_usage(acc_id, count, date_str)

        return [results_by_email[e] for e in ordered_unique], final_error_reason

    def _execute_http_bulk_request(
        self,
        chunk_emails: List[str],
        api_key: str,
        max_retries: int = 4,
    ) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        """
        Executes a single POST request with multipart form emails to Mail7 bulk validation endpoint.
        Returns (raw_results_list, error_reason).
        """
        email_payload = "\n".join(chunk_emails)
        files = {"emails": (None, email_payload)}
        headers = {"X-API-Key": api_key.strip()}

        last_error_reason: Optional[str] = None

        for attempt in range(max_retries):
            try:
                logger.info(
                    f"Posting bulk request with {len(chunk_emails)} emails to {self.endpoint} "
                    f"(attempt {attempt + 1}/{max_retries})..."
                )
                resp = requests.post(self.endpoint, files=files, headers=headers, timeout=(10, 60))

                if resp.status_code == 401:
                    logger.error("Mail7 returned HTTP 401 Unauthorized: Invalid API key.")
                    return None, "unauthorized_api_key"

                if resp.status_code == 403:
                    body_text = resp.text.lower()
                    if any(term in body_text for term in ("quota", "credit", "limit", "exhausted", "payment", "exceeded", "upgrade")):
                        logger.warning("Mail7 returned HTTP 403: Monthly verification quota exhausted.")
                        return None, "quota_exhausted"
                    else:
                        logger.error("Mail7 returned HTTP 403 Forbidden: API key unauthorized or plan restricted.")
                        return None, "unauthorized_api_key"

                if resp.status_code == 402:
                    logger.warning("Mail7 returned HTTP 402 Payment Required: Monthly credit limit exhausted.")
                    return None, "quota_exhausted"

                if resp.status_code == 400:
                    logger.error(f"Mail7 returned HTTP 400 Bad Request: {resp.text[:200]}")
                    return None, "bad_request"

                if resp.status_code == 429:
                    retry_header = resp.headers.get("Retry-After", "")
                    try:
                        retry_after = int(retry_header)
                    except ValueError:
                        # Documented Mail7 rate limit is 20 req/min for free tier
                        # Exponential backoff with jitter: 5s, 10s, 20s, 40s
                        retry_after = min(60, max(5, 5 * (2 ** attempt)))
                    jitter = self.random_func(0.5, 1.5)
                    total_wait = retry_after + jitter
                    logger.warning(
                        f"Mail7 returned HTTP 429 Too Many Requests (attempt {attempt + 1}/{max_retries}). "
                        f"Pacing backoff: waiting {total_wait:.1f}s before retry (DO NOT rotate account)..."
                    )
                    last_error_reason = "rate_limited"
                    if attempt < max_retries - 1:
                        self.sleep_func(total_wait)
                        continue
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
                raw_results = bulk_data.get("results")
                if not isinstance(raw_results, list):
                    logger.error(f"Mail7 bulk response missing 'results' list: {bulk_data}")
                    return None, "malformed_bulk_response"

                return raw_results, None

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

        return None, last_error_reason or "unknown_http_failure"

    def _verify_chunk_with_bisection(
        self,
        chunk_emails: List[str],
        api_key: str,
        account_id: str,
        date_str: str,
        max_retries: int = 3,
    ) -> Tuple[Dict[str, VerificationResult], Optional[str]]:
        """
        Submits a chunk of emails to Mail7 bulk API using the specified account.
        If HTTP 400 occurs:
        - If 1 email: isolates and marks invalid (reason="rejected_by_api_malformed_syntax").
        - If > 1 email: recursively bisects into two halves so remaining valid emails are verified.
        Returns (results_by_email, error_reason).
        """
        raw_results, error_reason = self._execute_http_bulk_request(
            chunk_emails=chunk_emails,
            api_key=api_key,
            max_retries=max_retries,
        )

        if error_reason == "bad_request":
            if len(chunk_emails) == 1:
                bad_email = chunk_emails[0]
                logger.warning(f"Isolated malformed email rejected by Mail7 with HTTP 400: {bad_email}")
                vr = VerificationResult(
                    email=bad_email,
                    status="invalid",
                    account_id=account_id,
                    reason="rejected_by_api_malformed_syntax",
                    raw_response={"error": "HTTP 400 Bad Request"},
                )
                return {bad_email: vr}, None

            # Bisection
            mid = len(chunk_emails) // 2
            left_half = chunk_emails[:mid]
            right_half = chunk_emails[mid:]
            logger.info(
                f"HTTP 400 on batch of {len(chunk_emails)} emails. Bisecting into {len(left_half)} and {len(right_half)}..."
            )

            left_results, left_err = self._verify_chunk_with_bisection(
                chunk_emails=left_half,
                api_key=api_key,
                account_id=account_id,
                date_str=date_str,
                max_retries=max_retries,
            )
            if left_err in ("quota_exhausted", "unauthorized_api_key", "missing_api_key"):
                return left_results, left_err

            right_results, right_err = self._verify_chunk_with_bisection(
                chunk_emails=right_half,
                api_key=api_key,
                account_id=account_id,
                date_str=date_str,
                max_retries=max_retries,
            )
            left_results.update(right_results)
            return left_results, right_err or left_err

        if raw_results is None:
            chunk_results: Dict[str, VerificationResult] = {}
            for email in chunk_emails:
                chunk_results[email] = VerificationResult(
                    email=email,
                    status="verification_error",
                    account_id=account_id,
                    reason=error_reason or "unknown_http_failure",
                )
            return chunk_results, error_reason

        # Process valid bulk response
        returned_map: Dict[str, Dict[str, Any]] = {}
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            ret_e = str(item.get("email", "")).strip().lower()
            if ret_e and ret_e not in returned_map:
                returned_map[ret_e] = item

        chunk_results = {}
        for email in chunk_emails:
            norm_e = email.strip().lower()
            if norm_e in returned_map:
                item = returned_map[norm_e]
                raw_st = str(item.get("status", "")).strip().lower()
                raw_valid = item.get("valid")
                details = str(item.get("details", "") or item.get("error", "") or "")

                if raw_st == "valid" or (raw_valid is True and raw_st != "not valid"):
                    status = "valid"
                elif raw_st in ("not valid", "not_valid", "invalid") or raw_valid is False:
                    status = "invalid"
                elif raw_st == "unknown" or raw_valid is None:
                    status = "unknown"
                else:
                    status = "verification_error"
                    details = f"unrecognized_status: {item.get('status')}"

                vr = VerificationResult(
                    email=email,
                    status=status,
                    account_id=account_id,
                    reason=details,
                    disposable=bool(item.get("is_disposable")),
                    raw_response=item,
                )
                chunk_results[email] = vr
            else:
                logger.warning(f"Address {email} missing from Mail7 bulk response.")
                chunk_results[email] = VerificationResult(
                    email=email,
                    status="verification_error",
                    account_id=account_id,
                    reason="missing_from_bulk_response",
                )

        return chunk_results, None


class QuickEmailVerifier(Mail7Verifier):
    """
    Backward-compatibility alias wrapping Mail7Verifier.
    Guarantees legacy references function seamlessly.
    """

    def __init__(self, *args, **kwargs):
        api_key = kwargs.pop("api_key", None) or kwargs.pop("key_1", None)
        kwargs.pop("key_2", None)
        super().__init__(api_key=api_key, **kwargs)

    def plan_and_partition(self, unique_emails: List[str], date_str: Optional[str] = None):
        """Deprecated partition: all emails verified via Mail7 bulk."""
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
