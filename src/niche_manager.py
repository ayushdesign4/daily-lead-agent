"""Niche management, normalization, deduplication, and Google query generation."""

import re
import logging
from typing import List, Tuple, Set, Dict, Optional
from src.state_manager import StateManager, get_today_ist_date

logger = logging.getLogger(__name__)

# Query Template specified in section 3 & 23 of the specification
QUERY_TEMPLATE = 'site:youtube.com "{niche}" "Business Inquiries" "gmail.com" India'

# Curated single-word niches tailored for high-volume YouTube outreach.
# STRICT RULE: Every niche must be exactly ONE WORD.
SEED_NICHES = [
    # Mindset, Motivation & Personal Growth
    "mindset", "motivation", "discipline", "productivity", "habits", "focus", "success",
    "meditation", "stoicism", "resilience", "inspiration", "growth", "ambition", "journaling",
    "mindfulness", "confidence", "struggle", "purpose", "leadership", "wisdom", "solitude",
    "grit", "gratitude", "manifestation", "positivity", "selfcare", "clarity", "affirmations",
    # Fitness, Health & Nutrition
    "fitness", "bodybuilding", "calisthenics", "crossfit", "yoga", "pilates", "nutrition",
    "diet", "running", "marathon", "powerlifting", "cardio", "wellness", "flexibility",
    "mobility", "physique", "hypertrophy", "strength", "athletics", "stretching", "skincare",
    "dermatology", "ayurveda", "weightloss", "supplements", "posture", "longevity", "rehab",
    "gym", "workouts", "aerobics", "zumba", "kettlebell", "triathlon", "endurance",
    # Software, Coding & Computing
    "coding", "programming", "python", "javascript", "typescript", "react", "flutter",
    "golang", "rust", "devops", "linux", "cybersecurity", "hacking", "networking",
    "database", "backend", "frontend", "fullstack", "algorithms", "leetcode", "docker",
    "kubernetes", "microservices", "cloud", "automation", "solidity", "blockchain",
    "webdev", "sysadmin", "computers", "software", "technology", "debugging", "compilers",
    # AI, Machine Learning & Data Science
    "ai", "deeplearning", "machinelearning", "datascience", "analytics", "vision",
    "nlp", "chatgpt", "prompting", "agents", "neural", "bigdata", "statistics",
    "transformers", "generative", "robotics", "llms", "synthetics", "genai",
    # Business, Entrepreneurship & Careers
    "business", "entrepreneurship", "startups", "freelancing", "marketing", "sales",
    "copywriting", "branding", "ecommerce", "dropshipping", "consulting", "management",
    "interviews", "resumes", "negotiation", "advertising", "agency", "careers",
    "retention", "monetization", "outsourcing", "solopreneur", "b2b", "crowdfunding",
    # Finance, Wealth & Investing
    "finance", "wealth", "investing", "stocks", "trading", "crypto", "bitcoin",
    "ethereum", "forex", "budgeting", "banking", "accounting", "taxation", "dividends",
    "mutualfunds", "commodities", "gold", "cryptocurrency", "economics", "fintech",
    "venture", "arbitrage", "derivatives", "options", "equities", "pensions",
    # Gaming & Esports
    "gaming", "gameplay", "esports", "minecraft", "valorant", "bgmi", "pubg",
    "roblox", "fortnite", "gta", "streaming", "speedrun", "playthrough", "walkthrough",
    "retrogaming", "cosplay", "gamers", "playstation", "xbox", "nintendo", "anime", "manga",
    # Creative Arts, Media, Video & Audio
    "design", "illustration", "animation", "blender", "photoshop", "premiere",
    "filmmaking", "cinematography", "photography", "vlogging", "podcasts", "storytelling",
    "voiceover", "audio", "sound", "music", "singing", "guitar", "piano", "drumming",
    "beats", "djing", "rap", "production", "calligraphy", "origami", "woodworking",
    "pottery", "painting", "sketching", "sculpting", "crafts", "typography", "cinema",
    "lighting", "acting", "theater", "screenwriting", "directing", "broadcasting",
    # Travel, Food & Outdoor Living
    "travel", "backpacking", "hiking", "trekking", "camping", "biking", "food",
    "cooking", "baking", "recipes", "streetfood", "dining", "culinary", "restaurant",
    "pastry", "sourdough", "cocktails", "gardening", "aquascaping", "farming",
    "pets", "dogs", "cats", "aquarium", "homesteading", "survival", "bushcraft",
    "wildlife", "nature", "foraging", "hydroponics", "permaculture", "botany",
    # Sports & Athletics
    "cricket", "football", "badminton", "tennis", "swimming", "boxing", "mma",
    "wrestling", "karate", "taekwondo", "judo", "chess", "basketball", "volleyball",
    "tabletennis", "cycling", "skating", "sprinting", "archery", "golf", "motorsport",
    "climbing", "bouldering", "surfing", "diving", "kayaking", "rowing", "sailing",
    # Automotive & Mobility
    "cars", "supercars", "motorcycles", "superbikes", "automotive", "tuning",
    "offroading", "racing", "drifting", "evs", "restoration", "aviation", "planes", "drones",
    # Education, Sciences & Humanities
    "physics", "chemistry", "biology", "mathematics", "astronomy", "astrophysics",
    "history", "geopolitics", "geography", "philosophy", "psychology", "sociology",
    "literature", "linguistics", "grammar", "vocabulary", "science", "experiment",
    "neuroscience", "genetics", "biochemistry", "anthropology", "archaeology", "ecology",
    # Lifestyle, Entertainment & Culture
    "fashion", "styling", "grooming", "streetwear", "sneakers", "movies",
    "comedy", "standup", "magic", "illusion", "mentalism", "unboxing", "critique",
    "reviews", "lifestyle", "parenting", "relationships", "dating", "marriage",
    "minimalism", "interior", "architecture", "decor", "thrifting", "perfumes",
    "watches", "jewelry", "satire", "parody", "improv", "ventriloquism", "acrobatics",
    # Specialized Crafts & Hobbies
    "carpentry", "blacksmithing", "leathercraft", "barista", "coffee", "brewing",
    "fermentation", "metallurgy", "woodcraft", "sewing", "embroidery", "quilting",
    "weaving", "crochet", "ceramics", "glassblowing", "gemology", "macrame",
    "woodturning", "lapidary", "enameling", "pyrography", "quilling", "tatting",
    "bonsai", "beekeeping", "entomology", "mycology", "horticulture", "viticulture",
    "mixology", "gastronomy", "charcuterie", "chocolatier", "patisserie", "confectionery",
    "roasting", "grilling", "smoking", "sommelier", "cartography", "cryptography"
]


def is_valid_one_word_niche(niche: str) -> bool:
    """Validate that niche string contains strictly one single word."""
    if not niche or not isinstance(niche, str):
        return False
    stripped = niche.strip()
    if not stripped or len(stripped.split()) != 1:
        return False
    return bool(re.match(r"^[A-Za-z0-9_-]+$", stripped))


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
    """Manages niche pool, checks against used niches, and constructs search queries."""

    def __init__(self, state_manager: Optional[StateManager] = None):
        self.state_manager = state_manager or StateManager()

    def get_used_normalized_niches(self) -> Set[str]:
        """Return a set of all normalized niches already used historically."""
        used_rows = self.state_manager.load_used_niches()
        return {normalize_niche(row["niche"]) for row in used_rows if row.get("niche")}

    def select_batch_niches(self, count: int = 10) -> List[Tuple[str, str]]:
        """
        Select up to `count` fresh, unused niches that do not overlap with
        each other or historically used niches.
        EVERY SELECTED NICHE IS STRICTLY ONE WORD.
        Returns list of (niche_name, formatted_query).
        """
        used_set = self.get_used_normalized_niches()
        selected: List[str] = []

        # 1. Search through curated single-word seed pool first
        for candidate in SEED_NICHES:
            if len(selected) >= count:
                break
            if not is_valid_one_word_niche(candidate):
                continue

            norm = normalize_niche(candidate)
            if norm in used_set:
                continue

            # Check semantic overlap against already selected niches in this batch
            if any(are_niches_semantically_too_close(candidate, s) for s in selected):
                continue

            selected.append(candidate)

        # 2. If curated pool is exhausted or running low, dynamically generate fresh single-word niches
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
                    if norm not in used_set and not any(are_niches_semantically_too_close(candidate, s) for s in selected):
                        selected.append(candidate)

        # 3. Dynamic Infinite Fallback: Single-word creator vertical generator
        if len(selected) < count:
            disciplines = [
                "creator", "vlogger", "streamer", "coder", "gamer", "builder",
                "hustler", "trader", "maker", "stylist", "coach", "tutor"
            ]
            counter = 1
            while len(selected) < count and counter < 1000:
                for disc in disciplines:
                    if len(selected) >= count:
                        break
                    candidate = f"{disc}{counter}"
                    norm = normalize_niche(candidate)
                    if norm not in used_set and not any(are_niches_semantically_too_close(candidate, s) for s in selected):
                        selected.append(candidate)
                counter += 1

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
        Persist the used niches into used_niches.csv.
        """
        if not date_str:
            date_str = get_today_ist_date()

        rows = [
            {"niche": niche, "date_used": date_str, "query_text": query}
            for niche, query in batch_niches
        ]
        self.state_manager.record_used_niches(rows)
