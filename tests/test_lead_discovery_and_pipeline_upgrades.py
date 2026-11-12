"""
Unit and Integration Tests for:
1. Multi-Dork Discovery Matrix (YouTube majority, Instagram YouTube dorks, developed Indian markets, 1-word & multi-word niches, query history)
2. Mail7 chunking, pacing, HTTP 429 rate-limit backoff, and rotation on quota exhaustion
3. Partial lead delivery in mode='deliver' (never re-scrapes, delivers partial queue)
4. Master database protection (historical data preserved intact)
"""

import os
import json
import tempfile
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch

from src.discovery_matrix import (
    DiscoveryMatrix,
    YOUTUBE_DORKS,
    INSTAGRAM_YOUTUBE_DORKS,
    INDIAN_LOCATIONS,
    REFRESHED_ONE_WORD_NICHES,
    REALISTIC_MULTI_WORD_NICHES,
    compute_query_hash,
)
from src.niche_manager import NicheManager, is_valid_niche, is_valid_one_word_niche
from src.outreach.verification_client import Mail7Verifier, VerificationResult
from src.outreach.mail7_pool import Mail7AccountPool


# ===========================================================================
# 1. Multi-Dork Discovery Matrix & Niche Pool Tests
# ===========================================================================

def test_youtube_dorks_form_clear_majority():
    """Verify that YouTube Dorks constitute the majority of template options (>80%)."""
    total = len(YOUTUBE_DORKS) + len(INSTAGRAM_YOUTUBE_DORKS)
    yt_ratio = len(YOUTUBE_DORKS) / total
    assert yt_ratio >= 0.80, f"YouTube Dorks should be >= 80%, found {yt_ratio:.1%}"


def test_instagram_dorks_strictly_target_youtube_creators():
    """Ensure every Instagram Dork explicitly contains a YouTube creator indicator."""
    yt_indicators = ["youtube.com/@", "youtuber", "youtube creator", "subscribe on youtube", "my youtube channel"]
    for dork in INSTAGRAM_YOUTUBE_DORKS:
        dork_lower = dork.lower()
        has_indicator = any(ind in dork_lower for ind in yt_indicators)
        assert has_indicator, f"Instagram Dork lacks YouTube creator targeting: {dork}"


def test_gmail_targeting_preserved():
    """Ensure generated queries maintain strong Gmail targeting."""
    with tempfile.TemporaryDirectory() as tmpdir:
        matrix = DiscoveryMatrix(
            state_file=Path(tmpdir) / "discovery_state.json",
            history_file=Path(tmpdir) / "query_history.json",
        )
        batch = matrix.generate_batch_queries(count=10)
        gmail_count = sum(1 for _, q in batch if "gmail.com" in q)
        assert gmail_count >= 8, f"At least 80% of queries must target gmail.com, found {gmail_count}/10"


def test_geographic_rotation_developed_indian_markets():
    """Ensure queries rotate across developed Indian urban markets."""
    expected_markets = {"Mumbai", "Pune", "Delhi", "Bengaluru", "Hyderabad", "Ahmedabad", "Jaipur", "Kolkata", "Chandigarh"}
    with tempfile.TemporaryDirectory() as tmpdir:
        matrix = DiscoveryMatrix(
            state_file=Path(tmpdir) / "discovery_state.json",
            history_file=Path(tmpdir) / "query_history.json",
        )
        # Generate 3 batches of 10 queries
        all_queries = []
        for _ in range(3):
            all_queries.extend(matrix.generate_batch_queries(count=10))

        found_markets = set()
        for _, q in all_queries:
            for market in expected_markets:
                if market in q:
                    found_markets.add(market)

        assert len(found_markets) >= 5, f"Expected at least 5 developed markets in queries, found: {found_markets}"


def test_supports_both_one_word_and_multi_word_niches():
    """Verify is_valid_niche accepts refreshed 1-word and 2-3 word creator niches."""
    # 1-word niches
    for niche in ["tech", "gaming", "cricket", "finance", "fitness", "vlog"]:
        assert is_valid_niche(niche), f"Should accept valid 1-word niche: {niche}"
        assert is_valid_one_word_niche(niche), f"Should pass 1-word validator: {niche}"

    # Realistic 2-3 word niches
    multi_word_samples = [
        "tech unboxing hindi",
        "bgmi gameplay highlights",
        "daily vlog hindi",
        "stock market investing hindi",
        "street food vlogger",
        "cricket analysis podcast",
        "graphic design tutorial hindi",
    ]
    for niche in multi_word_samples:
        assert is_valid_niche(niche), f"Should accept valid multi-word niche: {niche}"


def test_query_fingerprinting_prevents_duplicate_searches():
    """Ensure previously executed queries are never repeated."""
    with tempfile.TemporaryDirectory() as tmpdir:
        matrix = DiscoveryMatrix(
            state_file=Path(tmpdir) / "discovery_state.json",
            history_file=Path(tmpdir) / "query_history.json",
        )
        batch_1 = matrix.generate_batch_queries(count=10)
        queries_1 = [q for _, q in batch_1]
        matrix.record_queries_as_used(queries_1)

        # Generating second batch should produce distinct queries
        batch_2 = matrix.generate_batch_queries(count=10)
        queries_2 = [q for _, q in batch_2]

        overlap = set(queries_1) & set(queries_2)
        assert len(overlap) == 0, f"Found repeated queries across batches: {overlap}"


# ===========================================================================
# 2. Mail7 Chunking, Pacing, and Rate-Limit Tests
# ===========================================================================

def test_mail7_chunking_into_safe_batches():
    """Verify emails are validated in chunks of 35 rather than all at once."""
    mock_pool = MagicMock(spec=Mail7AccountPool)
    mock_account = MagicMock()
    mock_account.index = 1
    mock_account.account_id = "mail7_account_1"
    mock_account.api_key = "test_key_1"
    mock_account.is_configured = True
    mock_pool.get_active_account.return_value = mock_account

    sleeps = []
    mock_sleep = lambda s: sleeps.append(s)

    mock_ledger = MagicMock()
    mock_ledger.get_cached_result.return_value = None

    verifier = Mail7Verifier(
        pool=mock_pool,
        ledger=mock_ledger,
        sleep_func=mock_sleep,
    )
    verifier.chunk_size = 35

    # 100 test emails
    emails = [f"creator_{i}@gmail.com" for i in range(100)]

    chunk_calls = []

    def fake_verify_chunk(chunk_emails, api_key, account_id, date_str, max_retries):
        chunk_calls.append(len(chunk_emails))
        return {e: VerificationResult(email=e, status="valid", account_id=account_id) for e in chunk_emails}, None

    verifier._verify_chunk_with_bisection = fake_verify_chunk

    results, err = verifier.verify_bulk(emails)

    assert err is None
    assert len(results) == 100
    # 100 emails chunked by 35 -> [35, 35, 30]
    assert chunk_calls == [35, 35, 30], f"Expected chunks [35, 35, 30], got {chunk_calls}"
    # Pacing sleep should be called between chunks (2 sleeps for 3 chunks)
    pacing_sleeps = [s for s in sleeps if s == 3.0]
    assert len(pacing_sleeps) == 2, f"Expected 2 pacing sleeps of 3.0s, got: {sleeps}"


def test_mail7_http_429_backs_off_without_account_rotation():
    """Verify HTTP 429 triggers backoff retry and DOES NOT rotate account."""
    mock_pool = MagicMock(spec=Mail7AccountPool)
    mock_account = MagicMock()
    mock_account.index = 1
    mock_account.account_id = "mail7_account_1"
    mock_account.api_key = "test_key_1"
    mock_account.is_configured = True
    mock_pool.get_active_account.return_value = mock_account

    sleeps = []
    verifier = Mail7Verifier(
        pool=mock_pool,
        ledger=MagicMock(),
        sleep_func=lambda s: sleeps.append(s),
        random_func=lambda a, b: 1.0,
    )

    # Mock HTTP response: first returns 429, second returns success
    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.headers = {"Retry-After": "5"}

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {
        "results": [{"email": "test@gmail.com", "status": "valid", "valid": True}]
    }

    with patch("requests.post", side_effect=[resp_429, resp_200]) as mock_post:
        results, err = verifier._execute_http_bulk_request(
            chunk_emails=["test@gmail.com"],
            api_key="test_key_1",
            max_retries=4,
        )

        assert err is None
        assert results is not None
        assert len(results) == 1
        # Account pool should NOT have been rotated
        mock_pool.mark_account_exhausted.assert_not_called()
        # Backoff sleep should have been executed (5s + 1.0s jitter = 6.0s)
        assert any(s >= 5.0 for s in sleeps)


def test_mail7_rotates_only_on_confirmed_quota_exhaustion():
    """Verify account rotates when HTTP 402 or quota exceeded HTTP 403 is returned."""
    mock_pool = MagicMock(spec=Mail7AccountPool)
    acc1 = MagicMock(index=1, account_id="mail7_account_1", api_key="key_1", is_configured=True)
    acc2 = MagicMock(index=2, account_id="mail7_account_2", api_key="key_2", is_configured=True)
    mock_pool.get_active_account.side_effect = [acc1, acc2]
    mock_pool.mark_account_exhausted.return_value = acc2

    mock_ledger = MagicMock()
    mock_ledger.get_cached_result.return_value = None

    verifier = Mail7Verifier(
        pool=mock_pool,
        ledger=mock_ledger,
        sleep_func=lambda s: None,
    )

    # Account 1 reports quota exhaustion, Account 2 succeeds
    def fake_verify_chunk(chunk_emails, api_key, account_id, date_str, max_retries):
        if api_key == "key_1":
            return {}, "quota_exhausted"
        return {e: VerificationResult(email=e, status="valid", account_id=account_id) for e in chunk_emails}, None

    verifier._verify_chunk_with_bisection = fake_verify_chunk

    results, err = verifier.verify_bulk(["lead@gmail.com"])

    assert err is None
    assert len(results) == 1
    assert results[0].account_id == "mail7_account_2"
    # mark_account_exhausted must be called for Account 1
    mock_pool.mark_account_exhausted.assert_called_once_with(
        account_index=1,
        reason="HTTP 402/403 quota exhaustion",
    )


# ===========================================================================
# 3. Partial Lead Delivery in Mode='deliver' Tests
# ===========================================================================

def test_mode_deliver_never_re_scrapes_and_delivers_partial_queue():
    """Verify mode='deliver' strictly delivers whatever is in queue without scraping."""
    from src.main import DailyLeadAgent

    mock_state_mgr = MagicMock()
    mock_state_mgr.is_already_delivered_today.return_value = False

    mock_queue_mgr = MagicMock()
    # Queue has only 130 leads (less than target of 200)
    partial_leads = [{"email": f"partial_{i}@gmail.com"} for i in range(130)]
    mock_queue_mgr.get_queue_size.return_value = 130
    mock_queue_mgr.select_leads_for_delivery.return_value = (partial_leads, [])

    mock_delivery_mgr = MagicMock()
    mock_delivery_mgr.generate_lead_file.return_value = Path("output/leads_2026-11-12.txt")
    mock_delivery_mgr.send_daily_leads.return_value = True

    agent = DailyLeadAgent(
        target=200,
        state_manager=mock_state_mgr,
        queue_manager=mock_queue_mgr,
        delivery_manager=mock_delivery_mgr,
    )

    # Mock _process_and_fill_queue to fail if called
    agent._process_and_fill_queue = MagicMock(side_effect=AssertionError("Scraping should NOT be called in deliver mode!"))

    delivered_count = agent.run(mode="deliver", skip_scrape=True)

    assert delivered_count == 130
    # Delivery manager was invoked for all 130 leads
    mock_delivery_mgr.send_daily_leads.assert_called_once()
    # Delivery receipt recorded for 130 leads
    mock_state_mgr.record_delivery_receipt.assert_called_once()
    # Committed queue
    mock_queue_mgr.commit_delivered_leads.assert_called_once_with([])


def test_master_database_file_preserved_and_intact():
    """Verify master_leads.csv exists, has >= 5,400 rows, and is never corrupted."""
    master_file = Path("data/master_leads.csv")
    assert master_file.exists(), "master_leads.csv must exist!"
    with open(master_file, "r", encoding="utf-8") as f:
        row_count = sum(1 for _ in f) - 1  # exclude header
    assert row_count >= 5400, f"Master database should have >= 5400 records, found {row_count}"
