"""Comprehensive verification of smart email extraction and resilient bulk verification."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import json

from src.email_extractor import (
    clean_and_normalize_email,
    is_valid_email,
    extract_emails_from_text,
    extract_emails_from_item,
    repair_domain_boundaries,
)
from src.outreach.verification_client import Mail7Verifier, VerificationResult
from src.outreach.orchestrator import OutreachPipeline
from src.outreach.campaign_state import CampaignState
from src.outreach.quota_ledger import QuotaLedger
from src.outreach.suppression import SuppressionManager


class TestSmartEmailExtraction:
    """Test smart extraction and domain-boundary repair of corrupted Bright Data snippets."""

    def test_corrupted_suffix_cases_specified_by_user(self):
        """Test specific corrupted examples from user prompt."""
        # creator@gmail.com.more -> creator@gmail.com
        assert clean_and_normalize_email("creator@gmail.com.more") == "creator@gmail.com"
        assert is_valid_email(clean_and_normalize_email("creator@gmail.com.more"))

        # info@company.comread -> info@company.com
        assert clean_and_normalize_email("info@company.comread") == "info@company.com"
        assert is_valid_email(clean_and_normalize_email("info@company.comread"))

        # contact@gmail.com.links -> contact@gmail.com
        assert clean_and_normalize_email("contact@gmail.com.links") == "contact@gmail.com"
        assert is_valid_email(clean_and_normalize_email("contact@gmail.com.links"))

        # name@gmail.com.https -> name@gmail.com
        assert clean_and_normalize_email("name@gmail.com.https") == "name@gmail.com"
        assert is_valid_email(clean_and_normalize_email("name@gmail.com.https"))

    def test_legitimate_addresses_remain_unmodified(self):
        """Normal legitimate Gmail and business email addresses must be preserved exactly."""
        # Legitimate Gmail
        assert clean_and_normalize_email("user@gmail.com") == "user@gmail.com"
        assert is_valid_email("user@gmail.com")

        # Legitimate business email
        assert clean_and_normalize_email("support@company.co.uk") == "support@company.co.uk"
        assert is_valid_email("support@company.co.uk")

        # Legitimate multi-part ccTLDs
        assert clean_and_normalize_email("info@startup.co.in") == "info@startup.co.in"
        assert is_valid_email("info@startup.co.in")

        assert clean_and_normalize_email("sales@business.com.au") == "sales@business.com.au"
        assert is_valid_email("sales@business.com.au")

        assert clean_and_normalize_email("press@organization.org") == "press@organization.org"
        assert is_valid_email("press@organization.org")

    def test_multiple_emails_in_one_snippet(self):
        """Multiple emails in one snippet text are extracted correctly."""
        snippet = (
            "Contact creator@gmail.com.more or business@agency.co.in for sponsorships. "
            "Press inquiries: press@channel.comread. Do not message fake@image.png!"
        )
        extracted = extract_emails_from_text(snippet)
        assert "creator@gmail.com" in extracted
        assert "business@agency.co.in" in extracted
        assert "press@channel.com" in extracted
        assert "fake@image.png" not in extracted

    def test_actually_malformed_emails_not_falsely_converted(self):
        """Actually malformed emails are NOT converted into valid ones."""
        malformed_cases = [
            "invalid@.com",
            "missing_at_symbol.com",
            "two@@at.com",
            "@nousername.com",
            "username@domain..com",
            "not_an_email",
            "user@image.png",
            "video@clip.mp4",
        ]
        for bad in malformed_cases:
            cleaned = clean_and_normalize_email(bad)
            assert not is_valid_email(cleaned), f"Expected {bad} to be invalid, got cleaned={cleaned}"

    def test_item_extraction_from_brightdata_structure(self):
        """Extract valid emails from Bright Data search result item."""
        item = {
            "title": "Channel Title - Inquiries: creator@gmail.com.view",
            "description": "Welcome! For partnerships: partner@brand.comread. More info on site.",
            "snippets": "Secondary email: backup@youtube.com.",
            "link": "https://youtube.com/@channel",
        }
        extracted = extract_emails_from_item(item)
        assert "creator@gmail.com" in extracted
        assert "partner@brand.com" in extracted
        assert "backup@youtube.com" in extracted


class TestResilientBulkVerification:
    """Test resilient Mail7 verification and bisection behavior."""

    def test_one_malformed_email_does_not_break_entire_batch(self, tmp_path):
        """
        When Mail7 rejects a bulk request with HTTP 400 Bad Request due to one malformed address,
        bisection recursively isolates the bad address and verifies all other valid leads.
        """
        ledger = QuotaLedger(ledger_file=tmp_path / "ledger.csv", cache_file=tmp_path / "cache.csv")
        verifier = Mail7Verifier(api_key="valid_test_key", ledger=ledger, dry_run=False)

        emails = [f"valid_{i}@test.com" for i in range(10)]
        bad_email = "malformed%bad@bad_domain"
        emails.insert(4, bad_email)

        # Mock requests.post:
        # If payload contains bad_email, return HTTP 400 unless chunk length is 1
        def mock_post(url, files=None, headers=None, timeout=None):
            payload = files["emails"][1]
            chunk = payload.split("\n")
            mock_resp = MagicMock()
            if bad_email in chunk and len(chunk) > 1:
                mock_resp.status_code = 400
                mock_resp.text = "HTTP 400 Bad Request: malformed email syntax"
                return mock_resp
            elif bad_email in chunk and len(chunk) == 1:
                mock_resp.status_code = 400
                mock_resp.text = "HTTP 400 Bad Request: malformed email syntax"
                return mock_resp
            else:
                mock_resp.status_code = 200
                mock_resp.json.return_value = {
                    "results": [
                        {"email": e, "status": "Valid", "valid": True}
                        for e in chunk
                    ]
                }
                return mock_resp

        with patch("src.outreach.verification_client.requests.post", side_effect=mock_post):
            results, error_reason = verifier.verify_bulk(emails, date_str="2026-11-01")

        # The 10 valid emails must ALL be verified as 'valid'
        valid_results = [r for r in results if r.status == "valid"]
        assert len(valid_results) == 10
        assert all(r.is_deliverable for r in valid_results)

        # The 1 bad email must be isolated as 'invalid' with syntax failure reason
        bad_results = [r for r in results if r.email == bad_email]
        assert len(bad_results) == 1
        assert bad_results[0].status == "invalid"
        assert "malformed_syntax" in bad_results[0].reason

    def test_temporary_server_error_preserves_leads_for_retry(self, tmp_path):
        """
        Temporary API server error (HTTP 500) must pause the pipeline,
        preserve unverified leads in checkpoint, and NOT mark them as invalid or send empty batches.
        """
        state_file = tmp_path / "state.csv"
        batches_file = tmp_path / "batches.csv"
        state_mgr = CampaignState(state_file, batches_file)
        quota_ledger = QuotaLedger(tmp_path / "l.csv", tmp_path / "c.csv")

        lead_file = tmp_path / "leads.txt"
        lead_file.write_text("lead1@test.com\nlead2@test.com\n")

        pipeline = OutreachPipeline(
            dry_run=True,
            state_mgr=state_mgr,
            quota_ledger=quota_ledger,
            mail7_api_key="valid_key",
        )
        pipeline.verifier.dry_run = False

        # Mock HTTP 500 internal server error
        resp_500 = MagicMock()
        resp_500.status_code = 500

        with patch("src.outreach.verification_client.requests.post", return_value=resp_500):
            res = pipeline.run(manual_file=lead_file, force=True)

        assert res["status"] == "VERIFICATION_PAUSED_API_ERROR"
        assert "provider_server_error" in res["reason"]

        # Checkpoint must contain unresolved leads for resumption
        checkpoint = state_mgr.load_checkpoint(res["campaign_id"])
        assert checkpoint is not None
        assert set(checkpoint["unresolved_leads"]) == {"lead1@test.com", "lead2@test.com"}

        # No batches planned or sent
        batches = state_mgr.load_batches(res["campaign_id"])
        assert len(batches) == 0

    def test_outreach_does_not_report_empty_batches_as_sent(self, tmp_path):
        """
        If 0 leads are eligible for outreach, the pipeline halts safely,
        reports SKIPPED_ZERO_ELIGIBLE, and does NOT claim batches were sent.
        """
        state_file = tmp_path / "state.csv"
        batches_file = tmp_path / "batches.csv"
        state_mgr = CampaignState(state_file, batches_file)
        quota_ledger = QuotaLedger(tmp_path / "l.csv", tmp_path / "c.csv")
        supp_mgr = SuppressionManager(tmp_path / "supp.csv")

        # All leads in file are unsubscribed/suppressed
        lead_file = tmp_path / "leads.txt"
        lead_file.write_text("suppressed1@test.com\nsuppressed2@test.com\n")
        supp_mgr.add_suppression("suppressed1@test.com", "unsubscribed")
        supp_mgr.add_suppression("suppressed2@test.com", "unsubscribed")

        pipeline = OutreachPipeline(
            dry_run=True,
            state_mgr=state_mgr,
            quota_ledger=quota_ledger,
            suppression_mgr=supp_mgr,
        )

        res = pipeline.run(manual_file=lead_file, force=True)

        assert res["status"] == "SKIPPED_ZERO_ELIGIBLE"
        assert res["net_eligible_count"] == 0
        assert len(res["batches"]) == 0

        # State CSV must record 0 batches sent
        c = state_mgr.get_campaign(res["campaign_id"])
        assert c is not None
        assert c["status"] == "SKIPPED_ZERO_ELIGIBLE"
        assert c["batches_sent"] == "0"

    def test_eligible_recipients_distributed_to_9_senders(self, tmp_path):
        """
        When leads verify successfully, they are distributed to 9 senders and sent.
        """
        state_file = tmp_path / "state.csv"
        batches_file = tmp_path / "batches.csv"
        state_mgr = CampaignState(state_file, batches_file)
        quota_ledger = QuotaLedger(tmp_path / "l.csv", tmp_path / "c.csv")

        lead_file = tmp_path / "leads.txt"
        leads = [f"valid_creator_{i}@youtube.com" for i in range(18)]
        lead_file.write_text("\n".join(leads) + "\n")

        pipeline = OutreachPipeline(
            dry_run=True,
            state_mgr=state_mgr,
            quota_ledger=quota_ledger,
        )

        res = pipeline.run(manual_file=lead_file, force=True)

        assert res["overall_status"] == "COMPLETED"
        assert res["net_eligible_count"] == 18
        assert len(res["batches"]) == 9
        # 18 leads / 9 senders = 2 leads per sender
        assert all(b["count"] == 2 for b in res["batches"])
        assert all(b["status"] == "SENT" for b in res["batches"])
