"""
Tests for Niche Keyword Quality and Quantity Preservation.
Validates:
1. Final pool size is at least as large as the previously deployed pool (>= 5,106).
2. Keywords are strictly unique after normalization (lowercase, punctuation, whitespace).
3. Every single keyword present in used_niches.csv is strictly excluded from the pool.
4. Keywords strictly satisfy one-word format (no spaces, no digits).
5. No synthetic numbered fallback keywords exist in the pool.
6. The pool contains recognizable, diverse YouTube creator sub-niches across core domains.
"""

import csv
from pathlib import Path
import pytest

from src.curated_niches import CURATED_NICHES
from src.niche_manager import is_valid_one_word_niche, normalize_niche


def test_niche_pool_quantity_not_reduced():
    """Ensure the compiled niche pool is at least 5,106 entries."""
    assert len(CURATED_NICHES) >= 5106, f"Pool decreased: {len(CURATED_NICHES)} < 5106"


def test_niche_pool_normalized_uniqueness():
    """Ensure 100% of keywords in the pool are unique after normalization."""
    normalized_list = [normalize_niche(n) for n in CURATED_NICHES]
    unique_set = set(normalized_list)
    assert len(normalized_list) == len(unique_set), "Duplicate normalized niches detected in pool"


def test_niche_pool_excludes_all_used_niches():
    """Ensure zero overlap with historical used_niches.csv."""
    used_csv = Path("data/used_niches.csv")
    if not used_csv.exists():
        pytest.skip("data/used_niches.csv does not exist")

    with open(used_csv, encoding="utf-8") as f:
        used_set = {normalize_niche(r["niche"]) for r in csv.DictReader(f) if r.get("niche")}

    pool_normalized = {normalize_niche(n) for n in CURATED_NICHES}
    overlap = pool_normalized & used_set

    assert len(overlap) == 0, f"Found {len(overlap)} used niches still in curated pool: {list(overlap)[:10]}"


def test_all_niches_strictly_single_word_letters_only():
    """Ensure every niche is strictly one lexical word, pure letters, no hyphens, no underscores, no digits."""
    for n in CURATED_NICHES:
        assert is_valid_one_word_niche(n), f"Invalid niche format: {n}"
        assert n.isalpha(), f"Niche contains non-alphabetic characters: {n}"
        assert "-" not in n, f"Niche contains hyphen: {n}"
        assert "_" not in n, f"Niche contains underscore: {n}"
        assert " " not in n, f"Niche contains space: {n}"
        assert not any(c.isdigit() for c in n), f"Niche contains digits: {n}"
        assert len(n) >= 3, f"Niche too short: {n}"


def test_no_synthetic_numbered_fallbacks():
    """Ensure no artificial numbered keywords exist (e.g. creator101, gamer112)."""
    for n in CURATED_NICHES:
        assert not any(c.isdigit() for c in n), f"Synthetic numbered niche found: {n}"


def test_artificial_compound_mashups_rejected():
    """Ensure artificial concatenated multi-word phrases are strictly excluded from CURATED_NICHES."""
    pool_set = set(CURATED_NICHES)
    mashups = [
        "weddingphotography", "bathroomremodel", "cattraining", "timemanagement",
        "birdphotography", "dogtricks", "bakingtutorial", "cheflife", "vanlifevlog"
    ]
    for m in mashups:
        assert m not in pool_set, f"Artificial compound mashup found in pool: {m}"
        assert is_valid_one_word_niche(m) is False, f"Validator failed to reject mashup: {m}"


def test_established_compounds_accepted():
    """Ensure recognized, established creator single-word terms and compounds are preserved."""
    established = [
        "speedrunning", "woodcarving", "astrophotography", "calisthenic",
        "overclocking", "watercooling", "simracing", "overlanding"
    ]
    pool_set = set(CURATED_NICHES)
    for term in established:
        assert term in pool_set, f"Established creator term missing from pool: {term}"
        assert is_valid_one_word_niche(term) is True, f"Validator failed to accept established term: {term}"


def test_creator_subniches_coverage():
    """Verify presence of recognizable authentic single-word YouTube creator niches across core categories."""
    pool_set = set(CURATED_NICHES)

    # Gaming single-word niches
    assert "speedrunning" in pool_set
    assert "subnautica" in pool_set
    assert "terraria" in pool_set
    assert "cyberpunk" in pool_set
    assert "simracing" in pool_set

    # Tech single-word niches
    assert "overclocking" in pool_set
    assert "watercooling" in pool_set
    assert "audiophile" in pool_set
    assert "keycaps" in pool_set
    assert "videography" in pool_set

    # Fitness single-word niches
    assert "strongman" in pool_set
    assert "kettlebells" in pool_set
    assert "benchpress" in pool_set
    assert "deadlift" in pool_set
    assert "calisthenic" in pool_set

    # History & Science single-word niches
    assert "paleontology" in pool_set
    assert "astrophotography" in pool_set
    assert "cosmology" in pool_set
    assert "meteorology" in pool_set
    assert "oceanography" in pool_set

    # Food & Crafts single-word niches
    assert "overlanding" in pool_set
    assert "woodcarving" in pool_set
    assert "bladesmith" in pool_set
    assert "espresso" in pool_set
    assert "croissant" in pool_set
