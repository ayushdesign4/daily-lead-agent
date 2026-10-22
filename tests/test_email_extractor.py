"""Tests for email extraction, normalization, and validation."""

import pytest
from src.email_extractor import (
    clean_and_normalize_email,
    is_valid_email,
    extract_emails_from_text,
    extract_emails_from_apify_item,
    extract_emails_from_dataset,
)


def test_clean_and_normalize_email():
    assert clean_and_normalize_email("  Test@Example.Com  ") == "test@example.com"
    assert clean_and_normalize_email("<creator@youtube.in>") == "creator@youtube.in"
    assert clean_and_normalize_email('"contact@channel.com"') == "contact@channel.com"
    assert clean_and_normalize_email("(business@studio.co.in).") == "business@studio.co.in"


def test_is_valid_email():
    assert is_valid_email("creator@gmail.com") is True
    assert is_valid_email("business.inquiries@channel.co.in") is True
    assert is_valid_email("tech_reviews+work@sub.domain.org") is True

    # Invalid cases
    assert is_valid_email("") is False
    assert is_valid_email("plainaddress") is False
    assert is_valid_email("@missingusername.com") is False
    assert is_valid_email("username@.com") is False
    assert is_valid_email("username@domain..com") is False
    assert is_valid_email("thumbnail@2x.png") is False
    assert is_valid_email("banner@1080p.jpg") is False
    assert is_valid_email("fake@example.com") is False


def test_extract_emails_from_text():
    sample_text = (
        "For business inquiries, reach out at info@techchannel.com! "
        "Alternative: (contact.creators@gmail.com). Don't use asset@icon.png."
    )
    emails = extract_emails_from_text(sample_text)
    assert "info@techchannel.com" in emails
    assert "contact.creators@gmail.com" in emails
    assert "asset@icon.png" not in emails


def test_extract_emails_from_apify_item():
    item = {
        "title": "Top Tech YouTuber | Contact: sponsor@techindia.com",
        "description": "Send reviews to gear@techindia.com or sponsor@techindia.com",
        "organicResults": [
            {
                "snippet": "For brand deals: brands@agency.in",
                "url": "https://www.youtube.com/@channel/about"
            }
        ]
    }
    emails = extract_emails_from_apify_item(item)
    assert emails == {"sponsor@techindia.com", "gear@techindia.com", "brands@agency.in"}


def test_extract_emails_from_dataset():
    dataset = [
        {"snippet": "Email: user1@gmail.com, user2@gmail.com"},
        {"snippet": "Repeat: user1@gmail.com and new user3@gmail.com"},
    ]
    unique_list = extract_emails_from_dataset(dataset)
    assert len(unique_list) == 3
    assert set(unique_list) == {"user1@gmail.com", "user2@gmail.com", "user3@gmail.com"}


def test_conservative_normalization_and_formatting_artifacts():
    """Verify safe conservative normalization of Bright Data search snippet artifacts."""
    # 1. Spacing artifacts around delimiters
    assert clean_and_normalize_email("creator @ gmail.com") == "creator@gmail.com"
    assert clean_and_normalize_email("creator @ gmail . com") == "creator@gmail.com"
    assert clean_and_normalize_email("  john@example.com  ") == "john@example.com"
    assert clean_and_normalize_email("<creator@gmail.com>") == "creator@gmail.com"
    assert clean_and_normalize_email("(creator@gmail.com),") == "creator@gmail.com"
    assert clean_and_normalize_email("ayush.design+biz@gmail.com") == "ayush.design+biz@gmail.com"

    # 2. Text extraction with spacing artifacts
    text_with_spaces = (
        "Contact: creator @ gmail.com or team @ agency . in. "
        "Also write to <partner@youtube.com>, and ayush.design+biz@gmail.com. "
        "Do NOT decode obfuscated: secret [at] gmail [dot] com. "
        "Do NOT repair broken word spaces: jo hn@gmail.com or bad..syntax@gmail.com."
    )
    extracted = extract_emails_from_text(text_with_spaces)
    assert "creator@gmail.com" in extracted
    assert "team@agency.in" in extracted
    assert "partner@youtube.com" in extracted
    assert "ayush.design+biz@gmail.com" in extracted

    # Ensure ambiguous obfuscation is NOT guessed or extracted
    assert not any("secret" in e for e in extracted)
    # Ensure broken local parts are NOT accepted
    assert not any("jo hn" in e or "bad..syntax" in e for e in extracted)
