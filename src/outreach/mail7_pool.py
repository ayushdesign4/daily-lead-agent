"""Persistent 7-Account Mail7 API Key Pool with Sequential Rotation and Monthly Reset.

Rules:
1. Preferred order: Account 1 -> Account 2 -> ... -> Account 7.
2. Start with Account 1 on a new monthly cycle (IST).
3. Continue using the active account across daily runs (no daily reset).
4. Switch accounts only when confirmed exhausted (HTTP 402 or 403 quota exhaustion).
5. When exhausted, persist status and immediately continue with the next available account.
6. Never return to an exhausted account in the same monthly cycle.
7. If all 7 are exhausted, halt and preserve progress.
8. HTTP 401: Authentication failure, halt and alert user, do not burn other accounts.
9. Persistent state survives GitHub Actions restarts via data/mail7_pool_state.json.
10. Secrets: MAIL7_API_KEY_1 through MAIL7_API_KEY_7. Never expose secrets.
"""

from typing import List, Dict, Optional, Any, Union
from pathlib import Path
from dataclasses import dataclass
import os
import json
import logging
import hashlib
from datetime import datetime

from src.state_manager import get_today_ist_date
from src.outreach.config import (
    MAIL7_API_KEYS,
    MAIL7_POOL_STATE_FILE,
)

logger = logging.getLogger(__name__)


@dataclass
class Mail7Account:
    """Represents a single Mail7 account in the 7-account pool."""
    index: int  # 1 to 7
    api_key: Optional[str]
    name: str = ""
    account_id: str = ""
    secret_env_name: str = ""

    def __post_init__(self):
        if not self.name:
            self.name = f"Account {self.index}"
        if not self.account_id:
            self.account_id = f"mail7_account_{self.index}"
        if not self.secret_env_name:
            self.secret_env_name = f"MAIL7_API_KEY_{self.index}"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())


class Mail7AccountPool:
    """
    Manages the 7-account API key pool, persistent state, sequential rotation,
    and monthly reset.
    """

    TOTAL_ACCOUNTS: int = 7

    def __init__(
        self,
        keys: Optional[List[Optional[str]]] = None,
        state_file: Optional[Union[Path, str]] = None,
        today_ist_date: Optional[str] = None,
    ):
        if state_file is not None:
            self.state_file = Path(state_file)
        elif keys is not None:
            # Custom keys provided without explicit state_file: operate in-memory to isolate tests
            self.state_file = None
        else:
            # Default production mode: use persistent state file
            self.state_file = MAIL7_POOL_STATE_FILE

        # Load keys: prefer passed list, fallback to MAIL7_API_KEYS
        if keys is not None:
            raw_keys = list(keys)
        else:
            raw_keys = list(MAIL7_API_KEYS)

        # Pad with None to TOTAL_ACCOUNTS
        while len(raw_keys) < self.TOTAL_ACCOUNTS:
            raw_keys.append(None)
        raw_keys = raw_keys[:self.TOTAL_ACCOUNTS]

        # Construct Mail7Account objects (1-indexed: 1..7)
        self.accounts: Dict[int, Mail7Account] = {}
        for i, key in enumerate(raw_keys, 1):
            cleaned_key = key.strip() if key and isinstance(key, str) else None
            self.accounts[i] = Mail7Account(index=i, api_key=cleaned_key)

        # Load state and apply monthly reset check
        self.state: Dict[str, Any] = {}
        self._load_state()
        self._sync_key_fingerprints()
        self.reset_monthly_cycle_if_needed(today_ist_date=today_ist_date)

    def get_current_cycle(self, today_ist_date: Optional[str] = None) -> str:
        """Return the current monthly cycle identifier in IST (e.g. '2026-11')."""
        d = today_ist_date or get_today_ist_date()
        return d[:7]

    def _compute_key_fingerprint(self, key: Optional[str]) -> str:
        if not key:
            return ""
        return hashlib.sha256(key.strip().encode("utf-8")).hexdigest()[:16]

    def _sync_key_fingerprints(self) -> None:
        """Clear auth_failed or exhausted flags if a key has been replaced/updated."""
        key_fingerprints = self.state.setdefault("key_fingerprints", {})
        dirty = False
        for acc in self.accounts.values():
            idx_str = str(acc.index)
            curr_fp = self._compute_key_fingerprint(acc.api_key)
            prev_fp = key_fingerprints.get(idx_str)
            if prev_fp is not None and prev_fp != curr_fp:
                # Key was modified/updated
                if acc.index in self.state.get("auth_failed_accounts", []):
                    self.state["auth_failed_accounts"].remove(acc.index)
                    dirty = True
                if acc.index in self.state.get("exhausted_accounts", []):
                    self.state["exhausted_accounts"].remove(acc.index)
                    dirty = True
            key_fingerprints[idx_str] = curr_fp
        if dirty and self.state_file:
            self.save_state()

    def _load_state(self) -> None:
        """Load state from persistent JSON file or initialize default."""
        if self.state_file and self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    self.state = json.load(f)
                    return
            except Exception as e:
                logger.warning(f"Could not load Mail7 pool state from {self.state_file}: {e}")

        # Initialize fresh state
        current_cycle = self.get_current_cycle()
        self.state = {
            "version": 1,
            "monthly_cycle": current_cycle,
            "current_account_index": 1,
            "exhausted_accounts": [],
            "auth_failed_accounts": [],
            "last_successful_account": None,
            "key_fingerprints": {},
            "history": [
                {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "event": "POOL_INITIALIZED",
                    "account_index": 1,
                    "details": f"Initialized pool with monthly cycle {current_cycle}",
                }
            ],
        }

    def save_state(self) -> None:
        """Save state to persistent JSON file atomically."""
        if not self.state_file:
            return
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.state_file.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
            os.replace(temp_path, self.state_file)
        except Exception as e:
            logger.error(f"Failed to persist Mail7 pool state to {self.state_file}: {e}")

    def reset_monthly_cycle_if_needed(self, today_ist_date: Optional[str] = None) -> bool:
        """
        Check if calendar month has changed in IST.
        If changed, reset to Account 1 and clear exhausted account flags.
        Does NOT reset if current cycle matches.
        """
        current_cycle = self.get_current_cycle(today_ist_date)
        stored_cycle = self.state.get("monthly_cycle")

        if stored_cycle != current_cycle:
            logger.info(
                f"New monthly quota cycle detected: '{current_cycle}' (previous: '{stored_cycle}'). "
                "Resetting Mail7 account pool to Account 1 and clearing exhausted flags."
            )
            self.state["monthly_cycle"] = current_cycle
            self.state["current_account_index"] = 1
            self.state["exhausted_accounts"] = []
            self.state["auth_failed_accounts"] = []
            self.state.setdefault("history", []).append({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "event": "MONTHLY_RESET",
                "account_index": 1,
                "details": f"Monthly reset from {stored_cycle} to {current_cycle}",
            })
            self.save_state()
            return True
        return False

    def get_active_account(self) -> Optional[Mail7Account]:
        """
        Get the currently active account (1 to 7).
        If the current account index is exhausted or auth-failed,
        advances to the next available non-exhausted account.
        Returns None if all accounts are exhausted.
        """
        exhausted = set(self.state.get("exhausted_accounts", []))
        auth_failed = set(self.state.get("auth_failed_accounts", []))
        curr_idx = self.state.get("current_account_index", 1)

        # Check current account
        if curr_idx not in exhausted and curr_idx not in auth_failed:
            acc = self.accounts.get(curr_idx)
            if acc and acc.is_configured:
                return acc

        # Find next available account in sequential order (1 -> 2 -> ... -> 7)
        for idx in range(curr_idx, self.TOTAL_ACCOUNTS + 1):
            if idx not in exhausted and idx not in auth_failed:
                acc = self.accounts.get(idx)
                if acc and acc.is_configured:
                    if idx != curr_idx:
                        self.state["current_account_index"] = idx
                        self.save_state()
                    return acc

        return None

    def mark_account_exhausted(self, account_index: int, reason: str = "quota_exhausted") -> Optional[Mail7Account]:
        """
        Mark an account as confirmed exhausted for the current monthly cycle.
        Persists status immediately.
        Advances current_account_index to the next available account.
        Returns next Mail7Account if available, or None if all exhausted.
        """
        exhausted = self.state.setdefault("exhausted_accounts", [])
        if account_index not in exhausted:
            exhausted.append(account_index)

        self.state.setdefault("history", []).append({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event": "ACCOUNT_EXHAUSTED",
            "account_index": account_index,
            "reason": reason,
        })

        # Advance to next available account (account_index + 1 to 7)
        next_acc = None
        auth_failed = set(self.state.get("auth_failed_accounts", []))
        for idx in range(account_index + 1, self.TOTAL_ACCOUNTS + 1):
            if idx not in exhausted and idx not in auth_failed:
                candidate = self.accounts.get(idx)
                if candidate and candidate.is_configured:
                    next_acc = candidate
                    self.state["current_account_index"] = idx
                    break

        if not next_acc:
            logger.warning("All 7 Mail7 accounts in pool have been exhausted.")
        else:
            logger.info(f"Rotated to next Mail7 account: {next_acc.name} (Account {next_acc.index}).")

        self.save_state()
        return next_acc

    def mark_account_auth_failed(self, account_index: int, reason: str = "unauthorized_api_key") -> None:
        """
        Mark an account as authentication-failed (HTTP 401 or forbidden).
        Halts and does NOT silently consume other accounts without reporting.
        """
        auth_failed = self.state.setdefault("auth_failed_accounts", [])
        if account_index not in auth_failed:
            auth_failed.append(account_index)

        self.state.setdefault("history", []).append({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event": "AUTH_FAILED",
            "account_index": account_index,
            "reason": reason,
        })
        self.save_state()

    def record_success(self, account_index: int) -> None:
        """Record last successful account used."""
        self.state["last_successful_account"] = f"mail7_account_{account_index}"
        self.save_state()

    def is_all_exhausted(self) -> bool:
        """Check if all 7 accounts (or all configured accounts) are exhausted."""
        exhausted = set(self.state.get("exhausted_accounts", []))
        configured_indices = [idx for idx, acc in self.accounts.items() if acc.is_configured]
        if not configured_indices:
            return True
        return all(idx in exhausted for idx in configured_indices)

    def get_status_summary(self) -> Dict[str, Any]:
        """Return human-readable status of the 7-account pool."""
        exhausted = set(self.state.get("exhausted_accounts", []))
        auth_failed = set(self.state.get("auth_failed_accounts", []))
        curr_idx = self.state.get("current_account_index", 1)

        accounts_status = []
        for idx in range(1, self.TOTAL_ACCOUNTS + 1):
            acc = self.accounts.get(idx)
            is_conf = acc.is_configured if acc else False
            if idx in exhausted:
                st = "EXHAUSTED"
            elif idx in auth_failed:
                st = "AUTH_FAILED"
            elif not is_conf:
                st = "NOT_CONFIGURED"
            elif idx == curr_idx:
                st = "ACTIVE"
            elif idx < curr_idx:
                st = "PREVIOUS"
            else:
                st = "STANDBY"

            accounts_status.append({
                "account_index": idx,
                "name": f"Account {idx}",
                "status": st,
                "secret_env_name": f"MAIL7_API_KEY_{idx}",
                "is_configured": is_conf,
            })

        return {
            "monthly_cycle": self.state.get("monthly_cycle"),
            "current_account_index": curr_idx,
            "total_accounts": self.TOTAL_ACCOUNTS,
            "active_account_configured": bool(self.get_active_account()),
            "accounts": accounts_status,
        }
