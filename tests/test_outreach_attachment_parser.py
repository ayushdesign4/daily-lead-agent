"""Tests for attachment parsing across TXT and CSV formats."""

import pytest
from pathlib import Path
from src.outreach.attachment_parser import parse_lead_file, compute_content_hash


def test_parse_txt_file(tmp_path):
    txt_file = tmp_path / "leads_2026-10-01.txt"
    txt_file.write_text("user1@gmail.com\nuser2@gmail.com\n\nuser3@gmail.com\n", encoding="utf-8")

    raw, chash, fn = parse_lead_file(txt_file)
    assert len(raw) == 3
    assert raw == ["user1@gmail.com", "user2@gmail.com", "user3@gmail.com"]
    assert len(chash) == 64
    assert fn == "leads_2026-10-01.txt"


def test_parse_csv_standard_header(tmp_path):
    csv_file = tmp_path / "leads.csv"
    csv_file.write_text("Name,Email,Channel\nAlice,alice@gmail.com,Ch1\nBob,bob@gmail.com,Ch2\n", encoding="utf-8")

    raw, chash, fn = parse_lead_file(csv_file)
    assert raw == ["alice@gmail.com", "bob@gmail.com"]


def test_parse_csv_missing_extra_columns(tmp_path):
    csv_file = tmp_path / "leads_irregular.csv"
    # Row with extra columns, row with missing column, blank rows
    content = "Email,Notes\nlead1@test.com,Note1,ExtraCol\n\nlead2@test.com\n,EmptyEmail\nlead3@test.com\n"
    csv_file.write_text(content, encoding="utf-8")

    raw, chash, fn = parse_lead_file(csv_file)
    assert raw == ["lead1@test.com", "lead2@test.com", "lead3@test.com"]


def test_parse_csv_no_header_fallback(tmp_path):
    csv_file = tmp_path / "no_header.csv"
    csv_file.write_text("first@gmail.com,other1\nsecond@gmail.com,other2\n", encoding="utf-8")

    raw, chash, fn = parse_lead_file(csv_file)
    assert raw == ["first@gmail.com", "second@gmail.com"]


def test_content_hash_deterministic():
    data = "creator@gmail.com\n"
    hash1 = compute_content_hash(data)
    hash2 = compute_content_hash(data.encode("utf-8"))
    assert hash1 == hash2
    assert len(hash1) == 64
