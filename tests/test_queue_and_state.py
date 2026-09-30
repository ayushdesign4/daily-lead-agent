"""Tests for StateManager and QueueManager atomic behavior and queue rules."""

import pytest
from src.state_manager import StateManager
from src.queue_manager import QueueManager


def test_atomic_state_and_queue(tmp_path):
    master_file = tmp_path / "master.csv"
    queue_file = tmp_path / "queue.csv"
    niches_file = tmp_path / "used_niches.csv"
    runs_file = tmp_path / "runs.csv"

    state = StateManager(master_file, queue_file, niches_file, runs_file)
    queue_mgr = QueueManager(state)

    # 1. Initially empty
    assert queue_mgr.get_queue_size() == 0

    # 2. Add surplus leads
    leads = [
        {"email": f"surplus{i}@gmail.com", "date_added": "2026-09-30", "source_niche": "Tech", "source_run_id": "R1"}
        for i in range(10)
    ]
    added = queue_mgr.add_leads(leads)
    assert added == 10
    assert queue_mgr.get_queue_size() == 10

    # 3. Add same emails again -> deduplicated in queue
    added_again = queue_mgr.add_leads(leads)
    assert added_again == 0
    assert queue_mgr.get_queue_size() == 10

    # 4. Consume partial leads (e.g. need 4)
    consumed, shortage = queue_mgr.consume_leads(target_count=4)
    assert len(consumed) == 4
    assert shortage == 0
    assert queue_mgr.get_queue_size() == 6
    assert consumed[0]["email"] == "surplus0@gmail.com"

    # 5. Consume more than remaining (e.g. need 10)
    consumed2, shortage2 = queue_mgr.consume_leads(target_count=10)
    assert len(consumed2) == 6
    assert shortage2 == 4  # 10 requested - 6 available = 4 remaining shortage
    assert queue_mgr.get_queue_size() == 0


def test_idempotency_check(tmp_path):
    master_file = tmp_path / "master.csv"
    queue_file = tmp_path / "queue.csv"
    niches_file = tmp_path / "used_niches.csv"
    runs_file = tmp_path / "runs.csv"

    state = StateManager(master_file, queue_file, niches_file, runs_file)

    assert state.is_already_delivered_today("2026-09-30") is False

    # Record completed run
    state.record_daily_run(
        date_str="2026-09-30",
        status="COMPLETED",
        target=200,
        delivered=200,
        reason="Delivered 200 leads",
        run_id="R123",
    )

    assert state.is_already_delivered_today("2026-09-30") is True
    # Different date is not delivered
    assert state.is_already_delivered_today("2026-10-01") is False
