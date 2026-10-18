"""
Tests for Fresh-Lead Date Guard (FIX 2).
Ensures the outreach pipeline strictly requires today's fresh lead email based on
today's IST date (YYYY-MM-DD) and message metadata (header Date in IST).
Prevents reusing stale lead emails or attachments.
"""

import email
import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
from pathlib import Path

from src.outreach.gmail_watcher import GmailWatcher, DetectedLeadDelivery, IST_TZ
from src.outreach.orchestrator import OutreachPipeline
from src.outreach.campaign_state import CampaignState
from src.outreach.quota_ledger import QuotaLedger
from src.outreach.suppression import SuppressionManager


def _create_mock_mime_email(subject: str, date_header: str, from_addr: str, attachment_content: str = "creator@youtube.com\n") -> bytes:
    """Helper to build raw MIME email bytes with an attachment."""
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["Date"] = date_header
    msg["Message-ID"] = "<test-msg-123@example.com>"

    # Body
    msg.attach(MIMEText("Here are your leads", "plain"))

    # Attachment
    part = MIMEBase("text", "plain")
    part.set_payload(attachment_content.encode("utf-8"))
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", 'attachment; filename="leads.txt"')
    msg.attach(part)

    return msg.as_bytes()


def test_imap_accepts_todays_lead_email():
    """An email with today's subject date and today's IST header Date must be accepted."""
    today_ist = "2026-10-18"
    # Format RFC 2822 date in IST (UTC+0530)
    date_hdr = "Sun, 18 Oct 2026 11:00:00 +0530"

    raw_email = _create_mock_mime_email(
        subject=f"Daily New Leads — {today_ist}",
        date_header=date_hdr,
        from_addr="ayushdesign291@gmail.com",
    )

    watcher = GmailWatcher(username="ayushdesign291@gmail.com", password="dummy_password")

    with patch("imaplib.IMAP4_SSL") as mock_imap_cls:
        mock_imap = MagicMock()
        mock_imap_cls.return_value = mock_imap
        mock_imap.search.return_value = ("OK", [b"1"])
        mock_imap.fetch.return_value = ("OK", [(b"1", raw_email)])

        delivery = watcher.check_imap_inbox(target_date_str=today_ist)

        assert delivery is not None
        assert delivery.date_str == today_ist
        assert delivery.subject == f"Daily New Leads — {today_ist}"
        assert delivery.attachment_filename == "leads.txt"
        assert b"creator@youtube.com" in delivery.attachment_bytes


def test_imap_rejects_yesterdays_subject_date():
    """An email with yesterday's subject date must be skipped, returning None if no today's email exists."""
    today_ist = "2026-10-18"
    stale_date = "2026-10-17"
    date_hdr = "Sat, 17 Oct 2026 11:00:00 +0530"

    raw_email = _create_mock_mime_email(
        subject=f"Daily New Leads — {stale_date}",
        date_header=date_hdr,
        from_addr="ayushdesign291@gmail.com",
    )

    watcher = GmailWatcher(username="ayushdesign291@gmail.com", password="dummy_password")

    with patch("imaplib.IMAP4_SSL") as mock_imap_cls:
        mock_imap = MagicMock()
        mock_imap_cls.return_value = mock_imap
        mock_imap.search.return_value = ("OK", [b"1"])
        mock_imap.fetch.return_value = ("OK", [(b"1", raw_email)])

        delivery = watcher.check_imap_inbox(target_date_str=today_ist)

        assert delivery is None


def test_imap_rejects_stale_header_date():
    """An email where subject claims today, but header Date is actually yesterday in IST must be rejected."""
    today_ist = "2026-10-18"
    # Header date is actually Oct 17
    stale_hdr = "Sat, 17 Oct 2026 23:00:00 +0000"  # Oct 17 23:00 UTC = Oct 18 04:30 IST, but Oct 16 UTC is stale

    # Let's use clearly stale Date header: Oct 16 11:00 UTC = Oct 16 16:30 IST
    really_stale_hdr = "Fri, 16 Oct 2026 11:00:00 +0000"

    raw_email = _create_mock_mime_email(
        subject=f"Daily New Leads — {today_ist}",
        date_header=really_stale_hdr,
        from_addr="ayushdesign291@gmail.com",
    )

    watcher = GmailWatcher(username="ayushdesign291@gmail.com", password="dummy_password")

    with patch("imaplib.IMAP4_SSL") as mock_imap_cls:
        mock_imap = MagicMock()
        mock_imap_cls.return_value = mock_imap
        mock_imap.search.return_value = ("OK", [b"1"])
        mock_imap.fetch.return_value = ("OK", [(b"1", raw_email)])

        delivery = watcher.check_imap_inbox(target_date_str=today_ist)

        assert delivery is None


def test_orchestrator_stops_cleanly_when_no_fresh_delivery_detected(tmp_path):
    """When no delivery email arrives for today, orchestrator exits cleanly with NO campaign state or sends."""
    state_file = tmp_path / "state.csv"
    batches_file = tmp_path / "batches.csv"
    ledger_file = tmp_path / "ledger.csv"
    cache_file = tmp_path / "cache.csv"
    supp_file = tmp_path / "supp.csv"

    state_mgr = CampaignState(state_file, batches_file)
    quota_ledger = QuotaLedger(ledger_file, cache_file)
    supp_mgr = SuppressionManager(supp_file)

    accounts_json = json.dumps([
        {"email": f"sender{i+1}@gmail.com", "app_password": f"pass_{i+1}"}
        for i in range(9)
    ])

    pipeline = OutreachPipeline(
        dry_run=True,
        state_mgr=state_mgr,
        quota_ledger=quota_ledger,
        suppression_mgr=supp_mgr,
        raw_accounts_json=accounts_json,
    )

    with patch.object(GmailWatcher, "detect_next_delivery", return_value=None):
        result = pipeline.run()

        assert result["status"] == "NO_DELIVERY_DETECTED"
        # Verify no campaign state was created
        assert len(state_mgr.load_campaigns()) == 0
        # Verify no ledger usage recorded
        assert quota_ledger.get_daily_usage("mail7") == 0


def test_orchestrator_rejects_stale_delivery_date(tmp_path):
    """If watcher somehow produces a delivery with an older date_str, orchestrator rejects it before campaign creation."""
    state_file = tmp_path / "state.csv"
    batches_file = tmp_path / "batches.csv"
    ledger_file = tmp_path / "ledger.csv"
    cache_file = tmp_path / "cache.csv"
    supp_file = tmp_path / "supp.csv"

    state_mgr = CampaignState(state_file, batches_file)
    quota_ledger = QuotaLedger(ledger_file, cache_file)
    supp_mgr = SuppressionManager(supp_file)

    accounts_json = json.dumps([
        {"email": f"sender{i+1}@gmail.com", "app_password": f"pass_{i+1}"}
        for i in range(9)
    ])

    pipeline = OutreachPipeline(
        dry_run=True,
        state_mgr=state_mgr,
        quota_ledger=quota_ledger,
        suppression_mgr=supp_mgr,
        raw_accounts_json=accounts_json,
    )

    stale_delivery = DetectedLeadDelivery(
        source_type="imap",
        message_id="OLD-MSG-ID",
        subject="Daily New Leads — 2026-10-16",
        attachment_filename="leads.txt",
        attachment_bytes=b"stale_creator@youtube.com\n",
        date_str="2026-10-16",
    )

    with patch.object(GmailWatcher, "detect_next_delivery", return_value=stale_delivery):
        result = pipeline.run()

        assert result["status"] == "STALE_DELIVERY_REJECTED"
        assert result["delivery_date"] == "2026-10-16"
        # No campaign state created
        assert len(state_mgr.load_campaigns()) == 0
        # No ledger usage recorded
        assert quota_ledger.get_daily_usage("mail7") == 0
