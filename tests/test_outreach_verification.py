"""Tests for verification partitioning, QEV API response mapping, and quota enforcement."""

import pytest
from unittest.mock import patch, MagicMock
from src.outreach.verification_client import QuickEmailVerifier, VerificationResult
from src.outreach.quota_ledger import QuotaLedger


def test_partitioning_two_disjoint_batches_max_100(tmp_path):
    ledger = QuotaLedger(tmp_path / "l.csv", tmp_path / "c.csv", max_daily_quota_per_key=100)
    verifier = QuickEmailVerifier(key_1="key_a", key_2="key_b", ledger=ledger)

    # 250 unique emails
    emails = [f"creator_{i}@domain.com" for i in range(250)]

    batch_a, batch_b, deferred = verifier.plan_and_partition(emails, "2026-10-10")

    # Max 100 per account
    assert len(batch_a) == 100
    assert len(batch_b) == 100
    assert deferred == 50  # 250 - 200 = 50 deferred

    # Disjoint check: no email in both batches
    set_a, set_b = set(batch_a), set(batch_b)
    assert len(set_a.intersection(set_b)) == 0


def test_partitioning_with_partial_quota(tmp_path):
    ledger = QuotaLedger(tmp_path / "l.csv", tmp_path / "c.csv", max_daily_quota_per_key=100)
    # Account A already used 60 today (40 remaining)
    ledger.record_usage("account_1", 60, "2026-10-10")
    # Account B already used 90 today (10 remaining)
    ledger.record_usage("account_2", 90, "2026-10-10")

    verifier = QuickEmailVerifier(key_1="k1", key_2="k2", ledger=ledger)

    emails = [f"creator_{i}@domain.com" for i in range(100)]
    batch_a, batch_b, deferred = verifier.plan_and_partition(emails, "2026-10-10")

    assert len(batch_a) == 40
    assert len(batch_b) == 10
    assert deferred == 50


@patch("requests.get")
def test_response_mapping_policy(mock_get, tmp_path):
    ledger = QuotaLedger(tmp_path / "l.csv", tmp_path / "c.csv")
    verifier = QuickEmailVerifier(key_1="k1", key_2="k2", ledger=ledger)

    # Case 1: Strictly Valid
    resp_valid = MagicMock()
    resp_valid.status_code = 200
    resp_valid.json.return_value = {
        "result": "valid",
        "reason": "accepted_email",
        "disposable": False,
        "accept_all": False,
    }

    # Case 2: Disposable (Risky)
    resp_disposable = MagicMock()
    resp_disposable.status_code = 200
    resp_disposable.json.return_value = {
        "result": "valid",
        "reason": "accepted_email",
        "disposable": True,
        "accept_all": False,
    }

    # Case 3: Accept All / Catch-all (Risky)
    resp_accept_all = MagicMock()
    resp_accept_all.status_code = 200
    resp_accept_all.json.return_value = {
        "result": "valid",
        "reason": "accepted_email",
        "disposable": False,
        "accept_all": True,
    }

    # Case 4: Invalid
    resp_invalid = MagicMock()
    resp_invalid.status_code = 200
    resp_invalid.json.return_value = {
        "result": "invalid",
        "reason": "rejected_email",
    }

    # Case 5: Unknown
    resp_unknown = MagicMock()
    resp_unknown.status_code = 200
    resp_unknown.json.return_value = {
        "result": "unknown",
        "reason": "no_connect",
    }

    mock_get.side_effect = [resp_valid, resp_disposable, resp_accept_all, resp_invalid, resp_unknown]

    r1 = verifier.verify_single_email("c1@test.com", "k1", "account_1")
    assert r1.status == "valid"
    assert r1.is_deliverable is True

    r2 = verifier.verify_single_email("c2@test.com", "k1", "account_1")
    assert r2.status == "risky"
    assert r2.is_deliverable is False

    r3 = verifier.verify_single_email("c3@test.com", "k1", "account_1")
    assert r3.status == "risky"
    assert r3.is_deliverable is False

    r4 = verifier.verify_single_email("c4@test.com", "k1", "account_1")
    assert r4.status == "invalid"
    assert r4.is_deliverable is False

    r5 = verifier.verify_single_email("c5@test.com", "k1", "account_1")
    assert r5.status == "unknown"
    assert r5.is_deliverable is False
