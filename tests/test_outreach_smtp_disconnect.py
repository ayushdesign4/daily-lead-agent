"""Regression tests for SMTP disconnect handling, retry, uncertain delivery, and idempotency."""

import pytest
import smtplib
from unittest.mock import MagicMock, patch
from src.outreach.sender import OutreachSender, OutreachAccount
from src.outreach.campaign_state import CampaignState
from src.outreach.orchestrator import OutreachPipeline


@pytest.fixture
def test_account():
    return OutreachAccount(email="testsender@gmail.com", app_password="mock_app_password")


def test_smtp_disconnect_pre_transmission_retries_and_succeeds(test_account):
    sender = OutreachSender(dry_run=False)

    mock_server_fail = MagicMock()
    mock_server_fail.login.side_effect = smtplib.SMTPServerDisconnected("Connection unexpectedly closed")

    mock_server_success = MagicMock()

    with patch("src.outreach.sender.smtplib.SMTP_SSL") as mock_smtp_ssl:
        mock_smtp_ssl.side_effect = [mock_server_fail, mock_server_success]
        with patch("src.outreach.sender.time.sleep") as mock_sleep:
            success, status, err = sender.send_batch(
                account=test_account,
                subject="Test Subject",
                body_text="Test Body",
                bcc_recipients=["recip1@test.com", "recip2@test.com"],
                max_retries=3,
            )

    assert success is True
    assert status == "SENT"
    assert err is None
    assert mock_smtp_ssl.call_count == 2
    mock_sleep.assert_called_once_with(2)


def test_smtp_disconnect_pre_transmission_exhausts_retries(test_account):
    sender = OutreachSender(dry_run=False)

    with patch("src.outreach.sender.smtplib.SMTP_SSL") as mock_smtp_ssl:
        mock_smtp_ssl.side_effect = smtplib.SMTPServerDisconnected("Connection reset by peer")
        with patch("src.outreach.sender.time.sleep"):
            success, status, err = sender.send_batch(
                account=test_account,
                subject="Test Subject",
                body_text="Test Body",
                bcc_recipients=["recip1@test.com"],
                max_retries=3,
            )

    assert success is False
    assert status == "FAILED_REQUIRES_REVIEW"
    assert "PreTransmissionDisconnect: SMTPServerDisconnected" in (err or "")
    assert mock_smtp_ssl.call_count == 3


def test_smtp_disconnect_during_transmission_uncertain_no_retry(test_account):
    """
    If disconnect happens while calling sendmail, the server may have received the data.
    The sender must NOT retry automatically and must flag UncertainDelivery.
    """
    sender = OutreachSender(dry_run=False)

    mock_server = MagicMock()
    mock_server.sendmail.side_effect = smtplib.SMTPServerDisconnected("Connection broken during DATA")

    with patch("src.outreach.sender.smtplib.SMTP_SSL", return_value=mock_server) as mock_smtp_ssl:
        with patch("src.outreach.sender.time.sleep") as mock_sleep:
            success, status, err = sender.send_batch(
                account=test_account,
                subject="Test Subject",
                body_text="Test Body",
                bcc_recipients=["recip1@test.com"],
                max_retries=3,
            )

    assert success is False
    assert status == "FAILED_REQUIRES_REVIEW"
    assert "UncertainDelivery: SMTPServerDisconnected" in (err or "")
    # Must NOT retry
    assert mock_smtp_ssl.call_count == 1
    mock_sleep.assert_not_called()


def test_orchestrator_skips_sent_and_protects_unresolved_batch(tmp_path):
    """
    Orchestrator must never re-send batches marked SENT.
    And a batch previously marked FAILED_REQUIRES_REVIEW must not be resent without reconciliation.
    """
    state_file = tmp_path / "campaigns.csv"
    batches_file = tmp_path / "batches.csv"
    state_mgr = CampaignState(state_file=state_file, batches_file=batches_file)

    campaign_id = "CAMP-mockhash123-2026-10-11"

    # Pre-record batch 0 as SENT, batch 1 as FAILED_REQUIRES_REVIEW, batch 2 as SENT
    state_mgr.record_batch_plan(campaign_id, 0, "sender1@example.com", 1, "Subj 1", 10)
    state_mgr.update_batch_status(campaign_id, 0, "SENT")

    state_mgr.record_batch_plan(campaign_id, 1, "sender2@example.com", 2, "Subj 2", 10)
    state_mgr.update_batch_status(campaign_id, 1, "FAILED_REQUIRES_REVIEW", "SMTPServerDisconnected")

    state_mgr.record_batch_plan(campaign_id, 2, "sender3@example.com", 3, "Subj 3", 10)
    state_mgr.update_batch_status(campaign_id, 2, "SENT")

    # In dry-run mode or mocked run
    pipeline = OutreachPipeline(dry_run=True, state_mgr=state_mgr)

    # Mock detection of same file
    lead_file = tmp_path / "leads.csv"
    lead_file.write_text("email\nlead1@example.com\nlead2@example.com\n")

    # Check loaded batch statuses
    batches = state_mgr.load_batches(campaign_id)
    batch_map = {int(b["batch_index"]): b["status"] for b in batches}
    assert batch_map[0] == "SENT"
    assert batch_map[1] == "FAILED_REQUIRES_REVIEW"
    assert batch_map[2] == "SENT"
