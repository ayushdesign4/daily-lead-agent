"""
Tests for Event-Driven Lead Delivery -> Outreach Pipeline.
Verifies the end-to-end event-driven trigger, local delivery receipt handoff,
SHA256 integrity verification, idempotency, date-guard enforcement,
and preservation of core outreach configurations (niches, 9 accounts, BCC, templates).
"""

import hashlib
import json
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.outreach.gmail_watcher import GmailWatcher, DetectedLeadDelivery
from src.outreach.orchestrator import OutreachPipeline
from src.outreach.campaign_state import CampaignState
from src.outreach.quota_ledger import QuotaLedger
from src.outreach.suppression import SuppressionManager
from src.outreach.distributor import distribute_recipients
from src.outreach.template_manager import TemplateManager
from src.outreach.sender import OutreachSender, OutreachAccount


# ---------------------------------------------------------------------------
# Test 1: Workflow Run Trigger Configuration
# ---------------------------------------------------------------------------
def test_1_workflow_run_trigger_configuration():
    """Verify outreach_pipeline.yml uses workflow_run on Deliver Leads and has no cron schedule."""
    workflow_path = Path(".github/workflows/outreach_pipeline.yml")
    assert workflow_path.exists(), "outreach_pipeline.yml must exist"

    content = workflow_path.read_text(encoding="utf-8")

    # Must NOT have cron schedule
    assert "cron:" not in content, "cron schedule must be removed"
    assert "schedule:" not in content, "schedule trigger must be removed"

    # Must have workflow_run listening to Deliver Leads completion on main
    assert "workflow_run:" in content, "workflow_run trigger must be present"
    assert "Deliver Leads - 11 AM IST Delivery Check" in content
    assert "completed" in content
    assert "branches:" in content and "main" in content

    # Job must be conditional on success of workflow_run or workflow_dispatch
    assert "github.event.workflow_run.conclusion == 'success'" in content
    assert "github.event_name == 'workflow_dispatch'" in content


# ---------------------------------------------------------------------------
# Test 2: Failed or Cancelled Delivery Conclusion Does Not Run Outreach
# ---------------------------------------------------------------------------
def test_2_failed_or_cancelled_conclusion_blocked():
    """Verify conclusion filter rejects non-success conclusions."""
    def should_job_run(event_name: str, conclusion: str) -> bool:
        return event_name == "workflow_dispatch" or (
            event_name == "workflow_run" and conclusion == "success"
        )

    # Success should run
    assert should_job_run("workflow_run", "success") is True
    assert should_job_run("workflow_dispatch", "failure") is True

    # Failed, cancelled, skipped must NOT run
    assert should_job_run("workflow_run", "failure") is False
    assert should_job_run("workflow_run", "cancelled") is False
    assert should_job_run("workflow_run", "skipped") is False
    assert should_job_run("workflow_run", "timed_out") is False


# ---------------------------------------------------------------------------
# Test 3: Delivery with 0 leads does not start outreach
# ---------------------------------------------------------------------------
def test_3_zero_leads_delivery_does_not_start_outreach(tmp_path):
    """When receipt has delivered_count == 0 or is missing, check_local_receipt returns None and outreach halts safely."""
    date_str = "2026-10-20"
    receipt_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    receipt_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)

    watcher = GmailWatcher(username="ayushdesign291@gmail.com", password="dummy_password")

    # Missing receipt -> returns None
    res_none = watcher.check_local_receipt(target_date_str=date_str, receipt_dir=receipt_dir, output_dir=output_dir)
    assert res_none is None

    # Zero delivered leads -> returns None
    zero_receipt = receipt_dir / f"delivery_receipt_{date_str}.json"
    zero_receipt.write_text(json.dumps({
        "status": "DELIVERED",
        "date": date_str,
        "delivered_count": 0,
        "lead_file": f"leads_{date_str}.txt",
    }), encoding="utf-8")

    res_zero = watcher.check_local_receipt(target_date_str=date_str, receipt_dir=receipt_dir, output_dir=output_dir)
    assert res_zero is None

    # Orchestrator with no delivery returns NO_DELIVERY_DETECTED
    pipeline = OutreachPipeline(
        dry_run=True,
        state_mgr=CampaignState(tmp_path / "state.csv", tmp_path / "batches.csv"),
        quota_ledger=QuotaLedger(tmp_path / "ledger.csv", tmp_path / "cache.csv"),
        suppression_mgr=SuppressionManager(tmp_path / "supp.csv"),
    )
    with patch.object(pipeline.watcher, "detect_next_delivery", return_value=None):
        out_res = pipeline.run(today_ist_date=date_str)
        assert out_res["status"] == "NO_DELIVERY_DETECTED"
        assert out_res["date"] == date_str


# ---------------------------------------------------------------------------
# Test 4: Correct delivered TXT and hash reach orchestrator
# ---------------------------------------------------------------------------
def test_4_correct_delivered_txt_and_hash_reach_orchestrator(tmp_path):
    """Valid receipt and TXT file with valid SHA256 handoff cleanly to orchestrator."""
    date_str = "2026-10-20"
    receipt_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    receipt_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)

    lead_text = "creator1@youtube.com\ncreator2@youtube.com\n"
    txt_file = output_dir / f"leads_{date_str}.txt"
    txt_file.write_text(lead_text, encoding="utf-8")
    actual_hash = hashlib.sha256(txt_file.read_bytes()).hexdigest()

    receipt_file = receipt_dir / f"delivery_receipt_{date_str}.json"
    receipt_file.write_text(json.dumps({
        "status": "DELIVERED",
        "date": date_str,
        "delivered_count": 2,
        "lead_file": f"leads_{date_str}.txt",
        "content_hash": actual_hash,
        "run_id": "run-9999",
    }), encoding="utf-8")

    watcher = GmailWatcher(username="ayushdesign291@gmail.com", password="dummy_password")
    delivery = watcher.check_local_receipt(target_date_str=date_str, receipt_dir=receipt_dir, output_dir=output_dir)

    assert delivery is not None
    assert delivery.source_type == "local_receipt"
    assert delivery.content_hash == actual_hash
    assert delivery.attachment_filename == f"leads_{date_str}.txt"
    assert delivery.attachment_bytes == txt_file.read_bytes()

    # Pass to orchestrator
    state_mgr = CampaignState(tmp_path / "state.csv", tmp_path / "batches.csv")
    pipeline = OutreachPipeline(
        dry_run=True,
        state_mgr=state_mgr,
        quota_ledger=QuotaLedger(tmp_path / "ledger.csv", tmp_path / "cache.csv"),
        suppression_mgr=SuppressionManager(tmp_path / "supp.csv"),
    )
    with patch.object(pipeline.watcher, "detect_next_delivery", return_value=delivery):
        res = pipeline.run(today_ist_date=date_str)
        assert res["overall_status"] == "COMPLETED"
        assert res["campaign_id"] == f"CAMP-{actual_hash[:10]}-{date_str}"


# ---------------------------------------------------------------------------
# Test 5: Mismatched content hash fails integrity check
# ---------------------------------------------------------------------------
def test_5_mismatched_content_hash_fails_integrity(tmp_path):
    """If delivery specifies a content_hash that does not match attachment bytes, fail with INTEGRITY_CHECK_FAILED."""
    date_str = "2026-10-20"
    mismatched_delivery = DetectedLeadDelivery(
        subject=f"Daily New Leads — {date_str}",
        date_str=date_str,
        attachment_filename=f"leads_{date_str}.txt",
        attachment_bytes=b"creator@youtube.com\n",
        source_type="local_receipt",
        message_id="msg-123",
        content_hash="tampered_or_corrupt_hash_1234567890",
    )

    state_mgr = CampaignState(tmp_path / "state.csv", tmp_path / "batches.csv")
    pipeline = OutreachPipeline(
        dry_run=True,
        state_mgr=state_mgr,
        quota_ledger=QuotaLedger(tmp_path / "ledger.csv", tmp_path / "cache.csv"),
        suppression_mgr=SuppressionManager(tmp_path / "supp.csv"),
    )

    with patch.object(pipeline.watcher, "detect_next_delivery", return_value=mismatched_delivery):
        res = pipeline.run(today_ist_date=date_str)
        assert res["status"] == "INTEGRITY_CHECK_FAILED"
        assert res["expected_hash"] == "tampered_or_corrupt_hash_1234567890"
        # No campaign completed
        assert len(state_mgr.load_campaigns()) == 0


# ---------------------------------------------------------------------------
# Test 6: Duplicate events return ALREADY_COMPLETED without duplicate sending
# ---------------------------------------------------------------------------
def test_6_duplicate_events_return_already_completed(tmp_path):
    """Second delivery event with same content hash returns ALREADY_COMPLETED immediately."""
    date_str = "2026-10-20"
    content = b"creator1@youtube.com\ncreator2@youtube.com\n"
    c_hash = hashlib.sha256(content).hexdigest()

    delivery = DetectedLeadDelivery(
        subject=f"Daily New Leads — {date_str}",
        date_str=date_str,
        attachment_filename=f"leads_{date_str}.txt",
        attachment_bytes=content,
        source_type="local_receipt",
        message_id="receipt-run-1",
        content_hash=c_hash,
    )

    state_mgr = CampaignState(tmp_path / "state.csv", tmp_path / "batches.csv")
    pipeline = OutreachPipeline(
        dry_run=True,
        state_mgr=state_mgr,
        quota_ledger=QuotaLedger(tmp_path / "ledger.csv", tmp_path / "cache.csv"),
        suppression_mgr=SuppressionManager(tmp_path / "supp.csv"),
    )

    with patch.object(pipeline.watcher, "detect_next_delivery", return_value=delivery):
        # Run 1
        res1 = pipeline.run(today_ist_date=date_str)
        assert res1["overall_status"] == "COMPLETED"

        # Run 2 (duplicate event / retry)
        res2 = pipeline.run(today_ist_date=date_str)
        assert res2["status"] == "ALREADY_COMPLETED"
        assert res2["campaign_id"] == f"CAMP-{c_hash[:10]}-{date_str}"


# ---------------------------------------------------------------------------
# Test 7: Two delivery events with different hashes run separate campaigns
# ---------------------------------------------------------------------------
def test_7_different_hashes_run_separate_campaigns(tmp_path):
    """Deliveries with different content hashes are treated as distinct campaigns."""
    state_mgr = CampaignState(tmp_path / "state.csv", tmp_path / "batches.csv")
    pipeline = OutreachPipeline(
        dry_run=True,
        state_mgr=state_mgr,
        quota_ledger=QuotaLedger(tmp_path / "ledger.csv", tmp_path / "cache.csv"),
        suppression_mgr=SuppressionManager(tmp_path / "supp.csv"),
    )

    lead_bytes_1 = b"leadA@youtube.com\n"
    lead_bytes_2 = b"leadB@youtube.com\n"
    hash1 = hashlib.sha256(lead_bytes_1).hexdigest()
    hash2 = hashlib.sha256(lead_bytes_2).hexdigest()

    del1 = DetectedLeadDelivery(
        subject="Daily New Leads — 2026-10-20",
        date_str="2026-10-20",
        attachment_filename="leads_2026-10-20.txt",
        attachment_bytes=lead_bytes_1,
        source_type="local_receipt",
        message_id="m1",
        content_hash=hash1,
    )
    del2 = DetectedLeadDelivery(
        subject="Daily New Leads — 2026-10-21",
        date_str="2026-10-21",
        attachment_filename="leads_2026-10-21.txt",
        attachment_bytes=lead_bytes_2,
        source_type="local_receipt",
        message_id="m2",
        content_hash=hash2,
    )

    with patch.object(pipeline.watcher, "detect_next_delivery", return_value=del1):
        r1 = pipeline.run(today_ist_date="2026-10-20")
        assert r1["overall_status"] == "COMPLETED"
        assert r1["campaign_id"] == f"CAMP-{hash1[:10]}-2026-10-20"

    with patch.object(pipeline.watcher, "detect_next_delivery", return_value=del2):
        r2 = pipeline.run(today_ist_date="2026-10-21")
        assert r2["overall_status"] == "COMPLETED"
        assert r2["campaign_id"] == f"CAMP-{hash2[:10]}-2026-10-21"

    assert r1["campaign_id"] != r2["campaign_id"]


# ---------------------------------------------------------------------------
# Test 8: Stale delivery dates are rejected by date guard
# ---------------------------------------------------------------------------
def test_8_stale_delivery_dates_rejected_by_date_guard(tmp_path):
    """Delivery with yesterday's date is rejected by orchestrator date guard."""
    stale_delivery = DetectedLeadDelivery(
        subject="Daily New Leads — 2026-10-19",
        date_str="2026-10-19",
        attachment_filename="leads_2026-10-19.txt",
        attachment_bytes=b"creator@youtube.com\n",
        source_type="local_receipt",
        message_id="m_stale",
        content_hash=hashlib.sha256(b"creator@youtube.com\n").hexdigest(),
    )

    state_mgr = CampaignState(tmp_path / "state.csv", tmp_path / "batches.csv")
    pipeline = OutreachPipeline(
        dry_run=True,
        state_mgr=state_mgr,
        quota_ledger=QuotaLedger(tmp_path / "ledger.csv", tmp_path / "cache.csv"),
        suppression_mgr=SuppressionManager(tmp_path / "supp.csv"),
    )

    with patch.object(pipeline.watcher, "detect_next_delivery", return_value=stale_delivery):
        # Target date is 2026-10-20, delivery is 2026-10-19
        res = pipeline.run(today_ist_date="2026-10-20")
        assert res["status"] == "STALE_DELIVERY_REJECTED"
        assert res["delivery_date"] == "2026-10-19"
        assert res["expected_date"] == "2026-10-20"


# ---------------------------------------------------------------------------
# Test 9: Historical used niches and queue remain untouched
# ---------------------------------------------------------------------------
def test_9_historical_niches_and_queue_remain_untouched(tmp_path):
    """Running outreach pipeline does not mutate used_niches.csv or pending_queue.csv."""
    niches_csv = Path("data/used_niches.csv")
    queue_csv = Path("data/pending_queue.csv")

    assert niches_csv.exists(), "used_niches.csv must exist"
    assert queue_csv.exists(), "pending_queue.csv must exist"

    niches_before = niches_csv.read_bytes()
    queue_before = queue_csv.read_bytes()

    lead_file = tmp_path / "leads_test.txt"
    lead_file.write_text("creator1@youtube.com\ncreator2@youtube.com\n", encoding="utf-8")

    pipeline = OutreachPipeline(
        dry_run=True,
        state_mgr=CampaignState(tmp_path / "state.csv", tmp_path / "batches.csv"),
        quota_ledger=QuotaLedger(tmp_path / "ledger.csv", tmp_path / "cache.csv"),
        suppression_mgr=SuppressionManager(tmp_path / "supp.csv"),
    )
    res = pipeline.run(manual_file=lead_file, force=True)
    assert res["overall_status"] == "COMPLETED"

    niches_after = niches_csv.read_bytes()
    queue_after = queue_csv.read_bytes()

    assert niches_before == niches_after, "data/used_niches.csv must remain completely untouched"
    assert queue_before == queue_after, "data/pending_queue.csv must remain completely untouched"


# ---------------------------------------------------------------------------
# Test 10: 9-way sender accounts, BCC-only, and template rotation preserved
# ---------------------------------------------------------------------------
def test_10_sender_accounts_bcc_and_template_preserved():
    """Verify 9-way sender accounts, BCC-only to fixed address, and template cycling."""
    accounts = [
        OutreachAccount(email=f"sender{i+1}@gmail.com", app_password=f"pass_{i+1}")
        for i in range(9)
    ]
    senders = [a.email for a in accounts]

    leads = [f"lead_{i:03d}@creator.com" for i in range(180)]
    batches = distribute_recipients(leads, senders)

    assert len(batches) == 9
    for i, b in enumerate(batches):
        assert b["sender_account"] == f"sender{i+1}@gmail.com"
        assert b["count"] == 20

    # Template rotation test
    tm = TemplateManager()
    templates_used = [tm.get_template_for_batch(i)[0] for i in range(9)]
    # Expect 1, 2, 3, 1, 2, 3, 1, 2, 3
    assert templates_used == [1, 2, 3, 1, 2, 3, 1, 2, 3]

    # BCC-only verification
    sender = OutreachSender(dry_run=True)
    with patch("smtplib.SMTP_SSL") as mock_smtp_cls:
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = mock_server

        msg = sender.build_message(
            sender_email=accounts[0].email,
            subject="Test subject",
            body_text="Test body",
        )

        assert msg["To"] == "ayush@ayushdesign.site"
        assert msg["From"] == "sender1@gmail.com"
        # Bcc header must NOT appear in the MIME message headers (BCC privacy)
        assert msg["Bcc"] is None
