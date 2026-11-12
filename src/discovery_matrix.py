"""
Multi-Dork Discovery Matrix for Indian YouTube Creator Lead Generation.

Combines:
- Multiple high-yield YouTube Dorks (majority ~85%)
- Targeted YouTube-creator Instagram Dorks (~15%)
- Developed Indian market geographic rotation (Maharashtra, Delhi NCR, Karnataka, Gujarat, etc.)
- Refreshed 1-word and realistic 2-3 word creator niches
- Query fingerprint tracking to prevent repeated searches
- Persistent rotation state without touching master leads database
"""

import os
import re
import json
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Set, Optional, Any
from src.state_manager import atomic_write_json

logger = logging.getLogger(__name__)

DISCOVERY_STATE_FILE = Path("data/discovery_state.json")
QUERY_HISTORY_FILE = Path("data/query_history.json")

# ---------------------------------------------------------------------------
# 1. Dork Templates
# ---------------------------------------------------------------------------
# YouTube Dorks (Major share: ~85%)
YOUTUBE_DORKS = [
    # Channel Handle & Bio pages
    'site:youtube.com/@ "{niche}" ("gmail.com" OR "outlook.com") {location}',
    'site:youtube.com/@ ("collab" OR "sponsorship" OR "partnership") "{niche}" "gmail.com" {location}',
    'site:youtube.com/@ ("podcast" OR "interviews" OR "documentary") "{niche}" "gmail.com" {location}',
    'site:youtube.com/@ "{niche}" "business email" "gmail.com"',
    'site:youtube.com/@ "{niche}" "contact for business" "gmail.com"',
    
    # Creator Intent & Management
    'site:youtube.com ("creator" OR "influencer") "{niche}" ("contact" OR "business") "gmail.com" {location}',
    'site:youtube.com ("managed by" OR "business contact") "{niche}" "gmail.com" {location}',
    'site:youtube.com ("email for business" OR "contact for promotion") "{niche}" "gmail.com"',
    'site:youtube.com "{niche}" "For Business" "gmail.com" {location}',
    'site:youtube.com "{niche}" "Business Email" "gmail.com"',
    'site:youtube.com "{niche}" "Contact for business" "gmail.com"',
    'site:youtube.com "{niche}" "For collaborations" "gmail.com"',
    'site:youtube.com "{niche}" "Sponsorship" "gmail.com" {location}',
    'site:youtube.com "{niche}" "Collab" "gmail.com" {location}',
    'site:youtube.com "{niche}" "Contact me at" "gmail.com"',
    'site:youtube.com "{niche}" "Reach me at" "gmail.com"',
    'site:youtube.com "{niche}" "Work with me" "gmail.com"',
    'site:youtube.com "{niche}" "Paid promotion" "gmail.com"',
    'site:youtube.com "{niche}" "Management" "gmail.com" {location}',
]

# Instagram Dorks (Strictly targeting YouTube creators: ~15%)
# Every Dork must contain a YouTube indicator
INSTAGRAM_YOUTUBE_DORKS = [
    'site:instagram.com "youtube.com/@" "{niche}" ("business" OR "collab") "gmail.com"',
    'site:instagram.com ("youtuber" OR "youtube creator") "{niche}" ("business email" OR "collab") "gmail.com" {location}',
    'site:instagram.com ("subscribe on youtube" OR "my youtube channel") "{niche}" "gmail.com"',
]

# ---------------------------------------------------------------------------
# 2. Geographic Pool — Developed Indian Markets
# ---------------------------------------------------------------------------
# Prioritizing Hindi, Hinglish, Marathi, and English-speaking developed urban hubs
INDIAN_LOCATIONS = [
    # Maharashtra
    "Mumbai",
    "Pune",
    "Nagpur",
    # Delhi NCR
    "Delhi",
    "Noida",
    "Gurugram",
    # Karnataka (National tech/English hub)
    "Bengaluru",
    # Telangana (National creator hub)
    "Hyderabad",
    # Gujarat
    "Ahmedabad",
    "Surat",
    # Rajasthan
    "Jaipur",
    # West Bengal
    "Kolkata",
    # Punjab & Haryana
    "Chandigarh",
    "Ludhiana",
    # Madhya Pradesh
    "Indore",
    "Bhopal",
    # Uttar Pradesh (Developed hubs)
    "Lucknow",
    "Kanpur",
    # National / Broad Indian creator anchors
    "India",
    "Hindi",
    "Hinglish",
]

# ---------------------------------------------------------------------------
# 3. Niches Pool: Refreshed 1-word + Realistic 2-3 Word Creator Niches
# ---------------------------------------------------------------------------
REFRESHED_ONE_WORD_NICHES = [
    "tech", "gaming", "cricket", "finance", "fitness", "food", "travel",
    "education", "vlog", "comedy", "automobile", "gadgets", "realestate",
    "parenting", "filmmaking", "animation", "productivity", "fashion",
    "makeup", "coding", "motovlog", "podcast", "trading", "astronomy",
    "woodworking", "decor", "gardening", "cooking", "dance", "music",
    "freelance", "design", "business", "skincare", "nutrition", "robotics",
    "hardware", "cinematography", "storytelling", "standup", "interviews",
    "mindset", "history", "mythology", "aviation", "supercars", "pottery",
    "diy", "crafts", "calligraphy", "origami", "baking", "mixology",
    "calisthenics", "bodybuilding", "powerlifting", "marathon", "cycling",
    "badminton", "chess", "football", "sneakers", "streetwear", "thrift",
    "perfumes", "grooming", "hairstyles", "startups", "solopreneur",
]

REALISTIC_MULTI_WORD_NICHES = [
    # Technology & Software
    "tech unboxing hindi",
    "smartphone reviews india",
    "pc build guide hindi",
    "budget smartphone under 15000",
    "smart home automation india",
    "laptop review hindi",
    "ai tools review hindi",
    "software engineer vlog",
    "coding interview prep",
    "web development tutorial hindi",
    "python programming hindi",
    "cyber security tips hindi",
    "apple gadgets review",
    "gadgets under 500",
    
    # Gaming & Esports
    "bgmi gameplay highlights",
    "gta v roleplay hindi",
    "valorant gameplay india",
    "free fire montage hindi",
    "minecraft survival series hindi",
    "gaming pc setup india",
    "esports tournament highlights",
    "ps5 gameplay hindi",
    "mobile gaming streamer",
    "horror games gameplay hindi",

    # Finance, Investing & Business
    "stock market investing hindi",
    "business podcast hindi",
    "personal finance india",
    "mutual funds for beginners",
    "crypto trading hindi",
    "intraday trading strategy",
    "startup founder interview",
    "digital marketing agency",
    "dropshipping india guide",
    "online earning methods hindi",
    "freelancer journey india",
    "real estate investing india",
    "credit cards comparison india",
    "case study business hindi",

    # Vlogging, Lifestyle & Entertainment
    "daily vlog hindi",
    "family vlogger india",
    "village cooking channel",
    "delhi street food vlogger",
    "mumbai street food tour",
    "solo travel vlogger india",
    "budget travel guide hindi",
    "camping in himalayas",
    "couple vlog hindi",
    "college vlog india",
    "hostel life vlog",
    "hindi comedy sketches",
    "standup comedy hindi",
    "funny reaction video hindi",
    "unfiltered podcast hindi",
    "car review hindi",
    "superbike delivery india",
    "bike modification india",
    "motorcycle touring ladakh",
    "offroading 4x4 india",

    # Fitness, Health & Sports
    "cricket analysis podcast",
    "gym transformation workout",
    "home workout no equipment",
    "weight loss journey india",
    "healthy diet recipes hindi",
    "vegetarian muscle building",
    "yoga for beginners hindi",
    "calisthenics training india",
    "ipl match analysis",
    "cricket batting tips",

    # Fashion, Grooming & Beauty
    "meesho fashion haul",
    "street shopping haul delhi",
    "sarojini nagar haul",
    "mens grooming tips hindi",
    "budget styling guide men",
    "skincare routine india",
    "haircare tips hindi",
    "saree draping tutorial",
    "bridal makeup artist hindi",
    "budget perfumes for men",

    # Design, Creative & Education
    "graphic design tutorial hindi",
    "thumbnail design tutorial",
    "freelance video editing",
    "adobe premiere pro hindi",
    "photoshop manipulation tutorial",
    "blender 3d tutorial hindi",
    "drone filmmaking india",
    "camera gear review hindi",
    "wedding photography tips",
    "interior design tour india",
    "home decor makeover",
    "diy crafts easy hindi",
    "upsc preparation guide",
    "self improvement hindi",
    "book summary hindi",
    "historical events explained hindi",
    "science experiments hindi",
    "scary stories hindi",
]

# Combined clean niche pool
ALL_CURATED_NICHES = REFRESHED_ONE_WORD_NICHES + REALISTIC_MULTI_WORD_NICHES


def normalize_query_text(query: str) -> str:
    """Normalize query text for hash and fingerprinting."""
    return re.sub(r"\s+", " ", query.strip().lower())


def compute_query_hash(query: str) -> str:
    """Return SHA-256 fingerprint for a normalized query."""
    return hashlib.sha256(normalize_query_text(query).encode("utf-8")).hexdigest()[:16]


class DiscoveryMatrix:
    """
    Manages multi-dork search generation, rotation of niches, locations, and templates,
    and tracks query history to eliminate repetitive Google SERP searches.
    """

    def __init__(
        self,
        state_file: Path = DISCOVERY_STATE_FILE,
        history_file: Path = QUERY_HISTORY_FILE,
    ):
        self.state_file = Path(state_file)
        self.history_file = Path(history_file)
        self.state = self.load_state()
        self.history = self.load_history()

    def load_state(self) -> Dict[str, Any]:
        """Load persistent cursors for dorks, niches, and locations."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception as e:
                logger.warning(f"Could not load discovery state ({e}). Initializing defaults.")
        return {
            "dork_cursor": 0,
            "niche_cursor": 0,
            "location_cursor": 0,
            "batch_counter": 0,
        }

    def save_state(self) -> None:
        """Save rotation cursors atomically."""
        try:
            atomic_write_json(self.state_file, self.state)
        except Exception as e:
            logger.error(f"Failed to save discovery state: {e}")

    def load_history(self) -> Set[str]:
        """Load set of previously executed query fingerprints."""
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return set(data)
            except Exception as e:
                logger.warning(f"Could not load query history ({e}). Starting fresh set.")
        return set()

    def record_queries_as_used(self, queries: List[str]) -> None:
        """Record executed query fingerprints to prevent duplicate searches."""
        for q in queries:
            q_hash = compute_query_hash(q)
            self.history.add(q_hash)
        try:
            atomic_write_json(self.history_file, list(self.history))
        except Exception as e:
            logger.error(f"Failed to persist query history: {e}")

    def is_query_used(self, query: str) -> bool:
        """Check if query has been executed historically."""
        return compute_query_hash(query) in self.history

    def generate_batch_queries(
        self,
        count: int = 10,
        historical_used_niches: Optional[Set[str]] = None,
    ) -> List[Tuple[str, str]]:
        """
        Generate a batch of `count` unique search queries combining:
        - Diverse YouTube Dorks (majority: ~80-90%)
        - YouTube-focused Instagram Dorks (~10-20%)
        - Rotating Indian locations (Mumbai, Delhi, Pune, Bengaluru, etc.)
        - Refreshed 1-word & realistic 2-3 word niches
        
        Ensures:
        - No duplicate queries within batch
        - No previously executed queries (checked via query history)
        - High semantic diversity across every query
        Returns:
            List of (niche_display_name, formatted_query)
        """
        used_niches = historical_used_niches or set()
        selected_batch: List[Tuple[str, str]] = []
        batch_queries_seen: Set[str] = set()

        dork_cursor = self.state.get("dork_cursor", 0)
        niche_cursor = self.state.get("niche_cursor", 0)
        location_cursor = self.state.get("location_cursor", 0)
        batch_counter = self.state.get("batch_counter", 0) + 1

        total_niches = len(ALL_CURATED_NICHES)
        total_locations = len(INDIAN_LOCATIONS)
        total_yt_dorks = len(YOUTUBE_DORKS)
        total_ig_dorks = len(INSTAGRAM_YOUTUBE_DORKS)

        # Plan composition: In a batch of 10, use 8-9 YouTube Dorks and 1-2 Instagram YouTube Dorks
        ig_slots = {4, 9} if count >= 10 else {count - 1} if count >= 5 else set()

        attempts = 0
        max_attempts = total_niches * 5

        while len(selected_batch) < count and attempts < max_attempts:
            slot_idx = len(selected_batch)
            attempts += 1

            # 1. Pick template: Instagram if slot matches, else YouTube
            if slot_idx in ig_slots:
                template = INSTAGRAM_YOUTUBE_DORKS[dork_cursor % total_ig_dorks]
            else:
                template = YOUTUBE_DORKS[dork_cursor % total_yt_dorks]

            # 2. Pick niche
            niche = ALL_CURATED_NICHES[niche_cursor % total_niches]
            niche_norm = niche.strip().lower()

            # 3. Pick location
            location = INDIAN_LOCATIONS[location_cursor % total_locations]

            # Advance cursors for next selection
            dork_cursor += 1
            niche_cursor += 1
            location_cursor += 1

            # Format query string
            formatted_query = template.format(niche=niche, location=location)
            # Clean any double spaces or artifacts
            formatted_query = re.sub(r"\s+", " ", formatted_query).strip()

            norm_q = normalize_query_text(formatted_query)

            # Check intra-batch uniqueness and persistent history
            if norm_q in batch_queries_seen:
                continue
            if self.is_query_used(formatted_query):
                continue

            batch_queries_seen.add(norm_q)
            selected_batch.append((niche, formatted_query))

        # If strict history check prevented filling all slots, allow non-batch duplicates with altered location
        if len(selected_batch) < count:
            logger.warning(
                f"Discovery Matrix filled {len(selected_batch)}/{count} with strict unseen queries. "
                "Synthesizing additional permutations..."
            )
            for offset in range(count - len(selected_batch)):
                template = YOUTUBE_DORKS[(dork_cursor + offset) % total_yt_dorks]
                niche = ALL_CURATED_NICHES[(niche_cursor + offset * 3) % total_niches]
                loc = INDIAN_LOCATIONS[(location_cursor + offset * 2) % total_locations]
                query = re.sub(r"\s+", " ", template.format(niche=niche, location=loc)).strip()
                norm_q = normalize_query_text(query)
                if norm_q not in batch_queries_seen:
                    batch_queries_seen.add(norm_q)
                    selected_batch.append((niche, query))
                if len(selected_batch) >= count:
                    break

        # Update and save persistent state
        self.state["dork_cursor"] = dork_cursor % (total_yt_dorks * 10)
        self.state["niche_cursor"] = niche_cursor % total_niches
        self.state["location_cursor"] = location_cursor % total_locations
        self.state["batch_counter"] = batch_counter
        self.save_state()

        logger.info(
            f"Discovery Matrix generated {len(selected_batch)} diverse queries "
            f"(Batch #{batch_counter} | Cursors: dork={dork_cursor}, niche={niche_cursor}, loc={location_cursor})"
        )
        return selected_batch

    def format_query_for_niche(self, niche: str) -> str:
        """
        Format a single query for a given niche by rotating through YouTube (~85%) &
        Instagram (~15%) Dorks and developed Indian locations.
        """
        dork_cursor = self.state.get("dork_cursor", 0)
        location_cursor = self.state.get("location_cursor", 0)

        total_yt_dorks = len(YOUTUBE_DORKS)
        total_ig_dorks = len(INSTAGRAM_YOUTUBE_DORKS)
        total_locations = len(INDIAN_LOCATIONS)

        # ~85% YouTube Dorks, ~15% Instagram YouTube Dorks (1 out of every 7)
        if (dork_cursor % 7) == 6:
            template = INSTAGRAM_YOUTUBE_DORKS[(dork_cursor // 7) % total_ig_dorks]
        else:
            template = YOUTUBE_DORKS[dork_cursor % total_yt_dorks]

        location = INDIAN_LOCATIONS[location_cursor % total_locations]

        self.state["dork_cursor"] = (dork_cursor + 1) % (total_yt_dorks * 10)
        self.state["location_cursor"] = (location_cursor + 1) % total_locations
        self.save_state()

        query = template.format(niche=niche, location=location)
        return re.sub(r"\s+", " ", query).strip()
