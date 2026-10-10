"""Main orchestrator for the Verified Outreach Pipeline."""

import os
import sys
import logging
import argparse
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from typing import Optional, Dict, Any, List

from src.state_manager import get_today_ist_date
from src.config import SMTP_HOST, SMTP_PORT, GMAIL_USERNAME, GMAIL_APP_PASSWORD, DRY_RUN
from src.outreach.config import (
    OUTREACH_TO_EMAIL,
    NOTIFICATION_RECIPIENT,
    QEV_API_KEY_1,
    QEV_API_KEY_2,
    OUTREACH_ACCOUNTS_JSON,
)
from src.outreach.attachment_parser import parse_lead_file
from src.outreach.address_normalizer import filter_and_deduplicate_addresses
from src.outreach.quota_ledger import QuotaLedger
from src.outreach.verification_client import QuickEmailVerifier, VerificationResult
from src.outreach.suppression import SuppressionManager
from src.outreach.distributor import distribute_recipients
from src.outreach.template_manager import TemplateManager
from src.outreach.sender import (
    load_and_validate_accounts,
    OutreachSender,
    OutreachAccount,
)
from src.outreach.campaign_state import CampaignState
from src.outreach.gmail_watcher import GmailWatcher, DetectedLeadDelivery

logger = logging.getLogger("OutreachOrchestrator")


class OutreachPipeline:
    """End-to-end controller for the verified outreach pipeline."""

    def __init__(
        self,
        dry_run: bool = False,
        state_mgr: Optional[CampaignState] = None,
        quota_ledger: Optional[QuotaLedger] = None,
        suppression_mgr: Optional[SuppressionManager] = None,
        key_1: Optional[str] = None,
        key_2: Optional[str] = None,
        raw_accounts_json: Optional[str] = None,
    ):
        self.dry_run = dry_run or DRY_RUN
        self.state_mgr = state_mgr or CampaignState()
        self.quota_ledger = quota_ledger or QuotaLedger()
        self.suppression_mgr = suppression_mgr or SuppressionManager()
        self.verifier = QuickEmailVerifier(
            key_1=key_1 or QEV_API_KEY_1,
            key_2=key_2 or QEV_API_KEY_2,
            ledger=self.quota_ledger,
            dry_run=self.dry_run,
        )
        self.raw_accounts_json = raw_accounts_json or OUTREACH_ACCOUNTS_JSON

    def send_completion_notification(
        self,
        summary: Dict[str, Any],
        date_str: str,
    ) -> bool:
        """
        Send concise completion / failure notification to the owner inbox
        (DELIVERY_EMAIL) detailing counts, per-batch delivery status, and status.
        Never reveals passwords.
        """
        recipient = NOTIFICATION_RECIPIENT
        if not recipient:
            logger.warning("No notification recipient configured. Skipping completion email.")
            return False

        campaign_id = summary.get("campaign_id", "UNKNOWN")
        overall_status = summary.get("overall_status", "UNKNOWN")
        batches = summary.get("batches", [])

        # Subject
        subject = f"Outreach Pipeline Report — {date_str} [{overall_status}]"

        lines = [
            f"Daily Outreach Pipeline Report — {date_str}",
            "=" * 50,
            f"Campaign ID: {campaign_id}",
            f"Overall Status: {overall_status}",
            f"Source Attachment: {summary.get('attachment_filename')} (hash: {summary.get('attachment_hash', '')[:12]}...)",
            "",
            "1. INGESTION & NORMALIZATION:",
            f"   - Raw leads in file: {summary.get('leads_parsed', 0)}",
            f"   - Malformed/blank rejected: {summary.get('malformed_count', 0)}",
            f"   - Intra-file duplicates removed: {summary.get('duplicate_count', 0)}",
            f"   - Unique addresses eligible for verification: {summary.get('unique_count', 0)}",
            "",
            "2. VERIFICATION (QEV DUAL ACCOUNTS):",
            f"   - Account A verified: {summary.get('verified_a_count', 0)}",
            f"   - Account B verified: {summary.get('verified_b_count', 0)}",
            f"   - Explicitly VALID (deliverable): {summary.get('valid_count', 0)}",
            f"   - INVALID: {summary.get('invalid_count', 0)}",
            f"   - RISKY (disposable/catch-all): {summary.get('risky_count', 0)}",
            f"   - UNKNOWN: {summary.get('unknown_count', 0)}",
            f"   - VERIFICATION ERRORS: {summary.get('error_count', 0)}",
            f"   - Deferred due to 200 daily quota cap: {summary.get('deferred_count', 0)}",
            "",
            "3. SUPPRESSION & DISTRIBUTION:",
            f"   - Suppressed/unsubscribed filtered: {summary.get('suppressed_count', 0)}",
            f"   - Net eligible recipients for outreach: {summary.get('net_eligible_count', 0)}",
            f"   - Total sender accounts: {len(batches)} (planned: 9)",
            "",
            "4. PER-BATCH SEND STATUS (To: ayush@ayushdesign.site, BCC only):",
        ]

        all_sent = True
        for b in batches:
            idx = b.get("batch_index")
            sender = b.get("sender_account")
            recip_count = b.get("count", 0)
            st = b.get("status", "PENDING")
            subj = b.get("subject", "")
            err = b.get("error", "")
            lines.append(f"   - Batch #{idx} [{sender}]: {recip_count} recipients -> {st} (Subject: '{subj}'){f' Error: {err}' if err else ''}")
            if st not in ("SENT", "SKIPPED_EMPTY"):
                all_sent = False

        lines.append("")
        if overall_status == "COMPLETED" and all_sent:
            lines.append("STATEMENT: Daily outreach target completed successfully.")
        elif overall_status == "PARTIALLY_SENT":
            lines.append("STATEMENT: Daily outreach partially completed; some batches require review.")
        else:
            lines.append(f"STATEMENT: Daily outreach ended with status: {overall_status}.")

        body = "\n".join(lines)

        if self.dry_run:
            logger.info(f"[DRY RUN] Skipping notification email dispatch. Summary:\n{body}")
            return True

        if not GMAIL_USERNAME or not GMAIL_APP_PASSWORD:
            logger.warning("GMAIL credentials missing. Cannot dispatch notification email.")
            return False

        try:
            msg = MIMEMultipart()
            msg["From"] = GMAIL_USERNAME
            msg["To"] = recipient
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain", "utf-8"))

            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as server:
                server.login(GMAIL_USERNAME, GMAIL_APP_PASSWORD)
                server.send_message(msg)
            logger.info(f"Completion notification successfully sent to {recipient}")
            return True
        except Exception as e:
            logger.error(f"Failed to send completion notification: {e}")
            return False

    def run(
        self,
        manual_file: Optional[Path] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute full verified outreach pipeline.
        Returns execution summary dict.
        """
        date_str = get_today_ist_date()
        logger.info("=" * 60)
        logger.info(f"Starting Verified Outreach Pipeline | Date: {date_str} IST | Dry Run: {self.dry_run}")

        # Step 1: Detect newly delivered daily lead file
        watcher = GmailWatcher(state_mgr=self.state_mgr)
        delivery: Optional[DetectedLeadDelivery] = watcher.detect_next_delivery(manual_file=manual_file)

        if not delivery:
            logger.info("No new lead delivery email or file detected today. Exiting safely.")
            return {"status": "NO_DELIVERY_DETECTED", "date": date_str}

        logger.info(f"Detected delivery: {delivery.subject} from {delivery.source_type} (file: {delivery.attachment_filename})")

        # Step 2: Parse attachment & compute content hash
        raw_emails, content_hash, filename = parse_lead_file(
            content_or_path=delivery.attachment_bytes,
            filename=delivery.attachment_filename
        )
        campaign_id = f"CAMP-{content_hash[:10]}-{date_str}"

        # Step 3: Check idempotency
        if not force and self.state_mgr.is_campaign_completed(campaign_id):
            logger.info(f"Campaign {campaign_id} has already COMPLETED. Exiting to prevent duplicate sending.")
            return {"status": "ALREADY_COMPLETED", "campaign_id": campaign_id}

        self.state_mgr.save_campaign_state(
            campaign_id=campaign_id,
            status="ATTACHMENT_PARSED",
            source_message_id=delivery.message_id,
            attachment_hash=content_hash,
            counts={"parsed": len(raw_emails)},
            date_str=date_str,
        )

        # Step 4: Normalize, syntax check, and deduplicate
        unique_emails, malformed_count, duplicate_count = filter_and_deduplicate_addresses(raw_emails)
        logger.info(
            f"Normalization: {len(raw_emails)} raw -> {malformed_count} malformed -> "
            f"{duplicate_count} duplicate -> {len(unique_emails)} unique valid addresses"
        )

        # Step 5: Partition for QEV dual-account verification (max 100 each)
        batch_a, batch_b, deferred_count = self.verifier.plan_and_partition(unique_emails, date_str)
        self.state_mgr.save_campaign_state(
            campaign_id=campaign_id,
            status="VERIFICATION_IN_PROGRESS",
            counts={"parsed": len(raw_emails), "unique": len(unique_emails), "deferred": deferred_count},
            date_str=date_str,
        )

        # Step 6: Verify batches
        v_results: List[VerificationResult] = self.verifier.verify_batches(batch_a, batch_b, date_str)

        valid_emails = [r.email for r in v_results if r.is_deliverable]
        invalid_count = sum(1 for r in v_results if r.status == "invalid")
        risky_count = sum(1 for r in v_results if r.status == "risky")
        unknown_count = sum(1 for r in v_results if r.status == "unknown")
        error_count = sum(1 for r in v_results if r.status == "verification_error")

        logger.info(
            f"Verification Results: {len(v_results)} checked -> {len(valid_emails)} valid, "
            f"{invalid_count} invalid, {risky_count} risky, {unknown_count} unknown, {error_count} errors"
        )

        self.state_mgr.save_campaign_state(
            campaign_id=campaign_id,
            status="VERIFICATION_COMPLETE",
            counts={
                "parsed": len(raw_emails),
                "unique": len(unique_emails),
                "valid": len(valid_emails),
                "invalid": invalid_count,
                "risky": risky_count,
                "unknown": unknown_count,
                "deferred": deferred_count,
            },
            date_str=date_str,
        )

        # Step 7: Global deduplication and suppression check
        eligible_for_outreach, suppressed_count = self.suppression_mgr.filter_eligible(valid_emails)
        logger.info(f"Suppression filter: {len(valid_emails)} valid -> {suppressed_count} suppressed -> {len(eligible_for_outreach)} eligible")

        # Step 8: Load and validate 9 sender accounts
        # In dry run mode without accounts JSON, generate 9 mock accounts
        if self.dry_run and not self.raw_accounts_json:
            logger.info("[DRY RUN] Generating 9 simulated sender accounts for dry run testing.")
            accounts = [
                OutreachAccount(email=f"sender{i+1}@example.com", app_password="mock_app_password")
                for i in range(9)
            ]
        else:
            accounts = load_and_validate_accounts(self.raw_accounts_json)

        sender_emails = [a.email for a in accounts]

        # Step 9: Distribute recipients evenly across 9 accounts
        batches = distribute_recipients(eligible_for_outreach, sender_emails)

        # Record planned batches in state machine
        for b in batches:
            idx = b["batch_index"]
            tmpl_id, _ = TemplateManager.get_template_for_batch(idx)
            subj = TemplateManager.get_subject_for_batch(idx)
            self.state_mgr.record_batch_plan(
                campaign_id=campaign_id,
                batch_index=idx,
                sender_account=b["sender_account"],
                template_id=tmpl_id,
                subject=subj,
                recipient_count=b["count"],
            )

        self.state_mgr.save_campaign_state(
            campaign_id=campaign_id,
            status="BATCHES_PLANNED",
            batches_planned=len(batches),
            date_str=date_str,
        )

        # Step 10: Transmit batches via OutreachSender
        sender_service = OutreachSender(
            accounts=accounts,
            to_email=OUTREACH_TO_EMAIL,
            dry_run=self.dry_run,
        )

        existing_batches = {
            int(b.get("batch_index", -1)): b.get("status")
            for b in self.state_mgr.load_batches(campaign_id)
        }

        sent_count = 0
        has_failure = False

        for b in batches:
            idx = b["batch_index"]
            account_obj = next(a for a in accounts if a.email == b["sender_account"])
            tmpl_id, body_text = TemplateManager.get_template_for_batch(idx)
            subject = TemplateManager.get_subject_for_batch(idx)
            recipients = b["recipients"]

            # Idempotency check: skip already SENT batches
            prev_status = existing_batches.get(idx)
            if prev_status == "SENT":
                logger.info(f"Batch #{idx} ({account_obj.email}) already SENT. Skipping.")
                b["status"] = "SENT"
                sent_count += 1
                continue

            success, batch_status, error_msg = sender_service.send_batch(
                account=account_obj,
                subject=subject,
                body_text=body_text,
                bcc_recipients=recipients,
            )

            b["status"] = batch_status
            b["subject"] = subject
            b["error"] = error_msg or ""

            # Persist batch status immediately
            self.state_mgr.update_batch_status(
                campaign_id=campaign_id,
                batch_index=idx,
                status=batch_status,
                error=error_msg or "",
            )

            if success and batch_status in ("SENT", "SKIPPED_EMPTY"):
                sent_count += 1
            else:
                has_failure = True

        overall_status = "COMPLETED" if (sent_count == len(batches) and not has_failure) else (
            "PARTIALLY_SENT" if sent_count > 0 else "FAILED_REQUIRES_REVIEW"
        )

        self.state_mgr.save_campaign_state(
            campaign_id=campaign_id,
            status=overall_status,
            batches_planned=len(batches),
            batches_sent=sent_count,
            date_str=date_str,
        )

        summary = {
            "campaign_id": campaign_id,
            "overall_status": overall_status,
            "attachment_filename": filename,
            "attachment_hash": content_hash,
            "leads_parsed": len(raw_emails),
            "malformed_count": malformed_count,
            "duplicate_count": duplicate_count,
            "unique_count": len(unique_emails),
            "verified_a_count": len(batch_a),
            "verified_b_count": len(batch_b),
            "valid_count": len(valid_emails),
            "invalid_count": invalid_count,
            "risky_count": risky_count,
            "unknown_count": unknown_count,
            "error_count": error_count,
            "deferred_count": deferred_count,
            "suppressed_count": suppressed_count,
            "net_eligible_count": len(eligible_for_outreach),
            "batches": batches,
            "date": date_str,
        }

        # Step 11: Send completion notification
        self.send_completion_notification(summary, date_str)

        logger.info(f"Pipeline finished for {campaign_id} with status: {overall_status}")
        logger.info("=" * 60)
        return summary


def main():
    parser = argparse.ArgumentParser(description="Verified Outreach Pipeline CLI")
    parser.add_argument("--dry-run", action="store_true", help="Run without sending real emails or consuming QEV credits")
    parser.add_argument("--file", type=str, default=None, help="Path to manual lead file (.txt or .csv)")
    parser.add_argument("--force", action="store_true", help="Force execution even if already completed today")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    manual_path = Path(args.file) if args.file else None
    pipeline = OutreachPipeline(dry_run=args.dry_run)
    res = pipeline.run(manual_file=manual_path, force=args.force)

    status = res.get("status") or res.get("overall_status")
    if status in ("COMPLETED", "NO_DELIVERY_DETECTED", "ALREADY_COMPLETED"):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
