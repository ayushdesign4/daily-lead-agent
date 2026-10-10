"""Tests for BCC-only addressing, To field constant, and template rotation."""

import pytest
from src.outreach.template_manager import TemplateManager, APPROVED_TEMPLATES
from src.outreach.sender import OutreachSender, OutreachAccount


def test_to_field_is_always_ayush_and_bcc_only():
    account = OutreachAccount("sender1@gmail.com", "pass1")
    sender = OutreachSender(to_email="ayush@ayushdesign.site", dry_run=True)

    recipients = ["creator1@gmail.com", "creator2@gmail.com"]
    msg = sender.build_message(
        sender_email=account.email,
        subject="Thumbnail",
        body_text="Test body",
    )

    # Header inspections
    assert msg["To"] == "ayush@ayushdesign.site"
    assert msg["From"] == "sender1@gmail.com"
    assert "Cc" not in msg
    assert "Bcc" not in msg  # BCC MUST NOT be placed in MIME headers!

    # Verify recipients are NOT visible in header string
    raw_header = msg.as_string()
    assert "creator1@gmail.com" not in raw_header
    assert "creator2@gmail.com" not in raw_header


def test_three_template_rotation_pattern():
    """Verify deterministic 1, 2, 3, 1, 2, 3... pattern."""
    expected_ids = [1, 2, 3, 1, 2, 3, 1, 2, 3]

    for idx, expected in enumerate(expected_ids):
        tmpl_id, body = TemplateManager.get_template_for_batch(idx)
        assert tmpl_id == expected
        assert body == APPROVED_TEMPLATES[expected]
        assert "Ayush" in body


def test_nine_distinct_short_subjects():
    subjects = [TemplateManager.get_subject_for_batch(i) for i in range(9)]
    # All 9 subjects must be non-empty and distinct
    assert len(subjects) == 9
    assert len(set(subjects)) == 9
    for s in subjects:
        assert len(s) > 0
        assert len(s) < 30  # short subjects
