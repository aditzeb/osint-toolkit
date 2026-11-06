#!/usr/bin/env python3
"""Save an active Instagram web session via sessionid."""
import configparser
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from instagrapi import Client


def save_credentials_if_needed(username: str, credentials_path: str = "config/credentials.ini"):
    try:
        path = Path(credentials_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        parser = configparser.ConfigParser(interpolation=None)
        if path.exists():
            parser.read(path)
        if not parser.has_section("Credentials"):
            parser.add_section("Credentials")
        if not parser.get("Credentials", "username", fallback=""):
            parser.set("Credentials", "username", username)
        if not parser.get("Credentials", "password", fallback=""):
            parser.set("Credentials", "password", "session_authenticated")
        with open(path, "w", encoding="utf-8") as f:
            parser.write(f)
    except Exception as e:
        print(f"Warning: Could not update {credentials_path}: {e}")


def main():
    if len(sys.argv) > 1:
        sid = sys.argv[1].strip()
    else:
        print("To find your sessionid cookie:")
        print("1. Open instagram.com in Chrome/Edge/Firefox and log in.")
        print("2. Press F12 -> Application (or Storage) -> Cookies -> https://www.instagram.com")
        print("3. Copy the value of the 'sessionid' cookie.\n")
        sid = input("Paste your Instagram sessionid: ").strip()

    # Fix accidental double paste
    if len(sid) > 60 and len(sid) % 2 == 0 and sid[: len(sid) // 2] == sid[len(sid) // 2 :]:
        sid = sid[: len(sid) // 2]
        print("Detected and corrected double-pasted sessionid.")

    cl = Client()
    try:
        cl.login_by_sessionid(sid)
        out = Path("config/instagrapi_session.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        cl.dump_settings(out)
        save_credentials_if_needed(cl.username or "instagram_user")
        print(f"\n[OK] Successfully logged in as @{cl.username} (ID: {cl.user_id})!")
        print(f"[OK] Session saved to: {out}")
        print("Osintgram backend will now use this session.")
    except Exception as e:
        print(f"\n[Error] Login with sessionid failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
