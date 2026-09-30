"""Tests for lead TXT generation and Gmail delivery logic."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.delivery import DeliveryManager


def test_generate_lead_file(tmp_path):
    delivery = DeliveryManager()
    emails = ["creator1@gmail.com", "creator2@gmail.com", "creator3@gmail.com"]

    with patch("src.delivery.OUTPUT_DIR", tmp_path):
        file_path = delivery.generate_lead_file(emails, "2026-09-30")

        assert file_path.exists()
        assert file_path.name == "leads_2026-09-30.txt"

        lines = [line.strip() for line in file_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert lines == emails
        # Ensure ONLY emails, no header, no extra text
        assert len(lines) == 3


def test_send_daily_leads_dry_run(tmp_path):
    delivery = DeliveryManager(username="user@gmail.com", password="pwd", recipient="to@gmail.com", dry_run=True)
    fake_file = tmp_path / "leads_2026-09-30.txt"
    fake_file.write_text("a@b.com\n", encoding="utf-8")

    # In dry run mode, it should return True without calling smtplib
    result = delivery.send_daily_leads(
        file_path=fake_file,
        lead_count=200,
        queue_remaining=50,
        date_str="2026-09-30",
    )
    assert result is True


def test_send_credit_exhaustion_alert_dry_run():
    delivery = DeliveryManager(username="user@gmail.com", password="pwd", recipient="to@gmail.com", dry_run=True)

    result = delivery.send_credit_exhaustion_alert(
        date_str="2026-09-30",
        error_details="Insufficient Apify credits",
        leads_obtained_today=120,
        today_target=200,
        shortfall=80,
        daily_file_sent=True,
    )
    assert result is True
