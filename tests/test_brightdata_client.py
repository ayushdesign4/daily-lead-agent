"""
Unit and integration tests for BrightDataClient and Bright Data SERP API migration.
Tests all scenarios using mocks with ZERO live API calls or credits consumed.
"""

import json
from unittest.mock import MagicMock, patch
from pathlib import Path
import pytest
import requests

from src.brightdata_client import (
    BrightDataClient,
    BrightDataError,
    BrightDataAuthError,
    BrightDataCreditExhaustedError,
    BrightDataPermissionError,
)
from src.main import DailyLeadAgent
from src.state_manager import StateManager


# --- Fixtures ---

@pytest.fixture
def sample_organic_response():
    """Standard Bright Data parsed SERP response."""
    return {
        "general": {
            "query": "site:youtube.com \"gaming\" \"Business Inquiries\" \"gmail.com\" India",
            "results_cnt": 850
        },
        "organic": [
            {
                "position": 1,
                "title": "Pro Gamer India - YouTube",
                "link": "https://www.youtube.com/@progamerindia",
                "display_link": "https://www.youtube.com › @progamerindia",
                "description": "For business inquiries: progamer.biz@gmail.com. Daily gaming videos."
            },
            {
                "position": 2,
                "title": "Speedrunner Showcase - YouTube",
                "link": "https://www.youtube.com/@speedrunner",
                "display_link": "https://www.youtube.com › @speedrunner",
                "description": "Contact me at: runner.india@gmail.com for sponsorships."
            },
            {
                "position": 3,
                "title": "Game Reviews India - YouTube",
                "link": "https://www.youtube.com/@gamereviews",
                "display_link": "https://www.youtube.com › @gamereviews",
                "description": "Email: reviews.contact @ gmail.com."
            }
        ]
    }


# --- Tests ---

def test_missing_tokens_diagnostic(tmp_path):
    """Ensure clear diagnostic error when no tokens are configured, without leaking secrets."""
    state_file = tmp_path / "brightdata_state.json"
    client = BrightDataClient(tokens=[None, None, None], state_file=state_file)
    with pytest.raises(BrightDataAuthError) as exc_info:
        client.get_active_account()
    assert "No Bright Data API tokens configured" in str(exc_info.value)
    assert "BRIGHTDATA_API_TOKEN_1" in str(exc_info.value)


def test_build_search_url():
    """Verify Google dork URL encoding, India location (gl=in), English (hl=en), tbs=qdr:m3, and start offsets."""
    client = BrightDataClient(tokens=["tok_1", "tok_2", "tok_3"])

    # Page 1 (offset 0)
    url_p1 = client.build_search_url('site:youtube.com "tech" "Business Inquiries" "gmail.com" India', page=0)
    assert "gl=in" in url_p1
    assert "hl=en" in url_p1
    assert "tbs=qdr%3Am3" in url_p1 or "tbs=qdr:m3" in url_p1
    assert "start=0" in url_p1
    assert "brd_json=1" in url_p1

    # Page 2 (offset 10)
    url_p2 = client.build_search_url('site:youtube.com "tech"', page=1)
    assert "start=10" in url_p2

    # Page 20 (offset 190)
    url_p20 = client.build_search_url('site:youtube.com "tech"', page=19)
    assert "start=190" in url_p20


@patch("requests.post")
def test_execute_single_request_success(mock_post, tmp_path, sample_organic_response):
    """Verify single request dispatch, header authentication, and organic result extraction."""
    state_file = tmp_path / "brightdata_state.json"
    client = BrightDataClient(
        tokens=["test_token_1", "test_token_2", "test_token_3"],
        zones=["zone_1", "zone_2", "zone_3"],
        state_file=state_file
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {}
    mock_resp.json.return_value = sample_organic_response
    mock_post.return_value = mock_resp

    target_url = client.build_search_url("query test", page=0)
    results = client._execute_single_request(target_url)

    assert len(results) == 3
    assert results[0]["title"] == "Pro Gamer India - YouTube"
    assert results[0]["link"] == "https://www.youtube.com/@progamerindia"

    # Verify authorization header and payload
    call_args = mock_post.call_args
    assert call_args[1]["headers"]["Authorization"] == "Bearer test_token_1"
    assert call_args[1]["json"]["zone"] == "zone_1"


@patch("requests.post")
def test_run_search_batch_10_queries_with_early_stopping(mock_post, tmp_path, sample_organic_response):
    """
    Verify 10-query batch execution, Apify-compatible schema mapping,
    and early stopping when Google returns empty organic results.
    """
    state_file = tmp_path / "brightdata_state.json"
    client = BrightDataClient(
        tokens=["test_token_1", None, None],
        state_file=state_file,
        max_pages=20,
        max_queries=10
    )

    # Simulate: Page 1 returns 3 results, Page 2 returns 0 results (triggers early stop)
    page1_resp = MagicMock()
    page1_resp.status_code = 200
    page1_resp.headers = {}
    page1_resp.json.return_value = sample_organic_response

    empty_resp = MagicMock()
    empty_resp.status_code = 200
    empty_resp.headers = {}
    empty_resp.json.return_value = {"organic": []}

    mock_post.side_effect = [page1_resp, empty_resp] * 10

    queries = [f'site:youtube.com "niche_{i}"' for i in range(10)]
    dataset_items = client.run_search_batch(queries, max_pages=20)

    # 10 queries * 3 results from page 1 = 30 items
    assert len(dataset_items) == 30

    # Verify Apify data contract fields: title, url, snippet, searchQuery
    first_item = dataset_items[0]
    assert "title" in first_item
    assert "url" in first_item
    assert "snippet" in first_item
    assert "searchQuery" in first_item
    assert first_item["url"] == "https://www.youtube.com/@progamerindia"


@patch("requests.post")
def test_account_rotation_on_402_quota_exhausted(mock_post, tmp_path, sample_organic_response):
    """Verify that HTTP 402 marks Account 1 as EXHAUSTED and immediately rotates to Account 2."""
    state_file = tmp_path / "brightdata_state.json"
    client = BrightDataClient(
        tokens=["token_acc_1", "token_acc_2", "token_acc_3"],
        zones=["zone_1", "zone_2", "zone_3"],
        state_file=state_file,
        sleep_func=lambda s: None
    )

    # Account 1 returns 402 Payment Required; Account 2 succeeds with 200
    resp_402 = MagicMock()
    resp_402.status_code = 402
    resp_402.text = "Payment required / monthly limit reached"
    resp_402.headers = {"x-brd-err-code": "insufficient_funds"}

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.headers = {}
    resp_200.json.return_value = sample_organic_response

    mock_post.side_effect = [resp_402, resp_200]

    target_url = client.build_search_url("query test", page=0)
    results = client._execute_single_request(target_url)

    assert len(results) == 3
    # Check that rotation occurred and state updated
    assert client.state["active_account_index"] == 1
    assert client.state["accounts"][0]["status"] == "EXHAUSTED"
    assert client.state["accounts"][1]["status"] == "ACTIVE"


@patch("requests.post")
def test_all_accounts_exhausted_raises_credit_exhausted_error(mock_post, tmp_path):
    """Verify that when all 3 accounts return 402, BrightDataCreditExhaustedError is raised."""
    state_file = tmp_path / "brightdata_state.json"
    client = BrightDataClient(
        tokens=["token_acc_1", "token_acc_2", "token_acc_3"],
        state_file=state_file,
        sleep_func=lambda s: None
    )

    resp_402 = MagicMock()
    resp_402.status_code = 402
    resp_402.text = "Quota exhausted"
    resp_402.headers = {"x-brd-err-code": "insufficient_funds"}

    mock_post.return_value = resp_402

    target_url = client.build_search_url("query test", page=0)
    with pytest.raises(BrightDataCreditExhaustedError) as exc_info:
        client._execute_single_request(target_url)

    assert "exhausted their monthly quota" in str(exc_info.value)
    assert all(acc["status"] == "EXHAUSTED" for acc in client.state["accounts"])


@patch("requests.post")
def test_http_401_invalid_auth_rotates_to_next_account(mock_post, tmp_path, sample_organic_response):
    """Verify that HTTP 401 marks account as INVALID_AUTH and rotates without infinite loop."""
    state_file = tmp_path / "brightdata_state.json"
    client = BrightDataClient(
        tokens=["revoked_token", "valid_token_2", None],
        state_file=state_file,
        sleep_func=lambda s: None
    )

    resp_401 = MagicMock()
    resp_401.status_code = 401
    resp_401.text = "Unauthorized - invalid token"
    resp_401.headers = {}

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.headers = {}
    resp_200.json.return_value = sample_organic_response

    mock_post.side_effect = [resp_401, resp_200]

    target_url = client.build_search_url("query test", page=0)
    results = client._execute_single_request(target_url)

    assert len(results) == 3
    assert client.state["active_account_index"] == 1
    assert client.state["accounts"][0]["status"] == "INVALID_AUTH"


@patch("requests.post")
def test_http_429_rate_limit_retries_without_rotation(mock_post, tmp_path, sample_organic_response):
    """Verify that HTTP 429 does NOT rotate accounts, but retries with backoff."""
    state_file = tmp_path / "brightdata_state.json"
    client = BrightDataClient(
        tokens=["token_1", "token_2", "token_3"],
        state_file=state_file,
        sleep_func=lambda s: None
    )

    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.text = "Too Many Requests - Concurrency limit exceeded"
    resp_429.headers = {}

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.headers = {}
    resp_200.json.return_value = sample_organic_response

    mock_post.side_effect = [resp_429, resp_200]

    target_url = client.build_search_url("query test", page=0)
    results = client._execute_single_request(target_url)

    assert len(results) == 3
    # Active account MUST remain Account 1 (index 0)
    assert client.state["active_account_index"] == 0
    assert client.state["accounts"][0]["status"] == "ACTIVE"


@patch("requests.post")
def test_http_500_server_error_retries_without_rotation(mock_post, tmp_path, sample_organic_response):
    """Verify that HTTP 500 does NOT rotate accounts, but retries with backoff."""
    state_file = tmp_path / "brightdata_state.json"
    client = BrightDataClient(
        tokens=["token_1", "token_2", "token_3"],
        state_file=state_file,
        sleep_func=lambda s: None
    )

    resp_500 = MagicMock()
    resp_500.status_code = 500
    resp_500.text = "Internal Server Error"
    resp_500.headers = {}

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.headers = {}
    resp_200.json.return_value = sample_organic_response

    mock_post.side_effect = [resp_500, resp_200]

    target_url = client.build_search_url("query test", page=0)
    results = client._execute_single_request(target_url)

    assert len(results) == 3
    assert client.state["active_account_index"] == 0


@patch("requests.post")
def test_mid_batch_recovery_preserves_completed_queries(mock_post, tmp_path, sample_organic_response):
    """
    Verify mid-batch recovery:
    Query 1 succeeds on Account 1.
    Query 2 hits 402 on Account 1.
    Account rotates to Account 2 and executes Query 2.
    Query 1 is NOT repeated, and all collected results are returned.
    """
    state_file = tmp_path / "brightdata_state.json"
    client = BrightDataClient(
        tokens=["acc_1_tok", "acc_2_tok", None],
        zones=["zone_1", "zone_2", "zone_3"],
        state_file=state_file,
        max_pages=1,
        sleep_func=lambda s: None
    )

    resp_q1 = MagicMock()
    resp_q1.status_code = 200
    resp_q1.headers = {}
    resp_q1.json.return_value = {
        "organic": [{"title": "Q1 Creator", "link": "https://youtube.com/q1", "description": "q1@gmail.com"}]
    }

    resp_q2_402 = MagicMock()
    resp_q2_402.status_code = 402
    resp_q2_402.text = "Account 1 quota exceeded"
    resp_q2_402.headers = {"x-brd-err-code": "insufficient_funds"}

    resp_q2_200 = MagicMock()
    resp_q2_200.status_code = 200
    resp_q2_200.headers = {}
    resp_q2_200.json.return_value = {
        "organic": [{"title": "Q2 Creator", "link": "https://youtube.com/q2", "description": "q2@gmail.com"}]
    }

    mock_post.side_effect = [resp_q1, resp_q2_402, resp_q2_200]

    dataset = client.run_search_batch(["query_1", "query_2"], max_pages=1)

    assert len(dataset) == 2
    assert dataset[0]["title"] == "Q1 Creator"
    assert dataset[1]["title"] == "Q2 Creator"
    assert client.state["active_account_index"] == 1
    assert client.state["accounts"][0]["status"] == "EXHAUSTED"


def test_monthly_reset_logic(tmp_path):
    """Verify that when billing month changes, all accounts automatically reset to ACTIVE."""
    state_file = tmp_path / "brightdata_state.json"

    # Pre-populate state file with exhausted accounts from previous month (e.g. 2026-09)
    old_state = {
        "active_account_index": 2,
        "current_billing_month": "2026-09",
        "accounts": [
            {"index": 0, "status": "EXHAUSTED", "exhausted_at": "2026-09-15T00:00:00Z"},
            {"index": 1, "status": "EXHAUSTED", "exhausted_at": "2026-09-20T00:00:00Z"},
            {"index": 2, "status": "EXHAUSTED", "exhausted_at": "2026-09-25T00:00:00Z"},
        ]
    }
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(old_state, f)

    # Initialize client (will detect current month != 2026-09)
    client = BrightDataClient(tokens=["t1", "t2", "t3"], state_file=state_file)

    assert client.state["active_account_index"] == 0
    assert client.state["current_billing_month"] != "2026-09"
    assert all(acc["status"] == "ACTIVE" for acc in client.state["accounts"])
    assert all(acc["exhausted_at"] is None for acc in client.state["accounts"])


def test_main_orchestrator_integration_with_brightdata(tmp_path):
    """
    Verify end-to-end integration of DailyLeadAgent with BrightDataClient in test_mode.
    Zero external network calls made.
    """
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    data_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    master_file = data_dir / "master.csv"
    queue_file = data_dir / "queue.csv"
    niches_file = data_dir / "used_niches.csv"
    runs_file = data_dir / "daily_runs.csv"

    state_mgr = StateManager(master_file, queue_file, niches_file, runs_file)

    agent = DailyLeadAgent(
        target=10,
        dry_run=True,
        test_mode=True,
        state_manager=state_mgr
    )

    # Run in prepare mode
    result_count = agent.run(force=True, mode="prepare")
    assert result_count >= 10
    assert agent.queue_manager.get_queue_size() >= 10


def test_zone_pairing_and_rotation(tmp_path):
    """
    Verify exact token-to-zone pairings and zone rotation:
    - Account 1 pairs token_1 with zone token_1
    - Account 2 pairs token_2 with zone token_22
    - Account 3 pairs token_3 with zone token_333
    """
    state_file = tmp_path / "brightdata_state.json"
    client = BrightDataClient(
        tokens=["fake_tok_1", "fake_tok_2", "fake_tok_3"],
        state_file=state_file
    )

    # 1. Default zone configuration matches user's exact specification
    assert client.zones == ["token_1", "token_22", "token_333"]

    # 2. Account 1 active
    idx, tok, zone = client.get_active_account()
    assert idx == 0
    assert tok == "fake_tok_1"
    assert zone == "token_1"

    # 3. Rotate to Account 2
    idx2, tok2, zone2 = client.mark_account_exhausted(0, reason="test_quota")
    assert idx2 == 1
    assert tok2 == "fake_tok_2"
    assert zone2 == "token_22"

    # 4. Rotate to Account 3
    idx3, tok3, zone3 = client.mark_account_exhausted(1, reason="test_quota")
    assert idx3 == 2
    assert tok3 == "fake_tok_3"
    assert zone3 == "token_333"
