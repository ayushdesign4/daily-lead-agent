"""Niche management, normalization, deduplication, and Google query generation."""

import re
import logging
from typing import List, Tuple, Set, Dict, Optional
from src.state_manager import StateManager, get_today_ist_date

logger = logging.getLogger(__name__)

from src.curated_niches import CURATED_NICHES, NICHE_CATEGORIES
from src.niche_categories import CREATOR_CATEGORIES, classify_niche

# Query Template specified in section 3 & 23 of the specification
QUERY_TEMPLATE = 'site:youtube.com "{niche}" "Business Inquiries" "gmail.com" India'

# Curated single-word niches tailored for high-volume YouTube outreach.
# STRICT RULE: Every niche must be exactly ONE WORD with no digits.
SEED_NICHES = CURATED_NICHES



# Disallowed artificial compound suffixes that indicate glued-together multi-word phrases
DISALLOWED_MASHUP_SUFFIXES = (
    "photography", "videography", "cinematography", "review", "reviews",
    "tutorial", "tutorials", "tips", "hacks", "secrets", "tricks", "routine",
    "routines", "workout", "workouts", "vlog", "vlogs", "channel", "channels",
    "guide", "guides", "making", "hunting", "training",
    "learning", "decor", "makeover", "restoration", "cleaning",
    "cooking", "baking", "brewing", "farming", "gardening", "investing", "trading",
    "marketing", "branding", "strategy", "management", "remodel",
    "renovation", "installation", "collector", "collecting", "recording",
    "production", "engineering", "development", "programming", "exploration",
    "analysis", "breakdown", "theory", "theories", "documentary", "life"
)

# Established single words / domain terms that are legitimate despite suffix matches
ESTABLISHED_LEXICAL_COMPOUNDS = {
    "wildlife", "afterlife", "nightlife", "midlife", "halflife",
    "woodworking", "woodturning", "woodcarving", "metalworking", "blacksmithing",
    "bladesmith", "silversmith", "goldsmith", "metalsmith", "locksmith",
    "supercharger", "turbocharger", "intercooler", "overclocking", "undervolting",
    "watercooling", "hypertrophy", "bodybuilding", "powerlifting", "calisthenics",
    "speedrunning", "speedrunner", "simracing", "overlanding", "bikepacking",
    "astrophotography", "videography", "cinematography", "photography",
    "typography", "calligraphy", "cartography", "topography", "lithography",
    "paleontology", "archaeology", "anthropology", "geopolitics", "mixology",
    "homesteading", "permaculture", "aquascaping", "beekeeping", "antkeeping",
    "formicarium", "terrarium", "paludarium", "vivarium", "herpetoculture",
    "microcontroller", "semiconductor", "microbiology", "neuroscience",
    "psychology", "sociology", "linguistics", "philosophy", "theology",
    "mythology", "folklore", "cryptids", "creepypasta", "icebergs",
    "supernova", "supermassive", "exoplanet", "telescope", "microscope",
    "spectroscopy", "thermodynamics", "electromagnetism", "superconductivity",
    "nanotechnology", "quantum", "patisserie", "chocolatier", "charcuterie",
    "prosciutto", "fermentation", "sourdough", "croissant", "viennoiserie",
    "espresso", "aeropress", "pourover", "latteart", "chemex", "frenchpress",
    "smartwatch", "smartphone", "earbuds", "headphones", "audiophile",
    "motherboard", "chipset", "processor", "keycaps", "hotswap",
    "backpacking", "bushcraft", "spearfishing", "packrafting", "canyoneering",
    "spelunking", "geocaching", "foraging", "mushrooming", "birdwatching",
    "liveaboard", "survivalism", "glamping", "orienteering", "mountaineering",
    "bouldering", "flyfishing", "flytying", "ceramiccoating", "pinstriping",
    "upholstery", "autocross", "drivetrain", "valvetrain", "driveshaft",
    "camshaft", "crankshaft", "coilovers", "differential", "supermoto",
    "motocross", "supercross", "dirtbike", "caferacer", "sidecar",
    "fingerstyle", "audiomixing", "sounddesign", "storyboarding", "rotoscoping",
    "photogrammetry", "fingerdrumming", "orchestration", "synthesizer",
    "pedalboard", "drummachine", "slapbass", "keyboardist", "saxophonist",
    "trumpeter", "trombonist", "clarinetist", "accordion", "harmonica",
    "printmaking", "screenprinting", "bookbinding", "leathercraft",
    "cabinetmaking", "diorama", "miniatures", "airbrushing"
}


def is_valid_one_word_niche(niche: str) -> bool:
    """
    Validate that niche string contains strictly one single word and no digits,
    punctuation, or artificial multi-word compound mashups.
    """
    if not niche or not isinstance(niche, str):
        return False
    stripped = niche.strip()
    if not stripped or len(stripped.split()) != 1:
        return False
    # Strictly alphabetic letters only: NO hyphens, NO underscores, NO digits, NO spaces
    if not re.match(r"^[A-Za-z]+$", stripped):
        return False

    lower = stripped.lower()
    # Reject artificial compound mashups (e.g. weddingphotography, bathroomremodel)
    if lower not in ESTABLISHED_LEXICAL_COMPOUNDS:
        for s in DISALLOWED_MASHUP_SUFFIXES:
            if lower.endswith(s) and len(lower) > len(s) + 2:
                return False

    return True


def normalize_niche(niche: str) -> str:
    """
    Normalize niche string before comparison:
    - lowercase
    - trim spaces
    - collapse repeated whitespace
    - strip punctuation where practical
    Example: '  MOTIVATION  ' -> 'motivation'
    """
    text = niche.strip().lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def are_niches_semantically_too_close(niche1: str, niche2: str) -> bool:
    """
    Check if two niches have severe overlap (e.g. 'coding' vs 'code',
    'investing' vs 'invest', or legacy multi-word overlap)
    to avoid burning query slots on redundant creator pools.
    """
    n1 = normalize_niche(niche1)
    n2 = normalize_niche(niche2)
    if not n1 or not n2:
        return False
    if n1 == n2:
        return True

    # Multi-word token overlap check (for historical / multi-word niches)
    tokens1 = set(n1.split())
    tokens2 = set(n2.split())
    stopwords = {"and", "in", "for", "the", "of", "india", "guide", "tips", "channel"}
    core1 = tokens1 - stopwords
    core2 = tokens2 - stopwords
    if core1 and core2:
        intersection = core1 & core2
        smaller_len = min(len(core1), len(core2))
        if len(intersection) >= smaller_len and smaller_len >= 2:
            return True

    # Single-word stem/prefix overlap check
    shorter, longer = (n1, n2) if len(n1) <= len(n2) else (n2, n1)
    if len(shorter) >= 4 and longer.startswith(shorter[:4]):
        return True

    stem1 = re.sub(r"(ing|ers|er|s|ed|e)$", "", n1)
    stem2 = re.sub(r"(ing|ers|er|s|ed|e)$", "", n2)
    if len(stem1) >= 3 and stem1 == stem2:
        return True

    return False


class NicheManager:
    """
    Manages niche pool, category-based round-robin selection, persistent cursors,
    adaptive yield feedback, and query generation.
    """

    def __init__(self, state_manager: Optional[StateManager] = None):
        self.state_manager = state_manager or StateManager()

    def get_used_normalized_niches(self) -> Set[str]:
        """Return a set of all normalized niches already used historically."""
        used_rows = self.state_manager.load_used_niches()
        return {normalize_niche(row["niche"]) for row in used_rows if row.get("niche")}

    def load_selection_state(self) -> Dict:
        """Load persistent category cursors and staged niche state."""
        return self.state_manager.load_niche_selection_state()

    def save_selection_state(self, state: Dict) -> None:
        """Persist category cursors and staged niche state."""
        self.state_manager.save_niche_selection_state(state)

    def load_performance_state(self) -> Dict:
        """Load persistent performance feedback metrics."""
        return self.state_manager.load_niche_performance()

    def save_performance_state(self, perf: Dict) -> None:
        """Persist performance feedback metrics."""
        self.state_manager.save_niche_performance(perf)

    def get_category_priority_order(self) -> List[str]:
        """
        Rank categories balancing 70% exploitation (proven high fresh-lead yield)
        and 30% exploration (under-tested or rotating categories).
        Uses confidence-aware empirical Bayes shrinkage: score = (new_leads + 10.0) / (raw + 20.0).
        """
        perf = self.load_performance_state()
        cat_stats = perf.get("categories", {})
        selection_state = self.load_selection_state()
        rotation_offset = selection_state.get("category_rotation_offset", 0)

        # Calculate confidence-aware smoothed yield score for each creator category
        scored_cats: List[Tuple[str, float, int]] = []
        for cat in CREATOR_CATEGORIES:
            stats = cat_stats.get(cat, {})
            batches = stats.get("batches", 0)
            raw = max(0, stats.get("raw_emails", 0))
            new_leads = max(0, min(stats.get("new_leads", 0), raw if raw > 0 else stats.get("new_leads", 0)))
            # Prior weight M=20, prior mean p0=0.5: (new + 10) / (raw + 20)
            score = (new_leads + 10.0) / (raw + 20.0)
            scored_cats.append((cat, score, batches))

        # Sort proven categories by yield score descending
        # Break ties by number of batches or canonical rotation order
        scored_cats.sort(key=lambda x: (x[1], x[2]), reverse=True)
        ranked_categories = [x[0] for x in scored_cats]

        # 70% exploitation (top performers), 30% exploration (remaining/under-tested)
        total_cats = len(CREATOR_CATEGORIES)
        exploit_count = max(1, int(round(total_cats * 0.7)))  # 8 out of 11
        exploit_cats = ranked_categories[:exploit_count]
        explore_cats = ranked_categories[exploit_count:]

        # Rotate BOTH exploitation and exploration categories across consecutive batches
        # to ensure fair slot distribution and prevent any category (e.g. outdoors) from starving outside the 10-slot window
        if exploit_cats:
            rot_e = rotation_offset % len(exploit_cats)
            exploit_cats = exploit_cats[rot_e:] + exploit_cats[:rot_e]

        if explore_cats:
            rot_x = rotation_offset % len(explore_cats)
            explore_cats = explore_cats[rot_x:] + explore_cats[:rot_x]

        # Interleave exploitation and exploration to distribute diverse domains
        ordered: List[str] = []
        e_idx = 0
        x_idx = 0
        while e_idx < len(exploit_cats) or x_idx < len(explore_cats):
            # Take up to 2 exploit, then 1 explore
            for _ in range(2):
                if e_idx < len(exploit_cats):
                    ordered.append(exploit_cats[e_idx])
                    e_idx += 1
            if x_idx < len(explore_cats):
                ordered.append(explore_cats[x_idx])
                x_idx += 1

        return ordered

    def select_batch_niches(self, count: int = 10) -> List[Tuple[str, str]]:
        """
        Select up to `count` fresh, unused niches that do not overlap with
        each other or historically used niches.
        Uses category-based round-robin with persistent cursors, preventing
        alphabetical clustering while ensuring diverse domain representation.
        EVERY SELECTED NICHE IS STRICTLY ONE WORD.
        Returns list of (niche_name, formatted_query).
        """
        used_set = self.get_used_normalized_niches()
        selected: List[str] = []
        selected_norms: Set[str] = set()

        selection_state = self.load_selection_state()
        category_cursors: Dict[str, int] = selection_state.get("category_cursors", {})

        # Check for interrupted batch: if last_staged_niches exist and were NOT recorded into used_niches.csv
        last_staged = selection_state.get("last_staged_niches", [])
        if last_staged:
            unrecorded_staged = [
                n for n in last_staged
                if is_valid_one_word_niche(n)
                and normalize_niche(n) not in used_set
                and not any(are_niches_semantically_too_close(n, s) for s in selected)
            ]
            for n in unrecorded_staged:
                if len(selected) >= count:
                    break
                selected.append(n)
                selected_norms.add(normalize_niche(n))

        if len(selected) < count:
            category_order = self.get_category_priority_order()

            # Pass 1: Select 1 niche from each category in prioritized round-robin order
            for cat in category_order:
                if len(selected) >= count:
                    break
                cat_niches = NICHE_CATEGORIES.get(cat, [])
                cursor = category_cursors.get(cat, 0)
                n_len = len(cat_niches)
                if n_len == 0:
                    continue

                # Search starting from cursor position
                found = False
                for step in range(n_len):
                    idx = (cursor + step) % n_len
                    candidate = cat_niches[idx]
                    if not is_valid_one_word_niche(candidate):
                        continue
                    norm = normalize_niche(candidate)
                    if norm in used_set or norm in selected_norms:
                        continue
                    if any(are_niches_semantically_too_close(candidate, s) for s in selected):
                        continue

                    # Valid, unused, non-overlapping candidate found
                    selected.append(candidate)
                    selected_norms.add(norm)
                    category_cursors[cat] = (idx + 1) % n_len
                    found = True
                    break

            # Pass 2: If count not satisfied (e.g. some categories exhausted), fill remaining slots
            # round-robin across categories that still have available niches
            if len(selected) < count:
                passes_left = count - len(selected)
                for _ in range(passes_left):
                    if len(selected) >= count:
                        break
                    picked_in_cycle = False
                    for cat in category_order:
                        if len(selected) >= count:
                            break
                        cat_niches = NICHE_CATEGORIES.get(cat, [])
                        cursor = category_cursors.get(cat, 0)
                        n_len = len(cat_niches)
                        if n_len == 0:
                            continue

                        for step in range(n_len):
                            idx = (cursor + step) % n_len
                            candidate = cat_niches[idx]
                            if not is_valid_one_word_niche(candidate):
                                continue
                            norm = normalize_niche(candidate)
                            if norm in used_set or norm in selected_norms:
                                continue
                            if any(are_niches_semantically_too_close(candidate, s) for s in selected):
                                continue

                            selected.append(candidate)
                            selected_norms.add(norm)
                            category_cursors[cat] = (idx + 1) % n_len
                            picked_in_cycle = True
                            break
                    if not picked_in_cycle:
                        # Curated categories have no more available niches
                        break

        # Pass 3: Check flat SEED_NICHES for any unassigned candidate before synthetic fallbacks
        if len(selected) < count:
            for candidate in SEED_NICHES:
                if len(selected) >= count:
                    break
                if not is_valid_one_word_niche(candidate):
                    continue
                norm = normalize_niche(candidate)
                if norm in used_set or norm in selected_norms:
                    continue
                if any(are_niches_semantically_too_close(candidate, s) for s in selected):
                    continue
                selected.append(candidate)
                selected_norms.add(norm)

        # Pass 4: Dynamic generation fallback for backward compatibility when ALL curated seeds are used
        if len(selected) < count:
            prefixes = [
                "micro", "macro", "neuro", "cyber", "bio", "astro", "crypto",
                "retro", "hyper", "meta", "techno", "eco", "omni", "ultra", "pro"
            ]
            stems = [
                "tech", "finance", "fitness", "coding", "gaming", "design", "media",
                "science", "art", "craft", "music", "health", "space", "sports",
                "logic", "trade", "robotics", "optics", "analytics", "motion",
                "vlog", "audio", "cinema", "growth", "skills", "market"
            ]

            for prefix in prefixes:
                if len(selected) >= count:
                    break
                for stem in stems:
                    if len(selected) >= count:
                        break
                    candidate = f"{prefix}{stem}"
                    if not is_valid_one_word_niche(candidate):
                        continue
                    norm = normalize_niche(candidate)
                    if norm not in used_set and norm not in selected_norms and not any(are_niches_semantically_too_close(candidate, s) for s in selected):
                        selected.append(candidate)
                        selected_norms.add(norm)

        # Check clean exhaustion: NEVER output numbered tokens like creator1, vlogger101
        if len(selected) < count:
            if not selected:
                logger.warning("Niche pool exhausted! No fresh, unused niches available.")
            else:
                logger.warning(
                    f"Niche pool near exhaustion: requested {count} niches, but only {len(selected)} fresh niches available."
                )

        # Stage selected niches and advance rotation offset in state
        selection_state["category_cursors"] = category_cursors
        selection_state["last_staged_niches"] = selected
        selection_state["category_rotation_offset"] = selection_state.get("category_rotation_offset", 0) + 1
        self.save_selection_state(selection_state)

        result: List[Tuple[str, str]] = []
        for niche in selected:
            # Enforce strict single-word rule
            assert is_valid_one_word_niche(niche), f"Niche '{niche}' must be exactly one word"
            query = QUERY_TEMPLATE.format(niche=niche)
            result.append((niche, query))

        logger.info(f"Selected {len(result)} fresh one-word niches for current batch")
        return result

    def record_batch_as_used(self, batch_niches: List[Tuple[str, str]], date_str: Optional[str] = None) -> None:
        """
        Persist the used niches into used_niches.csv and clear last_staged_niches from state.
        """
        if not date_str:
            date_str = get_today_ist_date()

        rows = [
            {"niche": niche, "date_used": date_str, "query_text": query}
            for niche, query in batch_niches
        ]
        self.state_manager.record_used_niches(rows)

        # Clear staged niches in state since they are now permanently recorded
        selection_state = self.load_selection_state()
        if "last_staged_niches" in selection_state:
            selection_state["last_staged_niches"] = []
            self.save_selection_state(selection_state)

    def record_batch_performance(
        self,
        batch_niches: List[Tuple[str, str]],
        raw_count: int = 0,
        intra_dups: int = 0,
        master_dups: int = 0,
        new_count: int = 0,
        date_str: Optional[str] = None,
        status: str = "COMPLETED",
        error_type: Optional[str] = None,
    ) -> None:
        """
        Record search yield metrics per category to drive adaptive performance feedback.
        Technical failures (e.g. Apify timeout) increment failure counts but do NOT
        decrease yield scores.
        """
        if not batch_niches:
            return

        if not date_str:
            date_str = get_today_ist_date()

        perf = self.load_performance_state()
        cat_stats = perf.setdefault("categories", {})
        history = perf.setdefault("history", [])

        # Identify categories represented in this batch
        represented_cats: Set[str] = {classify_niche(niche) for niche, _ in batch_niches}
        num_cats = max(1, len(represented_cats))

        # Bounds guard: prevent negative counts or physically impossible ratios
        raw_count = max(0, int(raw_count))
        intra_dups = max(0, int(intra_dups))
        master_dups = max(0, int(master_dups))
        new_count = max(0, min(int(new_count), raw_count))

        # Distribute metrics across represented categories
        raw_per_cat = raw_count // num_cats
        intra_per_cat = intra_dups // num_cats
        master_per_cat = master_dups // num_cats
        new_per_cat = new_count // num_cats

        for cat in represented_cats:
            entry = cat_stats.setdefault(cat, {
                "batches": 0,
                "raw_emails": 0,
                "intra_duplicates": 0,
                "master_duplicates": 0,
                "new_leads": 0,
                "failures": 0,
                "yield_score": 0.5,
                "last_used_date": date_str,
            })

            entry["last_used_date"] = date_str

            if status == "FAILED":
                entry["failures"] = entry.get("failures", 0) + 1
                # Note: Technical failures do NOT decrement or recalculate yield_score
            else:
                entry["batches"] = entry.get("batches", 0) + 1
                entry["raw_emails"] = entry.get("raw_emails", 0) + raw_per_cat
                entry["intra_duplicates"] = entry.get("intra_duplicates", 0) + intra_per_cat
                entry["master_duplicates"] = entry.get("master_duplicates", 0) + master_per_cat
                entry["new_leads"] = entry.get("new_leads", 0) + new_per_cat

                # Update confidence-aware smoothed yield score (M=20, p0=0.5)
                entry["yield_score"] = round(
                    (entry["new_leads"] + 10.0) / (entry["raw_emails"] + 20.0),
                    4
                )

        # Log history item
        history.append({
            "date": date_str,
            "niches": [n for n, _ in batch_niches],
            "categories": list(represented_cats),
            "raw_emails": raw_count,
            "intra_duplicates": intra_dups,
            "master_duplicates": master_dups,
            "new_leads": new_count,
            "status": status,
            "error_type": error_type,
        })

        # Cap history to last 100 runs
        if len(history) > 100:
            perf["history"] = history[-100:]

        self.save_performance_state(perf)
        logger.info(
            f"Recorded performance for {len(represented_cats)} categories | Status: {status} | "
            f"New Leads: {new_count}/{raw_count}"
        )
