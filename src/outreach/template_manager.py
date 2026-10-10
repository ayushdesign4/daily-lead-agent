"""Outreach template manager implementing the 3 approved owner templates and short subjects."""

import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

# Approved base copy from Section 8 of specification
TEMPLATE_1 = """I came across your channel and had an observation for one of your thumbnails.

I have some examples of my work if you'd like to see them.

Would you be open to me trying one for your next upload?

Ayush"""

TEMPLATE_2 = """Found your channel and thought I'd reach out.

I'm a thumbnail designer and would love to show you my work.

Interested?

Ayush"""

TEMPLATE_3 = """Came across your channel and liked the content.

I design thumbnails for creators and wanted to share my work.

Want to take a look?

Ayush"""

APPROVED_TEMPLATES = {
    1: TEMPLATE_1,
    2: TEMPLATE_2,
    3: TEMPLATE_3,
}

# 9 distinct, short, relevant subjects for the 9 batches
APPROVED_SUBJECTS = [
    "Thumbnail",
    "Visuals",
    "Click",
    "Better Views",
    "Channel Design",
    "Thumbnails",
    "Cover Art",
    "Channel Visuals",
    "Video Clicks",
]


class TemplateManager:
    """Manages rotation of approved templates and distinct subjects for 9 batches."""

    @staticmethod
    def get_template(template_id: int) -> str:
        """Retrieve copy for template 1, 2, or 3."""
        if template_id not in APPROVED_TEMPLATES:
            raise ValueError(f"Invalid template ID {template_id}. Only templates 1, 2, and 3 are approved.")
        return APPROVED_TEMPLATES[template_id]

    @staticmethod
    def get_template_for_batch(batch_index: int) -> Tuple[int, str]:
        """
        Cycle through templates in deterministic pattern (1, 2, 3, 1, 2, 3, ...).
        Returns (template_id, body_text).
        """
        template_id = (batch_index % 3) + 1
        return template_id, APPROVED_TEMPLATES[template_id]

    @staticmethod
    def get_subject_for_batch(batch_index: int) -> str:
        """Get distinct short subject for batch index (0 to 8)."""
        idx = batch_index % len(APPROVED_SUBJECTS)
        return APPROVED_SUBJECTS[idx]
