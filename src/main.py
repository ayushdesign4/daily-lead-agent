"""Daily Lead Agent Orchestrator.

Implements demand-driven scraping, queue safety, transactional delivery,
credit exhaustion handling, and multi-stage overnight/11 AM workflows.
"""

import sys
import uuid
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from src.config import (
    DAILY_TARGET,
    MAX_QUERIES_PER_BATCH,
    LOGS_DIR,
    DRY_RUN,
    TEST_MODE,
)
from src.state_manager import StateManager, get_today_ist_date
from src.niche_manager import NicheManager
from src.email_extractor import extract_emails_from_dataset
from src.deduplicator import Deduplicator
from src.apify_client import (
    ApifyClient,
    ApifyCreditExhaustedError,
    ApifyAuthError,
    ApifyTimeoutError,
    ApifyError,
)
from src.queue_manager import QueueManager
from src.delivery import DeliveryManager


def setup_logging(date_str: str) -> logging.Logger:
    """Setup secure logger writing to both daily log file and console."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"{date_str}.log"

    logger = logging.getLogger("DailyLeadAgent")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


class DailyLeadAgent:
    """End-to-end controller for lead extraction and delivery."""

    def __init__(
        self,
        target: int = DAILY_TARGET,
        dry_run: bool = DRY_RUN,
        test_mode: bool = TEST_MODE,
        state_manager: Optional[StateManager] = None,
        apify_client: Optional[ApifyClient] = None,
        delivery_manager: Optional[DeliveryManager] = None,
    ):
        self.target = target
        self.dry_run = dry_run or test_mode
        self.test_mode = test_mode
        self.state_manager = state_manager or StateManager()
        self.queue_manager = QueueManager(self.state_manager)
        self.niche_manager = NicheManager(self.state_manager)
        self.apify_client = apify_client or ApifyClient()
        self.delivery_manager = delivery_manager or DeliveryManager(dry_run=self.dry_run)
        self.run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"

    def _process_and_fill_queue(self, date_str: str, logger: logging.Logger) -> Tuple[bool, str, int]:
        """
        Run demand-driven Apify batches until the pending queue contains at least `self.target` leads,
        or until niches/credits are exhausted.
        Returns:
            (credit_exhausted, exhaustion_reason, batches_run)
        """
        current_queue_size = self.queue_manager.get_queue_size()
        shortage = max(0, self.target - current_queue_size)

        if shortage == 0:
            logger.info(f"Pending queue already has {current_queue_size} leads (>= target {self.target}). 0 Apify batches needed.")
            return False, "", 0

        master_leads = self.state_manager.load_master_leads()
        deduplicator = Deduplicator(master_leads)

        batches_run = 0
        credit_exhausted = False
        exhaustion_reason = ""

        # Demand-driven loop: continues while shortage > 0, fresh niches exist, and API access is healthy
        while shortage > 0:
            batches_run += 1
            logger.info(f"--- Starting Apify Batch {batches_run} (Shortage: {shortage}) ---")

            # Select fresh niches
            batch_niches = self.niche_manager.select_batch_niches(MAX_QUERIES_PER_BATCH)
            if not batch_niches:
                logger.warning("No unused niches available in pool. Stopping search.")
                break

            niche_names = [n[0] for n in batch_niches]
            queries = [n[1] for n in batch_niches]
            logger.info(f"Batch {batches_run} queries ({len(queries)}): {niche_names}")

            try:
                if self.dry_run:
                    if self.test_mode:
                        logger.info(f"[TEST MODE] Generating simulated search results for batch {batches_run}...")
                        dataset_items = [
                            {
                                "title": f"Indian Creator {niche_names[0]} #{i}",
                                "snippet": f"Contact for business inquiries: creator_{batches_run}_{i}@gmail.com. Subscribe!",
                                "url": f"https://youtube.com/@channel_{batches_run}_{i}"
                            }
                            for i in range(15)
                        ]
                    else:
                        logger.info(f"[DRY RUN] Simulating empty Apify batch {batches_run}...")
                        dataset_items = []
                else:
                    dataset_items = self.apify_client.run_search_batch(queries)

                # Extract emails
                extracted_emails = extract_emails_from_dataset(dataset_items)
                raw_count = len(extracted_emails)

                # Deduplicate against batch and lifetime database
                genuinely_new_emails, intra_dups, master_dups = deduplicator.filter_new_emails(extracted_emails)
                new_count = len(genuinely_new_emails)

                logger.info(
                    f"Batch {batches_run} Summary: {raw_count} valid emails -> "
                    f"{intra_dups} intra-batch dups -> {master_dups} master dups -> "
                    f"{new_count} genuinely new leads"
                )

                # Record batch niches as permanently used
                self.niche_manager.record_batch_as_used(batch_niches, date_str)

                # If new leads obtained, record them into lifetime master DB and pending queue
                if genuinely_new_emails:
                    new_records = [
                        {
                            "email": email,
                            "date_first_seen": date_str,
                            "date_added": date_str,
                            "source_niche": niche_names[0] if niche_names else "Search",
                            "source_run_id": self.run_id,
                        }
                        for email in genuinely_new_emails
                    ]
                    # Update master DB (lifetime deduplication tracking)
                    self.state_manager.add_to_master(new_records)
                    # Add directly to pending queue (so leads are never lost if delivery fails)
                    self.queue_manager.add_leads(new_records)

                    # Update in-memory deduplicator
                    for email in genuinely_new_emails:
                        deduplicator.master_emails.add(email)

                # Recalculate shortage based on updated queue size
                current_queue_size = self.queue_manager.get_queue_size()
                shortage = max(0, self.target - current_queue_size)

                if shortage == 0:
                    logger.info(f"Target satisfied in queue ({current_queue_size} available). Stopping Apify immediately.")
                    break
                else:
                    logger.info(f"Target not yet satisfied. Remaining shortage: {shortage}")

            except (ApifyCreditExhaustedError, ApifyAuthError) as e:
                credit_exhausted = True
                exhaustion_reason = str(e)
                logger.error(f"Apify credit or authorization failure in batch {batches_run}: {e}")
                break
            except ApifyTimeoutError as e:
                logger.error(f"Apify actor run timed out in batch {batches_run}: {e}")
                break
            except ApifyError as e:
                logger.error(f"Apify error in batch {batches_run}: {e}")
                break

        return credit_exhausted, exhaustion_reason, batches_run

    def run(self, force: bool = False, mode: str = "all") -> int:
        """
        Execute the lead workflow according to mode:
        - 'prepare': 01:00 AM overnight preparation. Fills queue. Does NOT send daily email.
        - 'deliver': 11:00 AM IST delivery. Checks queue, runs search if needed, sends email.
        - 'all': Runs preparation and delivery in one session.
        """
        date_str = get_today_ist_date()
        logger = setup_logging(date_str)

        logger.info("=" * 60)
        logger.info(f"Starting Daily Lead Agent | Run ID: {self.run_id} | Date: {date_str} IST")
        logger.info(f"Target: {self.target} leads | Mode: {mode} | Dry Run: {self.dry_run}")

        # Step 1: Idempotency Protection (for delivery runs)
        if mode in ("deliver", "all"):
            if not force and self.state_manager.is_already_delivered_today(date_str):
                logger.info(f"Delivery for today ({date_str}) is already recorded as SENT/COMPLETED. Exiting to prevent duplicates.")
                return 0

        initial_queue_size = self.queue_manager.get_queue_size()
        logger.info(f"Starting pending queue size: {initial_queue_size}")

        credit_exhausted = False
        exhaustion_reason = ""

        # Step 2: Processing / Preparation
        if mode in ("prepare", "all") or (mode == "deliver" and initial_queue_size < self.target):
            credit_exhausted, exhaustion_reason, batches_run = self._process_and_fill_queue(date_str, logger)

        queue_after_processing = self.queue_manager.get_queue_size()

        # Step 3: Handle mode == "prepare" (OVERNIGHT RUN)
        if mode == "prepare":
            logger.info("Overnight preparation run complete. Daily email is scheduled for 11:00 AM IST.")
            status = "PREPARED_CREDIT_EXHAUSTED" if credit_exhausted else "PREPARED"
            reason = f"Prepared queue with {queue_after_processing} leads."
            if credit_exhausted:
                reason += f" Credit limit: {exhaustion_reason}"
                try:
                    self.delivery_manager.send_credit_exhaustion_alert(
                        date_str=date_str,
                        error_details=exhaustion_reason,
                        leads_obtained_today=queue_after_processing,
                        today_target=self.target,
                        shortfall=max(0, self.target - queue_after_processing),
                        daily_file_sent=False,
                    )
                except Exception as e:
                    logger.error(f"Failed to send credit alert email: {e}")

            self.state_manager.record_daily_run(
                date_str=date_str,
                status=status,
                target=self.target,
                delivered=0,
                reason=reason,
                run_id=self.run_id,
            )
            return queue_after_processing

        # Step 4: Handle mode == "deliver" or "all" (11:00 AM IST DELIVERY)
        # Stage leads from queue without mutating queue on disk
        leads_to_deliver, remaining_queue = self.queue_manager.select_leads_for_delivery(self.target)
        final_lead_count = len(leads_to_deliver)
        shortfall = self.target - final_lead_count

        if credit_exhausted:
            logger.warning("Sending credit exhaustion alert email to administrator...")
            try:
                self.delivery_manager.send_credit_exhaustion_alert(
                    date_str=date_str,
                    error_details=exhaustion_reason,
                    leads_obtained_today=final_lead_count,
                    today_target=self.target,
                    shortfall=shortfall,
                    daily_file_sent=(final_lead_count > 0),
                )
            except Exception as e:
                logger.error(f"Failed to send credit alert email: {e}")

        delivered_success = False
        if leads_to_deliver:
            emails_to_deliver = [item["email"] for item in leads_to_deliver]
            delivery_file_path = self.delivery_manager.generate_lead_file(emails_to_deliver, date_str)
            shortfall_note = exhaustion_reason if credit_exhausted else None

            try:
                delivered_success = self.delivery_manager.send_daily_leads(
                    file_path=delivery_file_path,
                    lead_count=final_lead_count,
                    queue_remaining=len(remaining_queue),
                    date_str=date_str,
                    target=self.target,
                    shortfall_reason=shortfall_note,
                )
            except Exception as e:
                logger.error(f"Failed to deliver daily lead email: {e}")
                delivered_success = False

            # TRANSACTIONAL QUEUE SAFETY & POST-DELIVERY STATE RECORDING:
            if delivered_success:
                # 1. Immediately record atomic delivery receipt (guarantees idempotency even if subsequent steps fail)
                try:
                    self.state_manager.record_delivery_receipt(date_str, self.run_id, emails_to_deliver)
                except Exception as receipt_err:
                    logger.error(f"Error recording delivery receipt: {receipt_err}")

                # 2. ONLY commit removal from queue after email successfully sent!
                self.queue_manager.commit_delivered_leads(remaining_queue)
                final_status = "PARTIAL_CREDIT_LIMIT" if credit_exhausted else "COMPLETED"
                status_reason = f"Delivered {final_lead_count}/{self.target} leads."
                if credit_exhausted:
                    status_reason += f" Credit limit: {exhaustion_reason}"
            else:
                # Delivery failed: DO NOT remove leads from queue!
                # All leads remain safely in pending_queue.csv for the next attempt.
                logger.error("Delivery failed. All staged leads are preserved safely in pending_queue.csv!")
                final_status = "DELIVERY_FAILED"
                status_reason = f"Delivery failed for {final_lead_count} leads. Leads preserved in queue."
        else:
            logger.warning("No leads available to deliver today.")
            final_status = "CREDIT_EXHAUSTED" if credit_exhausted else "NO_LEADS_AVAILABLE"
            status_reason = f"No leads available. Credit exhausted: {credit_exhausted}"

        # Record daily run state
        self.state_manager.record_daily_run(
            date_str=date_str,
            status=final_status,
            target=self.target,
            delivered=final_lead_count if delivered_success else 0,
            reason=status_reason,
            run_id=self.run_id,
        )

        logger.info(
            f"Run {self.run_id} finished. Status: {final_status} | "
            f"Delivered: {final_lead_count if delivered_success else 0}/{self.target} | "
            f"Queue Remaining: {self.queue_manager.get_queue_size()}"
        )
        logger.info("=" * 60)
        return final_lead_count if delivered_success else 0


def parse_args():
    parser = argparse.ArgumentParser(description="Daily Lead Agent for YouTube Creator Outreach")
    parser.add_argument("--target", type=int, default=DAILY_TARGET, help=f"Daily lead target (default: {DAILY_TARGET})")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without external API or SMTP calls")
    parser.add_argument("--test-mode", action="store_true", help="Run full pipeline with synthetic creator data (0 credits consumed)")
    parser.add_argument("--force", action="store_true", help="Bypass today's idempotency check")
    parser.add_argument("--mode", choices=["all", "prepare", "deliver"], default="all", help="Workflow mode ('prepare'=overnight, 'deliver'=11 AM)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    agent = DailyLeadAgent(target=args.target, dry_run=args.dry_run, test_mode=args.test_mode)
    count = agent.run(force=args.force, mode=args.mode)
    sys.exit(0)
