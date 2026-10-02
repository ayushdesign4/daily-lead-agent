"""Comprehensive integration tests for DailyLeadAgent scenarios."""

import pytest
from unittest.mock import MagicMock
from pathlib import Path

from src.main import DailyLeadAgent
from src.state_manager import StateManager, get_today_ist_date
from src.apify_client import ApifyClient, ApifyCreditExhaustedError, ApifyTimeoutError, ApifyError
from src.niche_manager import is_valid_one_word_niche
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

    delivered = agent.run(force=True, mode="deliver")

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

    delivered = agent.run(force=True, mode="deliver")

    assert delivered == 200
    # Exactly 1 batch must be run
    assert mock_apify.run_search_batch.call_count == 1
    # 153 surplus leads must remain in queue (73 initial + 280 scraped - 200 delivered = 153)
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

    delivered = agent.run(force=True, mode="deliver")

    # Delivered available 70 leads
    assert delivered == 70
    # Alert email must be sent
    mock_delivery.send_credit_exhaustion_alert.assert_called_once()
    # Daily email must also be sent with 70 leads
    mock_delivery.send_daily_leads.assert_called_once()
    # State recorded as PARTIAL_CREDIT_LIMIT
    runs = state.load_daily_runs()
    assert runs[-1]["status"] == "PARTIAL_CREDIT_LIMIT"


def test_overnight_run_does_not_send_daily_email(test_env):
    """
    Requirement 1:
    The 01:00 AM overnight workflow must ONLY prepare/process leads.
    It must NOT send the daily lead email.
    """
    state = test_env["state"]
    mock_apify = test_env["apify"]
    mock_delivery = test_env["delivery"]

    # Mock Apify returning 150 emails
    mock_apify.run_search_batch.return_value = [
        {"snippet": f"Email: creator_{i}@gmail.com"} for i in range(150)
    ]

    agent = DailyLeadAgent(
        target=100,
        dry_run=False,
        state_manager=state,
        apify_client=mock_apify,
        delivery_manager=mock_delivery,
    )

    # Run overnight preparation
    count_prepared = agent.run(force=True, mode="prepare")

    # Queue must have the prepared leads
    assert count_prepared >= 100
    assert len(state.load_queue()) >= 100
    # DAILY EMAIL MUST NOT BE SENT
    mock_delivery.send_daily_leads.assert_not_called()
    # Run status recorded as PREPARED
    runs = state.load_daily_runs()
    assert runs[-1]["status"] == "PREPARED"


def test_11_am_delivery_sends_exactly_once(test_env):
    """
    Requirement 1 & 5:
    The actual daily lead email is sent around 11:00 AM IST and sends exactly once (idempotent).
    """
    state = test_env["state"]
    mock_apify = test_env["apify"]
    mock_delivery = test_env["delivery"]

    # Prepare 50 leads in queue
    leads = [
        {"email": f"queued_{i}@gmail.com", "date_added": "2026-09-30", "source_niche": "Tech", "source_run_id": "PREV"}
        for i in range(50)
    ]
    state.add_to_queue(leads)

    agent = DailyLeadAgent(
        target=50,
        dry_run=False,
        state_manager=state,
        apify_client=mock_apify,
        delivery_manager=mock_delivery,
    )

    # First delivery at 11 AM
    delivered_1 = agent.run(force=False, mode="deliver")
    assert delivered_1 == 50
    assert mock_delivery.send_daily_leads.call_count == 1

    # Second delivery check at 11 AM (same day, no force)
    delivered_2 = agent.run(force=False, mode="deliver")
    assert delivered_2 == 0
    # Still called only once!
    assert mock_delivery.send_daily_leads.call_count == 1


def test_delivery_failure_restores_leads_to_queue(test_env):
    """
    Requirement 2 & 3:
    Never permanently remove leads from pending_queue.csv before successful delivery.
    If Gmail delivery fails, the selected leads remain safely in the queue.
    """
    state = test_env["state"]
    mock_apify = test_env["apify"]
    mock_delivery = test_env["delivery"]

    # Seed 50 leads in queue
    leads = [
        {"email": f"queued_{i}@gmail.com", "date_added": "2026-09-30", "source_niche": "Tech", "source_run_id": "PREV"}
        for i in range(50)
    ]
    state.add_to_queue(leads)

    # Simulate Gmail SMTP failure
    mock_delivery.send_daily_leads.return_value = False

    agent = DailyLeadAgent(
        target=50,
        dry_run=False,
        state_manager=state,
        apify_client=mock_apify,
        delivery_manager=mock_delivery,
    )

    delivered = agent.run(force=True, mode="deliver")
    assert delivered == 0

    # QUEUE MUST STILL CONTAIN ALL 50 LEADS!
    assert len(state.load_queue()) == 50
    runs = state.load_daily_runs()
    assert runs[-1]["status"] == "DELIVERY_FAILED"


def test_newly_discovered_leads_not_lost_when_delivery_fails(test_env):
    """
    Requirement 2 & 3:
    Newly discovered leads are not permanently lost if delivery fails immediately after scraping.
    """
    state = test_env["state"]
    mock_apify = test_env["apify"]
    mock_delivery = test_env["delivery"]

    # Queue initially empty
    assert len(state.load_queue()) == 0

    # Apify discovers 30 new leads
    mock_apify.run_search_batch.return_value = [
        {"snippet": f"Email: new_creator_{i}@gmail.com"} for i in range(30)
    ]

    # SMTP delivery fails
    mock_delivery.send_daily_leads.side_effect = Exception("SMTP connection failure")

    agent = DailyLeadAgent(
        target=30,
        dry_run=False,
        state_manager=state,
        apify_client=mock_apify,
        delivery_manager=mock_delivery,
    )

    delivered = agent.run(force=True, mode="deliver")
    assert delivered == 0

    # Leads must be safely recorded in master DB AND pending queue!
    assert len(state.load_master_leads()) == 30
    assert len(state.load_queue()) == 30


def test_more_than_5_batches_can_run_when_required(test_env):
    """
    Requirement 4:
    Remove arbitrary 5-batch limit.
    Continue demand-driven batches while fewer than target leads are obtained.
    """
    state = test_env["state"]
    mock_apify = test_env["apify"]
    mock_delivery = test_env["delivery"]

    # Each batch returns only 10 unique leads
    mock_apify.run_search_batch.side_effect = [
        [{"snippet": f"Email: b{batch}_{i}@gmail.com"} for i in range(10)]
        for batch in range(10)
    ]

    # Target 70 leads -> requires 7 batches (7 > 5)
    agent = DailyLeadAgent(
        target=70,
        dry_run=False,
        state_manager=state,
        apify_client=mock_apify,
        delivery_manager=mock_delivery,
    )

    delivered = agent.run(force=True, mode="deliver")
    assert delivered == 70

    # Apify was called exactly 7 times (> 5 batches!)
    assert mock_apify.run_search_batch.call_count == 7
    # Queue remaining should be 0
    assert len(state.load_queue()) == 0


def test_processing_stops_immediately_once_target_satisfied(test_env):
    """
    Requirement 4:
    Stop immediately when the daily target is satisfied. Never run unnecessary batches.
    """
    state = test_env["state"]
    mock_apify = test_env["apify"]
    mock_delivery = test_env["delivery"]

    # Target: 50. Batch 1 returns 30. Batch 2 returns 40 (total 70 >= 50).
    mock_apify.run_search_batch.side_effect = [
        [{"snippet": f"Email: b1_{i}@gmail.com"} for i in range(30)],
        [{"snippet": f"Email: b2_{i}@gmail.com"} for i in range(40)],
        [{"snippet": f"Email: b3_{i}@gmail.com"} for i in range(30)],  # Should NEVER be called
    ]

    agent = DailyLeadAgent(
        target=50,
        dry_run=False,
        state_manager=state,
        apify_client=mock_apify,
        delivery_manager=mock_delivery,
    )

    delivered = agent.run(force=True, mode="deliver")
    assert delivered == 50
    # Must stop after batch 2!
    assert mock_apify.run_search_batch.call_count == 2
    # 20 surplus leads in queue (30 + 40 - 50 = 20)
    assert len(state.load_queue()) == 20


def test_api_token_replacement_preserves_all_data(test_env):
    """
    Requirement 5:
    Changing the Apify API token must never reset or delete any existing data
    (master database, queue, niche history, or daily run history).
    """
    state = test_env["state"]
    mock_delivery = test_env["delivery"]

    # Populate state with initial records
    state.add_to_master([
        {"email": "saved@gmail.com", "date_first_seen": "2026-09-28", "source_niche": "Tech", "source_run_id": "OLD_KEY"}
    ])
    state.add_to_queue([
        {"email": "queued@gmail.com", "date_added": "2026-09-28", "source_niche": "Tech", "source_run_id": "OLD_KEY"}
    ])
    state.record_used_niches([
        {"niche": "Old Tech", "date_used": "2026-09-28", "query_text": "site:youtube.com ..."}
    ])
    state.record_daily_run(
        date_str="2026-09-28",
        status="COMPLETED",
        target=1,
        delivered=1,
        reason="Delivered 1 lead",
        run_id="OLD_KEY",
    )

    # Now create an agent with a completely new Apify token
    new_mock_apify = MagicMock(spec=ApifyClient)
    new_agent = DailyLeadAgent(
        target=10,
        dry_run=False,
        state_manager=state,
        apify_client=new_mock_apify,
        delivery_manager=mock_delivery,
    )

    # Verify that data files are completely preserved
    assert "saved@gmail.com" in state.load_master_leads()
    assert len(state.load_queue()) == 1
    assert state.load_queue()[0]["email"] == "queued@gmail.com"
    assert len(state.load_used_niches()) == 1
    assert state.load_used_niches()[0]["niche"] == "Old Tech"
    assert len(state.load_daily_runs()) == 1


def test_apify_timeout_handled_gracefully(test_env):
    """
    Requirement 1:
    If Apify actor run times out, treat it as a proper failure, do NOT process dataset
    as if it succeeded, and continue gracefully without crashing.
    """
    state = test_env["state"]
    mock_apify = test_env["apify"]
    mock_delivery = test_env["delivery"]

    # Apify raises timeout error
    mock_apify.run_search_batch.side_effect = ApifyTimeoutError("Run timed out after 600s")

    agent = DailyLeadAgent(
        target=50,
        dry_run=False,
        state_manager=state,
        apify_client=mock_apify,
        delivery_manager=mock_delivery,
    )

    # Should handle gracefully without raising unhandled exception
    count = agent.run(force=True, mode="prepare")
    assert count == 0
    # No leads extracted or delivered
    assert len(state.load_master_leads()) == 0
    assert len(state.load_queue()) == 0


def test_delivery_receipt_prevents_duplicate_send_if_subsequent_state_fails(test_env):
    """
    Requirement 2:
    Edge case where Gmail successfully sends lead file, but saving/updating delivery state
    fails immediately afterward (e.g. disk write error or crash).
    Subsequent runs must detect the verified delivery receipt, reconcile queue,
    and prevent duplicate sends.
    """
    state = test_env["state"]
    mock_apify = test_env["apify"]
    mock_delivery = test_env["delivery"]

    # Seed 20 leads in queue
    leads = [
        {"email": f"delivered_{i}@gmail.com", "date_added": "2026-09-30", "source_niche": "Tech", "source_run_id": "PREV"}
        for i in range(20)
    ]
    state.add_to_queue(leads)

    agent = DailyLeadAgent(
        target=20,
        dry_run=False,
        state_manager=state,
        apify_client=mock_apify,
        delivery_manager=mock_delivery,
    )

    # First run succeeds in delivery
    delivered = agent.run(force=True, mode="deliver")
    assert delivered == 20
    assert mock_delivery.send_daily_leads.call_count == 1
    assert state.has_delivery_receipt(get_today_ist_date()) is True

    # Now simulate that daily_runs.csv was somehow wiped or failed to save status
    state.initialize_files()
    from src.state_manager import atomic_write_csv, DAILY_RUNS_HEADERS
    atomic_write_csv(state.runs_file, DAILY_RUNS_HEADERS, [])

    # Second run without force
    second_delivered = agent.run(force=False, mode="deliver")
    assert second_delivered == 0
    # Email MUST NOT have been sent a second time!
    assert mock_delivery.send_daily_leads.call_count == 1
    # State was successfully reconciled
    runs = state.load_daily_runs()
    assert any(r.get("status") in ("COMPLETED", "SENT") for r in runs)


def test_batch_failure_resilience_recovers_in_next_batch(test_env):
    """
    Requirement 5:
    If an Apify batch times out or encounters a transient error, the agent must NOT terminate.
    It should log the error, preserve previous leads, and continue to the next fresh batch
    with unused niches until the daily target is reached.
    """
    state = test_env["state"]
    mock_apify = test_env["apify"]
    mock_delivery = test_env["delivery"]

    # Batch 1 times out; Batch 2 succeeds with 25 valid leads
    batch_2_dataset = [
        {"snippet": f"Contact for collaboration: creator_batch2_{i}@gmail.com"}
        for i in range(25)
    ]
    mock_apify.run_search_batch.side_effect = [
        ApifyTimeoutError("Platform timed out on batch 1"),
        batch_2_dataset,
    ]

    agent = DailyLeadAgent(
        target=20,
        dry_run=False,
        state_manager=state,
        apify_client=mock_apify,
        delivery_manager=mock_delivery,
    )

    delivered = agent.run(force=True, mode="all")
    assert delivered == 20
    # 2 batches were triggered on Apify
    assert mock_apify.run_search_batch.call_count == 2
    # Target was satisfied despite batch 1 failure
    assert len(state.load_master_leads()) == 25
    assert len(state.load_queue()) == 5
    mock_delivery.send_daily_leads.assert_called_once()


def test_orchestrator_only_selects_and_records_one_word_niches(test_env):
    """
    Requirement 1 & 3:
    Every niche selected and persisted by the orchestrator must be strictly ONE WORD.
    No multi-word phrases.
    """
    state = test_env["state"]
    mock_apify = test_env["apify"]
    mock_delivery = test_env["delivery"]

    mock_dataset = [
        {"snippet": f"Contact: creator_{i}@gmail.com"}
        for i in range(10)
    ]
    mock_apify.run_search_batch.return_value = mock_dataset

    agent = DailyLeadAgent(
        target=10,
        dry_run=False,
        state_manager=state,
        apify_client=mock_apify,
        delivery_manager=mock_delivery,
    )

    delivered = agent.run(force=True, mode="all")
    assert delivered == 10

    # Inspect used_niches.csv
    used_niches = state.load_used_niches()
    assert len(used_niches) > 0
    for row in used_niches:
        niche = row["niche"]
        assert is_valid_one_word_niche(niche), f"Recorded niche '{niche}' is not a valid one-word niche"
        assert len(niche.split()) == 1, f"Recorded niche '{niche}' has more than one word"
        # Check query template
        query = row["query_text"]
        assert f'"{niche}"' in query
        assert "site:youtube.com" in query


