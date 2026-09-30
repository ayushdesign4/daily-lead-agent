/**
 * Google Apps Script for Google Forms: Automatic Apify API Token Updater
 *
 * HOW TO SET UP (Takes ~2 minutes):
 * 1. Create a Google Form with 1 question:
 *    - Question: "Apify API Key" (Short answer text)
 * 2. In Google Form, click the 3 dots (top right) -> "Script editor" (Apps Script).
 * 3. Replace all code in the editor with this script.
 * 4. Fill in your GITHUB_OWNER, GITHUB_REPO, and GITHUB_PAT below.
 * 5. Click the Clock icon ("Triggers") on the left sidebar:
 *    - Click "+ Add Trigger"
 *    - Choose function: "onFormSubmit"
 *    - Event source: "From form"
 *    - Event type: "On form submit"
 *    - Click Save.
 *
 * When you submit a new Apify token from your phone, this script automatically
 * signals GitHub Actions to securely update the repository secret APIFY_API_TOKEN!
 */

const GITHUB_OWNER = "YOUR_GITHUB_USERNAME";
const GITHUB_REPO = "daily-lead-agent";
// Create a GitHub Personal Access Token (classic) with "repo" scope at https://github.com/settings/tokens
const GITHUB_PAT = "ghp_YOUR_PERSONAL_ACCESS_TOKEN";

function onFormSubmit(e) {
  try {
    let apifyKey = "";
    
    // Extract answer from form submission
    if (e && e.response) {
      const itemResponses = e.response.getItemResponses();
      for (let i = 0; i < itemResponses.length; i++) {
        const itemResponse = itemResponses[i];
        const title = itemResponse.getItem().getTitle().toLowerCase();
        if (title.includes("apify") || title.includes("token") || title.includes("key")) {
          apifyKey = itemResponse.getResponse().trim();
          break;
        }
      }
      // Fallback: take first item if name didn't match
      if (!apifyKey && itemResponses.length > 0) {
        apifyKey = itemResponses[0].getResponse().trim();
      }
    }

    if (!apifyKey) {
      Logger.log("No Apify key found in submission.");
      return;
    }

    Logger.log("Triggering GitHub dispatch to update APIFY_API_TOKEN...");

    const url = "https://api.github.com/repos/" + GITHUB_OWNER + "/" + GITHUB_REPO + "/dispatches";
    const payload = {
      event_type: "update_apify_token",
      client_payload: {
        new_token: apifyKey
      }
    };

    const options = {
      method: "post",
      contentType: "application/json",
      headers: {
        "Authorization": "Bearer " + GITHUB_PAT,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
      },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    };

    const response = UrlFetchApp.fetch(url, options);
    const code = response.getResponseCode();

    if (code === 204) {
      Logger.log("Successfully triggered GitHub token update!");
    } else {
      Logger.log("Error triggering GitHub dispatch: " + code + " " + response.getContentText());
    }
  } catch (err) {
    Logger.log("Exception in onFormSubmit: " + err.toString());
  }
}
