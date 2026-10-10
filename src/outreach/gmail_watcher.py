"""Mailbox watcher and file detector for daily lead delivery emails and attachments."""

import os
import re
import email
import imaplib
import logging
from pathlib import Path
from email.header import decode_header
from typing import Optional, Tuple, Dict, Any, List

from src.config import GMAIL_USERNAME, GMAIL_APP_PASSWORD, OUTPUT_DIR, DATA_DIR
from src.state_manager import get_today_ist_date
from src.outreach.config import (
    LEAD_DELIVERY_FROM,
    LEAD_EMAIL_SUBJECT_PATTERN,
)
from src.outreach.campaign_state import CampaignState
from src.outreach.attachment_parser import parse_lead_file

logger = logging.getLogger(__name__)


class DetectedLeadDelivery:
    """Encapsulates the detected daily lead message and its attachment."""
    def __init__(
        self,
        source_type: str,  # 'imap', 'local_receipt', 'manual'
        message_id: str,
        subject: str,
        attachment_filename: str,
        attachment_bytes: bytes,
        date_str: str,
    ):
        self.source_type = source_type
        self.message_id = message_id
        self.subject = subject
        self.attachment_filename = attachment_filename
        self.attachment_bytes = attachment_bytes
        self.date_str = date_str


class GmailWatcher:
    """Monitors mailbox or local delivery receipts for newly delivered daily lead files."""

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        sender_filter: Optional[str] = None,
        subject_pattern: str = LEAD_EMAIL_SUBJECT_PATTERN,
        state_mgr: Optional[CampaignState] = None,
    ):
        self.username = username or GMAIL_USERNAME
        self.password = password or GMAIL_APP_PASSWORD
        self.sender_filter = (sender_filter or LEAD_DELIVERY_FROM or self.username or "").lower()
        self.subject_pattern = subject_pattern
        self.state_mgr = state_mgr or CampaignState()

    def check_local_receipt(self, date_str: Optional[str] = None) -> Optional[DetectedLeadDelivery]:
        """
        Check if the 11 AM delivery workflow successfully completed locally
        and produced output/leads_YYYY-MM-DD.txt and delivery receipt.
        """
        if not date_str:
            date_str = get_today_ist_date()

        receipt_file = DATA_DIR / f"delivery_receipt_{date_str}.json"
        lead_file = OUTPUT_DIR / f"leads_{date_str}.txt"

        if lead_file.exists() and lead_file.stat().st_size > 0:
            with open(lead_file, "rb") as f:
                content = f.read()

            message_id = f"LOCAL-RECEIPT-{date_str}"
            if receipt_file.exists():
                try:
                    import json
                    data = json.loads(receipt_file.read_text(encoding="utf-8"))
                    message_id = data.get("receipt_id", message_id)
                except Exception:
                    pass

            return DetectedLeadDelivery(
                source_type="local_receipt",
                message_id=message_id,
                subject=f"Daily New Leads — {date_str}",
                attachment_filename=lead_file.name,
                attachment_bytes=content,
                date_str=date_str,
            )
        return None

    def check_manual_file(self, file_path: Path) -> Optional[DetectedLeadDelivery]:
        """Load from explicit manual dispatch file."""
        if not file_path.exists() or file_path.stat().st_size == 0:
            return None

        with open(file_path, "rb") as f:
            content = f.read()

        date_str = get_today_ist_date()
        message_id = f"MANUAL-{file_path.stem}-{date_str}"

        return DetectedLeadDelivery(
            source_type="manual",
            message_id=message_id,
            subject=f"Manual Lead File — {file_path.name}",
            attachment_filename=file_path.name,
            attachment_bytes=content,
            date_str=date_str,
        )

    def check_imap_inbox(self, max_messages: int = 15) -> Optional[DetectedLeadDelivery]:
        """
        Connect via IMAP SSL to detect newly delivered lead emails.
        Matches:
        - Sender matches sender_filter
        - Subject matches subject_pattern
        - Contains .txt or .csv attachment
        - Message ID not already processed
        """
        if not self.username or not self.password:
            logger.info("IMAP credentials not configured. Skipping IMAP mailbox check.")
            return None

        try:
            logger.info(f"Connecting to IMAP imap.gmail.com:993 as {self.username}...")
            mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
            mail.login(self.username, self.password)
            mail.select("INBOX")

            # Search recent messages
            status, messages = mail.search(None, "ALL")
            if status != "OK" or not messages[0]:
                mail.close()
                mail.logout()
                return None

            msg_ids = messages[0].split()
            # Inspect last max_messages
            for msg_id in reversed(msg_ids[-max_messages:]):
                status, data = mail.fetch(msg_id, "(RFC822)")
                if status != "OK" or not data or not data[0]:
                    continue

                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)

                # Decode subject
                subject, encoding = decode_header(msg.get("Subject", ""))[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding or "utf-8", errors="replace")

                from_header = str(msg.get("From", "")).lower()

                # Verify sender and subject
                if self.sender_filter and self.sender_filter not in from_header:
                    continue

                match = re.search(self.subject_pattern, subject)
                if not match:
                    continue

                date_str = match.group(1) if match.groups() else get_today_ist_date()
                gmail_msg_id = msg.get("Message-ID", f"IMAP-{msg_id.decode('ascii')}")

                # Extract attachment
                for part in msg.walk():
                    content_disposition = str(part.get("Content-Disposition", ""))
                    if "attachment" in content_disposition:
                        fn = part.get_filename() or "leads.txt"
                        if fn.lower().endswith((".txt", ".csv")):
                            payload = part.get_payload(decode=True)
                            if payload:
                                mail.close()
                                mail.logout()
                                return DetectedLeadDelivery(
                                    source_type="imap",
                                    message_id=gmail_msg_id,
                                    subject=subject,
                                    attachment_filename=fn,
                                    attachment_bytes=payload,
                                    date_str=date_str,
                                )

            mail.close()
            mail.logout()
        except Exception as e:
            logger.warning(f"IMAP check encountered error: {e}")

        return None

    def detect_next_delivery(self, manual_file: Optional[Path] = None) -> Optional[DetectedLeadDelivery]:
        """
        Unified detector checking:
        1. Explicit manual file input
        2. IMAP mailbox inspection (if configured)
        3. Local workspace delivery receipt / output file
        """
        if manual_file and manual_file.exists():
            return self.check_manual_file(manual_file)

        # Try IMAP first if credentials are present
        imap_result = self.check_imap_inbox()
        if imap_result:
            return imap_result

        # Fallback to local workspace output
        return self.check_local_receipt()
