"""Tests for address normalization, syntax filtering, and deduplication."""

import pytest
from src.outreach.address_normalizer import normalize_address, filter_and_deduplicate_addresses


def test_normalize_address_valid():
    assert normalize_address("  Test.User@Gmail.COM  ") == "Test.User@gmail.com"
    assert normalize_address("creator+sponsor@domain.co.in") == "creator+sponsor@domain.co.in"


def test_normalize_address_invalid():
    assert normalize_address("") is None
    assert normalize_address("not_an_email") is None
    assert normalize_address("missing_domain@") is None
    assert normalize_address("@missing_local.com") is None
    assert normalize_address("spaces in@domain.com") is None
    assert normalize_address(None) is None


def test_filter_and_deduplicate_addresses():
    raw = [
        "  User1@Domain.COM  ",
        "user1@domain.com",       # duplicate
        "USER1@DOMAIN.COM",       # duplicate
        "invalid@@email.com",     # malformed
        "   ",                   # blank
        "user2@domain.com",       # valid 2
        "user3@domain.org",       # valid 3
    ]

    unique, malformed, dups = filter_and_deduplicate_addresses(raw)
    assert len(unique) == 3
    assert unique == ["User1@domain.com", "user2@domain.com", "user3@domain.org"]
    assert malformed == 2
    assert dups == 2
