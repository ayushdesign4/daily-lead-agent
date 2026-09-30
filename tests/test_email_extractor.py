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
