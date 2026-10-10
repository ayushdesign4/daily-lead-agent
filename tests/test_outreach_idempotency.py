"""Tests for campaign idempotency, deduplication, and preventing duplicate sends."""

import json
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from src.outreach.orchestrator import OutreachPipeline
from src.outreach.campaign_state import CampaignState
from src.outreach.quota_ledger import QuotaLedger
from src.outreach.suppression import SuppressionManager


def test_completed_campaign_skips_on_rerun(tmp_path):
    state_file = tmp_path / "state.csv"
    batches_file = tmp_path / "batches.csv"
    lead_file = tmp_path / "leads.txt"
    lead_file.write_text("creator1@gmail.com\ncreator2@gmail.com\n", encoding="utf-8")

    state_mgr = CampaignState(state_file, batches_file)
    pipeline = OutreachPipeline(
        dry_run=True,
        state_mgr=state_mgr,
        quota_ledger=QuotaLedger(tmp_path / "l.csv", tmp_path / "c.csv"),
        suppression_mgr=SuppressionManager(tmp_path / "s.csv"),
    )

    # First run
    res1 = pipeline.run(manual_file=lead_file, force=False)
    assert res1["overall_status"] == "COMPLETED"

    # Second run without force: must detect ALREADY_COMPLETED
    res2 = pipeline.run(manual_file=lead_file, force=False)
    assert res2["status"] == "ALREADY_COMPLETED"


def test_message_id_deduplication(tmp_path):
    state_mgr = CampaignState(tmp_path / "st.csv", tmp_path / "bt.csv")
    state_mgr.save_campaign_state(
        campaign_id="CAMP-12345",
        status="COMPLETED",
        source_message_id="MSG-XYZ-999",
        attachment_hash="HASH-ABC",
    )

    assert state_mgr.is_message_already_processed("MSG-XYZ-999", "DIFFERENT-HASH") is True
    assert state_mgr.is_message_already_processed("OTHER-MSG", "HASH-ABC") is True
    assert state_mgr.is_message_already_processed("NEW-MSG", "NEW-HASH") is False
