"""Pending queue management and FIFO lead dispatching."""

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

    def consume_leads(self, target_count: int) -> Tuple[List[Dict[str, str]], int]:
        """
        Take up to `target_count` leads from the queue.
        Returns:
            (selected_leads, remaining_shortage)
        """
        queue = self.state_manager.load_queue()
        initial_size = len(queue)

        if initial_size == 0:
            logger.info("Pending queue is empty. Full target must be retrieved from search.")
            return [], target_count

        selected = queue[:target_count]
        remaining = queue[target_count:]

        # Atomically update queue
        self.state_manager.save_queue(remaining)

        delivered_count = len(selected)
        shortage = target_count - delivered_count

        logger.info(
            f"Consumed {delivered_count} leads from queue. "
            f"Remaining queue size: {len(remaining)}. "
            f"Remaining shortage: {shortage}"
        )
        return selected, shortage

    def add_leads(self, leads: List[Dict[str, str]]) -> int:
        """Add surplus leads to the pending queue."""
        added = self.state_manager.add_to_queue(leads)
        logger.info(f"Enqueued {added} surplus leads into pending queue.")
        return added
