"""Secure, isolated Mail7 verification runner for 35-email sample.
Strict budget: exactly 35 credits.
Runs in GitHub Actions using MAIL7_API_KEY_1 secret.
"""

import os
import sys
import json
import logging
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.outreach.verification_client import Mail7Verifier
from src.outreach.quota_ledger import QuotaLedger
from src.outreach.mail7_pool import Mail7AccountPool

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Mail7SampleTest")

# Exact 35-email candidate sample
SAMPLE_EMAILS = [
    # 19 emails extracted directly from live Bright Data SERP creator searches
    "sikanderxbixu@gmail.com",
    "photoeditorappss@gmail.com",
    "nb.studio.inc@gmail.com",
    "ahmadnasser.aff@gmail.com",
    "cryptp.kd711@gmail.com",
    "thehemantparmar@gmail.com",
    "gakkharcottonhosriepvtltd@gmail.com",
    "simonfpvbookings@gmail.com",
    "moettorres99@gmail.com",
    "spencerphotography6@gmail.com",
    "lucasbluevids@gmail.com",
    "home.solution.remodeling@gmail.com",
    "moreflex@gmail.com",
    "ccircle24@gmail.com",
    "devilpro2456@gmail.com",
    "raphaeditor52@gmail.com",
    "pmcgalaxy369@gmail.com",
    "mayamdesigns.business@gmail.com",
    "contact@gmail.com",
    # 16 emails from YouTube creator pool including repaired domain suffix leads
    "poulomibhakta@gmail.com",
    "mdajaj2662@gmail.com",
    "guitarcodylessons@gmail.com",
    "azhari.mifarizal@gmail.com",
    "pitabowlnc@gmail.com",
    "pitagrills@gmail.com",
    "techiebaghela@gmail.com",
    "yaxpatel500@gmail.com",
    "chamkomarketing@gmail.com",
    "solutionprtech@gmail.com",
    "dr.shubhamsaini@gmail.com",
    "foodonthetablebusiness@gmail.com",
    "shantanudeshmukh12@gmail.com",
    "krrishcreation79@gmail.com",
    "contact.rohitkhatrifitness@gmail.com",
    "fitnesspoint03@gmail.com",
]

assert len(SAMPLE_EMAILS) == 35, f"Expected 35 emails, got {len(SAMPLE_EMAILS)}"

api_key_1 = os.environ.get("MAIL7_API_KEY_1", "").strip()
if not api_key_1:
    logger.error("MAIL7_API_KEY_1 is not available in environment.")
    sys.exit(1)

logger.info(f"Loaded MAIL7_API_KEY_1 securely (masked: {'*' * 8}).")
logger.info(f"Submitting {len(SAMPLE_EMAILS)} sample emails to Mail7 (hard budget: 35 credits)...")

# Use isolated temp directory for ledger, cache, and pool state
temp_dir = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "mail7_isolated_test"
temp_dir.mkdir(parents=True, exist_ok=True)

isolated_ledger = QuotaLedger(
    ledger_file=temp_dir / "test_ledger.csv",
    cache_file=temp_dir / "test_cache.csv",
)

pool = Mail7AccountPool(
    keys=[api_key_1],
    state_file=temp_dir / "test_pool_state.json",
    today_ist_date="2026-11-01",
)

verifier = Mail7Verifier(
    pool=pool,
    ledger=isolated_ledger,
    dry_run=False,
)

# Execute real verification
results, error_reason = verifier.verify_bulk(SAMPLE_EMAILS, date_str="2026-11-01")

valid_emails = [r.email for r in results if r.status == "valid"]
invalid_emails = [r.email for r in results if r.status == "invalid"]
unknown_emails = [r.email for r in results if r.status == "unknown"]
error_emails = [r.email for r in results if r.status == "verification_error"]

invalid_percentage = (len(invalid_emails) / len(results) * 100) if results else 0.0
valid_percentage = (len(valid_emails) / len(results) * 100) if results else 0.0

summary = {
    "total_submitted": len(results),
    "credits_used": len(results),
    "valid_count": len(valid_emails),
    "valid_percentage": round(valid_percentage, 2),
    "invalid_count": len(invalid_emails),
    "invalid_percentage": round(invalid_percentage, 2),
    "unknown_count": len(unknown_emails),
    "error_count": len(error_emails),
    "error_reason": error_reason,
    "valid_emails": valid_emails,
    "invalid_emails": invalid_emails,
    "unknown_emails": unknown_emails,
    "error_emails": error_emails,
    "raw_results": [
        {"email": r.email, "status": r.status, "reason": r.reason, "account_id": r.account_id}
        for r in results
    ],
}

print("\n=== MAIL7_TEST_RESULTS_START ===")
print(json.dumps(summary, indent=2))
print("=== MAIL7_TEST_RESULTS_END ===\n")

if error_reason:
    logger.warning(f"Verification completed with warning/reason: {error_reason}")
else:
    logger.info("Verification completed successfully.")
