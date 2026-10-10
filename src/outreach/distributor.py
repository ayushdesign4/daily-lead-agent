"""Recipient distribution across 9 sender accounts."""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def distribute_recipients(
    eligible_emails: List[str],
    sender_accounts: List[str]
) -> List[Dict[str, Any]]:
    """
    Distribute eligible emails across sender accounts with strict constraints:
    - Sort deterministically (alphabetically)
    - Even distribution: difference between any two batch sizes <= 1
    - Each account receives floor(N/K) or ceil(N/K)
    - No duplicate recipient across batches
    - Returns list of batch dicts:
      [{'batch_index': int, 'sender_account': str, 'recipients': List[str]}]
    """
    num_senders = len(sender_accounts)
    if num_senders == 0:
        return []

    # Sort deterministically
    sorted_emails = sorted(list(dict.fromkeys(eligible_emails)))
    total_emails = len(sorted_emails)

    base_count = total_emails // num_senders
    remainder = total_emails % num_senders

    batches: List[Dict[str, Any]] = []
    current_idx = 0

    for i in range(num_senders):
        # The first `remainder` accounts get (base_count + 1), the rest get base_count
        batch_size = base_count + (1 if i < remainder else 0)
        batch_recipients = sorted_emails[current_idx:current_idx + batch_size]
        current_idx += batch_size

        batches.append({
            "batch_index": i,
            "sender_account": sender_accounts[i],
            "recipients": batch_recipients,
            "count": len(batch_recipients),
        })

    # Validate distribution invariant
    sizes = [b["count"] for b in batches]
    if sizes:
        assert max(sizes) - min(sizes) <= 1, "Distribution unevenness exceeds 1!"
    all_assigned = [em for b in batches for em in b["recipients"]]
    assert len(all_assigned) == len(set(all_assigned)) == total_emails, "Duplicate or dropped recipients!"

    logger.info(
        f"Distributed {total_emails} recipients across {num_senders} accounts. "
        f"Batch sizes: {sizes}"
    )
    return batches
