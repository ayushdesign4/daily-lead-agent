"""Tests for niche normalization, semantic overlap, batch query construction, and dynamic fallback."""

import pytest
from src.niche_manager import (
    normalize_niche,
    is_valid_one_word_niche,
    are_niches_semantically_too_close,
    NicheManager,
    SEED_NICHES,
    QUERY_TEMPLATE,
)
from src.state_manager import StateManager


def test_is_valid_one_word_niche():
    # Valid one word niches
    assert is_valid_one_word_niche("motivation") is True
    assert is_valid_one_word_niche("mindset") is True
    assert is_valid_one_word_niche("coding") is True
    assert is_valid_one_word_niche("micro-tech") is True
    assert is_valid_one_word_niche("web_dev") is True

    # Invalid multi-word or empty niches
    assert is_valid_one_word_niche("") is False
    assert is_valid_one_word_niche("personal finance") is False
    assert is_valid_one_word_niche("real estate") is False
    assert is_valid_one_word_niche("video editing") is False
    assert is_valid_one_word_niche("cricket analysis") is False
    assert is_valid_one_word_niche("prompt engineering") is False
    assert is_valid_one_word_niche("  motivation tips  ") is False


def test_seed_niches_all_strictly_one_word():
    """Ensure every single seed niche is strictly one word and there are 300+ entries."""
    assert len(SEED_NICHES) >= 300
    for niche in SEED_NICHES:
        assert is_valid_one_word_niche(niche), f"Seed niche '{niche}' is not a valid one-word niche"


def test_normalize_niche():
    assert normalize_niche("  Motivation  ") == "motivation"
    assert normalize_niche("MOTIVATION") == "motivation"
    assert normalize_niche("mindset") == "mindset"
    assert normalize_niche("  Tech   Reviews  ") == "tech reviews"
    assert normalize_niche("Tech-Reviews!") == "tech reviews"


def test_case_insensitivity_in_deduplication(tmp_path):
    """Case variants of the same niche (e.g. Motivation, motivation, MOTIVATION) must be treated as the same."""
    state = StateManager(tmp_path / "m.csv", tmp_path / "q.csv", tmp_path / "n.csv", tmp_path / "r.csv")
    niche_mgr = NicheManager(state)

    state.record_used_niches([
        {"niche": "Motivation", "date_used": "2026-09-29", "query_text": "q1"},
        {"niche": "MINDSET", "date_used": "2026-09-29", "query_text": "q2"},
    ])

    used_set = niche_mgr.get_used_normalized_niches()
    assert "motivation" in used_set
    assert "mindset" in used_set

    # Batch selection must not pick motivation or mindset even if cased differently
    batch = niche_mgr.select_batch_niches(count=10)
    batch_names = [b[0].lower() for b in batch]
    assert "motivation" not in batch_names
    assert "mindset" not in batch_names


def test_semantic_overlap():
    assert are_niches_semantically_too_close("Stock Market", "Stock Market Trading") is True
    assert are_niches_semantically_too_close("investing", "invest") is True
    assert are_niches_semantically_too_close("trading", "trade") is True
    assert are_niches_semantically_too_close("fitness", "coding") is False
    assert are_niches_semantically_too_close("motivation", "mindset") is False


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

    # Check query format and ensure strictly one-word niches
    for name, query in batch1:
        assert is_valid_one_word_niche(name)
        assert len(name.split()) == 1
        expected = QUERY_TEMPLATE.format(niche=name)
        assert query == expected
        assert "site:youtube.com" in query
        assert f'"{name}"' in query
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


def test_fresh_repository_empty_used_niches(tmp_path):
    """Fresh repository with empty used_niches.csv -> unused niches are available from curated pool."""
    state = StateManager(tmp_path / "m.csv", tmp_path / "q.csv", tmp_path / "n.csv", tmp_path / "r.csv")
    niche_mgr = NicheManager(state)

    assert len(niche_mgr.get_used_normalized_niches()) == 0
    batch = niche_mgr.select_batch_niches(count=10)
    assert len(batch) == 10
    # Curated pool should contain at least 300+ niches
    assert len(SEED_NICHES) >= 300
    # All selected should come from curated seed niches and be one word
    seed_norms = {normalize_niche(s) for s in SEED_NICHES}
    for name, query in batch:
        assert is_valid_one_word_niche(name)
        assert normalize_niche(name) in seed_norms


def test_partially_used_niche_pool(tmp_path):
    """Partially used niche pool -> only unused niches are selected, no duplicates."""
    state = StateManager(tmp_path / "m.csv", tmp_path / "q.csv", tmp_path / "n.csv", tmp_path / "r.csv")
    niche_mgr = NicheManager(state)

    # Use first 20 seed niches
    used_sample = [
        {"niche": niche, "date_used": "2026-09-29", "query_text": f"query {i}"}
        for i, niche in enumerate(SEED_NICHES[:20])
    ]
    state.record_used_niches(used_sample)

    assert len(niche_mgr.get_used_normalized_niches()) == 20

    batch = niche_mgr.select_batch_niches(count=10)
    assert len(batch) == 10

    used_norms = {normalize_niche(n["niche"]) for n in used_sample}
    for name, _ in batch:
        assert is_valid_one_word_niche(name)
        assert normalize_niche(name) not in used_norms


def test_all_curated_niches_used_dynamic_generation_fallback(tmp_path):
    """All curated niches used -> dynamic generation/fallback produces strictly one-word niches."""
    state = StateManager(tmp_path / "m.csv", tmp_path / "q.csv", tmp_path / "n.csv", tmp_path / "r.csv")
    niche_mgr = NicheManager(state)

    # Mark all curated seed niches as used
    all_seeds_used = [
        {"niche": niche, "date_used": "2026-09-28", "query_text": f"query {i}"}
        for i, niche in enumerate(SEED_NICHES)
    ]
    state.record_used_niches(all_seeds_used)

    assert len(niche_mgr.get_used_normalized_niches()) == len(SEED_NICHES)

    # Should dynamically generate 10 fresh niches
    batch = niche_mgr.select_batch_niches(count=10)
    assert len(batch) == 10

    used_norms = {normalize_niche(s) for s in SEED_NICHES}
    for name, query in batch:
        # Strictly one word
        assert is_valid_one_word_niche(name), f"Dynamic niche '{name}' is not one word"
        assert len(name.split()) == 1
        # None of the dynamic niches should match any used curated niche
        assert normalize_niche(name) not in used_norms
        assert "site:youtube.com" in query


def test_previously_used_niches_never_selected_again(tmp_path):
    """Previously used niches are never selected again across consecutive batches."""
    state = StateManager(tmp_path / "m.csv", tmp_path / "q.csv", tmp_path / "n.csv", tmp_path / "r.csv")
    niche_mgr = NicheManager(state)

    all_selected_names = set()

    # Run 5 batches of 10 = 50 niches
    for b in range(5):
        batch = niche_mgr.select_batch_niches(count=10)
        assert len(batch) == 10

        batch_names = [normalize_niche(item[0]) for item in batch]
        # Intra-batch uniqueness
        assert len(batch_names) == len(set(batch_names))

        # Cross-batch uniqueness: none should have been selected in prior batches
        for name in batch_names:
            assert name not in all_selected_names
            all_selected_names.add(name)

        # Record this batch as used
        niche_mgr.record_batch_as_used(batch, date_str="2026-09-30")

    assert len(all_selected_names) == 50
