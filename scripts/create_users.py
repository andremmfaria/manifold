#!/usr/bin/env python3
"""Bulk-create Manifold users through the REST API.

Admin credentials are sourced from environment variables (so it works straight off your
.env): ADMIN_USERNAME / ADMIN_PASSWORD. The script logs in as that superadmin and POSTs
each user in a JSON file to /api/v1/users.

Usage:
    python3 scripts/create_users.py [users.json]

Environment (read from the process env; the repo-root .env is auto-loaded if present):
    MANIFOLD_API_URL    Base URL of the backend API   (default: http://localhost:8000)
    ADMIN_USERNAME      Bootstrap superadmin username  (default: admin)
    ADMIN_PASSWORD      Bootstrap superadmin password  (required)
    ADMIN_NEW_PASSWORD  If the admin still must change its password on first login,
                        the script rotates ADMIN_PASSWORD -> ADMIN_NEW_PASSWORD and
                        continues. Without it, a forced password change aborts the run.

users.json format — a JSON array of objects:
    [
      {
        "username": "alice",
        "password": "s3cret!",
        "role": "regular",
        "email": "alice@example.com",
        "first_name": "Alice",
        "last_name": "Smith"
      },
      {"username": "bob", "password": "h0rse!", "role": "superadmin"}
    ]
  Only username + password are required; role defaults to "regular".
  email, first_name, and last_name are optional.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_USERS_FILE = REPO_ROOT / "scripts" / "users.json"


def load_dotenv(path: Path) -> None:
    """Populate os.environ from a .env file without overriding existing vars."""
    if not path.is_file():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def request(method: str, url: str, token: str | None = None, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            payload = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            payload = raw.decode(errors="replace")
        return exc.code, payload
    except urllib.error.URLError as exc:
        die(f"Cannot reach API at {url}: {exc.reason}")


def die(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(1)


def login(base_url: str, username: str, password: str) -> str:
    status, payload = request(
        "POST", f"{base_url}/api/v1/auth/login", body={"username": username, "password": password}
    )
    if status != 200:
        die(f"login failed for '{username}' ({status}): {payload}")
    return payload["access_token"]


def ensure_usable_admin(base_url: str, username: str, password: str) -> str:
    """Log in and resolve any forced first-run password change. Returns a usable token."""
    token = login(base_url, username, password)

    status, me = request("GET", f"{base_url}/api/v1/auth/me", token=token)
    if status != 200:
        die(f"could not read admin profile ({status}): {me}")

    if me.get("mustChangePassword"):
        new_password = os.environ.get("ADMIN_NEW_PASSWORD")
        if not new_password:
            die(
                "admin must change its password on first login. Set ADMIN_NEW_PASSWORD in the "
                "environment so the script can rotate it, or change it once in the UI."
            )
        status, payload = request(
            "PATCH",
            f"{base_url}/api/v1/auth/me/password",
            token=token,
            body={"current_password": password, "new_password": new_password},
        )
        if status != 204:
            die(f"password rotation failed ({status}): {payload}")
        print(f"rotated admin password for '{username}'; re-authenticating")
        token = login(base_url, username, new_password)

    return token


def load_users(path: Path) -> list[dict]:
    if not path.is_file():
        die(f"users file not found: {path} (see scripts/users.example.json)")
    try:
        users = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        die(f"invalid JSON in {path}: {exc}")
    if not isinstance(users, list):
        die(f"{path} must contain a JSON array of user objects")
    return users


def create_users(base_url: str, token: str, users: list[dict]) -> int:
    created = skipped = failed = 0
    for index, user in enumerate(users):
        username = user.get("username")
        password = user.get("password")
        if not username or not password:
            print(f"  [{index}] skipped: missing username/password")
            failed += 1
            continue
        body = {
            "username": username,
            "password": password,
            "role": user.get("role", "regular"),
            "email": user.get("email"),
            "first_name": user.get("first_name"),
            "last_name": user.get("last_name"),
        }
        if "must_change_password" in user:
            body["must_change_password"] = user["must_change_password"]

        status, payload = request("POST", f"{base_url}/api/v1/users", token=token, body=body)
        if status == 201:
            print(f"  created '{username}' (role={body['role']})")
            created += 1
        elif status in (400, 409):
            print(f"  skipped '{username}' (already exists / rejected): {payload}")
            skipped += 1
        else:
            print(f"  failed '{username}' ({status}): {payload}")
            failed += 1

    print(f"\nDone. created={created} skipped={skipped} failed={failed}")
    return 1 if failed else 0


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")

    base_url = os.environ.get("MANIFOLD_API_URL", "http://localhost:8000").rstrip("/")
    admin_user = os.environ.get("ADMIN_USERNAME", "admin")
    admin_password = os.environ.get("ADMIN_PASSWORD")
    if not admin_password:
        die("ADMIN_PASSWORD is not set (export it or put it in .env)")

    users_file = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_USERS_FILE
    users = load_users(users_file)
    if not users:
        print("no users to create")
        return 0

    print(f"API:   {base_url}")
    print(f"admin: {admin_user}")
    print(f"file:  {users_file}  ({len(users)} user(s))\n")

    token = ensure_usable_admin(base_url, admin_user, admin_password)
    return create_users(base_url, token, users)


if __name__ == "__main__":
    raise SystemExit(main())
