"""Dynamic Outreach Email Template Generator and Persistent Storage Engine.

Adheres strictly to the 10 reference templates and writing style rules:
- Length: 25-50 words (ideal range, acceptable 15-50 words).
- No Hi, Hello, Dear, or unnecessary greetings.
- Simple, natural, and professional English.
- No emojis, decorative symbols, or unnecessary special characters.
- Avoid exaggerated marketing language and spammy claims.
- No aggressive sales language.
- Sounds like a real freelance thumbnail designer contacting a creator.
- Friendly, direct, and conversational.
- Truthful discovery (no fabricated watch history or fake comments).
- Same basic purpose: introduce thumbnail design and ask to see portfolio.
- Sign off: "Ayush".
- Weekly persistent generation with history tracking to prevent accidental repetition.
"""

import os
import re
import json
import logging
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Set, Any
import random

from src.state_manager import get_today_ist_date

logger = logging.getLogger(__name__)

# Default persistent template storage file
DEFAULT_TEMPLATES_FILE = Path("data/outreach_templates.json")

# The 10 Reference Templates exactly as specified in the reference standard
REFERENCE_TEMPLATES: Dict[int, Dict[str, Any]] = {
    1: {
        "id": 1,
        "subject": "Your channel",
        "body": "Came across your channel and thought I’d get in touch.\n\nI design YouTube thumbnails and wanted to share my work.\n\nInterested in taking a look?\n\nAyush",
    },
    2: {
        "id": 2,
        "subject": "Thumbnail design",
        "body": "Found your videos recently.\n\nI work with creators on thumbnail design and thought my work might suit your channel.\n\nWant to see it?\n\nAyush",
    },
    3: {
        "id": 3,
        "subject": "Quick question",
        "body": "I’ve been checking out your channel.\n\nAre you open to seeing the work of a thumbnail designer?\n\nAyush",
    },
    4: {
        "id": 4,
        "subject": "Your videos",
        "body": "Came across a few of your uploads and wanted to connect.\n\nI design thumbnails for creators. Would you be interested in seeing my work?\n\nAyush",
    },
    5: {
        "id": 5,
        "subject": "Design work",
        "body": "I work on YouTube thumbnails and found your channel while browsing.\n\nThought I’d introduce myself and share what I do.\n\nInterested?\n\nAyush",
    },
    6: {
        "id": 6,
        "subject": "Thumbnail work",
        "body": "Your channel came up while I was exploring YouTube.\n\nI’m a thumbnail designer and thought there could be a good fit.\n\nWould you like to see my portfolio?\n\nAyush",
    },
    7: {
        "id": 7,
        "subject": "A quick introduction",
        "body": "I design thumbnails for YouTube creators and wanted to get in touch.\n\nWould you be open to checking out my work?\n\nAyush",
    },
    8: {
        "id": 8,
        "subject": "Channel thumbnails",
        "body": "I came across your channel and wanted to ask if you ever work with freelance thumbnail designers.\n\nI’d be happy to share my portfolio.\n\nAyush",
    },
    9: {
        "id": 9,
        "subject": "Your content",
        "body": "Found your channel recently and enjoyed looking through your uploads.\n\nI’m a thumbnail designer. Would you be interested in seeing some of my work?\n\nAyush",
    },
    10: {
        "id": 10,
        "subject": "Thumbnail portfolio",
        "body": "I help YouTube creators with thumbnail design.\n\nThought I’d reach out after finding your channel.\n\nWould you like me to send my portfolio?\n\nAyush",
    },
}

# Curated modular components for controlled, natural, professional English variations
OPENERS = [
    "Came across your channel and thought I’d get in touch.",
    "Found your channel while browsing YouTube.",
    "Your channel came up while I was exploring YouTube.",
    "Came across your uploads and wanted to reach out.",
    "I’ve been checking out your channel recently.",
    "Found your channel recently and wanted to connect.",
    "I came across your channel while looking through creator content.",
    "Found your videos recently while exploring YouTube.",
    "Your channel caught my attention while browsing.",
    "Came across your content and thought I’d introduce myself.",
    "I recently came across your channel.",
    "Found your channel while exploring content in your niche.",
    "Your channel came up and I wanted to drop a quick note.",
    "Came across a few of your uploads recently.",
    "Found your channel and thought I’d reach out directly.",
    "I’ve been looking through your channel and wanted to connect.",
]

CORE_PROPOSITIONS = [
    "I design YouTube thumbnails and wanted to share my work.",
    "I work with creators on thumbnail design and thought my work might suit your channel.",
    "I’m a freelance thumbnail designer and wanted to see if you’re open to connecting.",
    "I help creators with thumbnail design and wanted to introduce what I do.",
    "I design thumbnails for YouTube channels and thought there could be a good fit.",
    "I work on YouTube thumbnails and wanted to share a few examples.",
    "I’m a thumbnail designer and wanted to share what I’ve been working on.",
    "I create custom YouTube thumbnails and wanted to see if you ever work with freelancers.",
    "I specialize in YouTube thumbnails and thought my style might work well for your uploads.",
    "I work with creators on thumbnail visuals and wanted to share my portfolio.",
    "I’m a thumbnail designer looking to collaborate with creators like you.",
    "I design thumbnails for creators and thought I’d share some relevant samples.",
    "I focus on YouTube thumbnail design and wanted to share some recent examples.",
]

CALLS_TO_ACTION = [
    "Interested in taking a look?",
    "Want to see it?",
    "Are you open to seeing the work of a thumbnail designer?",
    "Would you be interested in seeing my work?",
    "Interested?",
    "Would you like to see my portfolio?",
    "Would you be open to checking out my work?",
    "I’d be happy to share my portfolio if you’re interested.",
    "Would you like me to send over my portfolio?",
    "Would you be open to taking a look at a few examples?",
    "Open to checking out some samples?",
    "Would you be interested in seeing some of my recent work?",
    "Would you like me to send a few samples?",
    "Interested in seeing some examples?",
]

SUBJECT_POOL = [
    "Your channel",
    "Thumbnail design",
    "Quick question",
    "Your videos",
    "Design work",
    "Thumbnail work",
    "A quick introduction",
    "Channel thumbnails",
    "Your content",
    "Thumbnail portfolio",
    "Channel visuals",
    "Video thumbnails",
    "Quick introduction",
    "Thumbnail designer",
    "Design inquiry",
    "Thumbnails for your channel",
    "Portfolio introduction",
    "Thumbnail samples",
    "Creator thumbnails",
    "Thumbnail visuals",
]

FORBIDDEN_GREETINGS = {
    "hi", "hello", "dear", "hey", "greetings", "good morning", "good afternoon", "good evening", "howdy", "sup"
}

FORBIDDEN_SPAM_WORDS = {
    "guaranteed", "viral", "explode", "skyrocket", "clickbait", "crazy", "boost your views",
    "100%", "urgent", "limited time", "act now", "secret", "make money", "free", "discount",
    "cheap", "best price", "winner", "congratulations", "satisfaction guaranteed", "unbelievable",
    "miracle", "no risk", "instant", "cash"
}

FORBIDDEN_FABRICATED_CLAIMS = {
    "watched your video", "loved your latest", "great upload yesterday", "watched your recent upload",
    "watched your new video", "subscriber of yours", "been following you for years", "huge fan"
}


def validate_template_style(subject: str, body: str) -> Tuple[bool, List[str]]:
    """
    Strict validation of email subject and body against all writing rules:
    - Length: 25-50 words (acceptable range: 15-50 words).
    - No greetings (Hi, Hello, Dear, etc.).
    - Professional, simple English without decorative symbols or emojis.
    - No spam phrases or exaggerated claims.
    - No fabricated watch history or fake comments.
    - Clear thumbnail design introduction and low-pressure ask to see portfolio.
    - Ends with signature 'Ayush'.
    """
    issues: List[str] = []

    # 1. Subject validation
    subj = (subject or "").strip()
    if not subj:
        issues.append("Subject is empty.")
    elif len(subj) > 30:
        issues.append(f"Subject exceeds 30 characters ({len(subj)} chars): '{subj}'.")

    # 2. No emojis or decorative symbols in subject or body
    full_text = f"{subj} {body}"
    if re.search(r"[\U00010000-\U0010ffff\u2600-\u26ff\u2700-\u27bf★🔥🚀✨💥>>==]", full_text):
        issues.append("Text contains emojis or decorative symbols.")

    # 3. No greetings
    body_stripped = (body or "").strip()
    if not body_stripped:
        issues.append("Body is empty.")
        return False, issues

    first_line = body_stripped.split("\n")[0].strip()
    first_words = re.sub(r"[^\w\s]", "", first_line.lower()).split()
    if first_words:
        first_word = first_words[0]
        if first_word in FORBIDDEN_GREETINGS:
            issues.append(f"Body starts with forbidden greeting: '{first_word}'.")
        if len(first_words) >= 2 and f"{first_words[0]} {first_words[1]}" in FORBIDDEN_GREETINGS:
            issues.append(f"Body starts with forbidden greeting: '{first_words[0]} {first_words[1]}'.")

    # 4. Length rule: ideally 25-50 words (acceptable 15-50 words)
    words = body_stripped.split()
    word_count = len(words)
    if word_count < 15 or word_count > 50:
        issues.append(f"Word count ({word_count}) is outside the acceptable 15-50 word range.")

    # 5. Sign-off: must end with Ayush
    lines = [ln.strip() for ln in body_stripped.split("\n") if ln.strip()]
    if not lines or lines[-1] != "Ayush":
        issues.append(f"Body must end with signature 'Ayush', found '{lines[-1] if lines else ''}'.")

    # 6. No spam or aggressive sales words
    lower_text = full_text.lower()
    for spam_term in FORBIDDEN_SPAM_WORDS:
        if re.search(rf"\b{re.escape(spam_term)}\b", lower_text):
            issues.append(f"Contains prohibited spam/marketing term: '{spam_term}'.")

    # 7. No fabricated personalization or fake watch history
    for fake_term in FORBIDDEN_FABRICATED_CLAIMS:
        if fake_term in lower_text:
            issues.append(f"Contains fabricated claim or fake watch history: '{fake_term}'.")

    # 8. Must mention thumbnails/designer
    if not any(kw in lower_text for kw in ("thumbnail", "thumbnails", "designer")):
        issues.append("Body does not mention thumbnails or designer.")

    # 9. Must ask about viewing work or portfolio
    if not any(kw in lower_text for kw in ("portfolio", "work", "examples", "samples", "take a look", "see it", "see them")):
        issues.append("Body does not ask creator to review work or portfolio.")

    return len(issues) == 0, issues


def compute_text_hash(text: str) -> str:
    """Compute normalized hash for deduplication and history tracking."""
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def get_current_week_key(date_str: Optional[str] = None) -> str:
    """Return ISO calendar week string, e.g. '2026-W44'."""
    if date_str:
        dt = datetime.strptime(date_str, "%Y-%m-%d").date()
    else:
        ist_str = get_today_ist_date()
        dt = datetime.strptime(ist_str, "%Y-%m-%d").date()
    iso_year, iso_week, _ = dt.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


class DynamicTemplateEngine:
    """
    Manages persistent weekly outreach templates, history tracking,
    and controlled variation generation adhering strictly to the 10 reference standards.
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or DEFAULT_TEMPLATES_FILE
        self._data: Optional[Dict[str, Any]] = None
        self._load_storage()

    def _load_storage(self) -> None:
        """Load storage file if present; otherwise initialize default in-memory structure."""
        if self.storage_path and self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                return
            except Exception as e:
                logger.warning(f"Could not load templates from {self.storage_path}: {e}")

        # Initialize with the 10 Reference Templates
        ref_list = [REFERENCE_TEMPLATES[i] for i in sorted(REFERENCE_TEMPLATES.keys())]
        self._data = {
            "version": 1,
            "reference_templates": ref_list,
            "generated_weeks": {},
            "history": [],
        }

    def _save_storage(self) -> None:
        """Persist storage state to disk atomically."""
        if not self.storage_path:
            return
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.storage_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            os.replace(temp_path, self.storage_path)
        except Exception as e:
            logger.error(f"Failed to persist templates to {self.storage_path}: {e}")

    def get_reference_templates(self) -> List[Dict[str, Any]]:
        """Return all 10 canonical reference templates."""
        return [REFERENCE_TEMPLATES[i] for i in sorted(REFERENCE_TEMPLATES.keys())]

    def get_reference_template(self, template_id: int) -> Dict[str, Any]:
        """Return specific reference template by ID (1 to 10)."""
        if template_id not in REFERENCE_TEMPLATES:
            raise ValueError(f"Invalid reference template ID {template_id}. Available IDs: 1 to 10.")
        return REFERENCE_TEMPLATES[template_id]

    def get_history_hashes(self, lookback_weeks: int = 4) -> Tuple[Set[str], Set[str]]:
        """Retrieve recent subject and body hashes from history to avoid repetition."""
        history = self._data.get("history", []) if self._data else []
        recent = history[-lookback_weeks:] if len(history) >= lookback_weeks else history

        used_subjects = set()
        used_bodies = set()
        for entry in recent:
            used_subjects.update(entry.get("subject_hashes", []))
            used_bodies.update(entry.get("body_hashes", []))

        return used_subjects, used_bodies

    def generate_weekly_variations(
        self,
        week_key: str,
        batch_count: int = 9,
        lookback_weeks: int = 4,
    ) -> List[Dict[str, Any]]:
        """
        Generate batch_count (default 9) original, varied templates for the given week.
        Ensures each batch in the week has a distinct subject and distinct body.
        Prevents repetition against recent history (lookback_weeks).
        Validates all templates against strict writing rules.
        """
        hist_subj_hashes, hist_body_hashes = self.get_history_hashes(lookback_weeks=lookback_weeks)

        # Deterministic RNG keyed by week_key so runs within the same week are consistent
        rng = random.Random(f"outreach_template_seed_{week_key}")

        shuffled_openers = list(OPENERS)
        rng.shuffle(shuffled_openers)

        shuffled_props = list(CORE_PROPOSITIONS)
        rng.shuffle(shuffled_props)

        shuffled_ctas = list(CALLS_TO_ACTION)
        rng.shuffle(shuffled_ctas)

        shuffled_subjs = list(SUBJECT_POOL)
        rng.shuffle(shuffled_subjs)

        templates: List[Dict[str, Any]] = []
        week_subj_hashes: List[str] = []
        week_body_hashes: List[str] = []

        used_subjs_in_batch: Set[str] = set()
        used_bodies_in_batch: Set[str] = set()

        o_idx = 0
        p_idx = 0
        c_idx = 0
        s_idx = 0

        for batch_i in range(batch_count):
            # Select subject
            subj = None
            for _ in range(len(shuffled_subjs)):
                cand_subj = shuffled_subjs[s_idx % len(shuffled_subjs)]
                s_idx += 1
                sh_hash = compute_text_hash(cand_subj)
                if cand_subj not in used_subjs_in_batch and (sh_hash not in hist_subj_hashes or len(used_subjs_in_batch) == 0):
                    subj = cand_subj
                    break
            if not subj:
                subj = shuffled_subjs[batch_i % len(shuffled_subjs)]

            used_subjs_in_batch.add(subj)

            # Construct body from modular blocks
            body = None
            for _ in range(50):
                cand_opener = shuffled_openers[o_idx % len(shuffled_openers)]
                o_idx += 1
                cand_prop = shuffled_props[p_idx % len(shuffled_props)]
                p_idx += 1
                cand_cta = shuffled_ctas[c_idx % len(shuffled_ctas)]
                c_idx += 1

                cand_body = f"{cand_opener}\n\n{cand_prop}\n\n{cand_cta}\n\nAyush"
                b_hash = compute_text_hash(cand_body)

                is_valid, _ = validate_template_style(subj, cand_body)
                if is_valid and cand_body not in used_bodies_in_batch and b_hash not in hist_body_hashes:
                    body = cand_body
                    break

            if not body:
                # Fallback to reference template with index
                ref = REFERENCE_TEMPLATES[(batch_i % 10) + 1]
                body = ref["body"]

            used_bodies_in_batch.add(body)

            templates.append({
                "template_id": batch_i + 1,
                "batch_index": batch_i,
                "subject": subj,
                "body": body,
            })

            week_subj_hashes.append(compute_text_hash(subj))
            week_body_hashes.append(compute_text_hash(body))

        # Record into history
        if self._data is not None:
            if "history" not in self._data:
                self._data["history"] = []

            # Avoid duplicate week entry in history
            self._data["history"] = [h for h in self._data["history"] if h.get("week_key") != week_key]
            self._data["history"].append({
                "week_key": week_key,
                "subject_hashes": week_subj_hashes,
                "body_hashes": week_body_hashes,
            })

        return templates

    def get_templates_for_week(
        self,
        date_str: Optional[str] = None,
        batch_count: int = 9,
        force_refresh: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve or generate persistent templates for the active week.
        Guarantees that within the same week, templates remain identical and persistent across all runs.
        """
        week_key = get_current_week_key(date_str)

        if self._data is None:
            self._load_storage()

        assert self._data is not None
        gen_weeks = self._data.setdefault("generated_weeks", {})

        if not force_refresh and week_key in gen_weeks:
            entry = gen_weeks[week_key]
            return entry.get("templates", [])

        # Generate fresh weekly templates
        templates = self.generate_weekly_variations(week_key, batch_count=batch_count)

        gen_weeks[week_key] = {
            "week_key": week_key,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "templates": templates,
        }
        self._data["active_week"] = week_key

        self._save_storage()
        return templates

    def get_template_for_batch(
        self,
        batch_index: int,
        date_str: Optional[str] = None,
    ) -> Tuple[int, str]:
        """
        Get the persistent weekly template (ID and body) for batch index (0 to 8).
        """
        templates = self.get_templates_for_week(date_str)
        idx = batch_index % len(templates)
        tmpl = templates[idx]
        return tmpl["template_id"], tmpl["body"]

    def get_subject_for_batch(
        self,
        batch_index: int,
        date_str: Optional[str] = None,
    ) -> str:
        """
        Get the persistent weekly subject for batch index (0 to 8).
        """
        templates = self.get_templates_for_week(date_str)
        idx = batch_index % len(templates)
        return templates[idx]["subject"]
