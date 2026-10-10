"""End-to-end pipeline integration test for outreach orchestrator."""

import json
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from src.outreach.orchestrator import OutreachPipeline
from src.outreach.campaign_state import CampaignState
from src.outreach.quota_ledger import QuotaLedger
from src.outreach.suppression import SuppressionManager
from src.outreach.verification_client import VerificationResult


def test_full_outreach_pipeline_e2e(tmp_path):
    state_file = tmp_path / "state.csv"
    batches_file = tmp_path / "batches.csv"
    ledger_file = tmp_path / "ledger.csv"
    cache_file = tmp_path / "cache.csv"
    supp_file = tmp_path / "supp.csv"

    # Create dummy lead file with 30 leads (some valid, duplicates, malformed)
    lead_file = tmp_path / "leads_2026-10-10.txt"
    leads = [f"creator_{i}@youtube.com" for i in range(25)]
    # Add duplicate and malformed
    leads.append("creator_0@youtube.com")  # duplicate
    leads.append("bad_email_at_nothing")    # malformed
    leads.append("unsubscribed@youtube.com") # will be suppressed
    lead_file.write_text("\n".join(leads) + "\n", encoding="utf-8")

    supp_mgr = SuppressionManager(supp_file)
    supp_mgr.add_suppression("unsubscribed@youtube.com", "unsubscribed")

    state_mgr = CampaignState(state_file, batches_file)
    quota_ledger = QuotaLedger(ledger_file, cache_file)

    # 9 sender accounts
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

    # Execute pipeline
    result = pipeline.run(manual_file=lead_file, force=True)

    assert result["overall_status"] == "COMPLETED"
    assert result["leads_parsed"] == 28
    assert result["malformed_count"] == 1
    assert result["duplicate_count"] == 1
    assert result["unique_count"] == 26
    # 25 unique eligible (26 minus 1 suppressed)
    assert result["suppressed_count"] == 1
    assert result["net_eligible_count"] == 25

    # Check 9 batches created
    batches = result["batches"]
    assert len(batches) == 9
    batch_counts = [b["count"] for b in batches]
    assert sum(batch_counts) == 25
    assert max(batch_counts) - min(batch_counts) <= 1
    # 25 / 9 = 2 remainder 7 -> seven 3s and two 2s
    assert sorted(batch_counts) == [2, 2, 3, 3, 3, 3, 3, 3, 3]

    # Verify all batches marked SENT
    assert all(b["status"] == "SENT" for b in batches)

    # Verify campaign state persisted as COMPLETED
    c = state_mgr.get_campaign(result["campaign_id"])
    assert c is not None
    assert c["status"] == "COMPLETED"
    assert c["batches_sent"] == "9"
