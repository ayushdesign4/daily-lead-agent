# 📖 Setup Guide — Daily Lead Agent

This step-by-step guide explains how to set up your Daily Lead Agent so it runs completely on its own every day on GitHub Actions without needing your computer or phone to stay on.

---

## 📋 Table of Contents
1. [Create GitHub Repository](#1-create-github-repository)
2. [Get Your Apify API Token](#2-get-your-apify-api-token)
3. [Generate Gmail App Password](#3-generate-gmail-app-password)
4. [Configure GitHub Secrets](#4-configure-github-secrets)
5. [Set Up 1-Click Google Form Token Replacement](#5-set-up-1-click-google-form-token-replacement)
6. [Test Your Setup](#6-test-your-setup)

---

## 1. Create GitHub Repository

1. Go to [GitHub.com](https://github.com) and create a new **Private** repository named `daily-lead-agent`.
2. Push this project to your repository:
   ```bash
   git add .
   git commit -m "Initial commit of Daily Lead Agent"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/daily-lead-agent.git
   git push -u origin main
   ```
3. Enable GitHub Actions Workflow Permissions:
   - In your repo, go to **Settings** -> **Actions** -> **General**.
   - Scroll down to **Workflow permissions**.
   - Select **Read and write permissions**.
   - Check **Allow GitHub Actions to create and approve pull requests**.
   - Click **Save**.

---

## 2. Get Your Apify API Token

1. Sign up or log into [Apify.com](https://apify.com).
2. Go to **Settings** -> **Integrations** (or [console.apify.com/account/integrations](https://console.apify.com/account/integrations)).
3. Under **Personal API tokens**, copy your token (looks like `apify_api_...`).

---

## 3. Generate Gmail App Password

To allow the agent to send you the daily `.txt` file via Gmail SMTP securely:

1. Go to your [Google Account Security](https://myaccount.google.com/security).
2. Ensure **2-Step Verification** is turned ON.
3. Search for or navigate to **App passwords** ([myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)).
4. Enter an app name (e.g. `Daily Lead Agent`) and click **Create**.
5. Copy the generated **16-character password** (e.g., `abcd efgh ijkl mnop`).

---

## 4. Configure GitHub Secrets

1. In your GitHub repository, click **Settings** (top tab) -> **Secrets and variables** -> **Actions**.
2. Click **New repository secret** for each of the following:

| Secret Name | Value Description | Example |
| :--- | :--- | :--- |
| `APIFY_API_TOKEN` | Your Apify personal API token | `apify_api_123456789...` |
| `GMAIL_USERNAME` | Your sending Gmail address | `yourname@gmail.com` |
| `GMAIL_APP_PASSWORD` | The 16-character Gmail App Password | `abcdefghijklmnop` |
| `DELIVERY_EMAIL` | Where to receive daily lead files | `yourinbox@gmail.com` |
| `GOOGLE_FORM_URL` | Link to your Google Form (see Step 5) | `https://forms.gle/XYZ...` |
| `GH_SECRET_UPDATE_PAT` | *(Optional)* GitHub PAT for Google Form auto-update | `ghp_12345...` |

---

## 5. Set Up 1-Click Google Form Token Replacement

When your Apify credits run out or you want to switch to a new Apify account, the system automatically emails you an alert with a link to your Google Form. You can update the key from your phone in seconds.

### Step A: Create the Google Form
1. Go to [forms.google.com](https://forms.google.com) and create a blank form.
2. Title it: **Daily Lead Agent — Apify Token Replacement**.
3. Add 1 question:
   - Question Title: `Apify API Key`
   - Question Type: **Short answer**
4. Click **Send** (top right), copy the short link (e.g. `https://forms.gle/abc123xyz`), and add it as the `GOOGLE_FORM_URL` GitHub Secret.

### Step B: Attach the Auto-Update Script (Google Apps Script)
1. On the Google Form edit page, click the **3 vertical dots** (top right) -> **Script editor**.
2. Erase any code inside `Code.gs` and paste the contents of [`scripts/google_apps_script.js`](scripts/google_apps_script.js).
3. At the top of the script, update:
   ```javascript
   const GITHUB_OWNER = "YOUR_GITHUB_USERNAME";
   const GITHUB_REPO = "daily-lead-agent";
   const GITHUB_PAT = "ghp_YOUR_PERSONAL_ACCESS_TOKEN";
   ```
   *(To create a GitHub PAT: Visit [github.com/settings/tokens](https://github.com/settings/tokens) -> Generate new token (classic) -> Select scope `repo` -> Copy token).*
4. Click **Triggers** (clock icon on the left menu) -> **+ Add Trigger**:
   - Choose which function to run: `onFormSubmit`
   - Select event source: `From form`
   - Select event type: `On form submit`
   - Click **Save**.
5. Done! Whenever you submit a new Apify token into the form, it will update the GitHub Secret automatically in the cloud.

---

## 6. Test Your Setup

You can test the entire workflow directly in GitHub Actions without waiting for 11:00 AM IST:

1. In your GitHub repository, click the **Actions** tab.
2. In the left sidebar, click **Daily Lead Agent - Overnight Run & Delivery**.
3. Click **Run workflow** (dropdown button on the right).
4. Options:
   - To run a zero-credit dry-run test: check **dry_run** -> click **Run workflow**.
   - To run for real: enter target `5` (or leave default `200`) -> click **Run workflow**.
5. Watch the workflow complete! Check your email inbox for the attached `leads_YYYY-MM-DD.txt` file.

---

## 🛡️ Data Persistence & Safety

- All lifetime leads are saved in `data/master_leads.csv`.
- Leftover leads are stored in `data/pending_queue.csv`.
- Niches are tracked in `data/used_niches.csv`.
- Each completed run pushes changes to GitHub using `GITHUB_TOKEN`.
- **Changing your Apify key will NEVER wipe or alter your existing leads, queue, or history!**
