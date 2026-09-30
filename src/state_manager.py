"""State manager handling atomic read/write operations for master database, queue, niches, and runs."""

import csv
import os
import tempfile
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple

from src.config import (
    MASTER_LEADS_FILE,
    PENDING_QUEUE_FILE,
    USED_NICHES_FILE,
    DAILY_RUNS_FILE,
    IST_TIMEZONE_OFFSET_HOURS,
)

logger = logging.getLogger(__name__)

# CSV Headers as specified in requirements
MASTER_LEADS_HEADERS = ["email", "date_first_seen", "source_niche", "source_run_id"]
PENDING_QUEUE_HEADERS = ["email", "date_added", "source_niche", "source_run_id"]
USED_NICHES_HEADERS = ["niche", "date_used", "query_text"]
DAILY_RUNS_HEADERS = ["date", "status", "target", "delivered", "reason", "run_id"]


def get_current_ist_time() -> datetime:
    """Return current timestamp in Indian Standard Time (UTC+5:30)."""
    ist = timezone(timedelta(hours=IST_TIMEZONE_OFFSET_HOURS))
    return datetime.now(ist)


def get_today_ist_date() -> str:
    """Return today's date formatted as YYYY-MM-DD in IST."""
    return get_current_ist_time().strftime("%Y-%m-%d")


def atomic_write_csv(file_path: Path, headers: List[str], rows: List[Dict[str, str]]) -> None:
    """
    Atomically write rows to a CSV file.
    Writes to a temporary file in the same directory first, then replaces the target file.
    This guarantees no corrupted or partial files if a crash occurs mid-write.
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = None
    try:
        # Create temp file in the same directory to allow atomic os.replace across filesystem boundaries
        with tempfile.NamedTemporaryFile("w", newline="", encoding="utf-8", dir=file_path.parent, delete=False) as f:
            temp_file = Path(f.name)
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
            f.flush()
            os.fsync(f.fileno())

        # Atomic replacement
        os.replace(temp_file, file_path)
    except Exception as e:
        logger.error(f"Failed atomic write to {file_path}: {e}")
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
            except OSError:
                pass
        raise


class StateManager:
    """Manages persistent data files and state transitions."""

    def __init__(
        self,
        master_file: Path = MASTER_LEADS_FILE,
        queue_file: Path = PENDING_QUEUE_FILE,
        niches_file: Path = USED_NICHES_FILE,
        runs_file: Path = DAILY_RUNS_FILE,
    ):
        self.master_file = master_file
        self.queue_file = queue_file
        self.niches_file = niches_file
        self.runs_file = runs_file
        self.initialize_files()

    def initialize_files(self) -> None:
        """Create empty CSV files with correct headers if they do not exist."""
        for path, headers in [
            (self.master_file, MASTER_LEADS_HEADERS),
            (self.queue_file, PENDING_QUEUE_HEADERS),
            (self.niches_file, USED_NICHES_HEADERS),
            (self.runs_file, DAILY_RUNS_HEADERS),
        ]:
            if not path.exists() or path.stat().st_size == 0:
                atomic_write_csv(path, headers, [])

    # ----------------- Master Database Operations -----------------

    def load_master_leads(self) -> Dict[str, Dict[str, str]]:
        """
        Load all lifetime master leads.
        Returns a dict mapping normalized lowercase email -> lead row dict.
        """
        self.initialize_files()
        leads: Dict[str, Dict[str, str]] = {}
        with open(self.master_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                email = row.get("email", "").strip().lower()
                if email:
                    leads[email] = row
        return leads

    def add_to_master(self, new_records: List[Dict[str, str]]) -> int:
        """
        Append new records to the master database atomically.
        Only adds emails not already present.
        Returns count of newly added records.
        """
        existing = self.load_master_leads()
        rows_to_keep = list(existing.values())
        added_count = 0

        for rec in new_records:
            email = rec.get("email", "").strip().lower()
            if email and email not in existing:
                existing[email] = rec
                rows_to_keep.append(rec)
                added_count += 1

        if added_count > 0:
            atomic_write_csv(self.master_file, MASTER_LEADS_HEADERS, rows_to_keep)
            logger.info(f"Added {added_count} leads to lifetime master database (total now: {len(rows_to_keep)})")

        return added_count

    # ----------------- Pending Queue Operations -----------------

    def load_queue(self) -> List[Dict[str, str]]:
        """Load pending queue leads in FIFO order."""
        self.initialize_files()
        queue: List[Dict[str, str]] = []
        with open(self.queue_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                email = row.get("email", "").strip().lower()
                if email:
                    queue.append(row)
        return queue

    def save_queue(self, queue_rows: List[Dict[str, str]]) -> None:
        """Atomically overwrite pending queue."""
        atomic_write_csv(self.queue_file, PENDING_QUEUE_HEADERS, queue_rows)
        logger.info(f"Pending queue updated. Total in queue: {len(queue_rows)}")

    def pop_from_queue(self, count: int) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
        """
        Pop up to `count` leads from queue.
        Returns (popped_leads, remaining_queue).
        Does not save immediately; caller saves when state transition succeeds.
        """
        queue = self.load_queue()
        popped = queue[:count]
        remaining = queue[count:]
        return popped, remaining

    def add_to_queue(self, new_records: List[Dict[str, str]]) -> int:
        """
        Append extra leads to the pending queue.
        Ensures no duplicate emails within the queue.
        Returns number of items actually added.
        """
        queue = self.load_queue()
        existing_emails = {row["email"].strip().lower() for row in queue}

        added = 0
        for rec in new_records:
            email = rec.get("email", "").strip().lower()
            if email and email not in existing_emails:
                clean_rec = {
                    "email": email,
                    "date_added": rec.get("date_added") or rec.get("date_first_seen") or get_today_ist_date(),
                    "source_niche": rec.get("source_niche", ""),
                    "source_run_id": rec.get("source_run_id", ""),
                }
                queue.append(clean_rec)
                existing_emails.add(email)
                added += 1

        if added > 0:
            self.save_queue(queue)
            logger.info(f"Added {added} extra leads to pending queue (queue size: {len(queue)})")
        return added

    # ----------------- Used Niches Operations -----------------

    def load_used_niches(self) -> List[Dict[str, str]]:
        """Load all recorded used niches."""
        self.initialize_files()
        niches: List[Dict[str, str]] = []
        with open(self.niches_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("niche"):
                    niches.append(row)
        return niches

    def record_used_niches(self, new_niches: List[Dict[str, str]]) -> None:
        """Atomically record newly used niches."""
        existing = self.load_used_niches()
        existing_keys = {n["niche"].strip().lower() for n in existing}

        added = 0
        for item in new_niches:
            key = item["niche"].strip().lower()
            if key and key not in existing_keys:
                existing.append(item)
                existing_keys.add(key)
                added += 1

        if added > 0:
            atomic_write_csv(self.niches_file, USED_NICHES_HEADERS, existing)
            logger.info(f"Recorded {added} new used niches (total recorded: {len(existing)})")

    # ----------------- Daily Runs / Idempotency -----------------

    def load_daily_runs(self) -> List[Dict[str, str]]:
        """Load history of daily runs."""
        self.initialize_files()
        runs: List[Dict[str, str]] = []
        with open(self.runs_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                runs.append(row)
        return runs

    def is_already_delivered_today(self, date_str: Optional[str] = None) -> bool:
        """
        Check whether today's delivery has already been successfully sent.
        Prevents duplicate daily emails if workflow runs multiple times.
        """
        if not date_str:
            date_str = get_today_ist_date()

        runs = self.load_daily_runs()
        for run in runs:
            if run.get("date") == date_str:
                status = run.get("status", "")
                try:
                    delivered = int(run.get("delivered", "0") or "0")
                except ValueError:
                    delivered = 0
                if status in ("SENT", "COMPLETED") or (status == "PARTIAL_CREDIT_LIMIT" and delivered > 0):
                    return True
        return False

    def record_daily_run(
        self,
        date_str: str,
        status: str,
        target: int,
        delivered: int,
        reason: str,
        run_id: str,
    ) -> None:
        """Record or update today's run status in daily_runs.csv."""
        runs = self.load_daily_runs()
        # Check if there is already an entry for this run_id or date
        updated = False
        new_row = {
            "date": date_str,
            "status": status,
            "target": str(target),
            "delivered": str(delivered),
            "reason": reason,
            "run_id": run_id,
        }

        for i, run in enumerate(runs):
            if run.get("date") == date_str and run.get("run_id") == run_id:
                runs[i] = new_row
                updated = True
                break

        if not updated:
            runs.append(new_row)

        atomic_write_csv(self.runs_file, DAILY_RUNS_HEADERS, runs)
        logger.info(f"Daily run recorded: date={date_str}, status={status}, delivered={delivered}/{target}")
