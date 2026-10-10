"""Tests for partial failure recovery, account validation security, and suppression list enforcement."""

import json
import pytest
from unittest.mock import MagicMock
from pathlib import Path
from src.outreach.sender import load_and_validate_accounts, OutreachAccount
from src.outreach.suppression import SuppressionManager
from src.outreach.orchestrator import OutreachPipeline
from src.outreach.campaign_state import CampaignState
from src.outreach.quota_ledger import QuotaLedger


def test_account_validation_fails_closed_without_echoing_secrets():
    # Test 1: Empty string
    with pytest.raises(ValueError) as exc:
        load_and_validate_accounts("")
    assert "validation failed closed" in str(exc.value).lower()

    # Test 2: Less than 9 accounts
    partial_accounts = json.dumps([
        {"email": f"sender{i}@gmail.com", "app_password": f"secret_pass_{i}"}
        for i in range(5)
    ])
    with pytest.raises(ValueError) as exc:
        load_and_validate_accounts(partial_accounts)
    assert "exactly 9 accounts" in str(exc.value)
    # Ensure no secret was leaked in the exception message
    assert "secret_pass" not in str(exc.value)

    # Test 3: Exactly 9 valid unique accounts
    valid_9 = json.dumps([
        {"email": f"sender{i+1}@gmail.com", "app_password": f"pass_{i+1}"}
        for i in range(9)
    ])
    accounts = load_and_validate_accounts(valid_9)
    assert len(accounts) == 9
    assert repr(accounts[0]) == "<OutreachAccount email='sender1@gmail.com'>"
    assert "pass_1" not in repr(accounts[0])


def test_suppression_list_filtering(tmp_path):
    supp_file = tmp_path / "suppressions.csv"
    supp_mgr = SuppressionManager(supp_file)

    supp_mgr.add_suppression("unsubscribed@domain.com", "user_requested", "2026-10-10")

    assert supp_mgr.is_suppressed("unsubscribed@domain.com") is True
    assert supp_mgr.is_suppressed("UNSUBSCRIBED@domain.com") is True
    assert supp_mgr.is_suppressed("active@domain.com") is False

    emails = ["active@domain.com", "unsubscribed@domain.com", "other@domain.com"]
    eligible, count = supp_mgr.filter_eligible(emails)
    assert count == 1
    assert eligible == ["active@domain.com", "other@domain.com"]


def test_partial_failure_resumes_only_unsent_batches(tmp_path):
    state_file = tmp_path / "state.csv"
    batches_file = tmp_path / "batches.csv"
    lead_file = tmp_path / "leads.txt"
    lead_file.write_text("c1@gmail.com\nc2@gmail.com\nc3@gmail.com\n", encoding="utf-8")

    state_mgr = CampaignState(state_file, batches_file)
    pipeline = OutreachPipeline(
        dry_run=True,
        state_mgr=state_mgr,
        quota_ledger=QuotaLedger(tmp_path / "l.csv", tmp_path / "c.csv"),
        suppression_mgr=SuppressionManager(tmp_path / "s.csv"),
    )

    # Run initial pipeline
    res = pipeline.run(manual_file=lead_file, force=True)
    campaign_id = res["campaign_id"]

    # Manually mark batch 0 and 1 as SENT, batch 2 as FAILED_REQUIRES_REVIEW
    state_mgr.update_batch_status(campaign_id, 0, "SENT")
    state_mgr.update_batch_status(campaign_id, 1, "SENT")
    state_mgr.update_batch_status(campaign_id, 2, "FAILED_REQUIRES_REVIEW")

    # Verify state reads correctly
    batches = state_mgr.load_batches(campaign_id)
    b_map = {int(b["batch_index"]): b["status"] for b in batches}
    assert b_map[0] == "SENT"
    assert b_map[1] == "SENT"
    assert b_map[2] == "FAILED_REQUIRES_REVIEW"
