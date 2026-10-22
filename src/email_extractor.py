"""Email extraction, cleaning, normalization, and strict validation."""

import re
import logging
from typing import List, Set, Any, Dict

logger = logging.getLogger(__name__)

# Strict regex matching requirement from specification Section 8
EMAIL_REGEX = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)

# Unambiguous spaced email candidate regex (e.g. "creator @ gmail.com" or "creator @ gmail . com")
# Negative lookahead (?!\s+[A-Z]) prevents matching across sentence boundaries like "in. Also"
SPACED_EMAIL_REGEX = re.compile(
    r"\b([A-Za-z0-9._%+-]+)\s*@\s*([A-Za-z0-9-]+(?:\.[a-zA-Z0-9-]+)*\s*\.\s*(?!\s+[A-Z])[A-Za-z]{2,10})\b"
)

# Common invalid file extensions that can masquerade as TLDs in text
INVALID_TLDS = {
    "png", "jpg", "jpeg", "gif", "webp", "svg", "bmp",
    "mp4", "mp3", "mov", "avi", "pdf", "zip", "exe", "js", "css"
}

# Example / placeholder domains to reject
EXCLUDED_DOMAINS = {
    "example.com", "sample.com", "domain.com", "email.com",
    "test.com", "localhost", "sentry.io", "wixpress.com"
}


def clean_and_normalize_email(raw_candidate: str) -> str:
    """
    Normalize email:
    - strip whitespace
    - lowercase
    - strip surrounding punctuation (quotes, brackets, trailing periods, commas)
    - safely repair unambiguous spacing around @ and domain dots
    """
    if not raw_candidate or not isinstance(raw_candidate, str):
        return ""
    text = raw_candidate.strip().lower()
    # Strip common enclosing punctuation
    text = text.strip("<>\"'()[]{}.,:;!*?")

    # Safely repair unambiguous spacing around @ and dots if local and domain labels have no internal spaces
    if "@" in text and text.count("@") == 1:
        parts = text.split("@")
        local = parts[0].strip()
        domain = parts[1].strip()
        if " " not in local:
            domain_labels = [lbl.strip() for lbl in domain.split(".")]
            if all(" " not in lbl and len(lbl) > 0 for lbl in domain_labels) and len(domain_labels) >= 2:
                text = f"{local}@{'.'.join(domain_labels)}"

    return text


def is_valid_email(email: str) -> bool:
    """
    Validate that an email string strictly complies with email standards
    and doesn't match false positives or invalid TLDs.
    """
    if not email or len(email) > 254:
        return False

    if not EMAIL_REGEX.fullmatch(email):
        return False

    parts = email.split("@")
    if len(parts) != 2:
        return False

    local_part, domain = parts
    if not local_part or not domain:
        return False

    # Check for consecutive dots or leading/trailing dots in parts
    if ".." in email or local_part.startswith(".") or local_part.endswith("."):
        return False
    if domain.startswith(".") or domain.endswith("."):
        return False

    domain_parts = domain.split(".")
    tld = domain_parts[-1].lower()
    if tld in INVALID_TLDS:
        return False

    if domain in EXCLUDED_DOMAINS:
        return False

    return True


def extract_emails_from_text(text: str) -> Set[str]:
    """Search arbitrary text for all valid email addresses."""
    if not text or not isinstance(text, str):
        return set()

    valid_emails = set()

    # Pass 1: Standard RFC-compliant matches
    for item in EMAIL_REGEX.findall(text):
        cleaned = clean_and_normalize_email(item)
        if is_valid_email(cleaned):
            valid_emails.add(cleaned)

    # Pass 2: Unambiguous spaced emails (e.g. "creator @ gmail.com" or "creator @ gmail . com")
    for match in SPACED_EMAIL_REGEX.finditer(text):
        cleaned = clean_and_normalize_email(match.group(0))
        if is_valid_email(cleaned):
            valid_emails.add(cleaned)

    return valid_emails


def extract_emails_from_item(item: Dict[str, Any]) -> Set[str]:
    """
    Extract valid emails from any text fields of a scraper item,
    including organicResults, title, description, url, snippets.
    """
    emails: Set[str] = set()

    def walk_and_extract(obj: Any):
        if isinstance(obj, str):
            emails.update(extract_emails_from_text(obj))
        elif isinstance(obj, dict):
            for val in obj.values():
                walk_and_extract(val)
        elif isinstance(obj, list):
            for elem in obj:
                walk_and_extract(elem)

    walk_and_extract(item)
    return emails


# Retain alias for Apify backward compatibility
extract_emails_from_apify_item = extract_emails_from_item


def extract_emails_from_dataset(dataset_items: List[Dict[str, Any]]) -> List[str]:
    """
    Extract all unique normalized valid emails from an entire Apify dataset batch.
    Preserves first-seen order while removing intra-batch duplicates.
    """
    seen: Set[str] = set()
    result: List[str] = []

    for item in dataset_items:
        extracted = extract_emails_from_apify_item(item)
        for email in extracted:
            if email not in seen:
                seen.add(email)
                result.append(email)

    logger.info(f"Extracted {len(result)} unique valid emails from {len(dataset_items)} dataset items")
    return result
