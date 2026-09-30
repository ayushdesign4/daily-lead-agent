"""Pending queue management and FIFO lead dispatching with transactional delivery safety."""

import logging
from typing import List, Dict, Tuple
from src.state_manager import StateManager

logger = logging.getLogger(__name__)


class QueueManager:
    """Manages the persistent FIFO queue of extra unconsumed leads."""

    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager

    def get_queue_size(self) -> int:
        """Return the current number of available leads in the queue."""
        queue = self.state_manager.load_queue()
        return len(queue)

    def select_leads_for_delivery(self, target_count: int) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
        """
        Stage up to `target_count` leads for delivery without mutating pending_queue.csv on disk.
        Returns:
            (selected_leads, remaining_queue)
        """
        queue = self.state_manager.load_queue()
        selected = queue[:target_count]
        remaining = queue[target_count:]
        logger.info(f"Staged {len(selected)} leads for delivery. Remaining in stage: {len(remaining)}")
        return selected, remaining

    def commit_delivered_leads(self, remaining_queue: List[Dict[str, str]]) -> None:
        """
        Atomically persist the remaining queue ONLY after delivery has successfully sent.
        """
        self.state_manager.save_queue(remaining_queue)
        logger.info(f"Delivered leads permanently removed from queue. Remaining: {len(remaining_queue)}")

    def restore_leads(self, leads_to_restore: List[Dict[str, str]]) -> None:
        """
        Restore leads back to the head of the queue if delivery failed.
        Ensures zero leads are lost due to email transmission failure.
        """
        current_queue = self.state_manager.load_queue()
        current_emails = {row["email"].strip().lower() for row in current_queue}
        restored = []
        for lead in leads_to_restore:
            email = lead["email"].strip().lower()
            if email not in current_emails:
                restored.append(lead)
                current_emails.add(email)
        new_queue = restored + current_queue
        self.state_manager.save_queue(new_queue)
        logger.info(f"Restored {len(restored)} leads to head of queue after delivery failure. Queue size: {len(new_queue)}")

    def consume_leads(self, target_count: int) -> Tuple[List[Dict[str, str]], int]:
        """
        Legacy helper for popping leads. Kept for backwards compatibility.
        """
        selected, remaining = self.select_leads_for_delivery(target_count)
        self.commit_delivered_leads(remaining)
        shortage = target_count - len(selected)
        return selected, shortage

    def add_leads(self, leads: List[Dict[str, str]]) -> int:
        """Add surplus leads to the pending queue."""
        added = self.state_manager.add_to_queue(leads)
        logger.info(f"Enqueued {added} surplus leads into pending queue.")
        return added
