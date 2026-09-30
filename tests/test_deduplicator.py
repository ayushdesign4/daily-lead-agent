"""Tests for deduplication within batch and against master database."""

import pytest
from src.deduplicator import Deduplicator


def test_deduplicator():
    # Lifetime master database mock
    master_leads = {
        "old_creator1@gmail.com": {"email": "old_creator1@gmail.com"},
        "old_creator2@gmail.com": {"email": "old_creator2@gmail.com"},
    }
    dedup = Deduplicator(master_leads)

    extracted = [
        "new1@gmail.com",
        "NEW1@GMAIL.COM",  # Intra-batch duplicate
        "old_creator1@gmail.com",  # Master database duplicate
        "new2@gmail.com",
        "new1@gmail.com",  # Another intra-batch duplicate
        "old_creator2@gmail.com",  # Master database duplicate
        "new3@gmail.com",
    ]

    genuinely_new, intra_dups, master_dups = dedup.filter_new_emails(extracted)

    assert genuinely_new == ["new1@gmail.com", "new2@gmail.com", "new3@gmail.com"]
    assert intra_dups == 2  # 2 repeats of new1
    assert master_dups == 2  # old_creator1 and old_creator2
