"""Email address normalization and syntax validation."""

import re
import logging
from typing import Optional, List, Set, Tuple

logger = logging.getLogger(__name__)

# RFC 5322 compatible regex for practical email validation
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)


def normalize_address(email: str) -> Optional[str]:
    """
    Normalize email address:
    - Trim whitespace
    - Lowercase domain portion (and lowercase overall for deduplication)
    - Validate syntax
    Returns normalized email string, or None if invalid/malformed.
    """
    if not email or not isinstance(email, str):
        return None

    cleaned = email.strip()
    if not cleaned or "@" not in cleaned:
        return None

    parts = cleaned.split("@", 1)
    if len(parts) != 2:
        return None

    local_part, domain = parts[0].strip(), parts[1].strip().lower()
    if not local_part or not domain:
        return None

    normalized = f"{local_part}@{domain}"

    # Syntax validation
    if not EMAIL_REGEX.match(normalized):
        return None

    # Length constraints
    if len(normalized) > 254 or len(local_part) > 64 or len(domain) > 253:
        return None

    return normalized


def filter_and_deduplicate_addresses(raw_emails: List[str]) -> Tuple[List[str], int, int]:
    """
    Takes a raw list of email strings:
    - Normalizes each
    - Discards invalid/blank entries
    - Deduplicates case-insensitively while preserving stable first-seen order
    Returns:
        (unique_valid_emails, malformed_count, duplicate_count)
    """
    seen: Set[str] = set()
    valid_list: List[str] = []
    malformed_count = 0
    duplicate_count = 0

    for raw in raw_emails:
        norm = normalize_address(raw)
        if not norm:
            malformed_count += 1
            continue

        key = norm.lower()
        if key in seen:
            duplicate_count += 1
            continue

        seen.add(key)
        valid_list.append(norm)

    return valid_list, malformed_count, duplicate_count
