"""Niche management, normalization, deduplication, and Google query generation."""

import re
import logging
from typing import List, Tuple, Set, Dict, Optional
from src.state_manager import StateManager, get_today_ist_date

logger = logging.getLogger(__name__)

# Query Template specified in section 3 & 23 of the specification
QUERY_TEMPLATE = 'site:youtube.com "{niche}" "Business Inquiries" "gmail.com" India'

# Curated seed niches specifically tailored for high-volume YouTube thumbnail outreach
# Grouped into distinct categories to avoid semantic overlap within batches
SEED_NICHES = [
    # Personal Finance & Wealth
    "Personal Finance India",
    "Mutual Funds Guide",
    "Stock Market for Beginners",
    "Real Estate Investing India",
    "Crypto and Web3 India",
    "Income Tax Saving Tips",
    "Credit Cards & Cashback",
    "Early Retirement FIRE India",
    "Small Business Loans",
    "Gold and Commodity Trading",
    # Fitness & Health
    "Calisthenics Home Workout",
    "Bodybuilding Transformation",
    "Yoga & Meditation Practice",
    "Indian Diet and Nutrition",
    "Fat Loss Workout Routine",
    "Powerlifting & Strength Training",
    "Marathon & Running Training",
    "Gym Workout for Beginners",
    "Healthy Meal Prep India",
    "Post-Pregnancy Fitness",
    # Travel & Food
    "Solo Traveling in India",
    "Indian Street Food Tour",
    "Budget Backpacking Asia",
    "Luxury Hotel Reviews",
    "Mountain Trekking Himalayas",
    "Hidden Gems Travel India",
    "Village Cooking Channel",
    "Traditional Indian Recipes",
    "Food Vlogging Delhi Mumbai",
    "Highway Dhaba Food Exploration",
    # Technology & Gadgets
    "Smartphone Unboxing and Review",
    "Custom PC Building Guide",
    "Best Laptops for Students",
    "Artificial Intelligence Tools",
    "Home Automation Smart Devices",
    "Cyber Security Tips India",
    "Camera Gear for Beginners",
    "Budget Audio & Headphones",
    "Smartwatches & Wearables",
    "Tech Hacks and Shortcuts",
    # Coding & Development
    "Python Programming Tutorial",
    "Web Development MERN Stack",
    "Data Science and Machine Learning",
    "DevOps and Cloud Computing",
    "Flutter Mobile App Development",
    "Full Stack Developer Roadmap",
    "Leetcode DSA Solutions",
    "Cybersecurity Ethical Hacking",
    "Frontend UI UX Design",
    "Backend System Design",
    # Business, Career & Startups
    "Indian Startup Case Studies",
    "E-commerce Business Model",
    "Freelancing Tips India",
    "Digital Marketing Strategy",
    "Campus Placement Interview Prep",
    "MBA Career Guidance",
    "Resumes and Portfolio Building",
    "Sales and Negotiation Skills",
    "Export Import Business India",
    "Franchise Business Opportunities",
    # Productivity & Self-Improvement
    "Time Management Techniques",
    "Book Summaries in Hindi",
    "Daily Routine and Habits",
    "Public Speaking & Communication",
    "Focus and Deep Work",
    "Study Motivation for Students",
    "Mental Health & Wellness",
    "Speed Reading & Note Taking",
    "Overcoming Procrastination",
    "Journaling and Mindfulness",
    # Gaming & Esports
    "PC Gaming Benchmarks",
    "Battlegrounds Mobile India BGMI",
    "GTA 5 Roleplay Series",
    "Minecraft Survival Guide",
    "Valorant Strategy and Highlights",
    "Esports Tournament Coverage",
    "Mobile Gaming Live Stream",
    "Story Mode Games Walkthrough",
    "Gaming Setup Room Tour",
    "Indie Game Reviews",
    # Filmmaking, Photography & Design
    "Video Editing in Premiere Pro",
    "Cinematic Smartphone Filmmaking",
    "Portrait Photography Tips",
    "YouTube Studio Lighting Setup",
    "Photoshop Thumbnail Design Tutorial",
    "DaVinci Resolve Color Grading",
    "Audio Recording for Creators",
    "Drone Flying and Cinematography",
    "Motion Graphics After Effects",
    "Street Photography India",
    # Automotive & Mobility
    "Electric Vehicle Reviews India",
    "New Car Buying Guide",
    "Superbike Touring and Vlogs",
    "Car Detailing and Care",
    "Off-Road 4x4 Adventures",
    "Used Car Inspection Tips",
    "Automotive Tech and Engines",
    "Motorcycle Maintenance Guide",
    "Scooter and Commuter Bikes",
    "Commercial Trucks and Buses",
    # Education & Exam Preparation
    "UPSC Civil Services Preparation",
    "SSC CGL Exam Strategy",
    "Bank PO Exam Preparation",
    "NEET Biology Lectures",
    "IIT JEE Physics Preparation",
    "CAT Exam Quantitative Aptitude",
    "History & Geopolitics Analysis",
    "Current Affairs Analysis India",
    "English Speaking Spoken Course",
    "Science Experiments at Home",
    # Lifestyle, Hobbies & Culture
    "Men Fashion and Grooming",
    "Home Interior Decor Ideas",
    "Gardening and Urban Farming",
    "Sneakerhead Collection India",
    "Guitar Lessons for Beginners",
    "Magic Tricks and Mentalism",
    "Longform Interview Podcasts",
    "Board Games and Hobbies",
    "Carpentry and DIY Woodworking",
    "Pet Care and Dog Training",
]


def normalize_niche(niche: str) -> str:
    """
    Normalize niche string before comparison:
    - lowercase
    - trim spaces
    - collapse repeated whitespace
    - strip punctuation where practical
    Example: '  TECH   REVIEWS  ' -> 'tech reviews'
    """
    text = niche.strip().lower()
    # Replace punctuation (except alphanumeric and spaces) with spaces
    text = re.sub(r"[^\w\s]", " ", text)
    # Collapse multiple whitespaces
    text = re.sub(r"\s+", " ", text).strip()
    return text


def are_niches_semantically_too_close(niche1: str, niche2: str) -> bool:
    """
    Check if two niches have severe word overlap (e.g. 'Stock Market' vs 'Stock Market Trading')
    to avoid burning query slots on redundant creator pools.
    """
    tokens1 = set(normalize_niche(niche1).split())
    tokens2 = set(normalize_niche(niche2).split())

    # Stopwords that shouldn't inflate overlap
    stopwords = {"and", "in", "for", "the", "of", "india", "guide", "tips", "channel"}
    core1 = tokens1 - stopwords
    core2 = tokens2 - stopwords

    if not core1 or not core2:
        return False

    intersection = core1 & core2
    smaller_len = min(len(core1), len(core2))

    # If the smaller niche is almost a subset of the larger niche
    if len(intersection) >= smaller_len and smaller_len >= 2:
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
        Returns list of (niche_name, formatted_query).
        """
        used_set = self.get_used_normalized_niches()
        selected: List[str] = []

        # 1. Search through curated seed pool first
        for candidate in SEED_NICHES:
            if len(selected) >= count:
                break
            norm = normalize_niche(candidate)
            if norm in used_set:
                continue

            # Check semantic overlap against already selected niches in this batch
            if any(are_niches_semantically_too_close(candidate, s) for s in selected):
                continue

            selected.append(candidate)

        # 2. If seed pool is running low, dynamically generate fresh vertical variations
        if len(selected) < count:
            modifiers = [
                "Podcast", "Masterclass", "Case Studies", "Deep Dive",
                "Community", "Tips and Tricks", "Channel", "Interviews", "Insights"
            ]
            base_topics = [
                "Architecture", "Real Estate", "Fintech", "Health Tech", "SaaS Growth",
                "Anime Analysis", "Standup Comedy", "Music Production", "DJing",
                "Astronomy", "Philosophy", "Psychology", "Mythology", "Culinary Arts",
                "Table Tennis", "Badminton", "Cricket Analysis", "Chess Strategy"
            ]
            for topic in base_topics:
                if len(selected) >= count:
                    break
                for mod in modifiers:
                    if len(selected) >= count:
                        break
                    candidate = f"{topic} {mod} India"
                    norm = normalize_niche(candidate)
                    if norm not in used_set and not any(are_niches_semantically_too_close(candidate, s) for s in selected):
                        selected.append(candidate)

        result: List[Tuple[str, str]] = []
        for niche in selected:
            query = QUERY_TEMPLATE.format(niche=niche)
            result.append((niche, query))

        logger.info(f"Selected {len(result)} fresh niches for current batch")
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
