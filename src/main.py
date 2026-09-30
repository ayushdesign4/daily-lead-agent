"""Daily Lead Agent Orchestrator.

Implements demand-driven scraping, queue consumption, deduplication,
credit exhaustion handling, and daily delivery.
"""

import sys
import uuid
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Optional

from src.config import (
    DAILY_TARGET,
    MAX_QUERIES_PER_BATCH,
    MAX_BATCHES_PER_RUN,
    LOGS_DIR,
    DRY_RUN,
    TEST_MODE,
)
from src.state_manager import StateManager, get_today_ist_date, get_current_ist_time
from src.niche_manager import NicheManager
from src.email_extractor import extract_emails_from_dataset
from src.deduplicator import Deduplicator
from src.apify_client import ApifyClient, ApifyCreditExhaustedError, ApifyAuthError, ApifyError
from src.queue_manager import QueueManager
from src.delivery import DeliveryManager

# Setup secure logger that will write to both file and console
def setup_logging(date_str: str) -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"{date_str}.log"

    logger = logging.getLogger("DailyLeadAgent")
    logger.setLevel(logging.INFO)

    # Avoid adding duplicate handlers if setup_logging called multiple times
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

    def run(self, force: bool = False, mode: str = "all") -> int:
        """
        Execute the daily lead workflow.
        Returns the number of leads delivered.
        """
        date_str = get_today_ist_date()
        logger = setup_logging(date_str)

        logger.info("=" * 60)
        logger.info(f"Starting Daily Lead Agent | Run ID: {self.run_id} | Date: {date_str} IST")
        logger.info(f"Target: {self.target} leads | Mode: {mode} | Dry Run: {self.dry_run}")

        # Step 1: Idempotency Protection
        if not force and self.state_manager.is_already_delivered_today(date_str):
            logger.info(f"Delivery for today ({date_str}) is already recorded as SENT/COMPLETED. Exiting to prevent duplicates.")
            return 0

        # Step 2: Queue inspection (Credit optimization rule: always check queue first)
        initial_queue_size = self.queue_manager.get_queue_size()
        logger.info(f"Starting pending queue size: {initial_queue_size}")

        daily_pool: List[Dict[str, str]] = []
        shortage = self.target

        # Pop from queue if available
        if initial_queue_size > 0:
            popped_leads, shortage = self.queue_manager.consume_leads(self.target)
            daily_pool.extend(popped_leads)
            logger.info(f"Retrieved {len(popped_leads)} leads from pending queue. Remaining shortage: {shortage}")

        credit_exhausted = False
        exhaustion_reason = ""
        batches_run = 0

        # Step 3: Run Apify in demand-driven batches if shortage remains
        if shortage > 0 and mode != "deliver_only":
            master_leads = self.state_manager.load_master_leads()
            deduplicator = Deduplicator(master_leads)

            while shortage > 0 and batches_run < MAX_BATCHES_PER_RUN:
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

                    # If new leads obtained, record them into master DB immediately
                    new_records = [
                        {
                            "email": email,
                            "date_first_seen": date_str,
                            "source_niche": niche_names[0] if niche_names else "Search",
                            "source_run_id": self.run_id,
                        }
                        for email in genuinely_new_emails
                    ]
                    self.state_manager.add_to_master(new_records)

                    # Also update our in-memory deduplicator so subsequent batches in this run won't duplicate
                    for email in genuinely_new_emails:
                        deduplicator.master_emails.add(email)

                    # Allocate to daily pool and pending queue
                    if new_count >= shortage:
                        allocated_to_today = new_records[:shortage]
                        surplus_for_queue = new_records[shortage:]

                        daily_pool.extend(allocated_to_today)
                        if surplus_for_queue:
                            self.queue_manager.add_leads(surplus_for_queue)

                        shortage = 0
                        logger.info(
                            f"Daily target SATISFIED! {len(allocated_to_today)} leads to today, "
                            f"{len(surplus_for_queue)} saved in pending queue. Stopping Apify immediately."
                        )
                        break
                    else:
                        daily_pool.extend(new_records)
                        shortage -= new_count
                        logger.info(f"Target not yet satisfied. Remaining shortage: {shortage}")

                except (ApifyCreditExhaustedError, ApifyAuthError) as e:
                    credit_exhausted = True
                    exhaustion_reason = str(e)
                    logger.error(f"Apify credit or authorization failure in batch {batches_run}: {e}")
                    # Stop immediately without retrying
                    break
                except ApifyError as e:
                    logger.error(f"Apify error in batch {batches_run}: {e}")
                    break

        # Step 4: Handle credit exhaustion notification if triggered
        final_lead_count = len(daily_pool)
        queue_remaining = self.queue_manager.get_queue_size()

        if credit_exhausted:
            logger.warning("Sending credit exhaustion alert email to administrator...")
            try:
                self.delivery_manager.send_credit_exhaustion_alert(
                    date_str=date_str,
                    error_details=exhaustion_reason,
                    leads_obtained_today=final_lead_count,
                    today_target=self.target,
                    shortfall=shortage,
                    daily_file_sent=(final_lead_count > 0),
                )
            except Exception as e:
                logger.error(f"Failed to send credit alert email: {e}")

        # Step 5: Deliver daily leads
        delivered_success = False
        delivery_file_path = None
        emails_to_deliver = [item["email"] for item in daily_pool]

        if emails_to_deliver:
            delivery_file_path = self.delivery_manager.generate_lead_file(emails_to_deliver, date_str)
            shortfall_note = exhaustion_reason if credit_exhausted else None

            try:
                delivered_success = self.delivery_manager.send_daily_leads(
                    file_path=delivery_file_path,
                    lead_count=final_lead_count,
                    queue_remaining=queue_remaining,
                    date_str=date_str,
                    target=self.target,
                    shortfall_reason=shortfall_note,
                )
            except Exception as e:
                logger.error(f"Failed to deliver daily lead email: {e}")
                delivered_success = False
        else:
            logger.warning("No leads available to deliver today.")

        # Step 6: Record run status in daily_runs.csv
        final_status = "FAILED"
        if delivered_success:
            final_status = "PARTIAL_CREDIT_LIMIT" if credit_exhausted else "COMPLETED"
        elif credit_exhausted:
            final_status = "CREDIT_EXHAUSTED"

        status_reason = f"Delivered {final_lead_count}/{self.target} leads."
        if credit_exhausted:
            status_reason += f" Credit limit: {exhaustion_reason}"

        self.state_manager.record_daily_run(
            date_str=date_str,
            status=final_status,
            target=self.target,
            delivered=final_lead_count,
            reason=status_reason,
            run_id=self.run_id,
        )

        logger.info(
            f"Run {self.run_id} finished. Status: {final_status} | "
            f"Delivered: {final_lead_count}/{self.target} | "
            f"Queue Remaining: {queue_remaining}"
        )
        logger.info("=" * 60)
        return final_lead_count


def parse_args():
    parser = argparse.ArgumentParser(description="Daily Lead Agent for YouTube Creator Outreach")
    parser.add_argument("--target", type=int, default=DAILY_TARGET, help=f"Daily lead target (default: {DAILY_TARGET})")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without external API or SMTP calls")
    parser.add_argument("--test-mode", action="store_true", help="Run full pipeline with synthetic creator data (0 credits consumed)")
    parser.add_argument("--force", action="store_true", help="Bypass today's idempotency check")
    parser.add_argument("--mode", choices=["all", "prepare", "deliver_only"], default="all", help="Workflow mode")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    agent = DailyLeadAgent(target=args.target, dry_run=args.dry_run, test_mode=args.test_mode)
    count = agent.run(force=args.force, mode=args.mode)
    sys.exit(0)
