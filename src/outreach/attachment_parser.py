"""Attachment parsing for TXT and CSV lead files with SHA-256 integrity calculation."""

import csv
import io
import hashlib
import logging
from pathlib import Path
from typing import List, Tuple, Union, Optional

logger = logging.getLogger(__name__)


def compute_content_hash(content: Union[str, bytes]) -> str:
    """Calculate SHA-256 digest of content for tamper detection and idempotency."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def parse_lead_file(
    content_or_path: Union[str, bytes, Path],
    filename: Optional[str] = None
) -> Tuple[List[str], str, str]:
    """
    Parse a lead file (TXT or CSV) from a file path or raw string/bytes.
    Handles:
    - .txt: one email per line
    - .csv: email column detection ('email', 'leads', 'contact', etc.) or first column
    - missing/extra columns, empty lines, whitespace
    - returns (raw_email_list, sha256_hash, detected_filename)
    """
    if isinstance(content_or_path, Path):
        file_path = content_or_path
        filename = filename or file_path.name
        with open(file_path, "rb") as f:
            raw_bytes = f.read()
    elif isinstance(content_or_path, bytes):
        raw_bytes = content_or_path
        filename = filename or "leads.txt"
    elif isinstance(content_or_path, str):
        # Could be path as str or raw text
        if Path(content_or_path).is_file():
            file_path = Path(content_or_path)
            filename = filename or file_path.name
            with open(file_path, "rb") as f:
                raw_bytes = f.read()
        else:
            raw_bytes = content_or_path.encode("utf-8")
            filename = filename or "leads.txt"
    else:
        raise ValueError(f"Unsupported content type: {type(content_or_path)}")

    content_hash = compute_content_hash(raw_bytes)

    # Decode safely with fallback
    for encoding in ["utf-8-sig", "utf-8", "latin-1", "ascii"]:
        try:
            text = raw_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw_bytes.decode("utf-8", errors="replace")

    lower_name = (filename or "").lower()
    raw_emails: List[str] = []

    if lower_name.endswith(".csv"):
        # CSV parsing
        try:
            reader = csv.reader(io.StringIO(text))
            rows = list(reader)
            if not rows:
                return [], content_hash, filename

            header = [c.strip().lower() for c in rows[0]]
            email_col_idx = -1

            # Check known email column names
            for candidate in ["email", "e-mail", "lead", "leads", "contact"]:
                if candidate in header:
                    email_col_idx = header.index(candidate)
                    break

            start_idx = 1 if email_col_idx != -1 else 0
            if email_col_idx == -1:
                # Default to column 0 if no header found
                email_col_idx = 0

            for r in rows[start_idx:]:
                if not r or len(r) <= email_col_idx:
                    continue
                val = r[email_col_idx].strip()
                if val:
                    raw_emails.append(val)
        except Exception as e:
            logger.warning(f"Error parsing as CSV ({e}), falling back to line-by-line: {filename}")
            for line in text.splitlines():
                stripped = line.strip()
                if stripped:
                    raw_emails.append(stripped)
    else:
        # Default TXT parsing: one per line
        for line in text.splitlines():
            stripped = line.strip()
            if stripped:
                raw_emails.append(stripped)

    logger.info(f"Parsed {len(raw_emails)} raw entries from {filename} (hash: {content_hash[:12]}...)")
    return raw_emails, content_hash, filename
