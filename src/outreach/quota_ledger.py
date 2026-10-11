"""Persistent quota ledger and verification cache for email verifier accounts."""

import csv
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple, Set, List
from src.state_manager import atomic_write_csv, get_today_ist_date
from src.outreach.config import (
    VERIFICATION_LEDGER_FILE,
    VERIFICATION_CACHE_FILE,
    MAX_VERIFICATIONS_PER_ACCOUNT_PER_DAY,
)

logger = logging.getLogger(__name__)

LEDGER_HEADERS = ["date", "account_id", "count_used"]
CACHE_HEADERS = ["email", "account_id", "status", "date_verified", "raw_result"]


class QuotaLedger:
    """Manages daily verification credit consumption and prevents double verification."""

    def __init__(
        self,
        ledger_file: Optional[Path] = None,
        cache_file: Optional[Path] = None,
        max_daily_quota_per_key: int = MAX_VERIFICATIONS_PER_ACCOUNT_PER_DAY,
    ):
        self.ledger_file = ledger_file or VERIFICATION_LEDGER_FILE
        self.cache_file = cache_file or VERIFICATION_CACHE_FILE
        self.max_daily_quota = max_daily_quota_per_key
        self._ensure_files()

    def _ensure_files(self) -> None:
        self.ledger_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.ledger_file.exists():
            atomic_write_csv(self.ledger_file, LEDGER_HEADERS, [])
        if not self.cache_file.exists():
            atomic_write_csv(self.cache_file, CACHE_HEADERS, [])

    def get_daily_usage(self, account_id: str, date_str: Optional[str] = None) -> int:
        """Get total verification requests used by an account on a given date."""
        if not date_str:
            date_str = get_today_ist_date()

        if not self.ledger_file.exists():
            return 0

        with open(self.ledger_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("date") == date_str and row.get("account_id") == account_id:
                    try:
                        return int(row.get("count_used", 0))
                    except ValueError:
                        return 0
        return 0

    def get_remaining_quota(self, account_id: str, date_str: Optional[str] = None) -> int:
        """Get remaining allowed verifications for an account today."""
        used = self.get_daily_usage(account_id, date_str)
        return max(0, self.max_daily_quota - used)

    def record_usage(self, account_id: str, count: int, date_str: Optional[str] = None) -> int:
        """
        Record additional verifications used by an account today.
        Returns total updated usage for today.
        """
        if not date_str:
            date_str = get_today_ist_date()

        rows: List[Dict[str, str]] = []
        found = False
        new_total = count

        if self.ledger_file.exists():
            with open(self.ledger_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("date") == date_str and row.get("account_id") == account_id:
                        found = True
                        prev = int(row.get("count_used", 0) or 0)
                        new_total = prev + count
                        row["count_used"] = str(new_total)
                    rows.append(row)

        if not found:
            rows.append({
                "date": date_str,
                "account_id": account_id,
                "count_used": str(new_total),
            })

        atomic_write_csv(self.ledger_file, LEDGER_HEADERS, rows)
        logger.info(f"Updated usage for {account_id} on {date_str}: {new_total}/{self.max_daily_quota}")
        return new_total

    def mark_account_exhausted(self, account_id: str, date_str: Optional[str] = None) -> None:
        """Mark account as having 0 remaining quota for the given date."""
        if not date_str:
            date_str = get_today_ist_date()

        rows: List[Dict[str, str]] = []
        found = False
        if self.ledger_file.exists():
            with open(self.ledger_file, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if row.get("date") == date_str and row.get("account_id") == account_id:
                        found = True
                        row["count_used"] = str(self.max_daily_quota)
                    rows.append(row)

        if not found:
            rows.append({
                "date": date_str,
                "account_id": account_id,
                "count_used": str(self.max_daily_quota),
            })

        atomic_write_csv(self.ledger_file, LEDGER_HEADERS, rows)
        logger.warning(f"Account {account_id} marked as fully exhausted on {date_str} (0 remaining)")

    def get_cached_result(self, email: str) -> Optional[Dict[str, str]]:
        """Return cached verification result if previously checked with definitive status."""
        norm_email = email.strip().lower()
        if not self.cache_file.exists():
            return None

        with open(self.cache_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("email", "").strip().lower() == norm_email:
                    # Do not treat cached errors as definitive
                    if row.get("status") in ("valid", "invalid", "risky", "unknown"):
                        return row
        return None

    def purge_error_results(self) -> int:
        """Purge any transient verification_error entries from cache file."""
        if not self.cache_file.exists():
            return 0

        clean_rows: List[Dict[str, str]] = []
        purged = 0
        with open(self.cache_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("status") == "verification_error":
                    purged += 1
                else:
                    clean_rows.append(row)

        if purged > 0:
            atomic_write_csv(self.cache_file, CACHE_HEADERS, clean_rows)
            logger.info(f"Purged {purged} transient error entries from verification cache.")
        return purged

    def cache_verification_results(self, records: List[Dict[str, str]]) -> None:
        """Store newly verified results in persistent cache. Only caches definitive outcomes."""
        if not records:
            return

        existing: List[Dict[str, str]] = []
        if self.cache_file.exists():
            with open(self.cache_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                existing = list(reader)

        seen_emails = {r.get("email", "").lower() for r in existing}
        for rec in records:
            # Only cache definitive results; never cache transient errors or quota exhaustion
            if rec.get("status") in ("valid", "invalid", "risky", "unknown"):
                if rec.get("email", "").lower() not in seen_emails:
                    existing.append(rec)
                    seen_emails.add(rec.get("email", "").lower())

        atomic_write_csv(self.cache_file, CACHE_HEADERS, existing)
