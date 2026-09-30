"""Configuration settings and environment variable handling for Daily Lead Agent."""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load local .env if present (used for local development/testing)
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Directories
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", str(BASE_DIR / "output")))
LOGS_DIR = Path(os.getenv("LOGS_DIR", str(BASE_DIR / "logs")))

# Ensure directories exist
for directory in [DATA_DIR, OUTPUT_DIR, LOGS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# File Paths
MASTER_LEADS_FILE = DATA_DIR / "master_leads.csv"
PENDING_QUEUE_FILE = DATA_DIR / "pending_queue.csv"
USED_NICHES_FILE = DATA_DIR / "used_niches.csv"
DAILY_RUNS_FILE = DATA_DIR / "daily_runs.csv"

# Lead Generation Settings
DAILY_TARGET = int(os.getenv("DAILY_TARGET", "200"))
MAX_QUERIES_PER_BATCH = int(os.getenv("MAX_QUERIES_PER_BATCH", "10"))
MAX_PAGES_PER_QUERY = int(os.getenv("MAX_PAGES_PER_QUERY", "30"))
MAX_BATCHES_PER_RUN = int(os.getenv("MAX_BATCHES_PER_RUN", "5"))  # Safe guard against runaway loop

# Apify Actor Settings
APIFY_ACTOR_ID = os.getenv("APIFY_ACTOR_ID", "apify/google-search-scraper")
APIFY_API_TOKEN: Optional[str] = os.getenv("APIFY_API_TOKEN")

# Gmail SMTP Settings
GMAIL_USERNAME: Optional[str] = os.getenv("GMAIL_USERNAME")
GMAIL_APP_PASSWORD: Optional[str] = os.getenv("GMAIL_APP_PASSWORD")
DELIVERY_EMAIL: Optional[str] = os.getenv("DELIVERY_EMAIL") or GMAIL_USERNAME
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))

# Alert & Token Replacement Settings
GOOGLE_FORM_URL = os.getenv(
    "GOOGLE_FORM_URL",
    "https://forms.gle/YOUR_FORM_ID_HERE"
)

# Test and Debug Flags
DRY_RUN = os.getenv("DRY_RUN", "false").lower() in ("true", "1", "yes")
TEST_MODE = os.getenv("TEST_MODE", "false").lower() in ("true", "1", "yes")

# India Timezone offset (+05:30)
IST_TIMEZONE_OFFSET_HOURS = 5.5
