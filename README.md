# 🚀 Daily Lead Agent — YouTube Creator Outreach Automation

A production-ready, fully autonomous lead extraction and delivery system specifically designed for thumbnail-design outreach. The system automatically discovers Indian YouTube creators using Apify's Google Search Scraper, deduplicates against an eternal lifetime database, manages an unconsumed queue, and emails **200 genuinely new creator emails** in a clean `.txt` attachment daily targeted at **11:00 AM IST**.

Runs **100% on GitHub Actions infrastructure**. Your phone, laptop, or personal computer do **NOT** need to remain online.

---

## 🌟 Key Architecture & Capabilities

1. **Credit-Optimized Search**:
   - Inspects the persistent FIFO pending queue (`data/pending_queue.csv`) **before** spending any Apify credits.
   - If the queue has 200+ leads, **0 Apify credits** are used.
   - If there is a shortage (e.g. 73 in queue, shortage = 127), runs search batches only until the shortage is filled, then **stops immediately**. Surplus leads are saved into the queue for tomorrow.

2. **Apify Google Search Scraper Actor (`apify/google-search-scraper`)**:
   - Strictly up to 10 niche queries per batch.
   - Max 30 pages per query.
   - Geographic & Language targeting: India (`countryCode: "in"`), English (`languageCode: "en"`).
   - Freshness filtering: Restricts search results to the **last 3 months** (`tbs: "qdr:m3"`).
   - All unnecessary paid ads, mobile emulation, AI overviews, and HTML storage are turned **OFF** to minimize compute unit consumption.

3. **Intelligent Niche Rotation & Semantic Protection**:
   - Standard query format: `site:youtube.com "<NICHE>" "Business Inquiries" "gmail.com" India`
   - Normalizes niches (case, spaces, punctuation) and records every attempted niche in `data/used_niches.csv`.
   - Built-in library of 150+ high-yield thumbnail outreach verticals across tech, gaming, finance, fitness, travel, food, vloggers, podcasts, etc., plus dynamic vertical generation.
   - **Zero repeat niches**: A niche is never reused across lifetime runs.

4. **Robust Multi-Stage Deduplication**:
   - Strips whitespace, brackets, quotes, and punctuation.
   - Validates RFC-compliant email structure and filters out invalid TLDs (`.png`, `.jpg`, etc.) and placeholder domains.
   - Deduplicates within the batch.
   - Deduplicates against the permanent master database (`data/master_leads.csv`). No email is ever delivered twice.

5. **Crash-Safe & Atomic Persistence**:
   - Uses atomic file replacement (`tempfile` + `os.replace` + `fsync`) to prevent CSV corruption during workflow interruption.
   - GitHub Actions automatically commits and pushes `data/`, `logs/`, and `output/` back to the repository.
   - State survives API token changes, workflow restarts, and manual triggers.

6. **Daily Delivery & Idempotency**:
   - Leads exported to `output/leads_YYYY-MM-DD.txt` containing **ONLY** email addresses (one per line, zero headers or metadata).
   - Delivered directly to your inbox using Gmail SMTP with SSL/TLS.
   - Delivery history recorded in `data/daily_runs.csv` to prevent duplicate emails if a workflow is retried.

7. **Graceful Credit Exhaustion & Mobile Token Replacement**:
   - When Apify credits expire or API limits are reached, the system **never loops or crashes**.
   - Delivers whatever genuine leads were already obtained today.
   - Sends a dedicated alert email containing a direct link to your **Google Form**.
   - You paste a new Apify API key into the Google Form from your phone.
   - Google Apps Script automatically signals GitHub Actions to update `APIFY_API_TOKEN` without touching code or wiping any data.

---

## 📂 Project Structure

```
daily-lead-agent/
│
├── .github/
│   └── workflows/
│       ├── daily_leads.yml       # Overnight run (01:00 AM IST) & state push
│       ├── deliver_leads.yml     # 11:00 AM IST delivery & idempotency check
│       └── update_token.yml      # Webhook workflow for Google Form key replacement
│
├── src/
│   ├── __init__.py
│   ├── config.py                 # Environment variables and path resolution
│   ├── state_manager.py          # Atomic CSV operations (master, queue, niches, runs)
│   ├── niche_manager.py          # Niche rotation, normalization, query generation
│   ├── apify_client.py           # Apify API client with credit exhaustion detection
│   ├── email_extractor.py        # Email extraction, regex validation & sanitization
│   ├── deduplicator.py           # Intra-batch & master database deduplication
│   ├── queue_manager.py          # FIFO queue consumption & surplus management
│   ├── delivery.py               # Gmail SMTP lead file & alert delivery
│   └── main.py                   # Central orchestrator CLI
│
├── scripts/
│   ├── update_github_secret.py   # Libsodium-encrypted GitHub secret updater
│   └── google_apps_script.js     # Ready-to-use Google Form submission trigger
│
├── data/                         # Permanent tracked database files
│   ├── master_leads.csv          # Lifetime database of all discovered leads
│   ├── pending_queue.csv         # Queue of extra leads for upcoming days
│   ├── used_niches.csv           # Historical log of all searched niches
│   └── daily_runs.csv            # Run execution log & duplicate prevention
│
├── output/                       # Generated leads_YYYY-MM-DD.txt files
├── logs/                         # Detailed execution logs (no secrets logged)
├── tests/                        # Full unit and integration test suite (22 tests)
├── requirements.txt              # Production and testing dependencies
├── SETUP_GUIDE.md                # Non-technical step-by-step setup guide
├── .env.example                  # Environment configuration template
└── README.md
```

---

## ⏰ Delivery Schedule & Timing

- **01:00 AM IST (19:30 UTC previous day)**: `daily_leads.yml` executes overnight.
  - Inspects queue.
  - Runs Apify batches if extra leads are needed.
  - Saves surplus to queue.
  - Commits database and logs back to the GitHub repository.
  - Sends lead email.
- **10:45 AM - 11:00 AM IST (05:15 UTC)**: `deliver_leads.yml` verifies today's delivery status.
  - If already delivered overnight, exits idempotently (0 duplicate emails sent).
  - If processing was pending, completes delivery before 11:00 AM.

---

## 🧪 Testing and Verification

A comprehensive 22-test automated suite covers all requirements:

```bash
# Run full unit and integration test suite
python -m pytest tests -v
```

### Dry Run & Test Mode (Zero Credits Used)

You can run the agent locally or in GitHub Actions with simulated creator data:

```bash
# Test full discovery, queueing, and TXT file creation with 0 Apify credits
python -m src.main --test-mode --target 25 --force
```

### Inspect Output File
```bash
cat output/leads_$(date +%Y-%m-%d).txt
```

---

## 🔑 Quick Setup Overview

For a step-by-step beginner guide with screenshots, see [SETUP_GUIDE.md](SETUP_GUIDE.md).

### Required GitHub Secrets:
1. `APIFY_API_TOKEN`: Your Apify personal API token.
2. `GMAIL_USERNAME`: Your Gmail address (e.g. `yourname@gmail.com`).
3. `GMAIL_APP_PASSWORD`: 16-character Google App Password (from [Google App Passwords](https://myaccount.google.com/apppasswords)).
4. `DELIVERY_EMAIL`: Where you want the leads delivered daily.
5. `GOOGLE_FORM_URL`: URL to your Google Form for 1-click phone token replacement.
