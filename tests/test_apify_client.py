"""Tests for ApifyClient payload construction, error handling, and credit exhaustion."""

import pytest
import requests
from unittest.mock import patch, MagicMock
from src.apify_client import (
    ApifyClient,
    ApifyAuthError,
    ApifyCreditExhaustedError,
    ApifyTimeoutError,
    ApifyError,
)


def test_build_actor_input():
    client = ApifyClient(token="mock_token")
    queries = [f"query {i}" for i in range(15)]  # Pass 15 queries

    actor_input = client.build_actor_input(queries)

    # Must clamp to maximum 10 queries per specification Section 3
    input_queries = actor_input["queries"].split("\n")
    assert len(input_queries) == 10
    assert actor_input["maxPagesPerQuery"] == 30
    assert actor_input["countryCode"] == "in"
    assert actor_input["languageCode"] == "en"
    assert actor_input["mobileResults"] is False
    assert actor_input["saveHtml"] is False
    assert actor_input["tbs"] == "qdr:m3"


@patch("requests.get")
def test_check_account_status_auth_error(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = "Unauthorized token"
    mock_get.return_value = mock_resp

    client = ApifyClient(token="bad_token")
    with pytest.raises(ApifyAuthError):
        client.check_account_status()


@patch("requests.get")
def test_check_account_status_over_limit(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": {
            "limits": {"isOverLimit": True}
        }
    }
    mock_get.return_value = mock_resp

    client = ApifyClient(token="limited_token")
    with pytest.raises(ApifyCreditExhaustedError):
        client.check_account_status()


@patch("requests.get")
@patch("requests.post")
def test_run_search_batch_credit_exhausted(mock_post, mock_get):
    # check_account_status passes
    mock_status_resp = MagicMock()
    mock_status_resp.status_code = 200
    mock_status_resp.json.return_value = {"data": {"limits": {"isOverLimit": False}}}
    mock_get.return_value = mock_status_resp

    # post to start run fails with 402 Payment Required
    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 402
    mock_post_resp.text = "Monthly usage credit exhausted"
    mock_post.return_value = mock_post_resp

    client = ApifyClient(token="valid_token")
    with pytest.raises(ApifyCreditExhaustedError):
        client.run_search_batch(["test query"])


@patch("requests.get")
@patch("requests.post")
def test_run_search_batch_platform_timed_out(mock_post, mock_get):
    """When Apify actor status transitions to TIMED-OUT on the platform, raise ApifyTimeoutError."""
    # check_account_status passes
    mock_status_resp = MagicMock()
    mock_status_resp.status_code = 200
    mock_status_resp.json.return_value = {"data": {"limits": {"isOverLimit": False}}}

    # post to start run succeeds
    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 200
    mock_post_resp.json.return_value = {"data": {"id": "run_123", "defaultDatasetId": "ds_123"}}
    mock_post.return_value = mock_post_resp

    # Polling returns TIMED-OUT status from Apify platform
    mock_poll_resp = MagicMock()
    mock_poll_resp.status_code = 200
    mock_poll_resp.json.return_value = {
        "data": {
            "status": "TIMED-OUT",
            "statusMessage": "Actor run timed out on platform"
        }
    }

    mock_get.side_effect = [mock_status_resp, mock_poll_resp]

    client = ApifyClient(token="valid_token")
    with patch("time.sleep", return_value=None):
        with pytest.raises(ApifyTimeoutError) as exc_info:
            client.run_search_batch(["test query"])

    assert "timed out on apify platform" in str(exc_info.value).lower()


@patch("requests.get")
@patch("requests.post")
def test_run_search_batch_polls_indefinitely_until_succeeded(mock_post, mock_get):
    """Ensure client does NOT timeout client-side; keeps polling past multiple iterations until SUCCEEDED."""
    mock_status_resp = MagicMock()
    mock_status_resp.status_code = 200
    mock_status_resp.json.return_value = {"data": {"limits": {"isOverLimit": False}}}

    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 200
    mock_post_resp.json.return_value = {"data": {"id": "run_999", "defaultDatasetId": "ds_999"}}
    mock_post.return_value = mock_post_resp

    mock_running_resp = MagicMock()
    mock_running_resp.status_code = 200
    mock_running_resp.json.return_value = {"data": {"status": "RUNNING"}}

    mock_succeeded_resp = MagicMock()
    mock_succeeded_resp.status_code = 200
    mock_succeeded_resp.json.return_value = {"data": {"status": "SUCCEEDED"}}

    mock_dataset_resp = MagicMock()
    mock_dataset_resp.status_code = 200
    mock_dataset_resp.json.return_value = [{"title": "Test Lead", "snippet": "contact@lead.com"}]

    # Simulates polling: status check, 5 RUNNING polls, then SUCCEEDED, then fetch dataset
    mock_get.side_effect = [
        mock_status_resp,
        mock_running_resp,
        mock_running_resp,
        mock_running_resp,
        mock_running_resp,
        mock_running_resp,
        mock_succeeded_resp,
        mock_dataset_resp,
    ]

    client = ApifyClient(token="valid_token")
    with patch("time.sleep", return_value=None):
        items = client.run_search_batch(["site:youtube.com 'motivation'"], poll_interval=15)

    assert len(items) == 1
    assert items[0]["snippet"] == "contact@lead.com"
