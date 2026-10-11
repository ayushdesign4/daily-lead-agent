"""Secure multi-account SMTP outreach sender with BCC-only and strict idempotency."""

import json
import time
import socket
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any, Optional, Tuple

from src.outreach.config import (
    OUTREACH_ACCOUNTS_JSON,
    OUTREACH_TO_EMAIL,
)

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


class OutreachAccount:
    """Represents a validated sender account. Never prints or echoes app_password."""
    def __init__(self, email: str, app_password: str):
        self.email = email.strip()
        self.app_password = app_password.replace(" ", "").strip()

    def __repr__(self) -> str:
        return f"<OutreachAccount email='{self.email}'>"


def load_and_validate_accounts(raw_json: Optional[str] = None) -> List[OutreachAccount]:
    """
    Parse and strictly validate the 9 sender accounts from OUTREACH_ACCOUNTS_JSON.
    Fails closed if:
    - JSON is missing or invalid
    - Count is not exactly 9
    - Any email is missing or duplicated
    - Any app_password is empty
    NEVER echoes credentials in error messages or logs.
    """
    json_str = raw_json or OUTREACH_ACCOUNTS_JSON
    if not json_str:
        raise ValueError("OUTREACH_ACCOUNTS_JSON secret is not set or empty. Validation failed closed.")

    try:
        data = json.loads(json_str)
    except Exception as e:
        raise ValueError(f"Failed to parse OUTREACH_ACCOUNTS_JSON as valid JSON: {type(e).__name__}") from None

    if not isinstance(data, list):
        raise ValueError("OUTREACH_ACCOUNTS_JSON must be a JSON array of account objects.")

    if len(data) != 9:
        raise ValueError(f"OUTREACH_ACCOUNTS_JSON must contain exactly 9 accounts. Found: {len(data)}")

    accounts: List[OutreachAccount] = []
    seen_emails = set()

    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Account record at index {idx} is not a JSON object.")

        email = item.get("email")
        app_password = item.get("app_password")

        if not email or not isinstance(email, str) or "@" not in email:
            raise ValueError(f"Account record at index {idx} has an invalid or missing email.")

        if not app_password or not isinstance(app_password, str) or not app_password.strip():
            raise ValueError(f"Account record at index {idx} has an empty or invalid password.")

        norm_email = email.strip().lower()
        if norm_email in seen_emails:
            raise ValueError(f"Duplicate email found in OUTREACH_ACCOUNTS_JSON: {norm_email}")

        seen_emails.add(norm_email)
        accounts.append(OutreachAccount(email=norm_email, app_password=app_password))

    logger.info(f"Successfully loaded and validated {len(accounts)} outreach sender accounts.")
    return accounts


class OutreachSender:
    """Handles sending email batches via individual sender SMTP connections."""

    def __init__(
        self,
        accounts: Optional[List[OutreachAccount]] = None,
        to_email: str = OUTREACH_TO_EMAIL,
        dry_run: bool = False,
    ):
        self.accounts = accounts or []
        self.to_email = to_email
        self.dry_run = dry_run

    def build_message(
        self,
        sender_email: str,
        subject: str,
        body_text: str,
    ) -> MIMEMultipart:
        """
        Construct MIME message with:
        - From: sender_email
        - To: self.to_email (ayush@ayushdesign.site)
        - Subject: subject
        - Body: body_text
        NOTE: BCC recipients are passed directly to sendmail/send_message envelope,
        NEVER placed in headers!
        """
        msg = MIMEMultipart("alternative")
        msg["From"] = sender_email
        msg["To"] = self.to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        return msg

    def send_batch(
        self,
        account: OutreachAccount,
        subject: str,
        body_text: str,
        bcc_recipients: List[str],
        max_retries: int = 3,
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Transmit outreach email to assigned batch recipients via BCC with stage-aware retry.
        Returns (success: bool, status: str, error_message: Optional[str]).
        Status values: 'SENT', 'FAILED_REQUIRES_REVIEW', 'SKIPPED_EMPTY'
        """
        if not bcc_recipients:
            logger.info(f"Batch for {account.email} has 0 recipients. Skipping transmission.")
            return True, "SKIPPED_EMPTY", None

        msg = self.build_message(
            sender_email=account.email,
            subject=subject,
            body_text=body_text,
        )

        # Full delivery envelope: To address + all BCC recipients
        envelope_recipients = [self.to_email] + bcc_recipients

        if self.dry_run:
            logger.info(
                f"[DRY RUN] Simulating SMTP send from {account.email} | "
                f"Subject: '{subject}' | To: {self.to_email} | BCC count: {len(bcc_recipients)}"
            )
            return True, "SENT", None

        for attempt in range(max_retries):
            stage = "CONNECTING"
            server = None
            try:
                logger.info(
                    f"Connecting to SMTP {SMTP_HOST}:{SMTP_PORT} as {account.email} "
                    f"(attempt {attempt + 1}/{max_retries})..."
                )
                server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30)

                stage = "AUTHENTICATING"
                server.login(account.email, account.app_password)

                stage = "TRANSMITTING"
                # Use sendmail to specify envelope recipients explicitly without exposing BCC in headers
                server.sendmail(account.email, envelope_recipients, msg.as_string())
                server.quit()

                logger.info(
                    f"Successfully sent batch from {account.email} to {len(bcc_recipients)} BCC recipients."
                )
                return True, "SENT", None

            except smtplib.SMTPAuthenticationError as e:
                logger.error(f"Authentication failed for sender account {account.email}: {type(e).__name__}")
                if server:
                    try:
                        server.close()
                    except Exception:
                        pass
                return False, "FAILED_REQUIRES_REVIEW", f"SMTPAuthenticationError: {type(e).__name__}"

            except (smtplib.SMTPServerDisconnected, ConnectionResetError, TimeoutError, socket.error, OSError) as e:
                if server:
                    try:
                        server.close()
                    except Exception:
                        pass

                if stage in ("CONNECTING", "AUTHENTICATING"):
                    logger.warning(
                        f"Transient connection drop at stage '{stage}' for {account.email} "
                        f"(attempt {attempt + 1}/{max_retries}): {type(e).__name__}: {e}"
                    )
                    if attempt < max_retries - 1:
                        backoff = 2 * (attempt + 1)
                        logger.info(f"Retrying connection for {account.email} in {backoff} seconds...")
                        time.sleep(backoff)
                        continue
                    else:
                        logger.error(f"Max connection retries exceeded for {account.email} at stage '{stage}'.")
                        return False, "FAILED_REQUIRES_REVIEW", f"PreTransmissionDisconnect: {type(e).__name__}"
                else:
                    # Disconnect occurred during TRANSMITTING - delivery status is uncertain
                    logger.error(
                        f"Disconnect occurred during message transmission for {account.email}. "
                        f"Delivery state is uncertain; preserving FAILED_REQUIRES_REVIEW to avoid duplicate send."
                    )
                    return False, "FAILED_REQUIRES_REVIEW", f"UncertainDelivery: {type(e).__name__}"

            except smtplib.SMTPException as e:
                if server:
                    try:
                        server.close()
                    except Exception:
                        pass
                logger.error(f"SMTP error at stage '{stage}' for {account.email}: {type(e).__name__}: {e}")
                err_prefix = "UncertainDelivery" if stage == "TRANSMITTING" else "SMTPException"
                return False, "FAILED_REQUIRES_REVIEW", f"{err_prefix}: {type(e).__name__}"

            except Exception as e:
                if server:
                    try:
                        server.close()
                    except Exception:
                        pass
                logger.error(f"Unexpected error at stage '{stage}' for {account.email}: {type(e).__name__}: {e}")
                err_prefix = "UncertainDelivery" if stage == "TRANSMITTING" else "UnexpectedException"
                return False, "FAILED_REQUIRES_REVIEW", f"{err_prefix}: {type(e).__name__}"

        return False, "FAILED_REQUIRES_REVIEW", "MaxRetriesExceeded"
