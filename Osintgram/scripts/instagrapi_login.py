#!/usr/bin/env python3
"""One-time interactive login for the instagrapi backend.

Run this manually from a terminal (never from the web server) so any 2FA or
challenge prompt Instagram throws can be answered interactively:

    python scripts/instagrapi_login.py

On success it saves the session to config/instagrapi_session.json, which the
web app's instagrapi backend (src/instagrapi_backend.py) then loads without
ever attempting an interactive login itself.
"""
import configparser
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from instagrapi import Client

from src.instagrapi_backend import DEFAULT_SESSION_PATH, resolve_instagrapi_credentials


def challenge_code_handler(username, choice):
    return input(f"\nEnter verification code ({choice}) received for @{username}: ").strip()


def save_credentials(username: str, password: str, credentials_path: str = "config/credentials.ini"):
    try:
        path = Path(credentials_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        parser = configparser.ConfigParser(interpolation=None)
        if path.exists():
            parser.read(path)
        if not parser.has_section("Credentials"):
            parser.add_section("Credentials")
        parser.set("Credentials", "username", username)
        parser.set("Credentials", "password", password)
        with open(path, "w", encoding="utf-8") as f:
            parser.write(f)
    except Exception as e:
        print(f"Warning: Could not save credentials to {credentials_path}: {e}")


def main():
    username, password = resolve_instagrapi_credentials()
    if not username:
        username = input("Instagram username: ").strip()
    if not password:
        import getpass

        password = getpass.getpass("Instagram password: ")

    cl = Client()
    cl.challenge_code_handler = challenge_code_handler

    print(f"\nConnecting to Instagram as @{username}...")
    try:
        cl.login(username, password)
    except Exception as e:
        print(f"\nLogin failed: {e}")
        if "out of date" in str(e).lower() or "upgrade" in str(e).lower() or "challenge" in str(e).lower():
            print("\nTip: Instagram may block direct credential login for automated clients.")
            print("You can easily log in using your browser sessionid via: scripts/set_session.py")
        sys.exit(1)

    session_path = Path(DEFAULT_SESSION_PATH)
    session_path.parent.mkdir(parents=True, exist_ok=True)
    cl.dump_settings(session_path)
    save_credentials(username, password)
    print(f"\n[OK] Login successful! Session saved to {session_path}.")
    print("Osintgram backend will now use this saved session.")


if __name__ == "__main__":
    main()
