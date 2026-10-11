"""Regression tests for verification failure, bounded retry, failover, and quota safety."""

import pytest
import requests
from unittest.mock import MagicMock, patch
from src.outreach.verification_client import QuickEmailVerifier, VerificationResult
from src.outreach.quota_ledger import QuotaLedger


def test_verify_single_email_transient_retry(tmp_path):
    ledger = QuotaLedger(
        ledger_file=tmp_path / "ledger.csv",
        cache_file=tmp_path / "cache.csv"
    )
    verifier = QuickEmailVerifier(key_1="test_key_1", key_2="test_key_2", ledger=ledger)

    # Simulate Timeout on first attempt, then HTTP 200 valid on second attempt
    mock_resp_success = MagicMock()
    mock_resp_success.status_code = 200
    mock_resp_success.json.return_value = {"result": "valid", "reason": "accepted_email"}

    with patch("src.outreach.verification_client.requests.get") as mock_get:
        mock_get.side_effect = [requests.Timeout("Connection timed out"), mock_resp_success]
        with patch("src.outreach.verification_client.time.sleep") as mock_sleep:
            res = verifier.verify_single_email("test@example.com", "test_key_1", "account_1", max_retries=2)

    assert res.status == "valid"
    assert res.reason == "accepted_email"
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once_with(1)


def test_verify_single_email_quota_exhausted_immediate_fail(tmp_path):
    ledger = QuotaLedger(
        ledger_file=tmp_path / "ledger.csv",
        cache_file=tmp_path / "cache.csv"
    )
    verifier = QuickEmailVerifier(key_1="test_key_1", key_2="test_key_2", ledger=ledger)

    mock_resp_402 = MagicMock()
    mock_resp_402.status_code = 402

    with patch("src.outreach.verification_client.requests.get") as mock_get:
        mock_get.return_value = mock_resp_402
        res = verifier.verify_single_email("test@example.com", "test_key_1", "account_1")

    assert res.status == "verification_error"
    assert res.reason == "quota_exhausted"
    # Should not retry 402/429
    assert mock_get.call_count == 1


def test_verify_single_email_unauthorized_key_immediate_fail(tmp_path):
    ledger = QuotaLedger(
        ledger_file=tmp_path / "ledger.csv",
        cache_file=tmp_path / "cache.csv"
    )
    verifier = QuickEmailVerifier(key_1="test_key_1", key_2="test_key_2", ledger=ledger)

    mock_resp_401 = MagicMock()
    mock_resp_401.status_code = 401

    with patch("src.outreach.verification_client.requests.get") as mock_get:
        mock_get.return_value = mock_resp_401
        res = verifier.verify_single_email("test@example.com", "bad_key", "account_1")

    assert res.status == "verification_error"
    assert res.reason == "unauthorized_api_key"
    assert mock_get.call_count == 1


def test_quota_exhaustion_failover_from_account_1_to_account_2(tmp_path):
    """
    Account 1 verifies 2 emails, then hits quota exhaustion on email 3.
    The remaining emails (email 3, 4) should failover to Account 2, which verifies them.
    Total live calls to Account 1 = 3 (including the 402 call).
    Account 1 is marked exhausted.
    Account 2 verifies 2 overflow emails + its own batch.
    """
    ledger = QuotaLedger(
        ledger_file=tmp_path / "ledger.csv",
        cache_file=tmp_path / "cache.csv",
        max_daily_quota_per_key=100
    )
    verifier = QuickEmailVerifier(key_1="key1", key_2="key2", ledger=ledger)

    batch_a = ["a1@test.com", "a2@test.com", "a3@test.com", "a4@test.com"]
    batch_b = ["b1@test.com"]

    def mock_verify_single(email, key, account_id, max_retries=2):
        if account_id == "account_1":
            if email in ("a1@test.com", "a2@test.com"):
                return VerificationResult(email=email, status="valid", account_id=account_id, reason="accepted_email")
            else:
                return VerificationResult(email=email, status="verification_error", account_id=account_id, reason="quota_exhausted")
        elif account_id == "account_2":
            return VerificationResult(email=email, status="valid", account_id=account_id, reason="accepted_email")
        return VerificationResult(email=email, status="unknown", account_id=account_id)

    with patch.object(verifier, "verify_single_email", side_effect=mock_verify_single):
        results = verifier.verify_batches(batch_a, batch_b, date_str="2026-10-11")

    assert len(results) == 5
    # All 5 should be valid because a3 and a4 failed over to account 2!
    for r in results:
        assert r.status == "valid"

    # Verify Account 1 ledger usage is recorded
    assert ledger.get_remaining_quota("account_1", "2026-10-11") == 0
    # Verify Account 2 verified b1, a3, a4 (3 emails)
    assert ledger.get_daily_usage("account_2", "2026-10-11") == 3


def test_never_cache_verification_errors(tmp_path):
    cache_file = tmp_path / "cache.csv"
    ledger = QuotaLedger(
        ledger_file=tmp_path / "ledger.csv",
        cache_file=cache_file
    )

    records = [
        {"email": "valid@test.com", "account_id": "account_1", "status": "valid", "date_verified": "2026-10-11", "raw_result": "accepted_email"},
        {"email": "error@test.com", "account_id": "account_1", "status": "verification_error", "date_verified": "2026-10-11", "raw_result": "quota_exhausted"},
        {"email": "invalid@test.com", "account_id": "account_2", "status": "invalid", "date_verified": "2026-10-11", "raw_result": "rejected_email"},
    ]

    ledger.cache_verification_results(records)

    assert ledger.get_cached_result("valid@test.com") is not None
    assert ledger.get_cached_result("invalid@test.com") is not None
    assert ledger.get_cached_result("error@test.com") is None


def test_verify_single_email_rate_limit_429_retries_with_backoff(tmp_path):
    ledger = QuotaLedger(
        ledger_file=tmp_path / "ledger.csv",
        cache_file=tmp_path / "cache.csv"
    )
    verifier = QuickEmailVerifier(key_1="test_key_1", key_2="test_key_2", ledger=ledger)

    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429
    mock_resp_429.headers = {"Retry-After": "3", "X-QEV-Remaining-Credits": "49"}

    mock_resp_success = MagicMock()
    mock_resp_success.status_code = 200
    mock_resp_success.json.return_value = {"result": "valid", "reason": "accepted_email"}

    with patch("src.outreach.verification_client.requests.get") as mock_get:
        mock_get.side_effect = [mock_resp_429, mock_resp_success]
        with patch("src.outreach.verification_client.time.sleep") as mock_sleep:
            res = verifier.verify_single_email("test@example.com", "test_key_1", "account_1", max_retries=2)

    assert res.status == "valid"
    assert res.reason == "accepted_email"
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once_with(3)

