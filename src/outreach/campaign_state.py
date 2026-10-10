"""Campaign state machine and persistent ledger for outreach pipeline idempotency."""

import csv
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from src.state_manager import atomic_write_csv, get_today_ist_date
from src.outreach.config import OUTREACH_STATE_FILE, OUTREACH_BATCHES_FILE

logger = logging.getLogger(__name__)

CAMPAIGN_HEADERS = [
    "campaign_id",
    "date",
    "source_message_id",
    "attachment_hash",
    "status",
    "leads_parsed",
    "unique_leads",
    "verified_valid",
    "verified_invalid",
    "verified_risky",
    "verified_unknown",
    "deferred_count",
    "batches_planned",
    "batches_sent",
    "updated_at",
]

BATCH_HEADERS = [
    "campaign_id",
    "batch_index",
    "sender_account",
    "template_id",
    "subject",
    "recipient_count",
    "status",  # 'PENDING', 'SENT', 'FAILED_REQUIRES_REVIEW', 'SKIPPED_EMPTY'
    "error",
    "sent_at",
]


class CampaignState:
    """Manages persistent campaign states and batch delivery tracking."""

    def __init__(
        self,
        state_file: Optional[Path] = None,
        batches_file: Optional[Path] = None,
    ):
        self.state_file = state_file or OUTREACH_STATE_FILE
        self.batches_file = batches_file or OUTREACH_BATCHES_FILE
        self._ensure_files()

    def _ensure_files(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.state_file.exists():
            atomic_write_csv(self.state_file, CAMPAIGN_HEADERS, [])
        if not self.batches_file.exists():
            atomic_write_csv(self.batches_file, BATCH_HEADERS, [])

    def load_campaigns(self) -> List[Dict[str, str]]:
        if not self.state_file.exists():
            return []
        with open(self.state_file, "r", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def get_campaign(self, campaign_id: str) -> Optional[Dict[str, str]]:
        for c in self.load_campaigns():
            if c.get("campaign_id") == campaign_id:
                return c
        return None

    def is_campaign_completed(self, campaign_id: str) -> bool:
        c = self.get_campaign(campaign_id)
        if not c:
            return False
        return c.get("status") == "COMPLETED"

    def is_message_already_processed(self, message_id: str, attachment_hash: str) -> bool:
        """Check if message or attachment hash was already completely sent."""
        for c in self.load_campaigns():
            if (c.get("source_message_id") == message_id or c.get("attachment_hash") == attachment_hash) and c.get("status") == "COMPLETED":
                return True
        return False

    def save_campaign_state(
        self,
        campaign_id: str,
        status: str,
        source_message_id: str = "",
        attachment_hash: str = "",
        counts: Optional[Dict[str, int]] = None,
        batches_planned: int = 9,
        batches_sent: int = 0,
        date_str: Optional[str] = None,
    ) -> None:
        """Atomically record or update overall campaign state."""
        if not date_str:
            date_str = get_today_ist_date()

        counts = counts or {}
        campaigns = self.load_campaigns()
        found = False

        record = {
            "campaign_id": campaign_id,
            "date": date_str,
            "source_message_id": source_message_id,
            "attachment_hash": attachment_hash,
            "status": status,
            "leads_parsed": str(counts.get("parsed", 0)),
            "unique_leads": str(counts.get("unique", 0)),
            "verified_valid": str(counts.get("valid", 0)),
            "verified_invalid": str(counts.get("invalid", 0)),
            "verified_risky": str(counts.get("risky", 0)),
            "verified_unknown": str(counts.get("unknown", 0)),
            "deferred_count": str(counts.get("deferred", 0)),
            "batches_planned": str(batches_planned),
            "batches_sent": str(batches_sent),
            "updated_at": date_str,
        }

        new_list: List[Dict[str, str]] = []
        for c in campaigns:
            if c.get("campaign_id") == campaign_id:
                found = True
                # Preserve initial source ids if omitted
                if not source_message_id:
                    record["source_message_id"] = c.get("source_message_id", "")
                if not attachment_hash:
                    record["attachment_hash"] = c.get("attachment_hash", "")
                new_list.append(record)
            else:
                new_list.append(c)

        if not found:
            new_list.append(record)

        atomic_write_csv(self.state_file, CAMPAIGN_HEADERS, new_list)
        logger.info(f"Campaign {campaign_id} status updated to: {status}")

    def load_batches(self, campaign_id: str) -> List[Dict[str, str]]:
        if not self.batches_file.exists():
            return []
        with open(self.batches_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return [b for b in reader if b.get("campaign_id") == campaign_id]

    def record_batch_plan(
        self,
        campaign_id: str,
        batch_index: int,
        sender_account: str,
        template_id: int,
        subject: str,
        recipient_count: int,
    ) -> None:
        """Record planned batch if not already recorded."""
        all_batches: List[Dict[str, str]] = []
        if self.batches_file.exists():
            with open(self.batches_file, "r", encoding="utf-8") as f:
                all_batches = list(csv.DictReader(f))

        # Check if already exists
        exists = any(
            b.get("campaign_id") == campaign_id and b.get("batch_index") == str(batch_index)
            for b in all_batches
        )
        if not exists:
            all_batches.append({
                "campaign_id": campaign_id,
                "batch_index": str(batch_index),
                "sender_account": sender_account,
                "template_id": str(template_id),
                "subject": subject,
                "recipient_count": str(recipient_count),
                "status": "PENDING",
                "error": "",
                "sent_at": "",
            })
            atomic_write_csv(self.batches_file, BATCH_HEADERS, all_batches)

    def update_batch_status(
        self,
        campaign_id: str,
        batch_index: int,
        status: str,
        error: str = "",
        timestamp: Optional[str] = None,
    ) -> None:
        """Update individual batch status immediately after transmission attempt."""
        if not timestamp:
            timestamp = get_today_ist_date()

        all_batches: List[Dict[str, str]] = []
        if self.batches_file.exists():
            with open(self.batches_file, "r", encoding="utf-8") as f:
                all_batches = list(csv.DictReader(f))

        updated = False
        for b in all_batches:
            if b.get("campaign_id") == campaign_id and b.get("batch_index") == str(batch_index):
                b["status"] = status
                b["error"] = error
                if status == "SENT":
                    b["sent_at"] = timestamp
                updated = True
                break

        if updated:
            atomic_write_csv(self.batches_file, BATCH_HEADERS, all_batches)
            logger.info(f"Campaign {campaign_id} batch {batch_index} status -> {status}")
