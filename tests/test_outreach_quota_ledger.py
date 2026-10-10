"""Tests for daily verifier quota ledger and result caching."""

import pytest
from pathlib import Path
from src.outreach.quota_ledger import QuotaLedger


def test_quota_ledger_tracking(tmp_path):
    ledger_file = tmp_path / "ledger.csv"
    cache_file = tmp_path / "cache.csv"

    ledger = QuotaLedger(ledger_file, cache_file, max_daily_quota_per_key=100)

    # Initial state
    assert ledger.get_daily_usage("account_1", "2026-10-10") == 0
    assert ledger.get_remaining_quota("account_1", "2026-10-10") == 100

    # Record 45 calls
    new_total = ledger.record_usage("account_1", 45, "2026-10-10")
    assert new_total == 45
    assert ledger.get_remaining_quota("account_1", "2026-10-10") == 55

    # Record another 55 calls -> quota exhausted
    new_total = ledger.record_usage("account_1", 55, "2026-10-10")
    assert new_total == 100
    assert ledger.get_remaining_quota("account_1", "2026-10-10") == 0

    # Account 2 remains untouched
    assert ledger.get_remaining_quota("account_2", "2026-10-10") == 100


def test_verification_cache_prevents_double_spending(tmp_path):
    ledger_file = tmp_path / "ledger.csv"
    cache_file = tmp_path / "cache.csv"

    ledger = QuotaLedger(ledger_file, cache_file)

    # Cache result for user@example.com
    ledger.cache_verification_results([{
        "email": "user@example.com",
        "account_id": "account_1",
        "status": "valid",
        "date_verified": "2026-10-10",
        "raw_result": "accepted_email",
    }])

    cached = ledger.get_cached_result("user@example.com")
    assert cached is not None
    assert cached["status"] == "valid"

    # Case insensitive lookup
    cached_upper = ledger.get_cached_result("USER@EXAMPLE.COM")
    assert cached_upper is not None
    assert cached_upper["status"] == "valid"

    # Non-existent
    assert ledger.get_cached_result("other@example.com") is None
