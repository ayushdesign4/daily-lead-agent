"""Tests for niche normalization, semantic overlap, and batch query construction."""

import pytest
from src.niche_manager import (
    normalize_niche,
    are_niches_semantically_too_close,
    NicheManager,
    QUERY_TEMPLATE,
)
from src.state_manager import StateManager


def test_normalize_niche():
    assert normalize_niche("  Tech   Reviews  ") == "tech reviews"
    assert normalize_niche("Tech-Reviews!") == "tech reviews"
    assert normalize_niche("Personal Finance...") == "personal finance"
    assert normalize_niche("STOCK   TRADING") == "stock trading"


def test_semantic_overlap():
    assert are_niches_semantically_too_close("Stock Market", "Stock Market Trading") is True
    assert are_niches_semantically_too_close("Yoga Meditation Practice", "Meditation Practice") is True
    assert are_niches_semantically_too_close("Tech Reviews", "Cooking Recipes") is False
    assert are_niches_semantically_too_close("Fitness Workout", "Real Estate Investing") is False


def test_niche_batch_selection_and_persistence(tmp_path):
    # Setup isolated test CSV files
    master_file = tmp_path / "master.csv"
    queue_file = tmp_path / "queue.csv"
    niches_file = tmp_path / "used_niches.csv"
    runs_file = tmp_path / "runs.csv"

    state = StateManager(master_file, queue_file, niches_file, runs_file)
    niche_mgr = NicheManager(state)

    # First batch of 5
    batch1 = niche_mgr.select_batch_niches(count=5)
    assert len(batch1) == 5

    # Check query format
    for name, query in batch1:
        expected = QUERY_TEMPLATE.format(niche=name)
        assert query == expected
        assert "site:youtube.com" in query
        assert '"Business Inquiries"' in query
        assert '"gmail.com"' in query
        assert "India" in query

    # Record batch 1 as used
    niche_mgr.record_batch_as_used(batch1, date_str="2026-09-30")

    # Select second batch: must NOT contain any niches from batch 1
    batch2 = niche_mgr.select_batch_niches(count=5)
    assert len(batch2) == 5

    batch1_names = {normalize_niche(b[0]) for b in batch1}
    batch2_names = {normalize_niche(b[0]) for b in batch2}
    assert len(batch1_names.intersection(batch2_names)) == 0
