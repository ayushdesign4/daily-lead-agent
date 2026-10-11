"""Email verification client for QuickEmailVerification API with dual-account quota management."""

import time
import logging
import requests
from typing import List, Dict, Tuple, Optional, Any
from src.state_manager import get_today_ist_date
from src.outreach.config import (
    QEV_API_KEY_1,
    QEV_API_KEY_2,
    QEV_API_BASE_URL,
    MAX_VERIFICATIONS_PER_ACCOUNT_PER_DAY,
)
from src.outreach.quota_ledger import QuotaLedger

logger = logging.getLogger(__name__)


class VerificationResult:
    """Standardized verification result object."""
    def __init__(
        self,
        email: str,
        status: str,  # 'valid', 'invalid', 'risky', 'unknown', 'verification_error'
        account_id: str,
        reason: Optional[str] = None,
        disposable: bool = False,
        accept_all: bool = False,
        raw_response: Optional[Dict[str, Any]] = None,
    ):
        self.email = email
        self.status = status
        self.account_id = account_id
        self.reason = reason or ""
        self.disposable = disposable
        self.accept_all = accept_all
        self.raw_response = raw_response or {}

    @property
    def is_deliverable(self) -> bool:
        """Strict policy: only 'valid' is eligible for outreach."""
        return self.status == "valid" and not self.disposable and not self.accept_all


class QuickEmailVerifier:
    """Client for validating emails using QuickEmailVerification API across dual accounts."""

    def __init__(
        self,
        key_1: Optional[str] = None,
        key_2: Optional[str] = None,
        ledger: Optional[QuotaLedger] = None,
        dry_run: bool = False,
    ):
        self.key_1 = key_1 or QEV_API_KEY_1
        self.key_2 = key_2 or QEV_API_KEY_2
        self.ledger = ledger or QuotaLedger()
        self.dry_run = dry_run
        self.base_url = QEV_API_BASE_URL

    def verify_single_email(
        self,
        email: str,
        api_key: str,
        account_id: str,
        max_retries: int = 2,
    ) -> VerificationResult:
        """Verify a single email using QEV API endpoint with bounded retry for transient network issues."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Simulating verification for {email} via {account_id}")
            return VerificationResult(
                email=email,
                status="valid",
                account_id=account_id,
                reason="accepted_email",
                disposable=False,
                accept_all=False,
                raw_response={"result": "valid", "simulated": True},
            )

        if not api_key:
            logger.error(f"No API key provided for {account_id}")
            return VerificationResult(
                email=email,
                status="verification_error",
                account_id=account_id,
                reason="missing_api_key",
            )

        params = {"email": email, "apikey": api_key}
        for attempt in range(max_retries):
            try:
                resp = requests.get(self.base_url, params=params, timeout=15)
                if resp.status_code == 401:
                    logger.error(f"Unauthorized QEV API key for {account_id}")
                    return VerificationResult(
                        email=email,
                        status="verification_error",
                        account_id=account_id,
                        reason="unauthorized_api_key",
                    )
                if resp.status_code in (402, 429):
                    logger.warning(f"Credit or rate limit reached on {account_id}: HTTP {resp.status_code}")
                    return VerificationResult(
                        email=email,
                        status="verification_error",
                        account_id=account_id,
                        reason="quota_exhausted",
                    )
                resp.raise_for_status()
                data = resp.json()

                # QEV schema mapping
                qev_result = str(data.get("result", "")).lower()
                reason = str(data.get("reason", "")).lower()
                disposable = bool(data.get("disposable") is True or str(data.get("disposable")).lower() == "true")
                accept_all = bool(data.get("accept_all") is True or str(data.get("accept_all")).lower() == "true")

                if qev_result == "valid":
                    if disposable or accept_all:
                        status = "risky"
                    else:
                        status = "valid"
                elif qev_result == "invalid":
                    status = "invalid"
                elif qev_result == "unknown":
                    status = "unknown"
                else:
                    status = "unknown"

                return VerificationResult(
                    email=email,
                    status=status,
                    account_id=account_id,
                    reason=reason,
                    disposable=disposable,
                    accept_all=accept_all,
                    raw_response={"result": qev_result, "reason": reason},
                )
            except (requests.Timeout, requests.ConnectionError) as e:
                if attempt < max_retries - 1:
                    logger.info(f"Transient network error verifying {email} on {account_id} (attempt {attempt+1}/{max_retries}), retrying: {e}")
                    time.sleep(1)
                    continue
                logger.warning(f"Network/timeout error verifying {email} on {account_id}: {e}")
                return VerificationResult(
                    email=email,
                    status="verification_error",
                    account_id=account_id,
                    reason=f"request_exception: {type(e).__name__}",
                )
            except requests.RequestException as e:
                logger.warning(f"Request exception verifying {email} on {account_id}: {e}")
                return VerificationResult(
                    email=email,
                    status="verification_error",
                    account_id=account_id,
                    reason=f"request_exception: {type(e).__name__}",
                )
            except Exception as e:
                logger.error(f"Unexpected parsing exception for {email} on {account_id}: {e}")
                return VerificationResult(
                    email=email,
                    status="verification_error",
                    account_id=account_id,
                    reason=f"parsing_exception: {type(e).__name__}",
                )

        return VerificationResult(
            email=email,
            status="verification_error",
            account_id=account_id,
            reason="max_retries_exceeded",
        )

    def plan_and_partition(
        self,
        unique_emails: List[str],
        date_str: Optional[str] = None
    ) -> Tuple[List[str], List[str], int]:
        """
        Partition up to 200 emails into two disjoint batches matching available daily quotas:
        - Batch 1: assigned to Account A (up to quota A, max 100)
        - Batch 2: assigned to Account B (up to quota B, max 100)
        - Returns (batch_a_emails, batch_b_emails, deferred_count)
        """
        if not date_str:
            date_str = get_today_ist_date()

        quota_a = self.ledger.get_remaining_quota("account_1", date_str)
        quota_b = self.ledger.get_remaining_quota("account_2", date_str)

        cap_a = min(quota_a, MAX_VERIFICATIONS_PER_ACCOUNT_PER_DAY)
        cap_b = min(quota_b, MAX_VERIFICATIONS_PER_ACCOUNT_PER_DAY)
        total_capacity = cap_a + cap_b

        eligible_to_verify = unique_emails[:total_capacity]
        deferred_count = max(0, len(unique_emails) - len(eligible_to_verify))

        batch_a = eligible_to_verify[:cap_a]
        batch_b = eligible_to_verify[cap_a:cap_a + cap_b]

        logger.info(
            f"Verification Partitioning: {len(unique_emails)} unique -> "
            f"Batch A: {len(batch_a)} (quota remaining: {cap_a}), "
            f"Batch B: {len(batch_b)} (quota remaining: {cap_b}), "
            f"Deferred: {deferred_count}"
        )
        return batch_a, batch_b, deferred_count

    def verify_batches(
        self,
        batch_a: List[str],
        batch_b: List[str],
        date_str: Optional[str] = None
    ) -> List[VerificationResult]:
        """
        Execute verification for two disjoint batches, using cache where available,
        updating daily quota usage atomically.
        If an account hits quota exhaustion, it halts immediately, marks the account exhausted,
        and fails over any remaining unverified leads to the second account (subject to second account quota).
        """
        if not date_str:
            date_str = get_today_ist_date()

        results: List[VerificationResult] = []
        cache_records_to_save: List[Dict[str, str]] = []

        # Process Batch A on Account 1
        live_calls_a = 0
        overflow_from_a: List[str] = []
        account_1_exhausted = False

        for email in batch_a:
            cached = self.ledger.get_cached_result(email)
            if cached:
                results.append(VerificationResult(
                    email=email,
                    status=cached.get("status", "unknown"),
                    account_id="cache",
                    reason="cached_result",
                ))
                continue

            if account_1_exhausted:
                overflow_from_a.append(email)
                continue

            res = self.verify_single_email(email, self.key_1 or "", "account_1")

            if res.reason == "quota_exhausted":
                logger.warning(f"Account 1 quota exhausted at email {email}. Halting Account 1 verification.")
                account_1_exhausted = True
                self.ledger.mark_account_exhausted("account_1", date_str)
                overflow_from_a.append(email)
                continue

            results.append(res)
            live_calls_a += 1
            if res.status in ("valid", "invalid", "risky"):
                cache_records_to_save.append({
                    "email": email,
                    "account_id": "account_1",
                    "status": res.status,
                    "date_verified": date_str,
                    "raw_result": res.reason,
                })

        if live_calls_a > 0 and not self.dry_run:
            self.ledger.record_usage("account_1", live_calls_a, date_str)

        # Build candidate list for Account 2: batch_b plus any overflow from batch_a
        combined_b = list(batch_b) + overflow_from_a
        quota_b_remaining = self.ledger.get_remaining_quota("account_2", date_str)
        live_calls_b = 0
        account_2_exhausted = False

        for email in combined_b:
            cached = self.ledger.get_cached_result(email)
            if cached:
                results.append(VerificationResult(
                    email=email,
                    status=cached.get("status", "unknown"),
                    account_id="cache",
                    reason="cached_result",
                ))
                continue

            if account_2_exhausted or live_calls_b >= quota_b_remaining:
                logger.warning(f"Cannot verify {email}: Account 2 daily quota limit reached ({live_calls_b}/{quota_b_remaining}).")
                results.append(VerificationResult(
                    email=email,
                    status="verification_error",
                    account_id="none",
                    reason="quota_exhausted",
                ))
                continue

            res = self.verify_single_email(email, self.key_2 or "", "account_2")

            if res.reason == "quota_exhausted":
                logger.warning(f"Account 2 quota exhausted at email {email}. Halting Account 2 verification.")
                account_2_exhausted = True
                self.ledger.mark_account_exhausted("account_2", date_str)
                results.append(res)
                continue

            results.append(res)
            live_calls_b += 1
            if res.status in ("valid", "invalid", "risky"):
                cache_records_to_save.append({
                    "email": email,
                    "account_id": "account_2",
                    "status": res.status,
                    "date_verified": date_str,
                    "raw_result": res.reason,
                })

        if live_calls_b > 0 and not self.dry_run:
            self.ledger.record_usage("account_2", live_calls_b, date_str)

        if cache_records_to_save and not self.dry_run:
            self.ledger.cache_verification_results(cache_records_to_save)

        return results
