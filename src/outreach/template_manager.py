"""Outreach template manager with dynamic weekly generation, persistent storage, and reference standards."""

import logging
from typing import Dict, Tuple, List, Optional, Any
from pathlib import Path

from src.state_manager import get_today_ist_date
from src.outreach.dynamic_templates import (
    DynamicTemplateEngine,
    REFERENCE_TEMPLATES,
    validate_template_style,
    get_current_week_key,
    DEFAULT_TEMPLATES_FILE,
)

logger = logging.getLogger(__name__)

# Expose canonical reference templates 1 to 10
TEMPLATE_1 = REFERENCE_TEMPLATES[1]["body"]
TEMPLATE_2 = REFERENCE_TEMPLATES[2]["body"]
TEMPLATE_3 = REFERENCE_TEMPLATES[3]["body"]
TEMPLATE_4 = REFERENCE_TEMPLATES[4]["body"]
TEMPLATE_5 = REFERENCE_TEMPLATES[5]["body"]
TEMPLATE_6 = REFERENCE_TEMPLATES[6]["body"]
TEMPLATE_7 = REFERENCE_TEMPLATES[7]["body"]
TEMPLATE_8 = REFERENCE_TEMPLATES[8]["body"]
TEMPLATE_9 = REFERENCE_TEMPLATES[9]["body"]
TEMPLATE_10 = REFERENCE_TEMPLATES[10]["body"]

APPROVED_TEMPLATES: Dict[int, str] = {
    i: REFERENCE_TEMPLATES[i]["body"]
    for i in range(1, 11)
}

# 9 distinct, short, relevant reference subjects for the 9 batches
APPROVED_SUBJECTS: List[str] = [
    REFERENCE_TEMPLATES[i]["subject"]
    for i in range(1, 10)
]

# Shared default dynamic engine instance
_DEFAULT_ENGINE = DynamicTemplateEngine(storage_path=DEFAULT_TEMPLATES_FILE)


class TemplateManager:
    """
    Manages rotation of approved templates, dynamic weekly variation generation,
    persistent storage, and distinct subjects for outreach batches.
    """

    engine: DynamicTemplateEngine = _DEFAULT_ENGINE

    @classmethod
    def set_engine(cls, custom_engine: DynamicTemplateEngine) -> None:
        """Inject custom engine instance (e.g. for isolated tests with temp files)."""
        cls.engine = custom_engine

    @classmethod
    def get_template(cls, template_id: int) -> str:
        """Retrieve copy for template ID (1 to 10)."""
        if template_id in APPROVED_TEMPLATES:
            return APPROVED_TEMPLATES[template_id]
        raise ValueError(f"Invalid template ID {template_id}. Available reference templates: 1 to 10.")

    @classmethod
    def get_reference_template(cls, template_id: int) -> Dict[str, Any]:
        """Retrieve full reference template specification (id, subject, body)."""
        return cls.engine.get_reference_template(template_id)

    @classmethod
    def get_all_reference_templates(cls) -> List[Dict[str, Any]]:
        """Retrieve all 10 canonical reference templates."""
        return cls.engine.get_reference_templates()

    @classmethod
    def get_template_for_batch(
        cls,
        batch_index: int,
        date_str: Optional[str] = None,
        use_dynamic: Optional[bool] = None,
    ) -> Tuple[int, str]:
        """
        Cycle through templates.
        - If use_dynamic is True, or if date_str is provided:
          Retrieves the persistent weekly dynamic template for this batch.
        - If use_dynamic is False, or date_str is None (legacy default):
          Cycles through templates in deterministic pattern (1, 2, 3, 1, 2, 3, ...).
        Returns (template_id, body_text).
        """
        if use_dynamic is True or (use_dynamic is None and date_str is not None):
            tmpl_id, body = cls.engine.get_template_for_batch(batch_index, date_str=date_str)
            # Retain integer template ID cycling for state compatibility
            return (batch_index % 3) + 1, body

        # Backward compatibility mode for legacy callers and unit tests
        template_id = (batch_index % 3) + 1
        return template_id, APPROVED_TEMPLATES[template_id]

    @classmethod
    def get_subject_for_batch(
        cls,
        batch_index: int,
        date_str: Optional[str] = None,
        use_dynamic: Optional[bool] = None,
    ) -> str:
        """
        Get distinct short subject for batch index (0 to 8).
        Resolves to the active weekly dynamic template subject.
        """
        target_date = date_str or get_today_ist_date()
        return cls.engine.get_subject_for_batch(batch_index, date_str=target_date)

    @classmethod
    def get_active_weekly_templates(cls, date_str: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve all persistent variations generated for the current week."""
        return cls.engine.get_templates_for_week(date_str)

    @classmethod
    def validate_template(cls, subject: str, body: str) -> Tuple[bool, List[str]]:
        """Validate template against strict writing rules."""
        return validate_template_style(subject, body)
