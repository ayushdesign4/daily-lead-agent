# 🧠 PROJECT CONTEXT & SYSTEM MEMORY — DAILY LEAD AGENT

**Repository:** `https://github.com/ayushdesign4/daily-lead-agent`  
**Branch:** `main` (synchronized with `origin/main`)  
**Context Reconstructed:** October 22, 2026  
**Runtime:** Python 3.11+ / GitHub Actions (Ubuntu-latest)  

---

## 1. Project Purpose & Core Value Proposition

The **Daily Lead Agent** is an autonomous, serverless lead generation and cold outreach platform built specifically for Indian YouTube creator outreach (primarily offering thumbnail design services).

### Key Objectives
- Discover **200 fresh, verified, highly targeted Indian YouTube creators** daily.
- Protect credit spend via demand-driven scraping (Apify Google Search Scraper). If the backlog queue already has sufficient leads, **zero search credits are consumed**.
- Maintain lifetime deduplication across all past runs (`data/master_leads.csv`). No email is ever contacted twice.
- Deliver a clean `.txt` lead file (one email per line) to the operator's inbox daily at **11:00 AM IST**.
- Automatically trigger the downstream **Verified Outreach Pipeline** upon delivery, validating email deliverables via the Mail7 Bulk API and dispatching personalized cold emails through a rotating pool of 9 Gmail sender accounts.
- Provide a zero-downtime mobile recovery loop: if Apify or Mail7 credits are exhausted, alert emails provide direct links to Google Forms, which trigger GitHub Actions workflows to rotate API keys via encrypted GitHub repository secrets (`PyNaCl`).

---

## 2. Technical Architecture & File Layout

```
daily-lead-agent/
│
├── .github/workflows/
│   ├── daily_leads.yml            # 01:00 AM IST overnight harvest (--mode prepare)
│   ├── deliver_leads.yml          # 11:00 AM IST delivery & idempotency check (--mode deliver)
│   ├── outreach_pipeline.yml      # Event-driven cold outreach triggered after delivery
│   ├── update_token.yml           # Dispatched workflow to update APIFY_API_TOKEN secret
│   └── update_mail7_key.yml       # Dispatched workflow to update MAIL7_API_KEY secret
│
├── src/
│   ├── config.py                  # Core configuration, paths, and environment settings
│   ├── state_manager.py           # Atomic CSV I/O, receipt logging, and IST timestamping
│   ├── niche_categories.py        # 11 creator categories & keyword classifier
│   ├── curated_niches.py          # 7,800+ strictly 1-word curated niches partitioned by category
│   ├── niche_manager.py           # Adaptive Bayesian yield selection & persistent category cursors
│   ├── apify_client.py            # Apify Google Search Scraper caller with credit detection
│   ├── email_extractor.py         # RFC-compliant email regex, domain validation, cleaning
│   ├── deduplicator.py            # Intra-batch & lifetime master deduplication
│   ├── queue_manager.py           # Transactional FIFO queue manager (data/pending_queue.csv)
│   ├── delivery.py                # Gmail SMTP delivery manager for leads & admin alerts
│   ├── main.py                    # Core orchestrator CLI (modes: prepare, deliver, all)
│   │
│   └── outreach/                  # Downstream Cold Outreach Subsystem
│       ├── config.py              # Outreach configuration, limits, and file paths
│       ├── orchestrator.py        # Outreach pipeline orchestrator CLI
│       ├── gmail_watcher.py       # Fresh-lead date guard & delivery receipt verifier
│       ├── attachment_parser.py   # Parses daily output lead files (.txt)
│       ├── address_normalizer.py  # RFC filtering & deduplication for outreach
│       ├── verification_client.py # Mail7 Bulk API client with quota/error handling
│       ├── quota_ledger.py        # Tracks verification credit usage & daily caps
│       ├── suppression.py         # Manages bounce/opt-out suppression lists
│       ├── distributor.py         # Shards verified leads across 9 sender accounts
│       ├── template_manager.py    # Personalized thumbnail pitch template rendering
│       ├── sender.py              # Multi-account SMTP sender with jitter & BCC to operator
│       └── campaign_state.py      # Atomic checkpointing for outreach campaign batches
│
├── data/                          # Persistent state tracked in Git (committed by GitHub Bot)
│   ├── master_leads.csv           # Lifetime database of all delivered leads
│   ├── pending_queue.csv          # Unconsumed backlog of fresh leads
│   ├── used_niches.csv            # Historical log of all queried niches
│   ├── daily_runs.csv             # Execution logs and delivery status
│   ├── delivery_receipt_*.json    # Atomic per-day delivery receipts
│   ├── outreach_state.csv         # Outreach campaign statuses
│   ├── outreach_batches.csv       # Batches sent per sender account
│   ├── outreach_suppressions.csv  # Unsubscribed/bounced emails
│   ├── verification_ledger.csv    # Mail7 credit tracking
│   ├── verification_cache.csv     # Cached email verification statuses
│   └── checkpoint_CAMP-*.json     # Interrupted outreach run recovery checkpoints
│
├── scripts/
│   ├── compile_niche_pool.py      # Compiler script generating src/curated_niches.py
│   ├── update_github_secret.py    # PyNaCl-encrypted secret updater for GitHub API
│   ├── google_apps_script.js      # Apps Script code connecting Google Forms to GitHub
│   └── niche_expansion_*.py       # Lexical vocab expansions (vocab 1 through 8)
│
├── tests/                         # Pytest test suite (129 tests across unit & integration)
├── reports/                       # Local dry-run audit & scenario test artifacts (untracked)
├── requirements.txt               # requests, python-dotenv, PyNaCl, pytest
└── SETUP_GUIDE.md                 # Complete non-technical setup documentation
```

---

## 3. End-to-End Workflow & Pipeline Lifecycles

```
                                  [01:00 AM IST]
                              daily_leads.yml (prepare)
                                         │
                                         ▼
                     ┌────────────────────────────────────────┐
                     │ Check data/pending_queue.csv           │
                     │ Shortage = DAILY_TARGET - QueueSize    │
                     └───────────────────┬────────────────────┘
                                         │
                   ┌─────────────────────┴─────────────────────┐
             Shortage == 0                               Shortage > 0
                   │                                           │
                   ▼                                           ▼
      0 Apify credits consumed                   NicheManager selects 10 queries
         (Queue sufficient)                      (70% Exploit / 30% Explore)
                                                               │
                                                               ▼
                                                 Apify Google Search Scraper
                                                               │
                                                               ▼
                                                 EmailExtractor + Deduplicator
                                                               │
                                                               ▼
                                                 Add genuinely new leads to
                                                 master_leads.csv & pending_queue
                                                               │
                                         ┌─────────────────────┘
                                         ▼
                                  [11:00 AM IST]
                             deliver_leads.yml (deliver)
                                         │
                                         ▼
                     ┌────────────────────────────────────────┐
                     │ Check Idempotency & Delivery History   │
                     │ Extract 200 leads from pending_queue   │
                     │ Generate output/leads_YYYY-MM-DD.txt   │
                     │ Send attachment to DELIVERY_EMAIL SMTP │
                     │ ONLY on success: commit queue removal  │
                     └───────────────────┬────────────────────┘
                                         │
                                         ▼
                             [Event Trigger: workflow_run]
                               outreach_pipeline.yml
                                         │
                                         ▼
                     ┌────────────────────────────────────────┐
                     │ GmailWatcher: Validate today's IST     │
                     │ delivery receipt exists and is fresh   │
                     │ Mail7 Bulk API: Validate deliverables  │
                     │ Suppression Check: Remove opted-out    │
                     │ Distributor: Shard across 9 accounts   │
                     │ OutreachSender: Send with jitter/BCC   │
                     │ Atomic checkpoint update & git commit  │
                     └────────────────────────────────────────┘
```

---

## 4. Key Engineering & Design Decisions

1. **Transactional Queue Safety**:
   - Leads are **never** removed from `data/pending_queue.csv` until SMTP delivery is confirmed with a 250 OK code.
   - If an email send fails, all staged leads remain intact in the queue for subsequent retry.
   - Atomic delivery receipts (`data/delivery_receipt_YYYY-MM-DD.json`) record sent email addresses immediately.

2. **Adaptive Bayesian Niche Ranking**:
   - 11 creator categories: `gaming`, `technology`, `automotive`, `fitness`, `finance`, `science`, `culinary`, `outdoors`, `creative`, `maker`, `exploration`.
   - Categories are ranked via empirical Bayes smoothed yield:
     $$\text{Score} = \frac{\text{new\_leads} + 10.0}{\text{raw\_emails} + 20.0}$$
   - Selection allocates 70% slots to high-yield exploit categories and 30% to explore categories.
   - To prevent category starvation outside the 10-slot batch window, rotation offsets cycle both exploit and explore categories evenly.

3. **Strict One-Word Niche Policy**:
   - Every niche query uses strictly one alphabetic word (no numbers, no hyphens, no underscores, no synthetic compound mashups like `weddingphotography`).
   - Standard query template: `site:youtube.com "{niche}" "Business Inquiries" "gmail.com" India`.

4. **Fresh-Lead Date Guard**:
   - `GmailWatcher` enforces that the outreach pipeline only runs on leads delivered on the current IST date. Prevents processing stale deliveries if scheduled runs are delayed.

5. **Self-Healing Token Rotation**:
   - Credit exhaustion or 401 unauthorized errors immediately notify the administrator via email with Google Form links.
   - Forms invoke Google Apps Script, which triggers `update_token.yml` or `update_mail7_key.yml` with sodium-encrypted secret payloads without exposing credentials.

---

## 5. Environment Variables & Secrets Reference

| Variable Name | Required By | Purpose / Example |
| :--- | :--- | :--- |
| `SEARCH_PROVIDER` | Core Agent | Provider selection (`brightdata` default, `apify` fallback) |
| `BRIGHTDATA_API_TOKEN_1` | Core Agent | Primary Bright Data account API token |
| `BRIGHTDATA_API_TOKEN_2` | Core Agent | Secondary Bright Data account API token (rotation pool) |
| `BRIGHTDATA_API_TOKEN_3` | Core Agent | Tertiary Bright Data account API token (rotation pool) |
| `BRIGHTDATA_ZONE_1` | Core Agent | Account 1 SERP zone name (default: `token_1`) |
| `BRIGHTDATA_ZONE_2` | Core Agent | Account 2 SERP zone name (default: `token_22`) |
| `BRIGHTDATA_ZONE_3` | Core Agent | Account 3 SERP zone name (default: `token_333`) |
| `APIFY_API_TOKEN` | Core Agent (Legacy) | Apify authentication token (retained as rollback fallback) |
| `APIFY_ACTOR_ID` | Core Agent (Legacy) | `apify/google-search-scraper` |
| `GMAIL_USERNAME` | Core Agent & Outreach | Primary sender Gmail address for lead delivery & alerts |
| `GMAIL_APP_PASSWORD` | Core Agent & Outreach | 16-character Google App Password (not account password) |
| `DELIVERY_EMAIL` | Core Agent & Outreach | Destination inbox for daily lead `.txt` files |
| `GOOGLE_FORM_URL` | Core Agent | Direct URL to form for token rotation |
| `DAILY_TARGET` | Core Agent | Number of leads per day (default: `200`) |
| `MAX_PAGES_PER_QUERY` | Core Agent | Maximum search pages per query (default: `20`) |
| `MAIL7_API_KEY` | Outreach Pipeline | Mail7 API key for bulk email verification |
| `MAIL7_ROTATION_FORM_URL`| Outreach Pipeline | Direct URL to form for Mail7 key rotation |
| `OUTREACH_ACCOUNTS_JSON`| Outreach Pipeline | JSON array of 9 sender accounts: `[{"email":"...", "app_password":"..."}]` |
| `OUTREACH_TO_EMAIL` | Outreach Pipeline | Fixed recipient field (`ayush@ayushdesign.site`), actual lead BCC'd |
| `GH_SECRET_UPDATE_PAT` | Secret Workflows | GitHub Personal Access Token with `secrets:write` permissions |

---

## 6. Recent Git History & Milestones

- **Bright Data Migration (2026-10-22)**: Replaced Apify scraping with Bright Data SERP API (`src/brightdata_client.py`), implementing 3-account rotation pool ($1 \to 2 \to 3$), 20-page pagination (`start=0` to `190`), early stopping on empty pages, conservative spacing normalization in `src/email_extractor.py`, and 100% test coverage.
- **`e77ad24` (2026-10-20)**: Implemented adaptive niche selection algorithm (`src/niche_categories.py`, `src/niche_manager.py`), Bayesian smoothing, bounds checking, and comprehensive scenario tests.
- **`35f6072` (2026-10-20)**: Bot auto-updated outreach pipeline state and checkpoints.
- **`66cf414` (2026-10-20)**: Bot auto-updated 11 AM IST delivery state (delivered leads, master leads, used niches).
- **`484d434` (2026-10-20)**: Improved single-word niche keyword quality, added subniches and vocab expansions 4–8.
- **`cb8398c` (2026-10-20)**: Connected outreach pipeline to run event-driven via `workflow_run` after successful 11 AM IST delivery.
- **`91545da` (2026-10-18)**: Expanded curated niche pool to 5,106+ single-word niches and added outreach date guard.

---

## 7. Current System Health & Audit Status

### Test Suite Execution
- **Pytest command:** `python -m pytest`
- **Total tests:** 142
- **Passing:** 142 (100% PASS)
- **Failing:** 0
- **Duration:** ~15 seconds across unit, mock, integration, and E2E tests.

---

## 8. Prioritized Next Actions

1. **Configure Bright Data Secrets in GitHub Repository**:
   Add `BRIGHTDATA_API_TOKEN_1`, `BRIGHTDATA_API_TOKEN_2`, and `BRIGHTDATA_API_TOKEN_3` under Settings &rarr; Secrets and variables &rarr; Actions.
2. **Execute Single-Query Smoke Verification**:
   Trigger a controlled single-query test under supervision to verify live Bright Data response parsing.
3. **Review Untracked Reports**:
   Decide whether `reports/` should be tracked in Git, added to `.gitignore`, or preserved as audit documentation.
4. **Production Run Monitoring**:
   Verify next automated execution of `daily_leads.yml` (01:00 AM IST) and `deliver_leads.yml` (11:00 AM IST) on GitHub Actions.
