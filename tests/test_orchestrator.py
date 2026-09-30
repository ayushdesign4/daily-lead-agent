"""Comprehensive integration tests for DailyLeadAgent scenarios."""

import pytest
from unittest.mock import MagicMock
from pathlib import Path

from src.main import DailyLeadAgent
from src.state_manager import StateManager
from src.apify_client import ApifyClient, ApifyCreditExhaustedError
from src.delivery import DeliveryManager


@pytest.fixture
def test_env(tmp_path):
    master_file = tmp_path / "master.csv"
    queue_file = tmp_path / "queue.csv"
    niches_file = tmp_path / "used_niches.csv"
    runs_file = tmp_path / "runs.csv"

    state = StateManager(master_file, queue_file, niches_file, runs_file)

    mock_apify = MagicMock(spec=ApifyClient)
    mock_delivery = MagicMock(spec=DeliveryManager)
    # Mock lead file generation
    mock_delivery.generate_lead_file.return_value = tmp_path / "leads_test.txt"
    mock_delivery.send_daily_leads.return_value = True

    return {
        "state": state,
        "apify": mock_apify,
        "delivery": mock_delivery,
        "tmp_path": tmp_path,
    }


def test_scenario_a_queue_has_sufficient_leads(test_env):
    """
    Example A from Spec:
    If pending queue contains 250 unsent leads:
    - Do NOT call Apify.
    - Select 200 from queue for today's delivery.
    - Keep remaining 50 in queue.
    - Send today's TXT file.
    - No unnecessary Apify credits used.
    """
    state = test_env["state"]
    mock_apify = test_env["apify"]
    mock_delivery = test_env["delivery"]

    # Seed 250 leads in queue
    leads = [
        {"email": f"queued_{i}@gmail.com", "date_added": "2026-09-29", "source_niche": "Tech", "source_run_id": "PREV"}
        for i in range(250)
    ]
    state.add_to_queue(leads)

    agent = DailyLeadAgent(
        target=200,
        dry_run=False,
        state_manager=state,
        apify_client=mock_apify,
        delivery_manager=mock_delivery,
    )

    delivered = agent.run(force=True)

    assert delivered == 200
    # Apify must NOT be called
    mock_apify.run_search_batch.assert_not_called()
    # 50 must remain in queue
    assert len(state.load_queue()) == 50
    # Delivery must be called with 200 leads
    mock_delivery.send_daily_leads.assert_called_once()


def test_scenario_b_queue_shortage_batch_surplus(test_env):
    """
    Example B from Spec:
    Daily target = 200, Queue = 73, Shortage = 127.
    Batch 1 produces 280 genuinely new emails:
    - 127 satisfy today's shortage.
    - Remaining 153 go to queue.
    - STOP. Do not run another batch.
    """
    state = test_env["state"]
    mock_apify = test_env["apify"]
    mock_delivery = test_env["delivery"]

    # Seed 73 leads in queue
    leads = [
        {"email": f"queued_{i}@gmail.com", "date_added": "2026-09-29", "source_niche": "Tech", "source_run_id": "PREV"}
        for i in range(73)
    ]
    state.add_to_queue(leads)

    # Mock Apify returning 280 new emails
    mock_dataset = [
        {"snippet": f"Contact for business: creator_{i}@gmail.com"}
        for i in range(280)
    ]
    mock_apify.run_search_batch.return_value = mock_dataset

    agent = DailyLeadAgent(
        target=200,
        dry_run=False,
        state_manager=state,
        apify_client=mock_apify,
        delivery_manager=mock_delivery,
    )

    delivered = agent.run(force=True)

    assert delivered == 200
    # Exactly 1 batch must be run
    assert mock_apify.run_search_batch.call_count == 1
    # 153 surplus leads must be in queue
    assert len(state.load_queue()) == 153
    # Master DB must now have all 280 newly discovered emails
    assert len(state.load_master_leads()) == 280


def test_scenario_c_credit_exhaustion_graceful_handling(test_env):
    """
    Scenario C from Spec (Credit exhaustion):
    Starting queue: 20 leads. Shortage: 180.
    Batch 1: 50 new leads obtained.
    Batch 2: Apify reports insufficient credits.
    System:
    - Sends 70 available leads (20 from queue + 50 from batch 1).
    - Sends Apify credit alert email with Google Form link.
    - Stops further Apify calls.
    - Preserves all data.
    """
    state = test_env["state"]
    mock_apify = test_env["apify"]
    mock_delivery = test_env["delivery"]

    # Seed 20 leads in queue
    leads = [
        {"email": f"queued_{i}@gmail.com", "date_added": "2026-09-29", "source_niche": "Tech", "source_run_id": "PREV"}
        for i in range(20)
    ]
    state.add_to_queue(leads)

    # Batch 1 returns 50 leads, Batch 2 raises ApifyCreditExhaustedError
    mock_apify.run_search_batch.side_effect = [
        [{"snippet": f"Email: creator_{i}@gmail.com"} for i in range(50)],
        ApifyCreditExhaustedError("Free tier usage limit reached. No compute units remaining."),
    ]

    agent = DailyLeadAgent(
        target=200,
        dry_run=False,
        state_manager=state,
        apify_client=mock_apify,
        delivery_manager=mock_delivery,
    )

    delivered = agent.run(force=True)

    # Delivered available 70 leads
    assert delivered == 70
    # Alert email must be sent
    mock_delivery.send_credit_exhaustion_alert.assert_called_once()
    # Daily email must also be sent with 70 leads
    mock_delivery.send_daily_leads.assert_called_once()
    # State recorded as PARTIAL_CREDIT_LIMIT
    runs = state.load_daily_runs()
    assert runs[-1]["status"] == "PARTIAL_CREDIT_LIMIT"


def test_scenario_d_idempotency_prevents_duplicate_send(test_env):
    """
    Scenario D: Idempotency protection.
    If run has already executed today, second run without --force must not send emails.
    """
    state = test_env["state"]
    mock_apify = test_env["apify"]
    mock_delivery = test_env["delivery"]

    agent = DailyLeadAgent(
        target=10,
        dry_run=True,
        state_manager=state,
        apify_client=mock_apify,
        delivery_manager=mock_delivery,
    )

    # First run
    agent.run(force=True)

    # Second run without force
    delivered_second = agent.run(force=False)
    assert delivered_second == 0
