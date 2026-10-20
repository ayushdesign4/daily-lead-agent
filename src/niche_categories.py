"""
Creator Niche Category Taxonomy and Classification for Daily Lead Agent.

Organizes the single-word niche pool into practical YouTube creator domains:
- gaming: Gaming, Esports, Walkthroughs, Speedrunning, Franchises
- technology: Tech, Software, Hardware, AI, Gadgets, Infrastructure
- automotive: Cars, Superbikes, Motorsports, Detailing, Tuning, Mechanics
- fitness: Bodybuilding, Calisthenics, Athletics, Powerlifting, Yoga
- finance: Personal Finance, Investing, Crypto, Real Estate, Startups, Commerce
- science: Science, Education, Astronomy, History, Academics, Deep Research
- culinary: Cooking, Baking, Specialty Coffee, Cocktails, Gastronomy
- outdoors: Travel, Camping, Hiking, Wildlife, Bushcraft, Permaculture
- creative: Filmmaking, Video Editing, Photography, Digital Art, Animation, Music
- maker: Woodworking, Metalworking, DIY, Crafts, Restoration, Ceramics
- exploration: Curated Review, Culture, Lifestyle, Specialized Exploration Niches
"""

import re
from typing import Dict, List, Set, Optional


def normalize_niche(niche: str) -> str:
    """Normalize niche string before classification."""
    text = niche.strip().lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# Canonical creator categories in default round-robin rotation order
CREATOR_CATEGORIES = [
    "gaming",
    "technology",
    "automotive",
    "fitness",
    "finance",
    "science",
    "culinary",
    "outdoors",
    "creative",
    "maker",
    "exploration",
]

# Dedicated automotive domain words (isolated from general crafts)
AUTO_DOMAIN_WORDS: Set[str] = {
    "ackermann", "airdam", "alternator", "antiroll", "autocross", "barnfind", "bellhousing",
    "bobber", "buggy", "caferacer", "camber", "camshaft", "canards", "carburetor", "carburizing",
    "caster", "ceramiccoating", "chopper", "clutchplate", "coilovers", "crankshaft", "cyaniding",
    "dampers", "detailing", "differentials", "diffuser", "downpipe", "driveshaft", "drivetrain",
    "dyno", "dynamometer", "exhaust", "flashtune", "flywheel", "gasket", "header", "headers",
    "hotrod", "ignition", "injector", "intercooler", "manifold", "motocross", "muffler",
    "nitrous", "overbore", "piston", "pistons", "pushrod", "radiator", "ratrod", "reflash",
    "sidecar", "silencer", "spoiler", "superbike", "superbikes", "supercharger", "supercharged",
    "supermoto", "supercar", "supercars", "suspension", "tachometer", "throttle", "turbocharger",
    "turbocharged", "undercarriage", "valvetrain", "wastegate", "wheelbase", "widebody",
    "motorsport", "karting", "dragracing", "rally", "offroading", "diesel", "autobattler"
}

# Substring and root patterns that map terms to categories
CATEGORY_STEMS: Dict[str, List[str]] = {
    "gaming": ["game", "rpg", "fps", "speedrun", "esport", "playthrough", "walkthrough", "modding", "nuzlocke", "stealth", "platformer", "soulsborne"],
    "technology": ["tech", "soft", "code", "dev", "data", "cyber", "micro", "nano", "robot", "cloud", "server", "logic", "hack", "script", "byte", "pixel", "semiconductor", "processor"],
    "automotive": ["auto", "car", "motor", "bike", "turbo", "engine", "wheel", "race", "racing", "speed", "gear", "tire"],
    "fitness": ["fit", "lift", "press", "gym", "squat", "flex", "muscle", "train", "sprint", "run", "athle", "cardio", "physi", "pectoral", "deltoid", "biceps", "triceps"],
    "finance": ["invest", "trade", "stock", "coin", "fund", "wealth", "bank", "market", "profit", "fisc", "econ", "pay", "dividend", "equity", "valuation"],
    "science": ["scien", "physic", "chem", "bio", "astro", "space", "geo", "theo", "morph", "logy", "hist", "fossil", "cosmo", "relativ", "quantum"],
    "culinary": ["cook", "bake", "food", "chef", "roast", "grill", "brew", "caff", "wine", "dine", "gourmet", "spice", "bread", "pastry", "coffee", "espresso"],
    "outdoors": ["camp", "hike", "trek", "outdoor", "wild", "fish", "hunt", "trail", "river", "forest", "mountain", "climb", "safari", "glacier", "canyon"],
    "creative": ["art", "film", "photo", "music", "drum", "guitar", "paint", "draw", "sketch", "sound", "cinema", "design", "vivid", "vignette", "aperture", "palette"],
    "maker": ["craft", "wood", "metal", "smith", "forge", "sew", "knit", "weave", "weld", "tool", "print", "sculpt", "potter", "carve", "lathe", "ceramic"],
}


def _build_static_category_map() -> Dict[str, str]:
    """Build unified keyword-to-category dictionary from author vocabularies."""
    mapping: Dict[str, str] = {}

    def _register(terms, category):
        for t in terms:
            norm = normalize_niche(t)
            if norm and norm not in mapping:
                mapping[norm] = category

    try:
        import scripts.niche_expansion_vocab as v1
        import scripts.niche_expansion_vocab_2 as v2
        import scripts.niche_expansion_vocab_3 as v3
        import scripts.niche_expansion_vocab_5 as v5
        import scripts.niche_expansion_vocab_6 as v6
        import scripts.niche_expansion_vocab_7 as v7
        import scripts.niche_expansion_vocab_8 as v8
        import scripts.niche_expansion_subniches as nes

        # 1. Gaming
        _register(v1.GAMING_EXPANSION, "gaming")
        _register(v2.GAMING_RETRO_INDIE_EXPANSION, "gaming")
        _register(nes.GAMING_CORE_SUBNICHES, "gaming")

        # 2. Technology & Hardware
        _register(v1.TECH_COMPUTING_EXPANSION, "technology")
        _register(v1.SOFTWARE_DEV_EXPANSION, "technology")
        _register(v1.AI_DATA_SCIENCE_EXPANSION, "technology")
        _register(nes.TECH_HARDWARE_SUBNICHES, "technology")

        # 3. Automotive
        _register(v2.MOTORSPORTS_AVIATION_TRANSPORT, "automotive")
        for w in AUTO_DOMAIN_WORDS:
            _register([w], "automotive")

        # 4. Fitness & Athletics
        _register(v1.FITNESS_SPORTS_OUTDOORS_EXPANSION, "fitness")
        _register(nes.FITNESS_ATHLETICS_SUBNICHES, "fitness")

        # 5. Finance & Business
        _register(v1.FINANCE_INVESTING_CRYPTO_EXPANSION, "finance")
        _register(v1.BUSINESS_MARKETING_ECOMMERCE_EXPANSION, "finance")
        _register(v2.PRODUCTIVITY_CAREER_ENTREPRENEURSHIP, "finance")
        _register(v6.FINANCE_BUSINESS_SUBNICHES, "finance")

        # 6. Education, Science & History
        _register(v1.SCIENCE_NATURE_HISTORY_EXPANSION, "science")
        _register(v3.STEM_MEDICINE_ACADEMICS, "science")
        _register(v8.DOCS_HISTORY_SCIENCE_PETS_SUBNICHES, "science")
        # Study & learning tools accurately classified into science/education
        mapping["anki"] = "science"


        # 7. Food & Culinary
        _register(v1.FOOD_CULINARY_COFFEE_EXPANSION, "culinary")
        _register(v2.FOOD_DRINK_REGIONAL, "culinary")

        # 8. Travel & Outdoors
        _register(v3.OUTDOOR_ADVANCED_SPORTS, "outdoors")
        _register(v5.TRAVEL_OUTDOOR_SUBNICHES, "outdoors")
        _register(v2.PETS_ANIMALS_WILDLIFE, "outdoors")

        # 9. Creative Arts & Media
        _register(v1.ARTS_DESIGN_CRAFTS_EXPANSION, "creative")
        _register(v2.FILM_MEDIA_POP_CULTURE, "creative")
        _register(v2.MUSIC_GENRES_PRODUCTION, "creative")
        _register(v2.FASHION_STYLE_BEAUTY, "creative")
        _register(nes.CREATIVE_ARTS_SUBNICHES, "creative")

        # 10. Maker & Crafts
        _register(v2.HOME_DESIGN_INTERIOR_DIY, "maker")
        _register(v3.SKILLS_MAGIC_CRAFTSMANSHIP, "maker")
        _register(v3.COLLECTIBLES_HOBBIES, "maker")
        for t in v7.CRAFTS_MAKER_AUTO_SUBNICHES:
            norm = normalize_niche(t)
            if norm not in AUTO_DOMAIN_WORDS:
                _register([t], "maker")

    except Exception:
        # Fallback to local keyword rules if scripts are not in path
        pass

    return mapping


_STATIC_CATEGORY_MAP: Dict[str, str] = _build_static_category_map()


def classify_niche(niche: str) -> str:
    """
    Classify a normalized single-word niche into a canonical creator category.
    Returns category name string.
    """
    norm = normalize_niche(niche)

    # 1. Check automotive words first
    if norm in AUTO_DOMAIN_WORDS:
        return "automotive"

    # 2. Check static author map
    if norm in _STATIC_CATEGORY_MAP:
        return _STATIC_CATEGORY_MAP[norm]

    # 3. Check domain stems
    for cat, stems in CATEGORY_STEMS.items():
        for stem in stems:
            if stem in norm and len(stem) >= 4:
                return cat

    # 4. Default to controlled exploration category
    return "exploration"


def group_niches_by_category(niches: List[str]) -> Dict[str, List[str]]:
    """
    Group a list of niches into category buckets.
    Preserves list order within each category.
    """
    buckets: Dict[str, List[str]] = {cat: [] for cat in CREATOR_CATEGORIES}
    for n in niches:
        cat = classify_niche(n)
        buckets[cat].append(n)
    return buckets
