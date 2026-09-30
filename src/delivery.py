"""Email delivery and notification system via Gmail SMTP."""

import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import List, Optional

from src.config import (
    GMAIL_USERNAME,
    GMAIL_APP_PASSWORD,
    DELIVERY_EMAIL,
    SMTP_HOST,
    SMTP_PORT,
    OUTPUT_DIR,
    GOOGLE_FORM_URL,
    DRY_RUN,
)

logger = logging.getLogger(__name__)


class DeliveryManager:
    """Handles TXT lead file generation, Gmail delivery, and alert emails."""

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        recipient: Optional[str] = None,
        dry_run: Optional[bool] = None,
    ):
        self.username = username or GMAIL_USERNAME
        self.password = password or GMAIL_APP_PASSWORD
        self.recipient = recipient or DELIVERY_EMAIL or self.username
        self.dry_run = dry_run if dry_run is not None else DRY_RUN

    def generate_lead_file(self, emails: List[str], date_str: str) -> Path:
        """
        Generate `output/leads_YYYY-MM-DD.txt` containing ONLY
        selected email addresses, one per line.
        """
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        file_path = OUTPUT_DIR / f"leads_{date_str}.txt"

        with open(file_path, "w", encoding="utf-8") as f:
            for email in emails:
                f.write(f"{email.strip()}\n")

        logger.info(f"Generated lead file: {file_path} with {len(emails)} leads")
        return file_path

    def _send_smtp_email(self, msg: MIMEMultipart) -> bool:
        """Helper to send an email message via Gmail SMTP with SSL/TLS."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Skipping actual SMTP transmission for: {msg['Subject']}")
            return True

        if not self.username or not self.password:
            logger.warning("Gmail credentials (GMAIL_USERNAME / GMAIL_APP_PASSWORD) not configured. Cannot send email.")
            return False

        try:
            logger.info(f"Connecting to SMTP server {SMTP_HOST}:{SMTP_PORT}...")
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as server:
                server.login(self.username, self.password)
                server.send_message(msg)
            logger.info(f"Email successfully delivered to {self.recipient}: {msg['Subject']}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email via SMTP: {e}")
            raise

    def send_daily_leads(
        self,
        file_path: Path,
        lead_count: int,
        queue_remaining: int,
        date_str: str,
        target: int = 200,
        shortfall_reason: Optional[str] = None,
    ) -> bool:
        """
        Send daily TXT file as attachment via Gmail.
        """
        subject = f"Daily New Leads — {date_str}"

        # Body formatting according to specification Section 12
        body_lines = [
            "Today's lead file is attached.\n",
            f"New leads delivered: {lead_count}",
            f"Queue remaining: {queue_remaining}",
        ]

        if shortfall_reason:
            body_lines.append(f"\nNote: Target of {target} was not reached because: {shortfall_reason}")
            body_lines.append(f"Delivered {lead_count} genuine leads obtained today.")

        body_text = "\n".join(body_lines)

        msg = MIMEMultipart()
        msg["From"] = self.username or "Lead Agent"
        msg["To"] = self.recipient or ""
        msg["Subject"] = subject
        msg.attach(MIMEText(body_text, "plain", "utf-8"))

        if file_path.exists():
            with open(file_path, "rb") as f:
                attachment = MIMEBase("application", "octet-stream")
                attachment.set_payload(f.read())
            encoders.encode_base64(attachment)
            attachment.add_header(
                "Content-Disposition",
                f"attachment; filename={file_path.name}",
            )
            msg.attach(attachment)

        return self._send_smtp_email(msg)

    def send_credit_exhaustion_alert(
        self,
        date_str: str,
        error_details: str,
        leads_obtained_today: int,
        today_target: int,
        shortfall: int,
        daily_file_sent: bool,
    ) -> bool:
        """
        Send alert email when Apify credits or API access are exhausted.
        Includes Google Form link for token replacement.
        """
        subject = "⚠️ Apify Credits/API Unavailable — Lead Agent"

        body = f"""Hello,

This is an automated alert from your Daily Lead Agent.

Apify credits or API access are currently unavailable. No further Apify calls will be attempted today.

--- RUN SUMMARY ---
• Date: {date_str}
• Reason: {error_details}
• Genuinely new leads obtained today: {leads_obtained_today}
• Daily target: {today_target}
• Shortfall: {shortfall}
• Daily leads file delivered: {"YES" if daily_file_sent else "NO (insufficient leads)"}

--- ACTION REQUIRED: UPDATE API TOKEN ---
To resume automated scraping without losing your database or queue:
1. Open this link from your phone or computer:
   {GOOGLE_FORM_URL}
2. Paste your new Apify API token and submit the form.

The next scheduled run will automatically use the new token while preserving all lifetime database records, pending leads, and niche history.

Best regards,
Daily Lead Agent
"""

        msg = MIMEMultipart()
        msg["From"] = self.username or "Lead Agent"
        msg["To"] = self.recipient or ""
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        logger.info(f"Sending credit exhaustion alert email to {self.recipient}")
        return self._send_smtp_email(msg)
