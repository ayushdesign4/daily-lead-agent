"""Deduplication against current batch and lifetime master database."""

import logging
from typing import List, Dict, Set, Tuple

logger = logging.getLogger(__name__)


class Deduplicator:
    """Handles multi-level deduplication for leads."""

    def __init__(self, master_leads: Dict[str, Dict[str, str]]):
        # master_leads is a mapping of email -> row
        self.master_emails: Set[str] = {e.lower().strip() for e in master_leads.keys()}

    def filter_new_emails(
        self,
        extracted_emails: List[str]
    ) -> Tuple[List[str], int, int]:
        """
        Deduplicates extracted emails:
        1. Removes internal duplicates in extracted_emails.
        2. Filters out any email already in lifetime master database.

        Returns:
            (genuinely_new_emails, intra_batch_duplicates_count, master_duplicates_count)
        """
        seen_in_batch: Set[str] = set()
        unique_batch_emails: List[str] = []
        intra_batch_duplicates = 0

        for raw_email in extracted_emails:
            norm_email = raw_email.lower().strip()
            if norm_email in seen_in_batch:
                intra_batch_duplicates += 1
            else:
                seen_in_batch.add(norm_email)
                unique_batch_emails.append(norm_email)

        # Now check against lifetime master DB
        genuinely_new: List[str] = []
        master_duplicates = 0

        for email in unique_batch_emails:
            if email in self.master_emails:
                master_duplicates += 1
            else:
                genuinely_new.append(email)

        logger.info(
            f"Deduplication summary: {len(extracted_emails)} raw -> "
            f"{intra_batch_duplicates} intra-batch duplicates -> "
            f"{master_duplicates} master duplicates removed -> "
            f"{len(genuinely_new)} genuinely new leads"
        )
        return genuinely_new, intra_batch_duplicates, master_duplicates
