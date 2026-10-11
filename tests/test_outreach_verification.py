"""Tests for Mail7 bulk email verification client: single request, mapping, rate-limits, and quota safety."""

import pytest
import requests
from unittest.mock import MagicMock, patch
from src.outreach.verification_client import Mail7Verifier, VerificationResult
from src.outreach.quota_ledger import QuotaLedger


@pytest.fixture
def test_ledger(tmp_path):
    return QuotaLedger(
        ledger_file=tmp_path / "ledger.csv",
        cache_file=tmp_path / "cache.csv"
    )


def test_200_emails_one_bulk_request(test_ledger):
    """Test requirement J.1 & J.4: 200 emails use exactly ONE bulk API request with correct headers and multipart field."""
    verifier = Mail7Verifier(api_key="mk_live_testkey123", ledger=test_ledger)

    emails = [f"lead_{i:03d}@example.com" for i in range(200)]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "total": 200,
        "results": [
            {"email": e, "valid": True, "status": "Valid", "details": "Email exists"}
            for e in emails
        ]
    }

    with patch("src.outreach.verification_client.requests.post", return_value=mock_resp) as mock_post:
        results, err = verifier.verify_bulk(emails)

    assert err is None
    assert len(results) == 200
    assert all(r.is_deliverable for r in results)

    # Exactly ONE HTTP request made
    assert mock_post.call_count == 1
    call_args, call_kwargs = mock_post.call_args

    # Correct endpoint
    assert "https://mail7.net/api/validate-bulk" in call_args[0]
    # Correct auth header
    assert call_kwargs["headers"]["X-API-Key"] == "mk_live_testkey123"
    # Correct multipart form field 'emails'
    files = call_kwargs["files"]
    assert "emails" in files
    payload_emails = files["emails"][1].split("\n")
    assert len(payload_emails) == 200
    assert payload_emails[0] == "lead_000@example.com"
    assert payload_emails[-1] == "lead_199@example.com"


def test_cached_results_excluded_from_bulk_payload(test_ledger):
    """Test requirement J.2 & J.14: Definitive cached results are excluded from the bulk payload."""
    # Pre-cache 20 leads
    pre_cached = [
        {"email": f"cached_{i}@example.com", "account_id": "mail7", "status": "valid", "date_verified": "2026-10-10", "raw_result": "ok"}
        for i in range(20)
    ]
    test_ledger.cache_verification_results(pre_cached)

    verifier = Mail7Verifier(api_key="mk_live_testkey123", ledger=test_ledger)

    # Submit 30 leads (20 cached + 10 new)
    all_emails = [f"cached_{i}@example.com" for i in range(20)] + [f"new_{i}@example.com" for i in range(10)]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "total": 10,
        "results": [
            {"email": f"new_{i}@example.com", "valid": True, "status": "Valid", "details": "ok"}
            for i in range(10)
        ]
    }

    with patch("src.outreach.verification_client.requests.post", return_value=mock_resp) as mock_post:
        results, err = verifier.verify_bulk(all_emails)

    assert err is None
    assert len(results) == 30
    assert mock_post.call_count == 1

    # Payload must only contain the 10 unresolved addresses
    files = mock_post.call_args[1]["files"]
    submitted = files["emails"][1].split("\n")
    assert len(submitted) == 10
    assert all(e.startswith("new_") for e in submitted)


def test_all_cached_makes_zero_requests(test_ledger):
    """When all emails are resolved in cache, zero HTTP requests are made."""
    test_ledger.cache_verification_results([
        {"email": "cached@test.com", "account_id": "mail7", "status": "valid", "date_verified": "2026-10-10", "raw_result": "ok"}
    ])
    verifier = Mail7Verifier(api_key="mk_live_testkey123", ledger=test_ledger)

    with patch("src.outreach.verification_client.requests.post") as mock_post:
        results, err = verifier.verify_bulk(["cached@test.com"])

    assert err is None
    assert len(results) == 1
    assert results[0].status == "valid"
    assert results[0].account_id == "cache"
    assert mock_post.call_count == 0


def test_mail7_result_mapping_valid_not_valid_unknown(test_ledger):
    """Test requirement J.5: Valid, Not Valid, and Unknown status mapping per Mail7 specification."""
    verifier = Mail7Verifier(api_key="mk_live_testkey123", ledger=test_ledger)
    emails = ["valid@test.com", "invalid@test.com", "unknown@test.com"]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "total": 3,
        "results": [
            {"email": "valid@test.com", "valid": True, "status": "Valid", "details": "Accepted"},
            {"email": "invalid@test.com", "valid": False, "status": "Not Valid", "details": "Mailbox not found"},
            {"email": "unknown@test.com", "valid": None, "status": "Unknown", "details": "Catch-all server"},
        ]
    }

    with patch("src.outreach.verification_client.requests.post", return_value=mock_resp):
        results, err = verifier.verify_bulk(emails)

    assert err is None
    r_map = {r.email: r for r in results}

    assert r_map["valid@test.com"].status == "valid"
    assert r_map["valid@test.com"].is_deliverable is True

    assert r_map["invalid@test.com"].status == "invalid"
    assert r_map["invalid@test.com"].is_deliverable is False

    assert r_map["unknown@test.com"].status == "unknown"
    assert r_map["unknown@test.com"].is_deliverable is False


def test_out_of_order_matching_by_normalized_email(test_ledger):
    """Test requirement J.6: Out-of-order results are matched by normalized email, never by array index."""
    verifier = Mail7Verifier(api_key="mk_live_testkey123", ledger=test_ledger)
    emails = ["first@test.com", "second@test.com", "third@test.com"]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    # Provider returns results in reverse order with uppercase emails
    mock_resp.json.return_value = {
        "total": 3,
        "results": [
            {"email": "THIRD@TEST.COM", "valid": True, "status": "Valid"},
            {"email": "FIRST@TEST.COM", "valid": False, "status": "Not Valid"},
            {"email": "SECOND@TEST.COM", "valid": None, "status": "Unknown"},
        ]
    }

    with patch("src.outreach.verification_client.requests.post", return_value=mock_resp):
        results, err = verifier.verify_bulk(emails)

    assert err is None
    r_map = {r.email: r for r in results}
    assert r_map["first@test.com"].status == "invalid"
    assert r_map["second@test.com"].status == "unknown"
    assert r_map["third@test.com"].status == "valid"


def test_missing_duplicate_unexpected_bulk_results(test_ledger):
    """Test requirement J.7: Detect missing, duplicate, and unexpected addresses safely."""
    verifier = Mail7Verifier(api_key="mk_live_testkey123", ledger=test_ledger)
    emails = ["expected_1@test.com", "expected_2@test.com", "missing@test.com"]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "total": 3,
        "results": [
            {"email": "expected_1@test.com", "valid": True, "status": "Valid"},
            {"email": "expected_1@test.com", "valid": True, "status": "Valid"},  # duplicate
            {"email": "unexpected@test.com", "valid": True, "status": "Valid"},  # unexpected
            {"email": "expected_2@test.com", "valid": False, "status": "Not Valid"},
            # missing@test.com is omitted
        ]
    }

    with patch("src.outreach.verification_client.requests.post", return_value=mock_resp):
        results, err = verifier.verify_bulk(emails)

    r_map = {r.email: r for r in results}
    assert r_map["expected_1@test.com"].status == "valid"
    assert r_map["expected_2@test.com"].status == "invalid"
    # Missing address must be flagged as verification_error, not marked invalid
    assert r_map["missing@test.com"].status == "verification_error"
    assert r_map["missing@test.com"].reason == "missing_from_bulk_response"


def test_rate_limit_429_honors_retry_after(test_ledger):
    """Test requirement J.8: Honors HTTP 429 Retry-After header with bounded backoff and succeeds on retry."""
    sleep_calls = []
    fake_sleep = lambda s: sleep_calls.append(s)

    verifier = Mail7Verifier(
        api_key="mk_live_testkey123",
        ledger=test_ledger,
        sleep_func=fake_sleep,
        random_func=lambda a, b: 0.5,
    )

    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.headers = {"Retry-After": "4"}

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {
        "total": 1,
        "results": [{"email": "retry@test.com", "valid": True, "status": "Valid"}]
    }

    with patch("src.outreach.verification_client.requests.post", side_effect=[resp_429, resp_200]) as mock_post:
        results, err = verifier.verify_bulk(["retry@test.com"])

    assert err is None
    assert results[0].status == "valid"
    assert mock_post.call_count == 2
    # Slept retry_after (4) + jitter (0.5) = 4.5
    assert len(sleep_calls) == 1
    assert sleep_calls[0] == 4.5


def test_unauthorized_key_401_and_403(test_ledger):
    """Test requirement J.9: 401 and 403 unauthorized keys halt immediately without retry."""
    verifier = Mail7Verifier(api_key="bad_key", ledger=test_ledger)

    resp_401 = MagicMock()
    resp_401.status_code = 401

    with patch("src.outreach.verification_client.requests.post", return_value=resp_401) as mock_post:
        results, err = verifier.verify_bulk(["test@example.com"])

    assert err == "unauthorized_api_key"
    assert mock_post.call_count == 1
    assert results[0].status == "verification_error"


def test_monthly_quota_exhaustion_stops_immediately(test_ledger):
    """Test requirement J.10: HTTP 402 or 403 quota exhaustion stops immediately without retry."""
    verifier = Mail7Verifier(api_key="key", ledger=test_ledger)

    resp_402 = MagicMock()
    resp_402.status_code = 402

    with patch("src.outreach.verification_client.requests.post", return_value=resp_402) as mock_post:
        results, err = verifier.verify_bulk(["test@example.com"])

    assert err == "quota_exhausted"
    assert mock_post.call_count == 1
    assert results[0].status == "verification_error"
