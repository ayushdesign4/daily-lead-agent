"""Unit and integration tests for the Dynamic Outreach Email Template System."""

import pytest
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.outreach.dynamic_templates import (
    DynamicTemplateEngine,
    REFERENCE_TEMPLATES,
    validate_template_style,
    get_current_week_key,
    compute_text_hash,
)
from src.outreach.template_manager import (
    TemplateManager,
    APPROVED_TEMPLATES,
    APPROVED_SUBJECTS,
)


class TestReferenceTemplates:
    """Verify all 10 canonical reference templates match style and requirements."""

    def test_all_10_reference_templates_available(self):
        """Verify all 10 reference templates are present and accessible."""
        assert len(REFERENCE_TEMPLATES) == 10
        ref_all = TemplateManager.get_all_reference_templates()
        assert len(ref_all) == 10

        for i in range(1, 11):
            ref = TemplateManager.get_reference_template(i)
            assert ref["id"] == i
            assert ref["subject"] and len(ref["subject"]) > 0
            assert ref["body"] and len(ref["body"]) > 0
            assert i in APPROVED_TEMPLATES

    def test_reference_templates_comply_with_writing_rules(self):
        """Every reference template must strictly comply with all writing style rules."""
        for i in range(1, 11):
            ref = TemplateManager.get_reference_template(i)
            subject = ref["subject"]
            body = ref["body"]

            # Style validator check
            is_valid, issues = validate_template_style(subject, body)
            assert is_valid, f"Template {i} failed style validation: {issues}"

            # Word count constraint (15 to 50 words)
            words = body.strip().split()
            assert 15 <= len(words) <= 50, f"Template {i} word count ({len(words)}) outside 15-50"

            # No greetings
            first_word = re.sub(r"[^\w]", "", words[0].lower())
            assert first_word not in {"hi", "hello", "dear", "hey", "greetings"}

            # Ends with Ayush
            assert body.strip().endswith("Ayush")

            # Subject length <= 30 chars
            assert len(subject) <= 30

            # No emojis or decorative chars
            assert not re.search(r"[\U00010000-\U0010ffff\u2600-\u26ff★🔥🚀✨]", subject + body)


class TestDynamicTemplateEngine:
    """Verify dynamic weekly variation generation, persistent storage, and non-repetition."""

    def test_weekly_variations_follow_writing_style(self, tmp_path):
        """Generated weekly variations must strictly obey writing rules."""
        engine = DynamicTemplateEngine(storage_path=tmp_path / "test_templates.json")

        for week_key in ["2026-W44", "2026-W45", "2026-W46"]:
            templates = engine.generate_weekly_variations(week_key=week_key, batch_count=9)
            assert len(templates) == 9

            for tmpl in templates:
                is_valid, issues = validate_template_style(tmpl["subject"], tmpl["body"])
                assert is_valid, f"Week {week_key} template failed style: {issues}"

                # Word count check
                words = tmpl["body"].strip().split()
                assert 20 <= len(words) <= 50, f"Word count ({len(words)}) outside ideal range"

                # No greetings
                assert not re.match(r"^(hi|hello|dear|hey|greetings)\b", tmpl["body"].strip(), re.IGNORECASE)

                # Signature
                assert tmpl["body"].strip().endswith("Ayush")

                # No spam terms or fabricated claims
                lower = (tmpl["subject"] + " " + tmpl["body"]).lower()
                assert not any(s in lower for s in ["guaranteed", "viral", "explode", "skyrocket", "clickbait", "crazy"])
                assert not any(f in lower for f in ["watched your video", "loved your latest", "great upload yesterday"])

    def test_subjects_and_bodies_distinct_within_week(self, tmp_path):
        """All 9 batches within a week must have distinct subjects and distinct bodies."""
        engine = DynamicTemplateEngine(storage_path=tmp_path / "test_templates.json")
        templates = engine.get_templates_for_week(date_str="2026-11-01", batch_count=9)

        subjects = [t["subject"] for t in templates]
        bodies = [t["body"] for t in templates]

        # 9 distinct subjects
        assert len(subjects) == 9
        assert len(set(subjects)) == 9

        # 9 distinct bodies
        assert len(bodies) == 9
        assert len(set(bodies)) == 9

    def test_persistent_storage_is_idempotent(self, tmp_path):
        """Templates are persisted to JSON and NOT regenerated randomly per recipient or per call."""
        storage_file = tmp_path / "outreach_templates.json"
        engine = DynamicTemplateEngine(storage_path=storage_file)

        # Call 1: Generates and persists for 2026-11-01 (week 2026-W44)
        first_call = engine.get_templates_for_week(date_str="2026-11-01")
        assert storage_file.exists()

        # Call 2: Must load exactly identical templates without re-randomizing
        second_call = engine.get_templates_for_week(date_str="2026-11-01")
        assert len(first_call) == len(second_call)
        for t1, t2 in zip(first_call, second_call):
            assert t1["subject"] == t2["subject"]
            assert t1["body"] == t2["body"]

        # Re-instantiate engine from disk file to verify persistence
        new_engine_instance = DynamicTemplateEngine(storage_path=storage_file)
        third_call = new_engine_instance.get_templates_for_week(date_str="2026-11-01")
        for t1, t3 in zip(first_call, third_call):
            assert t1["subject"] == t3["subject"]
            assert t1["body"] == t3["body"]

    def test_history_tracking_across_weeks(self, tmp_path):
        """History records are maintained across weekly rollovers to prevent repetition."""
        storage_file = tmp_path / "outreach_templates.json"
        engine = DynamicTemplateEngine(storage_path=storage_file)

        week1 = engine.get_templates_for_week(date_str="2026-10-26")  # Week 44
        week2 = engine.get_templates_for_week(date_str="2026-11-02")  # Week 45

        # Check history contains both weeks
        history = engine._data.get("history", [])
        week_keys = [h["week_key"] for h in history]
        assert "2026-W44" in week_keys
        assert "2026-W45" in week_keys

        # Ensure week 1 and week 2 are not identical
        w1_bodies = [t["body"] for t in week1]
        w2_bodies = [t["body"] for t in week2]
        assert w1_bodies != w2_bodies

    def test_no_fabricated_personalization(self, tmp_path):
        """System never fabricates watch history, specific video praise, or fake claims."""
        engine = DynamicTemplateEngine(storage_path=tmp_path / "test_templates.json")
        for week_idx in range(1, 10):
            week_key = f"2026-W{week_idx:02d}"
            templates = engine.generate_weekly_variations(week_key=week_key)
            for tmpl in templates:
                body = tmpl["body"].lower()
                assert "watched your" not in body
                assert "video about" not in body
                assert "loved your" not in body
                assert "great video" not in body
                # Truthful discovery phrasing only
                assert any(term in body for term in ["channel", "uploads", "videos", "content"])


class TestTemplateManagerIntegration:
    """Verify TemplateManager backward compatibility and pipeline integration."""

    def test_legacy_rotation_pattern_when_date_not_specified(self):
        """Legacy callers without date_str receive deterministic 1, 2, 3 pattern."""
        expected = [1, 2, 3, 1, 2, 3, 1, 2, 3]
        for idx, exp_id in enumerate(expected):
            tmpl_id, body = TemplateManager.get_template_for_batch(idx)
            assert tmpl_id == exp_id
            assert body == APPROVED_TEMPLATES[exp_id]
            assert "Ayush" in body

    def test_dynamic_rotation_when_date_specified(self, tmp_path):
        """When date_str is provided, TemplateManager retrieves weekly dynamic variations."""
        test_engine = DynamicTemplateEngine(storage_path=tmp_path / "templates.json")
        TemplateManager.set_engine(test_engine)

        try:
            subjects = [TemplateManager.get_subject_for_batch(i, date_str="2026-11-01") for i in range(9)]
            assert len(subjects) == 9
            assert len(set(subjects)) == 9

            templates = [TemplateManager.get_template_for_batch(i, date_str="2026-11-01") for i in range(9)]
            assert len(templates) == 9
            bodies = [t[1] for t in templates]
            assert len(set(bodies)) == 9
        finally:
            # Restore default engine
            TemplateManager.set_engine(TemplateManager._DEFAULT_ENGINE if hasattr(TemplateManager, "_DEFAULT_ENGINE") else test_engine)
