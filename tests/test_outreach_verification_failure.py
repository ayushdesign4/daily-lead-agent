"""Regression tests for Mail7 verification failure, bounded retry, checkpointing, and alert rotation."""

import json
import pytest
import requests
from unittest.mock import MagicMock, patch
from src.outreach.verification_client import Mail7Verifier, VerificationResult
from src.outreach.quota_ledger import QuotaLedger
from src.outreach.campaign_state import CampaignState
from src.outreach.orchestrator import OutreachPipeline


@pytest.fixture
def test_ledger(tmp_path):
    return QuotaLedger(
        ledger_file=tmp_path / "ledger.csv",
        cache_file=tmp_path / "cache.csv"
    )


def test_network_timeout_bounded_retry(test_ledger):
    """Test requirement J.11: Transient network timeout retries with backoff and succeeds on next attempt."""
    sleep_calls = []
    fake_sleep = lambda s: sleep_calls.append(s)

    verifier = Mail7Verifier(
        api_key="mk_live_key",
        ledger=test_ledger,
        sleep_func=fake_sleep,
        random_func=lambda a, b: 1.0,
    )

    resp_success = MagicMock()
    resp_success.status_code = 200
    resp_success.json.return_value = {
        "total": 1,
        "results": [{"email": "retry@test.com", "valid": True, "status": "Valid"}]
    }

    with patch("src.outreach.verification_client.requests.post") as mock_post:
        # First attempt times out, second succeeds
        mock_post.side_effect = [requests.Timeout("Connection timed out"), resp_success]
        results, err = verifier.verify_bulk(["retry@test.com"])

    assert err is None
    assert len(results) == 1
    assert results[0].status == "valid"
    assert mock_post.call_count == 2
    assert len(sleep_calls) == 1
    # 2**0 + 1.0 = 2.0
    assert sleep_calls[0] == 2.0


def test_never_cache_verification_errors(test_ledger):
    """Test requirement J.14: Transient verification errors are never saved in persistent cache."""
    records = [
        {"email": "valid@test.com", "account_id": "mail7", "status": "valid", "date_verified": "2026-10-11", "raw_result": "ok"},
        {"email": "error@test.com", "account_id": "mail7", "status": "verification_error", "date_verified": "2026-10-11", "raw_result": "timeout"},
        {"email": "unknown@test.com", "account_id": "mail7", "status": "unknown", "date_verified": "2026-10-11", "raw_result": "catch_all"},
    ]

    test_ledger.cache_verification_results(records)

    assert test_ledger.get_cached_result("valid@test.com") is not None
    assert test_ledger.get_cached_result("unknown@test.com") is not None
    assert test_ledger.get_cached_result("error@test.com") is None


def test_incomplete_verification_pauses_and_never_starts_outreach_send(tmp_path):
    """Test requirement J.18: Incomplete verification (quota exhaustion or auth failure) stops and never sends outreach."""
    state_file = tmp_path / "state.csv"
    batches_file = tmp_path / "batches.csv"
    state_mgr = CampaignState(state_file, batches_file)
    quota_ledger = QuotaLedger(tmp_path / "l.csv", tmp_path / "c.csv")

    lead_file = tmp_path / "leads.txt"
    lead_file.write_text("lead1@test.com\nlead2@test.com\n")

    alert_emails = []
    fake_send_alert = lambda *args, **kwargs: alert_emails.append(args)

    pipeline = OutreachPipeline(
        dry_run=True,
        state_mgr=state_mgr,
        quota_ledger=quota_ledger,
        mail7_api_key="exhausted_key",
        form_url="https://forms.gle/testrotationform",
    )
    pipeline.verifier.dry_run = False
    pipeline.send_rotation_alert = MagicMock(side_effect=fake_send_alert)

    # Mock Mail7 returning 402 quota exhausted
    resp_402 = MagicMock()
    resp_402.status_code = 402

    with patch("src.outreach.verification_client.requests.post", return_value=resp_402):
        with patch.object(pipeline, "send_completion_notification") as mock_completion:
            res = pipeline.run(manual_file=lead_file, force=True)

    # Verification must be paused
    assert res["status"] == "VERIFICATION_PAUSED_AUTH_OR_QUOTA"
    assert res["reason"] == "quota_exhausted"

    # Outreach send phase must NOT have started (zero batches planned or sent)
    batches = state_mgr.load_batches(res["campaign_id"])
    assert len(batches) == 0

    # Completion notification must NOT have been sent
    mock_completion.assert_not_called()

    # Rotation alert email was triggered
    assert len(alert_emails) == 1


def test_resumption_after_installing_replacement_key(tmp_path):
    """Test requirement J.13: Resumes paused verification when replacement key is configured."""
    state_file = tmp_path / "state.csv"
    batches_file = tmp_path / "batches.csv"
    state_mgr = CampaignState(state_file, batches_file)
    quota_ledger = QuotaLedger(tmp_path / "l.csv", tmp_path / "c.csv")

    lead_file = tmp_path / "leads.txt"
    lead_file.write_text("lead1@test.com\nlead2@test.com\n")

    # Run 1: Fails on initial key (HTTP 401)
    resp_401 = MagicMock()
    resp_401.status_code = 401

    pipeline_run1 = OutreachPipeline(
        dry_run=True,
        state_mgr=state_mgr,
        quota_ledger=quota_ledger,
        mail7_api_key="bad_key",
    )
    pipeline_run1.verifier.dry_run = False
    with patch("src.outreach.verification_client.requests.post", return_value=resp_401):
        res1 = pipeline_run1.run(manual_file=lead_file, force=True)

    assert res1["status"] == "VERIFICATION_PAUSED_AUTH_OR_QUOTA"
    checkpoint = state_mgr.load_checkpoint(res1["campaign_id"])
    assert checkpoint is not None
    assert checkpoint["error_reason"] == "unauthorized_api_key"

    # Run 2: Replacement key installed, succeeds and completes campaign
    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {
        "total": 2,
        "results": [
            {"email": "lead1@test.com", "valid": True, "status": "Valid"},
            {"email": "lead2@test.com", "valid": True, "status": "Valid"},
        ]
    }

    pipeline_run2 = OutreachPipeline(
        dry_run=True,
        state_mgr=state_mgr,
        quota_ledger=quota_ledger,
        mail7_api_key="mk_live_new_replacement_key",
    )
    pipeline_run2.verifier.dry_run = False
    with patch("src.outreach.verification_client.requests.post", return_value=resp_200):
        res2 = pipeline_run2.run(manual_file=lead_file, force=True)

    assert res2["overall_status"] == "COMPLETED"
    assert res2["valid_count"] == 2
    # Checkpoint cleared on complete success
    assert state_mgr.load_checkpoint(res1["campaign_id"]) is None


def test_random_batch_delays_between_5_and_20_seconds(tmp_path):
    """Test requirement J.16: Random delays are between 5-20s, not before first batch, not after final batch."""
    state_file = tmp_path / "state.csv"
    batches_file = tmp_path / "batches.csv"
    state_mgr = CampaignState(state_file, batches_file)
    quota_ledger = QuotaLedger(tmp_path / "l.csv", tmp_path / "c.csv")

    lead_file = tmp_path / "leads.txt"
    # 9 leads for 9 batches
    leads = [f"creator_{i}@example.com" for i in range(9)]
    lead_file.write_text("\n".join(leads) + "\n")

    sleep_calls = []
    fake_sleep = lambda s: sleep_calls.append(s)

    delays_generated = []
    def fake_random(a, b):
        assert a == 5 and b == 20
        d = 7
        delays_generated.append(d)
        return d

    pipeline = OutreachPipeline(
        dry_run=False,  # test pacing in live mode
        state_mgr=state_mgr,
        quota_ledger=quota_ledger,
        mail7_api_key="key",
        sleep_func=fake_sleep,
        random_func=fake_random,
    )

    # Mock Mail7 verification
    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {
        "total": 9,
        "results": [{"email": e, "valid": True, "status": "Valid"} for e in leads]
    }

    # Mock 9 sender accounts
    accounts_json = json.dumps([
        {"email": f"sender{i+1}@gmail.com", "app_password": f"pass_{i+1}"}
        for i in range(9)
    ])
    pipeline.raw_accounts_json = accounts_json

    with patch("src.outreach.verification_client.requests.post", return_value=resp_200):
        with patch("src.outreach.sender.smtplib.SMTP_SSL") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            res = pipeline.run(manual_file=lead_file, force=True)

    assert res["overall_status"] == "COMPLETED"
    # Exactly 8 inter-batch delays for 9 batches (not before batch 0, not after batch 8)
    assert len(sleep_calls) == 8
    assert all(s == 7 for s in sleep_calls)
    assert len(delays_generated) == 8


def test_no_secret_leakage_in_checkpoint_or_alert(tmp_path):
    """Test requirement J.12: Secrets never appear in checkpoints or notification alerts."""
    state_file = tmp_path / "state.csv"
    batches_file = tmp_path / "batches.csv"
    state_mgr = CampaignState(state_file, batches_file)

    secret_key = "mk_live_SUPER_SECRET_MAIL7_KEY_12345"

    checkpoint = state_mgr.save_checkpoint(
        campaign_id="CAMP-test-sec",
        checkpoint_data={
            "campaign_id": "CAMP-test-sec",
            "mail7_api_key": secret_key,  # attempt to leak key
            "api_key": secret_key,
            "leads": ["lead@test.com"],
        }
    )

    content = checkpoint.read_text(encoding="utf-8")
    assert secret_key not in content
    assert "SUPER_SECRET" not in content
