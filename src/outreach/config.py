"""Configuration settings for verified outreach pipeline."""

import os
import re
from pathlib import Path
from typing import Optional
from src.config import BASE_DIR, DATA_DIR, OUTPUT_DIR, LOGS_DIR, GMAIL_USERNAME, GMAIL_APP_PASSWORD, DELIVERY_EMAIL, DRY_RUN

# Outreach specific paths
OUTREACH_STATE_FILE = DATA_DIR / "outreach_state.csv"
OUTREACH_BATCHES_FILE = DATA_DIR / "outreach_batches.csv"
OUTREACH_SUPPRESSIONS_FILE = DATA_DIR / "outreach_suppressions.csv"
VERIFICATION_LEDGER_FILE = DATA_DIR / "verification_ledger.csv"
VERIFICATION_CACHE_FILE = DATA_DIR / "verification_cache.csv"

# Verifier API keys
QEV_API_KEY_1: Optional[str] = os.getenv("QEV_API_KEY_1")
QEV_API_KEY_2: Optional[str] = os.getenv("QEV_API_KEY_2")
QEV_API_BASE_URL: str = os.getenv("QEV_API_BASE_URL", "https://api.quickemailverification.com/v1/verify")
MAX_VERIFICATIONS_PER_ACCOUNT_PER_DAY: int = int(os.getenv("MAX_VERIFICATIONS_PER_ACCOUNT_PER_DAY", "100"))

# Sender accounts JSON string (array of 9 objects with email & app_password)
OUTREACH_ACCOUNTS_JSON: Optional[str] = os.getenv("OUTREACH_ACCOUNTS_JSON")

# Recipient 'To' address as mandated by rule 8
OUTREACH_TO_EMAIL: str = os.getenv("OUTREACH_TO_EMAIL", "ayush@ayushdesign.site")

# Detection settings
LEAD_DELIVERY_FROM: Optional[str] = os.getenv("LEAD_DELIVERY_FROM") or GMAIL_USERNAME
LEAD_EMAIL_SUBJECT_PATTERN: str = os.getenv("LEAD_EMAIL_SUBJECT_PATTERN", r"^Daily New Leads — (\d{4}-\d{2}-\d{2})")

# Notification destination
NOTIFICATION_RECIPIENT: str = os.getenv("OUTREACH_NOTIFICATION_EMAIL") or DELIVERY_EMAIL or GMAIL_USERNAME or OUTREACH_TO_EMAIL
