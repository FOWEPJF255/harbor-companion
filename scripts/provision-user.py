"""Provision a user without placing a password in arguments, logs, or .env."""
import argparse
import asyncio
import getpass
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from harbor.store import Store
from harbor.user_auth import UserAuth


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True)
    parser.add_argument("--database", type=Path, default=ROOT / "data" / "harbor.sqlite3")
    parser.add_argument("--adult-confirmed", action="store_true", help="The intended user has explicitly confirmed they are an adult.")
    args = parser.parse_args()
    if not args.adult_confirmed:
        parser.error("Use --adult-confirmed only after the intended user has confirmed adulthood.")
    password = getpass.getpass("New user password (at least 12 characters): ")
    if password != getpass.getpass("Confirm password: "):
        raise SystemExit("Passwords did not match; no account was created.")
    auth = UserAuth(Store(str(args.database)), SimpleNamespace(user_token_minutes=60, registration_enabled=False))
    try:
        user = await auth.provision(args.username, password, adult_confirmed=True)
    except ValueError as issue:
        raise SystemExit(str(issue)) from None
    print(f"User created: {user['username']} ({user['id']}). No login token was issued.")


if __name__ == "__main__":
    asyncio.run(main())
