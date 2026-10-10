"""Tests for 9-way recipient distribution balance and disjoint invariants."""

import pytest
from src.outreach.distributor import distribute_recipients


def test_distribution_balanced_within_one():
    senders = [f"sender{i+1}@gmail.com" for i in range(9)]

    # Test cases with various recipient pool sizes
    for n in [0, 5, 9, 10, 20, 99, 100, 185, 200]:
        emails = [f"lead_{i:03d}@creator.com" for i in range(n)]
        batches = distribute_recipients(emails, senders)

        assert len(batches) == 9
        counts = [b["count"] for b in batches]

        if n > 0:
            assert max(counts) - min(counts) <= 1, f"Failed for n={n}: counts={counts}"

        # Total count check
        assert sum(counts) == n

        # Every recipient appears exactly once
        assigned = [em for b in batches for em in b["recipients"]]
        assert len(assigned) == len(set(assigned)) == n


def test_deterministic_distribution():
    senders = [f"sender{i+1}@gmail.com" for i in range(9)]
    emails = [f"lead_{i}@creator.com" for i in range(50)]

    run1 = distribute_recipients(emails, senders)
    run2 = distribute_recipients(list(reversed(emails)), senders)

    for b1, b2 in zip(run1, run2):
        assert b1["sender_account"] == b2["sender_account"]
        assert b1["recipients"] == b2["recipients"]
