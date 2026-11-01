"""Tests for the Smart 7-Account Mail7 API Key Rotation System.

All tests are offline and mocked. No real emails sent, zero live Mail7 credits consumed.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from src.outreach.mail7_pool import Mail7AccountPool, Mail7Account
from src.outreach.verification_client import Mail7Verifier, VerificationResult
from src.outreach.quota_ledger import QuotaLedger


@pytest.fixture
def mock_7_keys():
    return [f"mk_mock_key_{i}" for i in range(1, 8)]


@pytest.fixture
def temp_pool_state_file(tmp_path):
    return tmp_path / "mail7_pool_state.json"


@pytest.fixture
def isolated_ledger(tmp_path):
    return QuotaLedger(
        ledger_file=tmp_path / "verification_ledger.csv",
        cache_file=tmp_path / "verification_cache.csv",
    )


class TestMail7AccountPool:
    """Unit tests for Mail7AccountPool state, rotation, and lifecycle."""

    def test_pool_initializes_with_account_1_active(self, mock_7_keys, temp_pool_state_file):
        pool = Mail7AccountPool(keys=mock_7_keys, state_file=temp_pool_state_file)
        active = pool.get_active_account()
        assert active is not None
        assert active.index == 1
        assert active.api_key == "mk_mock_key_1"
        assert active.account_id == "mail7_account_1"
        assert active.secret_env_name == "MAIL7_API_KEY_1"
        assert pool.state["current_account_index"] == 1
        assert pool.state["exhausted_accounts"] == []

    def test_active_account_persists_across_daily_runs_without_daily_reset(self, mock_7_keys, temp_pool_state_file):
        # Day 1: start at 1
        pool1 = Mail7AccountPool(keys=mock_7_keys, state_file=temp_pool_state_file, today_ist_date="2026-11-01")
        pool1.mark_account_exhausted(1)
        assert pool1.get_active_account().index == 2

        # Day 2: new daily run (same month 2026-11-02). MUST NOT reset to 1.
        pool2 = Mail7AccountPool(keys=mock_7_keys, state_file=temp_pool_state_file, today_ist_date="2026-11-02")
        active = pool2.get_active_account()
        assert active.index == 2
        assert pool2.state["exhausted_accounts"] == [1]

        # Day 3: new daily run (same month 2026-11-03).
        pool3 = Mail7AccountPool(keys=mock_7_keys, state_file=temp_pool_state_file, today_ist_date="2026-11-03")
        assert pool3.get_active_account().index == 2

    def test_monthly_rollover_resets_to_account_1_and_clears_exhausted(self, mock_7_keys, temp_pool_state_file):
        # Month 1: November 2026, exhaust accounts 1, 2, 3
        pool_nov = Mail7AccountPool(keys=mock_7_keys, state_file=temp_pool_state_file, today_ist_date="2026-11-20")
        pool_nov.mark_account_exhausted(1)
        pool_nov.mark_account_exhausted(2)
        pool_nov.mark_account_exhausted(3)
        assert pool_nov.get_active_account().index == 4
        assert pool_nov.state["exhausted_accounts"] == [1, 2, 3]

        # Month 2: December 2026 (new month cycle '2026-12').
        pool_dec = Mail7AccountPool(keys=mock_7_keys, state_file=temp_pool_state_file, today_ist_date="2026-12-01")
        assert pool_dec.state["monthly_cycle"] == "2026-12"
        assert pool_dec.state["current_account_index"] == 1
        assert pool_dec.state["exhausted_accounts"] == []
        assert pool_dec.get_active_account().index == 1

    def test_sequential_rotation_through_all_7_accounts(self, mock_7_keys, temp_pool_state_file):
        pool = Mail7AccountPool(keys=mock_7_keys, state_file=temp_pool_state_file)

        for expected_idx in range(1, 8):
            active = pool.get_active_account()
            assert active is not None
            assert active.index == expected_idx
            assert active.account_id == f"mail7_account_{expected_idx}"
            pool.mark_account_exhausted(expected_idx)

        # After exhausting all 7 accounts
        assert pool.is_all_exhausted() is True
        assert pool.get_active_account() is None
        assert pool.state["exhausted_accounts"] == [1, 2, 3, 4, 5, 6, 7]

    def test_exhausted_account_never_called_again_in_same_cycle(self, mock_7_keys, temp_pool_state_file):
        pool = Mail7AccountPool(keys=mock_7_keys, state_file=temp_pool_state_file)
        pool.mark_account_exhausted(1)
        pool.mark_account_exhausted(2)

        # Simulate workflow restart
        pool_restarted = Mail7AccountPool(keys=mock_7_keys, state_file=temp_pool_state_file)
        active = pool_restarted.get_active_account()
        assert active.index == 3
        assert 1 in pool_restarted.state["exhausted_accounts"]
        assert 2 in pool_restarted.state["exhausted_accounts"]

    def test_missing_or_partial_keys_handled_gracefully(self, temp_pool_state_file):
        # Only Accounts 1, 2, and 4 configured; others None
        partial_keys = ["key_1", "key_2", None, "key_4", None, None, None]
        pool = Mail7AccountPool(keys=partial_keys, state_file=temp_pool_state_file)

        assert pool.get_active_account().index == 1
        pool.mark_account_exhausted(1)
        assert pool.get_active_account().index == 2
        pool.mark_account_exhausted(2)
        # Should skip 3 (unconfigured) and go straight to 4
        assert pool.get_active_account().index == 4
        pool.mark_account_exhausted(4)
        # All configured are exhausted
        assert pool.get_active_account() is None
        assert pool.is_all_exhausted() is True


class TestMail7VerifierMultiAccount:
    """Integration tests for Mail7Verifier with 7-account pool rotation."""

    def test_immediate_switch_on_402_quota_exhaustion(self, mock_7_keys, temp_pool_state_file, isolated_ledger):
        """Account 1 gets 402, rotates to Account 2, completes remaining emails."""
        verifier = Mail7Verifier(
            keys=mock_7_keys,
            state_file=temp_pool_state_file,
            ledger=isolated_ledger,
        )

        resp_402 = MagicMock()
        resp_402.status_code = 402
        resp_402.text = "Monthly verification quota exceeded"

        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {
            "total": 2,
            "results": [
                {"email": "a@test.com", "valid": True, "status": "Valid"},
                {"email": "b@test.com", "valid": False, "status": "Invalid"},
            ]
        }

        call_keys = []
        def fake_post(*args, **kwargs):
            headers = kwargs.get("headers", {})
            key = headers.get("X-API-Key") or headers.get("X-Api-Key")
            call_keys.append(key)
            if key == "mk_mock_key_1":
                return resp_402
            return resp_200

        with patch("src.outreach.verification_client.requests.post", side_effect=fake_post):
            results, err = verifier.verify_bulk(["a@test.com", "b@test.com"])

        # No error because Account 2 took over and verified both!
        assert err is None
        assert len(results) == 2
        assert results[0].is_deliverable is True
        assert results[0].account_id == "mail7_account_2"
        assert results[1].is_deliverable is False

        # Account 1 was marked exhausted in pool
        assert 1 in verifier.pool.state["exhausted_accounts"]
        assert verifier.pool.state["current_account_index"] == 2
        assert call_keys == ["mk_mock_key_1", "mk_mock_key_2"]

    def test_rotation_across_three_accounts_in_single_bulk_session(self, mock_7_keys, temp_pool_state_file, isolated_ledger):
        """Account 1 fails (402), Account 2 fails (403 quota), Account 3 succeeds."""
        verifier = Mail7Verifier(
            keys=mock_7_keys,
            state_file=temp_pool_state_file,
            ledger=isolated_ledger,
        )

        resp_402 = MagicMock()
        resp_402.status_code = 402
        resp_402.text = "Quota limit reached"

        resp_403_quota = MagicMock()
        resp_403_quota.status_code = 403
        resp_403_quota.text = "Credits exhausted for this billing period"

        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {
            "total": 1,
            "results": [{"email": "lead@test.com", "valid": True, "status": "Valid"}]
        }

        def fake_post(*args, **kwargs):
            headers = kwargs.get("headers", {})
            key = headers.get("X-API-Key") or headers.get("X-Api-Key")
            if key == "mk_mock_key_1":
                return resp_402
            elif key == "mk_mock_key_2":
                return resp_403_quota
            elif key == "mk_mock_key_3":
                return resp_200
            raise AssertionError(f"Unexpected call with key {key}")

        with patch("src.outreach.verification_client.requests.post", side_effect=fake_post):
            results, err = verifier.verify_bulk(["lead@test.com"])

        assert err is None
        assert results[0].is_deliverable is True
        assert results[0].account_id == "mail7_account_3"
        assert verifier.pool.state["exhausted_accounts"] == [1, 2]
        assert verifier.pool.get_active_account().index == 3

    def test_all_7_accounts_exhausted_halts_and_preserves_unverified(self, mock_7_keys, temp_pool_state_file, isolated_ledger):
        """When all 7 accounts return 402, halt cleanly with quota_exhausted."""
        verifier = Mail7Verifier(
            keys=mock_7_keys,
            state_file=temp_pool_state_file,
            ledger=isolated_ledger,
        )

        resp_402 = MagicMock()
        resp_402.status_code = 402
        resp_402.text = "Quota exhausted"

        with patch("src.outreach.verification_client.requests.post", return_value=resp_402):
            results, err = verifier.verify_bulk(["lead1@test.com", "lead2@test.com"])

        assert err == "quota_exhausted"
        assert verifier.pool.is_all_exhausted() is True
        assert len(results) == 2
        assert all(r.status == "verification_error" for r in results)
        assert all(r.reason == "quota_exhausted" for r in results)

    def test_http_401_auth_failure_halts_immediately_without_burning_remaining_accounts(self, mock_7_keys, temp_pool_state_file, isolated_ledger):
        """Account 1 gets 401: halt immediately, mark auth_failed, do NOT try Account 2."""
        verifier = Mail7Verifier(
            keys=mock_7_keys,
            state_file=temp_pool_state_file,
            ledger=isolated_ledger,
        )

        resp_401 = MagicMock()
        resp_401.status_code = 401
        resp_401.text = "Invalid API Key"

        call_count = 0
        def fake_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return resp_401

        with patch("src.outreach.verification_client.requests.post", side_effect=fake_post):
            results, err = verifier.verify_bulk(["lead@test.com"])

        assert err == "unauthorized_api_key"
        assert call_count == 1  # Exactly ONE call, did NOT try account 2..7!
        assert 1 in verifier.pool.state["auth_failed_accounts"]
        assert verifier.pool.state["exhausted_accounts"] == []  # Not marked exhausted

    def test_http_429_retries_same_account_does_not_rotate(self, mock_7_keys, temp_pool_state_file, isolated_ledger):
        """HTTP 429 rate limit retries same account, does not switch account."""
        verifier = Mail7Verifier(
            keys=mock_7_keys,
            state_file=temp_pool_state_file,
            ledger=isolated_ledger,
            sleep_func=lambda s: None,
        )

        resp_429 = MagicMock()
        resp_429.status_code = 429
        resp_429.headers = {"Retry-After": "1"}

        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {
            "total": 1,
            "results": [{"email": "lead@test.com", "valid": True, "status": "Valid"}]
        }

        call_keys = []
        attempts = 0
        def fake_post(*args, **kwargs):
            nonlocal attempts
            attempts += 1
            headers = kwargs.get("headers", {})
            call_keys.append(headers.get("X-API-Key") or headers.get("X-Api-Key"))
            if attempts == 1:
                return resp_429
            return resp_200

        with patch("src.outreach.verification_client.requests.post", side_effect=fake_post):
            results, err = verifier.verify_bulk(["lead@test.com"])

        assert err is None
        assert results[0].is_deliverable is True
        assert results[0].account_id == "mail7_account_1"
        assert call_keys == ["mk_mock_key_1", "mk_mock_key_1"]  # Same account retried
        assert verifier.pool.state["current_account_index"] == 1
        assert verifier.pool.state["exhausted_accounts"] == []

    def test_ledger_records_correct_account_id(self, mock_7_keys, temp_pool_state_file, isolated_ledger):
        """Ledger records which specific Mail7 account was used for verification."""
        verifier = Mail7Verifier(
            keys=mock_7_keys,
            state_file=temp_pool_state_file,
            ledger=isolated_ledger,
        )

        # Force active to Account 3
        verifier.pool.state["current_account_index"] = 3
        verifier.pool.save_state()

        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {
            "total": 1,
            "results": [{"email": "creator@test.com", "valid": True, "status": "Valid"}]
        }

        with patch("src.outreach.verification_client.requests.post", return_value=resp_200):
            results, err = verifier.verify_bulk(["creator@test.com"], date_str="2026-11-01")

        assert err is None
        assert results[0].account_id == "mail7_account_3"

        # Check ledger record
        usage = isolated_ledger.get_daily_usage("mail7_account_3", "2026-11-01")
        assert usage == 1

        # Check cache record
        cached = isolated_ledger.get_cached_result("creator@test.com")
        assert cached is not None
        assert cached["account_id"] == "mail7_account_3"

    def test_never_exposes_secrets_in_logs_or_summaries(self, mock_7_keys, temp_pool_state_file):
        """Status summary and state do not expose secret values."""
        pool = Mail7AccountPool(keys=mock_7_keys, state_file=temp_pool_state_file)
        pool.save_state()
        summary = pool.get_status_summary()

        summary_json = json.dumps(summary)
        for key in mock_7_keys:
            assert key not in summary_json

        # State file on disk also does not contain keys (only indexes and metadata)
        pool_state_text = temp_pool_state_file.read_text(encoding="utf-8")
        for key in mock_7_keys:
            assert key not in pool_state_text
