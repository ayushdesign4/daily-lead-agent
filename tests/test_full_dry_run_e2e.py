"""Full dry-run end-to-end sequence test connecting lead generation to outreach."""

import json
import time
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from src.main import DailyLeadAgent
from src.state_manager import StateManager, get_today_ist_date
from src.apify_client import ApifyClient
from src.delivery import DeliveryManager

from src.outreach.orchestrator import OutreachPipeline
from src.outreach.campaign_state import CampaignState
from src.outreach.quota_ledger import QuotaLedger
from src.outreach.suppression import SuppressionManager
from src.outreach.sender import OutreachAccount
from src.outreach.template_manager import TemplateManager


def test_full_dry_run_end_to_end_sequence(tmp_path):
    start_time = time.time()
    today_str = get_today_ist_date()

    # Isolated test filesystem
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    data_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    master_file = data_dir / "master.csv"
    queue_file = data_dir / "queue.csv"
    niches_file = data_dir / "used_niches.csv"
    runs_file = data_dir / "daily_runs.csv"

    outreach_state_file = data_dir / "outreach_state.csv"
    outreach_batches_file = data_dir / "outreach_batches.csv"
    ledger_file = data_dir / "verification_ledger.csv"
    cache_file = data_dir / "verification_cache.csv"
    supp_file = data_dir / "outreach_suppressions.csv"

    # STAGE 1 & 2: Lead Generation & Delivery (MOCKED APIFY & SMTP)
    lead_state = StateManager(master_file, queue_file, niches_file, runs_file)

    mock_apify = MagicMock(spec=ApifyClient)
    # Generate 200 distinct test leads across simulated queries
    mock_dataset = [
        {"title": f"Creator {i}", "snippet": f"Business contact: test_creator_{i:03d}@youtube.com"}
        for i in range(200)
    ]
    mock_apify.run_search_batch.return_value = mock_dataset

    # Mock delivery manager to write local file and simulate SMTP without real sending
    test_lead_file = output_dir / f"leads_{today_str}.txt"
    with open(test_lead_file, "w", encoding="utf-8") as f:
        for i in range(200):
            f.write(f"test_creator_{i:03d}@youtube.com\n")

    mock_delivery = MagicMock(spec=DeliveryManager)
    mock_delivery.generate_lead_file.return_value = test_lead_file
    mock_delivery.send_daily_leads.return_value = True

    lead_agent = DailyLeadAgent(
        target=200,
        dry_run=True,
        state_manager=lead_state,
        apify_client=mock_apify,
        delivery_manager=mock_delivery,
    )

    # Deliver leads in dry-run mode
    delivered_count = lead_agent.run(force=True, mode="all")
    assert delivered_count == 200, "Lead generation did not satisfy 200 target"
    assert test_lead_file.exists(), "Lead file was not generated"

    # STAGE 3: Outreach Pipeline Detection
    campaign_state = CampaignState(outreach_state_file, outreach_batches_file)
    quota_ledger = QuotaLedger(ledger_file, cache_file)
    supp_mgr = SuppressionManager(supp_file)

    # 9 Valid Sender Accounts
    sender_accounts_json = json.dumps([
        {"email": f"sender{i+1}@gmail.com", "app_password": f"apppass_{i+1}"}
        for i in range(9)
    ])

    pipeline = OutreachPipeline(
        dry_run=True,
        state_mgr=campaign_state,
        quota_ledger=quota_ledger,
        suppression_mgr=supp_mgr,
        raw_accounts_json=sender_accounts_json,
    )

    # STAGE 4, 5, 6: Verification, Distribution, BCC Sender, Completion Notification
    outreach_summary = pipeline.run(manual_file=test_lead_file, force=True)

    assert outreach_summary["overall_status"] == "COMPLETED"
    assert outreach_summary["leads_parsed"] == 200
    assert outreach_summary["unique_count"] == 200

    # STAGE 4: Verification Partitioning
    assert outreach_summary["verified_a_count"] == 100
    assert outreach_summary["verified_b_count"] == 100
    assert outreach_summary["deferred_count"] == 0

    # STAGE 5: 9-Way Balanced Distribution & BCC Addressing
    batches = outreach_summary["batches"]
    assert len(batches) == 9
    batch_sizes = [b["count"] for b in batches]
    assert sum(batch_sizes) == 200
    assert max(batch_sizes) - min(batch_sizes) <= 1
    # 200 // 9 = 22 remainder 2 -> two 23s and seven 22s
    assert sorted(batch_sizes) == [22, 22, 22, 22, 22, 22, 22, 23, 23]

    # Every recipient in exactly 1 batch
    assigned_emails = [em for b in batches for em in b["recipients"]]
    assert len(assigned_emails) == len(set(assigned_emails)) == 200

    # Verify template rotation 1, 2, 3, 1, 2, 3...
    for b in batches:
        idx = b["batch_index"]
        expected_tmpl = (idx % 3) + 1
        expected_subj = TemplateManager.get_subject_for_batch(idx)
        assert b["subject"] == expected_subj
        assert b["status"] == "SENT"

    # STAGE 7: Idempotency Verification
    # Re-running with same file must detect ALREADY_COMPLETED and not resend
    rerun_summary = pipeline.run(manual_file=test_lead_file, force=False)
    assert rerun_summary["status"] == "ALREADY_COMPLETED"

    elapsed = time.time() - start_time
    print(f"\n[DRY RUN TEST COMPLETE] Runtime: {elapsed:.2f}s")
