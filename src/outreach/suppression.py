"""Suppression list management for unsubscribed, bounced, or excluded recipients."""

import csv
import logging
from pathlib import Path
from typing import Set, List, Dict, Optional, Tuple
from src.state_manager import atomic_write_csv, get_today_ist_date
from src.outreach.config import OUTREACH_SUPPRESSIONS_FILE

logger = logging.getLogger(__name__)

SUPPRESSION_HEADERS = ["email", "reason", "date_added"]


class SuppressionManager:
    """Maintains a persistent suppression list and checks addresses against it."""

    def __init__(self, file_path: Optional[Path] = None):
        self.file_path = file_path or OUTREACH_SUPPRESSIONS_FILE
        self._ensure_file()

    def _ensure_file(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            atomic_write_csv(self.file_path, SUPPRESSION_HEADERS, [])

    def load_suppressed_set(self) -> Set[str]:
        """Return a set of all lowercased suppressed emails."""
        if not self.file_path.exists():
            return set()

        suppressed = set()
        with open(self.file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                em = row.get("email", "").strip().lower()
                if em:
                    suppressed.add(em)
        return suppressed

    def is_suppressed(self, email: str) -> bool:
        """Check if an email is on the suppression list."""
        return email.strip().lower() in self.load_suppressed_set()

    def add_suppression(self, email: str, reason: str = "unsubscribed", date_str: Optional[str] = None) -> None:
        """Add an address to the suppression list."""
        if not date_str:
            date_str = get_today_ist_date()

        norm = email.strip().lower()
        rows: List[Dict[str, str]] = []
        if self.file_path.exists():
            with open(self.file_path, "r", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))

        if not any(r.get("email", "").strip().lower() == norm for r in rows):
            rows.append({
                "email": norm,
                "reason": reason,
                "date_added": date_str,
            })
            atomic_write_csv(self.file_path, SUPPRESSION_HEADERS, rows)
            logger.info(f"Added {norm} to suppression list (reason: {reason})")

    def filter_eligible(self, emails: List[str]) -> Tuple[List[str], int]:
        """Filter out any emails that appear on the suppression list."""
        suppressed_set = self.load_suppressed_set()
        eligible = []
        suppressed_count = 0

        for em in emails:
            if em.strip().lower() in suppressed_set:
                suppressed_count += 1
            else:
                eligible.append(em)

        return eligible, suppressed_count
