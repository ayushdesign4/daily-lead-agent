"""
Comprehensive test suite for Phase 9: Intelligent Niche Selection & Adaptive Feedback.

Validates:
1. Alphabetical ordering no longer determines niche selection.
2. Category-based round-robin selection provides diversity.
3. Selection is deterministic and resumable across sessions.
4. Used niches are never selected again.
5. Normalized duplicates are rejected.
6. The pool contains at least 5,106 valid single-word niches.
7. Invalid, hyphenated, numbered, or artificial compound terms are rejected.
8. Under-tested niches remain eligible for exploration.
9. Proven high-yield niches receive appropriate priority.
10. Low-yield niches are down-ranked without being permanently discarded after one failure.
11. Technical failures do not count as evidence of poor niche quality.
12. Duplicate-heavy searches influence future selection appropriately.
13. Interrupted batches preserve completed work and allow safe resumption.
14. Empty categories and exhausted pools are handled without synthetic fallback terms.
15. Historical state files are not destructively changed.
16. Existing queue, master-lead deduplication, prepare/deliver modes, delivery receipts, and outreach integration remain compatible.
"""

import pytest
import csv
from pathlib import Path
from src.curated_niches import CURATED_NICHES, NICHE_CATEGORIES
from src.niche_categories import CREATOR_CATEGORIES, classify_niche
from src.niche_manager import (
    NicheManager,
    is_valid_one_word_niche,
    normalize_niche,
    are_niches_semantically_too_close,
)
from src.state_manager import StateManager


@pytest.fixture
def temp_state_manager(tmp_path):
    """Provides isolated StateManager with temporary state files."""
    master = tmp_path / "master_leads.csv"
    queue = tmp_path / "pending_queue.csv"
    niches = tmp_path / "used_niches.csv"
    runs = tmp_path / "daily_runs.csv"
    state = StateManager(master, queue, niches, runs)
    # Set isolated json state files
    state.selection_state_file = tmp_path / "niche_selection_state.json"
    state.performance_file = tmp_path / "niche_performance.json"
    return state


def test_1_alphabetical_ordering_no_longer_determines_selection(temp_state_manager):
    """Selection in a batch must NOT be sorted alphabetically (e.g. not a, b, c sequence)."""
    niche_mgr = NicheManager(temp_state_manager)
    batch = niche_mgr.select_batch_niches(count=10)
    assert len(batch) == 10
    names = [b[0] for b in batch]

    # Verify that the sequence of 10 niches is NOT in strictly alphabetical order
    assert names != sorted(names), f"Batch was strictly alphabetical: {names}"


def test_2_category_based_round_robin_selection_provides_diversity(temp_state_manager):
    """A batch of 10 niches should span across multiple distinct creator categories."""
    niche_mgr = NicheManager(temp_state_manager)
    batch = niche_mgr.select_batch_niches(count=10)
    assert len(batch) == 10

    categories = [classify_niche(b[0]) for b in batch]
    unique_categories = set(categories)
    # Batch of 10 should represent at least 6 different categories
    assert len(unique_categories) >= 6, f"Expected diverse categories, got: {unique_categories}"


def test_3_selection_is_deterministic_and_resumable(temp_state_manager):
    """Cursors advance deterministically and persist between manager instances."""
    mgr1 = NicheManager(temp_state_manager)
    batch1 = mgr1.select_batch_niches(count=5)
    mgr1.record_batch_as_used(batch1, "2026-10-20")

    # Second manager instance loads state
    mgr2 = NicheManager(temp_state_manager)
    batch2 = mgr2.select_batch_niches(count=5)

    names1 = {b[0] for b in batch1}
    names2 = {b[0] for b in batch2}
    # No overlap
    assert len(names1.intersection(names2)) == 0

    # Ensure cursors advanced in state file
    state_data = temp_state_manager.load_niche_selection_state()
    assert "category_cursors" in state_data
    assert any(cursor > 0 for cursor in state_data["category_cursors"].values())


def test_4_used_niches_never_selected_again(temp_state_manager):
    """Recorded used niches are never selected in subsequent batches."""
    mgr = NicheManager(temp_state_manager)
    batch1 = mgr.select_batch_niches(count=10)
    mgr.record_batch_as_used(batch1, "2026-10-20")

    batch2 = mgr.select_batch_niches(count=10)
    names1 = {normalize_niche(b[0]) for b in batch1}
    names2 = {normalize_niche(b[0]) for b in batch2}
    assert len(names1.intersection(names2)) == 0


def test_5_normalized_duplicates_rejected(temp_state_manager):
    """Case variations, leading spaces, or punctuation variations are treated as used."""
    temp_state_manager.record_used_niches([
        {"niche": "SPEEDRUNNING", "date_used": "2026-10-19", "query_text": "q"},
        {"niche": "  Terraria  ", "date_used": "2026-10-19", "query_text": "q"},
    ])

    mgr = NicheManager(temp_state_manager)
    batch = mgr.select_batch_niches(count=20)
    selected_norms = {normalize_niche(b[0]) for b in batch}

    assert "speedrunning" not in selected_norms
    assert "terraria" not in selected_norms


def test_6_pool_contains_at_least_5106_valid_niches():
    """Verify total niche pool quantity is >= 5,106 and all are strictly one word."""
    assert len(CURATED_NICHES) >= 5106
    for niche in CURATED_NICHES:
        assert is_valid_one_word_niche(niche)


def test_7_invalid_terms_rejected():
    """Hyphenated, spaced, numbered, or artificial glued compounds are rejected."""
    assert not is_valid_one_word_niche("minecraft-hardcore")
    assert not is_valid_one_word_niche("pc building")
    assert not is_valid_one_word_niche("gamer101")
    assert not is_valid_one_word_niche("weddingphotography")
    assert not is_valid_one_word_niche("bathroomremodel")


def test_8_under_tested_niches_remain_eligible_for_exploration(temp_state_manager):
    """Categories with zero test history are included in exploration allocation (30%)."""
    mgr = NicheManager(temp_state_manager)
    # Simulate high performance for 3 categories
    mgr.record_batch_performance(
        [("speedrunning", "q")], raw_count=50, intra_dups=0, master_dups=0, new_count=45, status="COMPLETED"
    )
    priority_order = mgr.get_category_priority_order()
    # Untested categories must still be included in priority order
    for cat in CREATOR_CATEGORIES:
        assert cat in priority_order


def test_9_proven_high_yield_niches_receive_priority(temp_state_manager):
    """Categories that produce high genuinely new lead yield rank at top of exploitation."""
    mgr = NicheManager(temp_state_manager)
    # Gaming produces 40 new leads out of 50 raw (yield ~0.78)
    mgr.record_batch_performance(
        [("speedrunning", "q")], raw_count=50, intra_dups=5, master_dups=5, new_count=40, status="COMPLETED"
    )
    # Science produces 5 new leads out of 50 raw (yield ~0.11)
    mgr.record_batch_performance(
        [("astronomy", "q")], raw_count=50, intra_dups=20, master_dups=25, new_count=5, status="COMPLETED"
    )

    priority_order = mgr.get_category_priority_order()
    assert priority_order.index("gaming") < priority_order.index("science")


def test_10_low_yield_niches_down_ranked_without_permanent_discard(temp_state_manager):
    """Low-yield categories move lower in priority order but remain in pool and available."""
    mgr = NicheManager(temp_state_manager)
    # Low yield batch
    mgr.record_batch_performance(
        [("astronomy", "q")], raw_count=50, intra_dups=25, master_dups=25, new_count=0, status="COMPLETED"
    )
    priority_order = mgr.get_category_priority_order()
    assert "science" in priority_order  # Not discarded

    # Can still select from science
    batch = mgr.select_batch_niches(count=15)
    selected_cats = {classify_niche(b[0]) for b in batch}
    assert "science" in selected_cats


def test_11_technical_failures_do_not_degrade_yield_score(temp_state_manager):
    """Apify timeout / network failure increments failures count without decreasing yield score."""
    mgr = NicheManager(temp_state_manager)
    # Establish baseline
    mgr.record_batch_performance(
        [("speedrunning", "q")], raw_count=20, intra_dups=0, master_dups=0, new_count=18, status="COMPLETED"
    )
    perf_before = mgr.load_performance_state()
    score_before = perf_before["categories"]["gaming"]["yield_score"]

    # Technical failure occurs
    mgr.record_batch_performance(
        [("speedrunning", "q")], status="FAILED", error_type="ApifyTimeoutError"
    )
    perf_after = mgr.load_performance_state()
    score_after = perf_after["categories"]["gaming"]["yield_score"]
    failures = perf_after["categories"]["gaming"]["failures"]

    assert failures == 1
    assert score_after == score_before  # Technical failure did not lower score


def test_12_duplicate_heavy_searches_influence_future_selection(temp_state_manager):
    """A category with excessive duplicates yields lower score than a category with fresh leads."""
    mgr = NicheManager(temp_state_manager)
    # Category A: 10 raw, 0 new leads (all duplicates)
    mgr.record_batch_performance(
        [("speedrunning", "q")], raw_count=30, intra_dups=15, master_dups=15, new_count=0, status="COMPLETED"
    )
    # Category B: 10 raw, 8 new leads (high yield)
    mgr.record_batch_performance(
        [("robotics", "q")], raw_count=30, intra_dups=2, master_dups=2, new_count=26, status="COMPLETED"
    )

    priority = mgr.get_category_priority_order()
    assert priority.index("technology") < priority.index("gaming")


def test_13_interrupted_batches_preserve_completed_work_and_resume_safely(temp_state_manager):
    """If a batch is staged but interrupted before record_batch_as_used, staged niches are not lost."""
    mgr1 = NicheManager(temp_state_manager)
    batch1 = mgr1.select_batch_niches(count=5)
    staged_names = [b[0] for b in batch1]

    # Process crashes here: record_batch_as_used was NEVER called
    # Run new manager instance (representing retry/resumption)
    mgr2 = NicheManager(temp_state_manager)
    batch2 = mgr2.select_batch_niches(count=5)
    resumed_names = [b[0] for b in batch2]

    # The staged niches from the interrupted batch are preserved and safely re-presented
    assert set(resumed_names) == set(staged_names)

    # Now completion succeeds and records as used
    mgr2.record_batch_as_used(batch2, "2026-10-20")

    # Third run now picks fresh niches
    mgr3 = NicheManager(temp_state_manager)
    batch3 = mgr3.select_batch_niches(count=5)
    names3 = {b[0] for b in batch3}
    assert len(names3.intersection(set(resumed_names))) == 0


def test_14_empty_categories_and_exhausted_pools_handled_without_synthetic_numbers(temp_state_manager):
    """Exhaustion of pools cleanly returns empty/partial list with zero synthetic numbers."""
    mgr = NicheManager(temp_state_manager)
    # Use all curated niches
    all_seeds = [{"niche": s, "date_used": "2026-10-20", "query_text": "q"} for s in CURATED_NICHES]
    temp_state_manager.record_used_niches(all_seeds)

    # Use all secondary dynamic combos
    prefixes = ["micro", "macro", "neuro", "cyber", "bio", "astro", "crypto", "retro", "hyper", "meta", "techno", "eco", "omni", "ultra", "pro"]
    stems = ["tech", "finance", "fitness", "coding", "gaming", "design", "media", "science", "art", "craft", "music", "health", "space", "sports", "logic", "trade", "robotics", "optics", "analytics", "motion", "vlog", "audio", "cinema", "growth", "skills", "market"]
    more_used = [{"niche": f"{p}{s}", "date_used": "2026-10-20", "query_text": "q"} for p in prefixes for s in stems]
    temp_state_manager.record_used_niches(more_used)

    # Clean exhaustion: zero results, NO creator1, vlogger101
    batch = mgr.select_batch_niches(count=10)
    assert len(batch) == 0
    for name, _ in batch:
        assert not any(c.isdigit() for c in name)


def test_15_historical_state_files_not_destructively_changed(temp_state_manager):
    """Verify state operations append or write cleanly without corrupting CSV headers or content."""
    temp_state_manager.initialize_files()
    assert temp_state_manager.master_file.exists()
    assert temp_state_manager.queue_file.exists()
    assert temp_state_manager.niches_file.exists()
    assert temp_state_manager.runs_file.exists()

    with open(temp_state_manager.niches_file, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        assert header == ["niche", "date_used", "query_text"]


def test_16_orchestrator_integration_compatibility(temp_state_manager):
    """Verify that StateManager and NicheManager integrate seamlessly with DailyLeadAgent."""
    from src.main import DailyLeadAgent
    agent = DailyLeadAgent(target=10, dry_run=True, test_mode=True, state_manager=temp_state_manager)
    assert agent.niche_manager is not None
    assert agent.queue_manager is not None
    assert agent.target == 10


def test_17_category_rotation_and_outdoors_fairness(temp_state_manager):
    """Verify that rotation across consecutive batches prevents starvation of any category (especially outdoors)."""
    mgr = NicheManager(temp_state_manager)
    category_counts = {c: 0 for c in CREATOR_CATEGORIES}

    # Simulate 22 consecutive batches of 10
    for b in range(22):
        batch = mgr.select_batch_niches(count=10)
        assert len(batch) == 10
        mgr.record_batch_as_used(batch, date_str=f"2026-10-{b+1:02d}")
        for niche, _ in batch:
            cat = classify_niche(niche)
            category_counts[cat] += 1

    # Outdoors must NOT starve: should receive at least 15 selections across 22 batches
    assert category_counts["outdoors"] >= 15, f"Outdoors starved with only {category_counts['outdoors']} selections"
    # All 11 categories must receive at least 15 selections
    for cat, count in category_counts.items():
        assert count >= 15, f"Category '{cat}' underrepresented with count {count}"


def test_18_negative_and_impossible_metrics_bounds(temp_state_manager):
    """Verify negative or impossible metrics do not produce negative yield scores or corrupt state."""
    mgr = NicheManager(temp_state_manager)
    # Negative raw and impossible new leads count
    mgr.record_batch_performance([("speedrunning", "q")], raw_count=-10, new_count=50, status="COMPLETED")
    perf = mgr.load_performance_state()
    cat_entry = perf["categories"]["gaming"]

    assert cat_entry["raw_emails"] >= 0
    assert cat_entry["new_leads"] >= 0
    assert cat_entry["yield_score"] >= 0.0
    assert cat_entry["yield_score"] <= 1.0


def test_19_small_sample_ranking_confidence(temp_state_manager):
    """Verify empirical Bayes prevents 2/2 leads from prematurely outranking a robust 36/50 leads performer."""
    mgr = NicheManager(temp_state_manager)
    # Gaming: small sample 2/2 leads
    mgr.record_batch_performance([("speedrunning", "q")], raw_count=2, new_count=2, status="COMPLETED")
    # Technology: strong sample 36/50 leads (72% conversion over 50 leads)
    mgr.record_batch_performance([("overclocking", "q")], raw_count=50, new_count=36, status="COMPLETED")

    prio = mgr.get_category_priority_order()
    # Technology with 36/50 must outrank Gaming with 2/2
    assert prio.index("technology") < prio.index("gaming")


def test_20_category_recovery_after_poor_batches(temp_state_manager):
    """Verify that a category can recover in score and priority after a successful batch."""
    mgr = NicheManager(temp_state_manager)
    # Initial poor batch: 0/30 leads
    mgr.record_batch_performance([("speedrunning", "q")], raw_count=30, new_count=0, status="COMPLETED")
    perf1 = mgr.load_performance_state()
    score_low = perf1["categories"]["gaming"]["yield_score"]

    # Subsequent strong batch: 28/30 leads
    mgr.record_batch_performance([("speedrunning", "q")], raw_count=30, new_count=28, status="COMPLETED")
    perf2 = mgr.load_performance_state()
    score_high = perf2["categories"]["gaming"]["yield_score"]

    assert score_high > score_low
    assert score_high >= 0.40  # Recovered back towards prior


def test_21_curation_anki_and_generic_fillers():
    """Verify anki is reclassified to science, and generic non-niche fillers are pruned."""
    assert classify_niche("anki") == "science"
    assert "anki" in NICHE_CATEGORIES["science"]
    assert "anki" not in NICHE_CATEGORIES["finance"]

    # Generic grammatical fillers must not be in the final pool
    generic_fillers = ["additions", "adjusted", "adjustment", "adjustable", "admissions"]
    pool_set = {n.lower() for n in CURATED_NICHES}
    for filler in generic_fillers:
        assert filler not in pool_set, f"Generic filler '{filler}' found in CURATED_NICHES"

