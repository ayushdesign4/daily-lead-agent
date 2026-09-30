"""Utility script to update GitHub Actions secrets via GitHub REST API with libsodium encryption."""

import sys
import base64
import argparse
import requests
from nacl import encoding, public


def update_github_secret(
    owner: str,
    repo: str,
    secret_name: str,
    secret_value: str,
    github_token: str,
) -> bool:
    """
    Encrypts secret_value using the repository's libsodium public key and
    updates the GitHub Actions repository secret via the GitHub REST API.
    """
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Step 1: Get repo public key
    key_url = f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/public-key"
    resp = requests.get(key_url, headers=headers)
    if resp.status_code != 200:
        print(f"Error fetching public key (HTTP {resp.status_code}): {resp.text}", file=sys.stderr)
        return False

    key_data = resp.json()
    public_key_b64 = key_data["key"]
    key_id = key_data["key_id"]

    # Step 2: Encrypt secret with public key using libsodium Box
    public_key = public.PublicKey(public_key_b64.encode("utf-8"), encoding.Base64Encoder)
    sealed_box = public.SealedBox(public_key)
    encrypted_bytes = sealed_box.encrypt(secret_value.encode("utf-8"))
    encrypted_b64 = base64.b64encode(encrypted_bytes).decode("utf-8")

    # Step 3: Put secret
    secret_url = f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/{secret_name}"
    payload = {
        "encrypted_value": encrypted_b64,
        "key_id": key_id,
    }

    put_resp = requests.put(secret_url, headers=headers, json=payload)
    if put_resp.status_code in (201, 204):
        print(f"Successfully updated GitHub Secret: {secret_name}")
        return True
    else:
        print(f"Failed to update secret (HTTP {put_resp.status_code}): {put_resp.text}", file=sys.stderr)
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update GitHub Actions Secret")
    parser.add_argument("--owner", required=True, help="GitHub repository owner/username")
    parser.add_argument("--repo", required=True, help="GitHub repository name")
    parser.add_argument("--secret-name", default="APIFY_API_TOKEN", help="Secret name to update")
    parser.add_argument("--secret-value", required=True, help="New secret value")
    parser.add_argument("--github-token", required=True, help="GitHub Personal Access Token with repo secret permissions")

    args = parser.parse_args()
    success = update_github_secret(
        owner=args.owner,
        repo=args.repo,
        secret_name=args.secret_name,
        secret_value=args.secret_value,
        github_token=args.github_token,
    )
    sys.exit(0 if success else 1)
